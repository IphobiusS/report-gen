"""Audit the same Nimbus input against native outputs without modifying either."""
from pathlib import Path
import argparse
from collections import Counter
import hashlib
import json
import re
import sys
import unicodedata
import zipfile

import fitz
from lxml import etree, html
import markdown
from PIL import Image
from pypdf import PdfReader
import yaml

parser=argparse.ArgumentParser()
parser.add_argument('--tool',type=Path,required=True)
parser.add_argument('--project',type=Path,required=True)
parser.add_argument('--outputs',type=Path,required=True)
parser.add_argument('--result',type=Path,required=True)
args=parser.parse_args()
sys.path[:0]=[str(args.tool),str(args.tool/'webapp')]
import validate
import workflows
from resources import restricted_fetcher

project=args.project; out=args.outputs
raw=(project/'engagement.yaml').read_bytes(); data=yaml.safe_load(raw)
checks=[]
def check(name,condition,detail=None):
    checks.append({'check':name,'passed':bool(condition),'detail':detail})
def norm(text):
    return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(text))).replace('\u00ad','')
def md_parts(source):
    tree=html.fragment_fromstring(markdown.markdown(str(source),extensions=['fenced_code','tables']),create_parent='div')
    for node in tree.xpath('.//img'):
        node.tail=(node.get('alt') or '')+(node.tail or '')
    leaves=tree.xpath('.//p|.//li[not(p)]|.//th|.//td|.//pre|.//h1|.//h2|.//h3|.//h4')
    if not leaves: return [tree.text_content()]
    return [x.text_content() for x in leaves if x.text_content().strip()]

validate.require_valid(data,final=True)
issues=workflows.review(data,project)
check('Native final validation',True)
from datetime import date
expected_due={f'findings[{i}].due_date' for i,f in enumerate(data['findings']) if f.get('due_date') and f['due_date']<date.today().isoformat() and f.get('status','open') not in ('verified_fixed','accepted')}
expected_coverage={'coverage[16].status','coverage[19].status','coverage[21].status'}
check('Only documented coverage limits and calendar-based overdue dates',{x['path'] for x in issues}==expected_due|expected_coverage and all(x['level']=='warning' for x in issues),issues)

expected=[]
def add(path,value,md=False):
    if value in (None,''):return
    for i,text in enumerate(md_parts(value) if md else [str(value)]):
        if norm(text): expected.append({'path':path+(f'#{i}' if md else ''),'text':text})
for k in ['report_title','report_subtitle','client','assessor','assessor_title','date','version','osid','email']:
    add('meta.'+k,data['meta'].get(k))
for i,section in enumerate(data['report']['sections']):
    for key,value in section.items():
        if key=='key':continue
        path=f'report.sections[{i}].{key}'
        if isinstance(value,str):add(path,value,md=key!='title')
        elif isinstance(value,list):
            for j,row in enumerate(value):
                if isinstance(row,dict):
                    for k,v in row.items():add(f'{path}[{j}].{k}',v)
                else:add(f'{path}[{j}]',row)
for i,scope in enumerate(data['meta']['scope']):
    for k,v in scope.items():add(f'meta.scope[{i}].{k}',v)
for i,finding in enumerate(data['findings']):
    path=f'findings[{i}]'
    for key in ['id','title','cwe','affected','cvss_vector']:
        add(path+'.'+key,finding.get(key))
    for key in ['description_md','impact_md','remediation_md']:
        add(path+'.'+key,finding.get(key),md=True)
    for j,value in enumerate(finding.get('references',[])):add(f'{path}.references[{j}]',value)
    for j,step in enumerate(finding.get('walkthrough',[])):
        for key in ['lead','text_md','command']:
            add(f'{path}.walkthrough[{j}].{key}',step.get(key),md=key=='text_md')
    for key,value in finding.get('remediation_summary',{}).items():add(path+'.remediation_summary.'+key,value,md=True)
    add(path+'.owner',finding.get('owner'));add(path+'.due_date',finding.get('due_date'))
    for j,retest in enumerate(finding.get('retests',[])):
        for key in ['tested_on','assessor','notes_md']:
            add(f'{path}.retests[{j}].{key}',retest.get(key),md=key=='notes_md')
