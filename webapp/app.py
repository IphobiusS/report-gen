#!/usr/bin/env python3
"""report-gen webapp: editor local tipo SysReptor sobre el motor existente.

Arranca en http://127.0.0.1:8080. Cada proyecto es una carpeta en projects/
con su engagement.yaml e img/. El render reusa ../engine.py (WeasyPrint/Chromium).
"""
import re
import os
import subprocess
import secrets
import threading
import tempfile
from functools import wraps
from io import BytesIO
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from html import escape, unescape
import sys
from pathlib import Path

import yaml
from flask import Flask, jsonify, request, send_file, send_from_directory, abort, Response, session, g

HERE = Path(__file__).resolve().parent
REPORT_ROOT = HERE.parent
sys.path.insert(0, str(REPORT_ROOT))

from workspace_paths import select_workspace, browser_namespace, portable_project_slug, _no_links  # noqa: E402
WORKSPACE = select_workspace(REPORT_ROOT, create=True)
PROJECTS = WORKSPACE.projects

from wizard import MODELS, dump_yaml  # noqa: E402
import cvss  # noqa: E402
import export  # noqa: E402
import engine  # noqa: E402
import sections as sectionlib  # noqa: E402
import validate as validatelib  # noqa: E402
from storage import revision, atomic_write  # noqa: E402
import project_history  # noqa: E402
import workflows  # noqa: E402
from languages import normalize_language, language_tag, language_index
from error_messages import message as backend_message, current_language, normalized_language, set_language, reset_language  # noqa: E402

from report_designs import THEMES as ALLOWED_THEMES  # noqa: E402


def sanitize_meta(data):
    """Fija theme/lang a valores permitidos (evita inyeccion de rutas y crashes)."""
    m = data.setdefault("meta", {})
    if m.get("theme") not in ALLOWED_THEMES:
        m["theme"] = "serio" if "serio" in ALLOWED_THEMES else (next(iter(ALLOWED_THEMES), "serio"))
    m["lang"] = normalize_language(m.get("lang"), engine.report_language(data) if not m.get("lang") else "es")
    return data

app = Flask(__name__, static_folder=str(HERE / "static"), static_url_path="/static")

