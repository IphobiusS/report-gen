"""Disposable acceptance server. Fault routes exist only in this test process.

The caller owns a dedicated temporary directory with a sentinel. Never point
this runner at user projects. ENOSPC/EACCES are injected at the OS replace call;
crash_after_move really terminates the process after journaling/renaming.
"""
from pathlib import Path
import argparse
import errno
import json
import os
import signal
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'webapp')]

parser=argparse.ArgumentParser()
parser.add_argument('--workspace',required=True)
parser.add_argument('--port',type=int,default=0)
args=parser.parse_args()
root=Path(args.workspace).resolve()
if not root.name.startswith('report-gen-acceptance-0211-') or (root/'.test-only').read_text()!='synthetic acceptance workspace':
    raise SystemExit('This runner requires a dedicated disposable acceptance workspace')
os.environ['REPORT_GEN_WORKSPACE'] = str(root)
import app as api
import storage
from flask import request,jsonify,abort
api.PROJECTS=root/'projects';api.PROJECTS.mkdir(exist_ok=True)
api.app.config['LIBRARY_PATH']=str(root/'findings.json')
api.app.config['DESIGN_LIBRARY_PATH']=str(root/'designs.json')
fault=dict(mode=None,slug=None)
replace=storage.os.replace
rename=Path.rename

def failing_replace(source,target):
    dest=Path(target)
    if fault['mode'] in ('disk_full','permission') and dest.name=='engagement.yaml' and dest.resolve().is_relative_to(root):
        raise OSError(errno.ENOSPC if fault['mode']=='disk_full' else errno.EACCES,'Synthetic acceptance fault')
    return replace(source,target)

def crashing_rename(source,target):
    result=rename(source,target)
    if fault['mode']=='crash_after_move' and source==api.PROJECTS/fault['slug']:
        os._exit(92)
    return result

storage.os.replace=failing_replace
Path.rename=crashing_rename

@api.app.post('/api/__test__/fault')
def set_fault():
    body=request.get_json()
    if body.get('mode') not in (None,'disk_full','permission','crash_after_move'):abort(422)
    slug=body.get('slug')
    if slug is not None:api.proj_dir(slug)
    fault.update(mode=body.get('mode'),slug=slug)
    return jsonify(ok=True)

server=api.create_local_server(args.port)
def stop(*_):raise SystemExit(0)
signal.signal(signal.SIGTERM,stop)
try:
    print(json.dumps(dict(url=f'http://127.0.0.1:{server.effective_port}',port=server.effective_port)),flush=True)
    server.run()
finally:
    if 'export_queue' in api.app.extensions:api.app.extensions['export_queue'].close()
    server.close()
