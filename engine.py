#!/usr/bin/env python3
"""report-gen / engine.py  (Fase 2: informe completo desde YAML)"""

import argparse
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from safe_markup import md, md_inline, set_img_base
from resources import restricted_fetcher
from markupsafe import Markup
import validate as validatelib
from error_messages import language_scope, message

ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "templates"
THEMES = ROOT / "themes"

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITY_ORDER)}


def load_engagement(path):
    from input_guard import load_yaml_file
    data = load_yaml_file(path)
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


def report_language(data):
    """Resolve legacy absent/nullable language without modifying source metadata.

    English is the renderer's historical fallback. The wizard continues to
    select Spanish explicitly for new projects.
    """
    return (data.get("meta") or {}).get("lang") or "en"


def report_title(data):
    """Accessible presentation fallback; the missing source title stays missing."""
    title = (data.get("meta") or {}).get("report_title")
    if title is not None and str(title).strip():
        return title
    return "Informe sin título" if report_language(data) == "es" else "Untitled report"


def load_lang(lang):
    """Carga en.yaml como base y superpone el idioma pedido (rellena huecos)."""
    base = yaml.safe_load((ROOT / "lang" / "en.yaml").read_text(encoding="utf-8"))
    lang = lang or "en"
    if lang not in {"en", "es"}:
        raise ValueError(message("Idioma no soportado"))
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
        if f.get("mode", "vuln") == "vuln":
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
    # Classification and technical verification are independent. A finding
    # without a severity remains a finding and must not disappear at export.
    vulns = [f for f in findings if f.get("mode") != "machine"]
    vulns.sort(key=lambda f: SEVERITY_RANK.get(f.get("severity"), len(SEVERITY_ORDER)))
    machines = [f for f in findings if f.get("mode") == "machine"]
    return vulns + machines


def unclassified_count(findings):
    return sum(f.get("mode") != "machine" and f.get("severity") not in SEVERITY_RANK
               for f in findings)


def summary_text(findings, L):
    """Same totals and pending classification wording in every public format."""
    words = L["summary"]
    counts = severity_counts(findings)
    pending = unclassified_count(findings)
    total = sum(counts.values()) + pending
    noun = words["finding"] if total == 1 else words["findings"]
    text = f"{words['identified']} {total} {noun}"
    parts = [f"{counts[s]} {L['severity'][s].lower()}" for s in SEVERITY_ORDER if counts[s]]
    if pending:
        parts.append(words["pending_one" if pending == 1 else "pending_many"].replace("{n}", str(pending)))
    if parts:
        rating_label = words.get("rating_pending", words["rating"]) if pending else words["rating"]
        text += f" {rating_label} " + ", ".join(parts)
    machines = machine_count(findings)
    if machines:
        text += " " + words["and_machines_one" if machines == 1 else "and_machines_many"].replace("{n}", str(machines))
    return text + "."


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
                      autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True,
                      finalize=lambda value: "" if value is None else value)
    env.filters["md"] = md
    env.filters["md_inline"] = md_inline
    env.filters["css_string"] = css_string
    # IDs are literal author data; only their URL-fragment representation is
    # encoded. User-authored links pass through the Markdown boundary unchanged.
    env.filters["fragment"] = lambda value: quote(str(value), safe="")
    return env


def css_string(value):
    """Quote text for CSS content without HTML entities or style termination."""
    return Markup('"' + ''.join(
        f'\\{ord(char):x} ' if char in '\\"<>\n\r\f' or ord(char) < 32 else char
        for char in str(value or '')
    ) + '"')


def _tall_figure_image(path):
    """Optional layout hint from bounded local metadata, never decoded pixels.

    The upload boundary permits 12 MiB/25 MP. Larger files can still reach the
    existing export validation, but this hint does not read or decode them.
    Near-square evidence needs the same readable box as portrait evidence.
    """
    from io import BytesIO
    from PIL import Image
    limit = 12 * 1024 * 1024
    try:
        if path.stat().st_size > limit:
            return False
        with path.open('rb') as source:
            blob = source.read(limit + 1)
        if len(blob) > limit:
            return False
        with Image.open(BytesIO(blob)) as picture:
            width, height = picture.size
            if width * height > 25_000_000:
                return False
            # PNG's override calls load() to discover late EXIF chunks. Use
            # only metadata already read by the container header, including
            # JPEG orientation, without invoking a pixel decoder here.
            if Image.Image.getexif(picture).get(274) in (5, 6, 7, 8):
                width, height = height, width
    except (OSError, ValueError, Image.DecompressionBombError):
        return False
    return height * 4 >= width * 3


