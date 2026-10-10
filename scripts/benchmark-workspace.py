#!/usr/bin/env python3
"""Synthetic corpus and export worker for benchmark-workspace-0230.cjs.

The JS runner owns the browser and timing report and supplies disposable
synthetic workspaces. Keep real assessment data out of this benchmark. Timings
exclude preparation and verification, which are recorded separately.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic_image(path, index):
    """Deterministic, distinct 800x450 screenshots; no external assets or fonts."""
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (800, 450), (18, 26, 34))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 799, 37), fill=(39, 51, 62))
    draw.text((16, 13), f"SYNTHETIC EVIDENCE {index:04d} - SIMULATION ONLY", fill=(235, 244, 240))
    # Structured terminal-like data, including unique pixels for each index.
    for line in range(22):
        value = hashlib.sha256(f"report-gen-scale-0310:{index}:{line}".encode()).hexdigest()
        draw.text((18, 52 + line * 16), f"{line:02d}  {value}  example.invalid", fill=(98, 210, 151))
    draw.rectangle((650, 417, 780, 438), fill=(index % 256, index // 256, 91))
    image.save(path, format="PNG", optimize=False)


def seed(workspace, request):
    import project_history
    import workflows
    if not isinstance(request.get("slug"), str) or not re.fullmatch(r"synthetic-scale(?:-[a-z0-9]+)*", request["slug"]):
        raise ValueError("Use a synthetic-scale project slug without path components.")
    directory = Path(workspace) / "projects" / request["slug"]
    if directory.exists():
        raise ValueError("Existing project is preserved; seed into a new synthetic workspace.")
    (directory / "img").mkdir(parents=True, exist_ok=True)
    tiny = directory / "img/synthetic.png"
    tiny.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="))
    data = request["data"]
    if request.get("image_mode") == "distinct":
        for index, evidence in enumerate(data.get("evidence", []), 1):
            relative = f"img/synthetic-{index:04d}.png"
            synthetic_image(directory / relative, index)
            evidence["src"] = relative
    for index in range(request.get("unregistered_images", 0)):
        (directory / "img" / f"unregistered-{index + 1:04d}.png").write_bytes(tiny.read_bytes())
    if request.get("image_mode") == "distinct":
        tiny.unlink()
    workflows.normalize(data)
    project_history.save(directory, data)
    paths = sorted({row["src"] for row in data.get("evidence", [])})
    images = [{"path": p, "bytes": (directory / p).stat().st_size, "sha256": digest(directory / p)} for p in paths]
    return {"data": data, "images": images, "uniqueImageHashes": len({row["sha256"] for row in images}),
            "imageBytes": sum(row["bytes"] for row in images),
            "corpusSha256": hashlib.sha256(json.dumps({"data": data, "images": images}, sort_keys=True,
                                                        ensure_ascii=False).encode()).hexdigest()}


def export_one(source, fmt, output):
    import delivery
    import export
    import export_formats
    from tempfile import TemporaryDirectory
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    artifact = output / export_formats.get(fmt).filename
    if artifact.exists():
        raise ValueError("Existing benchmark artifact is preserved; choose a new output directory.")
    with TemporaryDirectory(prefix="rg-benchmark-capture-") as temporary:
        start = time.perf_counter()
        snapshot = Path(temporary) / "snapshot"
        captured = delivery.capture(Path(source).parent, snapshot)
        capture_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        result = export.export(snapshot / "engagement.yaml", fmt, artifact)
        export_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        checks = delivery.inspect_export(result, fmt, captured)
        verification_ms = (time.perf_counter() - start) * 1000
    memory = {"status": "unavailable"}
    try:
        import resource
        factor = 1 if sys.platform == "darwin" else 1024
        memory = {"workerPeakRssBytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * factor,
                  "largestChildPeakRssBytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * factor,
                  "scope": "Separate process high-water marks; not simultaneous aggregate memory."}
    except ImportError:
        pass
    return {"format": fmt, "captureMs": capture_ms, "exportMs": export_ms, "verificationMs": verification_ms,
            "bytes": result.stat().st_size, "sha256": digest(result), "artifact": result.name,
            "checks": checks, "memory": memory}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fixture = sub.add_parser("seed")
    fixture.add_argument("workspace", type=Path)
    render = sub.add_parser("export")
    render.add_argument("source", type=Path)
    render.add_argument("format", choices=("pdf", "docx", "md", "html"))
    render.add_argument("output", type=Path)
    args = parser.parse_args()
    result = seed(args.workspace, json.load(sys.stdin)) if args.command == "seed" else export_one(args.source, args.format, args.output)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
