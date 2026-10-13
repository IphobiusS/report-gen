"""Isolated server for release acceptance. Temporary projects only."""
from pathlib import Path
import tempfile, sys, signal, json
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'webapp')]
import app as api
with tempfile.TemporaryDirectory(prefix='report-gen-0212-') as temp:
    # macOS exposes its own temporary directory through /var -> /private/var.
    # Resolve this test-owned path before passing it to strict workspace checks.
    root=Path(temp).resolve()
    api.PROJECTS=root/'projects';api.PROJECTS.mkdir()
    api.app.config.update(LIBRARY_PATH=str(root/'library.json'),DESIGN_LIBRARY_PATH=str(root/'designs.json'))
    server=api.create_local_server(0)
    def stop(*_):raise SystemExit(0)
    signal.signal(signal.SIGTERM,stop)
    try:
        print(json.dumps({'url':f'http://127.0.0.1:{server.effective_port}'}),flush=True);server.run()
    finally:
        if 'export_queue' in api.app.extensions:api.app.extensions['export_queue'].close()
        server.close()
