"""Tests del validador de engagement (schema sin dependencias)."""
import validate

KEYS = {"confidentiality", "executive_summary", "findings", "appendix"}


def _levels(issues):
    return {lvl for lvl, _ in issues}


def test_valid_engagement_has_no_errors():
    data = {
        "meta": {"lang": "es", "report_title": "OK"},
        "report": {"sections": [{"key": "confidentiality"}, {"key": "findings"}]},
        "findings": [{"id": "F1", "mode": "vuln", "severity": "high",
                      "cvss": "8.1", "cvss_vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H"}],
    }
    issues = validate.validate(data, known_section_keys=KEYS)
    assert "error" not in _levels(issues)


def test_duplicate_ids_error():
    data = {"findings": [{"id": "F1"}, {"id": "F1"}]}
    issues = validate.validate(data, known_section_keys=KEYS)
    assert any("duplicad" in m.lower() and lvl == "error" for lvl, m in issues)


def test_invalid_severity_error():
    data = {"findings": [{"id": "F1", "severity": "grave"}]}
    issues = validate.validate(data, known_section_keys=KEYS)
    assert any("severidad" in m.lower() and lvl == "error" for lvl, m in issues)


def test_machine_without_host_warns():
    data = {"findings": [{"id": "M1", "mode": "machine"}]}
    issues = validate.validate(data, known_section_keys=KEYS)
    assert any("host" in m.lower() and lvl == "warning" for lvl, m in issues)


def test_bad_cvss_vector_warns():
    data = {"findings": [{"id": "F1", "cvss_vector": "CVSS:3.1/AV:X/nope"}]}
    issues = validate.validate(data, known_section_keys=KEYS)
    assert any("cvss" in m.lower() for _, m in issues)


def test_severity_cvss_mismatch_warns():
    data = {"findings": [{"id": "F1", "severity": "low", "cvss": "9.8"}]}
    issues = validate.validate(data, known_section_keys=KEYS)
    assert any("no coincide" in m.lower() for _, m in issues)


def test_unknown_section_error():
    data = {"report": {"sections": [{"key": "inventada"}]}}
    issues = validate.validate(data, known_section_keys=KEYS)
    assert any("seccion desconocida" in m.lower() and lvl == "error" for lvl, m in issues)


def test_severity_from_score_bands():
    assert validate.severity_from_score("0.0") == "info"
    assert validate.severity_from_score("3.9") == "low"
    assert validate.severity_from_score("6.9") == "medium"
    assert validate.severity_from_score("8.9") == "high"
    assert validate.severity_from_score("9.8") == "critical"
    assert validate.severity_from_score("abc") is None


def test_cvss_40_vectors_not_flagged():
    """Los vectores CVSS 4.0 validos NO deben marcarse como 'formato inesperado';
    solo los realmente malformados."""
    import validate
    def warns(vec):
        d = {"meta": {"lang": "es", "report_title": "T", "theme": "serio"},
             "findings": [{"id": "F1", "mode": "vuln", "title": "x", "severity": "high",
                           "cvss": "7.1", "cvss_vector": vec}]}
        return any("formato inesperado" in m for _, m in validate.validate(d))
    assert not warns("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N")
    assert not warns("CVSS:4.0/AV:N/AC:H/AT:N/PR:N/UI:N/VC:L/VI:N/VA:N/SC:N/SI:N/SA:N")
    assert not warns("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N")
    assert warns("CVSS:4.0/AV:X/AC:L")  # malformado sí


def test_english_messages():
    data = {"findings": [{"id": "F1", "mode": "machine"}, {"id": "F2", "mode": "vuln"}]}
    issues = validate.validate(data, known_section_keys=KEYS, lang="en")
    msgs = " ".join(m for _, m in issues).lower()
    assert "without host block" in msgs
    assert "without cvss score" in msgs


def test_spanish_is_default():
    data = {"findings": [{"id": "M1", "mode": "machine"}]}
    issues = validate.validate(data, known_section_keys=KEYS)
    assert any("sin bloque host" in m.lower() for _, m in issues)
