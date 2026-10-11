"""Convert the shared, sanitized Markdown tree to native Word elements."""
import re
from copy import deepcopy
from lxml import html
from docx.shared import Cm, Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from safe_markup import md, ordered_list_start
from .pagination import keep_table_together
from .images import word_image, fit_width, figure_space, paragraph_width, align_inline_picture
from report_layout import table_layout


def write_markdown(document, text, root, code_block, keep_tables=True, retest=False, column_weights=None):
    tree = html.fragment_fromstring(str(md(text, img_base="")), create_parent="div")
    available = document.sections[-1].page_width - document.sections[-1].left_margin - document.sections[-1].right_margin

    def picture(node, paragraph=None, parent=None, caption=None, href=None):
        if not node.get("src"):
            return
        source, size = word_image(node.get("src"), root)
        paragraph = paragraph or document.add_paragraph()
        containing_width = paragraph_width(document, paragraph)
        width = min(containing_width, Cm(15))
        requested = re.search(r"width:\s*([\d.]+)(%|cm|mm|in|px|pt)", node.get("style", ""))
        if requested:
            value, unit = float(requested[1]), requested[2]
            factor = containing_width / 100 if unit == "%" else Cm(1) * {"cm": 1, "mm": .1, "in": 2.54, "px": 2.54/96, "pt": 2.54/72}[unit]
            # Clamp before integer conversion: valid decimal syntax can exceed
            # floating-point range, while the page width is always finite.
            width = int(min(containing_width, value * factor))
        width = fit_width(document, size, width, figure_space(document, caption if caption is not None else node.get('alt', ''), width=containing_width))
        run = paragraph.add_run()
        shape = align_inline_picture(run.add_picture(source, width=max(Cm(.1), width)))
        if parent is not None: parent.append(run._r)
        shape._inline.docPr.set("descr", node.get("alt", ""))
        if href:
            if href.startswith('#'):
                from urllib.parse import unquote
                from .navigation import reference_name
                href = '#' + reference_name(unquote(href[1:]))
            link = OxmlElement('a:hlinkClick')
            link.set(qn('r:id'), paragraph.part.relate_to(href, RT.HYPERLINK, is_external=True))
            shape._inline.docPr.append(link)
        paragraph.paragraph_format.keep_together = True
        paragraph.paragraph_format.keep_with_next = True

    def inline(node, paragraph, bold=False, italic=False, code=False, parent=None):
        def add(value):
            if not value: return
            run = paragraph.add_run(value)
            run.bold = bold; run.italic = italic
            if code:
                run.font.name = "DejaVu Sans Mono"; run.font.size = Pt(9)
            if parent is not None:
                if parent.tag == qn('w:hyperlink'):
                    style = OxmlElement('w:rStyle'); style.set(qn('w:val'), 'Hyperlink')
                    run._r.get_or_add_rPr().append(style)
                parent.append(run._r)
        def linebreak():
            run = paragraph.add_run(); run.add_break()
            if parent is not None: parent.append(run._r)
        add(node.text)
        for child in node:
            tag = child.tag
            if tag == "br": linebreak()
            elif tag == "img": picture(child, paragraph, parent)
            elif tag == "a" and child.get("href"):
                link = OxmlElement("w:hyperlink")
                href = child.get('href')
                if href.startswith('#'):
                    from urllib.parse import unquote
                    from .navigation import reference_name
                    link.set(qn('w:anchor'), reference_name(unquote(href[1:])))
                else:
                    link.set(qn("r:id"), paragraph.part.relate_to(href, RT.HYPERLINK, is_external=True))
                paragraph._p.append(link)
                inline(child, paragraph, bold, italic, code, parent=link)
            elif tag == "figcaption":
                linebreak()
                inline(child, paragraph, bold, italic, code, parent=parent)
            else:
                inline(child, paragraph, bold or tag in {"b", "strong"}, italic or tag in {"i", "em"}, code or tag == "code", parent=parent)
            add(child.tail)

    def list_numbering(ordered, start=1):
        numbering = document.part.numbering_part.element
        ids = [int(x.get(qn("w:abstractNumId"))) for x in numbering.findall(qn("w:abstractNum"))]
        abstract_id = max(ids + [-1]) + 1
        abstract = OxmlElement("w:abstractNum"); abstract.set(qn("w:abstractNumId"), str(abstract_id))
        lvl = OxmlElement("w:lvl"); lvl.set(qn("w:ilvl"), "0")
        for tag, value in [("start", str(start)), ("numFmt", "decimal" if ordered else "bullet"), ("lvlText", "%1." if ordered else "•")]:
            el = OxmlElement("w:"+tag); el.set(qn("w:val"), value); lvl.append(el)
        abstract.append(lvl); numbering.append(abstract)
        return numbering.add_num(abstract_id).numId

    figure_wrappers = {}

    def paragraph_parts(node, wrappers=()):
        # The shared Markdown tree promotes images to block figures even
        # inside links/emphasis in sentences and list paragraphs. Split at any
        # inline depth, retaining formatting on either side and on the caption.
        fragment = html.Element(node.tag, dict(node.attrib))
        fragment.text = node.text
        for child in node:
            if child.tag == 'figure':
                if fragment.text_content().strip() or len(fragment):
                    yield fragment
                figure_wrappers[child] = wrappers
                yield child
                fragment = html.Element(node.tag, dict(node.attrib))
                fragment.text = child.tail
            elif child.xpath('.//figure'):
                for part in paragraph_parts(child, wrappers + (child,)):
                    if part.tag == 'figure':
                        if fragment.text_content().strip() or len(fragment):
                            yield fragment
                        yield part
                        fragment = html.Element(node.tag, dict(node.attrib))
                    else:
                        fragment.append(part)
                if len(fragment):
                    fragment[-1].tail = (fragment[-1].tail or '') + (child.tail or '')
                else:
                    fragment.text = (fragment.text or '') + (child.tail or '')
            else:
                fragment.append(deepcopy(child))
        if fragment.text_content().strip() or len(fragment):
            yield fragment

    def block(node, depth=0, list_paragraph=None):
        tag = node.tag
        if tag == 'p' and node.xpath('.//figure'):
            for part in paragraph_parts(node):
                block(part, depth)
            return
        if tag in {"ul", "ol"}:
            number_id = list_numbering(tag == "ol", ordered_list_start(node) if tag == 'ol' else 1)
            for item in node:
                p = document.add_paragraph()
                p.paragraph_format.left_indent = Cm(.65 * (depth+1)); p.paragraph_format.first_line_indent = Cm(-.4)
                pr = p._p.get_or_add_pPr().get_or_add_numPr(); pr.get_or_add_ilvl().val = 0; pr.get_or_add_numId().val = number_id
                started = bool((item.text or '').strip())
                if started: p.add_run(item.text)
                current = p
                def continuation():
                    paragraph = document.add_paragraph()
                    paragraph.paragraph_format.left_indent = Cm(.65 * (depth+1))
                    return paragraph
                for child in item:
                    if child.tag in {"ul", "ol"}:
                        block(child, depth+1); current = None; started = True
                    elif child.tag == "p":
                        for part in paragraph_parts(child):
                            if part.tag == 'figure':
                                block(part, depth+1, p if not started else None)
                            else:
                                target = p if not started else continuation()
                                inline(part, target)
                            started = True; current = None
                    elif child.tag in {'pre', 'table', 'blockquote', 'figure', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
                        block(child, depth+1, p if child.tag == 'figure' and not started else None)
                        current = None; started = True
                    elif child.xpath('.//figure'):
                        wrapper = html.Element('p')
                        wrapper.append(deepcopy(child)); wrapper[0].tail = None
                        for part in paragraph_parts(wrapper):
                            if part.tag == 'figure':
                                block(part, depth+1, p if not started else None); current = None
                            else:
                                if current is None: current = continuation()
                                inline(part, current)
                            started = True
                    else:
                        if current is None: current = continuation()
                        wrapper = html.Element("span"); wrapper.append(html.fromstring(html.tostring(child, with_tail=False)))
                        inline(wrapper, current); started = True
                    if child.tail and (child.tail.strip() or current is not None):
                        if current is None: current = continuation()
                        current.add_run(child.tail); started = True
        elif tag == "pre":
            p = code_block(node.text_content().removesuffix("\n"))
            if depth: p.paragraph_format.left_indent = Cm(.65 * depth)
        elif tag == "table":
            rows = node.xpath("./tr|./thead/tr|./tbody/tr|./tfoot/tr")
            cols = max([len(row) for row in rows]+[1])
            table = document.add_table(rows=0, cols=cols); table.style = "Table Grid"; table.autofit = False
            shares, _ = table_layout([[cell.text_content() for cell in row] for row in rows], column_weights)
            widths = [int(available * share / 100) for share in shares]
            for col, width in zip(table.columns, widths): col.width = width
            width_el = table._tbl.tblPr.find(qn("w:tblW")); width_el.set(qn("w:type"), "dxa"); width_el.set(qn("w:w"), str(int(available/635)))
            for row in rows:
                cells = table.add_row().cells
                for i, cell in enumerate(row):
                    cells[i].width = widths[i]; inline(cell, cells[i].paragraphs[0], bold=cell.tag == "th")
                if any(cell.tag == "th" for cell in row):
                    repeat = OxmlElement("w:tblHeader"); table.rows[-1]._tr.get_or_add_trPr().append(repeat)
            # As in the summary/inventory exporter, long tables must flow into
            # the remaining page space. Chaining 80+ rows with keepNext forces
            # a mostly empty preceding page before Word/Writer finally splits.
            keep_table_together(table, whole=keep_tables and len(table.rows) <= 24)
            document.add_paragraph()
        elif tag == "figure":
            if retest and document.paragraphs:
                document.paragraphs[-1].paragraph_format.keep_with_next = True
            caption = ' '.join(node.xpath('./figcaption//text()'))
            wrappers = figure_wrappers.get(node, ())
            href = next((part.get('href') for part in reversed(wrappers)
                         if part.tag == 'a' and part.get('href')), None)
            for child in node:
                if child.tag == "img":
                    picture_paragraph = list_paragraph or document.add_paragraph()
                    if depth:
                        picture_paragraph.paragraph_format.left_indent = Cm(.65 * depth)
                    picture(child, picture_paragraph, caption=caption, href=href)
                elif child.tag == "figcaption":
                    contents = deepcopy(child)
                    for wrapper in reversed(wrappers):
                        outer = html.Element(wrapper.tag, dict(wrapper.attrib))
                        outer.text = contents.text
                        for nested in list(contents): outer.append(nested)
                        contents = html.Element('span'); contents.append(outer)
                    p = document.add_paragraph(style="Caption"); inline(contents, p)
                    p.paragraph_format.keep_together = True
                    if depth: p.paragraph_format.left_indent = Cm(.65 * depth)
        elif tag == "img": picture(node)
        elif tag == "blockquote":
            for child in node: block(child, depth)
        elif tag == "hr": document.add_paragraph(" ")
        elif tag in {"p", "h1", "h2", "h3", "h4", "h5", "h6"}:
            p = document.add_paragraph(style=f"Heading {min(int(tag[1]), 4)}" if tag.startswith("h") else None)
            if depth: p.paragraph_format.left_indent = Cm(.65 * depth)
            # A bold list label (e.g. generated affected assets) belongs with
            # the first item; otherwise it can be orphaned at the page bottom.
            if (tag == 'p' and not (node.text or '').strip() and len(node) == 1
                    and node[0].tag in {'strong', 'b'} and not (node[0].tail or '').strip()
                    and node.getnext() is not None and node.getnext().tag in {'ul', 'ol'}):
                p.paragraph_format.keep_with_next = True
            if retest and node.getprevious() is not None and node.getprevious().tag == 'h3':
                p.paragraph_format.keep_with_next = True
            if (tag == 'p' and node.getnext() is not None and node.getnext().tag == 'pre'
                    and len(node.text_content()) <= 160 and node.xpath('.//strong|.//b')):
                p.paragraph_format.keep_with_next = True
            inline(node, p)
        else:
            p = document.add_paragraph(); inline(node, p)
    if tree.text and tree.text.strip(): document.add_paragraph(tree.text)
    for node in tree: block(node)
