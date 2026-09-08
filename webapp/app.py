#!/usr/bin/env python3
"""report-gen webapp: editor local tipo SysReptor sobre el motor existente.

Arranca en http://127.0.0.1:8080. Cada proyecto es una carpeta en projects/
con su engagement.yaml e img/. El render reusa ../engine.py (WeasyPrint/Chromium).
"""
import re
import subprocess
import secrets
import threading
import tempfile
from functools import wraps
from io import BytesIO
from urllib.parse import urlsplit
from html import escape
import sys
from pathlib import Path

import yaml
from flask import Flask, jsonify, request, send_file, send_from_directory, abort, Response, session

HERE = Path(__file__).resolve().parent
REPORT_ROOT = HERE.parent
PROJECTS = HERE / "projects"
PROJECTS.mkdir(exist_ok=True)
sys.path.insert(0, str(REPORT_ROOT))

from wizard import MODELS, dump_yaml  # noqa: E402
import cvss  # noqa: E402
import export  # noqa: E402
import engine  # noqa: E402
import sections as sectionlib  # noqa: E402
import validate as validatelib  # noqa: E402
from storage import revision, atomic_write  # noqa: E402
import project_history  # noqa: E402
import workflows  # noqa: E402

ALLOWED_THEMES = {p.stem for p in (REPORT_ROOT / "themes").glob("*.css") if p.stem != "_common"}
ALLOWED_LANGS = {"es", "en"}


def sanitize_meta(data):
    """Fija theme/lang a valores permitidos (evita inyeccion de rutas y crashes)."""
    m = data.setdefault("meta", {})
    if m.get("theme") not in ALLOWED_THEMES:
        m["theme"] = "serio" if "serio" in ALLOWED_THEMES else (next(iter(ALLOWED_THEMES), "serio"))
    if m.get("lang") not in ALLOWED_LANGS:
        m["lang"] = "es"
    return data

app = Flask(__name__, static_folder=str(HERE / "static"), static_url_path="/static")

