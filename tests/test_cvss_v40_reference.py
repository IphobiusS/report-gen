"""CVSS 4.0: nuestra implementacion vs el corpus de referencia de FIRST/Red Hat.

Este fichero valida contra un ORACULO EXTERNO (expected congelado en
tests/reference/first_v40_vectors.json, generado por copia fiel de la
implementacion de referencia FIRST/Red Hat). Separado a proposito de
test_cvss_v40.py, que contiene propiedades definidas por nosotros (parser, EQ,
invariantes estructurales)."""
import json
from pathlib import Path

from cvss import v40

CORPUS = json.loads((Path(__file__).parent / "reference" / "first_v40_vectors.json").read_text(encoding="utf-8"))
VECTORS = CORPUS["vectors"]


def test_corpus_is_substantial_and_covers_270_macrovectors():
    assert len(VECTORS) >= 300
    assert len({e["expected_macrovector"] for e in VECTORS}) == 270


def test_scores_match_first_reference():
    mism = []
    for e in VECTORS:
        eff = v40.effective_metrics(v40.parse_vector(e["vector"]))
        got = v40._score(eff)
        if got != e["expected_score"]:
            mism.append((e["vector"], got, e["expected_score"]))
    assert not mism, f"{len(mism)} divergencias vs FIRST, p.ej. {mism[:3]}"


def test_macrovectors_match_first_reference():
    for e in VECTORS:
        eff = v40.effective_metrics(v40.parse_vector(e["vector"]))
        assert v40.macrovector(eff) == e["expected_macrovector"], e["vector"]


def test_public_score_matches_corpus():
    for e in VECTORS[:50]:
        assert v40.score(e["vector"])["score"] == e["expected_score"]


def test_anchor_scores_published_by_first():
    assert v40.score("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H")["score"] == 10.0
    assert v40.score("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:N/SA:N")["score"] == 0.0


def test_rounding_regression_issue_vector():
    # MacroVector 001200 tiene 8.8 en la tabla, pero el vector interpolado da 8.7.
    # Caso historico de frontera de redondeo/interpolacion en CVSS 4.0.
    r = v40.score("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N")
    assert r["macrovector"] == "001200" and r["score"] == 8.7
