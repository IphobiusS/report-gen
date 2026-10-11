"""Editable DOCX using native Word styles and the report theme's palette."""
import re
from pathlib import Path

import engine

from .common import sev_label, cvss_label, summary_sev
from .images import word_image, fit_width


def _palette(meta, for_word=False):
    theme = meta.get("theme", "serio")
    css = (engine.THEMES / f"{theme}.css").read_text(encoding="utf-8")
    common = (engine.THEMES / "_common.css").read_text(encoding="utf-8")
    css = css.replace('@import "_common.css";', common)
    varmap = {}
    for block in re.findall(r":root\s*{([^}]*)}", css):
        for m in re.finditer(r"--([\w-]+)\s*:\s*([^;]+);", block):
            varmap["--" + m.group(1)] = m.group(2).strip()
    # Word page backgrounds are viewer/print dependent. Keep the dark cover,
    # but use an explicit readable paper palette for its editable body.
    if for_word and theme == "htb":
        varmap.update({"--ink": "#172333", "--ink-soft": "#334155", "--muted": "#536273",
                       "--panel": "#eef3f0", "--rule": "#cdd7d2", "--accent-ink": "#276515",
                       "--code-inline-bg": "#eef3f0", "--code-inline-fg": "#276515"})
    accent = (meta.get("branding") or {}).get("accent")
    if accent:
        varmap["--accent"] = accent

    if meta.get("design"):
        from design_render import palette
        varmap.update(palette(meta["design"]))

    def resolve(val, seen=()):
        def repl(m):
            n = m.group(1)
            if n in varmap and n not in seen:
                return resolve(varmap[n], seen + (n,))
            return (m.group(2).strip() if m.group(2) else "")
        return re.sub(r"var\((--[\w-]+)(?:,([^)]*))?\)", repl, val)

    res = {k: resolve(v).strip() for k, v in varmap.items()}

    def hx(name, default):
        v = res.get("--" + name, default).strip().lstrip("#")
        return v if len(v) == 6 and all(c in "0123456789abcdefABCDEF" for c in v) else default.lstrip("#")
    return hx


def _sev_chart_png(counts, hx, out, L):
    from PIL import Image, ImageDraw, ImageFont
    order = engine.SEVERITY_ORDER
    colmap = {s: hx("sev-" + s, "888888") for s in order}
    W, H = 900, 300
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    # The Pillow default face lacks some Spanish glyphs. Bundle the chart font
    # so both the language and its accents are reproducible without OS fonts.
    font = ImageFont.truetype(str(Path(__file__).parent / 'fonts' / 'DejaVuSans.ttf'), size=24)
    maxc = max([counts[s] for s in order] + [1])
    bw, gap, x0, base, top = 90, 80, 60, 250, 40
    for i, s in enumerate(order):
        x = x0 + i * (bw + gap)
        h = int((base - top) * counts[s] / maxc)
        y = base - h
        rgb = tuple(int(colmap[s][j:j+2], 16) for j in (0, 2, 4))
        if counts[s] > 0:
            d.rectangle([x, y, x + bw, base], fill=rgb)
            d.text((x + bw/2, y - 8), str(counts[s]), font=font, anchor='mb', fill=(20, 20, 30))
        else:
            d.line([x, base, x + bw, base], fill=(200, 200, 210), width=3)
        d.text((x + bw/2, base + 8), sev_label(L, s), font=font, anchor='mt', fill=(90, 90, 110))
    d.line([40, base, W - 20, base], fill=(210, 210, 220), width=2)
    im.save(out)


