"""Skip compatible con pytest y con el runner de stdlib."""


class Skipped(Exception):
    """Senal de test omitido para el runner de stdlib."""


def skip(reason):
    try:
        import pytest
        pytest.skip(reason)
    except ImportError:
        raise Skipped(reason)
