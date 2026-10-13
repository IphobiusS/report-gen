from pathlib import Path
import hashlib,json,zipfile
import fitz
from lxml import etree,html
import argparse,sys
p=argparse.ArgumentParser();p.add_argument("--tool",type=Path,required=True);p.add_argument("--before",type=Path,required=True);p.add_argument("--after",type=Path,required=True);p.add_argument("--project",type=Path,required=True);p.add_argument("--out",type=Path,required=True);args=p.parse_args()
sys.path.insert(0,str(args.tool.resolve()))
import project_history as history
import engine
import delivery
from safe_markup import md
from resources import relative_image
import tempfile
old=args.before;new=args.after
result={}
for name in ('nimbus-weasyprint.pdf','nimbus-chromium.pdf'):
 a=fitz.open(old/name);b=fitz.open(new/name)
 equal=[a[i].get_pixmap().samples==b[i].get_pixmap().samples for i in range(min(len(a),len(b)))]
 result[name]={'old_pages':len(a),'new_pages':len(b),'pixels_identical':len(a)==len(b) and all(equal),'different_pages':[i+1 for i,v in enumerate(equal) if not v]}
def word_parts(path):
 with zipfile.ZipFile(path) as z:parts={n:z.read(n) for n in z.namelist() if n.startswith('word/')}
 tree=etree.fromstring(parts['word/document.xml'])
 for node in tree.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/picture}cNvPr'):
  if (node.get('name') or '').startswith('tmp'):node.set('name','temporary-chart.png')
 parts['word/document.xml']=etree.tostring(tree)
 return parts
result['docx_parts_identical_except_temporary_chart_name']=word_parts(old/'nimbus.docx')==word_parts(new/'nimbus.docx')
with zipfile.ZipFile(new/'nimbus-markdown.zip') as z:
 source=z.read('report.md').decode();tree=html.fragment_fromstring(str(md(source,img_base='')),create_parent='div')
 with tempfile.TemporaryDirectory() as capture_temp:
  captured=delivery.capture(args.project,Path(capture_temp)/'snapshot')
  inspection=delivery.inspect_export(new/'nimbus-markdown.zip','md',captured)
 result['markdown_image_count']=inspection['images_verified']
 result['markdown_generated_chart_count']=inspection.get('generated_charts_verified',0)
 result['markdown_contract_checks']=inspection
 result['markdown_references_resolve']=all(relative_image(src).as_posix() in z.namelist() for src in tree.xpath('.//img/@src'))
with tempfile.TemporaryDirectory() as temp:
 dest=Path(temp)/'restored';history.import_bundle((new/'nimbus-completo-proyecto.zip').read_bytes(),dest)
 orig=args.project
 result['editable_backup_same_data']=engine.load_engagement(orig/'engagement.yaml')==engine.load_engagement(dest/'engagement.yaml')
 names=[p.relative_to(orig) for p in orig.rglob('*.png') if 'history' not in p.parts]
 result['editable_backup_same_images']=all((orig/n).read_bytes()==(dest/n).read_bytes() for n in names)
result['source_sha256']=hashlib.sha256((args.project/'engagement.yaml').read_bytes()).hexdigest()
args.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
