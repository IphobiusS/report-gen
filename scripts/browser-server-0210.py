"""Disposable local server for automated acceptance; never uses user projects."""
from pathlib import Path
import json
import signal
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'webapp')]
import app as api
import project_history
import export

with tempfile.TemporaryDirectory(prefix='report-gen-browser-0210-') as temp:
    root=Path(temp)
    api.PROJECTS=root/'projects';api.PROJECTS.mkdir()
    api.app.config['LIBRARY_PATH']=str(root/'findings.json')
    api.app.config['DESIGN_LIBRARY_PATH']=str(root/'designs.json')
    fixture=root/'quality-lab.zip'
    fixture.write_bytes(project_history.export_bundle(ROOT/'examples/quality-lab'))
    portable=export.export(ROOT/'examples/quality-lab/engagement.yaml','html',root/'quality-lab.html')
    server=api.create_local_server(0)
    def stop(*_): raise SystemExit(0)
    signal.signal(signal.SIGTERM,stop)
    try:
        print(json.dumps({'url':f'http://127.0.0.1:{server.effective_port}','fixture':str(fixture),'portable':str(portable)}),flush=True)
        server.run()
    finally:
        if 'export_queue' in api.app.extensions: api.app.extensions['export_queue'].close()
        server.close()
