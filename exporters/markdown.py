"""Exportacion a Markdown (consciente de secciones)."""
import engine

from .common import sev_label, cvss_label, summary_sev


def _md_sections(data, meta, L):
    import sections as _sections
    lab = L["labels"]
    rsecs = _sections.resolve_sections(data, L, meta.get("lang", "en"))
    out = []
    W = out.append
    W(f"# {meta.get('report_title','')}\n")
    if meta.get("report_subtitle"):
        W(f"*{meta['report_subtitle']}*\n")
    W(f"> {(meta.get('branding') or {}).get('confidential_text','CONFIDENTIAL')}\n")
    for k, v in [(lab["client"], meta.get("client", "")),
                 (lab["cover_assessor"], meta.get("assessor", "")),
                 (lab["cover_date"], meta.get("date", "")), (lab["cover_version"], meta.get("version", ""))]:
        if v:
            W(f"- **{k}:** {v}")
    W("")
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
                    W(v + "\n")
                elif f["type"] == "text":
                    W(v + "\n")
                elif f["type"] == "table":
                    cols = f.get("columns", [])
                    W("| " + " | ".join(c["label"] for c in cols) + " |")
                    W("|" + "---|" * len(cols))
                    for row in v:
                        W("| " + " | ".join(str(row.get(c["key"], "")) for c in cols) + " |")
                    W("")
                elif f["type"] == "list":
                    for it in v:
                        W(f"- {it}")
                    W("")
            elif f.get("default_lang"):
                for para in L["prose"][f["default_lang"]]:
                    W(para.replace("{client}", client).replace("{assessor}", meta.get("assessor", "")) + "\n")

    for i, s in enumerate(rsecs, 1):
        W(f"## {i}. {s['title']}\n")
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
                        W(f"| {p.get('name','')} | {p.get('title','')} | {p.get('email','')} |")
                    W("")
        elif sp == "scope":
            gen(s)
            if meta.get("scope"):
                W(f"### {lab['scope']}\n")
                W(f"| {lab['target']} | {lab['description']} |")
                W("|---|---|")
                for x in meta["scope"]:
                    W(f"| `{x.get('target','')}` | {x.get('description','')} |")
                W("")
        elif sp == "summary":
            counts = engine.severity_counts(data["findings"]); sumf = engine.summary_findings(data["findings"])
            parts = [f"{counts[k]} {sev_label(L, k).lower()}" for k in engine.SEVERITY_ORDER if counts[k] > 0]
            total = len(sumf); noun = L["summary"]["finding"] if total == 1 else L["summary"]["findings"]
            W(f"{L['summary']['identified']} **{total}** {noun} {L['summary']['rating']} {', '.join(parts) if parts else L['summary']['none']}.\n")
            if sumf:
                W(f"| {lab['col_num']} | {lab['col_sev']} | {lab['col_finding']} |")
                W("|---|---|---|")
                for j, f in enumerate(sumf, 1):
                    sv = summary_sev(L, f)
                    W(f"| {j} | {sv} | {f.get('title','')} |")
                W("")
        elif sp == "findings":
            for f in data["findings"]:
                if f.get("mode") == "machine":
                    _md_machine(W, f, L, lab)
                else:
                    _md_vuln(W, f, L, lab)
        elif sp == "appendix":
            gen(s)
            appx = engine.appendix_rows(data["findings"])
            if appx:
                W(f"### {lab['appendix']}\n")
                W(f"| {lab['host']} | {lab['item']} | {lab['value']} | {lab['notes']} |")
                W("|---|---|---|---|")
                for r in appx:
                    W(f"| {r['host']} | `{r['item']}` | `{r['value']}` | {r['notes']} |")
                W("")
        else:
            gen(s)
    return "\n".join(out).rstrip() + "\n"


