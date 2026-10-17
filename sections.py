"""Catalogo canonico de secciones y resolucion para el renderizador."""
from importlib.resources import files
from pathlib import Path
import yaml
from languages import normalize_language

ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "designs" / "report_sections.yaml"


def load_catalog():
    # Keep source/frozen layouts and the canonical files; packaged resources
    # also work when the application modules are loaded from a wheel ZIP.
    source = CATALOG_PATH if CATALOG_PATH.is_file() else files('designs').joinpath('report_sections.yaml')
    return yaml.safe_load(source.read_text(encoding="utf-8"))


def catalog_by_key():
    return {s["key"]: s for s in load_catalog()["sections"]}


def default_enabled():
    cat = load_catalog()
    return [{"key": s["key"]} for s in sorted(cat["sections"], key=lambda x: x.get("order", 999)) if s.get("on_by_default")]


def load_presets():
    path = ROOT / "designs" / "presets.yaml"
    source = path if path.is_file() else files('designs').joinpath('presets.yaml')
    if not source.is_file():
        return []
    return (yaml.safe_load(source.read_text(encoding="utf-8")) or {}).get("presets", [])


def preset_by_id(preset_id):
    for p in load_presets():
        if p.get("id") == preset_id:
            return p
    return None


def preset_sections(preset_id, lang="es"):
    """Devuelve la lista de secciones (con contenido base en el idioma dado) del
    preset. Si el preset no existe o su lista esta vacia, usa default_enabled()."""
    lang = normalize_language(lang)
    p = preset_by_id(preset_id)
    if not p or not p.get("sections"):
        return default_enabled()
    out = []
    for sec in p["sections"]:
        entry = {"key": sec["key"]}
        if sec.get("title"):
            title = sec["title"]
            entry["title"] = (title.get(lang) or title.get('es') or '') if isinstance(title, dict) else title
        if sec.get("body") is not None:
            b = sec["body"]                          # cuerpo de seccion generica (apendices)
            entry["body"] = (b.get(lang) or b.get("es") or "") if isinstance(b, dict) else b
        for field, bylang in (sec.get("content") or {}).items():
            if isinstance(bylang, dict):
                entry[field] = bylang.get(lang) or bylang.get("es") or ""
            else:
                entry[field] = bylang
        out.append(entry)
    return out


def is_empty_appendix(section, data, schema=None):
    """Only the automatic, optional appendix may be absent from presentation.

    Authored custom sections keep their own titles/bodies. The source's enabled
    section list stays intact so later proof records or fields can populate it.
    """
    if schema is None:
        schema = catalog_by_key().get(section.get("key"))
    if not schema or schema.get("special") != "appendix":
        return False
    if any(section.get(field["key"]) for field in schema.get("fields", [])):
        return False
    from engine import appendix_rows
    return not appendix_rows(data.get("findings") or [])


def resolve_sections(data, L, lang):
    """Convierte report.sections (activas + datos) en una lista lista para render."""
    lang = normalize_language(lang, default="en")
    bykey = catalog_by_key()
    from workflows import report_sections
    enabled = list((data.get("report") or {}).get("sections") or []) + report_sections(data)
    out = []
    for sec in enabled:
        key = sec.get("key")
        schema = bykey.get(key)
        if is_empty_appendix(sec, data, schema or {}):
            continue
        if not schema:
            # seccion generica (sin schema): titulo propio + cuerpo markdown.
            # Permite apendices nombrados (Appendix A - ...) y secciones a medida por preset.
            if sec.get("title") or sec.get("body"):
                out.append({
                    "key": key or "sec",
                    "title": sec.get("title") or key,
                    "special": None,
                    "fields": [{"key": "body", "type": "markdown", "label": "",
                                "value": sec.get("body"), "default_lang": None}],
                })
            continue
        title = sec.get("title") or schema.get(f"title_{lang}") or schema.get("title_es") or key
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
