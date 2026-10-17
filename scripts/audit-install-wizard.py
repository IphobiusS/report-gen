#!/usr/bin/env python3
"""Exercise and capture the actual Tk wizard (run under Xvfb on Linux CI)."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.install_wizard import Wizard  # noqa: E402


def main():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    from PIL import ImageGrab
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    for lang in ('es', 'en', 'pt'):
        with tempfile.TemporaryDirectory(prefix='report-gen-wizard-qa-') as temporary:
            root = Path(temporary)
            window = tk.Tk()
            try:
                wizard = Wizard(window, tk, ttk, filedialog, messagebox, lang)
                window.geometry('980x800+30+30')
                wizard.fields['workspace'].set(str(root / 'data'))
                wizard.fields['backups'].set(str(root / 'backups'))
                wizard.fields['launcher'].set(str(root / 'report-gen'))
                window.update()
                assert not wizard.busy and not wizard.allow.get()
                assert all(control.winfo_ismapped() for control in wizard.controls)
                assert all(control.winfo_rooty() + control.winfo_height() <= window.winfo_rooty() + window.winfo_height()
                           for control in wizard.controls), 'A wizard control is clipped'
                def capture(name):
                    window.update()
                    x, y = window.winfo_rootx(), window.winfo_rooty()
                    image = ImageGrab.grab(bbox=(x, y, x + window.winfo_width(), y + window.winfo_height()))
                    target = args.output / name
                    image.save(target)
                    return {'path': target.name, 'sha256': sha256(target.read_bytes()).hexdigest(),
                            'width': image.width, 'height': image.height}
                initial = capture('installer-' + lang + '.png')
                # A real diagnostic action must not create/install an environment.
                existing = (ROOT / '.venv').exists()
                wizard.diagnose()
                assert wizard.busy and all(str(control.cget('state')) == 'disabled' for control in wizard.controls)
                deadline = time.monotonic() + 150
                while wizard.busy and time.monotonic() < deadline:
                    window.update(); time.sleep(.02)
                assert not wizard.busy and wizard.status.get() == wizard.t('done')
                assert (ROOT / '.venv').exists() == existing
                diagnostic = capture('installer-' + lang + '-diagnostic.png')
                assert not list(root.rglob('*')), 'Diagnostic changed private paths'
                rows.append({'language': lang, 'checks_passed': 7, 'screenshots': [initial, diagnostic]})
            finally:
                window.destroy()
    receipt = {'schema': 1, 'passed': True, 'interface': 'native Tkinter', 'languages': rows,
               'limits': ['No dependency download, Windows desktop, or recovery performed in this GUI capture; backend integration tests cover real backup/recovery separately.']}
    (args.output / 'installer-gui.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': True, 'languages': len(rows), 'screenshots': 6}))


if __name__ == '__main__':
    main()