def to_markdown(data, meta, L, engagement_dir):
    if (data.get("report") or {}).get("sections"):
        return _md_sections(data, meta, L)
    lab = L["labels"]
    out = []
    W = out.append
    br = meta.get("branding") or {}
    conf = br.get("confidential_text", "CONFIDENTIAL")

    W(f"# {meta.get('report_title','')}\n")
    if meta.get("report_subtitle"):
        W(f"*{meta['report_subtitle']}*\n")
    W("")
    W(f"> {conf}\n")
    rows = []
    if meta.get("client"):
        rows.append((lab["client"], meta["client"]))
    rows.append((lab["cover_assessor"], f"{meta.get('assessor','')}"
                 + (f" ({meta['assessor_title']})" if meta.get("assessor_title") else "")))
    if meta.get("date"):
        rows.append((lab["cover_date"], meta["date"]))
    if meta.get("version"):
        rows.append((lab["cover_version"], meta["version"]))
    for k, v in rows:
        W(f"- **{k}:** {v}")
    W("")

    # Confidencialidad
    W(f"## {lab['confidentiality']}\n")
    if meta.get("confidentiality_md"):
        W(meta["confidentiality_md"] + "\n")
    else:
        client = (meta.get("client") or lab["client"]).rstrip(".")
        for para in L["prose"]["confidentiality"]:
            W(para.replace("{client}", client) + "\n")

    # Contactos
    contacts = meta.get("contacts") or {}
    if contacts.get("client") or contacts.get("assessor"):
        W(f"## {lab['contacts']}\n")
        for grp, title in [("client", lab["client"]), ("assessor", lab["team"])]:
            people = contacts.get(grp) or []
            if people:
                W(f"### {title}\n")
                W(f"| {lab['name']} | {lab['title']} | {lab['email']} |")
                W("|---|---|---|")
                for p in people:
                    W(f"| {p.get('name','')} | {p.get('title','')} | {p.get('email','')} |")
                W("")

    # Overview + scope
    W(f"## {lab['overview']}\n")
    W(f"### {lab['approach']}\n")
    if meta.get("overview", {}).get("approach_md"):
        W(meta["overview"]["approach_md"] + "\n")
    else:
        client = (meta.get("client") or lab["client"]).rstrip(".")
        for para in L["prose"]["approach"]:
            W(para.replace("{assessor}", meta.get("assessor", "")).replace("{client}", client) + "\n")
    if meta.get("scope"):
        W(f"### {lab['scope']}\n")
        W(f"| {lab['target']} | {lab['description']} |")
        W("|---|---|")
        for s in meta["scope"]:
            W(f"| `{s.get('target','')}` | {s.get('description','')} |")
        W("")

    # Summary
    sumf = engine.summary_findings(data["findings"])
    counts = engine.severity_counts(data["findings"])
    W(f"## {lab['summary']}\n")
    parts = [f"{counts[s]} {sev_label(L, s).lower()}" for s in engine.SEVERITY_ORDER if counts[s] > 0]
    total = len(sumf)
    noun = L["summary"]["finding"] if total == 1 else L["summary"]["findings"]
    W(f"{L['summary']['identified']} **{total}** {noun} {L['summary']['rating']} "
      f"{', '.join(parts) if parts else L['summary']['none']}.\n")
    if sumf:
        W(f"| {lab['col_num']} | {lab['col_sev']} | {lab['col_finding']} |")
        W("|---|---|---|")
        for i, f in enumerate(sumf, 1):
            sv = summary_sev(L, f)
            W(f"| {i} | {sv} | {f.get('title','')} |")
        W("")

    # Findings
    W(f"## {lab['findings']}\n")
    for f in data["findings"]:
        if f.get("mode") == "machine":
            _md_machine(W, f, L, lab)
        else:
            _md_vuln(W, f, L, lab)

    # Appendix
    appx = engine.appendix_rows(data["findings"])
    if appx:
        W(f"## {lab['appendix']}\n")
        W(L.get("appendix_intro", "") + "\n")
        W(f"| {lab['host']} | {lab['item']} | {lab['value']} | {lab['notes']} |")
        W("|---|---|---|---|")
        for r in appx:
            W(f"| {r['host']} | `{r['item']}` | `{r['value']}` | {r['notes']} |")
        W("")

    return "\n".join(out).rstrip() + "\n"


def _md_step(W, s, L):
    lead = f"**{s['lead']}** " if s.get("lead") else ""
    if s.get("text_md"):
        W(f"{lead}{s['text_md']}\n")
    elif lead:
        W(lead + "\n")
    if s.get("command"):
        W("```\n" + s["command"].strip() + "\n```\n")
    fig = s.get("figure")
    if fig and fig.get("src"):
        cap = f"*{L['figure']} {fig.get('number','')}. {fig.get('caption','')}*"
        W(f"![{fig.get('caption','')}]({fig['src']})\n\n{cap}\n")


def _md_vuln(W, f, L, lab):
    sev = sev_label(L, f.get("severity", "")) if f.get("severity") else ""
    W(f"### {f.get('id','')} {f.get('title','')}\n")
    meta_rows = []
    if sev:
        meta_rows.append((lab["col_sev"], sev + (f" ({f['cvss']})" if f.get("cvss") else "")))
    if f.get("cwe"):
        meta_rows.append((lab["cwe"], f["cwe"]))
    if f.get("cvss_vector"):
        meta_rows.append((cvss_label(lab, f), f"`{f['cvss_vector']}`"))
    if f.get("affected"):
        meta_rows.append((lab["affected"], f"`{f['affected']}`"))
    for k, v in meta_rows:
        W(f"- **{k}:** {v}")
    W("")
    if f.get("description_md"):
        W(f"**{lab['desc_root']}.** {f['description_md']}\n")
    if f.get("impact_md"):
        W(f"**{lab['impact']}.** {f['impact_md']}\n")
    if f.get("remediation_md"):
        W(f"**{lab['remediation']}.** {f['remediation_md']}\n")
    if f.get("references"):
        W(f"**{lab['references']}:**")
        for r in f["references"]:
            W(f"- {r}")
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
                W(f"- **{lbl}:** {rs[key]}")
        W("")


def _md_machine(W, f, L, lab):
    host = f.get("host") or {}
    W(f"### {f.get('id','')} {host.get('name') or f.get('title','')}\n")
    rows = []
    if host.get("ip"):
        rows.append((lab["ip"], f"`{host['ip']}`"))
    if f.get("open_ports"):
        rows.append((lab["open_ports"], f["open_ports"]))
    if host.get("os"):
        rows.append((lab["os"], host["os"]))
    for k, v in rows:
        W(f"- **{k}:** {v}")
    W("")
    if f.get("summary_md"):
        W(f"**{lab['attack_path']}.** {f['summary_md']}\n")
    for ph in f.get("phases", []):
        W(f"#### {ph.get('name','')}\n")
        for s in ph.get("steps", []):
            _md_step(W, s, L)
    if f.get("proof"):
        W(f"#### {lab['proof']}\n")
        W(f"| {lab['file']} | {lab['hash']} |")
        W("|---|---|")
        for p in f["proof"]:
            W(f"| `{p.get('name','')}` | `{p.get('value','')}` |")
        W("")
