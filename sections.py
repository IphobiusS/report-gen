"""Catalogo canonico de secciones y resolucion para el renderizador."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "designs" / "report_sections.yaml"


def load_catalog():
    return yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))


def catalog_by_key():
    return {s["key"]: s for s in load_catalog()["sections"]}


def default_enabled():
    cat = load_catalog()
    return [{"key": s["key"]} for s in sorted(cat["sections"], key=lambda x: x.get("order", 999)) if s.get("on_by_default")]


def preset_sections(name):
    cat = load_catalog()
    keys = cat.get("presets", {}).get(name)
    if not keys:
        return default_enabled()
    return [{"key": k} for k in keys]


def resolve_sections(data, L, lang):
    """Convierte report.sections (activas + datos) en una lista lista para render."""
    bykey = catalog_by_key()
    enabled = (data.get("report") or {}).get("sections") or []
    out = []
    for sec in enabled:
        key = sec.get("key")
        schema = bykey.get(key)
        if not schema:
            continue
        title = schema.get(f"title_{lang}") or schema.get("title_es") or key
        item = {"key": key, "title": title, "special": schema.get("special"), "fields": []}
        for f in schema.get("fields") or []:
            fld = {
                "key": f["key"], "type": f["type"],
                "label": f.get(f"label_{lang}") or f.get("label_es", ""),
                "value": sec.get(f["key"]),
                "default_lang": f.get("default_lang"),
            }
            if f["type"] == "table":
                fld["columns"] = [
                    {"key": c["key"], "label": c.get(f"label_{lang}") or c.get("label_es", "")}
                    for c in f.get("columns", [])
                ]
            item["fields"].append(fld)
        out.append(item)
    return out
