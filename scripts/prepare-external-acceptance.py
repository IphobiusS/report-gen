#!/usr/bin/env python3
"""Prepare synthetic Word inputs and blank human-session records; record no acceptance."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import engine
import export
import project_history
from version import __version__
from wizard import dump_yaml


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
        writer.writerow(["participant", "task", "version", "commit", "os_browser_viewer", "seconds", "setup_seconds", "interventions", "observed_blocker", "outcome"])
        for person in range(1, 6):
            for task in ("create", "deliver", "recover"):
                writer.writerow([f"P{person}", task, __version__, "", "", "", "", "", "", ""])
    result = {"schema": 1, "version": __version__, "synthetic": True, "documents": results,
              "word_native": "not_run", "human_sessions": "not_run", "human_observations_recorded": 0,
              "instructions": "Use CONTRIBUTING.md for voluntary sessions. Run verify-microsoft-word.ps1 on licensed desktop Word; inspect its rendered pages. Blank CSV rows are not completed sessions."}
    (destination / "acceptance-preparation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.output), ensure_ascii=False))
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Preparation failed: {exc}\n")
