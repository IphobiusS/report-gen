import argparse, json, sys, tempfile, copy
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--tool',required=True);p.add_argument('--out',required=True);a=p.parse_args()
sys.path[:0]=[a.tool,str(Path(a.tool)/'webapp')]
import evidence, validate, workflows, engine
from safe_markup import md
from lxml import html
from exporters.markdown import to_markdown
from exporters.docx import to_docx
from PIL import Image

def codes(text):
 t=html.fragment_fromstring(str(md(text)),create_parent='div'); return [n.text_content() for n in t.xpath('.//code')]
results={}
base='![Real](img/shot.png)\n\n'
cases={
 'prose':'El archivo img/shot.png fue capturado antes del cambio.',
 'link':'[Descargar la captura](img/shot.png)',
 'quote_code':'>     cat img/shot.png',
 'nested_list_code':'- Evidencia\n\n        cat img/shot.png',
 'double_slash_inline':r'\\`img/shot.png`',
 'ref_label':'![img/shot.png]\n\n[img/shot.png]: img/shot.png',
 'multiline_indent':'    cat img/shot.png\n    echo img/shot.png',
 'escaped_code':r'\`img/shot.png\`',
}
for k,v in cases.items():
 before=base+v; after=evidence.replace_references({'body':before},'img/shot.png','img/masked.png')['body']
 results[k]={'before':before,'after':after,'codes_before':codes(before),'codes_after':codes(after),'same_literals':codes(before)==codes(after)}
D={'meta':{'report_title':'Audit','lang':'es','theme':'corporativo'},'findings':[{'id':'F1','title':'Proof','severity':'info','cvss':0}]}
with tempfile.TemporaryDirectory() as d:
 d=Path(d);(d/'img').mkdir();Image.new('RGB',(10,10),'red').save(d/'img/shot.png')
 review={}
 for name,text in {'literal':'`![Example](img/missing.png)`','reference':'![Required][proof]\n\n[proof]: img/missing.png','remote':'![Required](https://invalid.example/missing.png)'}.items():
  data=copy.deepcopy(D); data['findings'][0]['description_md']=text
  review[name]=[r for r in workflows.review(data,d) if r['level']=='error']
 results['review']=review
 variants={
  'null_assessor':lambda v:v['meta'].update(assessor=None),
  'null_overview':lambda v:v['meta'].update(overview=None),
  'text_overview':lambda v:v['meta'].update(overview='test'),
  'list_confidentiality':lambda v:v['meta'].update(confidentiality_md=['text']),
  'numeric_host':lambda v:v['findings'][0].update(mode='machine',host={'name':123}),
  'null_caption':lambda v:v['findings'][0].update(walkthrough=[{'figure':{'src':'img/shot.png','caption':None}}]),
  'numeric_wordmark':lambda v:v['meta'].update(branding={'wordmark':123}),
  'list_email':lambda v:v['meta'].update(email=['example']),
 }
 types={}
 for name,mutate in variants.items():
  data=copy.deepcopy(D);mutate(data); errors=[x for x in validate.validate(data) if x[0]=='error']
  case={'errors':errors,'outputs':{}}
  if not errors:
   for fmt,fn in [('md',lambda:to_markdown(copy.deepcopy(data),data['meta'],engine.load_lang('es'),d)),('docx',lambda:to_docx(copy.deepcopy(data),data['meta'],engine.load_lang('es'),d,d/f'{name}.docx'))]:
    try:fn();case['outputs'][fmt]='ok'
    except Exception as e:case['outputs'][fmt]=type(e).__name__+': '+str(e)
  types[name]=case
 results['types']=types
Path(a.out).write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(results,ensure_ascii=False,indent=2))
