"""Tests de seguridad de la app web con el test client de Flask (sin servidor):
saneo de theme/lang, path traversal, nombre de imagen malicioso y tema invalido."""
import io
import shutil

import app as webapp


def _client():
    webapp.app.config["TESTING"] = True
    return webapp.app.test_client()


def _cleanup(slug):
    d = webapp.PROJECTS / slug
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def test_sanitize_meta_clamps_theme_and_lang():
    data = {"meta": {"theme": "../../etc/passwd", "lang": "xx"}, "findings": []}
    webapp.sanitize_meta(data)
    assert data["meta"]["theme"] in webapp.ALLOWED_THEMES
    assert data["meta"]["lang"] == "es"


def test_theme_route_blocks_traversal():
    c = _client()
    assert c.get("/theme/..%2f..%2fapp.py").status_code == 404
    assert c.get("/theme/../app.py").status_code == 404


def test_unknown_project_404():
    c = _client()
    assert c.get("/api/projects/no-existe-xyz").status_code == 404


def _png_bytes(w=2, h=2):
    from PIL import Image
    from io import BytesIO
    buf = BytesIO()
    Image.new("RGB", (w, h), "red").save(buf, "PNG")
    return buf.getvalue()


def test_image_upload_sanitizes_name():
    c = _client()
    slug = "sec-test-upload"
    try:
        c.post("/api/projects", json={"model": "corporativo-es", "title": "S", "slug": slug})
        # nombre con traversal -> basename seguro, sin ".."
        r = c.post(f"/api/projects/{slug}/image",
                   data={"file": (io.BytesIO(_png_bytes()), "../../x.png")},
                   content_type="multipart/form-data")
        assert r.status_code == 200
        src = r.get_json()["src"]
        assert src.startswith("img/") and ".." not in src
        # nombre '..' -> nombre de respaldo, no un 500
        r2 = c.post(f"/api/projects/{slug}/image",
                    data={"file": (io.BytesIO(_png_bytes()), "..")},
                    content_type="multipart/form-data")
        assert r2.status_code == 200
        assert r2.get_json()["src"].startswith("img/")
    finally:
        _cleanup(slug)


def test_image_upload_extension_from_content_not_name():
    """Un PNG llamado 'payload.html' se guarda como .png, no como .html."""
    c = _client()
    slug = "sec-test-ext"
    try:
        c.post("/api/projects", json={"model": "corporativo-es", "title": "S", "slug": slug})
        r = c.post(f"/api/projects/{slug}/image",
                   data={"file": (io.BytesIO(_png_bytes()), "payload.html")},
                   content_type="multipart/form-data")
        assert r.status_code == 200
        src = r.get_json()["src"]
        assert src.endswith(".png")
        assert not src.endswith(".html")
    finally:
        _cleanup(slug)


def test_image_upload_rejects_non_image():
    c = _client()
    slug = "sec-test-nonimg"
    try:
        c.post("/api/projects", json={"model": "corporativo-es", "title": "S", "slug": slug})
        r = c.post(f"/api/projects/{slug}/image",
                   data={"file": (io.BytesIO(b"\x89PNG solo cabecera, no es un png valido"), "x.png")},
                   content_type="multipart/form-data")
        assert r.status_code == 400
    finally:
        _cleanup(slug)


def test_image_upload_rejects_oversized():
    c = _client()
    slug = "sec-test-big"
    original = webapp.app.config.get("MAX_CONTENT_LENGTH")
    try:
        c.post("/api/projects", json={"model": "corporativo-es", "title": "S", "slug": slug})
        webapp.app.config["MAX_CONTENT_LENGTH"] = 64  # limite HTTP diminuto para la prueba
        r = c.post(f"/api/projects/{slug}/image",
                   data={"file": (io.BytesIO(_png_bytes(64, 64)), "big.png")},
                   content_type="multipart/form-data")
        assert r.status_code == 413
    finally:
        webapp.app.config["MAX_CONTENT_LENGTH"] = original
        _cleanup(slug)


def test_preview_bad_theme_does_not_500():
    c = _client()
    slug = "sec-test-preview"
    try:
        c.post("/api/projects", json={"model": "corporativo-es", "title": "S", "slug": slug})
        bad = {"meta": {"lang": "es", "report_title": "X", "theme": "../../etc/passwd"},
               "findings": []}
        r = c.post(f"/api/projects/{slug}/preview", json=bad)
        # se sanea a un tema valido y responde 200 (no derriba el worker)
        assert r.status_code == 200
    finally:
        _cleanup(slug)


def test_validate_endpoint_flags_bad_data():
    c = _client()
    data = {"meta": {"report_title": "X"}, "findings": [
        {"id": "F1", "mode": "machine"},               # machine sin host
        {"id": "F1", "severity": "muy_alta"},          # id duplicado + severidad invalida
    ], "report": {"sections": [{"key": "no_existe"}]}}
    r = c.post("/api/validate", json=data)
    assert r.status_code == 200
    msgs = " ".join(i["message"] for i in r.get_json()["issues"])
    assert "duplicad" in msgs.lower()
    assert "severidad" in msgs.lower()
    assert "sin bloque host" in msgs.lower()
    assert "seccion desconocida" in msgs.lower()


def _sc(): 
    import app as webapp
    webapp.app.config["TESTING"] = True
    return webapp.app.test_client()


def test_slug_length_capped_no_crash():
    """Slug enorme no debe crashear (OSError File name too long)."""
    import app as webapp
    r = _sc().post("/api/projects", json={"model": "corporativo-es", "title": "x", "slug": "a" * 300})
    assert r.status_code in (200, 409)
    assert len(webapp.slugify("a" * 300)) <= 80
    import shutil
    shutil.rmtree(webapp.PROJECTS / webapp.slugify("a" * 300), ignore_errors=True)


def test_slug_traversal_neutralized():
    import app as webapp
    for bad in ["../../evil", "a/../../b", "..\\..\\x"]:
        s = webapp.slugify(bad)
        assert "/" not in s and "\\" not in s and ".." not in s


def test_non_dict_bodies_do_not_500():
    c = _sc()
    assert c.post("/api/cvss", json=[1, 2]).status_code != 500
    assert c.post("/api/cvss", json={"version": "4.0", "vector": 123}).status_code == 400
    assert c.post("/api/validate", json=[1, 2, 3]).status_code != 500


def test_put_non_dict_body_rejected_and_preserves_project():
    import shutil, app as webapp
    c = _sc()
    c.post("/api/projects", json={"model": "corporativo-es", "title": "keep", "slug": "keepme"})
    assert c.put("/api/projects/keepme", json=[1, 2, 3]).status_code == 400
    assert c.put("/api/projects/keepme", json="x").status_code == 400
    assert c.get("/api/projects/keepme").status_code == 200  # no se borró
    shutil.rmtree(webapp.PROJECTS / "keepme", ignore_errors=True)
