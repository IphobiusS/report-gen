#!/usr/bin/env python3
"""Native, optional installation wizard. Requires Python 3.11+ with Tkinter."""
import argparse
from pathlib import Path
import queue
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from languages import language_argument, language_index  # noqa: E402
from error_messages import language_scope  # noqa: E402
from scripts import install_manager as manager  # noqa: E402


TEXT = {
    'title': ('report-gen · Instalación y recuperación', 'report-gen · Installation and recovery', 'report-gen · Instalação e recuperação'),
    'heading': ('Prepara tu espacio de trabajo', 'Prepare your workspace', 'Prepare seu espaço de trabalho'),
    'intro': ('Instala en una carpeta nueva. Tus proyectos permanecen separados de la aplicación.',
              'Install into a new folder. Your projects remain separate from the application.',
              'Instale em uma pasta nova. Seus projetos permanecem separados do aplicativo.'),
    'application': ('Aplicación extraída', 'Extracted application', 'Aplicativo extraído'),
    'workspace': ('Carpeta de datos y proyectos', 'Data and projects directory', 'Pasta de dados e projetos'),
    'previous': ('Aplicación anterior (opcional)', 'Previous application (optional)', 'Aplicativo anterior (opcional)'),
    'backups': ('Respaldos privados', 'Private backups', 'Backups privados'),
    'launcher': ('Acceso para abrir report-gen', 'Launcher to open report-gen', 'Atalho para abrir o report-gen'),
    'port': ('Puerto local del editor', 'Local editor port', 'Porta local do editor'),
    'browse': ('Elegir…', 'Browse…', 'Escolher…'),
    'paths': ('1 · Aplicación y datos', '1 · Application and data', '1 · Aplicativo e dados'),
    'actions': ('2 · Comprobar y preparar', '2 · Check and prepare', '2 · Verificar e preparar'),
    'recover_heading': ('3 · Recuperar una instalación', '3 · Recover an installation', '3 · Recuperar uma instalação'),
    'consent': ('Permitir descargar dependencias al instalar (requiere Internet).',
                'Allow dependency downloads during installation (requires Internet).',
                'Permitir baixar dependências durante a instalação (requer Internet).'),
    'stopped': ('Cierra todos los editores antes de instalar, actualizar o recuperar. Para versiones antiguas, indica su puerto real. Los datos antiguos dentro de webapp deben migrarse primero con start.py --upgrade-from.',
                'Close all editors before installing, updating or recovering. For older versions, enter their actual port. Legacy data inside webapp must first be migrated with start.py --upgrade-from.',
                'Feche todos os editores antes de instalar, atualizar ou recuperar. Em versões antigas, informe a porta real. Dados antigos dentro de webapp devem ser migrados primeiro com start.py --upgrade-from.'),
    'diagnose': ('Diagnosticar sin instalar', 'Diagnose without installing', 'Diagnosticar sem instalar'),
    'install': ('Instalar y activar', 'Install and activate', 'Instalar e ativar'),
    'update': ('Buscar actualización en GitHub', 'Check GitHub for an update', 'Buscar atualização no GitHub'),
    'recovery_note': ('Elige el registro de instalación guardado con tus respaldos. Se restaura la copia previa en una carpeta nueva y se abre con la aplicación anterior. Tus datos actuales se conservan.',
                      'Choose the installation receipt stored with your backups. Recovery restores the previous snapshot into a new folder and uses the previous application. Current data is preserved.',
                      'Escolha o registro de instalação salvo com seus backups. A recuperação restaura a cópia anterior em uma pasta nova e usa o aplicativo anterior. Os dados atuais são preservados.'),
    'receipt': ('Registro de instalación', 'Installation receipt', 'Registro de instalação'),
    'backup_file': ('Respaldo verificado', 'Verified backup', 'Backup verificado'),
    'preserved': ('Datos actuales conservados', 'Current data preserved', 'Dados atuais preservados'),
    'recover': ('Recuperar versión anterior', 'Recover previous version', 'Recuperar versão anterior'),
    'open': ('Abrir report-gen', 'Open report-gen', 'Abrir report-gen'),
    'ready': ('Listo para comprobar. No se descargó ni instaló nada.', 'Ready to check. Nothing has been downloaded or installed.', 'Pronto para verificar. Nada foi baixado ou instalado.'),
    'busy': ('La operación sigue en curso. Espera a que termine antes de cerrar.', 'An operation is still running. Wait until it finishes before closing.', 'Uma operação está em andamento. Aguarde sua conclusão antes de fechar.'),
    'setup': ('Preparando dependencias… Esto puede tardar varios minutos.', 'Preparing dependencies… This may take several minutes.', 'Preparando dependências… Isso pode levar vários minutos.'),
    'backup': ('Verificando el respaldo privado…', 'Verifying the private backup…', 'Verificando o backup privado…'),
    'activate': ('Activando el acceso local…', 'Activating the local launcher…', 'Ativando o atalho local…'),
    'restore': ('Restaurando en una carpeta nueva…', 'Restoring into a new folder…', 'Restaurando em uma pasta nova…'),
    'done': ('Operación terminada.', 'Operation completed.', 'Operação concluída.'),
    'error': ('No se pudo completar', 'Could not complete', 'Não foi possível concluir'),
    'up_to_date': ('No hay una versión más reciente publicada.', 'No newer version has been published.', 'Não há uma versão mais recente publicada.'),
    'update_ready': ('Actualización verificada y descargada. Revisa las carpetas y pulsa Instalar y activar para aplicarla.',
                     'Update verified and downloaded. Review the directories, then choose Install and activate to apply it.',
                     'Atualização verificada e baixada. Revise as pastas e selecione Instalar e ativar para aplicá-la.'),
    'no_tk': ('No se pudo abrir Tkinter. Este asistente necesita Python con Tk y una sesión gráfica. Alternativa: python start.py --ready --workspace RUTA. En Linux también puedes usar python scripts/install.py --workspace RUTA. No se instaló nada.',
              'Tkinter could not open. This wizard requires Python with Tk and a graphical session. Alternative: python start.py --ready --workspace PATH. On Linux you can also use python scripts/install.py --workspace PATH. Nothing was installed.',
              'Não foi possível abrir o Tkinter. Este assistente exige Python com Tk e uma sessão gráfica. Alternativa: python start.py --ready --workspace CAMINHO. No Linux, você também pode usar python scripts/install.py --workspace CAMINHO. Nada foi instalado.'),
}


