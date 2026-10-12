"""Exportacion a PDF: delega en engine.py (render a dos pasadas)."""
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from error_messages import current_language, message as backend_message
from storage import require_export_destination

REPO_ROOT = Path(__file__).resolve().parent.parent


def export_pdf(yaml_path, out_path):
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
                           cwd=str(REPO_ROOT), check=True, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired as exc:
            raise ValueError(backend_message(
                'El PDF superó el límite de 120 segundos. Reduce el contenido por exportación o vuelve a intentarlo con menos carga. La salida anterior se conserva.',
                en='PDF generation exceeded the 120-second limit. Reduce the content per export or retry with less load. The previous output is preserved.')) from exc
        except subprocess.CalledProcessError as exc:
            raise ValueError((exc.stderr or exc.stdout or backend_message("No se pudo generar el PDF")).strip()) from exc
        rendered.replace(out)
    return requested
