#!/usr/bin/env python3
"""Native QA only: preserve mixed-script link labels and exact click targets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZipFile
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def contract(path):
    with ZipFile(path) as archive:
        root=ET.fromstring(archive.read('word/document.xml'))
        rels=ET.fromstring(archive.read('word/_rels/document.xml.rels'))
    targets={n.get('Id'):n.get('Target') for n in rels if n.get('Type','').endswith('/hyperlink')}
    rows=[]
    for p in root.findall('.//'+W+'body//'+W+'p'):
        chars=[]; links=[]; fields=[]
        def destination(code):
            m=re.search(r'\bHYPERLINK\s+"([^"\r\n]*)"(?:\s+\\l\s+"([^"\r\n]*)")?',code)
            return (m[1]+('#'+m[2] if m[2] is not None else '')) if m else None
        def visit(n,target=None):
            if n.tag in (W+'pPr',W+'rPr'): return
            if n.tag==W+'hyperlink': target=targets.get(n.get(R+'id'))
            if n.tag==W+'fldSimple': target=destination(n.get(W+'instr',''))
            if n.tag==W+'fldChar':
                kind=n.get(W+'fldCharType')
                if kind=='begin':fields.append({'code':'','result':False})
                elif kind=='separate':fields[-1]['result']=True
                elif kind=='end':fields.pop()
                return
            if n.tag==W+'instrText':
                if fields:fields[-1]['code']+=n.text or ''
                return
            if fields:
                target=next((destination(f['code']) for f in reversed(fields) if f['result'] and destination(f['code'])),target)
            value=(n.text or '') if n.tag==W+'t' else '\t' if n.tag==W+'tab' else '\n' if n.tag in (W+'br',W+'cr') else None
            if value is not None:
                if fields and not all(f['result'] for f in fields): return
                chars.extend(value);links.extend([target]*len(value));return
            for child in n:visit(child,target)
        visit(p)
        if fields:raise ValueError('unclosed field')
        if chars:rows.append({'text':''.join(chars),'targets':links})
    return rows

def compare(source,saved):
    a,b=contract(source),contract(saved)
    return {'text_exact':[r['text'] for r in a]==[r['text'] for r in b],
            'character_targets_exact':a==b,'source_sha256':sha(source),'saved_sha256':sha(saved),
            'linked_characters_before':sum(t is not None for r in a for t in r['targets']),
            'linked_characters_after':sum(t is not None for r in b for t in r['targets'])}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--executable',required=True)
    parser.add_argument('--uno-python')
    parser.add_argument('--manifest',type=Path)
    a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((a.manifest or a.fixtures.parent/'manifest.json').read_text())
    results={'renderer':subprocess.check_output([a.executable,'--version'],text=True).strip(),'cases':[],'status':'running'}
    def convert(source,out,extension):
        out.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='rg-unicode-native-') as profile:
            command=[a.executable,'-env:UserInstallation='+Path(profile).as_uri(),'--headless','--nologo','--norestore','--convert-to',extension,'--outdir',str(out),str(source)]
            process=subprocess.run(command,capture_output=True,text=True,timeout=90,env={**os.environ,'SAL_USE_VCLPLUGIN':'svp'})
        expected=out/(source.stem+('.docx' if extension.startswith('docx') else '.pdf'))
        (out/(source.stem+'-'+extension.split(':')[0]+'.json')).write_text(json.dumps({'command':command,'returncode':process.returncode,'stdout':process.stdout,'stderr':process.stderr},indent=2)+'\n')
        if process.returncode or not expected.is_file():raise RuntimeError('Native conversion failed: '+str(expected))
        return expected
    try:
        for item in manifest['cases']:
            source=a.fixtures/item['file']
            if sha(source)!=item['sha256']:raise ValueError('Fixture hash mismatch')
            case={'variant':item['variant'],'expected':item['expected'],'stages':[]};results['cases'].append(case)
            convert(source,a.output/item['variant']/'source','pdf:writer_pdf_Export')
            current=source
            for stage in ('saved','reopened'):
                folder=a.output/item['variant']/stage
                current=convert(current,folder,'docx:Office Open XML Text')
                pdf=convert(current,folder,'pdf:writer_pdf_Export')
                comparison=compare(source,current);comparison.update({'stage':stage,'pdf_sha256':sha(pdf)});case['stages'].append(comparison)
                if not comparison['text_exact']:raise ValueError('Native save changed literal source text')
                if comparison['character_targets_exact']!=(item['expected']=='pass'):raise ValueError('Unexpected association result for '+item['variant'])
            if sha(source)!=item['sha256']:raise ValueError('Native conversion mutated original')
        results['status']='passed'
    except Exception as error:
        results['status']='failed';results['error']=str(error);raise
    finally:
        (a.output/'validation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
