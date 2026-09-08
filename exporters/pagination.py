"""Word pagination: keep a table together when it fits on one page."""
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def keep_table_together(table):
    # cantSplit alone only protects individual rows. keepNext chains every
    # row to the next one, ending at the table boundary (not the next finding).
    rows = table.rows
    for row_index, row in enumerate(rows):
        props = row._tr.get_or_add_trPr()
        if props.find(qn("w:cantSplit")) is None:
            props.append(OxmlElement("w:cantSplit"))
        for cell in row.cells:
            for i, paragraph in enumerate(cell.paragraphs):
                paragraph.paragraph_format.keep_together = True
                paragraph.paragraph_format.keep_with_next = row_index < len(rows)-1 or i < len(cell.paragraphs)-1