for group in ['assets','coverage','evidence']:
    for i,item in enumerate(data[group]):
        for key in {'assets':['name','target','kind','notes'],'coverage':['test','notes'],'evidence':['caption']}[group]:
            add(f'{group}[{i}].{key}',item.get(key))
add('limitations_md',data.get('limitations_md'),md=True)

texts={}; docs={}; text_variants={}
for backend in ['weasyprint','chromium']:
    doc=fitz.open(out/f'nimbus-{backend}.pdf');docs[backend]=doc
    texts[backend]='\n'.join(page.get_text(sort=True) for page in doc)
    # PDF drawing order differs from reading order. Running headers can also
    # interrupt a paragraph across pages. Check both orders, with and without
    # running matter; do not treat insertion of a label as lost content.
    text_variants[backend]=[texts[backend], '\n'.join(p.get_text(sort=False) for p in doc)]
    for sort in (False,True):
        text_variants[backend].append('\n'.join(p.get_text(sort=sort,clip=fitz.Rect(0,52,p.rect.width,p.rect.height-45)) for p in doc))
with zipfile.ZipFile(out/'nimbus.docx') as z:
    root=etree.fromstring(z.read('word/document.xml'))
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    texts['docx']='\n'.join(''.join(p.itertext()) for p in root.findall('.//w:p',ns))
    media={n:z.read(n) for n in z.namelist() if n.startswith('word/media/')}
    docx_rels=etree.fromstring(z.read('word/_rels/document.xml.rels'))
with zipfile.ZipFile(out/'nimbus-markdown.zip') as z:
    m=z.read('report.md').decode()
    texts['markdown']='\n'.join(md_parts(m))
    md_images={n:z.read(n) for n in z.namelist() if n!='report.md'}
    tree=html.fragment_fromstring(markdown.markdown(m,extensions=['fenced_code','tables']),create_parent='div')
    refs={node.get('src') for node in tree.xpath('.//img[@src]')}
    check('Markdown image references are complete',refs==set(md_images),{'references':len(refs),'embedded_files':len(md_images)})
    import publication
    check('Markdown images match clean publication derivatives',all(hashlib.sha256(b).digest()==hashlib.sha256(publication.clean_image((project/n).read_bytes())).digest() for n,b in md_images.items()))

texts['portable_html']=html.fromstring((out/'nimbus-portable.html').read_text()).xpath('string(//main)')
missing={}
for fmt,text in texts.items():
    flat=[norm(v) for v in text_variants.get(fmt,[text])]
    missing[fmt]=[item for item in expected if not any(norm(item['text']) in variant for variant in flat)]
    check('Content coverage '+fmt,not missing[fmt],{'fragments':len(expected),'missing':missing[fmt]})

source_images={p.name:p for p in (project/'img').iterdir() if p.is_file()}
def pixels(im):
    im=im.convert('RGB');return (im.size,hashlib.md5(im.tobytes()).hexdigest())
source_pixels=Counter(pixels(Image.open(p)) for p in source_images.values())
from io import BytesIO
word_pixels=Counter(pixels(Image.open(BytesIO(b))) for b in media.values())
check('DOCX preserves pixels of all 19 project images',all(word_pixels[x]>=n for x,n in source_pixels.items()),{'source':sum(source_pixels.values()),'docx':sum(word_pixels.values())})

