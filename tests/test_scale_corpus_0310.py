"""The measured image-heavy corpus must contain reproducible, distinct assets."""
import importlib.util
from pathlib import Path
import zipfile

from PIL import Image
import pytest
from exporters.markdown import parse_exported

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("scale_worker", ROOT / "scripts/benchmark-workspace.py")
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def request():
    return {"slug": "synthetic-scale", "image_mode": "distinct", "data": {
        "meta": {"report_title": "Synthetic scale", "lang": "es", "theme": "corporativo"},
        "report": {"sections": [{"key": "findings"}]},
        "findings": [{"id": f"F{i}", "uid": f"00000000-0000-4000-8000-{i:012d}", "mode": "vuln",
                      "title": f"SYNTHETIC_FINDING_{i}", "description_md": "Fictional test case.",
                      "evidence_uids": [f"10000000-0000-4000-8000-{i:012d}"]} for i in (1, 2)],
        "evidence": [{"uid": f"10000000-0000-4000-8000-{i:012d}", "title": f"Evidence {i}",
                      "src": "img/synthetic.png", "caption": "Synthetic test image."} for i in (1, 2)]}}


def test_image_heavy_corpus_is_reproducible_and_does_not_reuse_one_pixel(tmp_path):
    first = worker.seed(tmp_path / "first", request())
    second = worker.seed(tmp_path / "second", request())
    assert first["corpusSha256"] == second["corpusSha256"]
    assert first["uniqueImageHashes"] == 2
    assert first["imageBytes"] > 10_000
    assert first["images"] == second["images"]
    before = (tmp_path / "first/projects/synthetic-scale/engagement.yaml").read_bytes()
    with pytest.raises(ValueError, match="preserved"):
        worker.seed(tmp_path / "first", request())
    assert (tmp_path / "first/projects/synthetic-scale/engagement.yaml").read_bytes() == before
    for row in first["images"]:
        with Image.open(tmp_path / "first/projects/synthetic-scale" / row["path"]) as image:
            assert image.size == (800, 450)


def test_measured_export_preserves_both_images_and_existing_measurements(tmp_path):
    corpus = worker.seed(tmp_path / "workspace", request())
    source = tmp_path / "workspace/projects/synthetic-scale/engagement.yaml"
    result = worker.export_one(source, "md", tmp_path / "exports")
    assert result["checks"]["images_verified"] == 2
    assert all(result[key] >= 0 for key in ("captureMs", "exportMs", "verificationMs"))
    artifact = tmp_path / "exports" / result["artifact"]
    with zipfile.ZipFile(artifact) as package:
        assert all(row["path"] in package.namelist() for row in corpus["images"])
        text = parse_exported(package.read("report.md").decode()).text_content()
        assert "SYNTHETIC_FINDING_1" in text
        assert "SYNTHETIC_FINDING_2" in text
    before = worker.digest(artifact)
    with pytest.raises(ValueError, match="preserved"):
        worker.export_one(source, "md", tmp_path / "exports")
    assert worker.digest(artifact) == before
