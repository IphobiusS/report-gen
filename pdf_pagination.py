"""Paginate finding tables while preserving headers and rejecting clipped cells."""
from error_messages import message as backend_message
from diagnostic_locations import DiagnosticError
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
    return DiagnosticError(
        backend_message('Hallazgo {p0}: una celda, fila o encabezado de tabla no cabe en el área imprimible o perdió su encabezado al paginar. Reduce el contenido indivisible o el tamaño de la imagen, o divide esa celda. Las tablas con varias filas pueden continuar entre páginas. El PDF no se ha generado y la salida anterior se conserva.', p0=finding),
        code='export.pdf.table_oversized',
        location={'operation': 'export', 'format': 'pdf',
                  'finding_id': finding if finding != 'sin ID' else None},
    )


def relax_oversized_rows(document):
    """Relax only finding tables and body rows proven to need pagination.

    Short tables and ordinary rows retain their keep-together policy. The
    first layout identifies actual fragments, including nested tables; one
    fresh layout applies all changes together. The compact finding identity
    and repeated header/footer rows remain protected.
    """
    candidates = {}
    for number, page in enumerate(document.pages):
        def walk(box, finding=False, intro=False, repeated_group=False):
            element = getattr(box, 'element', None)
            if element is not None:
                classes = (element.get('class') or '').split()
                finding = finding or 'finding' in classes
                intro = intro or 'finding-intro' in classes
                repeated_group = repeated_group or element.tag in {'thead', 'tfoot'}
            kind = type(box).__name__
            eligible = (kind == 'TableRowBox' and not repeated_group
                        or kind in {'TableBox', 'InlineTableBox'} and finding)
            if (eligible and element is not None and not intro
                    and box.style['break_inside'] in {'avoid', 'avoid-page'}):
                record = candidates.setdefault(element, {'pages': set(), 'oversized': False})
                record['pages'].add(number)
                record['oversized'] |= box.height > page._page_box.height + 2
            for child in box.all_children():
                walk(child, finding, intro, repeated_group)

        walk(page._page_box)
    changed = False
    for element, record in candidates.items():
        if len(record['pages']) > 1 or record['oversized']:
            element.set('style', (element.get('style') or '') +
                        ';break-inside:auto!important;page-break-inside:auto!important')
            changed = True
    return changed


def verify_finding_tables(document):
    """Verify final page geometry, repeated headers and compact identities.

    A table may occupy several pages. Every fragment must remain printable,
    including its cells, text and replaced content; headers must survive each
    body fragment. Only the finding identity remains indivisible. WeasyPrint's
    private layout integration is isolated here and covered by real PDF tests.
    """
    identities = {}
    for number, page in enumerate(document.pages):
        page_box = page._page_box
        top, bottom = page_box.content_box_y(), page_box.content_box_y() + page_box.height
        left, right = page_box.content_box_x(), page_box.content_box_x() + page_box.width

        def walk(box, finding=None, in_table=False):
            element = getattr(box, "element", None)
            classes = (element.get('class') or '').split() if element is not None else []
            if "finding" in classes:
                finding = element.get("id") or "sin ID"
            kind = type(box).__name__
            intro = 'finding-intro' in classes and kind == 'BlockBox'
            table = kind in {'TableBox', 'InlineTableBox'}
            in_table = in_table or table
            if finding and intro:
                pages = identities.setdefault(element, set())
                pages.add(number)
                if len(pages) > 1 or box.position_y + box.height > bottom + 2:
                    raise table_error(finding)
            if finding and in_table:
                # A row/cell may split, but an actual fragment, line or image
                # must never extend into the footer or outside the page.
                if kind in {'TableBox', 'InlineTableBox', 'TableRowBox',
                            'TableCellBox', 'TextBox', 'BlockReplacedBox',
                            'InlineReplacedBox'}:
                    if (box.position_y < top - 2 or box.position_y + box.height > bottom + 2
                            or box.position_x < left - 2 or box.position_x + box.width > right + 2):
                        raise table_error(finding)
                if table and element is not None:
                    headers = {node for node in element if node.tag == 'thead'}
                    if headers and any(getattr(child, 'element', None) is not None
                                       and child.element.tag in {'tbody', 'tr'}
                                       for child in box.children):
                        actual = {getattr(child, 'element', None) for child in box.children}
                        if not headers <= actual:
                            raise table_error(finding)
            for child in box.all_children():
                walk(child, finding, in_table)

        walk(page_box)


