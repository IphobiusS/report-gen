"""Exportacion a Markdown (consciente de secciones)."""
from error_messages import message as backend_message
import engine
import re
from urllib.parse import quote
from resources import relative_image
from workflows import md_text

from .common import sev_label, cvss_label, summary_sev


def authored(text):
    """Escape literal anchor examples without changing fenced/inline code.

    The shared renderer treats raw HTML as text. Leaving report-like anchors
    unescaped in the Markdown export instead made its inspector mistake an
    authored example for a generated boundary (or a duplicate finding).
    """
    pattern = re.compile(r'^<a id="[^"<>]+"></a>\n(?=\s*#{1,6} )', re.M)
    matches = list(pattern.finditer(text))
    if not matches:
        return text
    from safe_markup import _parsed
    from lxml import html
    from uuid import uuid4
    prefix = 'RGANCHOREXAMPLE' + uuid4().hex + 'X'
    while prefix in text:
        prefix = 'RGANCHOREXAMPLE' + uuid4().hex + 'X'
    markers = {prefix + str(i) + 'X': i for i in range(len(matches))}
    parts = []; cursor = 0
    for marker, i in markers.items():
        match = matches[i]
        parts.extend((text[cursor:match.start()], marker + '\n'))
        cursor = match.end()
    probe = ''.join(parts) + text[cursor:]
    tree = html.fragment_fromstring(_parsed(probe), create_parent='div')
    token = re.compile(re.escape(prefix) + r'\d+X')
    prose = set()
    for node in tree.iter():
        for value, context in ((node.text, node), (node.tail, node.getparent())):
            if value and context is not None and not any(
                    element.tag in {'pre', 'code'} for element in [context, *context.iterancestors()]):
                prose.update(markers[match[0]] for match in token.finditer(value))
    parts = []; cursor = 0
    for i, match in enumerate(matches):
        parts.extend((text[cursor:match.start()], '&lt;' + match[0][1:] if i in prose else match[0]))
        cursor = match.end()
    result = ''.join(parts) + text[cursor:]
    if _parsed(result) != _parsed(text):
        raise ValueError(backend_message('No se puede preservar el ejemplo de ancla Markdown',
                                         en='Cannot preserve the Markdown anchor example'))
    return result


def _row(*values):
    return "| " + " | ".join(md_text(value) for value in values) + " |"


def _image(caption, source):
    # Labels are plain user text; destinations are validated local paths.
    # An unescaped closing bracket otherwise silently drops the image from ZIP.
    target = quote(relative_image(source).as_posix(), safe='/')
    return f"![{md_text(caption)}]({target})"


def _summary_chart(W, data, L):
    from .charts import summary_asset
    chart = summary_asset(data, L)
    if chart:
        W(_image(chart["alt"], chart["path"]) + "\n")
        W(md_text(chart["caption"]) + "\n")


def _cover_details(W, meta, L):
    lab = L['labels']
    assessor = str(meta.get('assessor') or '')
    if meta.get('assessor_title'):
        assessor += (' · ' if assessor else '') + str(meta['assessor_title'])
    for label, value in [(lab['client'], meta.get('client')),
                         (lab['cover_osid'], meta.get('osid')),
                         (lab['cover_email'], meta.get('email')),
                         (lab['cover_assessor'], assessor),
                         (lab['cover_date'], meta.get('date')),
                         (lab['cover_version'], meta.get('version'))]:
        if value not in (None, ''): W(f"- **{label}:** {md_text(value)}")
    W('')
    branding = meta.get('branding') or {}
    for key, label in [('logo', lab['assessor_logo']),
                       ('client_logo', lab['client_logo']),
                       ('cover_image', lab['cover_image'])]:
        if branding.get(key): W(_image(label, branding[key]) + '\n')


