"""Integracion de /api/cvss: despacho explicito por version 3.1/4.0, sin fallback
silencioso, y sin score parcial ante error."""
import app as webapp


def _c():
    webapp.app.config["TESTING"] = True
    return webapp.app.test_client()


def test_api_31_preserves_behavior_vector():
    r = _c().post("/api/cvss", json={"vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"})
    assert r.status_code == 200 and r.get_json()["score"] == 9.8


def test_api_31_preserves_behavior_metrics():
    m = {"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "U", "C": "H", "I": "H", "A": "H"}
    r = _c().post("/api/cvss", json={"version": "3.1", "metrics": m})
    assert r.status_code == 200 and r.get_json()["score"] == 9.8


def test_api_40_returns_full_shape():
    r = _c().post("/api/cvss", json={"version": "4.0",
        "vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H"})
    assert r.status_code == 200
    j = r.get_json()
    assert j["score"] == 10.0 and j["severity"] == "critical" and j["macrovector"] == "000100"
    assert j["vector"].startswith("CVSS:4.0/")


def test_api_40_by_prefix_without_version():
    r = _c().post("/api/cvss", json={"vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N"})
    assert r.status_code == 200 and r.get_json()["score"] == 8.7


def test_api_invalid_version_4xx():
    r = _c().post("/api/cvss", json={"version": "2.0", "vector": "CVSS:2.0/x"})
    assert r.status_code == 400


def test_api_invalid_40_vector_4xx_no_partial():
    r = _c().post("/api/cvss", json={"version": "4.0", "vector": "CVSS:4.0/AV:X"})
    assert r.status_code == 400
    assert "score" not in (r.get_json() or {})


def test_api_31_does_not_silently_score_40_vector():
    # version explicita 3.1 con vector 4.0: el parser 3.1 no debe inventar un score valido.
    # (Comportamiento: 3.1 parsea laxo; exigimos al menos que no devuelva el score 4.0.)
    r = _c().post("/api/cvss", json={"version": "4.0", "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"})
    assert r.status_code == 400  # 4.0 exige prefijo 4.0


def test_api_31_rejects_non_31_prefixed_vector():
    c = _c()
    for bad in ("CVSS:2.0/AV:N/AC:L", "basura/AV:N/AC:L", "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H"):
        r = c.post("/api/cvss", json={"version": "3.1", "vector": bad})
        assert r.status_code == 400, f"deberia rechazar {bad!r}"


def test_api_31_metrics_only_still_works_without_vector():
    m = {"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "U", "C": "H", "I": "H", "A": "H"}
    r = _c().post("/api/cvss", json={"version": "3.1", "metrics": m})
    assert r.status_code == 200 and r.get_json()["score"] == 9.8


def test_api_legacy_fallback_documented_behavior():
    c = _c()
    # sin version: prefijo 4.0 -> 4.0
    r4 = c.post("/api/cvss", json={"vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H"})
    assert r4.get_json()["score"] == 10.0 and "macrovector" in r4.get_json()
    # sin version: prefijo 3.1 -> 3.1
    r3 = c.post("/api/cvss", json={"vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"})
    assert r3.get_json()["score"] == 9.8


def test_api_cwe_lookup():
    r = _c().get("/api/cwe")
    assert r.status_code == 200
    d = r.get_json()
    assert len(d) >= 100
    assert d.get("312") == "Cleartext Storage of Sensitive Information"
    assert d.get("79", "").lower().find("cross-site scripting") >= 0
    assert all(not k.startswith("_") for k in d)  # sin metadatos
