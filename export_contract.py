"""Inspect visible export content. Structured formats preserve literal code per finding.

PDF extraction is a textual presence check, never a proof of literal whitespace,
block association or pixel layout. Its limitations travel with the check record.
"""
from error_messages import current_language, message as backend_message
from collections import Counter
from copy import deepcopy
import re
import unicodedata
import zipfile
from threading import Lock
from lxml import etree, html

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W = '{' + NS['w'] + '}'
# PDFium calls in one process must not run concurrently. Release all native
# objects inside this lock, including when extraction raises.
_PDFIUM_LOCK = Lock()
_PDF_CODE_MAX_STATES = 4096
_PDF_CODE_MAX_RANGES = 1_000_000
_PDF_TEXT_MAX_STATES = 4096
_PDF_TEXT_MAX_RANGES = 1_000_000


def normal(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', text).replace('\u00ad', '')).strip()


def literal(text):
    # XML and HTML normalize line endings; spaces, tabs and Unicode stay literal.
    return text.replace('\r\n', '\n').replace('\r', '\n')


def has_class(node, name):
    return name in (node.get('class') or '').split()


def list_lead(node):
    parts = [node.text or '']
    for child in node:
        if child.tag in ('ul', 'ol', 'pre', 'table'): break
        parts.append(child.text_content())
        parts.append(child.tail or '')
        if child.tag == 'p': break
    return normal(''.join(parts))


def _list_figure_parts(node):
    """Retain authored block boundaries in this list's lead only."""
    from export_semantics import _figure_link_parts
    lead = html.Element('div')
    lead.text = node.text
    for child in node:
        if child.tag in ('ul', 'ol', 'pre', 'table'): break
        lead.append(deepcopy(child))
        if child.tag == 'p': break
    parts = _figure_link_parts(lead)
    if parts and normal(''.join(part['text'] for part in parts)) == list_lead(node):
        return dict(label=list_lead(node), parts=parts)
    return None


def _code(node, markdown=False):
    text = literal(node.text_content())
    # A fenced Markdown block has one syntactic terminal newline. Commands
    # have class cmd in HTML and an additional framing newline in Markdown.
    return text.removesuffix('\n') if markdown or not has_class(node, 'cmd') else text


def _dom_paragraph_nodes(root):
    # A linked figure's caption belongs to its hyperlink/paragraph, including
    # inline walkthroughs without a p wrapper. Its exact caption is independently
    # bound to the image and destination by the semantic checks.
    return [n for n in root.xpath('.//p|.//figcaption')
            if not n.xpath('ancestor::pre')
            and not (n.tag == 'figcaption' and n.xpath('ancestor::p|ancestor::a'))]


def _paragraph_text(node):
    # A figure is a block even when a Markdown link surrounds it without
    # source spaces. Word must put the surrounding prose in separate visible
    # paragraphs. Preserve that block boundary in paragraph units only; link
    # labels and the DOM itself remain unchanged and are checked separately.
    parts = [node.text or '']
    for child in node:
        if not isinstance(child.tag, str):
            pass  # Comment text is not part of the visible paragraph.
        elif child.tag == 'figure':
            parts.extend(('\n', _paragraph_text(child), '\n'))
        else:
            parts.append(_paragraph_text(child))
        parts.append(child.tail or '')
    return ''.join(parts)


def _dom_units(root, markdown=False):
    from export_numbering import dom_markers
    markers = dom_markers(root)
    paragraphs = [normal(_paragraph_text(n)) for n in _dom_paragraph_nodes(root)
                  if normal(_paragraph_text(n))]
    # Actual paragraph order is used below, with block boundaries retained as spaces.
    text = normal(root.text_content())
    codes = [_code(n, markdown) for n in root.xpath('.//pre')]
    rows = [[normal(cell.text_content()) for cell in row if cell.tag in ('td', 'th')]
            for row in root.xpath('.//tr')]
    tables = [[[normal(cell.text_content()) for cell in row if cell.tag in ('td', 'th')]
               for row in table.xpath('./tr|./thead/tr|./tbody/tr|./tfoot/tr')]
              for table in root.xpath('.//table')]
    return dict(text=text, paragraphs=paragraphs, codes=codes, table_rows=rows, tables=tables,
                headings=[normal(n.text_content()) for n in root.xpath('.//h1|.//h2|.//h3|.//h4|.//h5|.//h6')
                          if (n.get('data-rg-anchor') is None if markdown else n.get('data-rg-authored-heading') == 'true')],
                list_items=[list_lead(n) for n in root.xpath('.//li')],
                list_markers=[markers.get(n) for n in root.xpath('.//li')])


def _clean(root):
    root = deepcopy(root)
    for node in root.xpath('.//br'):
        node.tail='\n'+(node.tail or '')
    for node in list(root.xpath('.//script|.//style')):
        node.drop_tree()
    for node in list(root.xpath('.//*')):
        if node.getparent() is not None and any(has_class(node, c) for c in ('cover', 'toc', 'c-pg')):
            node.drop_tree()
    return root


def _dom_scopes(tree, expected=None, markdown=False):
    root = _clean(tree)
    scopes = {}
    if not markdown:
        for node in list(root.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," finding ")]')):
            key = node.get('id')
            if not key or key in scopes: raise ValueError(backend_message('Identidad de hallazgo ausente o duplicada / Missing or duplicate finding identity'))
            scopes[key] = node
        global_root = deepcopy(root)
        for node in list(global_root.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," finding ")]')):
            node.drop_tree()
        scopes[''] = global_root
    else:
        scopes[''] = html.Element('div')
        headings = {s['id']: {normal(s['id'] + ' ' + s['title'])}
                    for s in expected.get('scopes', []) if s['id']}
        # With no authored title, HTML uses the existing finding identity as its
        # accessible label while Markdown's heading already carries that ID.
        for scope in expected.get('scopes', []):
            if scope['id'] and scope['title'] == scope['id']:
                headings[scope['id']].add(normal(scope['id']))
        current = ''
        for node in root:
            title = normal(node.text_content())
            anchor = node.get('data-rg-anchor')
            if node.tag == 'h3' and anchor in headings and title in headings[anchor]:
                current = anchor
                if current in scopes: raise ValueError(backend_message('Hallazgo ambiguo en Markdown / Ambiguous Markdown finding'))
                scopes[current] = html.Element('div')
            elif node.tag in ('h1', 'h2') and anchor is not None:
                current = ''
            scopes[current].append(deepcopy(node))
    return scopes


def _cover_units(tree):
    covers=tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," cover ")]')
    if not covers:return []
    cover=covers[0];values=[]
    for node in cover.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," cv-title ") or contains(concat(" ",normalize-space(@class)," ")," cv-subtitle ")]'):
        values.append(normal(node.text_content()))
    for row in cover.xpath('.//table[contains(@class,"cover-meta")]/tbody/tr'):
        if row.xpath('./th'):
            values.append(normal(' '.join(n.text_content() for n in row)))
        else:
            for cell in row:
                value=normal(' '.join(n.text_content() for n in cell))
                if value:values.append(value)
    return values