def to_docx(data, meta, L, engagement_dir, out_path):
    """DOCX con el diseno del tema (python-docx puro, sin dependencias externas).
    Portada, cabecera/pie con numero de pagina, cajas de finding, chips de
    severidad, bloques de codigo, grafico de severidades e imagenes."""
    import tempfile
    from workflows import project_report, report_sections
    data = project_report(data)
    meta = data["meta"]
    engine.number_figures(data["findings"])
    from docx import Document
    from docx.shared import Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
    from docx.enum.section import WD_SECTION
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    from .pagination import keep_table_together
    from report_layout import table_layout, WORKFLOW_COLUMNS

    lab = L["labels"]
    hx = _palette(meta, for_word=True)
    C = lambda name, d: RGBColor.from_string(hx(name, d))
    INK = C("ink", "0b0a1a"); INK_S = C("ink-soft", "2a2940"); MUTED = C("muted", "5f5e75")
    RULE = hx("rule", "d9d8e3"); PANEL = hx("panel", "f3f2f8")
    ACC = C("accent-ink", "1d8a12"); ACC_HEX = hx("accent", "39ff14")
    CODE_BG = hx("code-bg", "0b0a1a")
    SEV = {s: hx("sev-" + s, "888888") for s in engine.SEVERITY_ORDER}
    MONO = "DejaVu Sans Mono"
    doc = Document()
    # Use only the already prepared report metadata. In audience deliveries
    # this is the filtered copy, never the original private project metadata.
    # Core text properties are limited to 255 characters by python-docx.
    properties = doc.core_properties
    properties.title = str(meta.get("report_title") or "")[:255]
    properties.author = str(meta.get("assessor") or "")[:255]
    properties.language = str(meta.get("lang") or "")[:255]
    properties.last_modified_by = ""
    properties.comments = ""
    # The bundled Word template carries 2013 timestamps. Omit these unknown
    # dates rather than presenting template or assessment dates as creation.
    for date_key in ("dcterms:created", "dcterms:modified"):
        inherited_date = properties._element.find(qn(date_key))
        if inherited_date is not None:
            properties._element.remove(inherited_date)
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    theme = meta.get('theme', 'serio')
    if meta.get("report_density") == "compact":
        doc.styles["Normal"].paragraph_format.space_after = Pt(4)
        doc.styles["Normal"].paragraph_format.line_spacing = 1.05
    # The default Word Header/Footer styles carry central tab stops. Without
    # clearing them, the intended right-aligned metadata stops at mid-page.
    for style in ('Header', 'Footer'):
        doc.styles[style].paragraph_format.tab_stops.clear_all()
    # Built-in Word styles otherwise inherit its pale blue default theme.
    doc.styles["Caption"].font.color.rgb = MUTED
    for level in range(1, 5):
        doc.styles[f"Heading {level}"].font.color.rgb = INK_S

    def shd(el, fill):
        pr = el.get_or_add_tcPr() if el.tag.endswith("}tc") else el.get_or_add_pPr()
        s = OxmlElement("w:shd"); s.set(qn("w:val"), "clear"); s.set(qn("w:fill"), fill); pr.append(s)

    def cell_bg(cell, fill): shd(cell._tc, fill)
    def par_bg(p, fill): shd(p._p, fill)

    def par_border(p, color, edges=("bottom",), sz=6, space=2):
        pPr = p._p.get_or_add_pPr()
        bdr = OxmlElement("w:pBdr")
        for e in edges:
            b = OxmlElement("w:" + e)
            b.set(qn("w:val"), "single"); b.set(qn("w:sz"), str(sz))
            b.set(qn("w:space"), str(space)); b.set(qn("w:color"), color)
            bdr.append(b)
        pPr.append(bdr)

    def run_shade(run, fill):
        s = OxmlElement("w:shd"); s.set(qn("w:val"), "clear"); s.set(qn("w:fill"), fill)
        run._r.get_or_add_rPr().append(s)

    def cell_border(cell, spec):
        tcPr = cell._tc.get_or_add_tcPr()
        tb = tcPr.find(qn("w:tcBorders"))
        if tb is None:
            tb = OxmlElement("w:tcBorders"); tcPr.append(tb)
        for edge, (color, sz) in spec.items():
            e = OxmlElement("w:" + edge)
            e.set(qn("w:val"), "single"); e.set(qn("w:sz"), str(sz)); e.set(qn("w:space"), "0"); e.set(qn("w:color"), color)
            tb.append(e)

    def run_border(run, color, sz=4, space=3):
        b = OxmlElement("w:bdr")
        b.set(qn("w:val"), "single"); b.set(qn("w:sz"), str(sz)); b.set(qn("w:space"), str(space)); b.set(qn("w:color"), color)
        run._r.get_or_add_rPr().append(b)

    def field(p, instr):
        r = p.add_run()
        b = OxmlElement("w:fldChar"); b.set(qn("w:fldCharType"), "begin")
        t = OxmlElement("w:instrText"); t.set(qn("xml:space"), "preserve"); t.text = instr
        e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), "end")
        r._r.append(b); r._r.append(t); r._r.append(e)

    def add_plain(p, text):
        # Structured cells are plain text, as in the PDF. Markdown belongs only
        # to the explicitly Markdown fields handled by write_markdown.
        if text is not None and str(text): p.add_run(str(text))

    def add_markdown(text, keep_tables=True, retest=False, workflow_key=None):
        from .richtext import write_markdown
        columns = WORKFLOW_COLUMNS.get(workflow_key)
        write_markdown(doc, text, engagement_dir, code_block, keep_tables=keep_tables,
                       retest=retest, column_weights=columns)

    def code_block(text):
        from docx.enum.style import WD_STYLE_TYPE
        if "ReportGenCode" not in doc.styles:
            doc.styles.add_style("ReportGenCode", WD_STYLE_TYPE.PARAGRAPH).base_style = doc.styles["Normal"]
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        p = doc.add_paragraph(style="ReportGenCode"); par_bg(p, CODE_BG); par_border(p, ACC_HEX, ("left",), sz=18, space=4)
        p.paragraph_format.keep_together = True
        p.paragraph_format.keep_with_next = False
        p.paragraph_format.left_indent = Cm(0.2); p.paragraph_format.space_before = Pt(3); p.paragraph_format.space_after = Pt(3)
        lines = text.split("\n")
        for i, ln in enumerate(lines):
            if i:
                p.add_run().add_break()
            r = p.add_run(ln); r.font.name = MONO; r.font.size = Pt(9); r.font.color.rgb = RGBColor.from_string("E9E9F2")
        return p

    sec_no = [0]
    navigation = []

    def heading(text, level=1, sev=None, toc=False, anchor=None):
        p = doc.add_heading("", level=level)
        for r in list(p.runs):
            r.text = ""
        if level == 1:
            sec_no[0] += 1
            n = p.add_run(str(sec_no[0]) + "  "); n.font.color.rgb = ACC; n.bold = True
        t = p.add_run(text); t.font.color.rgb = INK if level == 1 else INK_S
        t.bold = True
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.keep_together = True
        if level == 1:
            t.font.size = Pt(17 if theme=='ejecutivo' else 15)
            if theme!='ejecutivo': par_border(p, hx("ink", "0b0a1a"), ("bottom",), sz=12)
        elif level == 2:
            t.font.size = Pt(12.5)
        else:
            t.font.size = Pt(10.5); t.font.color.rgb = INK_S
        if level == 1 or toc:
            navigation.append((p, p.text, 1 if level == 1 else 2))
        if sev:
            # Keep the entire shaded label together when a long title wraps.
            # Ordinary spaces inside the shaded run can be left on the old
            # line as an empty colored box, especially in LibreOffice.
            p.add_run(" ")
            label = sev_label(L, sev).replace(" ", "\u00a0")
            sp = p.add_run("\u00a0" + label + "\u00a0"); sp.bold = True
            sp.font.color.rgb = C("sev-chip-ink", "FFFFFF"); run_shade(sp, SEV.get(sev, "888888"))
        if anchor:
            from .navigation import add_reference
            add_reference(p, anchor)
        return p

    def kv_table(rows, keep_next=False):
        if keep_next:
            # Word/LibreOffice do not consistently chain keepNext across a
            # table boundary. Paragraph metadata keep the complete introduction
            # with the first prose line without forcing a new page per finding.
            from docx.enum.style import WD_STYLE_TYPE
            if 'ReportGenMeta' not in doc.styles:
                style=doc.styles.add_style('ReportGenMeta', WD_STYLE_TYPE.PARAGRAPH)
                style.base_style=doc.styles['Normal']
            for key,value in rows:
                p=doc.add_paragraph(style='ReportGenMeta')
                p.paragraph_format.keep_with_next=True
                p.paragraph_format.keep_together=True
                p.paragraph_format.space_after=Pt(4)
                p.paragraph_format.left_indent=Cm(4.6)
                p.paragraph_format.first_line_indent=Cm(-4.6)
                p.paragraph_format.tab_stops.add_tab_stop(Cm(4.6))
                par_bg(p,PANEL)
                r=p.add_run(key);r.font.size=Pt(8.5);r.font.color.rgb=MUTED;r.font.name=MONO
                p.add_run('\t');add_plain(p,value)
            return
        t = doc.add_table(rows=0, cols=2); t.autofit = False
        t.columns[0].width = Cm(4.6); t.columns[1].width = Cm(12.4)
        for k, v in rows:
            cells = t.add_row().cells
            cells[0].width = Cm(4.6); cells[1].width = Cm(12.4)
            cell_bg(cells[0], PANEL)
            rk = cells[0].paragraphs[0].add_run(k); rk.font.size = Pt(8.5); rk.font.color.rgb = MUTED; rk.font.name = MONO
            add_plain(cells[1].paragraphs[0], v)
        keep_table_together(t)
        if keep_next and t.rows:
            for cell in t.rows[-1].cells:
                for p in cell.paragraphs: p.paragraph_format.keep_with_next = True
        spacer = doc.add_paragraph()
        spacer.paragraph_format.space_after = Pt(2)
        spacer.paragraph_format.keep_with_next = keep_next
        return t

    def data_table(headers, rows, weights=None):
        t = doc.add_table(rows=1, cols=len(headers)); t.style = "Table Grid"; t.autofit = False
        available = sec1.page_width - sec1.left_margin - sec1.right_margin
        shares, _ = table_layout([headers] + rows, weights)
        widths = [int(available * share / 100) for share in shares]
        for col, width in zip(t.columns, widths): col.width = width
        for i, hd in enumerate(headers):
            c = t.rows[0].cells[i]; cell_bg(c, PANEL)
            c.width = widths[i]
            r = c.paragraphs[0].add_run(hd); r.bold = True; r.font.size = Pt(8.5); r.font.color.rgb = MUTED; r.font.name = MONO
        for row in rows:
            cs = t.add_row().cells
            for i, val in enumerate(row):
                cs[i].width = widths[i]
                add_plain(cs[i].paragraphs[0], val)
        repeat = OxmlElement('w:tblHeader'); t.rows[0]._tr.get_or_add_trPr().append(repeat)
        # A long inventory/summary cannot fit on a page. Linking every row
        # pushes it past preceding content before Word eventually splits it.
        # Keep short tables whole; long tables repeat their header and protect
        # individual rows while flowing into the available space.
        keep_table_together(t, whole=len(t.rows) <= 24)
        doc.add_paragraph()
        return t

    def figure(step):
        fig = step.get("figure")
        if not fig or not fig.get("src"):
            return
        img, size = word_image(fig["src"], engagement_dir)
        doc.add_picture(img, width=fit_width(doc, size, Cm(15), Cm(2)))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.paragraphs[-1].paragraph_format.keep_with_next = True
        doc.inline_shapes[-1]._inline.docPr.set("descr", (fig.get("caption") or ""))
        cap = doc.add_paragraph()
        rc = cap.add_run(f"{L['figure']} {fig.get('number','')}. "); rc.bold = True; rc.italic = True; rc.font.size = Pt(9); rc.font.color.rgb = INK_S
        rr = cap.add_run((fig.get("caption") or "")); rr.italic = True; rr.font.size = Pt(9); rr.font.color.rgb = MUTED

    def step(s):
        if s.get("lead"):
            p = doc.add_paragraph()
            p.paragraph_format.keep_with_next = True
            rb = p.add_run(s["lead"] + " "); rb.bold = True
        if s.get("text_md"):
            add_markdown(s["text_md"])
        if s.get("command"):
            code_block(s["command"])
        figure(s)

    # Independent cover rows avoid fragile stacks of blank paragraphs.
    from .cover import add_cover
    add_cover(doc, meta, lab, engagement_dir, hx)
    from .navigation import add_reference
    add_reference(doc.tables[0].cell(0, 0).paragraphs[0], '')
    br = meta.get("branding") or {}

    # ---------- Cuerpo (seccion 1, con cabecera/pie) ----------
    doc.add_section(WD_SECTION.NEW_PAGE)
    boundary = doc.paragraphs[-1]
    boundary.paragraph_format.space_before = Pt(0)
    boundary.paragraph_format.space_after = Pt(0)
    boundary.paragraph_format.line_spacing = Pt(1)
    boundary.add_run("").font.size = Pt(1)
    sec1 = doc.sections[-1]
    sec1.page_width = Cm(21); sec1.page_height = Cm(29.7)
    sec1.left_margin = sec1.right_margin = Cm(1.8); sec1.top_margin = Cm(1.6); sec1.bottom_margin = Cm(1.6)
    conf = str(br.get("confidential_text") if br.get("confidential_text") is not None else "CONFIDENTIAL")
    rhright = "  |  ".join(str(value) for value in (conf, "v" + str(meta["version"]) if meta.get("version") else "", meta.get("date")) if value)
    sec1.header.is_linked_to_previous = False
    hp = sec1.header.paragraphs[0]; hp.paragraph_format.tab_stops.add_tab_stop(Cm(17.4), WD_TAB_ALIGNMENT.RIGHT)
    r = hp.add_run(str(br.get("wordmark") if br.get("wordmark") is not None else "iphobiuss")); r.bold = True; r.font.color.rgb = ACC; r.font.size = Pt(8); r.font.name = MONO
    r = hp.add_run("\t" + rhright); r.font.size = Pt(7.5); r.font.color.rgb = MUTED; r.font.name = MONO
    par_border(hp, RULE, ("bottom",), sz=4)
    sec1.footer.is_linked_to_previous = False
    fp = sec1.footer.paragraphs[0]; fp.paragraph_format.tab_stops.add_tab_stop(Cm(17.4), WD_TAB_ALIGNMENT.RIGHT)
    r = fp.add_run(str(br.get("byline") or meta.get("assessor") or "")); r.font.size = Pt(7.5); r.font.color.rgb = MUTED; r.font.name = MONO
    r = fp.add_run("\t" + L["running"]["page"] + " "); r.font.size = Pt(7.5); r.font.color.rgb = MUTED; r.font.name = MONO
    field(fp, "PAGE")
    r = fp.add_run(" " + L["running"]["of"] + " "); r.font.size = Pt(7.5); r.font.color.rgb = MUTED; r.font.name = MONO
    field(fp, "NUMPAGES")

    def newpage():
        doc.add_page_break()

    has_finding_details = True

    def render_summary_body():
        sumf = engine.summary_findings(data["findings"]); counts = engine.severity_counts(data["findings"])
        doc.add_paragraph(engine.summary_text(data["findings"], L))
        if sum(counts.values()):
            if engine.unclassified_count(data["findings"]):
                doc.add_paragraph(L['summary']['chart_scope'])
            with tempfile.TemporaryDirectory(prefix='rg-chart-') as tempdir:
                chart = Path(tempdir) / 'severity.png'
                _sev_chart_png(counts, hx, chart, L)
                doc.add_picture(str(chart), width=Cm(9))
                doc.inline_shapes[-1]._inline.docPr.set("descr", "report-gen:severity-chart")
        if sumf:
            rows = [[i, summary_sev(L, f), f.get("title") or f.get("id", "")] for i, f in enumerate(sumf, 1)]
            table=data_table([lab["col_num"], lab["col_sev"], lab["col_finding"]], rows, [7, 27, 66])
            if has_finding_details:
                from .navigation import reference_name
                for row,f in zip(table.rows[1:],sumf):
                    p=row.cells[2].paragraphs[0];p.clear()
                    link=OxmlElement('w:hyperlink');link.set(qn('w:anchor'),reference_name(f['id']))
                    run=p.add_run(f.get('title') or f.get('id',''));link.append(run._r);p._p.append(link)

    def render_one_finding(f):
        if f.get("mode") == "machine":
            host = f.get("host") or {}
            heading(f"{f.get('id','')} {host.get('name') or f.get('title','')}", 2, toc=not bool((data.get('report') or {}).get('sections')), anchor=f.get('id'))
            rows = []
            if host.get("ip"): rows.append((lab["ip"], host["ip"]))
            if f.get("open_ports"): rows.append((lab["open_ports"], f["open_ports"]))
            if host.get("os"): rows.append((lab["os"], host["os"]))
            if rows: kv_table(rows, keep_next=True)
            if f.get("summary_md"):
                p = doc.add_paragraph(); p.paragraph_format.keep_with_next=True; rb = p.add_run(lab["attack_path"] + ". "); rb.bold = True
                add_markdown(f["summary_md"])
            for ph in f.get("phases", []):
                heading(ph.get("name", ""), 3)
                for s in ph.get("steps", []): step(s)
            if f.get("proof"):
                heading(lab["proof"], 3)
                data_table([lab["file"], lab["hash"]], [[p.get("name", ""), p.get("value", "")] for p in f["proof"]])
        else:
            heading(f"{f.get('id','')} {f.get('title','')}", 2, sev=f.get("severity"), toc=not bool((data.get('report') or {}).get('sections')), anchor=f.get('id'))
            rows = []
            if f.get("cwe"): rows.append((lab["cwe"], f["cwe"]))
            if f.get("cvss_vector") or f.get("cvss") not in (None, ""):
                score = str(f['cvss']) if f.get('cvss') not in (None, '') else ''
                rows.append((cvss_label(lab, f), (score + "  " + (f.get("cvss_vector") or "")).strip()))
            if f.get("affected"): rows.append((lab["affected"], f["affected"]))
            if rows: kv_table(rows, keep_next=True)
            for key, lbl in [("description_md", lab["desc_root"]), ("impact_md", lab["impact"]), ("remediation_md", lab["remediation"])]:
                if f.get(key):
                    # Match the generated HTML/Markdown field heading exactly:
                    # a leading image binds to this visible text in every format.
                    p = doc.add_paragraph(); p.paragraph_format.keep_with_next = True; rb = p.add_run(lbl); rb.bold = True
                    add_markdown(f[key])
            if f.get("references"):
                heading(lab["references"], 3)
                for r in f["references"]: doc.add_paragraph(r, style="List Bullet")
            if f.get("walkthrough"):
                heading(lab["walkthrough"], 3)
                for s in f["walkthrough"]: step(s)
            rs = f.get("remediation_summary") or {}
            if any(rs.values()):
                heading(lab["rem_summary"], 3)
                for key, lbl in [("short_md", lab["short_term"]), ("medium_md", lab["medium_term"]), ("long_md", lab["long_term"])]:
                    if rs.get(key):
                        p = doc.add_paragraph(style="List Bullet"); p.paragraph_format.keep_with_next = True
                        rb = p.add_run(lbl + ": "); rb.bold = True
                        add_markdown(rs[key])

    # ---- Rama por secciones (mismo orden/contenido que el PDF) ----
    if (data.get("report") or {}).get("sections"):
        import sections as _sections
        rsecs = _sections.resolve_sections(data, L, meta.get("lang", "en"))
        has_finding_details = any(s.get("special") == "findings" for s in rsecs)

        def render_generic(s):
            vals = [f for f in s["fields"] if f.get("value")]
            multi = len(vals) > 1
            for f in s["fields"]:
                v = f.get("value")
                if v:
                    if multi: heading(f["label"], 3)
                    if f["type"] == "markdown": add_markdown(v, keep_tables=False, retest=s.get("key") == "rg_retest", workflow_key=s.get("key"))
                    elif f["type"] == "text": doc.add_paragraph(v)
                    elif f["type"] == "table":
                        data_table([c["label"] for c in f.get("columns", [])], [[row.get(c["key"], "") for c in f.get("columns", [])] for row in v])
                    elif f["type"] == "list":
                        for it in v: doc.add_paragraph(str(it), style="List Bullet")
                elif f.get("default_lang"):
                    client = (meta.get("client") or lab["client"]).rstrip(".")
                    for para in L["prose"][f["default_lang"]]:
                        doc.add_paragraph(para.replace("{client}", client).replace("{assessor}", meta.get("assessor") or ""))

        for i, s in enumerate(rsecs, 1):
            if i > 1: newpage()
            heading(s["title"], 1, anchor=s['key'])
            sp = s.get("special")
            if sp == "contacts":
                c = meta.get("contacts") or {}
                for grp, gt in [("client", lab["client"]), ("assessor", lab["team"])]:
                    ppl = c.get(grp) or []
                    if ppl:
                        heading(gt, 2)
                        data_table([lab["name"], lab["title"], lab["email"]], [[p.get("name", ""), p.get("title", ""), p.get("email", "")] for p in ppl])
            elif sp == "scope":
                render_generic(s)
                if meta.get("scope"):
                    heading(lab["scope"], 2)
                    data_table([lab["target"], lab["description"]], [[x.get("target", ""), x.get("description", "")] for x in meta["scope"]])
            elif sp == "summary":
                render_summary_body()
            elif sp == "findings":
                for idx, f in enumerate(data["findings"]):
                    render_one_finding(f)
            elif sp == "appendix":
                render_generic(s)
                appx = engine.appendix_rows(data["findings"])
                if appx:
                    heading(lab["appendix"], 2)
                    doc.add_paragraph(L.get("appendix_intro", ""))
                    data_table([lab["host"], lab["item"], lab["value"], lab["notes"]], [[r["host"], r["item"], r["value"], r["notes"]] for r in appx])
            else:
                render_generic(s)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        from .navigation import add_toc
        add_toc(doc, navigation, lab['toc'], INK)
        doc.save(str(out_path))
        return Path(out_path)

    # Confidencialidad
    heading(lab["confidentiality"], 1, anchor='sec-conf')
    if meta.get("confidentiality_md"):
        add_markdown(meta["confidentiality_md"])
    else:
        client = (meta.get("client") or lab["client"]).rstrip(".")
        for para in L["prose"]["confidentiality"]:
            doc.add_paragraph(para.replace("{client}", client))

    # Contactos
    contacts = meta.get("contacts") or {}
    if contacts.get("client") or contacts.get("assessor"):
        newpage(); heading(lab["contacts"], 1, anchor='sec-contacts')
        for grp, gt in [("client", lab["client"]), ("assessor", lab["team"])]:
            ppl = contacts.get(grp) or []
            if ppl:
                heading(gt, 2)
                data_table([lab["name"], lab["title"], lab["email"]], [[p.get("name", ""), p.get("title", ""), p.get("email", "")] for p in ppl])

    # Overview
    newpage(); heading(lab["overview"], 1, anchor='sec-overview'); heading(lab["approach"], 2)
    if meta.get("overview", {}).get("approach_md"):
        add_markdown(meta["overview"]["approach_md"])
    else:
        client = (meta.get("client") or lab["client"]).rstrip(".")
        for para in L["prose"]["approach"]:
            doc.add_paragraph(para.replace("{assessor}", meta.get("assessor") or lab["team"]).replace("{client}", client))
    if meta.get("scope"):
        heading(lab["scope"], 2)
        data_table([lab["target"], lab["description"]], [[s.get("target", ""), s.get("description", "")] for s in meta["scope"]])

    # The legacy model uses the same summary and finding renderers.
    newpage(); heading(lab["summary"], 1, anchor='sec-summary')
    render_summary_body()
    newpage(); heading(lab["findings"], 1)
    for finding in data["findings"]:
        render_one_finding(finding)

    # Appendix
    appx = engine.appendix_rows(data["findings"])
    if appx:
        newpage(); heading(lab["appendix"], 1, anchor='sec-appendix')
        doc.add_paragraph(L.get("appendix_intro", ""))
        data_table([lab["host"], lab["item"], lab["value"], lab["notes"]], [[r["host"], r["item"], r["value"], r["notes"]] for r in appx])

    for extra in report_sections(data):
        newpage(); heading(extra["title"], 1, anchor=extra['key'])
        add_markdown(extra["body"], keep_tables=False, retest=extra["key"] == "rg_retest", workflow_key=extra['key'])
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    from .navigation import add_toc
    add_toc(doc, navigation, lab['toc'], INK)
    doc.save(str(out_path))
    return Path(out_path)