def _md_sections(data, meta, L):
    import sections as _sections
    lab = L["labels"]
    rsecs = _sections.resolve_sections(data, L, meta.get("lang", "en"))
    has_finding_details = any(s.get("special") == "findings" for s in rsecs)
    out = []
    W = out.append
    W(f"# {md_text(meta.get('report_title',''))}\n")
    if meta.get("report_subtitle"):
        W(f"*{md_text(meta['report_subtitle'])}*\n")
    W(f"> {md_text((meta.get('branding') or {}).get('confidential_text',lab['default_confidential']))}\n")
    _cover_details(W, meta, L)
    client = (meta.get("client") or lab["client"]).rstrip(".")

    def gen(s):
        vals = [f for f in s["fields"] if f.get("value")]
        multi = len(vals) > 1
        for f in s["fields"]:
            v = f.get("value")
            if v:
                if multi:
                    W(f"### {f['label']}\n")
                if f["type"] == "markdown":
                    W(authored(v) + "\n")
                elif f["type"] == "text":
                    W(md_text(v) + "\n")
                elif f["type"] == "table":
                    cols = f.get("columns", [])
                    W("| " + " | ".join(c["label"] for c in cols) + " |")
                    W("|" + "---|" * len(cols))
                    for row in v:
                        W(_row(*(row.get(c["key"], "") for c in cols)))
                    W("")
                elif f["type"] == "list":
                    for it in v:
                        W(f"- {md_text(it)}")
                    W("")
            elif f.get("default_lang"):
                for para in L["prose"][f["default_lang"]]:
                    W(md_text(para.replace("{client}", client).replace("{assessor}", meta.get("assessor") or "")) + "\n")

    for i, s in enumerate(rsecs, 1):
        W(anchor(s["key"]))
        W(f"## {i}. {md_text(s['title'])}\n")
        sp = s.get("special")
        if sp == "contacts":
            c = meta.get("contacts") or {}
            for grp, gt in [("client", lab["client"]), ("assessor", lab["team"])]:
                ppl = c.get(grp) or []
                if ppl:
                    W(f"### {gt}\n")
                    W(f"| {lab['name']} | {lab['title']} | {lab['email']} |")
                    W("|---|---|---|")
                    for p in ppl:
                        W(_row(p.get('name',''), p.get('title',''), p.get('email','')))
                    W("")
        elif sp == "scope":
            gen(s)
            if meta.get("scope"):
                W(f"### {lab['scope']}\n")
                W(f"| {lab['target']} | {lab['description']} |")
                W("|---|---|")
                for x in meta["scope"]:
                    W(_row(x.get('target',''), x.get('description','')))
                W("")
        elif sp == "summary":
            sumf = engine.summary_findings(data["findings"])
            W(engine.summary_text(data["findings"], L) + "\n")
            _summary_chart(W, data, L)
            if sumf:
                W(f"| {lab['col_num']} | {lab['col_sev']} | {lab['col_finding']} |")
                W("|---|---|---|")
                for j, f in enumerate(sumf, 1):
                    sv = summary_sev(L, f)
                    W(_summary_row(j,sv,f,linked=has_finding_details))
                W("")
        elif sp == "findings":
            for f in data["findings"]:
                if f.get("mode") == "machine":
                    _md_machine(W, f, L, lab)
                else:
                    _md_vuln(W, f, L, lab)
        elif sp == "appendix":
            gen(s)
            appx = engine.appendix_rows(data["findings"], L)
            if appx:
                W(f"### {lab['appendix']}\n")
                W(L.get("appendix_intro", "") + "\n")
                W(f"| {lab['host']} | {lab['item']} | {lab['value']} | {lab['notes']} |")
                W("|---|---|---|---|")
                for r in appx:
                    W(_row(r['host'], r['item'], r['value'], r['notes']))
                W("")
        else:
            gen(s)
    return "\n".join(out).rstrip() + "\n"