def render_html(env, data, engagement_dir, page_map, pagemarks, L, theme_href=None, img_base=None,
                machine_graphs=False):
    from workflows import project_report, report_sections
    documented_phase_counts = [len(f.get('phases', [])) for f in data.get('findings', [])]
    data = project_report(data)
    number_figures(data["findings"])
    meta = data["meta"]
    theme = meta.get("theme", "serio")
    from report_designs import THEMES as SUPPORTED_THEMES
    if theme not in SUPPORTED_THEMES:
        raise ValueError(message("Tema no soportado"))
    theme_css = THEMES / f"{theme}.css"
    if not theme_css.exists():
        raise ValueError(message("tema no encontrado: {p0}", p0=theme))
    findings = data["findings"]
    img_base_val = img_base or (engagement_dir.as_uri() + "/")
    set_img_base(img_base_val)
    section_based = bool((data.get("report") or {}).get("sections"))
    tpl = env.get_template("sections_report.html" if section_based else "base.html")
    colors = {key: re.search(r"--sev-" + key + r":\s*(#[0-9A-Fa-f]{6})", theme_css.read_text()).group(1) for key in SEVERITY_ORDER}
    ctx = dict(workflow_sections=report_sections(data), chart_colors=colors, meta=meta, findings=findings, sum_findings=summary_findings(findings),
               sev_counts=severity_counts(findings), sev_order=SEVERITY_ORDER,
               summary_text=summary_text(findings, L), unclassified_count=unclassified_count(findings),
               machine_count=machine_count(findings),
               appendix=appendix_rows(findings),
               theme_css=theme_href or theme_css.as_uri(),
               engagement_dir=img_base or (engagement_dir.as_uri() + "/"), page_map=page_map,
               pagemarks=pagemarks, L=L)
    ctx['machine_graphs'] = []
    if machine_graphs:
        from exporters.machine_graph import build
        ctx['machine_graphs'] = [build(f, count, meta['lang']) if f.get('mode') == 'machine' else None
                                 for f, count in zip(findings, documented_phase_counts)]
        ctx['machine_graph_css'] = (THEMES / '_machine_graph.css').read_text(encoding='utf-8')
    if section_based:
        import sections as _sections
        ctx["rsections"] = _sections.resolve_sections(data, L, meta.get("lang", "en"))
    ctx["finding_links"] = not section_based or any(
        section.get("special") == "findings" for section in ctx.get("rsections", []))
    import design_render
    if meta.get("design"):
        ctx['profile_css'] = design_render.css(meta['design'])
        from provider_branding import provider_mark
        ctx['provider_mark'] = provider_mark(meta['design'])
    from report_layout import prepare_html
    result = prepare_html(tpl.render(**ctx))
    from lxml import html as html_parser
    from resources import local_image
    from urllib.parse import urlsplit, quote
    from urllib.request import url2pathname
    tree = html_parser.document_fromstring(result)
    layout_changed = False
    image_layouts = {}
    for image in tree.xpath("//img[@src]"):
        source = image.get("src")
        if img_base is None:
            parsed = urlsplit(source)
            if parsed.scheme == "file":
                path = Path(url2pathname(parsed.path)).resolve()
                if not path.is_relative_to(engagement_dir.resolve()):
                    raise ValueError(message("Imagen fuera del engagement"))
                source = quote(path.relative_to(engagement_dir.resolve()).as_posix(), safe='/')
            path = local_image(source, engagement_dir)
        else:
            # Preview URLs refer back to project files, never to a network
            # resource. Preserve missing-image preview behavior; export still
            # follows the strict local validation above.
            if not source.startswith(img_base_val):
                continue
            try:
                path = local_image(source[len(img_base_val):], engagement_dir)
            except ValueError:
                continue
        figure = image.getparent()
        if figure.tag != "figure":
            continue
        if path not in image_layouts:
            image_layouts[path] = _tall_figure_image(path)
        if image_layouts[path]:
            classes = figure.get('class', '').split()
            if 'rg-tall' not in classes:
                figure.set('class', ' '.join([*classes, 'rg-tall']))
                layout_changed = True
    if layout_changed:
        result = html_parser.tostring(tree, encoding='unicode', method='html', doctype='<!DOCTYPE html>')
    return result