app.secret_key = secrets.token_hex(32)
app.config.update(TRUSTED_HOSTS=["127.0.0.1", "localhost", "[::1]"], SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict")
app.config.update(LIBRARY_PATH=str(WORKSPACE.findings), DESIGN_LIBRARY_PATH=str(WORKSPACE.designs),
                  WORKSPACE_ROOT=str(WORKSPACE.root), WORKSPACE_EXTERNAL=WORKSPACE.external,
                  UI_LANGUAGE=normalized_language(os.environ.get('REPORT_GEN_UI_LANG', 'es')))
_PROJECT_LOCK = threading.RLock()
_BROWSER_WORKSPACES = {}


def browser_workspace_id():
    paths = (PROJECTS, Path(app.config['LIBRARY_PATH']), Path(app.config['DESIGN_LIBRARY_PATH']))
    key = tuple(str(path.absolute()) for path in paths)
    with _PROJECT_LOCK:
        if key not in _BROWSER_WORKSPACES:
            _BROWSER_WORKSPACES[key] = browser_namespace(*paths)
        return _BROWSER_WORKSPACES[key]


def project_lock(fn):
    @wraps(fn)
    def locked(*args, **kwargs):
        with _PROJECT_LOCK:
            project_history.recover_transactions(PROJECTS)
            return fn(*args, **kwargs)
    return locked


@app.before_request
def select_error_language():
    """The UI preference controls backend prose, never authored report data."""
    g.error_language_token = set_language(request.headers.get('X-UI-Language', 'es'))


@app.teardown_request
def release_error_language(_error):
    token = g.pop('error_language_token', None)
    if token is not None:
        reset_language(token)


@app.before_request
def protect_local_api():
    if not request.path.startswith("/api/"):
        return
    g.browser_workspace_id = browser_workspace_id()
    supplied_workspace = request.headers.get('X-Report-Gen-Workspace')
    resource_workspace = request.args.getlist('workspace_id')
    if ((supplied_workspace is not None and supplied_workspace != g.browser_workspace_id)
            or (resource_workspace and resource_workspace != [g.browser_workspace_id])):
        abort(409, backend_message('El servidor cambió de espacio de trabajo. Conserva tus borradores y recarga la página.',
                                   en='The server changed workspace. Keep your drafts and reload the page.'))
    if request.path in ("/api/projects/import", "/api/workspace/restore"):
        request.max_content_length = project_history.MAX_ARCHIVE + 1024 * 1024
    if request.path.endswith("/attachments/upload"):
        request.max_content_length = 17 * 1024 * 1024
    if request.path.endswith('/visual') and request.method == 'POST':
        request.max_content_length = 17 * 1024 * 1024
    origin = request.headers.get("Origin")
    if origin:
        try:
            parsed = urlsplit(origin)
        except ValueError:
            abort(403, backend_message('Origen no permitido'))
        if parsed.scheme != request.scheme or parsed.netloc != request.host:
            abort(403, backend_message('Origen no permitido'))
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        abort(403, backend_message('Solicitud entre sitios bloqueada'))
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        supplied = request.headers.get("X-CSRF-Token", "")
        token = session.get("csrf", "")
        if not token or not secrets.compare_digest(supplied.encode('utf-8'), token.encode('utf-8')):
            abort(403, backend_message('Sesión local caducada; vuelve a abrir la aplicación'))
        if request.content_length and not request.path.endswith(("/image", "/attachments/upload", "/visual")) and request.path not in ("/api/projects/import", "/api/workspace/restore") and not request.is_json:
            abort(415, backend_message('Se requiere application/json'))


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
    if ('/history/' in request.path and request.path.endswith('/visual')) or request.path.endswith('/retest-diff/visual'):
        response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; frame-ancestors 'self'"
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        if getattr(g, 'browser_workspace_id', None):
            response.headers['X-Report-Gen-Workspace'] = g.browser_workspace_id
        if response.status_code >= 400:
            response.headers['Content-Language'] = language_tag(request.headers.get('X-UI-Language', 'es'))
    return response


from werkzeug.exceptions import HTTPException  # noqa: E402

@app.errorhandler(HTTPException)
def api_error(error):
    detail = error.description
    # Bare aborts and router/body-limit failures use Werkzeug's fixed English
    # defaults. Translate only those authored framework defaults; a custom
    # diagnostic can contain opaque user data and must stay untouched.
    if detail == type(error).description:
        lang = request.headers.get('X-UI-Language', 'es')
        defaults = {
            400: ('Solicitud no válida', 'Invalid request', 'Solicitação inválida'),
            401: ('Autenticación requerida', 'Authentication required', 'Autenticação obrigatória'),
            403: ('Acceso no permitido', 'Access is not allowed', 'Acesso não permitido'),
            404: ('Recurso no encontrado', 'Resource not found', 'Recurso não encontrado'),
            405: ('Método no permitido', 'Method is not allowed', 'Método não permitido'),
            408: ('La solicitud agotó el tiempo de espera', 'Request timed out', 'A solicitação excedeu o tempo limite'),
            409: ('La solicitud entra en conflicto con el estado actual', 'Request conflicts with the current state', 'A solicitação conflita com o estado atual'),
            413: ('Solicitud demasiado grande', 'Request is too large', 'Solicitação grande demais'),
            415: ('Tipo de contenido no compatible', 'Unsupported content type', 'Tipo de conteúdo incompatível'),
            422: ('No se pudo procesar la solicitud', 'Request could not be processed', 'Não foi possível processar a solicitação'),
            429: ('Demasiadas solicitudes; vuelve a intentarlo', 'Too many requests; try again', 'Solicitações em excesso; tente novamente'),
            500: ('Error interno al procesar la solicitud', 'Internal error while processing the request', 'Erro interno ao processar a solicitação'),
            503: ('Servicio no disponible', 'Service unavailable', 'Serviço indisponível'),
        }
        if error.code in defaults:
            detail = defaults[error.code][language_index(lang)]
    response = jsonify({"error": detail})
    # Host/routing errors can precede before_request; inspect only the explicit
    # preference here, without loading a project or bypassing the host guard.
    response.headers['Content-Language'] = language_tag(request.headers.get('X-UI-Language', 'es'))
    return response, error.code


@app.errorhandler(ValueError)
def invalid_data(error):
    response = jsonify({'error': str(error)})
    response.headers['Content-Language'] = language_tag(current_language())
    return response, 422


@app.errorhandler(OSError)
def storage_error(error):
    app.logger.error('No se pudo completar la operación de almacenamiento: %s', error)
    response = jsonify({'error': backend_message('No se pudo completar la operación. Revisa el espacio y los permisos, y vuelve a abrir el proyecto.')})
    response.headers['Content-Language'] = language_tag(current_language())
    return response, 503


@app.route("/api/session")
def local_session():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    from version import __version__
    return jsonify({"csrf": session["csrf"], "version": __version__, "workspace_id": g.browser_workspace_id,
                    "ui_language": normalized_language(app.config['UI_LANGUAGE'])})


def scope_api_markup(markup):
    """Bind native preview images/links that cannot send the fetch header."""
    def scoped(match):
        parsed = urlsplit(unescape(match[2]))
        query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != 'workspace_id']
        query.append(('workspace_id', g.browser_workspace_id))
        value = urlunsplit(('', '', parsed.path, urlencode(query), parsed.fragment))
        return match[1] + escape(value, quote=True) + match[3]
    return re.sub(r'''(\b(?:src|href)=["'])(/api/[^"']+)(["'])''', scoped, str(markup))