def to_markdown(data, meta, L, engagement_dir):
    from workflows import project_report, report_sections
    data = project_report(data)
    meta = data["meta"]
    import engine
    engine.number_figures(data["findings"])
    if (data.get("report") or {}).get("sections"):
        return _md_sections(data, meta, L)
    lab = L["labels"]
    out = []
    W = out.append
    br = meta.get("branding") or {}
    conf = br.get("confidential_text", lab["default_confidential"])

    W(f"# {md_text(meta.get('report_title',''))}\n")
    if meta.get("report_subtitle"):
        W(f"*{md_text(meta['report_subtitle'])}*\n")
    W("")
    W(f"> {md_text(conf)}\n")
    _cover_details(W, meta, L)

    # Confidencialidad
    W(anchor("sec-conf") + f"## {lab['confidentiality']}\n")
    if meta.get("confidentiality_md"):
        W(authored(meta["confidentiality_md"]) + "\n")
    else:
        client = (meta.get("client") or lab["client"]).rstrip(".")
        for para in L["prose"]["confidentiality"]:
            W(md_text(para.replace("{client}", client)) + "\n")

    # Contactos
    contacts = meta.get("contacts") or {}
    # The legacy HTML/PDF always exposes this section, even before people are
    # entered. Keep its destination so authored cross-references also work here.
    W(anchor("sec-contacts") + f"## {lab['contacts']}\n")
    for grp, title in [("client", lab["client"]), ("assessor", lab["team"])]:
        people = contacts.get(grp) or []
        if people:
            W(f"### {title}\n")
            W(f"| {lab['name']} | {lab['title']} | {lab['email']} |")
            W("|---|---|---|")
            for p in people:
                W(_row(p.get('name',''), p.get('title',''), p.get('email','')))
            W("")

    # Overview + scope
    W(anchor("sec-overview") + f"## {lab['overview']}\n")
    W(f"### {lab['approach']}\n")
    if meta.get("overview", {}).get("approach_md"):
        W(authored(meta["overview"]["approach_md"]) + "\n")
    else:
        client = (meta.get("client") or lab["client"]).rstrip(".")
        for para in L["prose"]["approach"]:
            W(md_text(para.replace("{assessor}", meta.get("assessor") or lab["team"]).replace("{client}", client)) + "\n")
    if meta.get("scope"):
        W(f"### {lab['scope']}\n")
        W(f"| {lab['target']} | {lab['description']} |")
        W("|---|---|")
        for s in meta["scope"]:
            W(_row(s.get('target',''), s.get('description','')))
        W("")

    # Summary
    sumf = engine.summary_findings(data["findings"])
    W(anchor("sec-summary") + f"## {lab['summary']}\n")
    W(engine.summary_text(data["findings"], L) + "\n")
    _summary_chart(W, data, L)
    if sumf:
        W(f"| {lab['col_num']} | {lab['col_sev']} | {lab['col_finding']} |")
        W("|---|---|---|")
        for i, f in enumerate(sumf, 1):
            sv = summary_sev(L, f)
            W(_summary_row(i,sv,f))
        W("")

    # Findings
    W(f"## {lab['findings']}\n")
    for f in data["findings"]:
        if f.get("mode") == "machine":
            _md_machine(W, f, L, lab)
        else:
            _md_vuln(W, f, L, lab)

    # Appendix
    appx = engine.appendix_rows(data["findings"], L)
    if appx:
        W(anchor("sec-appendix") + f"## {lab['appendix']}\n")
        W(L.get("appendix_intro", "") + "\n")
        W(f"| {lab['host']} | {lab['item']} | {lab['value']} | {lab['notes']} |")
        W("|---|---|---|---|")
        for r in appx:
            W(_row(r['host'], r['item'], r['value'], r['notes']))
        W("")

    for extra in report_sections(data):
        W(anchor(extra["key"]) + "\n## " + extra["title"] + "\n\n" + authored(extra["body"]) + "\n")
    return "\n".join(out).rstrip() + "\n"


def _figure_caption(label, number, value):
    """Keep visible caption lines without invalid whitespace-ended emphasis."""
    text = str(value or '').replace('\r\n', '\n').replace('\r', '\n')
    lines = [md_text(line) for line in text.split('\n')]
    lines[0] = f"{label} {number}. " + lines[0]
    # Blank source lines must stay inside the caption paragraph. A literal LF
    # entity keeps the line nonempty in Markdown syntax without adding a glyph;
    # standard hard breaks retain each authored line even without nl2br.
    lines = [line if line.strip() else line + '&#10;' for line in lines]
    body = '  \n'.join(lines)
    end = len(body.rstrip())
    # Markdown cannot close emphasis after whitespace, including an empty
    # caption's generated separator. Preserve that whitespace outside it.
    return '*' + body[:end] + '*' + body[end:]


def _md_step(W, s, L):
    lead = f"**{md_text(s['lead'])}** " if s.get("lead") else ""
    if s.get("text_md"):
        W((lead.rstrip() + '\n\n' if lead else '') + authored(s['text_md']) + '\n')
    elif lead:
        W(lead + "\n")
    if s.get("command"):
        command = s["command"].replace("\r\n", "\n").replace("\r", "\n")
        fence = '`' * max(3, 1 + max((len(x) for x in re.findall(r'`+', command)), default=0))
        W(fence + "\n" + command + "\n" + fence + "\n")
    fig = s.get("figure")
    if fig and fig.get("src"):
        cap = _figure_caption(L['figure'], fig.get('number', ''), fig.get('caption', ''))
        W(_image(fig.get('caption',''), fig['src']) + f"\n\n{cap}\n")