def from_tree(tree, image_digests=None, docx_image_digests=None):
    from export_semantics import dom
    import engine
    severity_label = engine.load_lang(tree.get("lang", "es"))["labels"]["col_sev"]
    image_digests = image_digests or {}
    from urllib.parse import unquote
    scopes = []
    for key, root in _dom_scopes(tree).items():
        titles = root.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," f-title ")]')
        units = _dom_units(root)
        rows = []; tables = []
        for table in root.xpath('.//table'):
            if has_class(table, 'meta') or has_class(table, 'hostbox'): continue
            table_rows = [[normal(cell.text_content()) for cell in row if cell.tag in ('th', 'td')]
                          for row in table.xpath('./tr|./thead/tr|./tbody/tr|./tfoot/tr')]
            rows += table_rows; tables.append(table_rows)
        lists = []
        for node in root.xpath('.//ol|.//ul'):
            if any(any(has_class(a, c) for c in ('steps', 'toc-list', 'toc'))
                   for a in [node, *node.iterancestors()]): continue
            items = [list_lead(x) for x in node if x.tag == 'li']
            if items and all(items): lists.append(items)
        # Individual list groups do not encode their position relative to
        # other lists. Retain DOM order too, including nested list items;
        # concatenating groups would place a parent's later sibling before
        # its nested children and reject a faithful nested procedure.
        authored_items = [node for node in root.xpath('.//li')
                          if not any(any(has_class(a, c) for c in ('steps', 'toc-list', 'toc'))
                                     for a in node.iterancestors())]
        list_sequence = [list_lead(node) for node in authored_items]
        from export_numbering import dom_markers
        markers = dom_markers(root)
        list_markers = [markers.get(node) for node in authored_items]
        list_figure_parts = [dict(parts, index=index) for index, node in enumerate(authored_items)
                             if (parts := _list_figure_parts(node))]
        semantic=dom(root, lambda src: image_digests[unquote(src)], severity_label=severity_label)
        for image in semantic['images']:
            image['docx_sha256'] = (docx_image_digests or {}).get(image['sha256'], image['sha256'])
        scopes.append(dict(id=key, semantic=semantic, title=normal(titles[0].text_content()) if titles else '',
                           headings=[normal(n.text_content()) for n in root.xpath('.//*[@data-rg-authored-heading="true"]')],
                           paragraphs=units['paragraphs'], paragraphs_md=[normal(_paragraph_text(n)) for n in _dom_paragraph_nodes(root) if not has_class(n,'chart-scope') and normal(_paragraph_text(n))], codes=units['codes'], table_rows=rows, tables=tables, lists=lists, list_sequence=list_sequence,
                           list_figure_parts=list_figure_parts, list_markers=list_markers))
    return dict(version=3, scopes=scopes, severity_label=severity_label, cover_units=_cover_units(tree),
                titles=[s['title'] for s in scopes if s['id']],
                code_lines=[line for s in scopes for code in s['codes'] for line in code.splitlines() if line],
                table_rows=[row for s in scopes for row in s['table_rows']],
                lists=[items for s in scopes for items in s['lists']])


def _word_text(node):
    parts = []
    for child in node.iter():
        if any(a.tag in (W+'pPr', W+'rPr') for a in child.iterancestors()): continue
        if any(run.find('./' + W + 'rPr/' + W + 'vanish') is not None
               for run in child.iterancestors(W + 'r')): continue
        if child.tag == W + 't': parts.append(child.text or '')
        elif child.tag == W + 'tab': parts.append('\t')
        elif child.tag in (W + 'br', W + 'cr'): parts.append('\n')
    return ''.join(parts)


def _word_numbered(paragraph):
    return bool(paragraph.xpath('./w:pPr/w:numPr|./w:pPr/w:pStyle[starts-with(@w:val,"List")]', namespaces=NS))


def _word_list_flows(paragraphs):
    """Observe physical siblings; never bridge another item, table or scope."""
    allowed = set(paragraphs)
    flows = []
    for first in paragraphs:
        if not _word_numbered(first): continue
        records = []; paragraph = first
        while (paragraph is not None and paragraph.tag == W+'p' and paragraph in allowed
               and (paragraph is first or not _word_numbered(paragraph))):
            style = paragraph.find('./'+W+'pPr/'+W+'pStyle')
            records.append(dict(text=normal(_word_text(paragraph)),
                                style=style.get(W+'val', '') if style is not None else '',
                                images=len(paragraph.xpath('.//w:drawing', namespaces=NS))))
            paragraph = paragraph.getnext()
        flows.append(records)
    return flows


def _word_figure_list_matches(parts, flow):
    cursor = 0
    for part in parts:
        if cursor >= len(flow): return False
        record = flow[cursor]
        if part['kind'] == 'figure':
            # The numbered paragraph may itself contain the first drawing.
            # Every caption must immediately follow its own drawing, with no
            # intervening prose or list marker. Images/links have their own
            # digest, destination and order checks in export_semantics.
            if record['text'] or record['images'] != 1: return False
            cursor += 1
            if cursor >= len(flow): return False
            record = flow[cursor]
            if record['style'] != 'Caption' or record['images']: return False
        elif part['kind'] != 'text' or record['images'] or record['style'] == 'Caption':
            return False
        if record['text'] != normal(part['text']): return False
        cursor += 1
    return True


def _word_list_items(scope, actual):
    """Verify a source-defined block lead, without joining ordinary list items."""
    items = list(actual['list_items'])
    for index, flow in enumerate(actual.get('list_flows', [])):
        for source in scope.get('list_figure_parts', []):
            parts = source['parts']
            if (normal(''.join(part['text'] for part in parts)) == source['label']
                    and _word_figure_list_matches(parts, flow)):
                # Each observed fragment has already matched exactly, and the
                # source supplies only its authored inter-block boundaries.
                items[index] = source['label']
                break
    return items


def _word_cover_units(cover):
    if cover is None: return []
    units = []
    title = cover.xpath('.//w:p[w:pPr/w:pStyle[@w:val="Title"]]', namespaces=NS)
    if title:
        units.append(normal(_word_text(title[0])))
        subtitle = title[0].getnext()
        if subtitle is not None and subtitle.tag == W+'p' and normal(_word_text(subtitle)):
            units.append(normal(_word_text(subtitle)))
    # Only the lower cover zone holds metadata. A long brand/classification
    # may use its own nested header table, which is not a label/value ledger.
    for table in cover.xpath('./w:tr[last()]/w:tc[last()]/w:tbl', namespaces=NS):
        for row in table.findall('./'+W+'tr'):
            cells = [[normal(_word_text(p)) for p in cell.findall('./'+W+'p')]
                     for cell in row.findall('./'+W+'tc')]
            # Grid metadata puts each label/value pair in one cell; ledger
            # metadata uses one row for the pair. Preserve full unit boundaries.
            if any(len(values) > 1 for values in cells):
                units.extend(normal(' '.join(values)) for values in cells if any(values))
            else:
                unit = normal(' '.join(value for values in cells for value in values))
                if unit: units.append(unit)
    return units


def _word_scopes(path, expected):
    from exporters.navigation import reference_name
    with zipfile.ZipFile(path) as package:
        tree = etree.fromstring(package.read('word/document.xml'), parser=etree.XMLParser(resolve_entities=False, no_network=True))
        blobs={n:package.read(n) for n in package.namelist() if n.startswith('word/media/') or n=='word/_rels/document.xml.rels'}
        from export_numbering import word_markers
        numbering = etree.fromstring(package.read('word/numbering.xml'), parser=etree.XMLParser(resolve_entities=False, no_network=True))
        markers = word_markers(tree, numbering)
    names = {reference_name(s['id']): s['id'] for s in expected['scopes'] if s['id']}
    groups = {'': []}; current = ''
    for node in tree.find(W + 'body'):
        if node.tag == W + 'sdt': continue  # Native table of contents, not the finding body.
        bookmarks = node.xpath('./w:bookmarkStart/@w:name', namespaces=NS)
        matches = [names[name] for name in bookmarks if name in names]
        if matches:
            if len(matches) != 1 or matches[0] in groups: raise ValueError(backend_message('Hallazgo ambiguo en Word / Ambiguous Word finding'))
            current = matches[0]; groups[current] = []
        elif (node.xpath('./w:pPr/w:pStyle[@w:val="Heading1"]', namespaces=NS)
              and any(name.startswith('rg_toc_') for name in bookmarks)):
            # Only generated section headings have native TOC bookmarks.
            # A user's # heading retains its current finding association.
            current = ''
        groups[current].append(node)
    profiles = {}
    for key, nodes in groups.items():
        paras = [p for node in nodes for p in ([node] if node.tag == W + 'p' else node.findall('.//' + W + 'p'))]
        rows = [[normal(_word_text(cell)) for cell in row.findall('./' + W + 'tc')]
                for node in nodes for row in node.findall('.//' + W + 'tr')]
        tables = [[[normal(_word_text(cell)) for cell in row.findall('./' + W + 'tc')]
                   for row in table.findall('./' + W + 'tr')]
                  for node in nodes for table in node.iter(W + 'tbl')]
        from export_semantics import word
        class Parts:
            def read(self,name): return blobs[name]
        semantic=word(nodes,Parts())
        profiles[key] = dict(semantic=semantic, text=normal(' '.join(_word_text(p) for p in paras)),
            headings=[normal(_word_text(p)) for p in paras
                      if p.xpath('./w:pPr/w:pStyle[starts-with(@w:val,"Heading")]', namespaces=NS)
                      and not p.findall('./' + W + 'bookmarkStart')],
            codes=[literal(_word_text(p)) for p in paras if p.xpath('./w:pPr/w:pStyle[@w:val="ReportGenCode"]', namespaces=NS)],
            paragraphs=[normal(_word_text(p)) for p in paras], table_rows=rows, tables=tables,
            list_items=[normal(_word_text(p)) for p in paras if _word_numbered(p)],
            list_markers=[markers.get(p) for p in paras if _word_numbered(p)],
            list_flows=_word_list_flows(paras))
    cover=tree.find(W+'body/'+W+'tbl')
    profiles['']['cover_text']=normal(' '.join(_word_text(p) for p in cover.findall('.//'+W+'p'))) if cover is not None else ''
    profiles['']['cover_units'] = _word_cover_units(cover)
    return profiles


