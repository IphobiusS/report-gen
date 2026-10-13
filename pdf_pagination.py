"""Preserve protected tables and paginate genuinely oversized narrative rows."""
from error_messages import message as backend_message
import re


PDF_URI_PATTERN = re.compile(r"\b(?:https?|ftps?)://[^\s<>\"'`]+", re.IGNORECASE)
# A bounded classifier, not language detection: long ASCII runs (32+) or
# technical runs (24+) containing a digit, underscore, slash or colon. Do not
# split non-ASCII shaping clusters or add break hints to ordinary short words.
PDF_IDENTIFIER_PATTERN = re.compile(
    r'(?<!\S)(?:[\x21-\x7e]{32,}|'
    r'(?=[\x21-\x7e]{24,}(?!\S))(?=[\x21-\x7e]*[0-9_/:])[\x21-\x7e]+)(?!\S)'
)


def compact_pdf_uri_breaks(source):
    """Coalesce generated URI hints in the private WeasyPrint input only.

    One ``wbr`` per ASCII character creates several layout/drawing objects per
    glyph. WeasyPrint represents those breaks internally as U+200B anyway.
    Let Pango shape one text run with the same optional break opportunities;
    its empty glyphs are omitted from the PDF, including its ToUnicode text.
    Authored markup, non-ASCII clusters and link destinations stay untouched.
    This representation must never be saved as the portable HTML export.
    """
    from bisect import bisect_left, bisect_right
    from lxml import html
    tree = html.document_fromstring(source)
    changed = False
    parents = {boundary.getparent() for boundary in
               tree.xpath('//wbr[@data-rg-pdf-uri-break="true"]')}
    for parent in parents:
        # _pdf_code_layout generates only plain break hints in each affected
        # text container. Retain any mixed/visible authored markup unchanged.
        if any(child.tag != 'wbr' or len(child) or child.text or
               dict(child.attrib) != {'data-rg-pdf-uri-break': 'true'}
               for child in parent):
            continue
        parts = [parent.text or '']
        offsets = set()
        length = len(parts[0])
        for boundary in parent:
            offsets.add(length)
            parts.append(boundary.tail or '')
            length += len(parts[-1])
        original = ''.join(parts)
        ordered_offsets = sorted(offsets)
        matches = [(match, ordered_offsets[bisect_right(ordered_offsets, match.start()):
                                          bisect_left(ordered_offsets, match.end())])
                   for match in PDF_URI_PATTERN.finditer(original)]
        if {offset for _, positions in matches for offset in positions} != offsets:
            continue
        for boundary in list(parent):
            parent.remove(boundary)
        parent.text = None
        if (len(matches) == 1 and not original[:matches[0][0].start()].strip()
                and not original[matches[0][0].end():].strip()):
            # A literal-only anchor needs no extra inline box (and therefore
            # no second inherited PDF annotation for each visible line).
            cuts = [0, *ordered_offsets, len(original)]
            parent.text = '\u200b'.join(original[a:b] for a, b in zip(cuts, cuts[1:]))
            parent.set('style', parent.get('style', '') + ';font-variant-ligatures:none')
            changed = True
            continue
        previous = None
        cursor = 0
        for match, positions in matches:
            if not positions:
                continue
            prefix = original[cursor:match.start()]
            if previous is None:
                parent.text = (parent.text or '') + prefix
            else:
                previous.tail = (previous.tail or '') + prefix
            # Common/contextual ligatures can cross an empty break glyph and
            # acquire an invalid ToUnicode map in WeasyPrint/Pango. The old
            # independent wbr boxes prevented these ligatures already. Limit
            # the setting to this literal; prose and required script shaping keep
            # their normal typography.
            run = html.Element('span', {
                'data-rg-pdf-uri-run': 'true',
                'style': 'font-variant-ligatures:none'})
            cuts = [match.start(), *positions, match.end()]
            run.text = '\u200b'.join(original[a:b] for a, b in zip(cuts, cuts[1:]))
            parent.append(run)
            previous = run
            cursor = match.end()
        if previous is None:
            parent.text = original
        else:
            previous.tail = original[cursor:]
        changed = True
    return html.tostring(tree, encoding='unicode', method='html') if changed else source


