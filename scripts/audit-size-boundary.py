#!/usr/bin/env python3
"""Real 12 MiB boundary, including YAML alias expansion and failed-save recovery."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine  # noqa: E402
import project_history  # noqa: E402

with tempfile.TemporaryDirectory(prefix='report-gen-boundary-') as temporary:
    directory = Path(temporary); path = directory/'engagement.yaml'
    source = 'meta: {}\nfindings: []\nextra: [&block "'+'A'*4_200_000+'", *block, *block]\n'
    path.write_text(source); data = engine.load_engagement(path); before = path.read_bytes()
    try:
        project_history.save(directory, data); outcome = 'saved'
    except ValueError as error:
        outcome = str(error)
    try:
        engine.load_engagement(path); readable = True
    except ValueError:
        readable = False
    result = {'input_bytes': len(before), 'saved_bytes': path.stat().st_size, 'outcome': outcome,
              'original_unchanged': path.read_bytes() == before, 'readable_after_rejection': readable,
              'no_staging_left': not list(directory.parent.glob('.transaction-*'))}
    result['passed'] = outcome != 'saved' and result['original_unchanged'] and readable
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
sys.exit(0 if result['passed'] else 1)