class Wizard:
    def __init__(self, window, tk, ttk, filedialog, messagebox, lang='es'):
        self.window, self.tk, self.ttk = window, tk, ttk
        self.filedialog, self.messagebox, self.lang = filedialog, messagebox, lang
        self.events, self.busy, self.open_target = queue.Queue(), False, None
        self.controls = []
        self.fields = {}
        self.window.title(self.t('title')); self.window.geometry('980x800'); self.window.minsize(800, 720)
        frame = ttk.Frame(window, padding=20); frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=self.t('heading'), font=('TkDefaultFont', 19, 'bold')).pack(anchor='w')
        ttk.Label(frame, text=self.t('intro')).pack(anchor='w', pady=(5, 14))
        paths = ttk.LabelFrame(frame, text=self.t('paths'), padding=12); paths.pack(fill='x')
        defaults = {'application': str(ROOT), 'workspace': str(manager.default_data()), 'previous': '',
                    'backups': str(Path.home() / 'report-gen-backups'), 'launcher': str(manager.default_launcher()), 'port': '8080'}
        for row, (name, value) in enumerate(defaults.items()):
            ttk.Label(paths, text=self.t(name)).grid(row=row, column=0, sticky='w', padx=(0, 14), pady=3)
            variable = tk.StringVar(value=value); self.fields[name] = variable
            entry = ttk.Entry(paths, textvariable=variable); entry.grid(row=row, column=1, sticky='ew', pady=3)
            self.controls.append(entry)
            if name != 'port':
                button = ttk.Button(paths, text=self.t('browse'), command=lambda name=name: self.browse(name))
                button.grid(row=row, column=2, padx=(8, 0), pady=3); self.controls.append(button)
        paths.columnconfigure(1, weight=1)
        ttk.Label(frame, text=self.t('stopped'), wraplength=920, foreground='#555555').pack(anchor='w', pady=(8, 10))
        actions = ttk.LabelFrame(frame, text=self.t('actions'), padding=12); actions.pack(fill='x')
        self.allow = tk.BooleanVar(value=False)
        consent = ttk.Checkbutton(actions, text=self.t('consent'), variable=self.allow)
        consent.pack(anchor='w'); self.controls.append(consent)
        buttons = ttk.Frame(actions); buttons.pack(fill='x', pady=(10, 0))
        for key, operation in [('diagnose', self.diagnose), ('update', self.update), ('install', self.install)]:
            button = ttk.Button(buttons, text=self.t(key), command=operation)
            button.pack(side='left', padx=(0, 10)); self.controls.append(button)
        recovery = ttk.LabelFrame(frame, text=self.t('recover_heading'), padding=12); recovery.pack(fill='x', pady=(12, 0))
        ttk.Label(recovery, text=self.t('recovery_note'), wraplength=880).pack(anchor='w')
        row = ttk.Frame(recovery); row.pack(fill='x', pady=(8, 0))
        self.receipt = tk.StringVar()
        entry = ttk.Entry(row, textvariable=self.receipt); entry.pack(side='left', fill='x', expand=True); self.controls.append(entry)
        for key, action in [('browse', self.browse_receipt), ('recover', self.recover)]:
            button = ttk.Button(row, text=self.t(key), command=action); button.pack(side='left', padx=(8, 0)); self.controls.append(button)
        self.status = tk.StringVar(value=self.t('ready'))
        ttk.Label(frame, textvariable=self.status, wraplength=910).pack(anchor='w', pady=(12, 4))
        self.bar = ttk.Progressbar(frame, mode='indeterminate'); self.bar.pack(fill='x')
        self.open_button = ttk.Button(frame, text=self.t('open'), command=self.open, state='disabled')
        self.open_button.pack(side='bottom', anchor='e', pady=(8, 0))
        self.details = tk.Text(frame, height=7, wrap='word', state='disabled')
        self.details.pack(fill='both', expand=True, pady=(6, 0))
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.window.after(100, self.poll)

    def t(self, key):
        return TEXT[key][language_index(self.lang)]

    def browse(self, name):
        value = self.filedialog.asksaveasfilename(title=self.t(name), initialfile=Path(self.fields[name].get()).name) if name == 'launcher' else self.filedialog.askdirectory(title=self.t(name))
        if value:
            self.fields[name].set(value)

    def browse_receipt(self):
        value = self.filedialog.askopenfilename(title=self.t('receipt'), filetypes=[('JSON', '*.json')], initialdir=self.fields['backups'].get())
        if value:
            self.receipt.set(value)

    def plan(self):
        values = {key: variable.get().strip() for key, variable in self.fields.items()}
        return manager.Plan(Path(values['application']), Path(values['workspace']), Path(values['launcher']),
                            Path(values['backups']), Path(values['previous']) if values['previous'] else None,
                            self.lang, int(values['port'])).validate()

    def task(self, action, worker):
        if self.busy:
            return
        self.busy = True; self.bar.start(12); self.open_button.configure(state='disabled')
        for control in self.controls:
            control.configure(state='disabled')
        def execute():
            try:
                with language_scope(self.lang):
                    result = worker(lambda stage: self.events.put(('stage', stage)))
                self.events.put(('result', (action, result)))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=execute, daemon=False).start()

    def perform(self, action):
        try:
            # Recovery is described by its durable receipt, not editable fields.
            if action == 'recover':
                receipt = self.receipt.get()
                self.task(action, lambda progress: manager.recovery(receipt, progress=progress))
                return
            plan = self.plan()
            if action == 'diagnose':
                self.task(action, lambda progress: manager.diagnose(plan.application, self.lang))
            elif action == 'install':
                allowed = self.allow.get()
                self.task(action, lambda progress: manager.install(plan, allow_network=allowed, progress=progress))
            elif action == 'update':
                self.task(action, lambda progress: manager.prepare_update(plan, progress=progress))
        except (ValueError, OSError) as exc:
            self.messagebox.showerror(self.t('error'), str(exc))

    def diagnose(self): self.perform('diagnose')
    def install(self): self.perform('install')
    def update(self): self.perform('update')
    def recover(self): self.perform('recover')

    def poll(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == 'stage':
                    self.status.set(self.t(payload)); continue
                self.busy = False; self.bar.stop()
                for control in self.controls:
                    control.configure(state='normal')
                if kind == 'error':
                    self.status.set(self.t('error')); self.show(payload)
                    continue
                action, result = payload
                self.status.set(self.t('done'))
                if action == 'update':
                    if result.get('available'):
                        self.fields['previous'].set(self.fields['application'].get())
                        self.fields['application'].set(result['application'])
                        self.status.set(self.t('update_ready'))
                    else:
                        self.status.set(self.t('up_to_date'))
                elif action in ('install', 'recover'):
                    self.open_target = (Path(result['application']), Path(result['workspace']), self.lang,
                                        result['port'])
                    self.open_button.configure(state='normal')
                    if result.get('receipt'):
                        self.receipt.set(result['receipt'])
                self.show(self.describe(result))
        except queue.Empty:
            pass
        self.window.after(100, self.poll)

    def describe(self, result):
        diagnosis = result.get('diagnostics', result)
        lines = []
        if result.get('version'):
            lines.append('report-gen ' + result['version'])
        for check in diagnosis.get('checks', []):
            lines.append(('✓ ' if check.get('ready') else '! ') + check['label'] + ': ' + check['detail'])
        if diagnosis.get('note'):
            lines.append(diagnosis['note'])
        for key, label in [('application', 'application'), ('workspace', 'workspace'), ('launcher', 'launcher'),
                           ('backup', 'backup_file'), ('receipt', 'receipt'), ('current_workspace_preserved', 'preserved')]:
            if result.get(key):
                lines.append(self.t(label) + ': ' + str(result[key]))
        if result.get('backup_sha256'):
            lines.append('SHA-256: ' + result['backup_sha256'])
        return '\n\n'.join(lines)

    def show(self, text):
        self.details.configure(state='normal'); self.details.delete('1.0', 'end')
        self.details.insert('end', text); self.details.configure(state='disabled')

    def open(self):
        if self.open_target is None or self.busy:
            return
        root, workspace, lang, port = self.open_target
        try:
            subprocess.Popen([str(manager.python_for(root)), str(root / 'start.py'), '--workspace', str(workspace),
                              '--lang', lang, '--port', str(port)], cwd=root,
                             creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0)
        except OSError as exc:
            self.messagebox.showerror(self.t('error'), str(exc))

    def close(self):
        if self.busy:
            self.messagebox.showinfo(self.t('title'), self.t('busy'))
        else:
            self.window.destroy()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lang', type=language_argument, choices=['es', 'en', 'pt'], default='es')
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--launcher', type=Path)
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        parser.error('Python 3.11+ is required.')
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
        window = tk.Tk()
    except (ImportError, RuntimeError):
        print(TEXT['no_tk'][language_index(args.lang)], file=sys.stderr)
        return 2
    except Exception as exc:
        # TclError also covers headless machines and an unavailable window system.
        if type(exc).__name__ != 'TclError':
            raise
        print(TEXT['no_tk'][language_index(args.lang)], file=sys.stderr)
        return 2
    wizard = Wizard(window, tk, ttk, filedialog, messagebox, args.lang)
    for name in ('workspace', 'launcher'):
        if getattr(args, name) is not None:
            wizard.fields[name].set(str(getattr(args, name)))
    window.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
