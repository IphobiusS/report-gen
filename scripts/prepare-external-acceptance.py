#!/usr/bin/env python3
"""Prepare synthetic Word inputs and blank human-session records; record no acceptance."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import engine
import export
import project_history
from version import __version__
from wizard import dump_yaml

TASKS = ("create", "deliver", "recover")
VISUAL_CHECKS = ("text_commands", "tables_images", "headings_pages", "index_links")
OUTCOMES = {"independent", "assisted", "blocked"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def revision():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def source_state(commit):
    if not commit:
        return "revision_unavailable"
    try:
        status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT, text=True)
        return "worktree_modified" if status.strip() else "committed"
    except (OSError, subprocess.CalledProcessError):
        return "state_unavailable"


def numeric(value, field, integer=False):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Missing or invalid {field}.") from exc
    if not math.isfinite(number) or number < 0 or (integer and not number.is_integer()):
        raise ValueError(f"Invalid {field}.")
    return number


def summarize(destination):
    """Validate locally recorded evidence; completeness never implies usability approval."""
    destination = Path(destination).resolve()
    manifest = json.loads((destination / "acceptance-preparation.json").read_text(encoding="utf-8"))
    expected = {row["case"]: row for row in manifest["documents"]}
    for row in expected.values():
        if sha256(destination / row["docx"]) != row["docx_sha256"]:
            raise ValueError("Prepared input changed; preserve the kit used during observation.")
    result = {"schema": 2, "version": manifest["version"], "commit": manifest.get("commit", ""),
              "source_state": manifest.get("source_state", "state_unavailable"),
              "word_native": "not_run", "word_visual": "not_run", "human_sessions": "not_run",
              "human_observations_recorded": 0, "participants_complete": 0,
              "outcomes": dict.fromkeys(sorted(OUTCOMES), 0), "usability_acceptance": "not_assessed"}
    native_file = destination / "word-verified/word-validation.json"
    native_rows = {}
    if native_file.exists():
        native = json.loads(native_file.read_text(encoding="utf-8-sig"))
        for row in native.get("results", []):
            case = Path(row.get("file", "")).stem
            if case not in expected or case in native_rows:
                raise ValueError("Unknown or duplicate Word case.")
            for key in ("pdf", "updated_docx"):
                value = row.get(key, "")
                if not value or Path(value).name != value or "\\" in value:
                    raise ValueError("Word evidence must use filenames within word-verified.")
            if (row.get("status") != "fields_updated_and_rendered" or not row.get("word_version")
                    or row.get("pages", 0) < 1
                    or row.get("source_sha256", "").lower() != expected[case]["docx_sha256"]
                    or row.get("pdf_sha256", "").lower() != sha256(native_file.parent / row["pdf"])
                    or row.get("updated_sha256", "").lower() != sha256(native_file.parent / row["updated_docx"])):
                raise ValueError("Word evidence does not match the prepared inputs and rendered files.")
            native_rows[case] = row
        result["word_native"] = "completed" if set(native_rows) == set(expected) else "partial"
    with (destination / "word-review.csv").open(newline="", encoding="utf-8") as stream:
        review_rows = list(csv.DictReader(stream))
    if len(review_rows) != len(expected) or {r["case"] for r in review_rows} != set(expected):
        raise ValueError("Visual review must contain exactly one row per prepared Word case.")
    reviewed = []
    for row in review_rows:
        if not any(row.get(key, "") for key in (*VISUAL_CHECKS, "reviewer", "reviewed_at", "notes", "pdf_sha256")):
            continue
        case = row["case"]
        if (case not in native_rows or not row.get("reviewer") or not row.get("reviewed_at")
                or row.get("pdf_sha256", "").lower() != native_rows[case]["pdf_sha256"].lower()
                or any(row.get(key) not in ("pass", "fail") for key in VISUAL_CHECKS)):
            raise ValueError("Visual review needs a reviewer, date, matching native PDF and all checks.")
        if "fail" in (row[key] for key in VISUAL_CHECKS) and not row.get("notes"):
            raise ValueError("Describe every failed visual review.")
        reviewed.append(all(row[key] == "pass" for key in VISUAL_CHECKS))
    if reviewed:
        result["word_visual"] = "issues_found" if not all(reviewed) else ("passed" if len(reviewed) == len(expected) else "partial")
    with (destination / "human-sessions.csv").open(newline="", encoding="utf-8") as stream:
        sessions = list(csv.DictReader(stream))
    wanted = {(f"P{person}", task) for person in range(1, 6) for task in TASKS}
    keys = {(row["participant"], row["task"]) for row in sessions}
    if len(sessions) != 15 or keys != wanted:
        raise ValueError("Human records must contain exactly the fifteen P1-P5 task rows.")
    completed = set()
    for row in sessions:
        observed_fields = ("os_browser_viewer", "seconds", "setup_seconds", "interventions", "observed_blocker", "outcome", "observer", "observed_at")
        if not any(row.get(key, "") for key in observed_fields):
            continue
        if (row.get("outcome") not in OUTCOMES or row.get("version") != manifest["version"]
                or not manifest.get("commit") or row.get("commit") != manifest["commit"]
                or any(not row.get(key) for key in ("os_browser_viewer", "observer", "observed_at"))):
            raise ValueError("A session needs an observed outcome, environment, observer, date and kit revision.")
        numeric(row["seconds"], "seconds")
        numeric(row["setup_seconds"], "setup_seconds")
        interventions = numeric(row["interventions"], "interventions", integer=True)
        if row["outcome"] == "independent" and interventions:
            raise ValueError("A task with moderator help is not independent.")
        if row["outcome"] == "assisted" and interventions == 0:
            raise ValueError("Assisted tasks must record moderator interventions.")
        if row["outcome"] == "blocked" and not row.get("observed_blocker"):
            raise ValueError("A blocked task must describe the observed blocker.")
        completed.add((row["participant"], row["task"]))
        result["outcomes"][row["outcome"]] += 1
    result["human_observations_recorded"] = len(completed)
    result["participants_complete"] = sum(all((f"P{person}", task) in completed for task in TASKS) for person in range(1, 6))
    if completed:
        result["human_sessions"] = "recorded" if len(completed) == 15 else "partial"
    result["word_acceptance"] = "passed" if result["word_native"] == "completed" and result["word_visual"] == "passed" else "pending"
    result["scope"] = "Local evidence consistency only. Participant identity, truth of observations and overall usability require human review."
    return result


def prepare(destination):
    destination = Path(destination).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Use an empty output directory; existing evidence is preserved.")
    destination.mkdir(parents=True, exist_ok=True)
    sources = destination / "synthetic-projects"
    sources.mkdir()
    documents = destination / "word-input"
    documents.mkdir()
    cases = []
    for name in ("quality-lab", "pending-severity"):
        shutil.copytree(ROOT / "examples" / name, sources / name)
        cases.append(name)
    project_history.import_bundle((ROOT / "examples/nimbus-demo-project.zip").read_bytes(), sources / "nimbus")
    cases.append("nimbus")
    stress = sources / "long-content"
    stress.mkdir()
    rows = "\n".join(f"| ASSET-{i:03} | Servicio sintético {i} | Pendiente de comprobación |" for i in range(1, 81))
    content = {
        "meta": {"report_title": "WORD-CORPUS-0270 · contenido largo", "lang": "es", "theme": "corporativo"},
        "report": {"sections": [{"key": "findings_summary"}, {"key": "findings"}]},
        "findings": [{"id": "F001", "mode": "vuln", "title": "Tabla larga y comandos literales",
                      "description_md": "Caso ficticio para paginación.\n\n| Activo | Servicio | Estado |\n| --- | --- | --- |\n" + rows,
                      "impact_md": "No representa un objetivo ni una vulnerabilidad real.",
                      "remediation_md": "1. Revisar continuidad de la tabla.\n2. Comprobar el índice y las cabeceras.",
                      "walkthrough": [{"command": "COMANDO_LITERAL_WORD_0270 --documento ejemplo --salida local", "description_md": "Conservar este comando como texto seleccionable."}]}],
    }
    dump_yaml(content, stress / "engagement.yaml")
    cases.append("long-content")
    results = []
    commit = revision()
    for name in cases:
        source = sources / name / "engagement.yaml"
        data = engine.load_engagement(source)
        target = export.export(source, "docx", documents / f"{name}.docx")
        results.append({"case": name, "findings": len(data.get("findings", [])),
                        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                        "docx": str(target.relative_to(destination)),
                        "docx_sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    with (destination / "human-sessions.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["participant", "task", "version", "commit", "os_browser_viewer", "seconds", "setup_seconds", "interventions", "observed_blocker", "outcome", "observer", "observed_at"])
        for person in range(1, 6):
            for task in TASKS:
                writer.writerow([f"P{person}", task, __version__, commit, "", "", "", "", "", "", "", ""])
    with (destination / "word-review.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["case", "reviewer", "reviewed_at", "pdf_sha256", *VISUAL_CHECKS, "notes"])
        for name in cases:
            writer.writerow([name, "", "", "", "", "", "", "", ""])
    (destination / "INSTRUCTIONS.txt").write_text(
        "PENDING: preparing this kit does not test native Word or observe people.\n"
        "1. On Windows with licensed Word: scripts/verify-microsoft-word.ps1 "
        "-InputDirectory <kit>/word-input -OutputDirectory <kit>/word-verified\n"
        "2. Inspect EVERY rendered PDF page. Complete word-review.csv with pass/fail for literal text/commands, "
        "table/image continuity, heading/page breaks and index/page links. Record the PDF SHA-256, reviewer "
        "and review date; describe failures. Do not infer visual approval from Word automation.\n"
        "3. Run the voluntary five-person protocol in CONTRIBUTING.md. Use P1-P5 and synthetic material. "
        "Record every task, including blocked tasks. Outcomes: independent, assisted or blocked. "
        "Record seconds, setup_seconds, intervention count, observer and observed_at. "
        "A browser script is not a human session. Keep observations outside public Git.\n"
        "4. python scripts/prepare-external-acceptance.py --summarize <kit>\n"
        "The command validates local evidence without changing it. Five recorded sessions do not "
        "automatically establish usability acceptance. Never fill missing observations from assumptions.\n",
        encoding="utf-8")
    result = {"schema": 2, "version": __version__, "commit": commit, "source_state": source_state(commit), "synthetic": True, "documents": results,
              "word_native": "not_run", "human_sessions": "not_run", "human_observations_recorded": 0,
              "instructions": "Use CONTRIBUTING.md for voluntary sessions. Run verify-microsoft-word.ps1 on licensed desktop Word; inspect its rendered pages. Blank CSV rows are not completed sessions."}
    (destination / "acceptance-preparation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_mutually_exclusive_group(required=True)
    command.add_argument("--output", type=Path, help="Prepare a new kit in an empty directory.")
    command.add_argument("--summarize", type=Path, help="Validate existing observations without altering them.")
    args = parser.parse_args()
    try:
        print(json.dumps(summarize(args.summarize) if args.summarize else prepare(args.output), ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f"Preparation failed: {exc}\n")