def checked_data(data, final=False):
    if not isinstance(data, dict):
        abort(400, backend_message('Se esperaba un objeto JSON'))
    issues = validatelib.structure_issues(data, current_language())
    if issues:
        return_data_error(issues)
    data.setdefault("meta", {})
    data.setdefault("findings", [])
    sanitize_meta(data)
    if final:
        issues = validatelib.validate(data, lang=current_language())
        if any(level == "error" for level, _ in issues):
            return_data_error(issues)
    return data


def return_data_error(issues):
    abort(422, "; ".join(message for level, message in issues if level == "error"))


def require_revision(path):
    tag = request.headers.get("If-Match")
    if not tag:
        abort(428, backend_message('Falta la revisión del proyecto; vuelve a cargarlo'))
    if tag.strip('"') != revision(path):
        abort(409, backend_message('El proyecto cambió en otra pestaña. Conserva tus cambios y vuelve a cargarlo'))


def source_data(directory, final=False):
    data = _json_dict() if request.content_length else engine.load_engagement(directory / "engagement.yaml")
    return checked_data(data, final=final)


def slugify(s, *, new=False):
    s = str(s or "").strip().lower()
    s = "".join(c if c.isalnum() or c in "-_" else "-" for c in s)
    s = re.sub(r"-+", "-", s).strip("-") or "engagement"
    slug = s[:80].strip("-") or "engagement"
    return portable_project_slug(slug) if new else slug


def _json_dict():
    if not request.is_json:
        abort(415, backend_message('Se requiere application/json'))
    from input_guard import load_json
    try:
        b = load_json(request.get_data())
    except ValueError as exc:
        abort(422, str(exc))
    if not isinstance(b, dict):
        abort(400, backend_message('Se esperaba un objeto JSON'))
    return b


def proj_dir(slug):
    # Resolving first would hide an internal alias and permit editing/deleting
    # the aliased project under a different identity. Check lexical components
    # (including Windows reparse points) before following any path.
    candidate = PROJECTS / slugify(slug)
    _no_links(candidate)
    base = PROJECTS.resolve()
    d = candidate.resolve()
    # defensa en profundidad: el resultado debe quedar dentro de projects/
    if base != d.parent:
        abort(404, backend_message('proyecto no encontrado'))
    if not d.exists():
        abort(404, backend_message('proyecto no encontrado: {p0}', p0=slug))
    return d


def load_owasp(kind):
    p = HERE / "data" / f"owasp_{kind}.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


# ---- UI --------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(str(HERE / "static"), "index.html")