def verify_chromium_table_geometry(page):
    """Reject indivisible table objects that exceed the real print area.

    Cell markers prove the cell fragments, not whether Chromium sliced a tall
    image inside them. Measure replaced/inline-block objects at the report's
    actual content width, including repeated outer/nested headers and cell
    padding/borders. Check offsets as well as dimensions. Restore the exact
    body style before the PDF proof; no text row is made indivisible.
    """
    finding = page.evaluate("""async () => {
      await document.fonts.ready;
      const body = document.body, original = body.getAttribute('style');
      const pxPerMm = 96 / 25.4, pageWidth = 178 * pxPerMm, pageHeight = 259 * pxPerMm;
      try {
        body.style.setProperty('width', '178mm', 'important');
        const size = value => Number.parseFloat(value) || 0;
        const bodyStyle = getComputedStyle(body), bodyRect = body.getBoundingClientRect();
        const bodyLeft = bodyRect.left + size(bodyStyle.paddingLeft) + size(bodyStyle.borderLeftWidth);
        const bodyRight = bodyRect.right - size(bodyStyle.paddingRight) - size(bodyStyle.borderRightWidth);
        for (const table of document.querySelectorAll('.finding table')) {
          const finding = table.closest('.finding')?.id || 'sin ID';
          const head = table.tHead;
          if (head && head.getBoundingClientRect().height > pageHeight + 2) return finding;
          for (const node of table.querySelectorAll('*')) {
            if (node.classList.contains('rg-table-boundary')) continue;
            const style = getComputedStyle(node), cell = node.closest('td,th');
            const atomic = ['IMG', 'SVG', 'CANVAS', 'VIDEO', 'OBJECT', 'EMBED', 'IFRAME'].includes(node.tagName.toUpperCase())
              || ['inline-block', 'inline-table', 'inline-flex', 'inline-grid'].includes(style.display);
            if (!atomic || !cell || style.display === 'none') continue;
            const rect = node.getBoundingClientRect();
            if (!rect.width || !rect.height) continue;
            let availableHeight = pageHeight;
            for (let owner = cell.closest('table'); owner; owner = owner.parentElement?.closest('table')) {
              if (owner.tHead && !owner.tHead.contains(node)) availableHeight -= owner.tHead.getBoundingClientRect().height;
            }
            for (let container = cell; container; container = container.parentElement?.closest('td,th')) {
              const cellStyle = getComputedStyle(container);
              availableHeight -= size(cellStyle.paddingTop) + size(cellStyle.paddingBottom)
                + size(cellStyle.borderTopWidth) + size(cellStyle.borderBottomWidth);
            }
            const cellStyle = getComputedStyle(cell), cellRect = cell.getBoundingClientRect();
            const left = Math.max(bodyLeft, cellRect.left + size(cellStyle.paddingLeft) + size(cellStyle.borderLeftWidth));
            const right = Math.min(bodyRight, cellRect.right - size(cellStyle.paddingRight) - size(cellStyle.borderRightWidth));
            if (rect.height > availableHeight + 2 || rect.width > pageWidth + 2
                || rect.left < left - 2 || rect.right > right + 2) return finding;
          }
        }
        return null;
      } finally {
        if (original === null) body.removeAttribute('style');
        else body.setAttribute('style', original);
      }
    }""")
    if finding is not None:
        raise table_error(finding)


