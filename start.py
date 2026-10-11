#!/usr/bin/env python3
"""Explicit install, diagnosis and local launch using the packaged sources."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import shlex
import subprocess
import sys
import venv
from workspace_paths import select_workspace, workspace_environment, ENVIRONMENT_KEY
ROOT=Path(__file__).resolve().parent


@contextmanager
def launcher_language(language):
    """Pass the launcher's initial UI choice without overriding browser preferences."""
    previous = os.environ.get('REPORT_GEN_UI_LANG')
    os.environ['REPORT_GEN_UI_LANG'] = language
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop('REPORT_GEN_UI_LANG', None)
        else:
            os.environ['REPORT_GEN_UI_LANG'] = previous


def _words(lang, es, en):
    return en if lang == 'en' else es


def _launch_hint(selection):
    command = ['python', 'start.py']
    if selection.external:
        command.extend(['--workspace', str(selection.root)])
    return subprocess.list2cmdline(command) if os.name == 'nt' else shlex.join(command)


def _install(local, lang):
    print(_words(lang, 'Preparando el entorno local; se descargarán dependencias.',
                 'Preparing the local environment; dependencies will be downloaded.'), flush=True)
    if not local.exists():
        venv.EnvBuilder(with_pip=True).create(ROOT / '.venv')
    # Upgrade the installer seeded by ensurepip before reading project metadata.
    subprocess.run([str(local), '-m', 'pip', 'install', '--upgrade', 'pip>=26.2,<27'], check=True, cwd=ROOT)
    subprocess.run([str(local), '-m', 'pip', 'install', '-e', str(ROOT),
                    '-c', str(ROOT / 'requirements-audited.txt')], check=True, cwd=ROOT)


def _dependencies(python):
    return subprocess.run([str(python), '-c',
                           'import flask, waitress, docx, yaml, PIL, lxml, jinja2, markdown, nh3, pypdf'],
                          capture_output=True, timeout=30, cwd=ROOT).returncode == 0


def _readiness(python, lang):
    process = subprocess.run([str(python), str(ROOT / 'diagnostics.py'), '--lang', lang],
                             capture_output=True, text=True, timeout=60, cwd=ROOT)
    if process.returncode:
        raise ValueError(_words(lang, 'No se pudo completar el diagnóstico. Ejecuta start.py --diagnose.',
                                'Diagnostics could not finish. Run start.py --diagnose.'))
    report = json.loads(process.stdout)
    for check in report['checks']:
        print(f"{'OK' if check['ready'] else '!'} {check['label']}: {check['detail']}", flush=True)
    print(report['note'], flush=True)
    return report.get('editor_ready', True)


def _upgrade(python, source, lang):
    command = [str(python), str(ROOT / 'launcher_upgrade.py'), '--source', source,
               '--destination', str(ROOT), '--lang', lang]
    if ENVIRONMENT_KEY in os.environ:
        command.extend(['--workspace', os.environ[ENVIRONMENT_KEY]])
    process = subprocess.run(command,
                             capture_output=True, text=True, cwd=ROOT)
    if process.returncode:
        try:
            error = json.loads(process.stderr)['error']
        except (ValueError, KeyError):
            error = _words(lang, 'No se pudo completar la migración; conserva ambas instalaciones.',
                           'Migration could not finish; keep both installations.')
        raise ValueError(error)
    result = json.loads(process.stdout)
    print(_words(lang, 'Migración verificada', 'Migration verified') + ': ' +
          _words(lang, '{projects} proyectos, {findings} hallazgos reutilizables, {designs} diseños.',
                 '{projects} projects, {findings} reusable findings, {designs} designs.').format(**result), flush=True)
    print(_words(lang, 'Respaldo: ', 'Backup: ') + result['backup'], flush=True)
    print(_words(lang, 'SHA-256: ', 'SHA-256: ') + result['sha256'], flush=True)
    print(_words(lang, 'La instalación anterior se conserva. Guarda el respaldo fuera de las entregas.',
                 'The previous installation is preserved. Keep the backup out of deliveries.'), flush=True)
    for warning in result.get('warnings', []):
        print(warning, flush=True)


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