# ---- Designs / catalogos ---------------------------------------------------
@app.route("/api/md", methods=["POST"])
def md_preview():
    body = _json_dict()
    slug = body.get("slug", "")
    if not isinstance(body.get("text", ""), str) or not isinstance(slug, str):
        abort(400, backend_message('Texto o proyecto inválido'))
    return jsonify({"html": scope_api_markup(engine.md(body.get("text", ""), img_base=f"/api/projects/{slugify(slug)}/resource/" if slug else ""))})


@app.route("/api/validate", methods=["POST"])
def validate_engagement():
    data = _json_dict()
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    lang = current_language() if 'X-UI-Language' in request.headers else request.args.get("lang") or meta.get("lang") or "es"
    issues = validatelib.validate(data, lang=lang)
    response = jsonify({"issues": [{"level": lvl, "message": msg} for lvl, msg in issues]})
    response.headers["Content-Language"] = language_tag(lang)
    return response


@app.route("/api/sections/catalog")
def sections_catalog():
    return jsonify(sectionlib.load_catalog())


@app.route("/api/designs")
def designs():
    return jsonify([{"key": k, **v} for k, v in MODELS.items()])


@app.route("/api/cwe")
def cwe_list():
    path = HERE / "data" / "cwe.json"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return jsonify({k: v for k, v in data.items() if not k.startswith("_")})


@app.route("/api/presets")
def presets_list():
    return jsonify([{"id": p["id"], "name_es": p.get("name_es", p["id"]), "name_en": p.get("name_en", p["id"]),
                     "desc_es": p.get("desc_es", ""), "desc_en": p.get("desc_en", ""), "theme": p.get("theme", ""),
                     "family": p.get("family", ""), "cert_es": p.get("cert_es", ""), "cert_en": p.get("cert_en", "")}
                    for p in sectionlib.load_presets()])


@app.route("/api/owasp/<kind>")
def owasp(kind):
    if kind not in ("web", "llm"):
        abort(404)
    return jsonify(load_owasp(kind))


@app.route("/api/cvss", methods=["POST"])
def api_cvss():
    # Politica de despacho:
    #  - Si `version` esta presente, se respeta estrictamente.
    #  - Si falta `version`, compat legacy: prefijo CVSS:4.0/ -> 4.0; resto/metrics -> 3.1.
    #  - Si `version` y el prefijo del vector se contradicen -> 400 (nunca cross-version).
    body = _json_dict()
    vector = str(body.get("vector") or "")
    version = body.get("version")
    if version is None:
        version = "4.0" if vector.startswith("CVSS:4.0/") else "3.1"
    if version == "3.1":
        if vector and not vector.startswith("CVSS:3.1/"):
            abort(400, backend_message('se esperaba un vector CVSS:3.1/'))
        try:
            metrics = body.get("metrics") or cvss.parse_vector(vector)
            return jsonify(cvss.compute(metrics))
        except Exception:
            abort(400, backend_message('vector o metricas CVSS 3.1 invalidos'))
    if version == "4.0":
        if not vector.startswith("CVSS:4.0/"):
            abort(400, backend_message('se esperaba un vector CVSS:4.0/'))
        try:
            return jsonify(cvss.score(vector))  # {score, severity, vector, macrovector}; ValueError si invalido
        except ValueError:
            abort(400, backend_message('vector CVSS 4.0 invalido'))
    abort(400, backend_message('version CVSS no soportada'))


# ---- Proyectos -------------------------------------------------------------
def new_project_destination(body):
    """Shared input and portable-name boundary for both creation routes."""
    if any(value is not None and not isinstance(value, str) for value in body.values()):
        abort(400, backend_message('Los datos del proyecto deben ser texto'))
    slug = slugify(body.get("slug") or body.get("title") or "engagement", new=True)
    directory = PROJECTS / slug
    if directory.exists() or (PROJECTS.exists() and any(path.name.casefold() == slug.casefold() for path in PROJECTS.iterdir())):
        abort(409, backend_message('Ya existe un proyecto con un nombre equivalente en mayúsculas o Unicode; usa otro nombre'))
    return slug, directory


@app.route("/api/projects")
@project_lock
def list_projects():
    from project_catalog import list_projects as project_catalog
    return jsonify(project_catalog(PROJECTS))


