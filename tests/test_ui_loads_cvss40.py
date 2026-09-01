"""Tras la integracion, index.html DEBE cargar cvss40.js (antes solo se exigia que
NO lo cargara; ahora es al reves)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_index_html_loads_cvss40_before_app():
    html = (ROOT / "webapp" / "static" / "index.html").read_text(encoding="utf-8")
    assert "/static/cvss40.js" in html
    assert html.index("/static/cvss40.js") < html.index("/static/app.js")


def test_app_js_delegates_40_to_module_not_duplicated():
    js = (ROOT / "webapp" / "static" / "app.js").read_text(encoding="utf-8")
    # la UI 4.0 debe llamar al modulo, no reimplementar la interpolacion
    assert "window.CVSS40" in js
    assert "MAX_SEVERITY" not in js and "MAX_COMPOSED" not in js  # sin tablas 4.0 duplicadas en app.js