def _pdf_code_layout(source):
    """Apply transient PDF layout without altering authored text.

    Keep code lines together, let literal URIs fill the available width, and
    reserve room for long list counters. Other exports and source markup
    retain their original representation.
    """
    from lxml import html
    uri = re.compile(r'\b(?:https?|ftps?)://[^\s<>"\'`]+', re.IGNORECASE)

    def url_breaks(element, text):
        # WeasyPrint still prefers a slash/hyphen before an overlong URI
        # segment even with word-break:break-all. Optional HTML break points
        # fill the available line without adding source text or hard breaks.
        # Keep every non-ASCII run intact, including combining marks and ZWJ
        # sequences; its native shaping/overflow handling remains in charge.
        cursor = 0
        tail = None

        def append(value):
            if tail is None:
                element.text = (element.text or '') + value
            else:
                tail.tail = (tail.tail or '') + value

        for match in uri.finditer(text):
            append(text[cursor:match.start()])
            token = match.group()
            start = 0
            for index in range(len(token) - 1):
                if '\x21' <= token[index] <= '\x7e' and '\x21' <= token[index + 1] <= '\x7e':
                    append(token[start:index + 1])
                    tail = html.Element('wbr', {'data-rg-pdf-uri-break': 'true'})
                    element.append(tail)
                    start = index + 1
            append(token[start:])
            cursor = match.end()
        append(text[cursor:])

    tree = html.document_fromstring(source)
    changed = False
    from safe_markup import ordered_list_start
    for ordered in tree.xpath('//ol'):
        start = ordered_list_start(ordered)
        count = sum(child.tag == 'li' for child in ordered)
        digits = len(str(start + max(0, count - 1)))
        if digits >= 5:
            # The default 40px list inset fits short counters, but ten-digit
            # markers intrude into the printed margin. Size only long-counter
            # lists in their own font's zero-width units, allowing punctuation
            # and a gutter. Retain the parser's exact counter-reset and text.
            ordered.set('style', ordered.get('style', '') + f';padding-left:{digits + 3}ch')
            changed = True
    for pre in tree.xpath('//pre'):
        content = pre
        if len(pre):
            if len(pre) != 1 or pre[0].tag != 'code' or len(pre[0]):
                continue
            content = pre[0]
        text = content.text or ''
        content.text = None
        parts = text.split('\n')
        for index, line in enumerate(parts):
            if index == len(parts) - 1 and not line:
                continue  # Preserve the preceding terminal LF without a new box.
            span = html.Element('span', {
                'class': 'rg-pdf-code-line',
                'style': 'display:inline-block;width:100%;vertical-align:top;'
                         'break-inside:avoid;page-break-inside:avoid'})
            url_breaks(span, line)
            span.tail = '\n' if index < len(parts) - 1 else ''
            content.append(span)
        pre.set('style', pre.get('style', '') +
                ';break-inside:auto;page-break-inside:auto;orphans:4;widows:4')
        changed = True

    for element in tree.xpath('//h1 | //h2 | //h3 | //h4 | //h5 | //h6 | '
                              '//code[not(ancestor::pre)] | //a[not(ancestor::pre)] | '
                              '//ul[contains(concat(" ", normalize-space(@class), " "), " refs ")]/li'):
        if len(element):
            continue  # Nested inline code is handled separately; retain markup.
        text = element.text or ''
        if not uri.search(text):
            continue
        if element.tag not in {'code', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'} and not uri.fullmatch(text.strip()):
            continue  # A human-readable label is prose, not a literal URI.
        if element.tag == 'code':
            # WeasyPrint does not reserve inline decoration when splitting
            # these fragments: the border can overflow and push a preceding
            # label onto its own line. Preserve the mono face/background, but
            # omit the decorative inset only for PDF code containing a URI.
            element.set('style', element.get('style', '') + ';padding:0;border:0')
        element.text = None
        url_breaks(element, text)
        changed = True
    return html.tostring(tree, encoding='unicode', method='html') if changed else source


def _verify_pdf_code_lines(document):
    """Reject an indivisible line taller than the available printed page."""
    for page in document.pages:
        root = page._page_box
        bottom = root.content_box_y() + root.height

        def walk(box):
            node = getattr(box, 'element', None)
            if (type(box).__name__ == 'InlineBlockBox' and node is not None
                    and 'rg-pdf-code-line' in node.get('class', '').split()
                    and (box.height > root.height + 2 or box.position_y + box.height > bottom + 2)):
                raise ValueError(message(
                    'PDF no generado: una línea de código es más alta que la página imprimible. '
                    'Divide esa línea explícitamente y vuelve a exportar. La salida anterior se conserva.',
                    en='PDF not generated: one code line is taller than the printable page. '
                       'Split that line explicitly and export again. The previous output is preserved.'))
            for child in box.all_children():
                walk(child)

        walk(root)


def render_pdf_weasyprint(html, out_pdf, base_url):
    from weasyprint import HTML
    from pdf_pagination import compact_pdf_uri_breaks, keep_short_labelled_lists, relax_oversized_rows, verify_finding_tables, prune_pdf_uri_break_links
    renderer = HTML(string=compact_pdf_uri_breaks(_pdf_code_layout(keep_short_labelled_lists(html))), base_url=str(base_url), url_fetcher=restricted_fetcher(base_url, THEMES))
    document = renderer.render()
    verify_finding_tables(document)
    if relax_oversized_rows(document):
        document = renderer.render()
        verify_finding_tables(document)
    _verify_pdf_code_lines(document)
    # WeasyPrint records unsupported code points while drawing the PDF, not
    # during layout. A ToUnicode map may preserve their text even though the
    # visible glyph is .notdef. Inspect the actual selected fonts after drawing
    # and before touching the destination; textual extraction cannot prove
    # that these characters were rendered.
    prune_pdf_uri_break_links(document)
    payload = document.write_pdf()
    missing = sorted({codepoint for font in document.fonts.values() for codepoint in font.missing})
    if missing:
        codes = ', '.join(f'U+{codepoint:04X}' for codepoint in missing[:16])
        if len(missing) > 16:
            codes += f' (+{len(missing) - 16})'
        raise ValueError(message(
            'PDF no generado: faltan glifos en las fuentes disponibles ({codes}). '
            'Instala una fuente compatible y vuelve a exportar; revisa visualmente el PDF. '
            'La salida anterior se conserva.',
            en='PDF not generated: available fonts lack glyphs ({codes}). '
               'Install a compatible font and export again; visually review the PDF. '
               'The previous output is preserved.', codes=codes))
    # Detect ambiguous extraction (notably RTL plus a wrapped hyphen) before
    # replacing a prior export, using only the just-rendered PDF bytes.
    from export_contract import pdf_text_pages
    pdf_text_pages(payload)
    Path(out_pdf).write_bytes(payload)


def render_pdf_chromium(html, out_pdf, meta):
    # Chromium (>=141) interpreta los margin boxes de @page del CSS, asi que la
    # cabecera/pie y el contador salen del mismo CSS que usa WeasyPrint. No se
    # inyecta header/footer template (duplicaria) ni margin (lo fija @page).
    from playwright.sync_api import sync_playwright
    from pdf_pagination import keep_short_labelled_lists, mark_finding_tables, verify_table_markers
    html, table_checks = mark_finding_tables(keep_short_labelled_lists(html))
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     dir=str(out_pdf.parent), encoding="utf-8") as tf:
        tf.write(html)
        tmp = Path(tf.name)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(java_script_enabled=False)
            def restrict(route):
                from urllib.parse import urlsplit
                from urllib.request import url2pathname
                parsed = urlsplit(route.request.url)
                path = Path(url2pathname(parsed.path)).resolve() if parsed.scheme == "file" else None
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
                sys.exit(message(
                    "[!] WeasyPrint no disponible ({error}): instala sus librerias de sistema (GTK) o usa --backend chromium",
                    en="[!] WeasyPrint unavailable ({error}): install its system libraries (GTK) or use --backend chromium",
                    error=exc.__class__.__name__))
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
                if key not in found and f"PGMK{quote(str(key), safe='')}PGMK" in norm:
                    found[key] = i
    return found


