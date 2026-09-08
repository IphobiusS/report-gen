"""Validacion de un engagement antes de renderizar. Sin dependencias externas
(alternativa portable a Pydantic): detecta datos que romperian o degradarian el
informe. Devuelve una lista de (nivel, mensaje) con nivel 'error' o 'warning'.

Reglas cubiertas: idioma/tema validos, modo de hallazgo, severidad valida, IDs
unicos y presentes, hallazgo 'machine' sin host, vector CVSS mal formado,
inconsistencia severidad declarada vs CVSS, y secciones inexistentes en el
catalogo canonico.
"""
import re
import math
from datetime import date, datetime

try:
    from sections import catalog_by_key
except Exception:  # pragma: no cover - catalogo opcional en validacion aislada
    catalog_by_key = None

SEVERITIES = {"critical", "high", "medium", "low", "info"}
MODES = {"vuln", "machine"}
LANGS = {"es", "en"}
CVSS_VECTOR_RE = re.compile(
    r"^CVSS:3\.[01]/AV:[NALP]/AC:[LH]/PR:[NLH]/UI:[NR]/S:[UC]/C:[HLN]/I:[HLN]/A:[HLN]$"
)


_MSG = {
    "title_empty": {"es": "meta.report_title esta vacio", "en": "meta.report_title is empty"},
    "lang_invalid": {"es": "meta.lang invalido: {lang!r} (usa es o en)", "en": "meta.lang invalid: {lang!r} (use es or en)"},
    "mode_invalid": {"es": "{fid}: mode invalido {mode!r} (usa vuln o machine)", "en": "{fid}: invalid mode {mode!r} (use vuln or machine)"},
    "sev_invalid": {"es": "{fid}: severidad invalida {sev!r}", "en": "{fid}: invalid severity {sev!r}"},
    "machine_no_host": {"es": "{fid}: hallazgo 'machine' sin bloque host", "en": "{fid}: 'machine' finding without host block"},
    "no_title": {"es": "{fid}: hallazgo sin titulo", "en": "{fid}: finding without title"},
    "no_cvss": {"es": "{fid}: hallazgo sin puntuacion CVSS", "en": "{fid}: finding without CVSS score"},
    "bad_vector": {"es": "{fid}: vector CVSS con formato inesperado: {vec}", "en": "{fid}: CVSS vector with unexpected format: {vec}"},
    "sev_mismatch": {"es": "{fid}: severidad declarada '{sev}' no coincide con CVSS {cvss} (implica '{band}')",
                     "en": "{fid}: declared severity '{sev}' does not match CVSS {cvss} (implies '{band}')"},
    "dup_ids": {"es": "IDs de hallazgo duplicados: {ids}", "en": "duplicate finding IDs: {ids}"},
    "no_id": {"es": "hay hallazgos sin id", "en": "there are findings without id"},
    "catalog_fail": {"es": "no se pudo cargar el catalogo para validar secciones: {exc}",
                     "en": "could not load catalog to validate sections: {exc}"},
    "no_catalog": {"es": "no se validaron las secciones: catalogo no disponible",
                   "en": "sections not validated: catalog unavailable"},
    "unknown_section": {"es": "seccion desconocida en el catalogo: {key!r}", "en": "unknown section in catalog: {key!r}"},
    "fid_no_id": {"es": "(hallazgo #{n} sin id)", "en": "(finding #{n} without id)"},
}


def _m(code, language, **kw):
    """Mensaje localizado; cae a espanol si el idioma no existe."""
    d = _MSG[code]
    return (d.get(language) or d["es"]).format(**kw)


def _cvss_vector_ok(vec):
    """Valida un vector CVSS. 3.0/3.1 por formato clasico; 4.0 con el motor CVSS
    (autoritativo). Evita falsos positivos con vectores 4.0 validos."""
    if vec.startswith("CVSS:3.1/") or vec.startswith("CVSS:4.0/"):
        try:
            import cvss
            cvss.score(vec)  # lanza ValueError si el vector 4.0 es invalido
            return True
        except ImportError:
            return False  # sin el paquete cvss no podemos validar 4.0: no marcar falso positivo
        except ValueError:
            return False
    return False


def severity_from_score(score):
    """Banda de severidad CVSS a partir del score numerico (mismas bandas 3.1/4.0)."""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(s) or not 0 <= s <= 10 or isinstance(score, bool):
        return None
    if s == 0:
        return "info"
    if s < 4.0:
        return "low"
    if s < 7.0:
        return "medium"
    if s < 9.0:
        return "high"
    return "critical"


