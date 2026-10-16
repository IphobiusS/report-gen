"""Local diagnostic coordinates, without copied report or scanner content.

Coordinates describe only what a validator actually knows. They are additive
API metadata, not report provenance or permission to publish private inputs.
All numeric coordinates are one-based except explicit ``*_index`` fields.
"""
from contextlib import contextmanager
import re


_POSITIVE = frozenset(('record', 'line', 'line_end', 'column', 'table', 'row', 'cell'))
_INDEXES = frozenset(('run_index', 'result_index', 'evidence_index'))
_TOKENS = frozenset(('field', 'finding_id', 'finding_uid', 'section'))


def coordinates(**values):
    """Keep bounded structural coordinates; never accept values, URLs or paths."""
    result = {}
    for key, value in values.items():
        if key in _POSITIVE and type(value) is int and 1 <= value <= 10_000_000:
            result[key] = value
        elif key in _INDEXES and type(value) is int and 0 <= value < 10_000_000:
            result[key] = value
        elif key == 'operation' and value in ('import', 'export'):
            result[key] = value
        elif key == 'format' and value in ('csv', 'burp', 'nuclei', 'nmap', 'sarif', 'pdf', 'docx', 'html', 'md'):
            result[key] = value
        elif key in _TOKENS and isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.\[\] ()/+-]{0,159}', value):
            result[key] = value
    return result


def diagnostic(code, message, **location):
    return {'code': code, 'message': str(message), 'location': coordinates(**location)}


def sanitize_diagnostics(values):
    """Bound private API/worker details and discard unknown structural fields."""
    if not isinstance(values, list):
        return []
    result = []
    for item in values[:64]:
        if not isinstance(item, dict):
            continue
        code, message, location = item.get('code'), item.get('message'), item.get('location')
        if (not isinstance(code, str) or not re.fullmatch(r'[a-z][a-z0-9_.]{0,79}', code)
                or not isinstance(message, str) or not isinstance(location, dict)):
            continue
        result.append(diagnostic(code, message[:1200], **{key: value for key, value in location.items()
                                                        if isinstance(key, str)}))
    return result


def error_diagnostics(error):
    """Return only explicit diagnostics; never guess coordinates from prose."""
    return sanitize_diagnostics(getattr(error, 'diagnostics', None))


class DiagnosticError(ValueError):
    """Preserve the historical error text and add machine-readable locations."""

    def __init__(self, message, *, code='input.invalid', location=None, diagnostics=None):
        super().__init__(message)
        self.diagnostics = sanitize_diagnostics([diagnostic(code, message, **(location or {}))]
                                               if diagnostics is None else diagnostics)


@contextmanager
def location_scope(*, code='input.invalid', **location):
    """Attach an enclosing record/scope while retaining more specific details."""
    try:
        yield
    except ValueError as exc:
        outer = coordinates(**location)
        if isinstance(exc, DiagnosticError):
            details = [{**item, 'location': {**outer, **item['location']}} for item in exc.diagnostics]
        else:
            details = [diagnostic(code, str(exc), **outer)]
        raise DiagnosticError(str(exc), diagnostics=details) from exc
