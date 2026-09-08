#!/usr/bin/env python3
"""report-gen / engine.py  (Fase 2: informe completo desde YAML)"""

import argparse
import re
import sys
import tempfile
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from safe_markup import md, md_inline, set_img_base
from resources import restricted_fetcher
import validate as validatelib

ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "templates"
THEMES = ROOT / "themes"

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITY_ORDER)}


def load_engagement(path):
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    validatelib.require_valid(data)
    data.setdefault("meta", {})
    data.setdefault("findings", [])
    return data


def _deep_merge(base, over):
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_lang(lang):
    """Carga en.yaml como base y superpone el idioma pedido (rellena huecos)."""
    base = yaml.safe_load((ROOT / "lang" / "en.yaml").read_text(encoding="utf-8"))
    lang = lang or "en"
    if lang not in {"en", "es"}:
        raise ValueError("Idioma no soportado")
    if lang != "en":
        p = ROOT / "lang" / f"{lang}.yaml"
        if p.exists():
            _deep_merge(base, yaml.safe_load(p.read_text(encoding="utf-8")))
        else:
            print(f"[i] idioma '{lang}' sin paquete, uso en.yaml")
    return base


def number_figures(findings):
    n = 0
    for f in findings:
        steps = []
        if f.get("mode") == "vuln":
            steps = f.get("walkthrough", [])
        elif f.get("mode") == "machine":
            for phase in f.get("phases", []):
                steps.extend(phase.get("steps", []))
        for step in steps:
            fig = step.get("figure")
            if fig and fig.get("src"):
                n += 1
                fig["number"] = n
    return n


def severity_counts(findings):
    counts = {s: 0 for s in SEVERITY_ORDER}
    for f in findings:
        if f.get("mode") == "machine":  # las maquinas no llevan severidad
            continue
        s = f.get("severity")
        if s in counts:
            counts[s] += 1
    return counts


def machine_count(findings):
    return sum(1 for f in findings if f.get("mode") == "machine")


def summary_findings(findings):
    vulns = [f for f in findings if f.get("mode") != "machine" and f.get("severity") in SEVERITY_RANK]
    vulns.sort(key=lambda f: SEVERITY_RANK[f["severity"]])
    machines = [f for f in findings if f.get("mode") == "machine"]
    return vulns + machines  # vulns por severidad, luego maquinas


def appendix_rows(findings):
    rows = []
    for f in findings:
        if f.get("host") and f["host"].get("name"):
            host = f["host"]["name"]
        elif f.get("host") and f["host"].get("ip"):
            host = f["host"]["ip"]
        else:
            host = f.get("affected", "")
        for p in f.get("proof", []) or []:
            rows.append({"host": host, "item": p.get("name", ""), "value": p.get("value", ""),
                         "notes": p.get("notes", "Proof file on target")})
        for fl in f.get("flags", []) or []:
            rows.append({"host": fl.get("host", host), "item": fl.get("name", "flag"),
                         "value": fl.get("value", ""), "notes": fl.get("location") or fl.get("method", "")})
    return rows


def select_findings(findings, only):
    if not only:
        return findings
    wanted = {x.strip() for x in only.split(",") if x.strip()}
    chosen = [f for f in findings if f.get("id") in wanted]
    missing = wanted - {f.get("id") for f in chosen}
    if missing:
        sys.exit(f"[!] findings no encontrados: {', '.join(sorted(missing))}")
    return chosen


def build_env():
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                      autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
    env.filters["md"] = md
    env.filters["md_inline"] = md_inline
    return env


