"""Exportacion a PDF: delega en engine.py (render a dos pasadas)."""
import subprocess
import sys
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from error_messages import current_language, message as backend_message
from storage import require_export_destination

REPO_ROOT = Path(__file__).resolve().parent.parent


def rendering_timeout():
    """Bound a whole two-pass PDF render, including its integrity checks."""
    raw = os.environ.get('REPORT_GEN_PDF_TIMEOUT')
    if raw is None:
        return 300
    if raw.isascii() and raw.isdecimal() and len(raw) <= 3:
        value = int(raw)
        if 30 <= value <= 600:
            return value
    raise ValueError(backend_message(
        'REPORT_GEN_PDF_TIMEOUT debe ser un entero entre 30 y 600 segundos.',
        en='REPORT_GEN_PDF_TIMEOUT must be an integer between 30 and 600 seconds.'))


def export_pdf(yaml_path, out_path):
    timeout = rendering_timeout()
    yaml_path = Path(yaml_path).resolve()
    requested = Path(out_path)
    # Validate the caller's real destination before replacing it with a staged
    # child destination. This writer is also exposed independently of export().
    from engine import load_engagement
    out = require_export_destination(yaml_path, requested, load_engagement(yaml_path))
    out.parent.mkdir(parents=True, exist_ok=True)
    # The engine writes intermediate pagination passes beside its destination.
    # A timed-out child cannot run its finally blocks, so own those files here.
    with TemporaryDirectory(prefix='.report-gen-pdf-', dir=out.parent) as temporary:
        rendered = Path(temporary) / 'report.pdf'
        try:
            subprocess.run([sys.executable, str(REPO_ROOT / "engine.py"), str(yaml_path), "-o", str(rendered),
                            '--error-language', current_language()],
                           cwd=str(REPO_ROOT), check=True, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise ValueError(backend_message(
                'El PDF superó el límite de {seconds} segundos. Reduce el contenido por exportación o vuelve a intentarlo con menos carga. La salida anterior se conserva.',
                en='PDF generation exceeded the {seconds}-second limit. Reduce the content per export or retry with less load. The previous output is preserved.',
                seconds=timeout)) from exc
        except subprocess.CalledProcessError as exc:
            raise ValueError((exc.stderr or exc.stdout or backend_message("No se pudo generar el PDF")).strip()) from exc
        rendered.replace(out)
    return requested
