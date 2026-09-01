"""Exportacion a PDF: delega en engine.py (render a dos pasadas)."""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def export_pdf(yaml_path, out_path):
    yaml_path = Path(yaml_path).resolve()
    out = Path(out_path)
    subprocess.run([sys.executable, str(REPO_ROOT / "engine.py"), str(yaml_path), "-o", str(out)],
                   cwd=str(REPO_ROOT), check=True)
    return out
