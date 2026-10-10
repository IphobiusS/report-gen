#!/usr/bin/env python3
"""Explicit install, diagnosis and local launch using the packaged sources."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import venv
ROOT=Path(__file__).resolve().parent


def _run_windows_server(command):
    """Keep the selected venv; clean up the child on Python console signals.

    Windows does not provide POSIX exec's same-PID replacement. Abrupt external
    TerminateProcess is outside this graceful console-shutdown guarantee.
    """
    process = None
    received = []

    def stop(signum, _frame):
        received.append(signum)
        if process is not None and process.poll() is None:
            process.terminate()

    previous = {kind: signal.getsignal(kind) for kind in (signal.SIGINT, signal.SIGTERM)}
    try:
        for kind in previous:
            signal.signal(kind, stop)
        process = subprocess.Popen(command, cwd=ROOT)
        if received:
            process.terminate()
        code = process.wait()
        return 128 + received[0] if received else code
    finally:
        try:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        finally:
            for kind, handler in previous.items():
                signal.signal(kind, handler)


def _run_server(python, port):
    command = [str(python), str(ROOT / 'webapp/app.py'), str(port)]
    if os.name == 'posix':
        # Replacement retains the launcher PID, environment and selected venv.
        # SIGTERM/SIGINT/SIGKILL cannot leave an orphaned server process behind.
        os.chdir(ROOT)
        os.execv(str(python), command)
    return _run_windows_server(command)


def main():
    parser=argparse.ArgumentParser(description='report-gen local launcher / lanzador local')
    parser.add_argument('--setup',action='store_true',help='Create .venv and install pinned dependencies / instalar')
    parser.add_argument('--diagnose',action='store_true',help='Test installed export engines / probar motores')
    parser.add_argument('--lang',choices=['es','en'],default='es')
    parser.add_argument('--port',type=int,default=8080)
    args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error('Port / Puerto: 1024–65535')
    if sys.version_info<(3,10):parser.error('Python 3.10+ required / necesario; validated with 3.12')
    local=ROOT/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if args.setup:
        if not local.exists():venv.EnvBuilder(with_pip=True).create(ROOT/'.venv')
        # ensurepip can seed an old installer even with a maintained Python.
        # Upgrade before processing project dependencies, in this venv only.
        subprocess.run([str(local),'-m','pip','install','--upgrade','pip>=26.2,<27'],check=True,cwd=ROOT)
        subprocess.run([str(local),'-m','pip','install','-e',str(ROOT),'-c',str(ROOT/'requirements-audited.txt')],check=True,cwd=ROOT)
        print('Instalado / Installed. Run: python3 start.py --diagnose; python3 start.py')
        return 0
    python=local if local.exists() else Path(sys.executable)
    check=subprocess.run([str(python),'-c','import flask, waitress, docx, yaml, PIL, lxml'],capture_output=True)
    if check.returncode:
        print('Faltan dependencias / Missing dependencies. Run: python3 start.py --setup',file=sys.stderr);return 1
    if args.diagnose:
        return subprocess.run([str(python),str(ROOT/'diagnostics.py'),'--lang',args.lang],cwd=ROOT).returncode
    print(f'report-gen -> http://127.0.0.1:{args.port}\nCtrl+C para salir / to stop',flush=True)
    return _run_server(python, args.port)

if __name__=='__main__':raise SystemExit(main())