def keep_short_labelled_lists(source):
    """Keep a brief label and its small inline-only list on one PDF page.

    This transient hint is deliberately bounded. Long, nested or illustrated
    lists must remain free to paginate, and the authored DOM text, targets and
    native list counters are unchanged. Both PDF engines use the same hint.
    """
    from lxml import html
    tree = html.document_fromstring(source)
    changed = False
    inline = {'a', 'strong', 'b', 'em', 'i', 'code', 'span', 'br', 's', 'del',
              'sub', 'sup', 'u', 'wbr'}
    for listing in tree.xpath('//ul|//ol'):
        label = listing.getprevious()
        if (label is None or label.tag != 'p' or (label.text or '').strip()
                or len(label) != 1 or label[0].tag not in {'strong', 'b'}
                or (label[0].tail or '').strip()
                or not 0 < len(label.text_content().strip()) <= 160
                or not 1 <= len(listing) <= 4
                or any(item.tag != 'li' for item in listing)
                or len(listing.text_content()) > 240
                or len(listing.xpath('.//br')) > 4
                or any(node.tag not in inline for item in listing
                       for node in item.iterdescendants())
                or any(node.tag not in inline for node in label.iterdescendants())):
            continue
        label.set('style', label.get('style', '') +
                  ';break-after:avoid;page-break-after:avoid')
        listing.set('style', listing.get('style', '') +
                    ';break-inside:avoid;page-break-inside:avoid')
        changed = True
    return html.tostring(tree, encoding='unicode', method='html') if changed else source


def table_error(finding):
    return ValueError(
        backend_message('Hallazgo {p0}: una tabla no cabe completa en una página junto a su encabezado. Reduce o divide la tabla, o muévela a una sección narrativa o anexo del informe. Las tablas del procedimiento del mismo hallazgo tienen el mismo límite. El PDF no se ha generado para evitar cortar la tabla.', p0=finding)
    )


def relax_oversized_rows(document):
    """Let an already fragmented narrative row retain its repeated header.

    Keeping ordinary rows together is useful, but WeasyPrint cannot honor
    ``break-inside: avoid`` on a row taller than a page. Its fallback can drop
    the table header on early fragments and strand the preceding title. Use
    the actual first layout to relax only those rows, without guessing from
    character counts or changing protected finding tables. The elements are
    owned by the HTML renderer; the caller performs one fresh layout after a
    change. Repeated header/footer rows are not oversized body rows.
    """
    rows = {}
    for number, page in enumerate(document.pages):
        def walk(box, protected=False, repeated_group=False):
            element = getattr(box, 'element', None)
            if element is not None:
                protected = protected or 'finding' in (element.get('class') or '').split()
                repeated_group = repeated_group or element.tag in {'thead', 'tfoot'}
            if (type(box).__name__ == 'TableRowBox' and element is not None
                    and not protected and not repeated_group
                    and box.style['break_inside'] in {'avoid', 'avoid-page'}):
                rows.setdefault(element, set()).add(number)
            for child in box.all_children():
                walk(child, protected, repeated_group)

        walk(page._page_box)
    changed = False
    for element, pages in rows.items():
        if len(pages) > 1:
            element.set('style', (element.get('style') or '') +
                        ';break-inside:auto!important;page-break-inside:auto!important')
            changed = True
    return changed


