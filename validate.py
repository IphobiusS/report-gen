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


def validate(data, known_section_keys=None):
    """Valida un dict de engagement. known_section_keys permite inyectar el
    catalogo en tests; si es None se intenta cargar el catalogo real."""
    issues = []
    data = data or {}
    meta = data.get("meta") or {}

    if not str(meta.get("report_title") or "").strip():
        issues.append(("warning", "meta.report_title esta vacio"))
    if meta.get("lang") not in (None, *LANGS):
        issues.append(("error", f"meta.lang invalido: {meta.get('lang')!r} (usa es o en)"))

    findings = data.get("findings") or []
    ids = []
    for i, f in enumerate(findings):
        fid = f.get("id") or f"(hallazgo #{i + 1} sin id)"
        ids.append(f.get("id"))
        mode = f.get("mode", "vuln")
        if mode not in MODES:
            issues.append(("error", f"{fid}: mode invalido {mode!r} (usa vuln o machine)"))
        sev = f.get("severity")
        if sev is not None and sev not in SEVERITIES:
            issues.append(("error", f"{fid}: severidad invalida {sev!r}"))
        if mode == "machine" and not (f.get("host") or {}):
            issues.append(("warning", f"{fid}: hallazgo 'machine' sin bloque host"))
        vec = f.get("cvss_vector")
        if vec and not _cvss_vector_ok(vec):
            issues.append(("warning", f"{fid}: vector CVSS con formato inesperado: {vec}"))
        band = severity_from_score(f.get("cvss"))
        if band and sev and band != sev:
            issues.append(("warning",
                            f"{fid}: severidad declarada '{sev}' no coincide con CVSS "
                            f"{f.get('cvss')} (implica '{band}')"))

    present = [x for x in ids if x]
    dups = sorted({x for x in present if present.count(x) > 1})
    if dups:
        issues.append(("error", f"IDs de hallazgo duplicados: {', '.join(dups)}"))
    if any(not x for x in ids):
        issues.append(("warning", "hay hallazgos sin id"))

    sections_list = (data.get("report") or {}).get("sections") or []
    if sections_list:
        keys = known_section_keys
        if keys is None and catalog_by_key is not None:
            try:
                keys = set(catalog_by_key().keys())
            except Exception as exc:  # noqa: BLE001 - visible, no silencioso
                issues.append(("warning", f"no se pudo cargar el catalogo para validar secciones: {exc}"))
                keys = None
        if keys is None:
            if known_section_keys is None and catalog_by_key is None:
                issues.append(("warning", "no se validaron las secciones: catalogo no disponible"))
        else:
            for s in sections_list:
                # las secciones genericas (apendices a medida) llevan titulo propio y no
                # estan en el catalogo: son validas, no un error.
                if s.get("key") not in keys and not s.get("title"):
                    issues.append(("error", f"seccion desconocida en el catalogo: {s.get('key')!r}"))

    return issues


def format_issues(issues):
    if not issues:
        return "sin problemas"
    return "\n".join(f"[{lvl}] {msg}" for lvl, msg in issues)