def _md_vuln(W, f, L, lab):
    sev = sev_label(L, f.get("severity", "")) if f.get("severity") else ""
    W(anchor(f.get("id", "")))
    W(f"### {md_text(f.get('id',''))} {md_text(f.get('title',''))}\n")
    meta_rows = []
    if sev:
        meta_rows.append((lab["col_sev"], sev))
    if f.get("cwe"):
        meta_rows.append((lab["cwe"], f["cwe"]))
    if f.get("cvss_vector") or f.get("cvss") not in (None, ""):
        score = str(f['cvss']) if f.get('cvss') not in (None, '') else ''
        meta_rows.append((cvss_label(lab, f), (score + " " + (f.get("cvss_vector") or "")).strip()))
    if f.get("affected"):
        meta_rows.append((lab["affected"], f["affected"]))
    for k, v in meta_rows:
        W(f"- **{k}:** {md_text(v)}")
    W("")
    if f.get("description_md"):
        W(f"**{lab['desc_root']}.**\n\n{authored(f['description_md'])}\n")
    if f.get("impact_md"):
        W(f"**{lab['impact']}.**\n\n{authored(f['impact_md'])}\n")
    if f.get("remediation_md"):
        W(f"**{lab['remediation']}.**\n\n{authored(f['remediation_md'])}\n")
    if f.get("references"):
        W(f"**{lab['references']}:**")
        W("")
        for r in f["references"]:
            W(f"- {md_text(r)}")
        W("")
    if f.get("walkthrough"):
        W(f"#### {lab['walkthrough']}\n")
        for s in f["walkthrough"]:
            _md_step(W, s, L)
    rs = f.get("remediation_summary") or {}
    if any(rs.values()):
        W(f"#### {lab['rem_summary']}\n")
        for key, lbl in [("short_md", lab["short_term"]), ("medium_md", lab["medium_term"]), ("long_md", lab["long_term"])]:
            if rs.get(key):
                W(f"**{lbl}:**\n\n{authored(rs[key])}\n")
        W("")


def _md_machine(W, f, L, lab):
    host = f.get("host") or {}
    W(anchor(f.get("id", "")))
    W(f"### {md_text(f.get('id',''))} {md_text(host.get('name') or f.get('title',''))}\n")
    rows = []
    if host.get("ip"):
        rows.append((lab["ip"], host["ip"]))
    if f.get("open_ports"):
        rows.append((lab["open_ports"], f["open_ports"]))
    if host.get("os"):
        rows.append((lab["os"], host["os"]))
    for k, v in rows:
        W(f"- **{k}:** {md_text(v)}")
    W("")
    if f.get("summary_md"):
        W(f"**{lab['attack_path']}.**\n\n{authored(f['summary_md'])}\n")
    for ph in f.get("phases", []):
        W(f"#### {md_text(ph.get('name',''))}\n")
        for s in ph.get("steps", []):
            _md_step(W, s, L)
    if f.get("proof"):
        W(f"#### {lab['proof']}\n")
        W(f"| {lab['file']} | {lab['hash']} |")
        W("|---|---|")
        for p in f["proof"]:
            W(_row(p.get('name',''), p.get('value','')))
        W("")


def anchor(identity):
    from html import escape
    return '<a id="'+escape(str(identity),quote=True)+'"></a>\n'


def parse_exported(source):
    """Keep report boundaries separate from authored headings and literal code."""
    from safe_markup import md
    from lxml import html
    from html import unescape
    from uuid import uuid4
    prefix='RGEXPORTEDANCHOR'+uuid4().hex+'X'
    while prefix in source:
        prefix='RGEXPORTEDANCHOR'+uuid4().hex+'X'
    markers={}
    def protect(match):
        marker=prefix+str(len(markers))+'X'
        markers[marker]=(unescape(match[1]),match[0].removesuffix('\n'))
        return marker+'\n'
    pattern=re.compile(r'^<a id="([^"<>]+)"></a>\n(?=\s*#{1,6} )',re.M)
    tree=html.fragment_fromstring(str(md(pattern.sub(protect,source),img_base='')),create_parent='main')
    ids=[]
    # Protect escaped identities from inline Markdown parsing, then let the
    # parser determine whether the marker is a boundary or literal code.
    # Only standalone paragraphs immediately before headings are boundaries.
    for node in list(tree):
        following=node.getnext()
        marker=markers.get(node.text or '')
        if (node.tag=='p' and len(node)==0 and marker and following is not None
                and following.tag in {'h1','h2','h3','h4','h5','h6'}):
            ids.append(marker[0])
            following.set('data-rg-anchor',marker[0])
            tree.remove(node)
    # A matching source line inside fenced/inline code stays exact text.
    token=re.compile(re.escape(prefix)+r'\d+X')
    def restore(value):
        return token.sub(lambda match:markers[match[0]][1],value) if value else value
    for node in tree.iter():
        node.text=restore(node.text)
        node.tail=restore(node.tail)
    if len(ids)!=len(set(ids)):raise ValueError(backend_message('Identificadores Markdown duplicados'))
    # Validate every internal destination against trusted emitted anchors.
    # Authored subsection links must target an explicit report section/finding.
    from urllib.parse import unquote
    for href in tree.xpath('.//a[starts-with(@href,"#")]/@href'):
        if href!='#' and unquote(href[1:]) not in ids:raise ValueError(backend_message('Destino Markdown inexistente: {p0}', p0=href))
    return tree


def _summary_row(number,severity,finding,linked=True):
    title=md_text(finding.get('title') or finding.get('id',''))
    if linked:
        title='['+title+'](#'+quote(finding['id'],safe='')+')'
    return '| '+md_text(number)+' | '+md_text(severity)+' | '+title+' |'
