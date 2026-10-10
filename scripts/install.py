#!/usr/bin/env python3
"""Prepare the source package and an explicit, external data workspace on Linux.

Downloads audited Python dependencies into the application's .venv. Never uses
sudo, changes system packages, migrates old data or claims to be a standalone EXE.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from workspace_paths import select_workspace  # noqa: E402

MARKER = '#!/bin/sh\n# report-gen-launcher-v1\n'
DESKTOP_MARKER = '# report-gen-desktop-v1\n'


def default_workspace(environment=None, home=None):
    environment = os.environ if environment is None else environment
    home = Path.home() if home is None else Path(home)
    configured = environment.get('REPORT_GEN_WORKSPACE')
    if configured:
        return Path(configured).expanduser()
    data = Path(environment.get('XDG_DATA_HOME', str(home / '.local/share'))).expanduser()
    if not data.is_absolute():
        raise ValueError('XDG_DATA_HOME must be an absolute path')
    return data / 'report-gen'


def safe_destination(path, marker):
    path = Path(os.path.abspath(path.expanduser()))
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError('Launcher destination must not contain symbolic links')
    if path.exists():
        if not path.is_file() or path.stat().st_nlink != 1 or not path.read_text(encoding='utf-8').startswith(marker):
            raise ValueError(f'The destination is not an existing report-gen launcher: {path}')
    if any(character in str(path) for character in '\r\n\x00'):
        raise ValueError('Control characters are not allowed in launcher paths')
    return path


def replace_owned(path, content, marker, mode):
    path = safe_destination(path, marker)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, prefix='.report-gen-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(mode)
        safe_destination(path, marker)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def launcher_text(root, workspace, lang):
    words = [str(root / '.venv/bin/python'), str(root / 'start.py'), '--workspace', str(workspace), '--lang', lang]
    # No --ready here: an ordinary click never installs or updates dependencies.
    return MARKER + 'exec ' + ' '.join(shlex.quote(word) for word in words) + ' "$@"\n'


def desktop_text(launcher):
    # Desktop Entry specification has its own quoting and percent field codes.
    value = str(launcher).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
    if '=' in str(launcher):
        raise ValueError('Desktop launcher paths cannot contain an equals sign')
    value = value.replace('\\', '\\\\')
    return (DESKTOP_MARKER + '[Desktop Entry]\nType=Application\nVersion=1.0\n'
            'Name=report-gen\nComment=Local pentest report editor\n'
            f'Exec="{value}"\nTerminal=true\nCategories=Development;Office;\n')


def install(root, workspace, launcher, desktop=None, lang='es'):
    root = Path(root).resolve()
    selection = select_workspace(root, str(workspace))
    launcher = safe_destination(launcher, MARKER)
    desktop = safe_destination(desktop, DESKTOP_MARKER) if desktop is not None else None
    for path in (launcher, desktop):
        if path is not None and (path == selection.root or path.is_relative_to(selection.root)):
            raise ValueError('Keep launchers outside the private data workspace')
    if not (root / 'requirements-audited.txt').is_file() or not (root / 'start.py').is_file():
        raise ValueError('Run the installer from the complete extracted source package')
    launch_content = launcher_text(root, selection.root, lang)
    desktop_content = desktop_text(launcher) if desktop is not None else None
    subprocess.run([sys.executable, str(root / 'start.py'), '--setup', '--workspace', str(selection.root), '--lang', lang],
                   check=True, cwd=root)
    python = root / '.venv/bin/python'
    process = subprocess.run([str(python), str(root / 'diagnostics.py'), '--lang', lang],
                             capture_output=True, text=True, timeout=90, check=True, cwd=root)
    diagnosis = json.loads(process.stdout)
    if not diagnosis.get('editor_ready'):
        raise ValueError('Editor dependencies are not ready; no launcher has been installed')
    replace_owned(launcher, launch_content, MARKER, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    if desktop is not None:
        replace_owned(desktop, desktop_content, DESKTOP_MARKER, stat.S_IRUSR | stat.S_IWUSR)
    return {'application': str(root), 'workspace': str(selection.root), 'launcher': str(launcher),
            'desktop': str(desktop) if desktop else None, 'diagnostics': diagnosis}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, help='Private data directory; default: XDG_DATA_HOME/report-gen')
    parser.add_argument('--launcher', type=Path, default=Path.home() / '.local/bin/report-gen')
    parser.add_argument('--desktop', action='store_true', help='Add/update the application-menu shortcut for this user')
    parser.add_argument('--lang', choices=['es', 'en'], default='es')
    args = parser.parse_args(argv)
    if not sys.platform.startswith('linux'):
        parser.error('This installer targets Linux/Kali. On Windows/macOS, use python start.py --ready --workspace PATH.')
    if sys.version_info < (3, 10):
        parser.error('Python 3.10+ is required; validated with Python 3.12')
    try:
        desktop = None
        if args.desktop:
            data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))).expanduser()
            if not data.is_absolute():
                raise ValueError('XDG_DATA_HOME must be absolute')
            desktop = data / 'applications/report-gen.desktop'
        result = install(ROOT, args.workspace or default_workspace(), args.launcher, desktop, args.lang)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'Installation could not finish: {exc}\n'
                    'Keep the extracted folder. Check Python venv support and the dependency error above; '
                    'no system packages were installed automatically.\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print('Open / Abrir: ' + shlex.quote(result['launcher']) + '\nhttp://127.0.0.1:8080\nCtrl+C to stop / para salir.')
    if not result['diagnostics'].get('pdf_ready'):
        print('PDF: no engine available. Read the native-library instructions in README.md; Word/Markdown/HTML remain available.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