def _pdf_hyphen_donor(page, reader):
    """Read fixed-width source codes through their explicit ToUnicode map.

    This deliberately small subset is only a corroborating reader for PDFium
    hyphen markers. It never supplies spaces or replaces the primary text.
    Unsupported mappings retain the explicit ambiguous-extraction rejection.
    """
    from pypdf.generic import (ByteStringObject, ContentStream, NameObject,
                               StreamObject, TextStringObject)

    def resolved(value):
        return value.get_object() if hasattr(value, 'get_object') else value

    def codespace(stream):
        data = re.sub(rb'%[^\r\n]*', b'', stream.get_data())
        if '/UseCMap' in stream or re.search(rb'\busecmap\b', data):
            raise ValueError(backend_message('No se puede corroborar el CMap heredado',
                                             en='Inherited CMap is not corroborated'))
        blocks = re.findall(rb'\b(\d+)\s+begincodespacerange\s*(.*?)\s*endcodespacerange\b', data, re.S)
        pair = (re.fullmatch(rb'\s*<([\da-fA-F]{4})>\s*<([\da-fA-F]{4})>\s*', blocks[0][1])
                if len(blocks) == 1 and int(blocks[0][0]) == 1 else None)
        if pair is None:
            raise ValueError(backend_message('El CMap no usa códigos fijos de dos bytes',
                                             en='CMap is not fixed two-byte'))
        lo, hi = (int(value, 16) for value in pair.groups())
        if lo > hi:
            raise ValueError(backend_message('Intervalo de códigos inválido', en='Invalid codespace'))
        return lo, hi, data

    resources = resolved(page.get('/Resources', {}))
    for ref in resolved(resources.get('/XObject', {})).values():
        if resolved(ref).get('/Subtype') != '/Image':
            raise ValueError(backend_message('No se puede corroborar el texto del objeto Form',
                                             en='Form text is not corroborated'))
    mappings = {}
    fonts = {}
    for name, ref in resolved(resources.get('/Font', {})).items():
        font = resolved(ref)
        if font.get('/Subtype') != '/Type0':
            raise ValueError(backend_message('La fuente no es Type0', en='Font is not Type0'))
        encoding = resolved(font.get('/Encoding'))
        if isinstance(encoding, StreamObject):
            lo, hi, data = codespace(encoding)
            if encoding.get('/WMode', 0) != 0 or re.search(rb'/WMode\s+1\b', data):
                raise ValueError(backend_message('No se puede corroborar la codificación vertical',
                                                 en='Vertical encoding is not corroborated'))
        elif encoding == '/Identity-H':
            lo, hi = 0, 65535
        else:
            raise ValueError(backend_message('No se puede corroborar la codificación con nombre',
                                             en='Named encoding is not corroborated'))
        unicode_map = resolved(font.get('/ToUnicode'))
        if not isinstance(unicode_map, StreamObject):
            raise ValueError(backend_message('Falta el mapa ToUnicode', en='Missing ToUnicode map'))
        tlo, thi, data = codespace(unicode_map)
        if b'beginbfrange' in data:
            raise ValueError(backend_message('No se pueden corroborar las asignaciones por intervalos',
                                             en='Range mappings are not corroborated'))
        mapping = {}
        for count, block in re.findall(rb'\b(\d+)\s+beginbfchar\s*(.*?)\s*endbfchar\b', data, re.S):
            pair_pattern = rb'<([\da-fA-F]{4})>\s*<([\da-fA-F]+)>'
            pairs = re.findall(pair_pattern, block)
            if re.sub(pair_pattern, b'', block).strip() or int(count) != len(pairs):
                raise ValueError(backend_message('Asignación Unicode mal formada',
                                                 en='Malformed Unicode mapping'))
            for code, value in pairs:
                code = int(code, 16)
                if code in mapping or not (lo <= code <= hi and tlo <= code <= thi):
                    raise ValueError(backend_message('Asignación Unicode ambigua',
                                                     en='Ambiguous Unicode mapping'))
                mapping[code] = bytes.fromhex(value.decode('ascii')).decode('utf-16-be', errors='strict')
        if not mapping:
            raise ValueError(backend_message('Asignación explícita vacía', en='Empty explicit mapping'))
        mappings[name] = mapping
        fonts[id(font)] = font
    selected = None
    stack = []
    for operands, operator in ContentStream(page.get_contents(), reader).operations:
        if operator == b'q':
            stack.append(selected)
        elif operator == b'Q':
            if not stack:
                raise ValueError(backend_message('Estado gráfico desequilibrado',
                                                 en='Unbalanced graphics state'))
            selected = stack.pop()
        elif operator == b'Tf':
            selected = operands[0]
        elif operator in (b'TJ', b'Tj', b"'", b'"'):
            values = operands[0] if operator == b'TJ' else [operands[-1]]
            for value in values:
                if not isinstance(value, (ByteStringObject, TextStringObject)):
                    continue
                blob = value.original_bytes if isinstance(value, TextStringObject) else bytes(value)
                if len(blob) % 2 or selected not in mappings:
                    raise ValueError(backend_message('Codificación de texto sin corroborar',
                                                     en='Unproved text encoding'))
                if any(int.from_bytes(blob[i:i+2], 'big') not in mappings[selected] for i in range(0, len(blob), 2)):
                    raise ValueError(backend_message('El código fuente no tiene una asignación Unicode explícita',
                                                     en='Source code missing explicit Unicode mapping'))
    # Only the reader-local decoding width changes. ToUnicode remains intact:
    # source character codes need not equal CIDs (non-identity CMaps work too).
    originals = [(font, font.get('/Encoding')) for font in fonts.values()]
    try:
        for font, _ in originals:
            font[NameObject('/Encoding')] = NameObject('/Identity-H')
        return unicodedata.normalize('NFC', page.extract_text() or '')
    finally:
        for font, encoding in originals:
            font[NameObject('/Encoding')] = encoding