app.secret_key = secrets.token_hex(32)
app.config.update(TRUSTED_HOSTS=["127.0.0.1", "localhost", "[::1]"], SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict")
_PROJECT_LOCK = threading.RLock()


def project_lock(fn):
    @wraps(fn)
    def locked(*args, **kwargs):
        with _PROJECT_LOCK:
            return fn(*args, **kwargs)
    return locked


@app.before_request
def protect_local_api():
    if not request.path.startswith("/api/"):
        return
    if request.path == "/api/projects/import":
        request.max_content_length = project_history.MAX_ARCHIVE + 1024 * 1024
    origin = request.headers.get("Origin")
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme != request.scheme or parsed.netloc != request.host:
            abort(403, "Origen no permitido")
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        abort(403, "Solicitud entre sitios bloqueada")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        supplied = request.headers.get("X-CSRF-Token", "")
        token = session.get("csrf", "")
        if not token or not secrets.compare_digest(supplied, token):
            abort(403, "Sesión local caducada; vuelve a abrir la aplicación")
        if request.content_length and not request.path.endswith("/image") and request.path != "/api/projects/import" and not request.is_json:
            abort(415, "Se requiere application/json")


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


from werkzeug.exceptions import HTTPException  # noqa: E402

@app.errorhandler(HTTPException)
def api_error(error):
    return jsonify({"error": error.description}), error.code


@app.route("/api/session")
def local_session():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return jsonify({"csrf": session["csrf"]})


def checked_data(data, final=False):
    if not isinstance(data, dict):
        abort(400, "Se esperaba un objeto JSON")
    issues = validatelib.structure_issues(data)
    if issues:
        return_data_error(issues)
    data.setdefault("meta", {})
    data.setdefault("findings", [])
    sanitize_meta(data)
    if final:
        issues = validatelib.validate(data)
        if any(level == "error" for level, _ in issues):
            return_data_error(issues)
    return data


def return_data_error(issues):
    abort(422, "; ".join(message for level, message in issues if level == "error"))


def require_revision(path):
    tag = request.headers.get("If-Match")
    if not tag:
        abort(428, "Falta la revisión del proyecto; vuelve a cargarlo")
    if tag.strip('"') != revision(path):
        abort(409, "El proyecto cambió en otra pestaña. Conserva tus cambios y vuelve a cargarlo")


def source_data(directory, final=False):
    data = _json_dict() if request.content_length else engine.load_engagement(directory / "engagement.yaml")
    return checked_data(data, final=final)


def slugify(s):
    s = str(s or "").strip().lower()
    s = "".join(c if c.isalnum() or c in "-_" else "-" for c in s)
    s = re.sub(r"-+", "-", s).strip("-") or "engagement"
    return s[:80].strip("-") or "engagement"  # cap de longitud: evita OSError con slugs enormes


def _json_dict():
    if not request.is_json:
        abort(415, "Se requiere application/json")
    b = request.get_json(silent=True)
    if not isinstance(b, dict):
        abort(400, "Se esperaba un objeto JSON")
    return b


def proj_dir(slug):
    base = PROJECTS.resolve()
    d = (PROJECTS / slugify(slug)).resolve()
    # defensa en profundidad: el resultado debe quedar dentro de projects/
    if base != d.parent:
        abort(404, "proyecto no encontrado")
    if not d.exists():
        abort(404, f"proyecto no encontrado: {slug}")
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
        abort(400, "Texto o proyecto inválido")
    return jsonify({"html": str(engine.md(body.get("text", ""), img_base=f"/api/projects/{slugify(slug)}/" if slug else ""))})


@app.route("/api/validate", methods=["POST"])
def validate_engagement():
    data = _json_dict()
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    lang = request.args.get("lang") or meta.get("lang") or "es"
    issues = validatelib.validate(data, lang=lang)
    return jsonify({"issues": [{"level": lvl, "message": msg} for lvl, msg in issues]})


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
            abort(400, "se esperaba un vector CVSS:3.1/")
        try:
            metrics = body.get("metrics") or cvss.parse_vector(vector)
            return jsonify(cvss.compute(metrics))
        except Exception:
            abort(400, "vector o metricas CVSS 3.1 invalidos")
    if version == "4.0":
        if not vector.startswith("CVSS:4.0/"):
            abort(400, "se esperaba un vector CVSS:4.0/")
        try:
            return jsonify(cvss.score(vector))  # {score, severity, vector, macrovector}; ValueError si invalido
        except ValueError:
            abort(400, "vector CVSS 4.0 invalido")
    abort(400, "version CVSS no soportada")


# ---- Proyectos -------------------------------------------------------------
@app.route("/api/projects")
def list_projects():
    out = []
    for d in sorted(PROJECTS.iterdir()):
        if not d.is_dir() or d.is_symlink() or d.name.startswith("."):
            continue
        y = d / "engagement.yaml"
        if y.exists():
            try:
                meta = (yaml.safe_load(y.read_text(encoding="utf-8")) or {}).get("meta", {})
            except Exception:
                meta = {}
            if not isinstance(meta, dict):
                meta = {}
            out.append({"slug": d.name, "title": meta.get("report_title", d.name),
                        "theme": meta.get("theme", ""), "lang": meta.get("lang", "")})
    return jsonify(out)


@app.route("/api/projects", methods=["POST"])
@project_lock
def create_project():
    body = _json_dict()
    if any(value is not None and not isinstance(value, str) for value in body.values()):
        abort(400, "Los datos del proyecto deben ser texto")
    model = MODELS.get(body.get("model", "corporativo-es")) or MODELS["corporativo-es"]
    slug = slugify(body.get("slug") or body.get("title") or "engagement")
    d = PROJECTS / slug
    if d.exists():
        abort(409, "ya existe un proyecto con ese nombre")
    (d / "img").mkdir(parents=True)
    meta = {
        "lang": model["lang"],
        "report_title": body.get("title", "Nuevo informe"),
        "report_subtitle": model["subtitle"],
        "client": body.get("client", ""),
        "assessor": "Sebastian Latorre Munoz (iphobiuss)",
        "assessor_title": "AI Red Team Operator",
        "date": body.get("date", ""),
        "version": "1.0",
        "theme": model["theme"],
        "branding": {"wordmark": "iphobiuss", "byline": "Sebastian Latorre Munoz / iphobiuss",
                     "accent": "#1f5fa8" if model["theme"] == "corporativo" else "#39ff14",
                     "confidential_text": model["confidential"]},
        "contacts": {"client": [], "assessor": [
            {"name": "Sebastian Latorre Munoz", "title": "AI Red Team Operator", "email": ""}]},
        "scope": [],
    }
    preset = body.get("preset")
    pdef = sectionlib.preset_by_id(preset) if preset else None
    if pdef:  # la plantilla fija el diseno (tema + acento)
        if pdef.get("theme") in ALLOWED_THEMES:
            meta["theme"] = pdef["theme"]
        if pdef.get("accent"):
            meta["branding"]["accent"] = pdef["accent"]
    sections = sectionlib.preset_sections(preset, model["lang"]) if preset else sectionlib.default_enabled()
    report = {"sections": sections}
    project_history.save(d, {"meta": meta, "report": report, "findings": []})
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
        abort(404, "No hay una versión anterior")
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
        abort(400, "sin archivo")
    # lectura acotada: nunca mas de MAX+1 en memoria (defensa aunque falle el limite HTTP)
    blob = f.read(MAX_IMAGE_BYTES + 1)
    if len(blob) > MAX_IMAGE_BYTES:
        abort(413, "imagen demasiado grande")
    # validacion real de imagen (no solo magic bytes) y formato permitido
    try:
        with Image.open(BytesIO(blob)) as img:
            fmt = img.format
            if img.width * img.height > 25_000_000:
                abort(413, "imagen mayor que 25 megapíxeles")
            img.verify()
    except HTTPException:
        raise
    except Exception:
        abort(400, "el archivo no es una imagen valida")
    if fmt not in IMAGE_EXT:
        abort(400, "formato no permitido (usa png, jpg, gif o webp)")
    # nombre saneado + extension DERIVADA del formato real detectado
    stem = secure_filename(Path(f.filename).stem)
    if not stem or stem in (".", ".."):
        stem = f"img_{uuid.uuid4().hex[:8]}"
    name = stem[:80] + "_" + uuid.uuid4().hex[:12] + IMAGE_EXT[fmt]
    (d / "img").mkdir(exist_ok=True)
    atomic_write(d / "img" / name, blob)
    return jsonify({"src": f"img/{name}"})


@app.route("/api/projects/<slug>/img/<path:name>")
def get_image(slug, name):
    return send_from_directory(str(proj_dir(slug) / "img"), name)


@app.route("/theme/<path:name>")
def theme_file(name):
    return send_from_directory(str(REPORT_ROOT / "themes"), name)


@app.route("/api/projects/<slug>/preview", methods=["POST"])
def preview_html(slug):
    d = proj_dir(slug)
    data = source_data(d)
    try:
        engine.number_figures(data["findings"])
        language = engine.load_lang(data["meta"].get("lang", "es"))
        html = engine.render_html(engine.build_env(), data, d, {}, False, language,
            theme_href=f"/theme/{data['meta']['theme']}.css", img_base=f"/api/projects/{slugify(slug)}/")
    except (ValueError, TypeError) as exc:
        abort(422, str(exc))
    html = html.replace("<head>", f'<head><base href="{escape(request.host_url, quote=True)}">', 1)
    return Response(html, mimetype="text/html")


@app.route("/api/projects/<slug>/render", methods=["POST"])
def render_project(slug):
    return render_snapshot(slug, "pdf", attachment=False)


MIMES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "md": "application/zip",
}


