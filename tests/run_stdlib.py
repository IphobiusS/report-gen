"""Entrada de compatibilidad: la suite actual necesita pytest y sus fixtures.

Instala las dependencias con: python -m pip install -e ".[dev]"
Instala las pruebas de interfaz con: npm install --ignore-scripts
"""
from pathlib import Path
import subprocess
import sys

if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", *sys.argv[1:]], cwd=Path(__file__).resolve().parent.parent))
