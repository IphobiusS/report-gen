"""Severity labels remain a single shaded unit after long finding titles."""
from copy import deepcopy

from docx import Document
from docx.oxml.ns import qn
import pytest

import engine
import export


@pytest.mark.parametrize("lang,title", [
    ("es", "La consulta de conectores alcanza la administración local y expone configuración interna"),
    ("en", "Connector checks reach the local administration service and disclose internal configuration"),
])
@pytest.mark.parametrize("severity", ["critical", "high", "medium", "low", "info"])
def test_long_finding_title_keeps_severity_padding_with_label(tmp_path, lang, title, severity):
    data = {
        "meta": {"lang": lang, "report_title": "Severity label regression", "theme": "corporativo"},
        "report": {"sections": [{"key": "findings"}]},
        "findings": [{"id": "F01", "title": title, "severity": severity,
                      "description_md": "A complete description follows the finding heading."}],
    }
    source = deepcopy(data)
    locale = engine.load_lang(lang)
    target = tmp_path / "report.docx"
    export.to_docx(data, data["meta"], locale, tmp_path, target)
    document = Document(target)
    heading = next(p for p in document.paragraphs if p.style.name == "Heading 2")
    shaded = [run for run in heading.runs
              if run._r.rPr is not None and run._r.rPr.find(qn("w:shd")) is not None]

    assert len(shaded) == 1
    chip = shaded[0]
    assert chip.text.strip() == locale["severity"][severity]
    # A breakable padding space can stay painted at the old line while the
    # actual label moves. All shading must travel with visible label text.
    assert " " not in chip.text
    assert chip.text.startswith("\u00a0") and chip.text.endswith("\u00a0")
    # python-docx creates fresh Run wrappers on every access; locate by XML.
    preceding = chip._r.getprevious()
    assert preceding is not None and "".join(preceding.itertext()).strip() == ""
    assert preceding.find(".//" + qn("w:shd")) is None
    assert title in heading.text
    assert data == source