def _pdf_proved_hyphens(page, reader, textpage, primary):
    """Recover only a real ASCII hyphen corroborated by independent PDF text."""
    import pypdfium2.raw as raw
    chars = [raw.FPDFText_GetUnicode(textpage, i) for i in range(textpage.count_chars())]
    if ''.join(map(chr, chars)) != primary or '\ufffe' in primary:
        raise ValueError(backend_message('La secuencia nativa de caracteres difiere',
                                         en='Native character sequence differs'))
    for index, char in enumerate(chars):
        if char == 2 and (raw.FPDFText_IsHyphen(textpage, index) != 1
                          or raw.FPDFText_HasUnicodeMapError(textpage, index) != 0):
            raise ValueError(backend_message('El marcador no tiene corroboración nativa de guion',
                                             en='Marker lacks native hyphen proof'))
    donor = [char for char in _pdf_hyphen_donor(page, reader) if not char.isspace()]
    primary = unicodedata.normalize('NFC', primary)
    actual = [char for char in primary if not char.isspace()]
    if len(actual) != len(donor) or any(a != b and not (a == '\x02' and b == '-') for a, b in zip(actual, donor)):
        raise ValueError(backend_message('El texto PDF independiente difiere',
                                         en='Independent PDF text diverges'))
    confirmed = iter(donor)
    result = []
    for char in primary:
        if char.isspace():
            result.append(char)
        else:
            mapped = next(confirmed)
            result.append(mapped if char == '\x02' else char)
    return ''.join(result)


def pdf_text_pages(source, *, geometry_pages=()):
    """Read the PDF, retaining the established extractor for ordinary fonts.

    PDFium dehyphenates both hard and soft hyphens to the same marker. Recover
    an ASCII hyphen only when native metadata and an independent, strictly
    mapped PDF text sequence corroborate it. Never infer from expected text.
    """
    from io import BytesIO
    from pypdf import PdfReader
    from pypdf.generic import StreamObject

    def resolved(value):
        return value.get_object() if hasattr(value, 'get_object') else value

    def custom_cmap(resources, seen):
        resources = resolved(resources)
        if id(resources) in seen:
            return False
        seen.add(id(resources))
        for font in resolved(resources.get('/Font', {})).values():
            encoding = font.get_object().get('/Encoding')
            if encoding is not None and isinstance(encoding.get_object(), StreamObject):
                return True
        for obj in resolved(resources.get('/XObject', {})).values():
            nested = obj.get_object().get('/Resources')
            if nested is not None and custom_cmap(nested, seen):
                return True
        return False

    reader = PdfReader(BytesIO(source) if isinstance(source, bytes) else source)
    raw_pages = []
    alternate = []
    for index, page in enumerate(reader.pages):
        special = index in geometry_pages or custom_cmap(page.get('/Resources', {}), set())
        text = '' if special else page.extract_text() or ''
        if special or any(unicodedata.bidirectional(char) in ('R', 'AL') for char in text):
            alternate.append(index)
        raw_pages.append(text)
    if alternate:
        import pypdfium2
        with _PDFIUM_LOCK, pypdfium2.PdfDocument(source) as document:
            for index in alternate:
                page = document[index]
                try:
                    textpage = page.get_textpage()
                    try:
                        # Bounded extraction supports full Unicode (unlike
                        # UCS-2 range extraction), custom font CMaps and logical
                        # RTL order. Read only the file, never expected content.
                        text = textpage.get_text_bounded(errors='strict')
                        if '\x02' in text or '\ufffe' in text:
                            try:
                                text = _pdf_proved_hyphens(reader.pages[index], reader, textpage, text)
                            except (ValueError, TypeError, AttributeError, KeyError, IndexError):
                                pass  # Keep the marker and fail safely below.
                    finally:
                        textpage.close()
                finally:
                    page.close()
                if '\x02' in text or '\ufffe' in text:
                    raise ValueError(backend_message(
                        'Extracción PDF ambigua en un guion partido de la página {page}. '
                        'Ajusta el ancho o el salto de línea de ese texto y vuelve a exportar. '
                        'La salida anterior se conserva.',
                        en='Ambiguous PDF text extraction at a wrapped hyphen on page {page}. '
                           'Adjust the width or line break of that text and export again. '
                           'The previous output is preserved.', page=index + 1))
                raw_pages[index] = text
    return [unicodedata.normalize('NFC', text).replace('\u00ad', '') for text in raw_pages]


def _profiles(path, fmt, expected):
    if fmt == 'pdf':
        # The generated cover is the first page. Its title/subtitle can be
        # separate visible blocks that pypdf concatenates without a space.
        # Use PDFium's actual geometric text boundaries there, not separators
        # reconstructed from any expected metadata values.
        raw_pages = pdf_text_pages(path, geometry_pages=(0,) if expected.get('cover_units') else ())
        pages = [normal(text) for text in raw_pages]
        return {'': dict(text=normal(' '.join(pages)), pages=pages,
                         line_edges=[_pdf_line_edges(text) for text in raw_pages],
                         cover_text=pages[0] if pages else '',
                         raw_text='\n'.join(raw_pages), codes=[], table_rows=[], list_items=[])}
    if fmt == 'docx': return _word_scopes(path, expected)
    from export_semantics import dom, html_digest, visible_copy
    if fmt == 'md':
        from exporters.markdown import parse_exported
        from resources import relative_image
        from hashlib import sha256
        with zipfile.ZipFile(path) as package:
            tree = parse_exported(package.read('report.md').decode())
            digests={n:sha256(package.read(n)).hexdigest() for n in package.namelist() if n!='report.md'}
        image_digest=lambda src:digests[relative_image(src).as_posix()]
        cover=html.Element('div')
        for n in tree:
            if n.tag=='h2': break
            cover.append(deepcopy(n))
        for label in cover.xpath('.//li/strong'):
            if label.text and label.text.endswith(':'): label.text=label.text[:-1]
        cover_text=normal(cover.text_content())
        cover_units = [normal(n.text_content()) for n in cover if n.tag == 'h1']
        title = cover.find('h1')
        subtitle = title.getnext() if title is not None else None
        if subtitle is not None and subtitle.tag == 'p' and subtitle.find('em') is not None:
            cover_units.append(normal(subtitle.text_content()))
        cover_units.extend(normal(n.text_content()) for n in cover.xpath('.//li'))
        for _ in range(len(cover)): tree.remove(tree[0])
    else:
        tree = visible_copy(html.document_fromstring(path.read_text(encoding='utf-8')))
        cover=tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," cover ")]')
        cover_text=' '.join(_cover_units(tree)) if cover else ''
        cover_units = _cover_units(tree)
        mains=tree.xpath('//main')
        if not mains: raise ValueError(backend_message('Informe oculto o ausente / Report hidden or missing'))
        tree=mains[0]
        image_digest=html_digest
    result={}
    for key,root in _dom_scopes(tree,expected,fmt=='md').items():
        result[key]=_dom_units(root,fmt=='md')
        result[key]['semantic']=dom(root,image_digest,fmt=='md',expected.get('severity_label', 'Severidad'))
    result['']['cover_text']=cover_text
    result['']['cover_units']=cover_units
    return result


def profile(path, fmt, expected=None):
    scopes = _profiles(path, fmt, expected or {'scopes': []})
    if expected is not None: return scopes
    return dict(text=normal(' '.join(row['text'] for row in scopes.values())),
                table_rows=[x for row in scopes.values() for x in row['table_rows']],
                list_items=[x for row in scopes.values() for x in row['list_items']])


def _ordered(units, text, what):
    cursor = 0
    for unit in units:
        where = text.find(unit, cursor)
        if where < 0: raise ValueError(backend_message('{p0} ausente o alterado / Missing or changed content', p0=what))
        cursor = where + len(unit)


def _paragraphs(units, paragraphs, scope):
    actual=[p for p in paragraphs if p];cursor=0
    for unit in units:
        found=None
        for start in range(cursor,len(actual)):
            combined=''
            for end in range(start,len(actual)):
                combined+=(' ' if combined else '')+actual[end]
                if combined==unit:found=end+1;break
                if len(combined)>=len(unit):break
            if found is not None:break
        if found is None:raise ValueError(backend_message('Párrafo ({p0}) ausente o alterado / Missing or changed paragraph', p0=scope or 'informe'))
        cursor=found


def _pdf_pattern(unit):
    # A PDF extractor may insert spaces inside a wrapped word/URL or next to
    # inline spans. Source whitespace remains REQUIRED. This is presence only;
    # inserted whitespace is not certified as a faithful literal rendering.
    unit = normal(unit)
    words = unit.split(' ')
    # "Approved" must not be supplied by "NotApproved", in prose, cells or
    # metadata. These word edges do not prove paragraph/table ownership.
    before = r'(?<!\w)' if unit and re.match(r'\w', unit[0]) else ''
    after = r'(?!\w)' if unit and re.match(r'\w', unit[-1]) else ''
    pattern = r'\s+'.join(r'\s*'.join(re.escape(c) for c in word) for word in words)
    return re.compile(before + pattern + after)


