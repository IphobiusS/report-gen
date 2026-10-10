"""The external acceptance kit contains real documents, never fabricated observations."""
import csv
import hashlib
import importlib.util
from pathlib import Path
import zipfile

from lxml import etree
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare_acceptance", ROOT / "scripts/prepare-external-acceptance.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_prepared_documents_and_blank_sessions_remain_unaccepted(tmp_path):
    result = module.prepare(tmp_path / "kit")
    assert result["word_native"] == result["human_sessions"] == "not_run"
    assert result["human_observations_recorded"] == 0
    assert {row["case"] for row in result["documents"]} == {"quality-lab", "pending-severity", "nimbus", "long-content"}
    for row in result["documents"]:
        path = tmp_path / "kit" / row["docx"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["docx_sha256"]
        with zipfile.ZipFile(path) as package:
            document = etree.fromstring(package.read("word/document.xml"))
            assert document.xpath('//*[local-name()="p"]')
    with zipfile.ZipFile(tmp_path / "kit/word-input/long-content.docx") as package:
        text = package.read("word/document.xml").decode()
        assert "ASSET-001" in text and "ASSET-080" in text
        assert "COMANDO_LITERAL_WORD_0270" in text
    with (tmp_path / "kit/human-sessions.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 15
    assert all(not row["outcome"] and not row["seconds"] for row in rows)


def test_preparation_preserves_existing_evidence(tmp_path):
    marker = tmp_path / "existing.json"
    marker.write_text('{"human_observations_recorded": 1}')
    with pytest.raises(ValueError, match="empty output"):
        module.prepare(tmp_path)
    assert marker.read_text() == '{"human_observations_recorded": 1}'
