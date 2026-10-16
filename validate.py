"""Validacion de un engagement antes de renderizar. Sin dependencias externas
(alternativa portable a Pydantic): detecta datos que romperian o degradarian el
informe. Devuelve una lista de (nivel, mensaje) con nivel 'error' o 'warning'.

Reglas cubiertas: idioma/tema validos, modo de hallazgo, severidad valida, IDs
unicos y presentes, hallazgo 'machine' sin host, vector CVSS mal formado,
inconsistencia severidad declarada vs CVSS, y secciones inexistentes en el
catalogo canonico.
"""
from error_messages import message as backend_message
from error_messages import language_argument
from languages import normalize_language
import re
import math
from collections import Counter
from report_designs import THEMES
from datetime import date, datetime

try:
    from sections import catalog_by_key
except Exception:  # pragma: no cover - catalogo opcional en validacion aislada
    catalog_by_key = None

SEVERITIES = {"critical", "high", "medium", "low", "info"}
MODES = {"vuln", "machine"}
# The portable shell owns these destinations. A contract checks them against
# the generated shell so a new control cannot silently steal a report anchor.
PORTABLE_CONTROL_IDS = {'view', 'kind', 'query', 'severity', 'clear-filters',
                        'results', 'print', 'empty-results'}


_MSG = {
    "title_empty": {"es": "meta.report_title esta vacio", "en": "meta.report_title is empty"},
    "lang_invalid": {"es": "meta.lang invalido: {lang!r} (usa es, en o pt)", "en": "meta.lang invalid: {lang!r} (use es, en or pt)"},
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
    "dup_anchors": {"es": "Anclas de informe duplicadas o reservadas: {ids}. Cambia el id del hallazgo o la clave de sección en conflicto.",
                    "en": "Duplicate or reserved report anchors: {ids}. Change the conflicting finding id or section key."},
}


for _key, _text in {'title_empty': 'meta.report_title está vazio', 'lang_invalid': 'meta.lang inválido: {lang!r} (use es, en ou pt)', 'mode_invalid': '{fid}: mode inválido {mode!r} (use vuln ou machine)', 'sev_invalid': '{fid}: severidade inválida {sev!r}', 'machine_no_host': "{fid}: achado 'machine' sem bloco host", 'no_title': '{fid}: achado sem título', 'no_cvss': '{fid}: achado sem pontuação CVSS', 'bad_vector': '{fid}: vetor CVSS com formato inesperado: {vec}', 'sev_mismatch': "{fid}: severidade declarada '{sev}' não corresponde ao CVSS {cvss} (indica '{band}')", 'dup_ids': 'IDs de achados duplicados: {ids}', 'no_id': 'há achados sem id', 'catalog_fail': 'não foi possível carregar o catálogo para validar as seções: {exc}', 'no_catalog': 'seções não validadas: catálogo indisponível', 'unknown_section': 'seção desconhecida no catálogo: {key!r}', 'fid_no_id': '(achado #{n} sem id)', 'dup_anchors': 'Âncoras de relatório duplicadas ou reservadas: {ids}. Altere o id do achado ou a chave de seção em conflito.'}.items():
    _MSG[_key]["pt"] = _text


def _m(code, language, **kw):
    """Mensaje localizado; cae a espanol si el idioma no existe."""
    d = _MSG[code]
    return (d.get(language) or d["es"]).format(**kw)


def _cvss_vector_ok(vec):
    """Valida CVSS 3.1 y 4.0 con sus motores; 3.0 no está soportado."""
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
    except (TypeError, ValueError, OverflowError):
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


def report_anchor_issues(data, language):
    """Validate the destinations the renderer actually emits, without rewriting IDs.

    Custom keys remain available when the corresponding automatic/legacy block
    is absent. Incomplete drafts keep their own identities until final review.
    """
    findings = data.get('findings') or []
    report = data.get('report') or {}
    active = report.get('sections') or []
    anchors = list(PORTABLE_CONTROL_IDS)
    catalog = catalog_by_key() if catalog_by_key is not None else {}
    if active:
        anchors.append('sec-toc')
        for section in active:
            key = section.get('key')
            if catalog.get(key, {}).get('special') == 'appendix':
                from sections import is_empty_appendix
                if is_empty_appendix(section, data, catalog[key]):
                    continue
            if key in catalog or section.get('title') or section.get('body'):
                anchors.append(key or 'sec')
        include_findings = any(catalog.get(section.get('key'), {}).get('special') == 'findings'
                               for section in active)
    else:
        anchors.extend(('sec-conf', 'sec-toc', 'sec-contacts', 'sec-overview', 'sec-summary'))
        if any(f.get('proof') or f.get('flags') for f in findings):
            anchors.append('sec-appendix')
        include_findings = True
    if include_findings:
        anchors.extend(f['id'] for f in findings if f.get('id'))
    # Mirror only the presence predicates of workflows.report_sections. Avoid
    # building its Markdown bodies just to validate an unfinished document.
    config = report.get('workflow') or {}
    if config.get('include_assets', True) and data.get('assets'):
        anchors.append('rg_assets')
    if config.get('include_coverage', True) and (data.get('coverage') or data.get('limitations_md')):
        anchors.append('rg_coverage')
    if config.get('include_retest', True) and any(
            f.get('retests') or f.get('owner') or f.get('due_date')
            or f.get('status', 'open') != 'open' or f.get('verification') for f in findings):
        anchors.append('rg_retest')
    if config.get('include_root_causes', False):
        from root_cause import selected_groups
        if selected_groups(data):
            anchors.append('rg_root_causes')
    duplicates = sorted(key for key, count in Counter(anchors).items() if count > 1)
    return [('error', _m('dup_anchors', language, ids=', '.join(duplicates)))] if duplicates else []


