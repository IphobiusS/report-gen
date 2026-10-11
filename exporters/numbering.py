"""Native Word lists, with recalculable fields for Writer's wide counters.

Writer imports native numbering starts as 16-bit values. Exceptional lists
whose starting ordinal exceeds 65535 use editable SEQ fields instead; ordinary
lists retain automatic paragraph numbering. The field result is cached for
readers that do not evaluate fields and is never a rasterized label.
"""
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt


class WordList:
    def __init__(self, document, ordered, start=1, count=1, depth=0, offset=0):
        self.start = start
        self.sequence = ordered and start > 65535
        numbering = document.part.numbering_part.element
        ids = [int(x.get(qn('w:abstractNumId'))) for x in numbering.findall(qn('w:abstractNum'))]
        abstract = OxmlElement('w:abstractNum')
        abstract_id = max(ids + [-1]) + 1
        abstract.set(qn('w:abstractNumId'), str(abstract_id))
        level = OxmlElement('w:lvl'); level.set(qn('w:ilvl'), '0')
        values = [('start', str(1 if self.sequence else start)),
                  ('numFmt', 'none' if self.sequence else 'decimal' if ordered else 'bullet')]
        if self.sequence:
            values.append(('suff', 'nothing'))
        values.append(('lvlText', '' if self.sequence else '%1.' if ordered else '•'))
        for tag, value in values:
            element = OxmlElement('w:' + tag); element.set(qn('w:val'), value); level.append(element)
        abstract.append(level); numbering.append(abstract)
        self.num_id = numbering.add_num(abstract_id).numId
        self.indent = Cm(.65 * (depth + 1)) + offset
        self.hanging = Cm(.4)
        digits = len(str(start + max(0, count - 1))) if ordered else 1
        # Wide native counters also need enough room before their text. Reserve
        # conservative glyph space at the actual body size without shrinking it.
        if ordered:
            size = document.styles['Normal'].font.size or Pt(11)
            self.hanging = max(self.hanging, Pt((digits + .5) * size.pt * .65 + size.pt * .4))
            self.indent += self.hanging - Cm(.4)
        self.extra_indent = self.indent - Cm(.65 * (depth + 1)) - offset

    def add(self, paragraph, index):
        paragraph.paragraph_format.left_indent = self.indent
        paragraph.paragraph_format.first_line_indent = -self.hanging
        if self.hanging > Cm(.4) or self.sequence:
            paragraph.paragraph_format.tab_stops.add_tab_stop(self.indent)
        properties = paragraph._p.get_or_add_pPr().get_or_add_numPr()
        properties.get_or_add_ilvl().val = 0
        properties.get_or_add_numId().val = self.num_id
        if not self.sequence:
            return
        field = OxmlElement('w:fldSimple')
        switch = f'\\r {self.start}' if index == 0 else '\\n'
        field.set(qn('w:instr'), f' SEQ RGList{self.num_id} {switch} \\* ARABIC ')
        run = OxmlElement('w:r'); text = OxmlElement('w:t'); text.text = str(self.start + index)
        run.append(text); field.append(run); paragraph._p.append(field)
        paragraph.add_run('.\t')