@app.route("/api/projects", methods=["POST"])
@project_lock
def create_project():
    body = _json_dict()
    slug, d = new_project_destination(body)
    model = MODELS.get(body.get("model", "corporativo-es")) or MODELS["corporativo-es"]
    appearance = body.get('appearance')
    if appearance is not None and appearance not in ALLOWED_THEMES:
        abort(422, backend_message('Diseño general desconocido'))
    meta = {
        "lang": model["lang"],
        "report_title": body.get("title", ("Nuevo informe", "New report", "Novo relatório")[language_index(model["lang"])]),
        "report_subtitle": model["subtitle"],
        "client": body.get("client", ""),
        "assessor": "",
        "assessor_title": "",
        "date": body.get("date", ""),
        "version": "1.0",
        "theme": model["theme"],
        "branding": {"wordmark": "iphobiuss", "byline": "Sebastian Latorre Munoz / iphobiuss",
                     "accent": "#1f5fa8" if model["theme"] == "corporativo" else "#39ff14",
                     "confidential_text": model["confidential"]},
        "contacts": {"client": [], "assessor": []},
        "scope": [],
    }
    preset = body.get("preset")
    pdef = sectionlib.preset_by_id(preset) if preset else None
    if pdef:  # la plantilla fija el diseno (tema + acento)
        if pdef.get("theme") in ALLOWED_THEMES:
            meta["theme"] = pdef["theme"]
        if pdef.get("accent"):
            meta["branding"]["accent"] = pdef["accent"]
    if appearance is not None:
        # Explicit gallery selection is independent of the selected structure.
        meta['theme'] = appearance
        meta['branding'].pop('accent', None)
    sections = sectionlib.preset_sections(preset, model["lang"]) if preset else sectionlib.default_enabled()
    report = {"sections": sections}
    with project_history.transaction(d) as staged:
        (staged / 'img').mkdir(exist_ok=True)
        project_history.save(staged, {"meta": meta, "report": report, "findings": []})
    return jsonify({"slug": slug})


@app.route("/api/projects/<slug>")
@project_lock
def get_project(slug):
    d = proj_dir(slug)
    try:
        data = engine.load_engagement(d / "engagement.yaml")
    except (ValueError, yaml.YAMLError) as exc:
        abort(422, str(exc))
    from copy import deepcopy
    before = deepcopy(data)
    workflows.normalize(data)
    if data != before:
        project_history.save(d, data)
    response = jsonify(data)
    response.set_etag(revision(d / "engagement.yaml"))
    return response


@app.route("/api/projects/<slug>", methods=["PUT"])
@project_lock
def save_project(slug):
    d = proj_dir(slug)
    data = checked_data(_json_dict())
    require_revision(d / "engagement.yaml")
    project_history.save(d, data)
    response = jsonify({"ok": True, "issues": [{"level": level, "message": message} for level, message in validatelib.validate(data)]})
    response.set_etag(revision(d / "engagement.yaml"))
    return response


@app.route("/api/projects/<slug>/restore", methods=["POST"])
@project_lock
def restore_project(slug):
    d = proj_dir(slug)
    target = d / "engagement.yaml"
    require_revision(target)
    backup = d / "engagement.yaml.bak"
    # Recover the preceding YAML revision together with its own image set.
    records = project_history.history(d)
    current = revision(target)
    previous_version = next((r for r in records if r['files'].get('engagement.yaml') != current), None)
    if previous_version:
        try:
            project_history.restore(d, previous_version['id'])
        except ValueError as exc:
            abort(422, str(exc))
    elif backup.is_file():
        # Compatibility for installations that only have the pre-0.13 YAML backup.
        previous = checked_data(engine.load_engagement(backup))
        project_history.save(d, previous)
    else:
        abort(404, backend_message('No hay una versión anterior'))
    response = jsonify({"ok": True})
    response.set_etag(revision(target))
    return response


@app.route("/api/projects/<slug>", methods=["DELETE"])
@project_lock
def delete_project(slug):
    import shutil
    d = proj_dir(slug)  # slugify neutraliza traversal; siempre bajo PROJECTS/
    if not d.exists():
        abort(404)
    require_revision(d / "engagement.yaml")
    shutil.rmtree(d)
    return jsonify({"ok": True})