pagination={}
for backend,doc in docs.items():
    reader=PdfReader(out/f'nimbus-{backend}.pdf')
    names=reader.named_destinations
    def destination_page(key):
        target=names.get(key) or names.get('/'+key)
        return reader.get_destination_page_number(target)+1 if target is not None else None
    tree=html.fromstring((out/f'nimbus-{backend}.html').read_text())
    rows=[]
    for link in tree.xpath('//ul[@class="toc-list"]/li/a'):
        key=link.get('href')[1:]; shown=int(link.xpath('.//span[@class="pg"]')[0].text_content())
        actual=destination_page(key)
        rows.append({'target':key,'shown':shown,'actual':actual})
    for row in tree.xpath('//table[@class="sumtable"]/tbody/tr'):
        cells=row.xpath('./td');title=cells[2].text_content().strip()
        f=next(f for f in data['findings'] if f['title']==title)
        # Chromium writes destinations for hyperlinks, not every HTML id.
        # Verify the visible finding heading against the actual PDF independently
        # of the generator's hidden pagination markers and HTML page labels.
        start=destination_page('findings'); end=destination_page('attack_narrative')
        matches=[i for i,p in enumerate(doc,1) if start <= i < end
                 and norm(f['title']) in norm(p.get_text())]
        actual=matches[0] if len(matches)==1 else None
        rows.append({'target':f['id'],'shown':int(cells[3].text_content()),'actual':actual,
                     'heading_matches':matches})
    check('TOC and finding page references '+backend,len(rows)==26 and all(x['shown']==x['actual'] for x in rows),rows)
    page_issues=[]
    for i,page in enumerate(doc,1):
        for b in page.get_text('dict')['blocks']:
            if b['type']==0:
                for line in b['lines']:
                    for span in line['spans']:
                        x0,y0,x1,y1=span['bbox']
                        if span['text'].strip() and (x0<0 or y0<0 or x1>page.rect.width+1 or y1>page.rect.height+1):
                            page_issues.append({'page':i,'text':span['text'],'bbox':span['bbox']})
        for im in page.get_image_info():
            if not page.rect.contains(fitz.Rect(im['bbox'])):page_issues.append({'page':i,'image':im['bbox']})
    check('Text and images remain inside pages '+backend,not page_issues,page_issues[:12])
    check('Fictional status and pagination on every body page '+backend,all('DEMO' in p.get_text() and norm(f'Página {i} de {len(doc)}') in norm(p.get_text()) for i,p in enumerate(doc,1) if i>1))
    check('No internal page markers '+backend,'PGMK' not in texts[backend])
    embedded=[]
    for page in doc:
        for im in page.get_image_info(hashes=True,xrefs=True):
            pix=fitz.Pixmap(doc,im['xref'])
            if pix.alpha:pix=fitz.Pixmap(pix,0)
            if pix.colorspace.n!=3:pix=fitz.Pixmap(fitz.csRGB,pix)
            embedded.append(((pix.width,pix.height),hashlib.md5(pix.samples).hexdigest()))
    check('PDF preserves every image pixel '+backend,Counter(embedded)==source_pixels,{'source':len(source_images),'placements':len(embedded),'missing':list((source_pixels-Counter(embedded)).elements())})
    pagination[backend]={'pages':len(doc),'images':len(embedded),'bytes':(out/f'nimbus-{backend}.pdf').stat().st_size}

# The actual WeasyPrint layout tree catches overflow within table cells even
# when the text remains somewhere on the physical page.
from weasyprint import HTML
from weasyprint.formatting_structure.boxes import TableCellBox,TextBox
layout=HTML(string=(out/'nimbus-weasyprint.html').read_text(),base_url=str(project),url_fetcher=restricted_fetcher(project,args.tool/'themes')).render()
bad=[]; cells=0
for pn,page in enumerate(layout.pages,1):
    for cell in page._page_box.descendants():
        if not isinstance(cell,TableCellBox):continue
        cells+=1;left=cell.border_box_x();right=left+cell.border_width()
        for child in cell.descendants():
            if isinstance(child,TextBox) and child.text.strip() and (child.position_x<left-.7 or child.position_x+child.width>right+.7):
                bad.append({'page':pn,'text':child.text,'cell':[left,right],'text_box':[child.position_x,child.width]})
check('All rendered table cells contain their text',not bad,{'cells':cells,'overflow':bad[:20]})

check('YAML unchanged by all exports',(project/'engagement.yaml').read_bytes()==raw)
from version import __version__ as version
result={'tool_version':version,'source_sha256':hashlib.sha256(raw).hexdigest(),'source_fragments':len(expected),'pagination':pagination,'checks':checks,'passed':all(x['passed'] for x in checks)}
args.result.parent.mkdir(parents=True,exist_ok=True)
args.result.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'checks':len(checks),'passed':result['passed'],'missing_counts':{k:len(v) for k,v in missing.items()},'failures':[x['check'] for x in checks if not x['passed']]},ensure_ascii=False,indent=2))
sys.exit(0 if result['passed'] else 1)
