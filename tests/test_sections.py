"""Tests del catalogo canonico de secciones y su resolucion."""
import sections


def test_catalog_loads():
    cat = sections.load_catalog()
    assert "sections" in cat and len(cat["sections"]) >= 10
    keys = {s["key"] for s in cat["sections"]}
    for k in ("confidentiality", "executive_summary", "findings", "appendix"):
        assert k in keys


def test_catalog_bilingual_titles():
    for s in sections.load_catalog()["sections"]:
        assert s.get("title_es") and s.get("title_en")


def test_default_enabled_includes_required():
    cat = sections.load_catalog()
    required = {s["key"] for s in cat["sections"] if s.get("required")}
    default = {s["key"] for s in sections.default_enabled()}
    assert required.issubset(default), "todas las obligatorias deben venir activas"


def test_presets_reference_real_sections():
    cat = sections.load_catalog()
    keys = {s["key"] for s in cat["sections"]}
    for name, plist in (cat.get("presets") or {}).items():
        for k in plist:
            assert k in keys, f"preset {name} referencia seccion inexistente {k}"


def test_resolve_sections_localizes_and_fills_values():
    data = {"report": {"sections": [
        {"key": "executive_summary", "summary": "Contenido X"},
        {"key": "findings"},
    ]}}
    L = {}
    resolved = sections.resolve_sections(data, L, "en")
    exec_sec = next(s for s in resolved if s["key"] == "executive_summary")
    assert exec_sec["title"] == "Executive Summary"  # titulo en ingles
    field = exec_sec["fields"][0]
    assert field["value"] == "Contenido X"
    findings_sec = next(s for s in resolved if s["key"] == "findings")
    assert findings_sec["special"] == "findings"


def test_resolve_ignores_unknown_keys():
    data = {"report": {"sections": [{"key": "no_existe"}, {"key": "confidentiality"}]}}
    resolved = sections.resolve_sections(data, {}, "es")
    assert [s["key"] for s in resolved] == ["confidentiality"]


def test_presets_load_and_resolve():
    """Los presets cargan, resuelven secciones validas y traen contenido bilingue."""
    import sections
    presets = sections.load_presets()
    ids = {p["id"] for p in presets}
    assert {"base", "client", "exam", "cpts", "cwes", "ctf"} <= ids
    catalog_keys = {s["key"] for s in sections.load_catalog()["sections"]}
    for p in presets:
        for sec in sections.preset_sections(p["id"], "es"):
            # cada seccion es del catalogo, o generica (apendice nombrado) con titulo propio
            assert sec["key"] in catalog_keys or sec.get("title")
    # contenido base bilingue
    ctf_es = sections.preset_sections("ctf", "es")[0]
    ctf_en = sections.preset_sections("ctf", "en")[0]
    assert "Walkthrough" in ctf_es.get("summary", "") and ctf_es["summary"] != ctf_en["summary"]
    # preset inexistente -> default
    assert sections.preset_sections("nope", "es") == sections.default_enabled()