@app.route("/api/projects/<slug>/export/<fmt>", methods=["POST"])
def export_project(slug, fmt):
    if fmt not in MIMES:
        abort(404)
    return render_snapshot(slug, fmt)


def render_snapshot(slug, fmt, attachment=True):
    d = proj_dir(slug)
    data = source_data(d, final=True)
    snapshot = None
    try:
        # Snapshot YAML lives beside img/ but never overwrites the saved project.
        with tempfile.NamedTemporaryFile(dir=d, prefix=".render-", suffix=".yaml", delete=False) as f:
            snapshot = Path(f.name)
        dump_yaml(data, snapshot)
        with tempfile.TemporaryDirectory(prefix="report-gen-export-") as temp:
            suffix = "zip" if fmt == "md" else fmt
            target = Path(temp) / f"report.{suffix}"
            out = export.export(snapshot, "mdzip" if fmt == "md" else fmt, target)
            payload = out.read_bytes()
        return send_file(BytesIO(payload), mimetype=MIMES[fmt], as_attachment=attachment,
                         download_name=f"{slugify(slug)}.{suffix}")
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        abort(422, str(exc))
    finally:
        if snapshot:
            snapshot.unlink(missing_ok=True)
            snapshot.with_suffix(snapshot.suffix + ".bak").unlink(missing_ok=True)


from workflow_api import register as register_workflows  # noqa: E402
register_workflows(sys.modules[__name__])


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"report-gen webapp -> http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
