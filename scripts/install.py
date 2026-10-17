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
from languages import console_language, language_argument, language_index  # noqa: E402
from error_messages import language_scope, message  # noqa: E402

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
        raise ValueError(message('XDG_DATA_HOME must be an absolute path', en='XDG_DATA_HOME must be an absolute path', pt='XDG_DATA_HOME deve ser um caminho absoluto'))
    return data / 'report-gen'


def safe_destination(path, marker):
    path = Path(os.path.abspath(path.expanduser()))
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError(message('Launcher destination must not contain symbolic links', en='Launcher destination must not contain symbolic links', pt='O destino do atalho não pode conter links simbólicos'))
    if path.exists():
        if not path.is_file() or path.stat().st_nlink != 1 or not path.read_text(encoding='utf-8').startswith(marker):
            raise ValueError(message('The destination is not an existing report-gen launcher: {path}', en='The destination is not an existing report-gen launcher: {path}', pt='O destino não é um atalho existente do report-gen: {path}', path=path))
    if any(character in str(path) for character in '\r\n\x00'):
        raise ValueError(message('Control characters are not allowed in launcher paths', en='Control characters are not allowed in launcher paths', pt='Caracteres de controle não são permitidos nos caminhos dos atalhos'))
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
        raise ValueError(message('Desktop launcher paths cannot contain an equals sign', en='Desktop launcher paths cannot contain an equals sign', pt='O caminho do atalho de desktop não pode conter o sinal de igual'))
    value = value.replace('\\', '\\\\')
    return (DESKTOP_MARKER + '[Desktop Entry]\nType=Application\nVersion=1.0\n'
            'Name=report-gen\nComment=Local pentest report editor\n'
            'Comment[es]=Editor local de informes de pentesting\n'
            'Comment[pt_BR]=Editor local de relatórios de pentest\n'
            f'Exec="{value}"\nTerminal=true\nCategories=Development;Office;\n')


