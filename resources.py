"""Local report resources: no network, traversal, or symlink escapes."""
from pathlib import Path
from urllib.parse import unquote, urlsplit
import re

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def relative_image(src):
    if not isinstance(src, str) or not src:
        raise ValueError("Ruta de imagen vacía")
    parsed = urlsplit(src)
    raw = unquote(parsed.path)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or "\\" in raw or re.match(r"^[a-zA-Z]:", raw):
        raise ValueError("Usa una imagen local del engagement")
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts or "originals" in path.parts or "history" in path.parts or path.suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError("Ruta o formato de imagen no permitido")
    return path


def local_image(src, root):
    path = (Path(root).resolve() / relative_image(src)).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError("La imagen está fuera del engagement")
    if any(path.is_relative_to(Path(root).resolve() / name) for name in ("originals", "history")):
        raise ValueError("Los originales y el historial no son recursos de entrega")
    if not path.is_file():
        raise ValueError(f"Imagen no encontrada: {src}")
    return path


def restricted_fetcher(root, themes):
    try:
        from weasyprint.urls import URLFetcher
        fetch_resource = URLFetcher(allowed_protocols={"file"}, fail_on_errors=True)
    except ImportError:
        from weasyprint import default_url_fetcher
        fetch_resource = default_url_fetcher
    roots = [Path(root).resolve(), Path(themes).resolve()]
    def fetch(url, **kwargs):
        parsed = urlsplit(url)
        if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
            raise ValueError("El renderizador solo admite recursos locales")
        from urllib.request import url2pathname
        path = Path(url2pathname(unquote(parsed.path))).resolve()
        if not any(path.is_relative_to(r) for r in roots):
            raise ValueError("Recurso fuera de los directorios permitidos")
        if path.suffix.lower() not in IMAGE_SUFFIXES | {".css", ".ttf", ".otf", ".woff", ".woff2"}:
            raise ValueError("Tipo de recurso no permitido")
        return fetch_resource(url, **kwargs)
    fetch._fail_on_errors = True
    return fetch
