#!/usr/bin/env python3
"""report-gen webapp: editor local tipo SysReptor sobre el motor existente.

Arranca en http://127.0.0.1:8080. Cada proyecto es una carpeta en projects/
con su engagement.yaml e img/. El render reusa ../engine.py (WeasyPrint/Chromium).
"""
import re
import subprocess
import sys
from pathlib import Path

import yaml
from flask import Flask, jsonify, request, send_file, send_from_directory, abort, Response

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


def slugify(s):
    s = (s or "").strip().lower()
    s = "".join(c if c.isalnum() or c in "-_" else "-" for c in s)
    s = re.sub(r"-+", "-", s).strip("-") or "engagement"
    return s[:80].strip("-") or "engagement"  # cap de longitud: evita OSError con slugs enormes


def _json_dict(force=True):
    b = request.get_json(force=force, silent=True)
    return b if isinstance(b, dict) else {}


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
    engine.set_img_base(f"/api/projects/{slug}/" if slug else "")
    html = str(engine.md(body.get("text", "")))
    return jsonify({"html": html})


@app.route("/api/validate", methods=["POST"])
def validate_engagement():
    data = _json_dict()
    issues = validatelib.validate(data)
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
                     "desc_es": p.get("desc_es", ""), "desc_en": p.get("desc_en", "")}
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
        y = d / "engagement.yaml"
        if y.exists():
            try:
                meta = (yaml.safe_load(y.read_text(encoding="utf-8")) or {}).get("meta", {})
            except Exception:
                meta = {}
            out.append({"slug": d.name, "title": meta.get("report_title", d.name),
                        "theme": meta.get("theme", ""), "lang": meta.get("lang", "")})
    return jsonify(out)


@app.route("/api/projects", methods=["POST"])
def create_project():
    body = _json_dict()
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
    sections = sectionlib.preset_sections(preset, model["lang"]) if preset else sectionlib.default_enabled()
    report = {"sections": sections}
    dump_yaml({"meta": meta, "report": report, "findings": []}, d / "engagement.yaml")
    return jsonify({"slug": slug})


@app.route("/api/projects/<slug>")
def get_project(slug):
    d = proj_dir(slug)
    data = yaml.safe_load((d / "engagement.yaml").read_text(encoding="utf-8"))
    return jsonify(data)


@app.route("/api/projects/<slug>", methods=["PUT"])
def save_project(slug):
    d = proj_dir(slug)
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        abort(400, "cuerpo JSON invalido (se esperaba un objeto)")
    data.setdefault("meta", {})
    data.setdefault("findings", [])
    sanitize_meta(data)
    dump_yaml(data, d / "engagement.yaml")
    return jsonify({"ok": True})


@app.route("/api/projects/<slug>", methods=["DELETE"])
def delete_project(slug):
    import shutil
    d = proj_dir(slug)  # slugify neutraliza traversal; siempre bajo PROJECTS/
    if not d.exists():
        abort(404)
    shutil.rmtree(d, ignore_errors=True)
    return jsonify({"ok": True})


MAX_IMAGE_BYTES = 12 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_BYTES + 1024 * 1024  # limite HTTP (margen multipart)

# Formato real detectado por Pillow -> extension canonica. El nombre del usuario
# NUNCA decide el tipo del recurso servido.
IMAGE_EXT = {"PNG": ".png", "JPEG": ".jpg", "GIF": ".gif", "WEBP": ".webp"}


@app.route("/api/projects/<slug>/image", methods=["POST"])
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
            img.verify()
    except Exception:
        abort(400, "el archivo no es una imagen valida")
    if fmt not in IMAGE_EXT:
        abort(400, "formato no permitido (usa png, jpg, gif o webp)")
    # nombre saneado + extension DERIVADA del formato real detectado
    stem = secure_filename(Path(f.filename).stem)
    if not stem or stem in (".", ".."):
        stem = f"img_{uuid.uuid4().hex[:8]}"
    name = stem + IMAGE_EXT[fmt]
    (d / "img").mkdir(exist_ok=True)
    (d / "img" / name).write_bytes(blob)
    return jsonify({"src": f"img/{name}"})


@app.route("/api/projects/<slug>/img/<path:name>")
def get_image(slug, name):
    return send_from_directory(str(proj_dir(slug) / "img"), name)


@app.route("/theme/<path:name>")
def theme_file(name):
    return send_from_directory(str(REPORT_ROOT / "themes"), name)


@app.route("/api/projects/<slug>/preview", methods=["POST"])
def preview_html(slug):
    """HTML de vista previa en vivo (rapido, una sola pasada, sin PDF)."""
    d = proj_dir(slug)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = yaml.safe_load((d / "engagement.yaml").read_text(encoding="utf-8"))
    data.setdefault("meta", {})
    data.setdefault("findings", [])
    sanitize_meta(data)
    try:
        engine.number_figures(data["findings"])
        L = engine.load_lang(data["meta"].get("lang", "en"))
        env = engine.build_env()
        html = engine.render_html(env, data, d, {}, False, L,
                                  theme_href=f"/theme/{data['meta'].get('theme', 'serio')}.css",
                                  img_base=f"/api/projects/{slug}/")
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500
    html = html.replace("<head>", f'<head><base href="{request.host_url}">', 1)
    return Response(html, mimetype="text/html")


@app.route("/api/projects/<slug>/render", methods=["POST"])
def render_project(slug):
    d = proj_dir(slug)
    # guardar lo que venga antes de renderizar
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        data.setdefault("meta", {})
        data.setdefault("findings", [])
        sanitize_meta(data)
        dump_yaml(data, d / "engagement.yaml")
    out_pdf = d / "report.pdf"
    proc = subprocess.run(
        [sys.executable, str(REPORT_ROOT / "engine.py"), str(d / "engagement.yaml"), "-o", str(out_pdf)],
        cwd=str(REPORT_ROOT), capture_output=True, text=True)
    if proc.returncode != 0 or not out_pdf.exists():
        return jsonify({"error": proc.stderr or proc.stdout or "render fallido"}), 500
    return send_file(str(out_pdf), mimetype="application/pdf")


MIMES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "md": "text/markdown",
}


@app.route("/api/projects/<slug>/export/<fmt>", methods=["POST"])
def export_project(slug, fmt):
    d = proj_dir(slug)
    if fmt not in MIMES:
        abort(404)
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        data.setdefault("meta", {})
        data.setdefault("findings", [])
        sanitize_meta(data)
        dump_yaml(data, d / "engagement.yaml")
    try:
        out = export.export(d / "engagement.yaml", fmt)
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500
    return send_file(str(out), mimetype=MIMES[fmt], as_attachment=True, download_name=f"{slug}.{fmt}")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"report-gen webapp -> http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
