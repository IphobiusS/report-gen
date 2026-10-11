"""Semantic checks on public artifacts, never on hidden audit annotations.

Checks bind metadata, ordered links and evidence placements to their finding.
Static CSS checks cover the default screen view; they are not a layout engine.
"""
from error_messages import message as backend_message
from base64 import b64decode
from hashlib import sha256
from urllib.parse import unquote
import posixpath
import re

from lxml import etree
from export_contract import normal, has_class, W, NS, _word_text

R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'


def visible_copy(tree):
    """Remove statically hidden nodes before collecting any verified content.

    Apply ordinary author selectors, inline declarations and !important for the
    default screen view. Dynamic state, geometry and occlusion require a browser.
    Unsupported conditional rules are left to the explicit visual-review gate.
    """
    from copy import deepcopy
    import tinycss2
    import cssselect2
    root = deepcopy(tree)
    matcher = cssselect2.Matcher()

    def declarations(tokens):
        return [(d.lower_name, tinycss2.serialize(d.value).strip().lower(), d.important)
                for d in tinycss2.parse_declaration_list(tokens, skip_comments=True, skip_whitespace=True)
                if d.type == 'declaration' and d.lower_name in ('display', 'visibility', 'opacity', 'content-visibility')]

    def rules(source):
        for rule in tinycss2.parse_stylesheet(source, skip_comments=True, skip_whitespace=True):
            if rule.type == 'qualified-rule':
                try: selectors = cssselect2.compile_selector_list(tinycss2.serialize(rule.prelude))
                except cssselect2.SelectorError: continue
                for selector in selectors:
                    if selector.pseudo_element is None: matcher.add_selector(selector, declarations(rule.content))
            elif rule.type == 'at-rule' and rule.lower_at_keyword == 'media' and rule.content:
                media = tinycss2.serialize(rule.prelude).strip().lower()
                if media in ('screen', 'all'): rules(tinycss2.serialize(rule.content))
    for node in root.xpath('.//style'): rules(node.text or '')
    hidden = []
    states = {}
    for wrapped in cssselect2.ElementWrapper.from_html_root(root).iter_subtree():
        node = wrapped.etree_element
        computed = {}
        for specificity, order, _, decls in matcher.match(wrapped):
            for name, value, important in decls:
                key = (important, 0, specificity, order)
                if name not in computed or key >= computed[name][0]: computed[name] = (key, value)
        for name, value, important in declarations(node.get('style', '')):
            key = (important, 1, (0, 0, 0), 0)
            if name not in computed or key >= computed[name][0]: computed[name] = (key, value)
        prop = {k: v[1] for k, v in computed.items()}
        parent = states.get(node.getparent(), (False, 'visible'))
        opacity = prop.get('opacity', '1')
        try: transparent = float(opacity.rstrip('%')) == 0
        except ValueError: transparent = False
        blocked = parent[0] or 'hidden' in node.attrib or prop.get('display') == 'none' or transparent or prop.get('content-visibility') == 'hidden'
        visibility = prop.get('visibility', parent[1])
        states[node] = (blocked, visibility)
        if blocked or visibility in ('hidden', 'collapse'): hidden.append(node)
    # Reject unverified hidden text by removing it; descendants made visible by
    # overrides are conservatively removed too, never falsely certified visible.
    for node in reversed(hidden):
        if node.getparent() is not None: node.drop_tree()
    return root


def caption(value):
    return re.sub(r'^(?:Figura|Figure)\s+\d+\.\s*', '', normal(value))


def dom(root, image_digest, markdown=False, severity_label='Severidad'):
    fields = []
    if markdown:
        # Exported metadata are top-level label/value list items, not arbitrary
        # prose mentioning the same value somewhere in the finding.
        for node in root.xpath('./ul/li'):
            if len(node) and node[0].tag in ('strong', 'b') and node[0].text_content().endswith(':'):
                label = normal(node[0].text_content()).removesuffix(':')
                value = normal((node[0].tail or '') + ''.join(n.text_content() + (n.tail or '') for n in list(node)[1:]))
                fields.append([label, value])
        severity = next((v for k,v in fields if k == severity_label), '')
        fields = [row for row in fields if row[0] != severity_label]
    else:
        for table in root.xpath('.//table'):
            if not (has_class(table, 'meta') or has_class(table, 'hostbox')): continue
            for row in table.xpath('./tbody/tr|./tr'):
                cells = row.xpath('./th|./td')
                if len(cells) == 2 and not cells[1].xpath(
                        './p|./ul|./ol|./table|./pre|./figure|./blockquote|./hr|./h1|./h2|./h3|./h4|./h5|./h6'):
                    fields.append([normal(cells[0].text_content()), normal(cells[1].text_content())])
        chips = root.xpath('.//header//*[contains(concat(" ", normalize-space(@class), " "), " sev-chip ")]')
        severity = normal(chips[0].text or '') if chips else ''
    links = [[normal(n.text_content()), unquote(n.get('href')) if n.get('href').startswith('#') else n.get('href')]
             for n in root.xpath('.//a[@href]')]
    images = []; codes = 0
    context=[]
    prefixes={}
    blocks={'p','div','li','tr','td','th','pre','h1','h2','h3','h4','figure','figcaption','br','dt','dd'}
    def preceding(node):
        if node.tag=='img':prefixes[node]=normal(''.join(context))[-200:]
        if node.tag in {'p','pre','li','h1','h2','h3','h4','td','th','figcaption','dt','dd'}:context.clear()
        if node.tag in blocks:context.append(' ')
        if node.text:context.append(node.text)
        for child in node:
            preceding(child)
            if child.tail:context.append(child.tail)
        if node.tag in blocks:context.append(' ')
    preceding(root)
    for node in root.iter():
        if node.tag == 'pre': codes += 1
        if node.tag != 'img': continue
        figure = next((a for a in node.iterancestors() if a.tag == 'figure'), None)
        cap = figure.find('figcaption') if figure is not None else None
        text = cap.text_content() if cap is not None else node.get('alt', '')
        images.append(dict(sha256=image_digest(node.get('src')), caption=caption(text), code_index=codes, preceding_text=prefixes[node]))
    return dict(fields=fields, severity=severity, links=links, images=images)


