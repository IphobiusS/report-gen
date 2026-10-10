"""Actual DOCX metadata describes the approved report, not its Word template."""
from copy import deepcopy
from zipfile import ZipFile

from docx import Document
import pytest

import export
import workflows
from wizard import dump_yaml


@pytest.mark.parametrize("title,assessor,language", [
    ("Evaluación sintética de autorización", "Equipo ficticio", "es"),
    ("Synthetic report " + "A" * 300, "", "en"),
])
def test_actual_word_export_has_report_metadata_without_inherited_template_dates(
    tmp_path, title, assessor, language
):
    data = workflows.normalize({
        "meta": {"report_title": title, "assessor": assessor,
                 "lang": language, "theme": "serio"},
        "report": {"sections": [{"key": "findings"}]},
        "findings": [{"id": "F01", "title": "Synthetic finding", "mode": "vuln",
                      "severity": "info", "cvss": 0, "description_md": "BODY-CANARY-0231"}],
    })
    before = deepcopy(data)
    source = tmp_path / "engagement.yaml"
    dump_yaml(data, source)
    source_bytes = source.read_bytes()
    output = export.export(source, "docx", tmp_path / "report.docx")
    document = Document(output)
    properties = document.core_properties
    assert properties.title == title[:255]
    assert properties.author == assessor
    assert properties.language == language
    assert properties.created is None and properties.modified is None
    assert not properties.comments and not properties.last_modified_by
    assert "BODY-CANARY-0231" in "\n".join(p.text for p in document.paragraphs)
    with ZipFile(output) as package:
        assert package.testzip() is None
        core = package.read("docProps/core.xml").decode()
        assert "2013-12-23" not in core and "python-docx" not in core
    assert data == before and source.read_bytes() == source_bytes
