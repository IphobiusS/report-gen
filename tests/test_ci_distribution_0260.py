"""Release reproducibility and proof that parallel CI cannot silently lose tests."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ci = load_script("ci-pytest")
release = load_script("build-release")


def sample_receipts():
    nodes = [f"tests/test_{module}.py::test_{case}" for module in range(8) for case in range(5)]
    groups = ci.partition(nodes, 4, {"modules": {}})
    receipts = [{**group, "schema": 1, "shard_count": 4, "collection_count": len(nodes),
                 "collection_sha256": ci.fingerprint(nodes), "exit_code": 0,
                 "executed_count": len(group["nodeids"])} for group in groups]
    return nodes, receipts


def test_shards_balance_duration_preserve_modules_and_ignore_collection_order():
    weights = {"modules": {f"tests/test_{module}.py": {"cases": 5, "seconds": seconds}
                           for module, seconds in enumerate((100, 80, 60, 40, 30, 20, 10, 5))}}
    nodes, _ = sample_receipts()
    groups = ci.partition(nodes, 4, weights)
    assert groups == ci.partition(list(reversed(nodes)), 4, weights)
    assert sorted(n for g in groups for n in g["nodeids"]) == sorted(nodes)
    assert max(g["estimated_seconds"] for g in groups) - min(g["estimated_seconds"] for g in groups) <= 20
    for module in weights["modules"]:
        assert sum(any(n.startswith(module + "::") for n in group["nodeids"]) for group in groups) == 1


def test_complete_shard_receipts_prove_exact_union():
    nodes, receipts = sample_receipts()
    assert ci.verify(receipts) == {"tests": len(nodes), "shards": 4,
                                   "collection_sha256": ci.fingerprint(nodes)}


def test_actual_pytest_shards_execute_their_entire_partition(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    for index in range(4):
        (tests / f"test_module_{index}.py").write_text("def test_one():\n    assert True\n\ndef test_two():\n    assert True\n")
    launcher = tmp_path / "run.py"
    launcher.write_text(
        "import importlib.util, pathlib, sys\n"
        f"spec = importlib.util.spec_from_file_location('ci_runner', {str(ROOT / 'scripts/ci-pytest.py')!r})\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(module)\n"
        f"module.ROOT = pathlib.Path({str(tmp_path)!r})\n"
        "raise SystemExit(module.main(sys.argv[1:]))\n"
    )
    receipts = []
    for index in range(1, 5):
        receipt = tmp_path / f"shard-{index}.json"
        result = subprocess.run([sys.executable, str(launcher), "--index", str(index), "--output", str(receipt)],
                                cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        receipts.append(json.loads(receipt.read_text()))
    assert ci.verify(receipts)["tests"] == 8


@pytest.mark.parametrize("mutation", ["missing", "repeated", "failed", "different_collection", "omission",
                                     "duplicate_test", "not_executed"])
def test_coverage_gate_rejects_incomplete_or_inconsistent_results(mutation):
    _, receipts = sample_receipts()
    if mutation == "missing":
        receipts.pop()
    elif mutation == "repeated":
        receipts[1] = receipts[0]
    elif mutation == "failed":
        receipts[0]["exit_code"] = 1
    elif mutation == "different_collection":
        receipts[0]["collection_sha256"] = "0" * 64
    elif mutation == "omission":
        receipts[0]["nodeids"].pop()
        receipts[0]["executed_count"] -= 1
    elif mutation == "duplicate_test":
        receipts[1]["nodeids"][0] = receipts[0]["nodeids"][0]
    else:
        receipts[0]["executed_count"] -= 1
    with pytest.raises(ValueError):
        ci.verify(receipts)


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for name, value in (("user.name", "Distribution test"), ("user.email", "test@example.invalid")):
        subprocess.run(["git", "-C", str(repo), "config", name, value], check=True)
    (repo / "version.py").write_text('__version__ = "0.26.0"\n')
    (repo / "README.md").write_text("Committed guide\n")
    (repo / "launch.sh").write_text("#!/bin/sh\nexit 0\n")
    (repo / "launch.sh").chmod(0o755)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "Source fixture"], check=True)
    return repo


def test_package_reproduces_committed_bytes_and_never_reads_working_data(tmp_path):
    repo = make_repo(tmp_path)
    first = release.build_release(repo, "HEAD", tmp_path / "first")
    (repo / "README.md").write_text("Uncommitted edit must stay local\n")
    (repo / "webapp" / "projects").mkdir(parents=True)
    (repo / "webapp" / "projects" / "private.yaml").write_text("secret: synthetic\n")
    second = release.build_release(repo, first["commit"], tmp_path / "second")
    assert first == second
    assert (tmp_path / "first" / first["archive"]).read_bytes() == (tmp_path / "second" / first["archive"]).read_bytes()
    assert len(first["files"]) == 3
    with zipfile.ZipFile(tmp_path / "first" / first["archive"]) as package:
        root = first["archive"].removesuffix(".zip")
        assert package.read(f"{root}/README.md") == b"Committed guide\n"
        assert package.getinfo(f"{root}/launch.sh").external_attr >> 16 == 0o100755
        assert all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in package.infolist())
    metadata = json.loads((tmp_path / "first" / first["archive"].replace(".zip", ".json")).read_text())
    assert metadata["tree"] == release.git(repo, "rev-parse", "HEAD^{tree}").decode().strip()


@pytest.mark.parametrize("path", ["webapp/projects/client.yaml", "webapp/library/private.json", "out/result.pdf",
                                  "cache/__pycache__/compiled.pyc", "node_modules/example/index.js"])
def test_package_refuses_tracked_private_or_generated_files(tmp_path, path):
    repo = make_repo(tmp_path)
    file = repo / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("Synthetic data\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "Unsafe fixture"], check=True)
    with pytest.raises(ValueError, match="User data or generated"):
        release.build_release(repo, "HEAD", tmp_path / "package")
    assert not (tmp_path / "package").exists()


def test_package_allows_empty_projects_placeholder():
    assert not release.forbidden("webapp/projects/.gitkeep")
    assert release.forbidden("webapp/projects/client/.gitkeep")
