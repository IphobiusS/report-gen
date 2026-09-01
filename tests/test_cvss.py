"""Tests de la calculadora CVSS 3.1: vectores oficiales, bandas de severidad,
consistencia total sobre las 2592 combinaciones y paridad Python vs puerto JS."""
import itertools
import json
import shutil
import subprocess
from pathlib import Path

import cvss

ROOT = Path(__file__).resolve().parent.parent

# Vectores oficiales / CVE conocidos con score y severidad esperados.
OFFICIAL = [
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", 9.8, "critical"),
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H", 10.0, "critical"),
    ("CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H", 8.1, "high"),
    ("CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H", 7.8, "high"),
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H", 7.5, "high"),
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N", 6.1, "medium"),
    ("CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:N/A:N", 5.9, "medium"),
    ("CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:U/C:L/I:L/A:N", 2.9, "low"),
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N", 0.0, "info"),
    ("CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H", 9.9, "critical"),
    ("CVSS:3.1/AV:L/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", 8.4, "high"),
    ("CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", 8.8, "high"),
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N", 5.3, "medium"),
    ("CVSS:3.1/AV:P/AC:H/PR:H/UI:R/S:U/C:L/I:N/A:N", 1.6, "low"),
    ("CVSS:3.1/AV:N/AC:L/PR:H/UI:N/S:C/C:H/I:H/A:H", 9.1, "critical"),
]

VALS = {"AV": "NALP", "AC": "LH", "PR": "NLH", "UI": "NR",
        "S": "UC", "C": "HLN", "I": "HLN", "A": "HLN"}


def test_official_vectors():
    for vec, score, sev in OFFICIAL:
        r = cvss.compute(cvss.parse_vector(vec))
        assert r["score"] == score, f"{vec}: {r['score']} != {score}"
        assert r["severity"] == sev, f"{vec}: {r['severity']} != {sev}"


def test_severity_bands():
    assert cvss.severity_label(0.0) == "info"
    assert cvss.severity_label(3.9) == "low"
    assert cvss.severity_label(4.0) == "medium"
    assert cvss.severity_label(6.9) == "medium"
    assert cvss.severity_label(7.0) == "high"
    assert cvss.severity_label(8.9) == "high"
    assert cvss.severity_label(9.0) == "critical"
    assert cvss.severity_label(10.0) == "critical"


def test_roundup():
    assert cvss._roundup(4.0) == 4.0
    assert cvss._roundup(4.01) == 4.1
    assert cvss._roundup(0.0) == 0.0


def test_all_combinations_in_range():
    """Las 2592 combinaciones dan un score valido en [0, 10]."""
    n = 0
    for combo in itertools.product(*VALS.values()):
        m = dict(zip(VALS.keys(), combo))
        r = cvss.compute(m)
        assert 0.0 <= r["score"] <= 10.0
        assert r["severity"] in {"info", "low", "medium", "high", "critical"}
        n += 1
    assert n == 2592


def test_vector_roundtrip():
    for vec, _, _ in OFFICIAL:
        r = cvss.compute(cvss.parse_vector(vec))
        assert r["vector"] == vec


def test_python_js_parity():
    """El puerto JS del navegador debe coincidir con el Python en TODAS las
    combinaciones. Se salta si node no esta disponible."""
    node = shutil.which("node")
    if not node:  # pragma: no cover
        return
    harness = ROOT / "tests" / "_cvss_harness.js"
    src = (ROOT / "webapp" / "static" / "app.js").read_text(encoding="utf-8")
    cv = src[src.index("const CV = {"):src.index("function roundup")]
    fns = src[src.index("function roundup"):src.index("function cvssParse")]
    fns += "function cvssParse(v){const m=Object.assign({},CV.D);(v||'').split('/').forEach(p=>{const[k,val]=p.split(':');if(CV.M.includes(k))m[k]=val;});return m;}"
    harness.write_text(cv + "\n" + fns + "\nconst out=[];function rec(i,m){const K=CV.M;if(i===K.length){out.push(cvssCompute(m).score.toFixed(1));return;}const vals={AV:'NALP',AC:'LH',PR:'NLH',UI:'NR',S:'UC',C:'HLN',I:'HLN',A:'HLN'};for(const c of vals[K[i]]){m[K[i]]=c;rec(i+1,Object.assign({},m));}}rec(0,{});console.log(JSON.stringify(out));\n", encoding="utf-8")
    try:
        res = subprocess.run([node, str(harness)], capture_output=True, text=True, timeout=60)
        js_scores = json.loads(res.stdout)
    finally:
        harness.unlink(missing_ok=True)
    py_scores = []
    keys = ["AV", "AC", "PR", "UI", "S", "C", "I", "A"]
    for combo in itertools.product(*[VALS[k] for k in keys]):
        m = dict(zip(keys, combo))
        py_scores.append(f"{cvss.compute(m)['score']:.1f}")
    assert len(js_scores) == len(py_scores) == 2592
    assert js_scores == py_scores


def test_score_dispatch_31_correct():
    r = cvss.score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")
    assert r["score"] == 9.8 and r["severity"] == "critical"


def test_score_dispatch_40_returns_number():
    # Tras la validacion contra FIRST, el dispatch 4.0 devuelve score real.
    r = cvss.score("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H")
    assert r["score"] == 10.0 and r["severity"] == "critical"


def test_score_rejects_unknown_version():
    for bad in ("CVSS:2.0/AV:N/AC:L/Au:N/C:C/I:C/A:C", "basura", ""):
        try:
            cvss.score(bad)
            assert False, f"deberia rechazar: {bad!r}"
        except ValueError:
            pass