MAX_IMAGE_BYTES = 12 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_BYTES + 1024 * 1024  # limite HTTP (margen multipart)

# Formato real detectado por Pillow -> extension canonica. El nombre del usuario
# NUNCA decide el tipo del recurso servido.
IMAGE_EXT = {"PNG": ".png", "JPEG": ".jpg", "GIF": ".gif", "WEBP": ".webp"}


@app.route("/api/projects/<slug>/image", methods=["POST"])
@project_lock
def upload_image(slug):
    from werkzeug.utils import secure_filename
    from PIL import Image
    from io import BytesIO
    import uuid
    d = proj_dir(slug)
    f = request.files.get("file")
    if not f or not f.filename:
        abort(400, backend_message('sin archivo'))
    # lectura acotada: nunca mas de MAX+1 en memoria (defensa aunque falle el limite HTTP)
    blob = f.read(MAX_IMAGE_BYTES + 1)
    if len(blob) > MAX_IMAGE_BYTES:
        abort(413, backend_message('imagen demasiado grande'))
    # validacion real de imagen (no solo magic bytes) y formato permitido
    try:
        with Image.open(BytesIO(blob)) as img:
            fmt = img.format
            if img.width * img.height > 25_000_000:
                abort(413, backend_message('imagen mayor que 25 megapíxeles'))
            img.verify()
    except HTTPException:
        raise
    except Exception:
        abort(400, backend_message('el archivo no es una imagen valida'))
    if fmt not in IMAGE_EXT:
        abort(400, backend_message('formato no permitido (usa png, jpg, gif o webp)'))
    # nombre saneado + extension DERIVADA del formato real detectado
    stem = secure_filename(Path(f.filename).stem)
    if not stem or stem in (".", ".."):
        stem = f"img_{uuid.uuid4().hex[:8]}"
    name = stem[:80] + "_" + uuid.uuid4().hex[:12] + IMAGE_EXT[fmt]
    _no_links(d / "img")
    (d / "img").mkdir(exist_ok=True)
    atomic_write(d / "img" / name, blob)
    return jsonify({"src": f"img/{name}"})


@app.route("/api/projects/<slug>/img/<path:name>")
def get_image(slug, name):
    return project_image(slug, 'img/' + name)


@app.route("/api/projects/<slug>/resource/<path:name>")
@project_lock
def project_image(slug, name):
    from resources import local_image
    from urllib.parse import quote
    try:
        path = local_image(quote(name, safe='/'), proj_dir(slug))
    except ValueError:
        abort(404, backend_message('Imagen no disponible'))
    return send_file(path)


@app.route("/theme/<path:name>")
def theme_file(name):
    return send_from_directory(str(REPORT_ROOT / "themes"), name)


@app.route("/api/projects/<slug>/preview", methods=["POST"])
@project_lock
def preview_html(slug):
    d = proj_dir(slug)
    data = source_data(d)
    try:
        engine.number_figures(data["findings"])
        language = engine.load_lang(engine.report_language(data))
        html = engine.render_html(engine.build_env(), data, d, {}, False, language,
            theme_href=f"/theme/{data['meta']['theme']}.css", img_base=f"/api/projects/{slugify(slug)}/resource/")
    except (ValueError, TypeError) as exc:
        abort(422, str(exc))
    html = html.replace("<head>", f'<head><base href="{escape(request.host_url, quote=True)}">', 1)
    return Response(scope_api_markup(html), mimetype="text/html")


@app.route("/api/projects/<slug>/render", methods=["POST"])
def render_project(slug):
    return render_snapshot(slug, "pdf", attachment=False)


from export_formats import REGISTRY as EXPORT_FORMATS, catalog as export_catalog  # noqa: E402
MIMES = {key: spec.mime for key, spec in EXPORT_FORMATS.items()}

@app.get('/api/export-formats')
def export_formats():
    return jsonify(export_catalog())



@app.route("/api/projects/<slug>/export/<fmt>", methods=["POST"])
def export_project(slug, fmt):
    if fmt not in MIMES:
        abort(404)
    return render_snapshot(slug, fmt)


