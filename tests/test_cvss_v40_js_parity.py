"""Paridad Python <-> JavaScript para CVSS 4.0.

`webapp/static/cvss40.js` es un port MECANICO del Python congelado (`cvss/v40.py`).
Este test exige que produzca EXACTAMENTE lo mismo (score Y macrovector, no solo
score) sobre el corpus congelado + una muestra amplia determinista, y valida por
separado los defaults/X y MSI:S/MSA:S. Se salta si `node` no esta disponible.

El modulo JS NO esta cableado a la UI todavia: este checkpoint es exclusivamente
"JS 4.0 implementado; paridad Python<->JS demostrada", sin tocar Flask/HTML/calc.
"""
import json
import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path

from cvss import v40
from _support import skip

ROOT = Path(__file__).resolve().parent.parent
CVSS40_JS = ROOT / "webapp" / "static" / "cvss40.js"
NODE = shutil.which("node")

ORDER = v40.METRIC_ORDER
BASE = v40.BASE
OPT = {**v40.THREAT, **v40.ENVIRONMENTAL, **v40.SUPPLEMENTAL}


def _build(m):
    return "CVSS:4.0/" + "/".join(f"{k}:{m[k]}" for k in ORDER if k in m)


def _sample():
    """Corpus congelado (367) + ~20k deterministas (misma semilla que la validacion
    contra la referencia)."""
    vectors = {e["vector"] for e in json.loads(
        (ROOT / "tests" / "reference" / "first_v40_vectors.json").read_text(encoding="utf-8"))["vectors"]}
    rng = random.Random(20260831)

    def rv(p):
        m = {k: rng.choice(v) for k, v in BASE.items()}
        for k, vals in OPT.items():
            if rng.random() < p:
                m[k] = rng.choice(vals)
        return _build(m)

    for _ in range(6000):
        vectors.add(rv(0.0))
    for _ in range(3000):
        m = {k: rng.choice(v) for k, v in BASE.items()}
        m["E"] = rng.choice(["A", "P", "U", "X"])
        vectors.add(_build(m))
    for _ in range(4000):
        vectors.add(rv(0.5))
    for _ in range(5000):
        vectors.add(rv(0.85))
    for _ in range(2000):
        m = {k: rng.choice(v) for k, v in BASE.items()}
        m["MSI"] = rng.choice(["S", "H", "L", "N", "X"])
        m["MSA"] = rng.choice(["S", "H", "L", "N", "X"])
        vectors.add(_build(m))
    return sorted(vectors)


def _run_js(vectors, effective=False):
    """Ejecuta cvss40.js bajo node sobre `vectors`; devuelve dict vec -> datos."""
    with tempfile.TemporaryDirectory() as d:
        vf = Path(d) / "v.json"
        vf.write_text(json.dumps(vectors), encoding="utf-8")
        emit = ("{score:r.score,macrovector:r.macrovector,effective:C.effectiveMetrics(C.parseVector(vec))}"
                if effective else "[r.score,r.macrovector]")
        run = Path(d) / "run.js"
        run.write_text(
            f'const C=require({json.dumps(str(CVSS40_JS))});const fs=require("fs");'
            f'const V=JSON.parse(fs.readFileSync({json.dumps(str(vf))},"utf8"));const out={{}};'
            f'for(const vec of V){{const r=C.score(vec);out[vec]={emit};}}'
            f'process.stdout.write(JSON.stringify(out));', encoding="utf-8")
        res = subprocess.run([NODE, str(run)], capture_output=True, text=True, encoding="utf-8", timeout=120)
        if res.returncode:
            raise RuntimeError("node fallo: " + res.stderr[:300])
        return json.loads(res.stdout)


def test_js_parity_score_and_macrovector():
    if not NODE:
        skip("Node.js no disponible")
    vectors = _sample()
    js = _run_js(vectors)
    mism_score, mism_macro = [], []
    for vec in vectors:
        eff = v40.effective_metrics(v40.parse_vector(vec))
        if v40._score(eff) != js[vec][0]:
            mism_score.append(vec)
        if v40.macrovector(eff) != js[vec][1]:
            mism_macro.append(vec)
    assert len(vectors) >= 20000
    assert len({v40.macrovector(v40.effective_metrics(v40.parse_vector(v))) for v in vectors}) == 270
    assert not mism_score, f"{len(mism_score)} divergencias de score, p.ej. {mism_score[:3]}"
    assert not mism_macro, f"{len(mism_macro)} divergencias de macrovector, p.ej. {mism_macro[:3]}"


def test_js_effective_metrics_and_defaults():
    if not NODE:
        skip("Node.js no disponible")
    # Vectores que ejercen defaults/X y safety, donde una traduccion inocua romperia EQ4.
    base = "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H"
    cases = [
        base,                                   # sin opcionales -> E:X, CR/IR/AR:X, modificadas ausentes
        base + "/E:X/CR:X/IR:X/AR:X",           # X explicitas
        base + "/E:P/CR:L/MSI:S",               # threat + env + safety
        base + "/MSI:S/MSA:S",                  # doble safety -> EQ4=0
        base + "/MAV:P/MAC:H/MSC:N/MSI:N/MSA:N",  # modificadas explicitas
        "CVSS:4.0/AV:P/AC:H/AT:P/PR:H/UI:A/VC:N/VI:L/VA:N/SC:L/SI:N/SA:N/E:U",
    ]
    js = _run_js(cases, effective=True)
    for vec in cases:
        py_eff = v40.effective_metrics(v40.parse_vector(vec))
        assert js[vec]["effective"] == py_eff, f"effective distinto en {vec}"
        assert js[vec]["macrovector"] == v40.macrovector(py_eff), f"macrovector distinto en {vec}"


def test_js_anchors_published_by_first():
    if not NODE:
        skip("Node.js no disponible")
    js = _run_js([
        "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H",
        "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N",
        "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:N/SA:N",
    ])
    assert js["CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H"][0] == 10.0
    assert js["CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N"][0] == 8.7
    assert js["CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:N/SA:N"][0] == 0.0
