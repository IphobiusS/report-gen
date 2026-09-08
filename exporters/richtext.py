"""Convert the shared, sanitized Markdown tree to native Word elements."""
import re
from lxml import html
from docx.shared import Cm, Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from resources import local_image
from safe_markup import md
from .pagination import keep_table_together


def write_markdown(document, text, root, code_block):
    tree = html.fragment_fromstring(str(md(text, img_base="")), create_parent="div")
    available = document.sections[-1].page_width - document.sections[-1].left_margin - document.sections[-1].right_margin

    def picture(node, paragraph=None):
        if not node.get("src"):
            return
        path = local_image(node.get("src"), root)
        paragraph = paragraph or document.add_paragraph()
        width = min(available, Cm(15))
        requested = re.search(r"width:\s*([\d.]+)(%|cm|mm|in|px|pt)", node.get("style", ""))
        if requested:
            value, unit = float(requested[1]), requested[2]
            width = min(available, int(available * value / 100) if unit == "%" else int(Cm(value * {"cm": 1, "mm": .1, "in": 2.54, "px": 2.54/96, "pt": 2.54/72}[unit])))
        from PIL import Image
        with Image.open(path) as im:
            # Fit portrait screenshots on a page while preserving aspect ratio.
            max_height = document.sections[-1].page_height - document.sections[-1].top_margin - document.sections[-1].bottom_margin - Cm(2)
            width = min(width, int(max_height * im.width / im.height))
        shape = paragraph.add_run().add_picture(str(path), width=max(Cm(.1), width))
        shape._inline.docPr.set("descr", node.get("alt", ""))
        paragraph.paragraph_format.keep_with_next = True

    def inline(node, paragraph, bold=False, italic=False, code=False):
        def add(value, parent=None):
            if not value: return
            run = paragraph.add_run(value)
            run.bold = bold; run.italic = italic
            if code:
                run.font.name = "Consolas"; run.font.size = Pt(9)
            if parent is not None:
                parent.append(run._r)
        add(node.text)
        for child in node:
            tag = child.tag
            if tag == "br": paragraph.add_run().add_break()
            elif tag == "img": picture(child, paragraph)
            elif tag == "a" and child.get("href"):
                link = OxmlElement("w:hyperlink")
                link.set(qn("r:id"), paragraph.part.relate_to(child.get("href"), RT.HYPERLINK, is_external=True))
                run = OxmlElement("w:r"); props = OxmlElement("w:rPr")
                style = OxmlElement("w:rStyle"); style.set(qn("w:val"), "Hyperlink"); props.append(style); run.append(props)
                text_node = OxmlElement("w:t"); text_node.text = child.text_content(); run.append(text_node); link.append(run); paragraph._p.append(link)
            else:
                inline(child, paragraph, bold or tag in {"b", "strong"}, italic or tag in {"i", "em"}, code or tag == "code")
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

    def block(node, depth=0):
        tag = node.tag
        if tag in {"ul", "ol"}:
            number_id = list_numbering(tag == "ol", int(node.get("start", "1")))
            for item in node:
                p = document.add_paragraph()
                p.paragraph_format.left_indent = Cm(.65 * (depth+1)); p.paragraph_format.first_line_indent = Cm(-.4)
                pr = p._p.get_or_add_pPr().get_or_add_numPr(); pr.get_or_add_ilvl().val = 0; pr.get_or_add_numId().val = number_id
                p.add_run(item.text or "")
                first = True
                for child in item:
                    if child.tag in {"ul", "ol"}: block(child, depth+1)
                    elif child.tag == "p":
                        target = p if first else document.add_paragraph()
                        inline(child, target); first = False
                    else:
                        wrapper = html.Element("span"); wrapper.append(html.fromstring(html.tostring(child, with_tail=False)))
                        inline(wrapper, p)
                    if child.tail: p.add_run(child.tail)
        elif tag == "pre":
            code_block(node.text_content().removesuffix("\n"))
        elif tag == "table":
            rows = node.xpath("./tr|./thead/tr|./tbody/tr|./tfoot/tr")
            cols = max([len(row) for row in rows]+[1])
            table = document.add_table(rows=0, cols=cols); table.style = "Table Grid"; table.autofit = False
            widths = [int(available / cols)] * cols
            for col, width in zip(table.columns, widths): col.width = width
            width_el = table._tbl.tblPr.find(qn("w:tblW")); width_el.set(qn("w:type"), "dxa"); width_el.set(qn("w:w"), str(int(available/635)))
            for row in rows:
                cells = table.add_row().cells
                for i, cell in enumerate(row):
                    cells[i].width = widths[i]; inline(cell, cells[i].paragraphs[0], bold=cell.tag == "th")
                if any(cell.tag == "th" for cell in row):
                    repeat = OxmlElement("w:tblHeader"); table.rows[-1]._tr.get_or_add_trPr().append(repeat)
            keep_table_together(table)
            document.add_paragraph()
        elif tag == "figure":
            for child in node:
                if child.tag == "img": picture(child)
                elif child.tag == "figcaption":
                    p = document.add_paragraph(style="Caption"); inline(child, p)
        elif tag == "img": picture(node)
        elif tag == "blockquote":
            for child in node: block(child, depth)
        elif tag == "hr": document.add_paragraph(" ")
        elif tag in {"p", "h1", "h2", "h3", "h4", "h5", "h6"}:
            p = document.add_paragraph(style=f"Heading {min(int(tag[1]), 4)}" if tag.startswith("h") else None)
            inline(node, p)
        else:
            p = document.add_paragraph(); inline(node, p)
    if tree.text and tree.text.strip(): document.add_paragraph(tree.text)
    for node in tree: block(node)
