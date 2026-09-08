"""Real local HTTP API + the full editor in a simulated DOM."""
import os
from pathlib import Path
import subprocess
import threading
from werkzeug.serving import make_server
import app as webapp
from _support import auth_client


def test_editor_with_real_api(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, 'PROJECTS', tmp_path)
    monkeypatch.setitem(webapp.app.config, 'LIBRARY_PATH', str(tmp_path / 'library.json'))
    client=auth_client(webapp.app)
    for slug in ['a','b']:
        assert client.post('/api/projects',json={'slug':slug,'title':slug.upper()}).status_code==200
    server=make_server('127.0.0.1',0,webapp.app,threaded=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        result=subprocess.run(['node',str(Path(__file__).with_name('ui_integration.cjs')),f'http://127.0.0.1:{server.server_port}/'],capture_output=True,text=True,timeout=60,env=os.environ.copy())
        assert result.returncode==0,result.stdout+result.stderr
        print(result.stdout)
    finally:
        server.shutdown();thread.join(timeout=3)
