"""Recheck the recovered fictional R16 projects without changing their sources."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import delivery
import export
import export_formats


def audit(output):
    output.mkdir(parents=True, exist_ok=False)
    source = ROOT / 'qa/r16-recovery/projects'
    before = {str(p.relative_to(source)): sha256(p.read_bytes()).hexdigest()
              for p in source.rglob('*') if p.is_file()}
    results = []
    for language in ('es', 'en', 'pt'):
        project = source / language
        destination = output / language
        destination.mkdir()
        captured = delivery.capture(project, destination / 'snapshot')
        for fmt, spec in export_formats.REGISTRY.items():
            started = time.perf_counter()
            item = {'language': language, 'format': fmt}
            try:
                path = export.export(project / 'engagement.yaml', fmt, destination / spec.filename)
                item.update(bytes=path.stat().st_size, sha256=sha256(path.read_bytes()).hexdigest())
                item['checks'] = delivery.inspect_export(path, fmt, captured)
                item['status'] = 'passed'
            except Exception as exc:
                item.update(status='failed', error=f'{type(exc).__name__}: {exc}')
            item['seconds'] = round(time.perf_counter() - started, 3)
            results.append(item)
            print(json.dumps(item, ensure_ascii=False), flush=True)
            (output / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
    after = {str(p.relative_to(source)): sha256(p.read_bytes()).hexdigest()
             for p in source.rglob('*') if p.is_file()}
    assert before == after, 'The original project bytes changed during export'
    (output / 'source-sha256.json').write_text(json.dumps(before, indent=2) + '\n')
    return 0 if all(r['status'] == 'passed' for r in results) else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    sys.exit(audit(parser.parse_args().output))