def validate(data, known_section_keys=None, lang="es"):
    """Valida un dict de engagement. known_section_keys permite inyectar el
    catalogo en tests; si es None se intenta cargar el catalogo real.
    lang controla el idioma de los mensajes (es/en)."""
    lang = lang if isinstance(lang, str) and lang in LANGS else "es"
    issues = structure_issues(data, lang)
    if issues:
        return issues
    data = data or {}
    meta = data.get("meta") or {}

    if not str(meta.get("report_title") or "").strip():
        issues.append(("warning", _m("title_empty", lang)))
    if meta.get("theme") not in (None, "serio", "corporativo", "offsec", "htb"):
        issues.append(("error", "meta.theme no soportado"))
    if meta.get("lang") not in (None, *LANGS):
        issues.append(("error", _m("lang_invalid", lang, lang=meta.get("lang"))))

    findings = data.get("findings") or []
    ids = []
    for i, f in enumerate(findings):
        fid = f.get("id") or _m("fid_no_id", lang, n=i + 1)
        ids.append(f.get("id"))
        mode = f.get("mode", "vuln")
        if mode not in MODES:
            issues.append(("error", _m("mode_invalid", lang, fid=fid, mode=mode)))
        sev = f.get("severity")
        if sev is not None and sev not in SEVERITIES:
            issues.append(("error", _m("sev_invalid", lang, fid=fid, sev=sev)))
        if mode == "machine" and not (f.get("host") or {}):
            issues.append(("warning", _m("machine_no_host", lang, fid=fid)))
        if mode == "vuln":
            if not str(f.get("title") or "").strip():
                issues.append(("warning", _m("no_title", lang, fid=fid)))
            if f.get("cvss") is None or str(f.get("cvss")).strip() == "":
                issues.append(("warning", _m("no_cvss", lang, fid=fid)))
        vec = f.get("cvss_vector")
        if vec and not _cvss_vector_ok(vec):
            issues.append(("error", _m("bad_vector", lang, fid=fid, vec=vec)))
        supplied = f.get("cvss") is not None and str(f.get("cvss")).strip() != ""
        if supplied and severity_from_score(f["cvss"]) is None:
            issues.append(("error", f"{fid}: CVSS debe ser un número finito entre 0 y 10" if lang == "es" else f"{fid}: CVSS must be a finite number between 0 and 10"))
        if vec and _cvss_vector_ok(vec) and not vec.startswith("CVSS:3.0/"):
            import cvss
            actual = cvss.score(vec)["score"]
            if supplied and severity_from_score(f["cvss"]) is not None and not math.isclose(float(f["cvss"]), actual, abs_tol=1e-8):
                issues.append(("error", f"{fid}: CVSS {f['cvss']} no coincide con el vector ({actual})" if lang == "es" else f"{fid}: CVSS {f['cvss']} does not match vector ({actual})"))
        elif vec and vec.startswith("CVSS:3.0/"):
            issues.append(("error", f"{fid}: CVSS 3.0 no soportado; utiliza 3.1 o 4.0"))
        band = severity_from_score(f.get("cvss"))
        if band and sev and band != sev:
            issues.append(("error", _m("sev_mismatch", lang, fid=fid, sev=sev, cvss=f.get("cvss"), band=band)))

    present = [x for x in ids if x]
    dups = sorted({x for x in present if present.count(x) > 1})
    if dups:
        issues.append(("error", _m("dup_ids", lang, ids=", ".join(dups))))
    if any(not x for x in ids):
        issues.append(("warning", _m("no_id", lang)))

    sections_list = (data.get("report") or {}).get("sections") or []
    if sections_list:
        keys = known_section_keys
        if keys is None and catalog_by_key is not None:
            try:
                keys = set(catalog_by_key().keys())
            except Exception as exc:  # noqa: BLE001 - visible, no silencioso
                issues.append(("warning", _m("catalog_fail", lang, exc=exc)))
                keys = None
        if keys is None:
            if known_section_keys is None and catalog_by_key is None:
                issues.append(("warning", _m("no_catalog", lang)))
        else:
            for s in sections_list:
                # las secciones genericas (apendices a medida) llevan titulo propio y no
                # estan en el catalogo: son validas, no un error.
                if s.get("key") not in keys and not s.get("title"):
                    issues.append(("error", _m("unknown_section", lang, key=s.get("key"))))

    return issues


