"""Local report resources: no network, traversal, or symlink escapes."""
from error_messages import message as backend_message
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
import re

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def relative_image(src):
    if not isinstance(src, str) or not src:
        raise ValueError(backend_message('Ruta de imagen vacía'))
    parsed = urlsplit(src)
    raw = unquote(parsed.path)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or "\\" in raw or re.match(r"^[a-zA-Z]:", raw):
        raise ValueError(backend_message('Usa una imagen local del engagement'))
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts or "originals" in path.parts or "history" in path.parts or path.suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError(backend_message('Ruta o formato de imagen no permitido'))
    return path


def local_image(src, root):
    path = (Path(root).resolve() / relative_image(src)).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError(backend_message('La imagen está fuera del engagement'))
    if any(path.is_relative_to(Path(root).resolve() / name) for name in ("originals", "history")):
        raise ValueError(backend_message('Los originales y el historial no son recursos de entrega'))
    if not path.is_file():
        raise ValueError(backend_message('Imagen no encontrada: {p0}', p0=src))
    return path


def project_image_member(name):
    """An archive name is a physical path, not a URL to decode a second time."""
    from workflows import safe_member
    if not safe_member(name):
        return False
    try:
        return relative_image(quote(name, safe='/')).as_posix() == name
    except ValueError:
        return False


def markdown_fields():
    from sections import catalog_by_key
    return {'body'} | {field['key'] for section in catalog_by_key().values()
                      for field in section.get('fields', []) if field['type'] == 'markdown'}


def image_references(data):
    """Raw image destinations with their source field, before sanitization.

    Only Markdown fields are parsed. Command strings, titles, plain metadata
    and private originals are not Markdown image references.
    """
    from workflows import strings
    from input_guard import ensure_data_tree
    from safe_markup import raw_image_sources
    ensure_data_tree(data)
    fields = markdown_fields()
    for field, text in strings(data):
        if field.endswith(('.src', '.logo', '.client_logo', '.cover_image')) and text:
            yield field, text
        key = field.rsplit('.', 1)[-1]
        if '![' in text and (key.endswith('_md') or key in fields):
            for source in sorted(raw_image_sources(text)):
                yield field, source


def referenced_images(data):
    return {source for _, source in image_references(data)}


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
            raise ValueError(backend_message('El renderizador solo admite recursos locales'))
        from urllib.request import url2pathname
        path = Path(url2pathname(parsed.path)).resolve()
        if not any(path.is_relative_to(r) for r in roots):
            raise ValueError(backend_message('Recurso fuera de los directorios permitidos'))
        if path.suffix.lower() not in IMAGE_SUFFIXES | {".css", ".ttf", ".otf", ".woff", ".woff2"}:
            raise ValueError(backend_message('Tipo de recurso no permitido'))
        return fetch_resource(url, **kwargs)
    fetch._fail_on_errors = True
    return fetch