def mark_finding_tables(source):
    """Mark every cell boundary for the optional Chromium PDF preflight.

    Markers live only in a temporary document and are removed before the
    published PDF. Per-cell checks also catch an oversized middle row, which
    a first/last-table-only check would miss. Repeated header tokens are
    expected on every body page, rather than treated as duplicate content.
    """
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
            key = f"{prefix}T{len(checks)}"
            table.set('data-rg-pdf-table', key)
            protected = any('finding-intro' in (node.get('class') or '').split()
                            for node in table.iterancestors())
            check = {'finding': finding.get('id') or 'sin ID', 'key': key,
                     'protected': protected, 'cells': []}
            for index, cell in enumerate(cells):
                start, end = f"{key}S{index}END", f"{key}E{index}END"
                cell.set("style", (cell.get("style") or "") + ";position:relative")
                for token, edge in [(start, "top:0;left:0"), (end, "bottom:0;right:0")]:
                    marker = html.Element("span", {"class": "rg-table-boundary", "style": f"position:absolute;{edge};font-size:1px;line-height:1px;color:white;opacity:0.01"})
                    marker.text = token
                    cell.append(marker)
                header = cell.getparent().getparent().tag == 'thead'
                check['cells'].append({'start': start, 'end': end, 'header': header})
            checks.append(check)
    return html.tostring(tree, encoding="unicode", method="html"), checks


def verify_table_markers(pdf_bytes, checks, *, check_headers=True, margins=(0, 0), side_margins=(0, 0)):
    """Check every printable cell boundary and return multipage table keys.

    Ordinary finding tables can continue across pages; the compact identity
    cannot. Every marker must survive, and every repeated header must cover
    all pages occupied by body cells. Vertical and lateral margins are PDF
    points, supplied by the fixed A4 report layout in the Chromium renderer.
    """
    from io import BytesIO
    import pdfplumber
    with pdfplumber.open(BytesIO(pdf_bytes)) as document:
        character_pages = [[(letter, c["top"], c["bottom"], c["x0"], c["x1"]) for c in page.chars if c["size"] <= 1.0 for letter in c["text"]] for page in document.pages]
        heights = [page.height for page in document.pages]
        widths = [page.width for page in document.pages]
        pages = ["".join(c[0] for c in chars) for chars in character_pages]
    fragmented = []
    for check in checks:
        finding = check['finding']
        body_pages, header_pages, all_pages = set(), [], set()
        for cell in check['cells']:
            locations = []
            for edge, token in enumerate((cell['start'], cell['end'])):
                found = set()
                for page, text in enumerate(pages):
                    for match in re.finditer(re.escape(token), text):
                        found.add(page)
                        letters = character_pages[page][match.start():match.end()]
                        if any(top < margins[0] - 2 or bottom > heights[page] - margins[1] + 2
                               for _, top, bottom, _, _ in letters):
                            raise table_error(finding)
                        # The invisible token itself can be wider than a
                        # narrow numeric cell. Only its anchored edge proves
                        # the actual cell boundary; checking the entire token
                        # would reject otherwise printable narrow columns.
                        if (edge == 0 and letters[0][3] < side_margins[0] - 2
                                or edge == 1 and letters[-1][4] > widths[page] - side_margins[1] + 2):
                            raise table_error(finding)
                if not found:
                    raise DiagnosticError(backend_message(
                        'No se pudo verificar la paginación de la tabla del hallazgo {p0}. Prueba el motor WeasyPrint.', p0=finding),
                        code='export.pdf.table_pagination_unverified',
                        location={'operation': 'export', 'format': 'pdf',
                                  'finding_id': finding if finding != 'sin ID' else None})
                locations.append(found)
            first, last = locations
            if min(first) > max(last):
                raise table_error(finding)
            occupied = set(range(min(first), max(last) + 1))
            all_pages.update(occupied)
            if cell['header']:
                header_pages.append(first & last)
            else:
                body_pages.update(occupied)
        if check['protected'] and len(all_pages) > 1:
            raise table_error(finding)
        if check_headers and any(not body_pages <= seen for seen in header_pages):
            raise table_error(finding)
        if len(all_pages) > 1:
            fragmented.append(check['key'])
    return fragmented


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
