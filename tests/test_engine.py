"""Tests del motor: markdown (figuras, code fences, base de imagenes), claves de
TOC, conteos de severidad y render de HTML (sin navegador)."""
import engine
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_md_figure_from_image():
    html = str(engine.md('![Epigrafe de prueba](img/x.png){width="auto"}'))
    assert '<figure class="mdfig"' in html
    assert "Epigrafe de prueba" in html
    assert "<figcaption>" in html


def test_md_code_fence_preserved():
    html = str(engine.md("```bash\nnxc smb 10.0.0.0/24\n```"))
    assert "nxc smb 10.0.0.0/24" in html
    assert "<pre>" in html


def test_md_image_base_prefix():
    engine.set_img_base("/api/projects/demo/")
    html = str(engine.md("![c](img/a.png)"))
    assert 'src="/api/projects/demo/img/a.png"' in html
    engine.set_img_base("")


def test_md_ignores_images_inside_fence():
    html = str(engine.md("```\n![no](img/x.png)\n```"))
    # dentro del bloque de codigo NO debe convertirse en figura
    assert "<figure" not in html


def test_toc_keys_section_model():
    data = {"report": {"sections": [{"key": "confidentiality"}, {"key": "findings"}]},
            "findings": [{"id": "F1"}, {"id": "F2"}]}
    keys = engine.toc_keys(data)
    assert "confidentiality" in keys and "findings" in keys
    assert "F1" in keys and "F2" in keys


def test_toc_keys_fixed_model():
    data = {"findings": [{"id": "F1", "severity": "high"}]}
    keys = engine.toc_keys(data)
    assert keys[:4] == ["conf", "contacts", "overview", "summary"]
    assert "F1" in keys


def test_severity_counts_and_summary_order():
    findings = [
        {"id": "F1", "severity": "low", "title": "a"},
        {"id": "F2", "severity": "critical", "title": "b"},
        {"id": "F3", "severity": "high", "title": "c"},
        {"id": "M1", "mode": "machine", "severity": "medium", "title": "Box"},
    ]
    counts = engine.severity_counts(findings)
    # las maquinas NO cuentan en severidad (aunque tengan 'medium')
    assert counts["critical"] == 1 and counts["low"] == 1 and counts["high"] == 1 and counts["medium"] == 0
    assert engine.machine_count(findings) == 1
    ordered = engine.summary_findings(findings)
    # vulns por severidad, la maquina al final
    assert [f["id"] for f in ordered] == ["F2", "F3", "F1", "M1"]


def test_render_html_sections_smoke():
    from pathlib import Path
    data = {
        "meta": {"lang": "es", "report_title": "T", "theme": "corporativo"},
        "report": {"sections": [{"key": "executive_summary", "summary": "Hola mundo"},
                                {"key": "findings"}]},
        "findings": [{"id": "F1", "mode": "vuln", "title": "X", "severity": "high"}],
    }
    env = engine.build_env()
    L = engine.load_lang("es")
    html = engine.render_html(env, data, Path(".").resolve(), page_map={}, pagemarks=False, L=L)
    assert "Resumen ejecutivo" in html
    assert "Hola mundo" in html
    assert "F1" in html


def test_chromium_temp_html_written_as_utf8():
    """Regresion Windows: el HTML temporal para Chromium debe escribirse en UTF-8
    (en Windows el default es cp1252 y las tildes salian como '?')."""
    src = (ROOT_DIR / "engine.py").read_text(encoding="utf-8")
    i = src.index("NamedTemporaryFile")
    call = src[i:i + 200]
    assert 'encoding="utf-8"' in call, "el HTML temporal de Chromium debe usar encoding utf-8"


def test_raw_html_in_prose_is_escaped():
    """Los payloads HTML en la prosa se muestran como TEXTO (no se ejecutan ni se
    los come el render)."""
    html = str(engine.md("PoC: <script>alert(1)</script>"))
    assert "&lt;script&gt;" in html and "<script>" not in html
    # el codigo y las imagenes no se ven afectados
    assert "<code>" in str(engine.md("usa `x`"))
    assert "mdfig" in str(engine.md("![c](img/a.png)"))