def _pdf_line_edges(text):
    """Map extractor line breaks to normalized offsets using only PDF text."""
    text = unicodedata.normalize('NFC', text).replace('\u00ad', '')
    words = list(re.finditer(r'\S+', text))
    starts, ends = set(), set()
    offset = 0
    breaks = '\r\n\f\v\x85\u2028\u2029'
    for index, word in enumerate(words):
        previous = words[index - 1].end() if index else 0
        following = words[index + 1].start() if index + 1 < len(words) else len(text)
        if index == 0 or any(char in breaks for char in text[previous:word.start()]):
            starts.add(offset)
        offset += len(word.group())
        if index + 1 == len(words) or any(char in breaks for char in text[word.end():following]):
            ends.add(offset)
        offset += 1  # The single whitespace produced by normal().
    return {'starts': starts, 'ends': ends}


def _pdf_uri_page_fragments(unit, pages, line_edges, budget):
    """Match literal-URI continuations at retained extractor line boundaries.

    Ordinary prose words remain indivisible across pages. Only a URI may
    continue within a word, from a line end to a line start on the immediately
    following page. This is bounded textual presence, not block association,
    copyable-whitespace verification or a geometric layout certificate.
    Every accepted character is read from the PDF; source text is never used
    to repair extraction. Actual non-reusable ranges go to the same allocator.
    """
    from bisect import bisect_left
    unit = normal(unit)
    uris = list(re.finditer(r"\b(?:https?|ftps?)://[^\s<>\"'`]+", unit, re.IGNORECASE))
    if not uris or len(line_edges) != len(pages):
        return []
    budget(len(unit))
    uri_starts = [match.start() for match in uris]

    def in_uri(offset):
        index = bisect_left(uri_starts, offset) - 1
        return index >= 0 and offset < uris[index].end()

    def word_char(char):
        return bool(re.match(r'\w', char))

    def fragments(first, page, edges):
        within_uri = in_uri(first)
        starts = (sorted(edges['starts']) if within_uri else
                  (match.start() for match in re.finditer(re.escape(unit[first]), page)))
        for start in starts:
            budget(1)
            if start >= len(page) or page[start] != unit[first]:
                continue
            if (not within_uri and word_char(unit[first]) and start > 0
                    and word_char(page[start - 1])):
                continue
            source, actual = first, start
            while source < len(unit) and actual < len(page):
                budget(1)
                if unit[source].isspace():
                    if not page[actual].isspace():
                        break  # Authored whitespace is required, as in _pdf_pattern.
                    source += 1
                    while actual < len(page) and page[actual].isspace():
                        actual += 1
                    continue
                while actual < len(page) and page[actual].isspace():
                    actual += 1  # Extractor line/span spacing inside a source word.
                if actual == len(page) or page[actual] != unit[source]:
                    break
                source += 1
                actual += 1
                boundary = (not word_char(unit[source - 1]) or actual == len(page)
                            or not word_char(page[actual]))
                if source == len(unit):
                    if boundary:
                        yield source, start, actual
                elif unit[source].isspace() and boundary:
                    yield source + 1, start, actual
                elif in_uri(source) and actual in edges['ends']:
                    yield source, start, actual

    carry, completed = {}, set()
    for number, (page, edges) in enumerate(zip(pages, line_edges)):
        progressed = {}
        states = 0
        for first, chains in {0: {()}, **carry}.items():
            for consumed, start, end in fragments(first, page, edges):
                for chain in chains:
                    budget(len(chain) + 1)
                    candidate = chain + ((number, start, end),)
                    if consumed == len(unit):
                        completed.add(candidate)
                    else:
                        target = progressed.setdefault(consumed, set())
                        if candidate not in target:
                            if states >= _PDF_TEXT_MAX_STATES:
                                _pdf_text_check_incomplete()
                            states += 1
                            target.add(candidate)
        carry = progressed  # A chain cannot skip an empty/unmatched page.
    return sorted(completed)


def _pdf_occurrences(unit, pages, *, alternatives=False):
    """Count text chains using real, non-reusable ranges on adjacent pages.

    Headers/footers can interrupt a paragraph. Consume the longest verified
    source-word prefix on each consecutive page, retaining alternate starts.
    This is global textual presence, not a proof of block association.
    """
    if alternatives:
        return _pdf_text_fragments(unit, pages, prefixes=True)
    from functools import lru_cache
    words = normal(unit).split()
    if not words:
        return []

    @lru_cache(maxsize=2048)
    def pattern(first, size):
        return _pdf_pattern(' '.join(words[first:first + size]))

    def longest(first, page, start):
        lo, hi, best = 1, len(words) - first, None
        while lo <= hi:
            size = (lo + hi) // 2
            match = pattern(first, size).search(page, start)
            if match is not None:
                best = size, match.span()
                lo = size + 1
            else:
                hi = size - 1
        return best

    candidates = []
    carry = {}
    for page_index, page in enumerate(pages):
        cursor = 0
        while True:
            progressed = {}
            completed = []
            for first, ranges in [(0, ()), *carry.items()]:
                fragment = longest(first, page, cursor)
                if fragment is None:
                    continue  # A chain cannot skip a page with no fragment.
                size, (start, end) = fragment
                next_ranges = ranges + ((page_index, start, end),)
                consumed = first + size
                if consumed == len(words):
                    completed.append(next_ranges)
                else:
                    previous = progressed.get(consumed)
                    if previous is None or (end, next_ranges[0]) < (previous[-1][2], previous[0]):
                        progressed[consumed] = next_ranges
            if not completed:
                carry = progressed
                break
            chosen = min(completed, key=lambda ranges: (ranges[-1][2], ranges[0]))
            candidates.append(chosen)
            cursor = chosen[-1][2]
            carry = {}

    # Preserve directly contiguous matches too, including a token physically
    # wrapped across a page with no intervening header/footer. Their offsets
    # are mapped back to pages and merged, never added as duplicate counts.
    offsets = []
    offset = 0
    for page in pages:
        offsets.append(offset)
        offset += len(page) + 1
    for match in _pdf_pattern(unit).finditer(' '.join(pages)):
        ranges = []
        for index, (page, offset) in enumerate(zip(pages, offsets)):
            start, end = max(match.start() - offset, 0), min(match.end() - offset, len(page))
            if end > start:
                ranges.append((index, start, end))
        if (ranges and all(pages[p][a:b].strip() for p, a, b in ranges)
                and all(b[0] == a[0] + 1 for a, b in zip(ranges, ranges[1:]))):
            candidates.append(tuple(ranges))
    found = []
    previous = (-1, 0)
    for ranges in sorted(set(candidates), key=lambda r: (r[-1][0], r[-1][2], r[0])):
        if (ranges[0][0], ranges[0][1]) >= previous:
            found.append(ranges)
            previous = ranges[-1][0], ranges[-1][2]
    return found