def format_issues(issues):
    if not issues:
        return "sin problemas"
    return "\n".join(f"[{lvl}] {msg}" for lvl, msg in issues)


# A draft may omit content; containers and typed fields must still be valid.
_TEXT = (str, int, float, date, datetime)

def structure_issues(data, lang="es"):
    issues = []
    def error(path, expected):
        issues.append(("error", f"{path}: se esperaba {expected}" if lang == "es" else f"{path}: expected {expected}"))
    def obj(value, path):
        if not isinstance(value, dict):
            error(path, "object"); return False
        return True
    def rows(value, path, check):
        if not isinstance(value, list):
            error(path, "list"); return
        if len(value) > 10000:
            error(path, "at most 10000 entries"); return
        for i, item in enumerate(value):
            if obj(item, f"{path}[{i}]"): check(item, f"{path}[{i}]")
    def strings(value, path):
        for key, item in value.items():
            if item is not None and (not isinstance(item, _TEXT) or isinstance(item, bool)):
                error(f"{path}.{key}", "text or number")
    def text_fields(value, path, keys):
        for key in keys:
            if key in value and value[key] is not None and not isinstance(value[key], str):
                error(f"{path}.{key}", "text")
    def step(value, path):
        text_fields(value, path, ("lead", "text_md", "command"))
        if "figure" in value:
            if obj(value["figure"], path+".figure"):
                text_fields(value["figure"], path+".figure", ("src", "caption"))
    def phase(value, path):
        text_fields(value, path, ("name",))
        if "steps" in value: rows(value["steps"], path+".steps", step)
    def finding(value, path):
        text_fields(value, path, ("id", "mode", "title", "severity", "cvss_vector", "cwe", "affected", "open_ports", "description_md", "summary_md", "impact_md", "remediation_md"))
        if "cvss" in value and value["cvss"] is not None and (not isinstance(value["cvss"], (str, int, float)) or isinstance(value["cvss"], bool)):
            error(path+".cvss", "number")
        for key in ("host", "remediation_summary"):
            if key in value and obj(value[key], path+"."+key): strings(value[key], path+"."+key)
        for key, fn in (("proof", strings), ("flags", strings), ("walkthrough", step), ("phases", phase)):
            if key in value: rows(value[key], path+"."+key, fn)
        if "references" in value and (not isinstance(value["references"], list) or not all(isinstance(x, str) for x in value["references"])):
            error(path+".references", "list of text")
    if not obj(data, "engagement"): return issues
    from workflows import structure_errors
    issues.extend(structure_errors(data))
    if "meta" in data and obj(data["meta"], "meta"):
        meta = data["meta"]
        text_fields(meta, "meta", ("lang", "theme", "report_title", "report_subtitle", "client", "assessor", "assessor_title"))
        for key in ("branding",):
            if key in meta and obj(meta[key], "meta."+key):
                strings(meta[key], "meta."+key)
                accent = meta[key].get("accent")
                if accent and (not isinstance(accent, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", accent)):
                    error("meta.branding.accent", "#RRGGBB")
        if "scope" in meta: rows(meta["scope"], "meta.scope", strings)
        if "contacts" in meta and obj(meta["contacts"], "meta.contacts"):
            for key, value in meta["contacts"].items(): rows(value, "meta.contacts."+key, strings)
    if "findings" in data: rows(data["findings"], "findings", finding)
    if "report" in data and obj(data["report"], "report") and "sections" in data["report"]:
        catalog = catalog_by_key() if catalog_by_key else {}
        def section(value, path):
            text_fields(value, path, ("key", "title", "body"))
            key = value.get("key")
            if not isinstance(key, str): return
            for field in catalog.get(key, {}).get("fields", []):
                k = field["key"]
                if k not in value: continue
                if field["type"] == "table": rows(value[k], path+"."+k, strings)
                elif field["type"] == "list":
                    if not isinstance(value[k], list) or not all(isinstance(x, str) for x in value[k]): error(path+"."+k, "list of text")
                else: text_fields(value, path, (k,))
        rows(data["report"]["sections"], "report.sections", section)
    return issues


def require_valid(data, final=False):
    issues = validate(data) if final else structure_issues(data)
    errors = [msg for level, msg in issues if level == "error"]
    if errors:
        raise ValueError("; ".join(errors))
    return issues
