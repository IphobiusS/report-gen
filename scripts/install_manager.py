"""Testable operations behind the native installation wizard.

Application directories are selected extracted packages, never overwritten.
Recovery restores a verified pre-update backup to a *new* workspace and points
the launcher at the preserved previous application. Current data stays intact.
"""
import ast
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from error_messages import message  # noqa: E402
from workspace_paths import _no_links, select_workspace  # noqa: E402
from workspace_access import exclusive_paths  # noqa: E402
from scripts import install as installer  # noqa: E402
from scripts.install_snapshot import write_private  # noqa: E402

WINDOWS_MARKER = '@echo off\r\nrem report-gen-launcher-v1\r\n'
RECEIPT_SCHEMA = 'report-gen-installation-1'


def path(value):
    if not str(value).strip() or any(ord(char) < 32 or ord(char) == 127 for char in str(value)):
        raise ValueError(message('Indica una ruta válida.', en='Provide a valid path.', pt='Informe um caminho válido.'))
    result = Path(value).expanduser().absolute()
    _no_links(result)
    return result.resolve()


def separate(first, second):
    return first != second and first not in second.parents and second not in first.parents


def application(value):
    root = path(value)
    for name in ('start.py', 'version.py', 'engine.py', 'requirements-audited.txt', 'webapp/app.py'):
        entry = root / name
        _no_links(entry)
        if not entry.is_file() or entry.stat().st_nlink != 1:
            raise ValueError(message('Selecciona un paquete de report-gen completo y extraído.',
                en='Select a complete extracted report-gen package.', pt='Selecione um pacote completo e extraído do report-gen.'))
    return root


def version(root):
    target = root / 'version.py'
    if target.stat().st_size > 8192:
        raise ValueError('Invalid application version.')
    tree = ast.parse(target.read_text(encoding='utf-8'))
    values = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == '__version__' for target in node.targets)]
    if len(values) != 1 or not isinstance(values[0], str) or not re.fullmatch(r'\d+\.\d+\.\d+', values[0]):
        raise ValueError('Invalid application version.')
    return values[0]


def python_for(root, windows=None):
    windows = os.name == 'nt' if windows is None else windows
    return root / '.venv' / ('Scripts/python.exe' if windows else 'bin/python')


def default_launcher():
    return Path.home() / ('Desktop/report-gen.cmd' if os.name == 'nt' else '.local/bin/report-gen')


def default_data():
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'report-gen/data'
    return installer.default_workspace()


def launcher_content(root, workspace, lang, windows=None, port=8080):
    windows = os.name == 'nt' if windows is None else windows
    if not windows:
        content = installer.launcher_text(root, workspace, lang)
        return content.replace(' "$@"\n', f' --port {int(port)} "$@"\n'), installer.MARKER
    words = [str(python_for(root, True)), str(root / 'start.py'), '--workspace', str(workspace), '--lang', lang, '--port', str(port)]
    if any(any(char in value for char in '"\r\n\x00') for value in words):
        raise ValueError('Unsupported Windows launcher path.')
    # Disable delayed expansion and escape percent expansion in literal paths.
    quoted = ' '.join('"' + word.replace('%', '%%') + '"' for word in words)
    # cmd.exe otherwise decodes UTF-8 paths using the user's legacy code page.
    # Capture/restore it around the child; the first lines are ASCII-only.
    return (WINDOWS_MARKER + 'setlocal DisableDelayedExpansion\r\n'
            'for /f "tokens=2 delims=:" %%a in (\'chcp\') do set "REPORT_GEN_LAUNCH_CP=%%a"\r\n'
            'chcp 65001 >nul\r\n' + quoted + '\r\n'
            'set "REPORT_GEN_LAUNCH_EXIT=%ERRORLEVEL%"\r\n'
            'chcp %REPORT_GEN_LAUNCH_CP% >nul\r\n'
            'exit /b %REPORT_GEN_LAUNCH_EXIT%\r\n'), WINDOWS_MARKER


def _safe_launcher(target, marker):
    # read_text's newline normalization is accounted for by install.safe_destination.
    _no_links(target)
    return installer.safe_destination(target, marker.replace('\r\n', '\n'))