def _pdf_text_fragments(unit, pages, *, prefixes, budget=None):
    """Enumerate actual adjacent-page chains without discarding later starts.

    The maximal-prefix pass is a cheap constructive search. If it cannot
    supply a disjoint assignment, the exhaustive pass retains shorter prefixes
    too. Construction has a work limit before candidates enter the allocator.
    """
    words = normal(unit).split()
    if not words:
        return []
    examined = 0

    def consume(amount=1):
        nonlocal examined
        examined += amount
        if examined > _PDF_TEXT_MAX_RANGES:
            _pdf_text_check_incomplete()
        if budget is not None:
            budget(amount)

    patterns = [_pdf_pattern(word) for word in words]
    starts = [re.compile('(?=(' + pattern.pattern + '))') for pattern in patterns]
    carry = {}
    completed = set()
    for page_index, page in enumerate(pages):
        progressed = {}
        for first, chains in {0: {()}, **carry}.items():
            for match in starts[first].finditer(page):
                start, end = match.span(1)
                consumed = first + 1
                fragments = [(consumed, start, end)]
                while consumed < len(words) and end < len(page) and page[end].isspace():
                    following = end
                    while following < len(page) and page[following].isspace():
                        following += 1
                    next_word = patterns[consumed].match(page, following)
                    if next_word is None:
                        break
                    end = next_word.end()
                    consumed += 1
                    fragments.append((consumed, start, end))
                    consume()
                for consumed, start, end in fragments if prefixes else fragments[-1:]:
                    for chain in chains:
                        consume(len(chain) + 1)
                        candidate = chain + ((page_index, start, end),)
                        if consumed == len(words):
                            completed.add(candidate)
                        else:
                            progressed.setdefault(consumed, set()).add(candidate)
        carry = progressed
    return sorted(completed)


def _pdf_present(units, actual, label_es, label_en):
    """Require visible text occurrences, without claiming PDF block geometry."""
    counts = Counter(unit for unit in units if unit)
    across = {}
    options = []
    construction_work = 0

    def budget(amount):
        nonlocal construction_work
        construction_work += amount
        if construction_work > _PDF_TEXT_MAX_RANGES:
            _pdf_text_check_incomplete()

    offsets = []
    offset = 0
    for page in actual['pages']:
        offsets.append(offset)
        offset += len(page) + 1
    for unit, count in counts.items():
        pattern = re.compile('(?=(' + _pdf_pattern(unit).pattern + '))')
        ranges = set()
        for page_index, page in enumerate(actual['pages']):
            for match in pattern.finditer(page):
                budget(1)
                ranges.add(((page_index, *match.span(1)),))
        if len(ranges) < count:
            spanning = _pdf_occurrences(unit, actual['pages'])
            budget(sum(map(len, spanning)))
            ranges.update(spanning)
            across[unit] = sum(len(occurrence) > 1 for occurrence in spanning[:count])
        # Different source values may overlap too: one occurrence of
        # "Approved with conditions" cannot also supply a missing "Approved"
        # cell. Retain alternatives instead of making a greedy assignment.
        options.append(set(tuple((offsets[p] + start, offsets[p] + end)
                                 for p, start, end in occurrence)
                           for occurrence in ranges))

    def allocated():
        return _pdf_disjoint_text_ranges(tuple(counts.values()),
                                         tuple(tuple(sorted(ranges)) for ranges in options))

    if allocated():
        return sum(counts.values()), sum(across.values())
    # A fast constructive pass may omit the only compatible page continuation.
    # Failure is never proof of missing text until all bounded alternatives
    # have been considered, including shorter prefixes and later starts.
    for prefixes in (False, True):
        for unit, ranges in zip(counts, options):
            alternatives = _pdf_text_fragments(unit, actual['pages'], prefixes=prefixes, budget=budget)
            ranges.update(tuple((offsets[p] + start, offsets[p] + end)
                                for p, start, end in occurrence)
                          for occurrence in alternatives)
        if allocated():
            return sum(counts.values()), sum(across.values())
    if actual.get('line_edges'):
        for unit, ranges in zip(counts, options):
            continuations = _pdf_uri_page_fragments(
                unit, actual['pages'], actual['line_edges'], budget)
            ranges.update(tuple((offsets[p] + start, offsets[p] + end)
                                for p, start, end in occurrence)
                          for occurrence in continuations)
            # A later fallback can rediscover an already verified chain.
            # Count each source unit at most its authored multiplicity; this
            # is a continuation-check count, not a geometric paragraph count.
            across[unit] = max(across.get(unit, 0), sum(
                len(occurrence) > 1 for occurrence in continuations[:counts[unit]]))
        if allocated():
            return sum(counts.values()), sum(across.values())
    raise ValueError(backend_message(
        'Texto de {label} PDF ausente o alterado',
        en='Missing or changed PDF {label} text',
        label=label_en if current_language() == 'en' else label_es))


def _pdf_text_check_incomplete():
    raise ValueError(backend_message(
        'No se pudo completar la verificación PDF: apariciones de texto ambiguas. '
        'La salida no se considera verificada.',
        en='PDF verification could not be completed: ambiguous text occurrences. '
           'The output is not considered verified.'))


def _pdf_disjoint_text_ranges(needs, options):
    """Allocate actual text fragments, including interleaved page continuations.

    A candidate is a tuple of disjoint physical ranges. Gaps between its page
    fragments remain available to other cells/paragraphs, so no table geometry
    or association is inferred. Categories are checked separately because a
    paragraph inside a list legitimately belongs to both content categories.
    """
    from bisect import bisect_left
    from heapq import heappop, heappush
    examined = 0

    def budget(ranges=0, states=0):
        nonlocal examined
        examined += ranges
        if examined > _PDF_TEXT_MAX_RANGES or states > _PDF_TEXT_MAX_STATES:
            _pdf_text_check_incomplete()

    def overlaps(left, right):
        i = j = 0
        while i < len(left) and j < len(right):
            a, b = left[i], right[j]
            if a[0] < b[1] and b[0] < a[1]:
                return True
            if a[1] <= b[0]:
                i += 1
            else:
                j += 1
        return False

    def compatible_count(ranges):
        # A constructive lower bound, exact for single contiguous ranges.
        # With fragmented candidates it must never reject on its own.
        if all(len(candidate) == 1 for candidate in ranges):
            end = -1
            count = 0
            for candidate in sorted(ranges, key=lambda value: (value[0][1], value[0][0])):
                if candidate[0][0] >= end:
                    count += 1
                    end = candidate[0][1]
            return count
        chosen = []
        for candidate in sorted(ranges, key=lambda value: (value[-1][1], value[0][0])):
            budget(len(chosen) * len(candidate))
            if all(not overlaps(candidate, prior) for prior in chosen):
                chosen.append(candidate)
        return len(chosen)

    def reduce_state(needs, options):
        while needs:
            budget(sum(len(candidate) for ranges in options for candidate in ranges))
            lower = tuple(compatible_count(ranges) for ranges in options)
            if any(len(ranges) < need or (all(len(c) == 1 for c in ranges) and bound < need)
                   for need, ranges, bound in zip(needs, options, lower)):
                return None
            forced = {i for i, (need, ranges) in enumerate(zip(needs, options))
                      if need == len(ranges)}
            if forced:
                taken = sorted(span for i in forced for candidate in options[i]
                               for span in candidate)
                if any(left[1] > right[0] for left, right in zip(taken, taken[1:])):
                    return None
                starts = [span[0] for span in taken]

                def available(candidate):
                    for start, end in candidate:
                        previous = bisect_left(starts, end) - 1
                        if previous >= 0 and taken[previous][1] > start:
                            return False
                    return True

                options = tuple(tuple(candidate for candidate in ranges
                                      if available(candidate))
                                for i, ranges in enumerate(options) if i not in forced)
                needs = tuple(need for i, need in enumerate(needs) if i not in forced)
                continue
            active = Counter()
            ending = []
            competing = set()
            for start, end, kind in sorted((start, end, i) for i, ranges in enumerate(options)
                                          for candidate in ranges for start, end in candidate):
                while ending and ending[0][0] <= start:
                    _, expired = heappop(ending)
                    active[expired] -= 1
                    if not active[expired]:
                        del active[expired]
                others = active.keys() - {kind}
                if others:
                    competing.update(others)
                    competing.add(kind)
                active[kind] += 1
                heappush(ending, (end, kind))
            # An independent type can be discharged only with a constructive
            # non-overlapping set, never just its candidate count.
            competing.update(i for i, (need, bound) in enumerate(zip(needs, lower))
                             if bound < need)
            if len(competing) == len(needs):
                return needs, options
            needs = tuple(need for i, need in enumerate(needs) if i in competing)
            options = tuple(ranges for i, ranges in enumerate(options) if i in competing)
        return (), ()

    def branches(needs, options):
        kind = min(range(len(needs)), key=lambda i: len(options[i]) - needs[i])
        choices = sorted(options[kind], key=lambda candidate:
                         (sum(end - start for start, end in candidate), candidate))
        for index, taken in enumerate(choices):
            budget(sum(len(candidate) for ranges in options for candidate in ranges))
            next_needs = []
            next_options = []
            for i, (need, ranges) in enumerate(zip(needs, options)):
                if i == kind:
                    need -= 1
                    ranges = choices[index + 1:]
                if need:
                    next_needs.append(need)
                    next_options.append(tuple(candidate for candidate in ranges
                                              if not overlaps(candidate, taken)))
            yield tuple(next_needs), tuple(next_options)

    stack = [iter([(needs, options)])]
    seen = set()
    states = 0
    while stack:
        try:
            state = next(stack[-1])
        except StopIteration:
            stack.pop()
            continue
        if state in seen:
            continue
        states += 1
        budget(states=states)
        if len(seen) >= 2048:
            seen.clear()
        seen.add(state)
        state = reduce_state(*state)
        if state is None:
            continue
        if not state[0]:
            return True
        stack.append(branches(*state))
    return False


