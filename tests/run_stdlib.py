"""Runner minimo con solo la libreria estandar, para correr la suite donde no
haya pytest instalado. Descubre funciones test_* en los modulos test_*.py y las
ejecuta. Con pytest instalado, usa pytest en su lugar.

    python tests/run_stdlib.py
"""
import importlib
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "webapp", ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def main():
    test_files = sorted(Path(__file__).parent.glob("test_*.py"))
    passed = failed = skipped = 0
    failures = []
    from _support import Skipped
    for tf in test_files:
        mod = importlib.import_module(tf.stem)
        for name in dir(mod):
            if not name.startswith("test_"):
                continue
            fn = getattr(mod, name)
            if not callable(fn):
                continue
            try:
                fn()
                passed += 1
            except Skipped:
                skipped += 1
            except Exception:
                failed += 1
                failures.append((f"{tf.stem}.{name}", traceback.format_exc()))
    print(f"\n{'=' * 50}")
    for tid, tb in failures:
        print(f"FALLA {tid}\n{tb}")
    print(f"RESULTADO: {passed} OK, {skipped} SKIP, {failed} fallas ({len(test_files)} modulos)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
