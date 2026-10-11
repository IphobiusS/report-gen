"""Inspect visible export content. Structured formats preserve literal code per finding.

PDF extraction is a textual presence check, never a proof of literal whitespace,
block association or pixel layout. Its limitations travel with the check record.
"""
from error_messages import message as backend_message
from collections import Counter
from copy import deepcopy
import re
import unicodedata
import zipfile
from lxml import etree, html

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W = '{' + NS['w'] + '}'


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


def _dom_units(root, markdown=False):
    paragraphs = [normal(n.text_content()) for n in _dom_paragraph_nodes(root)
                  if normal(n.text_content())]
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
                list_items=[list_lead(n) for n in root.xpath('.//li')])


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
        list_sequence = [list_lead(node) for node in root.xpath('.//li')
                         if not any(any(has_class(a, c) for c in ('steps', 'toc-list', 'toc'))
                                    for a in node.iterancestors())]
        semantic=dom(root, lambda src: image_digests[unquote(src)], severity_label=severity_label)
        for image in semantic['images']:
            image['docx_sha256'] = (docx_image_digests or {}).get(image['sha256'], image['sha256'])
        scopes.append(dict(id=key, semantic=semantic, title=normal(titles[0].text_content()) if titles else '',
                           headings=[normal(n.text_content()) for n in root.xpath('.//*[@data-rg-authored-heading="true"]')],
                           paragraphs=units['paragraphs'], paragraphs_md=[normal(n.text_content()) for n in _dom_paragraph_nodes(root) if not has_class(n,'chart-scope') and normal(n.text_content())], codes=units['codes'], table_rows=rows, tables=tables, lists=lists, list_sequence=list_sequence))
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


def _word_scopes(path, expected):
    from exporters.navigation import reference_name
    with zipfile.ZipFile(path) as package:
        tree = etree.fromstring(package.read('word/document.xml'), parser=etree.XMLParser(resolve_entities=False, no_network=True))
        blobs={n:package.read(n) for n in package.namelist() if n.startswith('word/media/') or n=='word/_rels/document.xml.rels'}
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
            list_items=[normal(_word_text(p)) for p in paras if p.xpath('./w:pPr/w:numPr|./w:pPr/w:pStyle[starts-with(@w:val,"List")]', namespaces=NS)])
    cover=tree.find(W+'body/'+W+'tbl')
    profiles['']['cover_text']=normal(' '.join(_word_text(p) for p in cover.findall('.//'+W+'p'))) if cover is not None else ''
    return profiles


def _profiles(path, fmt, expected):
    if fmt == 'pdf':
        from pypdf import PdfReader
        raw_pages = [unicodedata.normalize('NFC', page.extract_text() or '').replace('\u00ad', '')
                     for page in PdfReader(path).pages]
        pages = [normal(text) for text in raw_pages]
        return {'': dict(text=normal(' '.join(pages)), pages=pages,
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
        for _ in range(len(cover)): tree.remove(tree[0])
    else:
        tree = visible_copy(html.document_fromstring(path.read_text(encoding='utf-8')))
        cover=tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," cover ")]')
        cover_text=' '.join(_cover_units(tree)) if cover else ''
        mains=tree.xpath('//main')
        if not mains: raise ValueError(backend_message('Informe oculto o ausente / Report hidden or missing'))
        tree=mains[0]
        image_digest=html_digest
    result={}
    for key,root in _dom_scopes(tree,expected,fmt=='md').items():
        result[key]=_dom_units(root,fmt=='md')
        result[key]['semantic']=dom(root,image_digest,fmt=='md',expected.get('severity_label', 'Severidad'))
    result['']['cover_text']=cover_text
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
    words=normal(unit).split(' ')
    return re.compile(r'\s+'.join(r'\s*'.join(re.escape(c) for c in word) for word in words))


