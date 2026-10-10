"""Shareable diagnostics contain only fixed fields, never arbitrary probe output."""
import hashlib
import hmac
import json
import platform
import sys

from version import __version__


def project(diagnostics):
    checks = diagnostics.get('checks', [])
    states = {}
    for key in ('weasyprint', 'chromium', 'docx', 'storage'):
        matches = [row for row in checks if isinstance(row, dict) and row.get('id') == key]
        ready = matches[0].get('ready') if len(matches) == 1 else None
        states[key] = 'passed' if ready is True else 'failed' if ready is False else 'not_checked'
    system = platform.system()
    return {'schema': 1, 'application': 'report-gen', 'version': __version__,
            'system': system if system in ('Linux', 'Windows', 'Darwin') else 'Other',
            'python': '.'.join(str(part) for part in sys.version_info[:3]),
            'synthetic_exports': {key: states[key] for key in ('weasyprint', 'chromium', 'docx')},
            'workspace_write': states['storage']}


def encode(report):
    return (json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + '\n').encode('utf-8')


def token(report, secret):
    if isinstance(secret, str):
        secret = secret.encode('utf-8')
    return hmac.new(secret, b'support-report-v1\x00' + encode(report), hashlib.sha256).hexdigest()


def verified(report, supplied, secret):
    if not isinstance(report, dict) or not isinstance(supplied, str) or len(supplied) != 64:
        return False
    try:
        blob = encode(report)
        return len(blob) < 4096 and hmac.compare_digest(token(report, secret), supplied)
    except (ValueError, TypeError, UnicodeError):
        return False