def _publish_launcher(target, content, marker):
    _safe_launcher(target, marker)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('wb', dir=target.parent, prefix='.report-gen-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content.encode('utf-8')); stream.flush(); os.fsync(stream.fileno())
        temporary.chmod(0o700)
        _safe_launcher(target, marker)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _launcher_bytes(target):
    _no_links(target)
    if not target.exists():
        return None
    if not target.is_file() or target.stat().st_nlink != 1 or target.stat().st_size > 65536:
        raise ValueError('Invalid report-gen launcher.')
    return target.read_bytes()


def _unchanged_launcher(target, expected):
    if _launcher_bytes(target) != expected:
        raise ValueError(message('El acceso cambió durante la operación. No se reemplazó.',
            en='The launcher changed during the operation. It was not replaced.',
            pt='O atalho mudou durante a operação. Ele não foi substituído.'))


@dataclass(frozen=True)
class Plan:
    application: Path
    workspace: Path
    launcher: Path
    backups: Path
    previous: Path | None = None
    language: str = 'es'
    port: int = 8080

    def validate(self):
        root = application(self.application)
        workspace = select_workspace(root, str(path(self.workspace)), environ={}).root
        previous = application(self.previous) if self.previous else None
        backups = path(self.backups)
        launcher = path(self.launcher)
        if self.language not in ('es', 'en', 'pt') or not 1024 <= self.port <= 65535:
            raise ValueError('Invalid language or server port.')
        for protected in (root, workspace, *((previous,) if previous else ())):
            if not separate(backups, protected) or not separate(launcher, protected):
                raise ValueError(message('Guarda los respaldos y el acceso fuera de las aplicaciones y de los datos.',
                    en='Keep backups and the launcher outside applications and data.',
                    pt='Mantenha os backups e o atalho fora dos aplicativos e dos dados.'))
        if previous and (not separate(root, previous) or not separate(workspace, previous)):
            raise ValueError(message('Usa instalaciones separadas y una carpeta de datos externa.',
                en='Use separate installations and an external data directory.',
                pt='Use instalações separadas e uma pasta externa de dados.'))
        if not separate(backups, launcher):
            raise ValueError('Keep the launcher outside the backup directory.')
        _, marker = launcher_content(root, workspace, self.language, port=self.port)
        _safe_launcher(launcher, marker)
        return Plan(root, workspace, launcher, backups, previous, self.language, self.port)


def _stopped(port):
    # Also catches a pre-0.41 editor which does not yet participate in OS locks.
    # A custom legacy port must be selected in the wizard before continuing.
    with socket.socket() as probe:
        probe.settimeout(0.25)
        if probe.connect_ex(('127.0.0.1', port)) == 0:
            raise ValueError(message('Cierra el servidor local del puerto {port} antes de continuar.',
                en='Close the local server on port {port} before continuing.',
                pt='Feche o servidor local na porta {port} antes de continuar.', port=port))


def run(command, timeout=120):
    # Pipes use the Windows ANSI encoding unless explicitly configured. Keep
    # Unicode workspace/backup paths lossless across the JSON child boundary.
    environment = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    result = subprocess.run([str(word) for word in command], capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=timeout, cwd=ROOT, env=environment)
    if result.returncode:
        # Preserve actionable pip/venv details without unbounded GUI text.
        raise ValueError((result.stderr or result.stdout or 'Operation failed.')[-12000:])
    return result.stdout


def diagnose(root, lang='es'):
    root = application(root)
    python = python_for(root)
    if not python.is_file():
        return {'editor_ready': False, 'pdf_ready': False, 'checks': [], 'note': message(
            'El entorno local todavía no está instalado. Puedes prepararlo con el botón Instalar.',
            en='The local environment is not installed yet. Use the Install button to prepare it.',
            pt='O ambiente local ainda não está instalado. Use o botão Instalar para prepará-lo.')}
    return json.loads(run([python, root / 'diagnostics.py', '--lang', lang]))


def _helper(root, action, workspace, *args, lang='es', timeout=120):
    return json.loads(run([python_for(root), ROOT / 'scripts/install_snapshot.py', action,
                          '--workspace', workspace, '--lang', lang, *args], timeout))


def install(plan, *, allow_network=False, progress=lambda text: None):
    plan = plan.validate()
    _stopped(plan.port)
    if not (plan.application / 'workspace_access.py').is_file():
        raise ValueError(message('Selecciona la versión nueva que incluye el bloqueo de instalación (0.41 o posterior).',
            en='Select the new version containing the installation guard (0.41 or later).',
            pt='Selecione a nova versão que inclui o bloqueio de instalação (0.41 ou posterior).'))
    protected = (plan.application, plan.workspace, plan.launcher, *((plan.previous,) if plan.previous else ()))
    # Fail before even installing into the separate new package if data is active.
    with exclusive_paths(*protected):
        previous_launcher = _launcher_bytes(plan.launcher)
    if not allow_network:
        raise ValueError(message('Autoriza la descarga de dependencias para instalar.',
            en='Allow dependency downloads before installing.', pt='Autorize o download de dependências para instalar.'))
    progress('setup')
    run([sys.executable, plan.application / 'start.py', '--setup', '--workspace', plan.workspace,
         '--lang', plan.language], timeout=900)
    with exclusive_paths(*protected):
        _stopped(plan.port)
        progress('diagnose')
        diagnosis = diagnose(plan.application, plan.language)
        if not diagnosis.get('editor_ready'):
            raise ValueError(message('El diagnóstico no está listo. Se conserva el acceso anterior.',
                en='Diagnostics are not ready. The previous launcher is preserved.',
                pt='O diagnóstico não está pronto. O atalho anterior foi preservado.'))
        progress('backup')
        snapshot = _helper(plan.application, 'snapshot', plan.workspace, '--directory', plan.backups, lang=plan.language)
        content, marker = launcher_content(plan.application, plan.workspace, plan.language, port=plan.port)
        receipt = dict(snapshot, schema=RECEIPT_SCHEMA, application=str(plan.application), workspace=str(plan.workspace),
            launcher=str(plan.launcher), previous=str(plan.previous) if plan.previous else None,
            previous_version=version(plan.previous) if plan.previous else None, language=plan.language,
            version=version(plan.application), port=plan.port,
            launcher_sha256=sha256(content.encode()).hexdigest(), diagnostics=diagnosis)
        target = plan.backups / ('installation-' + uuid.uuid4().hex + '.json')
        # A usable recovery receipt is durable before switching the one launcher.
        write_private(target, (json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode())
        progress('activate')
        _unchanged_launcher(plan.launcher, previous_launcher)
        _publish_launcher(plan.launcher, content, marker)
        progress('done')
        return dict(receipt, receipt=str(target))


def recovery(receipt_path, *, progress=lambda text: None):
    receipt_path = path(receipt_path)
    if not receipt_path.is_file() or receipt_path.stat().st_nlink != 1 or receipt_path.stat().st_size > 65536:
        raise ValueError('Invalid installation receipt.')
    data = json.loads(receipt_path.read_text(encoding='utf-8'))
    if data.get('schema') != RECEIPT_SCHEMA or not data.get('previous'):
        raise ValueError(message('Este registro no tiene una instalación anterior.',
            en='This receipt has no previous installation.', pt='Este registro não possui uma instalação anterior.'))
    plan = Plan(Path(data['application']), Path(data['workspace']), Path(data['launcher']),
                receipt_path.parent, Path(data['previous']), data['language'], data['port']).validate()
    if version(plan.previous) != data['previous_version']:
        raise ValueError('The previous application version changed; recovery was not activated.')
    archive = path(data['backup'])
    if archive.parent != receipt_path.parent or not re.fullmatch(r'[a-f0-9]{64}', data.get('backup_sha256', '')):
        raise ValueError('Recovery backup does not belong to this receipt.')
    content, marker = launcher_content(plan.application, plan.workspace, plan.language, port=plan.port)
    if (sha256(content.encode()).hexdigest() != data['launcher_sha256'] or not plan.launcher.is_file()
            or plan.launcher.read_bytes() != content.encode()):
        raise ValueError(message('El acceso cambió desde la instalación. La recuperación no lo reemplazó.',
            en='The launcher changed since installation. Recovery did not replace it.',
            pt='O atalho mudou desde a instalação. A recuperação não o substituiu.'))
    _stopped(plan.port)
    # Keep restored live data beside the existing workspace, outside backups;
    # the recovered installation remains eligible for the next guided update.
    destination = plan.workspace.parent / (plan.workspace.name + '-recovered-' + uuid.uuid4().hex)
    select_workspace(plan.previous, str(destination), environ={})
    if not separate(destination, plan.backups):
        raise ValueError('Recovery data must remain separate from backups.')
    with exclusive_paths(plan.application, plan.previous, plan.workspace, plan.launcher, destination):
        _unchanged_launcher(plan.launcher, content.encode())
        progress('diagnose')
        diagnosis = diagnose(plan.previous, plan.language)
        if not diagnosis.get('editor_ready'):
            raise ValueError(message('Repara las dependencias de la instalación anterior antes de recuperarla.',
                en='Repair the previous installation dependencies before recovery.',
                pt='Repare as dependências da instalação anterior antes da recuperação.'))
        progress('restore')
        result = _helper(plan.application, 'restore', destination, '--archive', archive,
                         '--digest', data['backup_sha256'], lang=plan.language)
        _unchanged_launcher(plan.launcher, content.encode())
        content, marker = launcher_content(plan.previous, destination, plan.language, port=plan.port)
        _publish_launcher(plan.launcher, content, marker)
        progress('done')
        return dict(result, application=str(plan.previous), launcher=str(plan.launcher),
                    current_workspace_preserved=str(plan.workspace), backup=str(archive), port=plan.port)


def prepare_update(plan, *, progress=lambda text: None):
    plan = plan.validate()
    _stopped(plan.port)
    with exclusive_paths(plan.application, plan.workspace):
        pass
    progress('update')
    if not python_for(plan.application).is_file():
        raise ValueError(message('Instala primero el entorno local.', en='Install the local environment first.', pt='Instale primeiro o ambiente local.'))
    result = _helper(plan.application, 'update', plan.workspace, '--directory', plan.application.parent / 'report-gen-updates',
                     '--application', plan.application, lang=plan.language, timeout=900)
    progress('done')
    return result
