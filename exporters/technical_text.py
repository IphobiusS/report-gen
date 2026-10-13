"""Opt-in locale metadata for literal technical text in editable Word files.

This helper does not change text, link targets or layout controls. The private
nonlinguistic locale is useful only with the optional report-gen line-break
adapter; ordinary DOCX export must not call this helper implicitly.
"""
from collections import defaultdict
from copy import deepcopy
import re

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import CONTENT_TYPE as CT
from pdf_pagination import PDF_IDENTIFIER_PATTERN, PDF_URI_PATTERN

TECHNICAL_LOCALE = 'zxx-ZZ-x-rgwrap'
_TEXT = qn('w:t')
_RUN = qn('w:r')
_PROPERTIES = qn('w:rPr')
_TRANSPARENT = {qn('w:' + name) for name in ('hyperlink', 'smartTag', 'dir', 'bdo', 'sdtContent')}
_EMPTY_MARKERS = {qn('w:' + name) for name in (
    'bookmarkStart', 'bookmarkEnd', 'commentRangeStart', 'commentRangeEnd',
    'proofErr', 'permStart', 'permEnd')}
_EXCLUDED_ANCESTORS = {qn('w:' + name) for name in ('fldSimple', 'del', 'moveFrom', 'drawing', 'pict')}


def technical_spans(text):
    """Return nonoverlapping Python-character offsets for eligible literals.

    Use the PDF classifier's 24+ technical subset, requiring a digit,
    underscore, slash or colon. Long alphabetic prose is not nonlinguistic.
    URLs have a 32-character floor and must be entirely ASCII; never mark the
    ASCII prefix of a Unicode URL or shaping cluster.
    """
    ranges = []
    for match in PDF_IDENTIFIER_PATTERN.finditer(text):
        if (re.search(r'[0-9_/:]', match.group())
                and not PDF_URI_PATTERN.search(match.group())):
            ranges.append(match.span())
    for match in PDF_URI_PATTERN.finditer(text):
        token = match.group()
        if len(token) >= 32 and token.isascii():
            ranges.append(match.span())
    return sorted(set(ranges))


def _text_groups(paragraph, field_depth):
    """Keep semantic XML boundaries while collecting text across formatting."""
    groups = []
    current = []

    def boundary():
        if current:
            groups.append(current[:])
            current.clear()

    def visit(container):
        for child in container:
            if child.tag in {qn('w:pPr'), _PROPERTIES} or child.tag in _EMPTY_MARKERS:
                continue
            if child.tag == _RUN:
                visit(child)
            elif child.tag == _TEXT:
                if field_depth[0]:
                    boundary()
                else:
                    current.append(child)
            elif child.tag == qn('w:fldChar'):
                boundary()
                kind = child.get(qn('w:fldCharType'))
                if kind == 'begin':
                    field_depth[0] += 1
                elif kind == 'end':
                    field_depth[0] = max(0, field_depth[0] - 1)
            elif child.tag in _TRANSPARENT:
                visit(child)
            elif child.tag == qn('w:sdt'):
                content = child.find(qn('w:sdtContent'))
                if content is not None:
                    visit(content)
            else:
                # Fields, tabs, hard/soft breaks, symbols, drawings, tracked
                # deletions and unknown inline objects cannot join a token.
                boundary()

    visit(paragraph)
    boundary()
    return groups


def _mark_run(run, intervals):
    """Split only affected runs, cloning every style and nontext child."""
    properties = run.find(_PROPERTIES)
    language = properties.find(qn('w:lang')) if properties is not None else None
    if language is not None and language.get(qn('w:val')) == TECHNICAL_LOCALE:
        return False
    pieces = []
    for child in run:
        if child.tag == _PROPERTIES:
            continue
        ranges = intervals.get(child, [])
        if child.tag != _TEXT or not ranges:
            pieces.append((False, deepcopy(child)))
            continue
        text = child.text or ''
        cursor = 0
        for start, end in ranges:
            for first, last, marked in ((cursor, start, False), (start, end, True)):
                if first == last:
                    continue
                node = deepcopy(child)
                node.text = text[first:last]
                if node.text[:1].isspace() or node.text[-1:].isspace():
                    node.set(qn('xml:space'), 'preserve')
                pieces.append((marked, node))
            cursor = end
        if cursor < len(text):
            node = deepcopy(child)
            node.text = text[cursor:]
            if node.text[:1].isspace() or node.text[-1:].isspace():
                node.set(qn('xml:space'), 'preserve')
            pieces.append((False, node))

    last_marked = None
    replacement = None
    replacements = []
    for marked, child in pieces:
        if replacement is None or marked != last_marked:
            replacement = OxmlElement('w:r')
            replacement.attrib.update(run.attrib)
            if properties is not None:
                replacement.append(deepcopy(properties))
            if marked:
                prop = replacement.get_or_add_rPr()
                lang = prop.find(qn('w:lang'))
                if lang is None:
                    lang = OxmlElement('w:lang')
                    # CT_RPr maintains schema order for existing and new lang.
                    prop.insert_element_before(lang, 'w:eastAsianLayout', 'w:specVanish',
                                               'w:oMath', 'w:rPrChange')
                lang.set(qn('w:val'), TECHNICAL_LOCALE)
            replacements.append(replacement)
            last_marked = marked
        replacement.append(child)
    if not replacements:
        return False
    replacements[-1].tail = run.tail
    for replacement in replacements:
        run.addprevious(replacement)
    run.getparent().remove(run)
    return True


def _mark_story(root):
    changed = 0
    field_depth = [0]
    for paragraph in root.iter(qn('w:p')):
        if any(parent.tag in _EXCLUDED_ANCESTORS for parent in paragraph.iterancestors()):
            continue
        edits = defaultdict(lambda: defaultdict(list))
        for nodes in _text_groups(paragraph, field_depth):
            text = ''.join(node.text or '' for node in nodes)
            spans = technical_spans(text)
            cursor = 0
            span_index = 0
            for node in nodes:
                length = len(node.text or '')
                while span_index < len(spans) and spans[span_index][1] <= cursor:
                    span_index += 1
                index = span_index
                while index < len(spans) and spans[index][0] < cursor + length:
                    start, end = spans[index]
                    left, right = max(start, cursor), min(end, cursor + length)
                    if left < right:
                        edits[node.getparent()][node].append((left - cursor, right - cursor))
                    index += 1
                cursor += length
        for run, intervals in edits.items():
            changed += _mark_run(run, intervals)
    return changed


def mark_technical_text(document):
    """Mark eligible literals in body, tables and existing headers/footers.

    Return the number of original runs changed. Field instructions/results
    are left untouched, including complex fields that cross paragraphs.
    Character offsets are Python Unicode offsets, never UTF-16 byte indexes.
    Repeated application leaves the XML byte-identical and returns zero.
    """
    story_types = {CT.WML_DOCUMENT_MAIN, CT.WML_HEADER, CT.WML_FOOTER}
    return sum(_mark_story(part.element) for part in document.part.package.parts
               if part.content_type in story_types and hasattr(part, 'element'))