def render_html(env, data, engagement_dir, page_map, pagemarks, L, theme_href=None, img_base=None):
    from workflows import project_report, report_sections
    data = project_report(data)
    number_figures(data["findings"])
    meta = data["meta"]
    theme = meta.get("theme", "serio")
    if theme not in {"serio", "corporativo", "offsec", "htb"}:
        raise ValueError("Tema no soportado")
    theme_css = THEMES / f"{theme}.css"
    if not theme_css.exists():
        raise ValueError(f"tema no encontrado: {theme}")
    findings = data["findings"]
    img_base_val = img_base or (engagement_dir.as_uri() + "/")
    set_img_base(img_base_val)
    section_based = bool((data.get("report") or {}).get("sections"))
    tpl = env.get_template("sections_report.html" if section_based else "base.html")
    colors = {key: re.search(r"--sev-" + key + r":\s*(#[0-9A-Fa-f]{6})", theme_css.read_text()).group(1) for key in SEVERITY_ORDER}
    ctx = dict(workflow_sections=report_sections(data), chart_colors=colors, meta=meta, findings=findings, sum_findings=summary_findings(findings),
               sev_counts=severity_counts(findings), sev_order=SEVERITY_ORDER,
               machine_count=machine_count(findings),
               appendix=appendix_rows(findings),
               theme_css=theme_href or theme_css.as_uri(),
               engagement_dir=img_base or (engagement_dir.as_uri() + "/"), page_map=page_map,
               pagemarks=pagemarks, L=L)
    if section_based:
        import sections as _sections
        ctx["rsections"] = _sections.resolve_sections(data, L, meta.get("lang", "en"))
    result = tpl.render(**ctx)
    if img_base is None:
        from lxml import html as html_parser
        from resources import local_image
        from urllib.parse import urlsplit, unquote
        from urllib.request import url2pathname
        for image in html_parser.fromstring(result).xpath("//img[@src]"):
            source = image.get("src")
            parsed = urlsplit(source)
            if parsed.scheme == "file":
                path = Path(url2pathname(unquote(parsed.path))).resolve()
                if not path.is_relative_to(engagement_dir.resolve()):
                    raise ValueError("Imagen fuera del engagement")
                source = path.relative_to(engagement_dir.resolve()).as_posix()
            local_image(source, engagement_dir)
    return result


def render_pdf_weasyprint(html, out_pdf, base_url):
    from weasyprint import HTML
    from pdf_pagination import verify_finding_tables
    document = HTML(string=html, base_url=str(base_url), url_fetcher=restricted_fetcher(base_url, THEMES)).render()
    verify_finding_tables(document)
    document.write_pdf(str(out_pdf))


def render_pdf_chromium(html, out_pdf, meta):
    # Chromium (>=141) interpreta los margin boxes de @page del CSS, asi que la
    # cabecera/pie y el contador salen del mismo CSS que usa WeasyPrint. No se
    # inyecta header/footer template (duplicaria) ni margin (lo fija @page).
    from playwright.sync_api import sync_playwright
    from pdf_pagination import mark_finding_tables, verify_table_markers
    html, table_checks = mark_finding_tables(html)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     dir=str(out_pdf.parent), encoding="utf-8") as tf:
        tf.write(html)
        tmp = Path(tf.name)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(java_script_enabled=False)
            def restrict(route):
                from urllib.parse import urlsplit, unquote
                from urllib.request import url2pathname
                parsed = urlsplit(route.request.url)
                path = Path(url2pathname(unquote(parsed.path))).resolve() if parsed.scheme == "file" else None
                if path and (path == tmp or path.is_relative_to(ROOT / "themes") or path.is_relative_to(Path(meta["_resource_root"]))):
                    route.continue_()
                else:
                    route.abort()
            pg.route("**/*", restrict)
            pg.goto(tmp.as_uri())
            pg.emulate_media(media="print")
            if table_checks:
                proof = pg.pdf(prefer_css_page_size=True, print_background=True)
                verify_table_markers(proof, table_checks)
            pg.evaluate("document.querySelectorAll('.rg-table-boundary').forEach(node => node.remove())")
            pg.pdf(path=str(out_pdf), prefer_css_page_size=True, print_background=True)
            b.close()
    finally:
        tmp.unlink(missing_ok=True)


def resolve_backend(backend):
    if backend in ("auto", "weasyprint"):
        import contextlib
        import io
        try:
            # WeasyPrint imprime un bloque a stderr si le faltan libs de sistema;
            # lo capturamos para no ensuciar la salida.
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                import weasyprint  # noqa: F401
            return "weasyprint"
        except Exception as exc:  # ImportError, u OSError si faltan libs de sistema (GTK en Windows)
            if backend == "weasyprint":
                sys.exit(f"[!] WeasyPrint no disponible ({exc.__class__.__name__}): instala sus "
                         f"librerias de sistema (GTK) o usa --backend chromium")
            print("[i] Backend PDF: Chromium (WeasyPrint no disponible)")
            return "chromium"
    return backend


