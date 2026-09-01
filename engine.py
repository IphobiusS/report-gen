#!/usr/bin/env python3
"""report-gen / engine.py  (Fase 2: informe completo desde YAML)"""

import argparse
import re
import sys
import tempfile
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "templates"
THEMES = ROOT / "themes"

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITY_ORDER)}

MD = markdown.Markdown(extensions=["fenced_code", "tables", "sane_lists", "nl2br"], output_format="html5")

# Imagenes estilo SysReptor: ![epigrafe](src){width="auto"} -> <figure> con epigrafe.
_IMG_RE = re.compile(r'!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+)(?:\s+"[^"]*")?\)(?:\{(?P<attrs>[^}]*)\})?')


_IMG_BASE = {"v": ""}


def set_img_base(base):
    _IMG_BASE["v"] = base or ""


def _img_figure(m):
    alt = (m.group("alt") or "").strip()
    src = m.group("src")
    if src.startswith("img/"):
        src = _IMG_BASE["v"] + src
    attrs = m.group("attrs") or ""
    wm = re.search(r'width\s*=\s*"?([^"\s]+)"?', attrs)
    style = ""
    if wm and wm.group(1) not in ("auto", ""):
        style = f' style="width:{wm.group(1)}"'
    cap = f"<figcaption>{alt}</figcaption>" if alt else ""
    return f'<figure class="mdfig"><img src="{src}" alt="{alt}"{style}>{cap}</figure>'


def _esc_html_outside_code(line):
    # Escapa < y > en la prosa (fuera de inline-code) para que los payloads HTML
    # se muestren como TEXTO literal y no se interpreten/ejecuten. Los spans de
    # codigo `...` y los bloques ``` los escapa el propio Markdown.
    parts = re.split(r"(`[^`]*`)", line)
    return "".join(p if p.startswith("`") else p.replace("<", "&lt;").replace(">", "&gt;")
                   for p in parts)


def _preprocess_md(text):
    out, in_fence = [], False
    for line in str(text).split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
        else:
            # 1) escapar HTML crudo de la prosa; 2) luego expandir imagenes a <figure>
            out.append(_IMG_RE.sub(_img_figure, _esc_html_outside_code(line)))
    return "\n".join(out)


def md(text):
    if not text:
        return Markup("")
    MD.reset()
    return Markup(MD.convert(_preprocess_md(str(text))))


def md_inline(text):
    html = str(md(text)).strip()
    if html.startswith("<p>") and html.endswith("</p>") and html.count("<p>") == 1:
        html = html[3:-4]
    return Markup(html)


def load_engagement(path):
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
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
    meta = data["meta"]
    theme = meta.get("theme", "serio")
    theme_css = THEMES / f"{theme}.css"
    if not theme_css.exists():
        raise ValueError(f"tema no encontrado: {theme}")
    findings = data["findings"]
    img_base_val = img_base or (engagement_dir.as_uri() + "/")
    set_img_base(img_base_val)
    section_based = bool((data.get("report") or {}).get("sections"))
    tpl = env.get_template("sections_report.html" if section_based else "base.html")
    ctx = dict(meta=meta, findings=findings, sum_findings=summary_findings(findings),
               sev_counts=severity_counts(findings), sev_order=SEVERITY_ORDER,
               machine_count=machine_count(findings),
               appendix=appendix_rows(findings),
               theme_css=theme_href or theme_css.as_uri(),
               engagement_dir=img_base or (engagement_dir.as_uri() + "/"), page_map=page_map,
               pagemarks=pagemarks, L=L)
    if section_based:
        import sections as _sections
        ctx["rsections"] = _sections.resolve_sections(data, L, meta.get("lang", "en"))
    return tpl.render(**ctx)


def render_pdf_weasyprint(html, out_pdf, base_url):
    from weasyprint import HTML
    HTML(string=html, base_url=str(base_url)).write_pdf(str(out_pdf))


def render_pdf_chromium(html, out_pdf, meta):
    # Chromium (>=141) interpreta los margin boxes de @page del CSS, asi que la
    # cabecera/pie y el contador salen del mismo CSS que usa WeasyPrint. No se
    # inyecta header/footer template (duplicaria) ni margin (lo fija @page).
    from playwright.sync_api import sync_playwright
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     dir=str(out_pdf.parent), encoding="utf-8") as tf:
        tf.write(html)
        tmp = Path(tf.name)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            pg.goto(tmp.as_uri())
            pg.emulate_media(media="print")
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
        render_pdf_chromium(html, out_pdf, meta)


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
    if (data.get("report") or {}).get("sections"):
        keys = [s["key"] for s in data["report"]["sections"] if s.get("key")]
        keys += [f["id"] for f in data["findings"]]
        return keys
    keys = ["conf", "contacts", "overview", "summary"]
    keys += [f["id"] for f in data["findings"]]
    if appendix_rows(data["findings"]):
        keys.append("appendix")
    return keys


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
    tmp_pdf = out_dir / f".{engagement_dir.name}.pass1.pdf"
    do_render(html1, tmp_pdf, engagement_dir, meta, backend)
    page_map = read_page_map(tmp_pdf, keys)
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
    main()
