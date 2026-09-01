import pathlib
"""Catalogo canonico de secciones y resolucion para el renderizador."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "designs" / "report_sections.yaml"


HERE = pathlib.Path(__file__).resolve().parent


def load_catalog():
    return yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))


def catalog_by_key():
    return {s["key"]: s for s in load_catalog()["sections"]}


def default_enabled():
    cat = load_catalog()
    return [{"key": s["key"]} for s in sorted(cat["sections"], key=lambda x: x.get("order", 999)) if s.get("on_by_default")]


def load_presets():
    import yaml
    path = HERE / "designs" / "presets.yaml"
    if not path.exists():
        return []
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("presets", [])


def preset_by_id(preset_id):
    for p in load_presets():
        if p.get("id") == preset_id:
            return p
    return None


def preset_sections(preset_id, lang="es"):
    """Devuelve la lista de secciones (con contenido base en el idioma dado) del
    preset. Si el preset no existe o su lista esta vacia, usa default_enabled()."""
    p = preset_by_id(preset_id)
    if not p or not p.get("sections"):
        return default_enabled()
    out = []
    for sec in p["sections"]:
        entry = {"key": sec["key"]}
        for field, bylang in (sec.get("content") or {}).items():
            if isinstance(bylang, dict):
                entry[field] = bylang.get(lang) or bylang.get("es") or ""
            else:
                entry[field] = bylang
        out.append(entry)
    return out


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
