"""Skip compatible con pytest y con el runner de stdlib."""


class Skipped(Exception):
    """Senal de test omitido para el runner de stdlib."""


def skip(reason):
    try:
        import pytest
        pytest.skip(reason)
    except ImportError:
        raise Skipped(reason)


def auth_client(app):
    client = app.test_client()
    token = client.get("/api/session").get_json()["csrf"]
    client.environ_base["HTTP_X_CSRF_TOKEN"] = token
    original_open = client.open
    def open_with_revision(*args, **kwargs):
        path = args[0] if args and isinstance(args[0], str) else kwargs.get("path", "")
        method = kwargs.get("method", "GET").upper()
        if method in {"PUT", "DELETE"} and path.startswith("/api/projects/"):
            response = original_open(path, method="GET")
            headers = dict(kwargs.pop("headers", {}))
            if response.headers.get("ETag"): headers.setdefault("If-Match", response.headers["ETag"])
            kwargs["headers"] = headers
        return original_open(*args, **kwargs)
    client.open = open_with_revision
    return client