def install(root, workspace, launcher, desktop=None, lang='es'):
    root = Path(root).resolve()
    selection = select_workspace(root, str(workspace))
    launcher = safe_destination(launcher, MARKER)
    desktop = safe_destination(desktop, DESKTOP_MARKER) if desktop is not None else None
    for path in (launcher, desktop):
        if path is not None and (path == selection.root or path.is_relative_to(selection.root)):
            raise ValueError(message('Keep launchers outside the private data workspace', en='Keep launchers outside the private data workspace', pt='Mantenha os atalhos fora do espaço de trabalho de dados privados'))
    if not (root / 'requirements-audited.txt').is_file() or not (root / 'start.py').is_file():
        raise ValueError(message('Run the installer from the complete extracted source package', en='Run the installer from the complete extracted source package', pt='Execute o instalador a partir do pacote de código-fonte completo e extraído'))
    launch_content = launcher_text(root, selection.root, lang)
    desktop_content = desktop_text(launcher) if desktop is not None else None
    subprocess.run([sys.executable, str(root / 'start.py'), '--setup', '--workspace', str(selection.root), '--lang', lang],
                   check=True, cwd=root)
    python = root / '.venv/bin/python'
    process = subprocess.run([str(python), str(root / 'diagnostics.py'), '--lang', lang],
                             capture_output=True, text=True, timeout=90, check=True, cwd=root)
    diagnosis = json.loads(process.stdout)
    if not diagnosis.get('editor_ready'):
        raise ValueError(message('Editor dependencies are not ready; no launcher has been installed', en='Editor dependencies are not ready; no launcher has been installed', pt='As dependências do editor não estão prontas; nenhum atalho foi instalado'))
    replace_owned(launcher, launch_content, MARKER, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    if desktop is not None:
        replace_owned(desktop, desktop_content, DESKTOP_MARKER, stat.S_IRUSR | stat.S_IWUSR)
    return {'application': str(root), 'workspace': str(selection.root), 'launcher': str(launcher),
            'desktop': str(desktop) if desktop else None, 'diagnostics': diagnosis}


def main(argv=None):
    initial_language = console_language(argv)
    def w(es, en, pt):
        return (es, en, pt)[language_index(initial_language)]
    parser = argparse.ArgumentParser(description=w('Instalar report-gen y su acceso local en Linux.', 'Install report-gen and its local launcher on Linux.', 'Instala o report-gen e seu atalho local no Linux.'))
    parser.add_argument('--workspace', type=Path, help=w('Carpeta de datos privados; predeterminada: XDG_DATA_HOME/report-gen', 'Private data directory; default: XDG_DATA_HOME/report-gen', 'Pasta de dados privados; padrão: XDG_DATA_HOME/report-gen'))
    parser.add_argument('--launcher', type=Path, default=Path.home() / '.local/bin/report-gen')
    parser.add_argument('--desktop', action='store_true', help=w('Crear o actualizar el acceso en el menú de aplicaciones', 'Add/update the application-menu shortcut for this user', 'Cria ou atualiza o atalho no menu de aplicativos para este usuário'))
    parser.add_argument('--lang', type=language_argument, choices=['es', 'en', 'pt'], default='es')
    parser.add_argument('--gui', action='store_true', help=w('Abrir el asistente gráfico opcional (Python con Tkinter)',
        'Open the optional graphical wizard (Python with Tkinter)', 'Abre o assistente gráfico opcional (Python com Tkinter)'))
    args = parser.parse_args(argv)
    if args.gui:
        if args.desktop:
            parser.error(w('--desktop pertenece al instalador de consola.', '--desktop belongs to the console installer.', '--desktop pertence ao instalador de console.'))
        from scripts.install_wizard import main as graphical_main
        command = ['--lang', args.lang]
        if args.workspace:
            command.extend(['--workspace', str(args.workspace)])
        if args.launcher != Path.home() / '.local/bin/report-gen':
            command.extend(['--launcher', str(args.launcher)])
        return graphical_main(command)
    if not sys.platform.startswith('linux'):
        parser.error(w('Este instalador es para Linux/Kali. En Windows/macOS, usa python start.py --ready --workspace RUTA.', 'This installer targets Linux/Kali. On Windows/macOS, use python start.py --ready --workspace PATH.', 'Este instalador é para Linux/Kali. No Windows/macOS, use python start.py --ready --workspace CAMINHO.'))
    if sys.version_info < (3, 11):
        parser.error(w('Se requiere Python 3.11+; validado con Python 3.12', 'Python 3.11+ is required; validated with Python 3.12', 'Python 3.11+ é necessário; validado com Python 3.12'))
    try:
        desktop = None
        if args.desktop:
            data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))).expanduser()
            if not data.is_absolute():
                raise ValueError(message('XDG_DATA_HOME must be absolute', en='XDG_DATA_HOME must be absolute', pt='XDG_DATA_HOME deve ser absoluto', language=args.lang))
            desktop = data / 'applications/report-gen.desktop'
        with language_scope(args.lang):
            result = install(ROOT, args.workspace or default_workspace(), args.launcher, desktop, args.lang)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, w('La instalación no pudo terminar: ', 'Installation could not finish: ', 'Não foi possível concluir a instalação: ') + str(exc) + '\n' +
                    w('Conserva la carpeta extraída. Comprueba el soporte venv de Python y el error de dependencias; no se instalaron paquetes del sistema automáticamente.',
                      'Keep the extracted folder. Check Python venv support and the dependency error above; no system packages were installed automatically.',
                      'Mantenha a pasta extraída. Verifique o suporte a venv do Python e o erro de dependências acima; nenhum pacote do sistema foi instalado automaticamente.') + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(w('Abrir: ', 'Open: ', 'Abrir: ') + shlex.quote(result['launcher']) + '\nhttp://127.0.0.1:8080\n' + w('Ctrl+C para salir.', 'Ctrl+C to stop.', 'Ctrl+C para sair.'))
    if not result['diagnostics'].get('pdf_ready'):
        print(w('PDF: no hay motor disponible. Revisa las bibliotecas nativas en README.md; Word/Markdown/HTML siguen disponibles.', 'PDF: no engine available. Read the native-library instructions in README.en.md; Word/Markdown/HTML remain available.', 'PDF: nenhum mecanismo disponível. Consulte as bibliotecas nativas em README.pt.md; Word/Markdown/HTML continuam disponíveis.'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
