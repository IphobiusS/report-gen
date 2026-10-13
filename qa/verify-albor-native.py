#!/usr/bin/env python3
"""Audit frozen Albor DOCX bytes in a standalone installed LibreOffice OXT.

This QA-only script never registers an extension factory and never overwrites
the original DOCX. The native worker imports only the standard library and UNO.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid
from zipfile import ZipFile

TAG = 'zxx-ZZ-x-rgwrap'
SERVICE = 'com.sun.star.i18n.BreakIterator_qlt_ZZ_zxx-ZZ-x-rgwrap'
IMPLEMENTATION = 'org.reportgen.TechnicalLiteralBreakIterator'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
NS = {'w': W[1:-1]}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_contract(path):
    """Preserve source paragraphs and destinations, excluding live page caches.

    HYPERLINK fields retain their visible result and exact URI. Only cached
    PAGE/NUMPAGES/PAGEREF values may change when the document is laid out again.
    Empty structural paragraphs are not visible authored text.
    """
    from lxml import etree
    with ZipFile(path) as package:
        tree = etree.fromstring(package.read('word/document.xml'))
        relationships = etree.fromstring(package.read('word/_rels/document.xml.rels'))
        styles = etree.fromstring(package.read('word/styles.xml'))
    targets = {node.get('Id'): node.get('Target') for node in relationships
               if node.get('Type', '').endswith('/hyperlink') and node.get('TargetMode') == 'External'}
    style_nodes = {node.get(W + 'styleId'): node for node in styles.findall(W + 'style')}
    default_language = styles.find('./' + W + 'docDefaults/' + W + 'rPrDefault/' + W + 'rPr/' + W + 'lang')
    default_language = default_language.get(W + 'val') if default_language is not None else None
    def style_language(identity, seen=()):
        if identity in seen or identity not in style_nodes:
            return None
        node = style_nodes[identity]
        language = node.find('./' + W + 'rPr/' + W + 'lang')
        if language is not None and language.get(W + 'val') is not None:
            return language.get(W + 'val')
        base = node.find(W + 'basedOn')
        return style_language(base.get(W + 'val'), (*seen, identity)) if base is not None else None
    destinations, paragraphs, paragraph_links, paragraph_private = [], [], [], []
    def field_destination(code):
        match = re.search(r'\bHYPERLINK\s+"([^"\r\n]*)"(?:\s+\\l\s+"([^"\r\n]*)")?', code)
        if match:
            return match[1] + ('#' + match[2] if match[2] is not None else '')
        return None
    def excluded(code):
        return bool(re.match(r'\s*(?:PAGE|NUMPAGES|PAGEREF)\b', code))
    for paragraph in tree.xpath('//w:body//w:p', namespaces=NS):
        parts, fields, links, private = [], [], [], []
        pstyle = paragraph.find('./' + W + 'pPr/' + W + 'pStyle')
        language = style_language(pstyle.get(W + 'val') if pstyle is not None else 'Normal') or default_language
        def append(value, locale):
            private.extend(locale == TAG for _ in value)
            parts.extend(value)
        def link(start, target):
            if target is not None:
                destinations.append(target)
                links.append((start, len(parts), target))
        def visit(node, locale=language):
            if node.tag == W + 'r':
                charstyle = node.find('./' + W + 'rPr/' + W + 'rStyle')
                if charstyle is not None:
                    locale = style_language(charstyle.get(W + 'val')) or locale
                direct = node.find('./' + W + 'rPr/' + W + 'lang')
                if direct is not None and direct.get(W + 'val') is not None:
                    locale = direct.get(W + 'val')
            if node.tag == W + 'hyperlink':
                start = len(parts)
                for child in node:
                    visit(child, locale)
                if node.get(R + 'id') is not None:
                    link(start, targets[node.get(R + 'id')])
                return
            if node.tag == W + 'fldSimple':
                code = node.get(W + 'instr', '')
                start = len(parts)
                if not excluded(code):
                    for child in node:
                        visit(child, locale)
                link(start, field_destination(code))
                return
            if node.tag == W + 'fldChar':
                kind = node.get(W + 'fldCharType')
                if kind == 'begin':
                    fields.append({'code': '', 'result': False, 'start': len(parts)})
                elif kind == 'separate' and fields:
                    fields[-1]['result'] = True
                elif kind == 'end' and fields:
                    field = fields.pop()
                    link(field['start'], field_destination(field['code']))
                return
            if node.tag == W + 'instrText':
                if fields:
                    fields[-1]['code'] += node.text or ''
                return
            hidden_cache = any(excluded(item['code']) for item in fields)
            if node.tag == W + 't':
                if not hidden_cache:
                    append(node.text or '', locale)
                return
            if node.tag == W + 'tab':
                if not hidden_cache:
                    append('\t', locale)
                return
            if node.tag in (W + 'br', W + 'cr'):
                if not hidden_cache and node.get(W + 'type', 'textWrapping') == 'textWrapping':
                    append('\n', locale)
                return
            for child in node:
                visit(child, locale)
        visit(paragraph)
        if fields:
            raise ValueError('Unclosed Word field in paragraph')
        text = ''.join(parts)
        if text:
            paragraphs.append(text)
            association = [None] * len(text)
            for first, last, target in links:
                for index in range(first, last):
                    if association[index] not in (None, target):
                        raise ValueError('Overlapping different hyperlink targets')
                    association[index] = target
            paragraph_links.append(association)
            paragraph_private.append([index for index, marked in enumerate(private)
                                      if marked and not text[index].isspace()])
    return {'paragraphs': paragraphs, 'external_targets': sorted(set(destinations)),
            'external_placements': len(destinations),
            'paragraph_link_targets': paragraph_links,
            'paragraph_private_offsets': paragraph_private,
            'private_locale_runs': len(tree.xpath('//w:lang[@w:val=$tag]', namespaces=NS, tag=TAG))}


def compare_saved(original, saved):
    before, after = source_contract(original), source_contract(saved)
    if before['paragraphs'] != after['paragraphs']:
        first = next((index for index, pair in enumerate(zip(before['paragraphs'], after['paragraphs']))
                      if pair[0] != pair[1]), min(len(before['paragraphs']), len(after['paragraphs'])))
        raise ValueError('Native save changed authored paragraph sequence at ' + str(first)
                         + ': ' + repr(before['paragraphs'][first:first+1])
                         + ' -> ' + repr(after['paragraphs'][first:first+1]))
    if before['external_targets'] != after['external_targets']:
        raise ValueError('Native save changed exact external destinations')
    if before['paragraph_link_targets'] != after['paragraph_link_targets']:
        raise ValueError('Native save changed hyperlink-to-visible-text associations')
    if before['paragraph_private_offsets'] != after['paragraph_private_offsets']:
        raise ValueError('Native save changed effective private locale on literal characters')
    return {'sha256': digest(saved), 'authored_paragraphs_exact': len(before['paragraphs']),
            'external_targets_byte_exact': len(before['external_targets']),
            'private_locale_runs': after['private_locale_runs'],
            'live_page_field_caches': 'Excluded from text comparison; actual visible values are checked separately.'}


def uno_worker(config_path):
    import uno
    config = json.loads(Path(config_path).read_text())
    native = load_module('native_extension_worker', Path(config['product']) / 'scripts/verify-libreoffice-extension.py')
    output = Path(config['output'])
    connection = 'pipe,name=albor-native-' + uuid.uuid4().hex
    environment = native.native_environment()
    def prop(name, value):
        result = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
        result.Name, result.Value = name, value
        return result
    log = (output / 'office.log').open('wb')
    process = subprocess.Popen([config['executable'], '-env:UserInstallation=' + Path(config['profile']).as_uri(),
                                '--headless', '--nodefault', '--norestore', '--nologo',
                                '--accept=' + connection + ';urp;StarOffice.ServiceManager'],
                               stdout=log, stderr=log, env=environment)
    receipt = {'status': 'running', 'factory_registered_by_client': False, 'documents': []}
    document, desktop = None, None
    try:
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)
        context, last_error = None, None
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline and process.poll() is None:
            try:
                context = resolver.resolve('uno:' + connection + ';urp;StarOffice.ComponentContext')
                break
            except Exception as error:
                last_error = str(error)
                time.sleep(.2)
        if context is None:
            raise ValueError(f'Writer did not become ready: exit={process.poll()}, {last_error}')
        manager = context.ServiceManager
        adapter = manager.createInstanceWithContext(SERVICE, context)
        if adapter is None or adapter.getImplementationName() != IMPLEMENTATION:
            raise ValueError('Standalone installed OXT service is unavailable')
        receipt['implementation'] = adapter.getImplementationName()
        desktop = manager.createInstanceWithContext('com.sun.star.frame.Desktop', context)
        for item in config['documents']:
            original = source = Path(item['source'])
            folder = output / item['language']; folder.mkdir(exist_ok=True)
            for stage in ('original', 'reopened'):
                before_hash = digest(original)
                document = desktop.loadComponentFromURL(source.as_uri(), '_blank', 0,
                    (prop('Hidden', True), prop('ReadOnly', False), prop('UpdateDocMode', 3)))
                if document is None:
                    raise ValueError('Writer did not load ' + str(source))
                document.refresh()
                document.TextFields.refresh()
                exact = []
                for literal in item['literal_checks']:
                    search = document.createSearchDescriptor()
                    search.SearchString = literal['value']
                    search.SearchCaseSensitive = True
                    search.SearchRegularExpression = False
                    search.SearchWords = False
                    search.SearchSimilarity = False
                    found = document.findAll(search)
                    strings = [found.getByIndex(index).String for index in range(found.getCount())]
                    if len(strings) != literal['occurrences'] or any(value != literal['value'] for value in strings):
                        raise ValueError('Native editor lost or changed literal: ' + literal['name'])
                    exact.append({'name': literal['name'], 'occurrences': len(strings)})
                pdf = folder / (stage + '.pdf')
                saved = folder / (stage + '.docx')
                document.storeToURL(pdf.as_uri(), (prop('FilterName', 'writer_pdf_Export'), prop('Overwrite', True)))
                document.storeToURL(saved.as_uri(), (prop('FilterName', 'Office Open XML Text'), prop('Overwrite', True)))
                document.close(True); document = None
                if digest(original) != before_hash:
                    raise ValueError('Original DOCX was modified')
                receipt['documents'].append({'language': item['language'], 'stage': stage,
                    'source_sha256': digest(source), 'saved_sha256': digest(saved), 'pdf_sha256': digest(pdf),
                    'native_editor_literal_checks': exact})
                source = saved
        if not desktop.terminate():
            raise ValueError('Writer refused graceful termination')
        process.wait(timeout=25)
        if process.returncode:
            raise ValueError('Writer failed during teardown: ' + str(process.returncode))
        receipt['status'] = 'passed'
    except Exception as error:
        receipt.update(status='failed', error=str(error))
        raise
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
        log.close()
        receipt['office_returncode'] = process.returncode
        write_json(output / 'uno.json', receipt)


def inspect_albor_wrap(source_docx, native_pdf):
    """Read-only Albor wrapping oracle, using source margins and painted cell borders.
    
    This deliberately does not claim support for merged/floating tables, RTL,
    multi-column sections or arbitrary rich paragraphs. Ambiguous geometry fails.
    The native DOCX text/link oracle remains responsible for exact Unicode/copy.
    """
    from collections import defaultdict
    from hashlib import sha256
    from pathlib import Path
    import re
    from zipfile import ZipFile
    
    import fitz
    from lxml import etree
    
    NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    W = '{' + NS['w'] + '}'
    TAG = 'zxx-ZZ-x-rgwrap'
    
    
    def _require(ok, message):
        if not ok:
            raise ValueError('Albor wrap: ' + message)
    
    
    def _value(element, name, default=None):
        return element.get(W + name, default) if element is not None else default
    
    
    def _text(element):
        return ''.join(element.xpath('.//w:t/text()', namespaces=NS))
    
    
    def _source_rows(path):
        with ZipFile(path) as archive:
            root = etree.fromstring(archive.read('word/document.xml'))
            styles = etree.fromstring(archive.read('word/styles.xml'))
        style_map = {_value(s, 'styleId'): s for s in styles.findall(W + 'style')}
    
        def style_chain(name):
            seen, chain = set(), []
            while name in style_map:
                _require(name not in seen, 'cyclic style inheritance')
                seen.add(name); style = style_map[name]; chain.insert(0, style)
                name = _value(style.find(W + 'basedOn'), 'val')
            return chain
    
        body = root.find(W + 'body')
        pending, rows = [], []
        for block in body:
            pending.append(block)
            section = block if block.tag == W + 'sectPr' else block.find('./w:pPr/w:sectPr', NS)
            if section is None:
                continue
            size, margins = section.find(W + 'pgSz'), section.find(W + 'pgMar')
            _require(size is not None and margins is not None, 'missing explicit section dimensions')
            columns = section.find(W + 'cols')
            _require(int(_value(columns, 'num', '1')) == 1, 'multi-column section unsupported')
            bounds = {name: int(_value(margins, name, '0')) / 20 for name in ('left', 'right', 'top', 'bottom')}
            bounds.update(width=int(_value(size, 'w')) / 20, height=int(_value(size, 'h')) / 20)
            for item in pending:
                paragraphs = [item] if item.tag == W + 'p' else item.findall('.//w:p', NS)
                for paragraph in paragraphs:
                    text = _text(paragraph)
                    match = re.fullmatch(r'(URL: |LINK: |TOKEN: )(\S+)', text)
                    if not match:
                        continue
                    prefix, value = match.groups()
                    eligible = value.isascii() and (
                        (prefix in ('URL: ', 'LINK: ') and value.startswith(('https://', 'http://')) and len(value) >= 32)
                        or (prefix == 'TOKEN: ' and len(value) >= 24 and re.search(r'[0-9_/:]', value)))
                    properties = paragraph.find(W + 'pPr')
                    pstyle = _value(properties.find(W + 'pStyle') if properties is not None else None, 'val', 'Normal')
                    right_indent = 0
                    for container in [*style_chain(pstyle), paragraph]:
                        ind = container.find('./w:pPr/w:ind', NS)
                        if ind is not None:
                            _require(_value(ind, 'rightChars') is None, 'character-based indentation unsupported')
                            right_indent = int(_value(ind, 'right', str(right_indent)))
                    row = {'prefix': prefix, 'value': value, 'eligible': bool(eligible), 'bounds': dict(bounds),
                           'right_indent_pt': right_indent / 20, 'context': 'paragraph'}
                    cell = next((a for a in paragraph.iterancestors() if a.tag == W + 'tc'), None)
                    if cell is not None:
                        table = next(a for a in cell.iterancestors() if a.tag == W + 'tbl')
                        _require(not table.xpath('.//w:gridSpan|.//w:vMerge|./w:tblPr/w:tblpPr', namespaces=NS),
                                 'merged or floating diagnostic table unsupported')
                        width = cell.find('./w:tcPr/w:tcW', NS)
                        _require(_value(width, 'type') == 'dxa', 'cell needs an explicit absolute width')
                        table_style = _value(table.find('./w:tblPr/w:tblStyle', NS), 'val', 'TableNormal')
                        padding = {'left': None, 'right': None}
                        for container in [*style_chain(table_style), table, cell]:
                            spec = './w:tcPr/w:tcMar/' if container is cell else './w:tblPr/w:tblCellMar/'
                            for side in padding:
                                node = container.find(spec + 'w:' + side, NS)
                                if node is not None:
                                    _require(_value(node, 'type', 'dxa') == 'dxa', 'relative cell padding unsupported')
                                    padding[side] = int(_value(node, 'w')) / 20
                        _require(all(v is not None for v in padding.values()), 'cell padding unresolved')
                        row.update(context='table', cell_width_pt=int(_value(width, 'w')) / 20,
                                   padding_pt=padding)
                    elif paragraph.find('./w:pPr/w:numPr', NS) is not None:
                        row['context'] = 'list'
                    rows.append(row)
            pending = []
        _require(not pending, 'source section end missing')
        _require(rows, 'no diagnostic literal paragraphs')
        marked = [''.join(run.xpath('./w:t/text()', namespaces=NS)) for run in root.xpath(
            '//w:r[w:rPr/w:lang[@w:val=$tag]]', namespaces=NS, tag=TAG)]
        return rows, marked
    
    
    def _lines(page):
        groups = defaultdict(list)
        for block in page.get_text('rawdict')['blocks']:
            for line in block.get('lines', []):
                for span in line['spans']:
                    # Retain logical order inside a font span, including ligatures.
                    by_baseline = defaultdict(list)
                    for char in span['chars']:
                        by_baseline[round(char['origin'][1], 1)].append(char)
                    for baseline, chars in by_baseline.items():
                        groups[baseline].append(chars)
        return [(y, [char for chars in sorted(spans, key=lambda s: s[0]['bbox'][0]) for char in chars])
                for y, spans in sorted(groups.items())]
    
    
    def _cell_bounds(page, prefix, expected_width):
        vertical, horizontal = [], []
        for drawing in page.get_drawings():
            for item in drawing['items']:
                pairs = []
                if item[0] == 'l':
                    pairs = [(item[1], item[2])]
                elif item[0] == 're':
                    rectangle = item[1]
                    pairs = [(rectangle.tl, rectangle.tr), (rectangle.tr, rectangle.br),
                             (rectangle.br, rectangle.bl), (rectangle.bl, rectangle.tl)]
                for a, b in pairs:
                    if abs(a.x - b.x) < .15:
                        vertical.append((a.x, min(a.y, b.y), max(a.y, b.y)))
                    elif abs(a.y - b.y) < .15:
                        horizontal.append((a.y, min(a.x, b.x), max(a.x, b.x)))
        middle = (prefix.y0 + prefix.y1) / 2
        xs = sorted({round(x, 3) for x, y0, y1 in vertical if y0 - .5 <= middle <= y1 + .5})
        lefts = [x for x in xs if x < prefix.x0]
        rights = [x for x in xs if x > prefix.x1]
        _require(lefts and rights, 'diagnostic cell lacks enclosing painted vertical borders')
        left, right = max(lefts), min(rights)
        _require(abs((right - left) - expected_width) <= 1.0,
                 'painted cell width disagrees with DOCX width')
        ys = sorted({round(y, 3) for y, x0, x1 in horizontal
                     if x0 - 1 <= left and x1 + 1 >= right})
        top = [y for y in ys if y < prefix.y0]
        bottom = [y for y in ys if y > prefix.y1]
        _require(top and bottom, 'diagnostic cell lacks enclosing painted row borders')
        return fitz.Rect(left, max(top), right, min(bottom))
    
    
    def _inspect_albor_wrap(source_docx, native_pdf):
        """Reject early wraps/overflow in Albor's ASCII diagnostic contexts."""
        rows, marked = _source_rows(source_docx)
        measured, excluded = [], []
        with fitz.open(native_pdf) as document:
            hits = []
            page_lines = [_lines(page) for page in document]
            for number, page in enumerate(document):
                for prefix in ('URL: ', 'LINK: ', 'TOKEN: '):
                    hits.extend((number, rectangle, prefix) for rectangle in page.search_for(prefix.rstrip()))
            hits.sort(key=lambda h: (h[0], round(h[1].y0, 1), h[1].x0))
            _require(len(hits) == len(rows), f'diagnostic prefix count differs: PDF={len(hits)}, DOCX={len(rows)}')
            for index, (row, (number, prefix_box, found_prefix)) in enumerate(zip(rows, hits), 1):
                _require(row['prefix'] == found_prefix, 'diagnostic paragraph order/identity is ambiguous')
                if not row['eligible']:
                    excluded.append({'diagnostic': index, 'prefix': row['prefix'], 'value': row['value'],
                                     'reason': 'Outside technical-ASCII scope; literal preservation is checked separately.'})
                    continue
                bounds = row['bounds']
                page = document[number]
                _require(abs(page.rect.width - bounds['width']) < .5 and abs(page.rect.height - bounds['height']) < .5,
                         'native page size differs from source section')
                left, right = bounds['left'], bounds['width'] - bounds['right'] - row['right_indent_pt']
                cell = None
                if row['context'] == 'table':
                    cell = _cell_bounds(page, prefix_box, row['cell_width_pt'])
                    left, right = cell.x0 + row['padding_pt']['left'], cell.x1 - row['padding_pt']['right'] - row['right_indent_pt']
                _require(left - 1 <= prefix_box.x0 < prefix_box.x1 <= right + 1, 'prefix falls outside its external bounds')
                wanted = ''.join((row['prefix'] + row['value']).split())
                chars = []
                for page_number in range(number, len(document)):
                    if cell is not None and page_number != number:
                        break
                    for line_number, (baseline, line) in enumerate(page_lines[page_number]):
                        if page_number == number and baseline < prefix_box.y0:
                            continue
                        if not bounds['top'] <= baseline <= bounds['height'] - bounds['bottom']:
                            continue
                        if cell is not None and not cell.y0 <= baseline <= cell.y1:
                            continue
                        for char in line:
                            middle = (char['bbox'][0] + char['bbox'][2]) / 2
                            if not left - 1 <= middle <= right + 1 or char['c'].isspace():
                                continue
                            if page_number == number and prefix_box.y0 <= baseline <= prefix_box.y1 and char['bbox'][0] < prefix_box.x0 - .5:
                                continue
                            chars.append(dict(char, row=(page_number, line_number)))
                        if len(chars) >= len(wanted):
                            break
                    if len(chars) >= len(wanted):
                        break
                chars = chars[:len(wanted)]
                _require(''.join(c['c'] for c in chars) == wanted,
                         f'literal missing, clipped or contaminated in diagnostic {index}')
                prefix_length = len(row['prefix'].replace(' ', ''))
                _require(chars[prefix_length - 1]['row'] == chars[prefix_length]['row'],
                         f'prefix orphaned before technical literal in diagnostic {index}')
                value_chars = chars[prefix_length:]
                groups = []
                for char in value_chars:
                    if not groups or groups[-1][0] != char['row']:
                        groups.append((char['row'], []))
                    groups[-1][1].append(char)
                samples = []
                for line_index, (identity, line_chars) in enumerate(groups):
                    last = max(c['bbox'][2] for c in line_chars)
                    _require(last <= right + 1.5, f'technical literal overflows in diagnostic {index}')
                    if line_index + 1 == len(groups):
                        continue
                    following = groups[line_index + 1][1][0]
                    advance = following['bbox'][2] - following['bbox'][0]
                    gap = right - last
                    _require(advance > 0 and gap <= advance + 1.5,
                             f'premature technical wrap in diagnostic {index}: gap={gap:.2f}, next={advance:.2f}')
                    samples.append({'page': identity[0] + 1, 'gap_pt': round(gap, 3), 'next_character_pt': round(advance, 3)})
                measured.append({'diagnostic': index, 'context': row['context'], 'prefix': row['prefix'],
                                 'value': row['value'], 'page': number + 1, 'line_count': len(groups),
                                 'external_right_pt': round(right, 3),
                                 'boundary_source': 'painted PDF cell borders + DOCX padding' if cell is not None else 'DOCX section margins + paragraph right indentation',
                                 'prefix_continues': True, 'nonfinal_lines': samples})
        _require(measured, 'no ASCII diagnostics measured')
        measured_values = {r['value'] for r in measured}
        return {'status': 'passed', 'source_docx_sha256': sha256(Path(source_docx).read_bytes()).hexdigest(),
                'native_pdf_sha256': sha256(Path(native_pdf).read_bytes()).hexdigest(),
                'measured': measured, 'excluded_diagnostics': excluded,
                'marked_fragments_outside_measured_exact_values': [s for s in marked if s not in measured_values],
                'scope': 'Only Albor URL/LINK/TOKEN diagnostic paragraphs in ordinary sections, lists and nonmerged painted table cells; no universal wrapping acceptance.'}
    return _inspect_albor_wrap(source_docx, native_pdf)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('product', 'fixtures', 'manifest', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--executable', required=True)
    parser.add_argument('--unopkg', required=True)
    parser.add_argument('--uno-python', required=True)
    args = parser.parse_args()
    args.product = args.product.resolve()
    args.fixtures = args.fixtures.resolve()
    args.output = args.output.resolve(); args.output.mkdir(parents=True, exist_ok=False)
    output = args.output
    result = {'status': 'running', 'created_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'Exact final Albor DOCX files, installed optional OXT, official LibreOffice 26.2.6.3 Linux.',
              'visual_review': 'pending', 'microsoft_word': 'not_run', 'documents': []}
    try:
        sys.path.insert(0, str(args.product))
        native = load_module('native_extension', args.product / 'scripts/verify-libreoffice-extension.py')
        verifier = load_module('native_report', args.product / 'scripts/verify-libreoffice.py')
        builder = load_module('oxt_builder', args.product / 'integrations/libreoffice/build_oxt.py')
        manifest = json.loads(args.manifest.read_text())
        result['manifest_sha256'] = digest(args.manifest)
        result['corpus_seal_sha256'] = manifest['corpus_seal_sha256']
        actual_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.product, text=True).strip()
        if actual_sha != manifest['product_sha']:
            raise ValueError('Frozen product commit mismatch')
        actual_tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=args.product, text=True).strip()
        if actual_tree != manifest['product_tree']:
            raise ValueError('Frozen product tree mismatch')
        result['product_sha'] = actual_sha
        result['product_tree'] = actual_tree
        if os.geteuid() == 0:
            raise ValueError('Use an ordinary non-root account for standalone OXT acceptance')
        environment = native.native_environment()
        version = native.run([args.executable, '--version'], output / 'version.json', timeout=20, env=environment)['stdout'].strip()
        if not version.startswith('LibreOffice 26.2.6.3 ') or not native.stable_version(version):
            raise ValueError('Unexpected native renderer: ' + version)
        result['renderer_version'] = version
        oxt = builder.build_oxt(output / 'report-gen-technical-literals.oxt')
        result['oxt_sha256'] = digest(oxt)
        if result['oxt_sha256'] != manifest['oxt_sha256']:
            raise ValueError('Audited OXT bytes mismatch')
        inputs = []
        for item in manifest['documents']:
            path = (args.fixtures / item['file']).resolve()
            if path.parent != args.fixtures or digest(path) != item['sha256']:
                raise ValueError('Final DOCX fixture path/hash mismatch')
            contract = source_contract(path)
            if not contract['private_locale_runs']:
                raise ValueError('Final DOCX does not contain activated technical metadata')
            if len(contract['external_targets']) != item['expected_external_targets']:
                raise ValueError('Unexpected source external-target inventory')
            if contract['external_targets'] != item['literal_targets']:
                raise ValueError('Exact source external-target manifest mismatch')
            literals = []
            for literal in item['literals']:
                occurrences = sum(text.count(literal['value']) for text in contract['paragraphs'])
                if not occurrences:
                    raise ValueError('Manifest literal missing from original DOCX: ' + literal['name'])
                literals.append(dict(literal, occurrences=occurrences))
            inputs.append({'language': item['language'], 'source': str(path), 'literal_checks': literals})
        if {item['language'] for item in inputs} != {'es', 'en'} or len(inputs) != 2:
            raise ValueError('Expected exactly one Spanish and one English frozen DOCX')
        with tempfile.TemporaryDirectory(prefix='albor-native-oxt-') as profile:
            try:
                native.initialize_profile(args, profile, output, environment)
                native.run([args.unopkg, '-env:UserInstallation=' + Path(profile).as_uri(), 'add', '--verbose',
                    '--log-file', str(output / 'unopkg.log'), '--suppress-license', str(oxt)],
                    output / 'installation.json', timeout=60, env=environment)
                native.run([args.unopkg, '-env:UserInstallation=' + Path(profile).as_uri(), 'list'],
                           output / 'installed-list.json', timeout=30, env=environment)
                config = {'product': str(args.product), 'output': str(output), 'profile': profile,
                          'executable': args.executable, 'documents': inputs}
                write_json(output / 'config.json', config)
                native.run([args.uno_python, str(Path(__file__).resolve()), '--worker', str(output / 'config.json')],
                           output / 'worker.json', timeout=540, env=environment)
            finally:
                native.preserve_profile_metadata(profile, output)
        import fitz
        for item in manifest['documents']:
            source = args.fixtures / item['file']
            for stage in ('original', 'reopened'):
                folder = output / item['language']
                pdf = folder / (stage + '.pdf')
                saved = folder / (stage + '.docx')
                with fitz.open(pdf) as document:
                    geometry = {'pages': len(document), 'internal_links': sum(
                        link['kind'] == fitz.LINK_GOTO for page in document for link in page.get_links())}
                    pages = []
                    for number, page in enumerate(document, 1):
                        png = folder / (stage + f'-{number:02}.png')
                        page.get_pixmap(dpi=110, alpha=False).save(png)
                        pages.append({'page': number, 'file': png.name, 'sha256': digest(png)})
                check = {'language': item['language'], 'stage': stage, 'docx_sha256': digest(source),
                         'native_docx': compare_saved(source, saved), 'pdf_sha256': digest(pdf), 'pages': pages,
                         'contents': verifier.inspect_contents(source, pdf),
                         'content': verifier.inspect_native_content(source, pdf, item['capture']),
                         'links': verifier.inspect_links(source, pdf, geometry),
                         'technical_line_fill': inspect_albor_wrap(source, pdf)}
                if check['contents']['entries_checked'] != manifest['expected_contents_entries']:
                    raise ValueError('Final native contents inventory mismatch')
                result['documents'].append(check)
                write_json(output / 'validation.json', result)
            if digest(source) != item['sha256']:
                raise ValueError('Input DOCX bytes changed during native acceptance')
        result['status'] = 'passed'
        return 0
    except Exception as error:
        result.update(status='failed', error=str(error))
        print(str(error), file=sys.stderr)
        return 1
    finally:
        write_json(output / 'validation.json', result)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        uno_worker(sys.argv[2])
    else:
        raise SystemExit(main())