def _pdf_code_line_pattern(line):
    physical_wrap = r'(?:\r?\n[ \t]*)?'
    words = normal(line).split()
    body = r'\s+'.join(physical_wrap.join(re.escape(char) for char in word) for word in words)
    # A logical command occupies complete physical lines. Matching only an
    # interior substring would accept changed identifiers, option suffixes,
    # prefixes or an additional command on the same line.
    return re.compile(r'^[ \t]*' + body + r'[ \t]*\r?$', re.M)


def _pdf_code_multiplicity(codes, text):
    # Blocks may share individual lines. Count those lines globally so one
    # extracted occurrence cannot satisfy two different authored blocks.
    # Different logical lines can also compete for the same physical lines:
    # TOKEN\nAB cannot supply both TOKENAB and the separate TOKEN / AB lines.
    required = Counter(normal(line) for code in codes for line in code.splitlines() if normal(line))
    candidates = []
    candidate_count = 0
    for line in required:
        # Retain overlapping alternatives; a greedy finditer can discard the
        # only occurrence compatible with another requested logical line.
        pattern = re.compile('(?=(' + _pdf_code_line_pattern(line).pattern + '))', re.M)
        ranges = []
        for match in pattern.finditer(text):
            candidate_count += 1
            if candidate_count > _PDF_CODE_MAX_RANGES:
                _pdf_code_check_incomplete()
            ranges.append(match.span(1))
        candidates.append(tuple(ranges))
    if not _pdf_disjoint_code_ranges(tuple(required.values()), tuple(candidates)):
        raise ValueError(backend_message('Texto de código PDF ausente o alterado / Missing or changed PDF code text'))


def _pdf_code_check_incomplete():
    raise ValueError(backend_message(
        'No se pudo completar la verificación PDF: ajuste de líneas de código ambiguo. '
        'La salida no se considera verificada.',
        en='PDF verification could not be completed: ambiguous code line wrapping. '
           'The output is not considered verified.'))


def _pdf_disjoint_code_ranges(needs, options):
    """Allocate global text occurrences without reusing physical characters.

    Exact interval allocation, not a greedy choice: ambiguous wraps may have
    several valid placements. Forced and independent types are discharged
    first, so ordinary reports and large repeated blocks need no search.
    This does not establish block association or global source order.
    """
    from bisect import bisect_left
    from heapq import heappop, heappush
    examined = 0

    def budget(ranges=0, states=0):
        nonlocal examined
        examined += ranges
        if examined > _PDF_CODE_MAX_RANGES or states > _PDF_CODE_MAX_STATES:
            _pdf_code_check_incomplete()

    def overlap(left, right):
        return left[0] < right[1] and right[0] < left[1]

    def capacity(ranges):
        end = -1
        count = 0
        for start, stop in sorted(ranges, key=lambda span: (span[1], span[0])):
            if start >= end:
                count += 1
                end = stop
        return count

    def reduce_state(needs, options):
        while needs:
            budget(sum(map(len, options)))
            if any(capacity(ranges) < need for need, ranges in zip(needs, options)):
                return None
            forced = {i for i, (need, ranges) in enumerate(zip(needs, options))
                      if need == len(ranges)}
            if forced:
                taken = sorted(span for i in forced for span in options[i])
                if capacity(taken) < len(taken):
                    return None
                starts = [span[0] for span in taken]

                def available(span):
                    prior = bisect_left(starts, span[1]) - 1
                    return prior < 0 or taken[prior][1] <= span[0]

                options = tuple(tuple(span for span in ranges
                                      if available(span))
                                for i, ranges in enumerate(options) if i not in forced)
                needs = tuple(need for i, need in enumerate(needs) if i not in forced)
                continue
            # Find types with no competing type. Their own maximum set of
            # disjoint occurrences is sufficient; choosing it affects no one.
            active = Counter()
            ending = []
            competing = set()
            for start, end, kind in sorted((start, end, i) for i, ranges in enumerate(options)
                                            for start, end in ranges):
                while ending and ending[0][0] <= start:
                    _, expired = heappop(ending)
                    active[expired] -= 1
                    if not active[expired]:
                        del active[expired]
                others = active.keys() - {kind}
                if others:
                    competing.update(others)
                    competing.add(kind)
                active[kind] += 1
                heappush(ending, (end, kind))
            if len(competing) == len(needs):
                return needs, options
            needs = tuple(need for i, need in enumerate(needs) if i in competing)
            options = tuple(ranges for i, ranges in enumerate(options) if i in competing)
        return (), ()

    def branches(needs, options):
        kind = min(range(len(needs)), key=lambda i: len(options[i]) - needs[i])
        choices = sorted(options[kind], key=lambda span: (span[1] - span[0], span[0]))
        for index, taken in enumerate(choices):
            budget(sum(map(len, options)))
            next_needs = []
            next_options = []
            for i, (need, ranges) in enumerate(zip(needs, options)):
                if i == kind:
                    need -= 1
                    ranges = choices[index + 1:]
                if need:
                    next_needs.append(need)
                    next_options.append(tuple(span for span in ranges if not overlap(span, taken)))
            yield tuple(next_needs), tuple(next_options)

    # Iterative depth-first search avoids Python recursion limits for a large
    # collection of ambiguous lines. Generate alternatives lazily and retain
    # only a bounded memo cache. An explicit work budget fails closed on
    # adversarial ambiguity, reporting an incomplete check, not lost content.
    stack = [iter([(needs, options)])]
    seen = set()
    states = 0
    while stack:
        try:
            state = next(stack[-1])
        except StopIteration:
            stack.pop()
            continue
        if state in seen:
            continue
        states += 1
        budget(states=states)
        if len(seen) >= 2048:
            seen.clear()
        seen.add(state)
        state = reduce_state(*state)
        if state is None:
            continue
        if not state[0]:
            return True
        stack.append(branches(*state))
    return False


def _pdf_code_lines(code, text):
    # Preserve the extractor's physical line endings. A long token can wrap in
    # the PDF without acquiring a literal space; normal() would erase that
    # distinction. Only physical newlines may interrupt a source token here.
    # Source whitespace still requires whitespace, punctuation stays literal,
    # and all nonblank lines of this block must occur in source order. PDF text
    # extraction cannot certify indentation or exact whitespace width.
    cursor = 0
    checked = 0
    wrapped = 0
    for line in code.splitlines():
        if not normal(line):
            continue
        pattern = _pdf_code_line_pattern(line)
        match = pattern.search(text, cursor)
        if match is None:
            raise ValueError(backend_message('Texto de código PDF ausente o alterado / Missing or changed PDF code text'))
        cursor = match.end()
        checked += 1
        wrapped += '\n' in match.group()
    return checked, wrapped


