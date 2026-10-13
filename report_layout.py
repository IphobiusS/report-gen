"""Layout hints shared by PDF/HTML and Word; assessment text stays untouched."""
import math
import re
from lxml import html


WORKFLOW_COLUMNS = {
    'rg_assets': [14, 32, 16, 38],
    'rg_coverage': [25, 29, 15, 31],
    'rg_retest': [38, 17, 15, 15, 15],
}


def table_layout(rows, weights=None):
    """Content-aware column shares, not equal widths or report-specific IDs.

    Saturating text demand leaves room for short labels while giving prose
    more space. Only short cells that fit their share receive nowrap hints.
    Explicit workflow proportions take precedence. This is a layout heuristic,
    not a promise that an arbitrary table can fit a page.
    """
    columns = max((len(row) for row in rows), default=0)
    if not columns:
        return [], []
    values = [[re.sub(r'\s+', ' ', str(row[i] or '')).strip()
               for row in rows if i < len(row)] for i in range(columns)]
    demands, minimums = [], []
    for cells in values:
        length = max((len(value) for value in cells), default=0)
        word = max((len(w) for value in cells for w in value.split()), default=0)
        demands.append(max(8, min(60, max(min(word, 24), math.sqrt(length * 12)))))
        # Reserve room for ordinary words (including bold row labels) before
        # distributing the remaining width. Very long URLs/hashes may wrap.
        minimums.append(min(25, (min(word, 20) * 5.2 + 14) / 4.65))
    if weights and len(weights) == columns and all(w > 0 for w in weights):
        demands = weights
    total = sum(demands)
    shares = [100 * demand / total for demand in demands]
    if not weights:
        scale = min(1, 90 / sum(minimums))
        minimums = [value * scale for value in minimums]
        remaining = set(range(columns))
        while remaining:
            small = {i for i in remaining if shares[i] < minimums[i]}
            if not small:
                break
            for i in small:
                shares[i] = minimums[i]
            remaining -= small
            budget = 100 - sum(shares[i] for i in range(columns) if i not in remaining)
            demand = sum(demands[i] for i in remaining)
            for i in remaining:
                shares[i] = budget * demands[i] / demand
    compact = [bool(cells) and all(len(v) <= 12 for v in cells)
               and shares[i] >= (max(map(len, cells), default=0) * 4.7 + 14) / 4.9
               for i, cells in enumerate(values)]
    return shares, compact


def html_rows(table):
    return table.xpath('./tr|./thead/tr|./tbody/tr|./tfoot/tr')


def prepare_html(source):
    tree = html.document_fromstring(source)
    for table in tree.xpath('//table[not(@class)]'):
        table.set('class', 'md-table')
    for block in tree.xpath('//pre'):
        label = block.getprevious()
        if (label is not None and label.tag == 'p' and len(label.text_content()) <= 160
                and label.xpath('.//strong|.//b')):
            label.set('class', 'rg-code-label')
    for table in tree.xpath('//table'):
        if not set((table.get('class') or '').split()) & {'md-table', 'scope', 'contacts'}:
            continue
        rows = html_rows(table)
        cells = [[c for c in row if c.tag in {'th', 'td'}] for row in rows]
        # Leave merged layouts alone; column positions need span-aware mapping.
        if not cells or any(c.get('colspan') or c.get('rowspan') for row in cells for c in row):
            continue
        weights = next((WORKFLOW_COLUMNS[e.get('id')] for e in table.iterancestors()
                        if e.get('id') in WORKFLOW_COLUMNS), None)
        shares, compact = table_layout([[c.text_content() for c in row] for row in cells], weights)
        for group in table.xpath('./colgroup'):
            table.remove(group)
        group = html.Element('colgroup')
        for width in shares:
            group.append(html.Element('col', style=f'width:{width:.4f}%'))
        table.insert(0, group)
        table.set('class', table.get('class', '') + ' rg-content-table')
        for row in cells:
            for i, cell in enumerate(row):
                if compact[i]:
                    cell.set('class', 'rg-compact-cell')
    for section in tree.xpath('//*[@id="rg_retest"]'):
        group = None
        for child in list(section):
            if child.tag == 'h3':
                group = html.Element('div', {'class': 'retest-entry'})
                section.insert(section.index(child), group)
            if group is not None:
                group.append(child)
        # Verification summaries follow the same h3 convention as narrative
        # retest notes, but their tables must paginate by row. Keeping an
        # entire summary together can abandon most of the preceding page.
        for group in section.xpath('./div[@class="retest-entry"]'):
            if group.xpath('./table'):
                group.set('class', 'retest-entry retest-table-group')
    return html.tostring(tree, encoding='unicode', method='html', doctype='<!DOCTYPE html>')