def do_render(html, out_pdf, base_url, meta, backend):
    if backend == "weasyprint":
        render_pdf_weasyprint(html, out_pdf, base_url)
    else:
        render_pdf_chromium(html, out_pdf, {**meta, "_resource_root": str(base_url)})


def read_page_map(pdf_path, keys):
    import pdfplumber
    found = {}
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            txt = page.extract_text() or ""
            norm = re.sub(r"\s+", "", txt)
            for key in keys:
                if key not in found and f"PGMK{key}PGMK" in norm:
                    found[key] = i
    return found


def toc_keys(data):
    from workflows import report_sections
    extra_keys = [s["key"] for s in report_sections(data)]
    if (data.get("report") or {}).get("sections"):
        keys = [s["key"] for s in data["report"]["sections"] if s.get("key")]
        keys += [f["id"] for f in data["findings"]]
        return keys + extra_keys
    keys = ["conf", "contacts", "overview", "summary"]
    keys += [f["id"] for f in data["findings"]]
    if appendix_rows(data["findings"]):
        keys.append("appendix")
    return keys + extra_keys


def main():
    ap = argparse.ArgumentParser(description="Generador de informes de pentest (iphobiuss)")
    ap.add_argument("engagement")
    ap.add_argument("-o", "--out")
    ap.add_argument("--only")
    ap.add_argument("--html", action="store_true")
    ap.add_argument("--backend", default="auto", choices=["auto", "weasyprint", "chromium"])
    ap.add_argument("--lang", help="idioma del informe (en, es); sobreescribe meta.lang")
    ap.add_argument("--theme", help="tema/diseno; sobreescribe meta.theme")
    args = ap.parse_args()

    yaml_path = Path(args.engagement).resolve()
    engagement_dir = yaml_path.parent
    data = load_engagement(yaml_path)
    data["findings"] = select_findings(data["findings"], args.only)
    validatelib.require_valid(data, final=True)
    number_figures(data["findings"])

    meta = data["meta"]
    if args.lang:
        meta["lang"] = args.lang
    if args.theme:
        meta["theme"] = args.theme
    L = load_lang(meta.get("lang", "en"))

    try:
        import validate as _validate
        issues = _validate.validate(data)
    except Exception as exc:  # noqa: BLE001 - visible, no silencioso
        print(f"[warning] la validacion no pudo ejecutarse: {exc}")
        issues = []
    for lvl, msg in issues:
        print(f"[{lvl}] {msg}")

    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    out_pdf = Path(args.out).resolve() if args.out else out_dir / f"{engagement_dir.name}.pdf"
    backend = resolve_backend(args.backend)
    env = build_env()
    keys = toc_keys(data)

    html1 = render_html(env, data, engagement_dir, page_map={}, pagemarks=True, L=L)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".pdf", dir=out_pdf.parent, delete=False) as tmp:
        tmp_pdf = Path(tmp.name)
    try:
        do_render(html1, tmp_pdf, engagement_dir, meta, backend)
        page_map = read_page_map(tmp_pdf, keys)
    finally:
        tmp_pdf.unlink(missing_ok=True)
    missing = [k for k in keys if k not in page_map]
    if missing:
        print(f"[i] sin pagina resuelta para: {', '.join(missing)}")

    html2 = render_html(env, data, engagement_dir, page_map=page_map, pagemarks=False, L=L)
    if args.html:
        (out_pdf.with_suffix(".html")).write_text(html2, encoding="utf-8")
        print(f"[+] HTML: {out_pdf.with_suffix('.html')}")
    do_render(html2, out_pdf, engagement_dir, meta, backend)
    print(f"[+] PDF ({backend}, {meta.get('theme','serio')}, {meta.get('lang','en')}): {out_pdf}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        sys.exit(f"[!] {exc}")
