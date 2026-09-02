"""Validacion de un engagement antes de renderizar. Sin dependencias externas
(alternativa portable a Pydantic): detecta datos que romperian o degradarian el
informe. Devuelve una lista de (nivel, mensaje) con nivel 'error' o 'warning'.

Reglas cubiertas: idioma/tema validos, modo de hallazgo, severidad valida, IDs
unicos y presentes, hallazgo 'machine' sin host, vector CVSS mal formado,
inconsistencia severidad declarada vs CVSS, y secciones inexistentes en el
catalogo canonico.
"""
import re

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


def _m(code, lang, **kw):
    """Mensaje localizado; cae a espanol si el idioma no existe."""
    d = _MSG[code]
    return (d.get(lang) or d["es"]).format(**kw)


def _cvss_vector_ok(vec):
    """Valida un vector CVSS. 3.0/3.1 por formato clasico; 4.0 con el motor CVSS
    (autoritativo). Evita falsos positivos con vectores 4.0 validos."""
    if CVSS_VECTOR_RE.match(vec):
        return True
    if vec.startswith("CVSS:4.0/"):
        try:
            import cvss
            cvss.score(vec)  # lanza ValueError si el vector 4.0 es invalido
            return True
        except ImportError:
            return True  # sin el paquete cvss no podemos validar 4.0: no marcar falso positivo
        except ValueError:
            return False
    return False


def severity_from_score(score):
    """Banda de severidad CVSS a partir del score numerico (mismas bandas 3.1/4.0)."""
    try:
        s = float(score)
    except (TypeError, ValueError):
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
    lang = lang if lang in LANGS else "es"
    issues = []
    data = data or {}
    meta = data.get("meta") or {}

    if not str(meta.get("report_title") or "").strip():
        issues.append(("warning", _m("title_empty", lang)))
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
            if not str(f.get("cvss") or "").strip():
                issues.append(("warning", _m("no_cvss", lang, fid=fid)))
        vec = f.get("cvss_vector")
        if vec and not _cvss_vector_ok(vec):
            issues.append(("warning", _m("bad_vector", lang, fid=fid, vec=vec)))
        band = severity_from_score(f.get("cvss"))
        if band and sev and band != sev:
            issues.append(("warning", _m("sev_mismatch", lang, fid=fid, sev=sev, cvss=f.get("cvss"), band=band)))

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