def toc_keys(data):
    from workflows import report_sections
    if (data.get("report") or {}).get("sections"):
        from sections import resolve_sections
        resolved = resolve_sections(data, None, report_language(data))
        keys = [s["key"] for s in resolved]
        if any(s.get('special') == 'findings' for s in resolved):
            keys += [f["id"] for f in data["findings"]]
        return keys
    # Use the emitted HTML destinations rather than legacy short aliases:
    # a documentary finding called 'conf' must not share the confidentiality
    # block's page marker ('sec-conf').
    keys = ["sec-conf", "sec-contacts", "sec-overview", "sec-summary"]
    keys += [f["id"] for f in data["findings"]]
    if appendix_rows(data["findings"]):
        keys.append("sec-appendix")
    return keys + [s["key"] for s in report_sections(data)]


def main():
    ap = argparse.ArgumentParser(description="Generador de informes de pentest (iphobiuss)")
    ap.add_argument("engagement")
    ap.add_argument("-o", "--out")
    ap.add_argument("--only")
    ap.add_argument("--html", action="store_true")
    ap.add_argument("--backend", default="auto", choices=["auto", "weasyprint", "chromium"])
    ap.add_argument("--lang", help="idioma del informe (en, es); sobreescribe meta.lang")
    ap.add_argument("--theme", help="tema/diseno; sobreescribe meta.theme")
    ap.add_argument("--error-language", default="es", choices=["es", "en"],
                    help="idioma de los errores; no cambia el idioma del informe")
    args = ap.parse_args()
    with language_scope(args.error_language):
        return _run(args)


