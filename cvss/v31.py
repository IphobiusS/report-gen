"""Calculadora CVSS 3.1 Base (score, severidad y vector). Implementacion propia
segun la especificacion oficial FIRST CVSS v3.1."""
import math

AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.20}
AC = {"L": 0.77, "H": 0.44}
UI = {"N": 0.85, "R": 0.62}
CIA = {"H": 0.56, "L": 0.22, "N": 0.00}
PR_U = {"N": 0.85, "L": 0.62, "H": 0.27}
PR_C = {"N": 0.85, "L": 0.68, "H": 0.50}

METRICS = ["AV", "AC", "PR", "UI", "S", "C", "I", "A"]
DEFAULT = {"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "U", "C": "N", "I": "N", "A": "N"}


def _roundup(x):
    i = round(x * 100000)
    if i % 10000 == 0:
        return i / 100000.0
    return (math.floor(i / 10000) + 1) / 10.0


def severity_label(score):
    if score == 0:
        return "info"
    if score < 4.0:
        return "low"
    if score < 7.0:
        return "medium"
    if score < 9.0:
        return "high"
    return "critical"


def compute(m):
    """m: dict con AV,AC,PR,UI,S,C,I,A. Devuelve {score, severity, vector}."""
    mm = dict(DEFAULT)
    mm.update({k: v for k, v in (m or {}).items() if k in METRICS and v})
    scope_changed = mm["S"] == "C"
    pr = (PR_C if scope_changed else PR_U)[mm["PR"]]
    expl = 8.22 * AV[mm["AV"]] * AC[mm["AC"]] * pr * UI[mm["UI"]]
    iss = 1 - (1 - CIA[mm["C"]]) * (1 - CIA[mm["I"]]) * (1 - CIA[mm["A"]])
    if scope_changed:
        impact = 7.52 * (iss - 0.029) - 3.25 * pow(iss - 0.02, 15)
    else:
        impact = 6.42 * iss
    if impact <= 0:
        score = 0.0
    elif scope_changed:
        score = _roundup(min(1.08 * (impact + expl), 10))
    else:
        score = _roundup(min(impact + expl, 10))
    vector = "CVSS:3.1/" + "/".join(f"{k}:{mm[k]}" for k in METRICS)
    return {"score": round(score, 1), "severity": severity_label(score), "vector": vector, "metrics": mm}


def parse_vector(vector):
    m = dict(DEFAULT)
    if not vector:
        return m
    for part in vector.split("/"):
        if ":" in part:
            k, _, v = part.partition(":")
            if k in METRICS:
                m[k] = v
    return m


if __name__ == "__main__":
    tests = [
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", 9.8, "critical"),
        ("CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H", 9.9, "critical"),
        ("CVSS:3.1/AV:L/AC:H/PR:H/UI:R/S:U/C:L/I:L/A:N", 2.9, "low"),
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N", 0.0, "info"),
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N", 6.1, "medium"),
    ]
    ok = True
    for vec, exp_s, exp_sev in tests:
        r = compute(parse_vector(vec))
        status = "OK" if (r["score"] == exp_s and r["severity"] == exp_sev) else "FALLA"
        if status == "FALLA":
            ok = False
        print(f"{status}  {vec}  -> {r['score']} {r['severity']} (esperado {exp_s} {exp_sev})")
    print("TODOS OK" if ok else "HAY FALLAS")