def verify_finding_tables(document):
    """Inspect actual WeasyPrint page fragments before writing PDF bytes.

    WeasyPrint exposes its layout tree through _page_box. Keep the integration
    isolated here and exercise it with rendered PDF regression tests.
    """
    seen = {}
    for number, page in enumerate(document.pages):
        page_box = page._page_box
        bottom = page_box.content_box_y() + page_box.height

        def walk(box, finding=None):
            element = getattr(box, "element", None)
            if element is not None and "finding" in (element.get("class") or "").split():
                finding = element.get("id") or "sin ID"
            intro = element is not None and "finding-intro" in (element.get("class") or "").split() and type(box).__name__ == "BlockBox"
            if finding and (intro or type(box).__name__ in {"TableBox", "InlineTableBox"}):
                pages = seen.setdefault(id(element), set())
                pages.add(number)
                if len(pages) > 1 or box.position_y + box.height > bottom + 2:
                    raise table_error(finding)
            for child in box.all_children():
                walk(child, finding)

        walk(page_box)


def mark_finding_tables(source):
    """Add zero-size boundary markers for a Chromium PDF layout preflight."""
    from lxml import html
    import secrets
    tree = html.document_fromstring(source)
    checks = []
    prefix = "RGTABLE" + secrets.token_hex(6).upper()
    for finding in tree.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " finding ")]'):
        for table in finding.xpath('.//table'):
            cells = table.xpath('./tr/th|./tr/td|./thead/tr/th|./thead/tr/td|./tbody/tr/th|./tbody/tr/td|./tfoot/tr/th|./tfoot/tr/td')
            if not cells:
                continue
            start, end = f"{prefix}S{len(checks)}END", f"{prefix}E{len(checks)}END"
            for cell, token, edge in [(cells[0], start, "top:0;left:0"), (cells[-1], end, "bottom:0;right:0")]:
                cell.set("style", (cell.get("style") or "") + ";position:relative")
                marker = html.Element("span", {"class": "rg-table-boundary", "style": f"position:absolute;{edge};font-size:1px;line-height:1px;color:white;opacity:0.01"})
                marker.text = token
                cell.append(marker)
            checks.append((finding.get("id") or "sin ID", start, end))
    return html.tostring(tree, encoding="unicode", method="html"), checks


def verify_table_markers(pdf_bytes, checks):
    """A protected table must have both boundaries on exactly one PDF page."""
    from io import BytesIO
    import pdfplumber
    with pdfplumber.open(BytesIO(pdf_bytes)) as document:
        character_pages = [[(letter, c["top"], c["bottom"]) for c in page.chars if c["size"] <= 1.0 for letter in c["text"]] for page in document.pages]
        heights = [page.height for page in document.pages]
        pages = ["".join(c[0] for c in chars) for chars in character_pages]
    for finding, start, end in checks:
        first = [i for i, page in enumerate(pages) if start in page]
        last = [i for i, page in enumerate(pages) if end in page]
        if not first or not last:
            raise ValueError(backend_message('No se pudo verificar la paginación de la tabla del hallazgo {p0}. Prueba el motor WeasyPrint.', p0=finding))
        if len(first) != 1 or first != last:
            raise table_error(finding)
        page = first[0]
        for token in (start, end):
            offset = pages[page].index(token)
            if any(top < 0 or bottom > heights[page] for _, top, bottom in character_pages[page][offset:offset+len(token)]):
                raise table_error(finding)


def prune_pdf_uri_break_links(document):
    """Remove zero-area annotations inherited by generated URI break boxes.

    WeasyPrint inherits the enclosing link on every wbr and its ::before
    box. These have no hit area, while the enclosing anchor already covers
    each visible line. Keeping them adds two useless PDF annotations per
    character. Leave all visible link rectangles and exact targets intact.
    """
    removed = 0
    for page in document.pages:
        retained = []
        for link in page.links:
            kind, target, rectangle, box = link
            element = getattr(box, 'element', None)
            # WeasyPrint's PDF writer consumes (x1, y1, x2, y2).
            empty = rectangle[0] == rectangle[2] or rectangle[1] == rectangle[3]
            if (kind in {'internal', 'external'} and empty
                    and element is not None
                    and element.get('data-rg-pdf-uri-break') == 'true'
                    and getattr(box, 'element_tag', None) in {'wbr', 'wbr::before'}):
                removed += 1
            else:
                retained.append(link)
        page.links[:] = retained
    return removed
