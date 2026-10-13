#!/usr/bin/env python3
"""Build real PDF/Word samples and the local gallery's WebP previews.
Uses the public export facade and synthetic, explicitly labelled sample data.
"""
import argparse
import json
import re
from pathlib import Path
import sys
import yaml
import fitz
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import design_library as lib
from design_samples import sample_data, general_sample_name
from report_designs import THEMES
import export

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--only',nargs='*')
parser.add_argument('--lang',choices=['es','en','pt'],default='es')
args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
previews=ROOT/'webapp/static/design-previews';results=[]
jobs=[(p,v) for p in lib.catalog()['profiles'] for v in lib.VARIANTS]+[({'id':t,'name':t,'general':True},'brand') for t in sorted(THEMES)]
for p,variant in jobs:
    ident=p['id']
    if args.only and ident not in args.only: continue
    folder=out/ident/variant;folder.mkdir(parents=True,exist_ok=True)
    data=sample_data(lib.profile('offsec-oscp') if p.get('general') else p,variant,args.lang)
    if p.get('general'):
        data['meta'].pop('design');data['meta']['theme']=ident
        data['meta']['report_subtitle']=general_sample_name(ident,args.lang)+' / '+{'es':'Muestra ficticia','en':'Fictional sample','pt':'Amostra fictícia'}[args.lang]
    source=folder/'engagement.yaml';source.write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False))
    pdf=export.export(source,'pdf',folder/'muestra.pdf')
    docx=export.export(source,'docx',folder/'muestra.docx')
    document=fitz.open(pdf)
    destinations=document.resolve_names()
    page_indices={'cover':0, **{label:destinations['sample-'+label]['page'] for label in ('summary','technical')}}
    assert all(0<=index<len(document) for index in page_indices.values()),(ident,variant,page_indices)
    text='\n'.join(page.get_text() for page in document)
    assert 'find ./evidence -type f -print' in text
    assert 'sha256sum ./evidence/session.txt' in text
    assert 'analista@example.test' in document[0].get_text()
    # Metadata must stay in the lower third, independent of layout/variant.
    dates=document[0].search_for('2026-10-03')
    assert dates and min(r.y0 for r in dates)>document[0].rect.height*.68,(ident,variant,dates)
    dest=previews/ident/(args.lang if args.lang!='es' else '');dest.mkdir(parents=True,exist_ok=True)
    for label,index in page_indices.items():
        pix=document[index].get_pixmap(matrix=fitz.Matrix(1.3,1.3),alpha=False)
        im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
        im.save(dest/(variant+'-'+label+'.webp'),'WEBP',quality=86)
    results.append({'id':ident,'variant':variant,'lang':args.lang,'pdf_pages':len(document),'docx':str(docx.relative_to(out)),'preview_pages':page_indices,'checks':['named_destinations','code_preserved','cover_fields','lower_metadata']})
    print(ident,variant,'PASS',flush=True)
(out/'generation.json').write_text(json.dumps(results,indent=2)+'\n')
# Contact sheets are review aids; every thumbnail derives from an actual exported PDF.
font=ImageFont.truetype(str(ROOT/'exporters/fonts/DejaVuSans.ttf'),16)
for provider in dict.fromkeys([p['provider'] for p in lib.catalog()['profiles']]+['General']):
    group=re.sub(r'[^a-z0-9]+','-',provider.lower()).strip('-')
    ids=[p['id'] for p in lib.catalog()['profiles'] if p['provider']==provider] if group!='general' else sorted(THEMES)
    for variant in ('brand','quiet') if group!='general' else ('brand',):
        available=[(ident,previews/ident/(args.lang if args.lang!='es' else '')/(variant+'-cover.webp')) for ident in ids if (previews/ident/(args.lang if args.lang!='es' else '')/(variant+'-cover.webp')).exists()]
        if not available:continue
        cols=4;cellw=245;cellh=356
        sheet=Image.new('RGB',(cols*cellw,((len(available)+cols-1)//cols)*cellh),'#E8ECF0');draw=ImageDraw.Draw(sheet)
        for n,(ident,path) in enumerate(available):
            im=Image.open(path);im.thumbnail((221,310));x=(n%cols)*cellw+12;y=(n//cols)*cellh+12
            sheet.paste(im,(x,y));draw.text((x,y+318),ident,font=font,fill='#182B3B')
        sheet.save(out/(group+'-'+variant+'.png'))
