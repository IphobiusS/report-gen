#!/usr/bin/env python3
"""Fachada de compatibilidad de exportacion.

La logica vive en el paquete `exporters/` (common, markdown, docx, pdf). Este
modulo se mantiene para que los consumidores existentes (`webapp`, tests, CLI)
sigan usando `import export` y `export.export(...)` sin cambios. No contiene
logica de formato: solo despacha y reexporta.
"""
import argparse
import zipfile
from resources import local_image, relative_image
import validate as validatelib
from pathlib import Path
from storage import atomic_output, require_export_destination

from exporters.common import prepare, sev_label  # noqa: F401  (re-export compat)
from exporters.markdown import to_markdown
from exporters.docx import to_docx
from exporters.pdf import export_pdf

ROOT = Path(__file__).resolve().parent


def _write_pdf(yaml_path, out):
    with atomic_output(out) as temporary:
        export_pdf(yaml_path, temporary)
    return out


def _write_docx(yaml_path, out):
    data, meta, L = prepare(yaml_path)
    with atomic_output(out) as temporary:
        to_docx(data, meta, L, yaml_path.parent, temporary)
    return out


def _write_markdown(yaml_path, out):
    data, meta, L = prepare(yaml_path)
    source = to_markdown(data, meta, L, yaml_path.parent)
    from exporters.markdown import parse_exported
    tree = parse_exported(source)
    images = {node.get("src") for node in tree.xpath(".//img[@src]")}
    from exporters.charts import summary_asset
    chart = summary_asset(data, L)
    with atomic_output(out) as temporary:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as package:
            package.writestr("report.md", source)
            written = set()
            for src in sorted(images):
                if chart and src == chart["path"]:
                    # A generated resource never reads or overwrites project files.
                    package.writestr(chart["path"], chart["blob"])
                    continue
                path = local_image(src, yaml_path.parent)
                member = relative_image(src).as_posix()
                if member not in written:
                    package.write(path, member)
                    written.add(member)
    return out


def _write_html(yaml_path, out):
    from portable_report import build
    with atomic_output(out) as temporary:
        temporary.write_text(build(yaml_path.parent), encoding='utf-8')
    return out


def _export(yaml_path, fmt, out_path=None):
    from export_formats import get
    spec = get(fmt)
    source = Path(yaml_path).resolve()
    data = __import__('engine').load_engagement(source)
    validatelib.require_valid(data, final=True)
    out = Path(out_path) if out_path else ROOT/'out'/f'{source.parent.name}.{spec.extension}'
    if spec.key == 'md':
        out = out.with_suffix('.zip')
    out = require_export_destination(source, out, data)
    return spec.render(source, out)


def export(yaml_path, fmt, out_path=None):
    """All public formats share a cleaned, isolated copy. Source stays private."""
    from tempfile import TemporaryDirectory
    import publication
    source=Path(yaml_path).resolve()
    data=__import__('engine').load_engagement(source)
    validatelib.require_valid(data, final=True)
    from export_formats import get
    spec=get(fmt)
    suffix=spec.extension
    output=Path(out_path).resolve() if out_path else ROOT/'out'/f'{source.parent.name}.{suffix}'
    if spec.key == 'md':
        output = output.with_suffix('.zip')
    output = require_export_destination(source, output, data)
    with TemporaryDirectory(prefix='rg-public-') as tmp:
        snapshot=Path(tmp)/'report'
        publication.snapshot(source.parent,snapshot,data=data)

        return _export(snapshot/'engagement.yaml',fmt,output)


def main():
    ap = argparse.ArgumentParser(description="Exporta un engagement a pdf/docx/md/html")
    ap.add_argument("engagement")
    ap.add_argument("--format", "-f", required=True, choices=[*__import__("export_formats").REGISTRY, "mdzip"])
    ap.add_argument("-o", "--out")
    args = ap.parse_args()
    out = export(args.engagement, args.format, args.out)
    print(f"[+] {args.format}: {out}")


if __name__ == "__main__":
    main()
