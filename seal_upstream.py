"""Sello upstream de CVSS 4.0: compara nuestro cvss/v40.py contra la implementacion
de referencia REAL de FIRST/Red Hat (paquete PyPI `cvss`), ejecutada sin modificar.

Requisitos (en un venv LIMPIO, NO instales report-gen):
    pip install cvss==3.6
Ejecucion (desde la RAIZ del repo, donde esta la carpeta cvss/):
    python seal_upstream.py

Que hace:
  - Genera el corpus congelado (tests/reference/first_v40_vectors.json) + ~20k
    vectores deterministas (misma semilla que la validacion del proyecto).
  - Puntua cada vector con NUESTRO cvss/v40.py (paquete local).
  - Puntua los MISMOS vectores con el paquete `cvss` de PyPI (upstream real) en un
    SUBPROCESO aislado, para evitar la colision de nombres cvss local vs cvss PyPI.
  - Reporta divergencias. 0 => "Python CVSS 4.0 parity with reference implementation: 100%".

Nota: los vectores se construyen en orden canonico, asi que tanto nuestro parser
(estricto) como el de upstream (laxo) los aceptan; no hay diferencias de aceptacion
sintactica que interpretar como divergencias del scorer.
"""
import json
import os
import random
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.abspath(__file__))

# ---- 1) NUESTRO score (paquete local; REPO al frente del path) ----
sys.path.insert(0, REPO)
from cvss import v40  # noqa: E402  (paquete local del repo)

BASE = v40.BASE
OPT = {**v40.THREAT, **v40.ENVIRONMENTAL, **v40.SUPPLEMENTAL}
ORDER = v40.METRIC_ORDER


def build(m):
    return "CVSS:4.0/" + "/".join(f"{k}:{m[k]}" for k in ORDER if k in m)


def generate_vectors():
    vectors = set()
    corpus_path = os.path.join(REPO, "tests", "reference", "first_v40_vectors.json")
    with open(corpus_path, encoding="utf-8") as fh:
        for e in json.load(fh)["vectors"]:
            vectors.add(e["vector"])
    rng = random.Random(20260831)

    def rv(p):
        m = {k: rng.choice(v) for k, v in BASE.items()}
        for k, vals in OPT.items():
            if rng.random() < p:
                m[k] = rng.choice(vals)
        return build(m)

    for _ in range(6000):
        vectors.add(rv(0.0))
    for _ in range(3000):
        m = {k: rng.choice(v) for k, v in BASE.items()}
        m["E"] = rng.choice(["A", "P", "U", "X"])
        vectors.add(build(m))
    for _ in range(4000):
        vectors.add(rv(0.5))
    for _ in range(5000):
        vectors.add(rv(0.85))
    for _ in range(2000):
        m = {k: rng.choice(v) for k, v in BASE.items()}
        m["MSI"] = rng.choice(["S", "H", "L", "N", "X"])
        m["MSA"] = rng.choice(["S", "H", "L", "N", "X"])
        vectors.add(build(m))
    return sorted(vectors)


CHILD = r'''
import json, sys
vectors = json.load(open(sys.argv[1], encoding="utf-8"))
import cvss                      # <-- PyPI upstream (cwd = tempdir, sin cvss local en path)
from cvss import CVSS4
print("[seal] upstream cvss version:", getattr(cvss, "__version__", "?"), file=sys.stderr)
out = {}
for v in vectors:
    try:
        c = CVSS4(v)
        s = getattr(c, "base_score", None)
        if s is None:
            s = c.scores()[0]
        out[v] = float(s)
    except Exception as e:  # noqa: BLE001
        out[v] = "ERR:" + str(e)[:60]
json.dump(out, open(sys.argv[2], "w"))
'''


def score_upstream(vectors):
    tmp = tempfile.gettempdir()
    vec_file = os.path.join(tmp, "seal_vectors.json")
    child_file = os.path.join(tmp, "seal_child.py")
    out_file = os.path.join(tmp, "seal_upstream_scores.json")
    with open(vec_file, "w", encoding="utf-8") as fh:
        json.dump(vectors, fh)
    with open(child_file, "w", encoding="utf-8") as fh:
        fh.write(CHILD)
    # cwd=tmp para que 'import cvss' resuelva al de PyPI, no al paquete local del repo
    subprocess.run([sys.executable, child_file, vec_file, out_file], cwd=tmp, check=True)
    with open(out_file, encoding="utf-8") as fh:
        return json.load(fh)


def norm(x):
    try:
        return f"{float(x):.1f}"
    except (TypeError, ValueError):
        return str(x)


def main():
    vectors = generate_vectors()
    print(f"[seal] vectores a comparar: {len(vectors)}")
    ours = {v: v40.score(v)["score"] for v in vectors}
    upstream = score_upstream(vectors)

    errors = [v for v in vectors if isinstance(upstream.get(v), str)]
    mismatches = [(v, ours[v], upstream[v]) for v in vectors
                  if v not in errors and norm(ours[v]) != norm(upstream[v])]

    macros = len({v40.macrovector(v40.effective_metrics(v40.parse_vector(v))) for v in vectors})
    print(f"[seal] MacroVectors cubiertos: {macros}/270")
    print(f"[seal] errores de parseo en upstream: {len(errors)}")
    print(f"[seal] DIVERGENCIAS de score: {len(mismatches)}")
    for v, o, u in mismatches[:15]:
        print(f"    {v}\n      ours={o}  upstream={u}")
    if errors:
        print("[seal] vectores con ERR upstream (revisar; no deberia haber):")
        for v in errors[:10]:
            print(f"    {v} -> {upstream[v]}")

    ok = not mismatches and not errors
    print("\n" + ("=" * 60))
    if ok:
        print("SELLO OK: Python CVSS 4.0 parity with reference implementation: 100%")
        print(f"  Reference: RedHatProductSecurity/cvss (pip cvss), {len(vectors)} vectores, 0 divergencias.")
    else:
        print("SELLO PENDIENTE: hay divergencias o errores. Revisar arriba.")
    print("=" * 60)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