def main(argv=None):
    parser = argparse.ArgumentParser(description='report-gen local launcher / lanzador local')
    parser.add_argument('--setup', action='store_true', help='Install dependencies and stop / instalar y terminar')
    parser.add_argument('--ready', action='store_true',
                        help='Allow dependency installation, diagnose and start / permitir instalación, comprobar y abrir')
    parser.add_argument('--diagnose', action='store_true', help='Test installed export engines / probar motores')
    parser.add_argument('--upgrade-from', metavar='DIRECTORY',
                        help='Back up and restore an old installation into this empty one / migrar desde instalación anterior')
    parser.add_argument('--workspace', metavar='DIRECTORY',
                        help='External data directory (or REPORT_GEN_WORKSPACE) / carpeta externa de datos')
    parser.add_argument('--lang', choices=['es', 'en'], default='es')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error('Port / Puerto: 1024–65535')
    if sys.version_info < (3, 11):
        parser.error('Python 3.11+ required / necesario; validated with 3.12')
    if args.setup and (args.ready or args.upgrade_from):
        parser.error('--setup instala y termina / installs and stops; use --ready for the combined flow')
    if args.diagnose and (args.ready or args.upgrade_from):
        parser.error('--diagnose es independiente / is standalone')
    lang = args.lang
    local = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    try:
        selection = select_workspace(ROOT, args.workspace)
        with workspace_environment(selection), launcher_language(lang):
            if args.setup:
                _install(local, lang)
                print(_words(lang, 'Instalado. Ejecuta: ', 'Installed. Run: ') + _launch_hint(selection) + ' --ready')
                return 0
            python = local if local.exists() else Path(sys.executable)
            if args.ready:
                # --ready is explicit consent to install; ordinary launch and diagnosis
                # never create a virtual environment or contact package servers.
                if not local.exists() or not _dependencies(local):
                    _install(local, lang)
                python = local
            if not _dependencies(python):
                print(_words(lang, 'Faltan dependencias del editor. Ejecuta: python start.py --ready',
                             'Editor dependencies are missing. Run: python start.py --ready'), file=sys.stderr)
                return 1
            if args.diagnose:
                return subprocess.run([str(python), str(ROOT / 'diagnostics.py'), '--lang', lang],
                                      cwd=ROOT, timeout=60).returncode
            if args.upgrade_from:
                _upgrade(python, args.upgrade_from, lang)
                if not args.ready:
                    ready = _readiness(python, lang)
                    print(_words(lang, 'Para abrir: ', 'To start: ') + _launch_hint(selection), flush=True)
                    return 0 if ready else 1
            if args.ready and not _readiness(python, lang):
                print(_words(lang, 'Repara las dependencias del editor: python start.py --setup',
                             'Repair editor dependencies: python start.py --setup'), file=sys.stderr)
                return 1
            print(_words(lang, 'Datos: ', 'Data: ') + str(selection.root), flush=True)
            print(f'report-gen -> http://127.0.0.1:{args.port}\n' +
                  _words(lang, 'Ctrl+C para salir', 'Ctrl+C to stop'), flush=True)
            return _run_server(python, args.port)
    except subprocess.CalledProcessError:
        print(_words(lang, 'La instalación no terminó. Revisa la conexión y el error anterior; '
                     'vuelve a ejecutar python start.py --setup. En Linux, comprueba que python3-venv esté instalado.',
                     'Installation did not finish. Check connectivity and the error above, then rerun '
                     'python start.py --setup. On Linux, ensure python3-venv is installed.'), file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        print(_words(lang, 'La comprobación excedió el tiempo disponible. Ejecuta python start.py --diagnose '
                     'para revisar la instalación.',
                     'The check timed out. Run python start.py --diagnose to inspect the installation.'), file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(_words(lang, 'No se pudo completar la preparación: ', 'Preparation could not finish: ') +
              str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
