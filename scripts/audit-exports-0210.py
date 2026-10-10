"""Reproducible offline export audit and bounded stress corpus.

Run with an empty output directory. An optional previously redacted project
backup can be supplied with --project; it is never included in the code release.
"""
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import argparse
import json
import shutil
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import delivery
import engine
import export
import export_formats
import project_history
import validate
from wizard import dump_yaml


def run(args):
    target=Path(args.output).resolve()
    if target.exists() and any(target.iterdir()): raise ValueError('Use an empty output directory')
    target.mkdir(parents=True,exist_ok=True)
    record={'cases':[], 'stress':[], 'offline':True}
    def save(): (target/'results.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    cases=[]
    for name in ('quality-lab','nimbus'):
        original=ROOT/'examples'/name
        if original.is_dir():
            copy=target/name/'source';shutil.copytree(original,copy);cases.append((name,copy))
        elif name=='nimbus':
            copy=target/name/'source';copy.parent.mkdir(parents=True)
            project_history.import_bundle((ROOT/'examples/nimbus-demo-project.zip').read_bytes(),copy)
            cases.append((name,copy))
    if args.project:
        source=target/'historical-redacted'/'source'
        source.parent.mkdir(parents=True)
        project_history.import_bundle(Path(args.project).read_bytes(),source)
        cases.append(('historical-redacted',source))
    for name,source in cases:
        case={'case':name,'exports':{}};record['cases'].append(case)
        data=engine.load_engagement(source/'engagement.yaml')
        case['findings']=len(data.get('findings',[]))
        snapshot=source.parent/'snapshot';captured=delivery.capture(source,snapshot)
        case['content_contract']={key:len(value) for key,value in captured['contract'].items() if isinstance(value,list)}
        for fmt,spec in export_formats.REGISTRY.items():
            begin=time.perf_counter();path=export.export(source/'engagement.yaml',fmt,source.parent/spec.filename)
            checks=delivery.inspect_export(path,fmt,captured)
            # Fictitious sensitive controls must not reach any public artifact.
            from export_contract import profile
            text=profile(path,fmt)['text']
            assert 'PRIVATE_CAPTURE_AUDIT_0210' not in text
            assert 'SYNTHETIC_SECRET_AUDIT_0210' not in text
            case['exports'][fmt]={'seconds':round(time.perf_counter()-begin,3),'bytes':path.stat().st_size,
                                  'sha256':sha256(path.read_bytes()).hexdigest(),'checks':checks}
            save();print(name,fmt,case['exports'][fmt],flush=True)
        (source.parent/'editable-project.zip').write_bytes(project_history.export_bundle(source))
        bundle=delivery.build(snapshot,list(export_formats.REGISTRY),'audit-copy',name,captured,source.parent/'delivery')
        (source.parent/'delivery.zip').write_bytes(bundle)
        # Verify all manifest entries, not merely the ZIP CRCs.
        with zipfile.ZipFile(source.parent/'delivery.zip') as package:
            manifest=json.loads(package.read('verificacion.json'))
            assert all(sha256(package.read(k)).hexdigest()==v['sha256'] for k,v in manifest['files'].items())
        case['delivery_hashes_verified']=len(manifest['files']);save()
    if args.stress:
        base={'meta':{'report_title':'Carga sintética','lang':'es','theme':'corporativo','report_density':'compact'},
              'report':{'sections':[{'key':'findings_summary'},{'key':'findings'}]},'findings':[]}
        for size in (100,1000):
            data=deepcopy(base)
            data['findings']=[{'id':f'F{i:04d}','title':f'Caso sintético {i}', 'mode':'vuln',
                'description_md':f'Contenido sintético {i}.\n\n| Campo | Valor |\n| --- | --- |\n| Caso | {i} |',
                'impact_md':'Sin objetivo real.','remediation_md':'1. Documentar\n2. Comprobar',
                'walkthrough':[{'command':f'COMANDO_LITERAL_{i:04d} --ejemplo'}]} for i in range(size)]
            directory=target/f'stress-{size}';directory.mkdir();dump_yaml(data,directory/'engagement.yaml')
            begin=time.perf_counter();validate.require_valid(data,final=True)
            validation_ms=round((time.perf_counter()-begin)*1000,2)
            captured=delivery.capture(directory,directory/'snapshot')
            for fmt in (['pdf','html','md','docx'] if size==100 else ['html','md','docx']):
                begin=time.perf_counter();path=export.export(directory/'engagement.yaml',fmt,directory/export_formats.get(fmt).filename)
                checks=delivery.inspect_export(path,fmt,captured)
                item=dict(findings=size,format=fmt,validation_ms=validation_ms,seconds=round(time.perf_counter()-begin,3),bytes=path.stat().st_size,checks=checks)
                record['stress'].append(item);save();print('stress',item,flush=True)
    save()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True);parser.add_argument('--project');parser.add_argument('--stress',action='store_true')
    run(parser.parse_args())