def _run(args):
    yaml_path = Path(args.engagement).resolve()
    engagement_dir = yaml_path.parent
    data = load_engagement(yaml_path)
    source_inputs = data.copy()
    out_dir = ROOT / "out"
    out_pdf = Path(args.out).resolve() if args.out else out_dir / f"{engagement_dir.name}.pdf"
    data["findings"] = select_findings(data["findings"], args.only)
    meta = data["meta"]
    if args.lang:
        meta["lang"] = args.lang
    if args.theme:
        meta["theme"] = args.theme
    issues = validatelib.require_valid(data, final=True)
    from storage import require_export_destination
    out_pdf = require_export_destination(yaml_path, out_pdf, source_inputs)
    if args.html:
        require_export_destination(yaml_path, out_pdf.with_suffix(".html"), source_inputs)
    number_figures(data["findings"])
    L = load_lang(report_language(data))

    for lvl, msg in issues:
        print(f"[{lvl}] {msg}")

    backend = resolve_backend(args.backend)
    env = build_env()
    keys = toc_keys(data)

    html1 = render_html(env, data, engagement_dir, page_map={}, pagemarks=True, L=L, machine_graphs=True)
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

    html2 = render_html(env, data, engagement_dir, page_map=page_map, pagemarks=False, L=L, machine_graphs=True)
    if args.html:
        (out_pdf.with_suffix(".html")).write_text(html2, encoding="utf-8")
        print(f"[+] HTML: {out_pdf.with_suffix('.html')}")
    from storage import atomic_output
    with atomic_output(out_pdf) as output:
        do_render(html2, output, engagement_dir, meta, backend)
    print(f"[+] PDF ({backend}, {meta.get('theme','serio')}, {meta.get('lang','en')}): {out_pdf}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        sys.exit(f"[!] {exc}")
