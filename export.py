#!/usr/bin/env python3
"""Fachada de compatibilidad de exportacion.

La logica vive en el paquete `exporters/` (common, markdown, docx, pdf). Este
modulo se mantiene para que los consumidores existentes (`webapp`, tests, CLI)
sigan usando `import export` y `export.export(...)` sin cambios. No contiene
logica de formato: solo despacha y reexporta.
"""
import argparse
import zipfile
from lxml import html
from resources import local_image
from safe_markup import md
import validate as validatelib
from pathlib import Path

from exporters.common import prepare, sev_label  # noqa: F401  (re-export compat)
from exporters.markdown import to_markdown
from exporters.docx import to_docx
from exporters.pdf import export_pdf

ROOT = Path(__file__).resolve().parent


def export(yaml_path, fmt, out_path=None):
    yaml_path = Path(yaml_path).resolve()
    engagement_dir = yaml_path.parent
    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    stem = engagement_dir.name

    if fmt not in {"pdf", "docx", "md", "mdzip"}:
        raise ValueError("Formato no soportado")
    validatelib.require_valid(__import__("engine").load_engagement(yaml_path), final=True)
    if fmt == "pdf":
        out = Path(out_path) if out_path else out_dir / f"{stem}.pdf"
        return export_pdf(yaml_path, out)

    data, meta, L = prepare(yaml_path)
    if fmt in {"md", "mdzip"}:
        out = Path(out_path).with_suffix(".zip") if out_path else out_dir / f"{stem}.zip"
        out.parent.mkdir(parents=True, exist_ok=True)
        source = to_markdown(data, meta, L, engagement_dir)
        tree = html.fragment_fromstring(str(md(source, img_base="")), create_parent="div")
        images = {node.get("src") for node in tree.xpath(".//img[@src]")}
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as package:
            package.writestr("report.md", source)
            for src in sorted(images):
                path = local_image(src, engagement_dir)
                package.write(path, src)
        return out
    if fmt == "docx":
        out = Path(out_path) if out_path else out_dir / f"{stem}.docx"
        return to_docx(data, meta, L, engagement_dir, out)
    raise SystemExit(f"formato no soportado: {fmt}")


def main():
    ap = argparse.ArgumentParser(description="Exporta un engagement a pdf/docx/md")
    ap.add_argument("engagement")
    ap.add_argument("--format", "-f", required=True, choices=["pdf", "docx", "md", "mdzip"])
    ap.add_argument("-o", "--out")
    args = ap.parse_args()
    out = export(args.engagement, args.format, args.out)
    print(f"[+] {args.format}: {out}")


if __name__ == "__main__":
    main()