def _pdf_across_pages(unit, pages):
    # PDF painting order can put a table/header after the final paragraph of
    # a page. Match contiguous fragments on consecutive pages, consuming every
    # source word. This remains text presence, never proof of visual layout.
    words=normal(unit).split(' ')
    for first in range(len(pages)-1):
        cursor=0
        for page in pages[first:]:
            lo,hi,best=1,len(words)-cursor,0
            while lo<=hi:
                size=(lo+hi)//2
                if _pdf_pattern(' '.join(words[cursor:cursor+size])).search(page):
                    best=size;lo=size+1
                else:hi=size-1
            if not best:break  # No skipping unrelated pages.
            cursor+=best
            if cursor==len(words):return True
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
    physical_wrap = r'(?:\r?\n[ \t]*)?'
    for line in code.splitlines():
        words = normal(line).split()
        if not words:
            continue
        pattern = re.compile(r'\s+'.join(
            physical_wrap.join(re.escape(char) for char in word) for word in words))
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
    cover_text=observed['']['text'] if fmt=='pdf' else observed[''].get('cover_text','')
    for unit in expected['cover_units']:
        if fmt=='pdf':
            if not _pdf_pattern(unit).search(cover_text): raise ValueError(backend_message('Metadato de portada PDF alterado / Cover metadata changed'))
        elif unit not in cover_text: raise ValueError(backend_message('Metadato de portada alterado / Cover metadata changed'))
        metadata+=1
    if fmt == 'pdf':
        prose=Counter(p for scope in expected['scopes'] for p in scope['paragraphs'])
        for unit,count in prose.items():
            if len(_pdf_pattern(unit).findall(observed['']['text']))<count:
                if count==1 and _pdf_across_pages(unit,observed['']['pages']):page_break_paragraphs+=1
                else:raise ValueError(backend_message('Párrafo PDF ausente o alterado / PDF paragraph missing or changed'))
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
        counts=Counter(actual['list_items'])
        for item,count in Counter(x for items in scope['lists'] for x in items).items():
            if counts[item]<count:raise ValueError(backend_message('Lista alterada / List changed'))
        for items in scope['lists']:
            cursor = 0
            for item in items:
                found = next((i for i in range(cursor, len(actual['list_items'])) if actual['list_items'][i] == item), None)
                if found is None: raise ValueError(backend_message('Lista alterada / List changed'))
                cursor = found + 1; structure += 1
        cursor = 0
        for item in scope.get('list_sequence', []):
            found = next((i for i in range(cursor, len(actual['list_items']))
                          if actual['list_items'][i] == item), None)
            if found is None: raise ValueError(backend_message('Lista alterada o listas desordenadas / List changed or lists reordered'))
            cursor = found + 1; list_order_checked += 1
    return dict(content_units_checked=content, structure_units_checked=structure,
                paragraphs_checked=paragraphs, literal_code_blocks_checked=codes,
                finding_association_checked=fmt != 'pdf', contract_version=3,
                metadata_values_checked=metadata, link_targets_checked=links, evidence_associations_checked=placements,
                static_visibility_checked=fmt=='html', evidence_association_checked=fmt!='pdf',
                pdf_page_break_paragraphs=page_break_paragraphs,
                pdf_wrapped_code_lines=wrapped_code_lines,
                authored_tables_checked=tables_checked,
                authored_headings_checked=headings_checked,
                authored_list_items_order_checked=list_order_checked,
                manual_review_required=True,
                format_specific_omissions=(sum(len(s['paragraphs'])-len(s['paragraphs_md']) for s in expected['scopes']) if fmt=='md' else 0),
                verification_scope=('text_presence_only' if fmt == 'pdf' else 'scoped_content_metadata_links_evidence'),
                limitations=(['PDF: extracción textual; revisar espacios, indentación, asociación de bloques y presentación. / Text extraction; review literal whitespace, block association and layout.'] if fmt == 'pdf' else ['La comparación estática no certifica geometría, oclusiones, CSS condicional ni estado dinámico; requiere revisión visual. Markdown omite el gráfico y su leyenda de alcance. / Content checks do not verify visual layout. Markdown omits the chart and its scope caption.']))
