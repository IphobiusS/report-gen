"""Deterministic report charts and palettes shared by editable and Markdown exports."""
import re
from pathlib import Path
from io import BytesIO
from hashlib import sha256
import engine
from error_messages import message
from .common import sev_label


def palette(meta, for_word=False):
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


def severity_chart_png(counts, hx, out, L):
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
    im.save(out, format="PNG")


def _asset(counts, colors, labels, caption):
    """A generated resource is bound to its pixels, counts and accessible prose."""
    target = BytesIO()
    severity_chart_png(counts, lambda token, default: colors.get(token[4:], default).lstrip('#'),
                       target, {'severity': labels})
    blob = target.getvalue()
    digest = sha256(blob).hexdigest()
    alt = caption + ': ' + '; '.join(f'{labels[key]}: {counts[key]}' for key in engine.SEVERITY_ORDER) + '.'
    return {'path': f'report-gen-assets/severity-{digest}.png', 'sha256': digest,
            'counts': counts, 'alt': alt, 'caption': caption, 'blob': blob}


def summary_asset(data, L):
    """Return the included summary's chart, never an evidence figure."""
    from workflows import project_report
    from sections import resolve_sections
    data = project_report(data)
    meta = data['meta']
    if (data.get('report') or {}).get('sections') and not any(
            section.get('special') == 'summary'
            for section in resolve_sections(data, L, meta.get('lang', 'en'))):
        return None
    counts = engine.severity_counts(data['findings'])
    if not sum(counts.values()):
        return None
    hx = palette(meta)
    colors = {key: '#' + hx('sev-' + key, '888888') for key in engine.SEVERITY_ORDER}
    return _asset(counts, colors, L['severity'], L['summary']['chart_scope'])


def contracts_from_tree(tree):
    """Read canonical summary SVG paints/counts, independent of a ZIP's claims."""
    result = []
    L = engine.load_lang(tree.get('lang', 'es'))
    for svg in tree.xpath('.//svg[contains(concat(" ",normalize-space(@class)," ")," sevchart ")]'):
        labels = svg.xpath('./text[contains(concat(" ",normalize-space(@class)," ")," bar-lab ")]/text()')
        if labels != [L['severity'][key] for key in engine.SEVERITY_ORDER]:
            raise ValueError(message('Etiquetas inesperadas en el gráfico canónico de severidad', en='Unexpected canonical severity-chart labels'))
        counts = {key: 0 for key in engine.SEVERITY_ORDER}
        colors = {key: '#888888' for key in engine.SEVERITY_ORDER}
        for bar in svg.xpath('./rect[contains(concat(" ",normalize-space(@class)," ")," bar ")]'):
            key = next((key for key in engine.SEVERITY_ORDER if 'bar-' + key in bar.get('class', '').split()), None)
            value = bar.getnext()
            if key is None or value is None or 'bar-val' not in value.get('class', '').split():
                raise ValueError(message('Barra inesperada en el gráfico canónico de severidad', en='Unexpected canonical severity-chart bar'))
            counts[key] = int(value.text)
            colors[key] = bar.get('fill')
            if counts[key] < 1 or not re.fullmatch(r'#[0-9a-fA-F]{6}', colors[key] or ''):
                raise ValueError(message('Color o conteo inválido en el gráfico canónico de severidad', en='Invalid canonical severity-chart paint or count'))
        if not sum(counts.values()):
            raise ValueError(message('El gráfico canónico de severidad está vacío', en='Unexpected empty canonical severity chart'))
        asset = _asset(counts, colors, L['severity'], L['summary']['chart_scope'])
        section = next((p for p in svg.iterancestors() if p.tag == 'section' and p.get('id')), None)
        if section is None:
            raise ValueError(message('El gráfico de severidad no tiene sección en el informe', en='Severity chart has no report section'))
        asset.pop('blob')
        asset['section'] = section.get('id')
        asset['lead'] = ' '.join(section.xpath('string(.//p[@class="sum-lead"])').split())
        result.append(asset)
    return result
def verify_markdown_charts(tree, digests, expected):
    """Check generated chart identity/order before excluding it from evidence checks."""
    def fail():
        raise ValueError(message('Gráfico Markdown ausente o alterado', en='Markdown chart missing or changed'))
    for chart in expected:
        images = tree.xpath('.//img[@src=$src]', src=chart['path'])
        anchors = tree.xpath('./h2[@data-rg-anchor=$section]', section=chart['section'])
        if len(images) != 1 or len(anchors) != 1 or digests.get(chart['path']) != chart['sha256']:
            fail()
        image = images[0]
        figure = image.getparent()
        lead = anchors[0].getnext()
        if (lead is None or lead.tag != 'p' or ' '.join(lead.text_content().split()) != chart['lead']
                or figure.tag != 'figure' or lead.getnext() is not figure
                or image.get('alt') != chart['alt']
                or figure.xpath('string(./figcaption)') != chart['alt']
                or len(figure.xpath('./img')) != 1):
            fail()
        caption = figure.getnext()
        if caption is None or caption.tag != 'p' or caption.text_content() != chart['caption']:
            fail()
        figure.drop_tree()
        caption.drop_tree()