@language_argument
def markdown_control_issues(data, lang=None):
    """Return field-addressed errors before a renderer decodes numeric refs."""
    from resources import markdown_fields
    from safe_markup import validate_character_references
    from workflows import strings
    fields = markdown_fields()
    issues = []
    for path, text in strings(data):
        key = path.rsplit('.', 1)[-1]
        if key.endswith('_md') or key in fields:
            try:
                validate_character_references(text)
            except ValueError as exc:
                issues.append((path, str(exc)))
    return issues


@language_argument
def validate(data, known_section_keys=None, lang=None):
    """Valida un dict de engagement. known_section_keys permite inyectar el
    catalogo en tests; si es None se intenta cargar el catalogo real.
    lang controla el idioma de los mensajes (es/en/pt)."""
    lang = normalize_language(lang)
    issues = structure_issues(data, lang)
    if issues:
        return issues
    controls = markdown_control_issues(data, lang)
    if controls:
        return [('error', f'{path}: {message}') for path, message in controls]
    data = data or {}
    meta = data.get("meta") or {}

    if not str(meta.get("report_title") or "").strip():
        issues.append(("warning", _m("title_empty", lang)))
    if "theme" in meta and meta["theme"] not in THEMES:
        issues.append(("error", backend_message('meta.theme no soportado')))
    if meta.get("lang") is not None and normalize_language(meta.get("lang"), None) is None:
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
        version = f.get("cvss_version")
        if version not in (None, "", "3.1", "4.0"):
            issues.append(("error", backend_message('{p0}: cvss_version debe ser 3.1 o 4.0', p0=fid)))
        elif vec and version and not vec.startswith(f"CVSS:{version}/"):
            issues.append(("error", backend_message('{p0}: cvss_version no coincide con el vector', p0=fid)))
        vector_valid = bool(vec) and _cvss_vector_ok(vec)
        if vec and not vector_valid:
            issues.append(("error", _m("bad_vector", lang, fid=fid, vec=vec)))
        supplied = f.get("cvss") is not None and str(f.get("cvss")).strip() != ""
        if supplied and severity_from_score(f["cvss"]) is None:
            issues.append(("error", backend_message("{fid}: CVSS debe ser un número finito entre 0 y 10", en="{fid}: CVSS must be a finite number between 0 and 10", pt="{fid}: CVSS deve ser um número finito entre 0 e 10", language=lang, fid=fid)))
        vector_score = None
        if vector_valid:
            import cvss
            vector_score = cvss.score(vec)["score"]
            if supplied and severity_from_score(f["cvss"]) is not None and not math.isclose(float(f["cvss"]), vector_score, abs_tol=1e-8):
                issues.append(("error", backend_message("{fid}: CVSS {score} no coincide con el vector ({vector_score})", en="{fid}: CVSS {score} does not match vector ({vector_score})", pt="{fid}: CVSS {score} não corresponde ao vetor ({vector_score})", language=lang, fid=fid, score=f["cvss"], vector_score=vector_score)))
        elif vec and vec.startswith("CVSS:3.0/"):
            issues.append(("error", backend_message('{p0}: CVSS 3.0 no soportado; utiliza 3.1 o 4.0', p0=fid)))
        # Vector-only reports retain their absent/nullable score in every
        # export. The calculated value is used only to validate classification.
        band_score = f.get("cvss") if supplied else vector_score
        band = severity_from_score(band_score)
        if band and sev and band != sev:
            issues.append(("error", _m("sev_mismatch", lang, fid=fid, sev=sev, cvss=band_score, band=band)))

    present = [x for x in ids if x]
    dups = sorted(x for x, count in Counter(present).items() if count > 1)
    if dups:
        issues.append(("error", _m("dup_ids", lang, ids=", ".join(dups))))
    if any(not x for x in ids):
        issues.append(("error", _m("no_id", lang)))
    issues.extend(report_anchor_issues(data, lang))

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

    from resources import image_references, relative_image
    for path, source in image_references(data):
        try: relative_image(source)
        except ValueError as exc: issues.append(('error', f'{path}: {exc}'))

    return issues


