"""Test-only Flask transport over stdin/stdout when TCP is unavailable."""
import base64
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'webapp')]
import app as webapp  # noqa: E402

with tempfile.TemporaryDirectory(prefix='report-gen-dom-') as tmp:
    root=Path(tmp)
    webapp.PROJECTS=root/'projects';webapp.PROJECTS.mkdir()
    webapp.app.config['LIBRARY_PATH']=str(root/'library'/'findings.json')
    webapp.app.config['DESIGN_LIBRARY_PATH']=str(root/'library'/'designs.json')
    webapp.app.config['CLIENT_PROFILES_PATH']=str(root/'library'/'client-profiles.json')
    client=webapp.app.test_client()
    if '--seed' in sys.argv:
        csrf=client.get('/api/session').get_json()['csrf']
        for slug in ('a','b'):
            r=client.post('/api/projects',json={'slug':slug,'title':slug.upper()},headers={'X-CSRF-Token':csrf})
            assert r.status_code==200
    for line in sys.stdin:
        message=json.loads(line)
        try:
            r=client.open(message['path'],method=message.get('method','GET'),headers=message.get('headers',{}),data=base64.b64decode(message.get('body','')))
            result={'id':message['id'],'status':r.status_code,'headers':list(r.headers.items()),'body':base64.b64encode(r.data).decode()}
        except Exception as exc:
            result={'id':message['id'],'error':str(exc)}
        print(json.dumps(result),flush=True)