def render_snapshot(slug, fmt, attachment=True):
    try:
        with tempfile.TemporaryDirectory(prefix="report-gen-export-") as temp:
            import shutil
            from lxml import html as html_parser
            from urllib.parse import quote
            from urllib.request import url2pathname
            from resources import local_image
            root = Path(temp) / 'project'
            root.mkdir()
            snapshot = root / 'engagement.yaml'
            # Copy one consistent YAML/image state; release the lock before rendering.
            with _PROJECT_LOCK:
                d = proj_dir(slug)
                data = source_data(d, final=True)
                markup = engine.render_html(engine.build_env(), data, d, {}, False,
                                            engine.load_lang(engine.report_language(data)))
                sources = {node.get('src') for node in html_parser.fromstring(markup).xpath('//img[@src]')}
                for source in sources:
                    parsed = urlsplit(source)
                    relative = Path(url2pathname(parsed.path)).relative_to(d.resolve()).as_posix()
                    image = local_image(quote(relative, safe='/'), d)
                    target_image = root / relative
                    target_image.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(image, target_image)
                dump_yaml(data, snapshot)
            suffix = "zip" if fmt == "md" else fmt
            target = Path(temp) / f"report.{suffix}"
            out = export.export(snapshot, "mdzip" if fmt == "md" else fmt, target)
            payload = out.read_bytes()
        return send_file(BytesIO(payload), mimetype=MIMES[fmt], as_attachment=attachment,
                         download_name=f"{slugify(slug)}.{suffix}")
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        abort(422, str(exc))


from workflow_api import register as register_workflows  # noqa: E402
register_workflows(sys.modules[__name__])
from dashboard_api import register as register_dashboard  # noqa: E402
register_dashboard(sys.modules[__name__])
from remediation_api import register as register_remediation  # noqa: E402
register_remediation(sys.modules[__name__])
from bulk_api import register as register_bulk  # noqa: E402
register_bulk(sys.modules[__name__])
from update_api import register as register_update  # noqa: E402
register_update(sys.modules[__name__])
from retest_api import register as register_retest_views  # noqa: E402
register_retest_views(sys.modules[__name__])
from experience_api import register as register_experience  # noqa: E402
register_experience(sys.modules[__name__])
from design_api import register as register_designs  # noqa: E402
register_designs(sys.modules[__name__])
from workspace_api import register as register_workspace  # noqa: E402
register_workspace(sys.modules[__name__])
from backup_routine_api import register as register_backup_routine  # noqa: E402
backup_routine = register_backup_routine(sys.modules[__name__])
from progress_api import register as register_progress  # noqa: E402
register_progress(sys.modules[__name__])
from workbench_api import register as register_workbench  # noqa: E402
register_workbench(sys.modules[__name__])


from publication_api import register as register_publication
register_publication(sys.modules[__name__])


def create_local_server(port=8080):
    """One process preserves the shared project lock; never expose the editor."""
    from waitress import create_server
    server = create_server(app, host='127.0.0.1', port=port, threads=4,
                           max_request_body_size=project_history.MAX_ARCHIVE + 1024 * 1024,
                           channel_timeout=180, clear_untrusted_proxy_headers=True)
    routine = backup_routine()
    original_close = server.close
    def close_with_backups():
        routine.stop()
        original_close()
    server.close = close_with_backups
    routine.start()
    return server



from attachments_api import register as register_attachments  # noqa: E402
register_attachments(sys.modules[__name__])

from privacy_api import register as register_privacy  # noqa: E402
register_privacy(sys.modules[__name__])

from insights_api import register as register_insights  # noqa: E402
register_insights(sys.modules[__name__])
from audience_api import register as register_audiences  # noqa: E402
register_audiences(sys.modules[__name__])
from assistant_api import register as register_assistant  # noqa: E402
register_assistant(sys.modules[__name__])
from visual_api import register as register_visual  # noqa: E402
register_visual(sys.modules[__name__])

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = create_local_server(port)
    print(f"report-gen webapp -> http://127.0.0.1:{server.effective_port}", flush=True)
    try:
        server.run()
    finally:
        server.close()