# A draft may omit content; containers and typed fields must still be valid.
_TEXT = (str, int, float, date, datetime)

@language_argument
def structure_issues(data, lang=None):
    from input_guard import ensure_data_tree
    try:
        ensure_data_tree(data)
    except ValueError as exc:
        return [('error', str(exc))]
    issues = []
    def error(path, expected):
        issues.append(("error", backend_message("{path}: se esperaba {expected}", en="{path}: expected {expected}", pt="{path}: era esperado {expected}", language=lang, path=path, expected=expected)))
    def obj(value, path):
        if not isinstance(value, dict):
            error(path, backend_message('object')); return False
        return True
    def rows(value, path, check):
        if not isinstance(value, list):
            error(path, backend_message('list')); return
        if len(value) > 10000:
            error(path, backend_message('at most 10000 entries')); return
        for i, item in enumerate(value):
            if obj(item, f"{path}[{i}]"): check(item, f"{path}[{i}]")
    def strings(value, path):
        for key, item in value.items():
            if item is not None and (not isinstance(item, _TEXT) or isinstance(item, bool)):
                error(f"{path}.{key}", backend_message('text or number'))
    def text_fields(value, path, keys):
        for key in keys:
            if key in value and value[key] is not None and not isinstance(value[key], str):
                error(f"{path}.{key}", backend_message('text'))
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
            error(path+".cvss", backend_message('number'))
        elif isinstance(value.get("cvss"), (int, float)):
            # An arbitrary-size Python integer can become Infinity in the
            # browser, then silently turn into null on its next JSON save.
            # Finite out-of-range draft scores remain semantic review issues.
            try: finite = math.isfinite(float(value['cvss']))
            except OverflowError: finite = False
            if not finite: error(path+".cvss", backend_message('finite portable number'))
        for key in ("host", "remediation_summary"):
            if key in value and obj(value[key], path+"."+key): strings(value[key], path+"."+key)
        for key, fn in (("proof", strings), ("flags", strings), ("walkthrough", step), ("phases", phase)):
            if key in value: rows(value[key], path+"."+key, fn)
        if "references" in value and (not isinstance(value["references"], list) or not all(isinstance(x, str) for x in value["references"])):
            error(path+".references", backend_message('list of text'))
    if not obj(data, "engagement"): return issues
    if 'project_management' in data:
        from project_catalog import validate_metadata
        try: validate_metadata(data['project_management'])
        except ValueError as exc: issues.append(('error', str(exc)))
    from workflows import structure_errors
    issues.extend(structure_errors(data))
    from insights import validate_structure
    issues.extend(validate_structure(data))
    if "meta" in data and obj(data["meta"], "meta"):
        meta = data["meta"]
        if meta.get("report_density", "comfortable") not in ("comfortable", "compact"):
            error("meta.report_density", backend_message('comfortable or compact'))
        if "design" in meta:
            from design_library import validate_design
            try: validate_design(meta["design"])
            except (ValueError, TypeError) as exc: issues.append(("error", str(exc)))
        text_fields(meta, "meta", ("lang", "theme", "report_title", "report_subtitle", "client", "assessor", "assessor_title", "confidentiality_md"))
        for key in ("date", "version", "email", "osid"):
            if key in meta: strings({key: meta[key]}, 'meta')
        if 'overview' in meta and obj(meta['overview'], 'meta.overview'):
            text_fields(meta['overview'], 'meta.overview', ('approach_md',))
        for key in ("branding",):
            if key in meta and obj(meta[key], "meta."+key):
                strings(meta[key], "meta."+key)
                text_fields(meta[key], 'meta.'+key, ('logo', 'client_logo', 'cover_image'))
                accent = meta[key].get("accent")
                if accent and (not isinstance(accent, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", accent)):
                    error("meta.branding.accent", backend_message('#RRGGBB'))
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
                    if not isinstance(value[k], list) or not all(isinstance(x, str) for x in value[k]): error(path+"."+k, backend_message('list of text'))
                else: text_fields(value, path, (k,))
        rows(data["report"]["sections"], "report.sections", section)
    return issues


def require_valid(data, final=False):
    issues = validate(data) if final else structure_issues(data)
    errors = [msg for level, msg in issues if level == "error"]
    if errors:
        raise ValueError("; ".join(errors))
    return issues