def html_digest(source):
    if not source or not source.startswith('data:image/') or ';base64,' not in source:
        raise ValueError(backend_message('Imagen no incorporada / Image is not embedded'))
    return sha256(b64decode(source.split(',', 1)[1], validate=True)).hexdigest()


def word(nodes, package):
    reltree = etree.fromstring(package.read('word/_rels/document.xml.rels'), parser=etree.XMLParser(resolve_entities=False, no_network=True))
    relationships = {n.get('Id'):n.get('Target') for n in reltree}
    fields=[]; links=[]; images=[]; severity=''; codes=0; context=[]
    for node in nodes:
        if node.xpath('.//w:pPr/w:pStyle[@w:val="Title"]', namespaces=NS): continue  # Cover has its own contract.
        paras = [node] if node.tag == W+'p' else node.findall('.//'+W+'p')
        for p in paras:
            prefixes={}
            context.append(' ')
            for el in p.iter():
                if el.tag in (W+'t',W+'tab',W+'br',W+'cr'):
                    context.append(_word_text(el))
                elif el.tag.endswith('}inline'):
                    prefixes[el]=normal(''.join(context))[-200:]
            if p.xpath('./w:pPr/w:pStyle[@w:val="ReportGenMeta"]', namespaces=NS):
                key, sep, value = _word_text(p).partition('\t')
                if sep: fields.append([normal(key),normal(value)])
            if p.xpath('./w:pPr/w:pStyle[@w:val="Heading2"]', namespaces=NS) and not severity:
                severity = normal(''.join(_word_text(n) for n in p.xpath('./w:r[w:rPr/w:shd]', namespaces=NS)))
            if p.xpath('./w:pPr/w:pStyle[@w:val="ReportGenCode"]', namespaces=NS): codes += 1
            for link in p.findall('.//'+W+'hyperlink'):
                anchor = link.get(W+'anchor')
                target = '#'+anchor if anchor else relationships.get(link.get(R+'id'), '')
                links.append([normal(_word_text(link)), target])
            for picture in p.xpath('.//*[local-name()="inline"]'):
                props = picture.xpath('./*[local-name()="docPr"]')
                descr = props[0].get('descr', '') if props else ''
                if descr == 'report-gen:severity-chart': continue
                for blip in picture.findall('.//'+A+'blip'):
                    target = relationships.get(blip.get(R+'embed'), '')
                    member = posixpath.normpath(posixpath.join('word', target))
                    if not member.startswith('word/media/'): raise ValueError(backend_message('Imagen Word fuera del paquete'))
                    images.append(dict(sha256=sha256(package.read(member)).hexdigest(),caption=caption(descr),code_index=codes,preceding_text=prefixes[picture]))
        # Older Word layouts and ordinary machine metadata use native tables.
        if node.tag == W+'tbl':
            for row in node.findall('./'+W+'tr'):
                cells = row.findall('./'+W+'tc')
                if len(cells)==2: fields.append([normal(_word_text(c)) for c in cells])
    return dict(fields=fields,severity=severity,links=links,images=images)


def check(scope, actual, fmt):
    expected = scope['semantic']
    for field in expected['fields']:
        if field not in actual['fields']:
            raise ValueError(backend_message('Metadato alterado ({p0}: {p1}) / Metadata changed', p0=scope['id'] or 'informe', p1=field[0]))
    if scope['id'] and expected['severity'] != actual['severity']:
        raise ValueError(backend_message('Severidad alterada ({p0}) / Severity changed', p0=scope['id']))
    links = expected['links']
    if fmt == 'docx':
        from exporters.navigation import reference_name
        links = [[label, '#'+reference_name(target[1:]) if target.startswith('#') else target] for label,target in links]
    if links != actual['links']:
        raise ValueError(backend_message('Destino u orden de enlaces alterado ({p0}) / Links changed', p0=scope['id'] or 'informe'))
    images_ok=len(expected['images'])==len(actual['images'])
    for wanted,found in zip(expected['images'],actual['images']):
        digest = wanted.get('docx_sha256', wanted['sha256']) if fmt == 'docx' else wanted['sha256']
        images_ok=images_ok and digest==found['sha256'] and all(wanted[k]==found[k] for k in ('caption','code_index'))
        images_ok=images_ok and found['preceding_text'].endswith(wanted['preceding_text'])
    if not images_ok:
        raise ValueError(backend_message('Asociación de evidencia alterada ({p0}) / Evidence placement changed', p0=scope['id'] or 'informe'))
    return len(expected['fields'])+bool(expected['severity']),len(links),len(expected['images'])