def inspect(path, fmt, expected):
    if not expected: return {}
    if expected.get('version') != 3: raise ValueError(backend_message('Contrato de exportación antiguo: vuelve a generarlo / Regenerate old export contract'))
    observed = profile(path, fmt, expected)
    content = 0; structure = 0; paragraphs = 0; codes = 0; page_break_paragraphs = 0; wrapped_code_lines = 0
    metadata = 0; links = 0; placements = 0; tables_checked = 0; list_order_checked = 0; headings_checked = 0
    pdf_table_cells = 0; pdf_list_items = 0; list_markers_checked = 0
    cover_text = observed[''].get('cover_text', '')
    if fmt != 'pdf' and expected['cover_units'] != observed[''].get('cover_units', []):
        raise ValueError(backend_message('Metadato de portada alterado / Cover metadata changed'))
    for unit in expected['cover_units']:
        if fmt=='pdf':
            if not _pdf_pattern(unit).search(cover_text): raise ValueError(backend_message('Metadato de portada PDF alterado / Cover metadata changed'))
        metadata+=1
    if fmt == 'pdf':
        # Table cells and plain li elements need not contain a paragraph.
        # Their text must not silently fall outside the PDF presence contract.
        # Count repetitions globally; PDF order, boundaries and finding
        # association remain explicitly outside this textual check.
        pdf_table_cells, _ = _pdf_present(
            (cell for scope in expected['scopes'] for row in scope.get('table_rows', []) for cell in row),
            observed[''], 'tabla', 'table')
        pdf_list_items, _ = _pdf_present(
            (item for scope in expected['scopes'] for item in scope.get('list_sequence', [])),
            observed[''], 'lista', 'list')
        _, page_break_paragraphs = _pdf_present(
            (paragraph for scope in expected['scopes'] for paragraph in scope['paragraphs']),
            observed[''], 'párrafo', 'paragraph')
        _pdf_code_multiplicity(
            (code for scope in expected['scopes'] for code in scope['codes']),
            observed['']['raw_text'])
    for scope in expected['scopes']:
        key = '' if fmt == 'pdf' else scope['id']
        if key not in observed: raise ValueError(backend_message('Falta el hallazgo {p0} / Finding missing', p0=scope['id']))
        actual = observed[key]; text = actual['text']
        # Authored headings are content too. They previously fell between the
        # paragraph and generated-title checks, allowing silent loss/changes.
        heading_cursor = 0
        for heading in scope.get('headings', []):
            if not heading:
                continue
            if fmt == 'pdf':
                if not _pdf_pattern(heading).search(text):
                    raise ValueError(backend_message('Encabezado ausente o alterado', en='Missing or changed heading'))
            else:
                found = next((i for i in range(heading_cursor, len(actual['headings']))
                              if actual['headings'][i] == heading), None)
                if found is None:
                    raise ValueError(backend_message('Encabezado ausente o alterado', en='Missing or changed heading'))
                heading_cursor = found + 1
            headings_checked += 1
        if scope['title']:
            _ordered([scope['title']], text, 'Título'); content += 1
        # Repeated paragraphs consume separate occurrences and cannot move to
        # another finding in HTML, Markdown or Word.
        prose=scope['paragraphs_md'] if fmt=='md' else scope['paragraphs']
        if fmt != 'pdf': _paragraphs(prose, actual['paragraphs'], scope['id'])
        paragraphs += len(prose)
        if fmt == 'pdf':
            for label,value in scope['semantic']['fields']:
                if not _pdf_pattern(value).search(text): raise ValueError(backend_message('Metadato PDF ausente o alterado: {p0}', p0=label))
                metadata+=1
            for code in scope['codes']:
                checked, wrapped = _pdf_code_lines(code, actual['raw_text'])
                content += checked
                wrapped_code_lines += wrapped
            continue
        from export_semantics import check
        m,l,p=check(scope,actual['semantic'],fmt)
        metadata+=m;links+=l;placements+=p
        if scope['codes'] != actual['codes']:
            raise ValueError(backend_message('Código literal alterado ({p0}) / Literal code changed', p0=scope['id'] or 'informe'))
        codes += len(scope['codes'])
        content += sum(len([line for line in c.splitlines() if line]) for c in scope['codes'])
        # Multiplicity alone would accept a reordered procedure or priority
        # table. Consume each expected row in source order, while allowing
        # format-specific metadata rows between authored table rows.
        rows = [tuple(row) for row in actual['table_rows']]
        row_cursor = 0
        for row in scope['table_rows']:
            record = tuple(row)
            found = next((i for i in range(row_cursor, len(rows)) if rows[i] == record), None)
            if found is None: raise ValueError(backend_message('Tabla alterada o filas desordenadas / Table changed or rows reordered'))
            row_cursor = found + 1; structure += 1
        # Table boundaries also matter. Two similar tables can be swapped or
        # merged while retaining exactly the same flattened row sequence.
        table_cursor = 0
        for table in scope.get('tables', []):
            found = next((i for i in range(table_cursor, len(actual['tables']))
                          if actual['tables'][i] == table), None)
            if found is None: raise ValueError(backend_message('Tabla alterada o tablas desordenadas / Table changed or tables reordered'))
            table_cursor = found + 1; tables_checked += 1
        list_items = _word_list_items(scope, actual) if fmt == 'docx' else actual['list_items']
        counts=Counter(list_items)
        for item,count in Counter(x for items in scope['lists'] for x in items).items():
            if counts[item]<count:raise ValueError(backend_message('Lista alterada / List changed'))
        for items in scope['lists']:
            cursor = 0
            for item in items:
                found = next((i for i in range(cursor, len(list_items)) if list_items[i] == item), None)
                if found is None: raise ValueError(backend_message('Lista alterada / List changed'))
                cursor = found + 1; structure += 1
        cursor = 0
        source_list_parts = {record['index']: record['parts'] for record in scope.get('list_figure_parts', [])}
        flows = actual.get('list_flows', [])
        for item_index, item in enumerate(scope.get('list_sequence', [])):
            found = next((i for i in range(cursor, len(list_items))
                          if list_items[i] == item
                          and ('list_markers' not in scope
                               or actual['list_markers'][i] == scope['list_markers'][item_index])
                          and (fmt != 'docx' or item_index not in source_list_parts
                               or (i < len(flows) and _word_figure_list_matches(source_list_parts[item_index], flows[i])))), None)
            if found is None: raise ValueError(backend_message('Lista alterada o listas desordenadas / List changed or lists reordered'))
            cursor = found + 1; list_order_checked += 1
            if 'list_markers' in scope: list_markers_checked += 1
    return dict(content_units_checked=content, structure_units_checked=structure,
                paragraphs_checked=paragraphs, literal_code_blocks_checked=codes,
                finding_association_checked=fmt != 'pdf', contract_version=3,
                metadata_values_checked=metadata, link_targets_checked=links, evidence_associations_checked=placements,
                static_visibility_checked=fmt=='html', evidence_association_checked=fmt!='pdf',
                pdf_page_break_paragraphs=page_break_paragraphs,
                pdf_wrapped_code_lines=wrapped_code_lines,
                pdf_table_cells_checked=pdf_table_cells,
                pdf_list_items_checked=pdf_list_items,
                authored_tables_checked=tables_checked,
                authored_headings_checked=headings_checked,
                authored_list_items_order_checked=list_order_checked,
                authored_list_markers_checked=list_markers_checked,
                manual_review_required=True,
                format_specific_omissions=(sum(len(s['paragraphs'])-len(s['paragraphs_md']) for s in expected['scopes']) if fmt=='md' else 0),
                verification_scope=('text_presence_only' if fmt == 'pdf' else 'scoped_content_metadata_links_evidence'),
                limitations=(['PDF: extracción textual; revisar espacios, indentación, asociación de bloques y presentación. / Text extraction; review literal whitespace, block association and layout.'] if fmt == 'pdf' else ['La comparación estática no certifica geometría, oclusiones, CSS condicional ni estado dinámico; requiere revisión visual. Markdown omite el gráfico y su leyenda de alcance. / Content checks do not verify visual layout. Markdown omits the chart and its scope caption.']))
