"""Read-only comparison against a recorded or explicitly chosen project version.

A delivered snapshot is an author's local stage declaration. It is not proof
that an export finished, or that a recipient received a report. Export queue
jobs expire and audience packages do not persist a project-linked baseline.
"""
from error_messages import message as backend_message
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import project_history as history
import workflows
from input_guard import load_yaml
from storage import revision
from validate import require_valid


def _instant(value):
    try:
        date = datetime.fromisoformat(value)
        return date.astimezone(timezone.utc) if date.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def candidates(directory):
    """Validate metadata and retain real timestamps; never normalize source data."""
    result = []
    for record in history.history(directory):
        path = Path(directory) / 'history' / 'snapshots' / (record['id'] + '.json')
        result.append(dict(id=record['id'], label=record['label'], stage=record['stage'],
                           created=record['created'], snapshot_sha256=sha256(path.read_bytes()).hexdigest(),
                           date_comparable=_instant(record['created']) is not None))
    # Labels and dates are documentary metadata, not inferred recipient events.
    return result


def select_baseline(versions, baseline=None):
    if baseline is not None:
        if not isinstance(baseline, str) or not workflows.UID.fullmatch(baseline):
            raise ValueError(backend_message('Versión base inválida / Invalid baseline version'))
        selected = next((row for row in versions if row['id'] == baseline), None)
        if selected is None:
            raise ValueError(backend_message('La versión base no existe / Baseline version does not exist'))
        return deepcopy(selected), 'explicit', None
    delivered = [row for row in versions if row['stage'] == 'delivered']
    if not delivered:
        return None, 'no_delivered_baseline', 'no_recorded_delivery'
    if any(not row['date_comparable'] for row in delivered):
        return None, 'ambiguous_latest', 'timestamp_without_timezone'
    latest = max(_instant(row['created']) for row in delivered)
    tied = [row for row in delivered if _instant(row['created']) == latest]
    if len(tied) != 1:
        return None, 'ambiguous_latest', 'same_timestamp'
    return deepcopy(tied[0]), 'latest_recorded_delivery', None


def comparison(before, after):
    """Preserve identity and expose field names only in the local summary."""
    require_valid(before)
    require_valid(after)
    def pool(data):
        rows = {}
        for finding in data.get('findings', []):
            identity = finding.get('uid') or finding.get('id')
            if not isinstance(identity, str) or not identity or identity in rows:
                raise ValueError(backend_message('Identidad de hallazgo ambigua / Ambiguous finding identity'))
            rows[identity] = finding
        return rows
    old, new = pool(before), pool(after)
    if any(bool(old[key].get('uid')) != bool(new[key].get('uid')) for key in old.keys() & new.keys()):
        raise ValueError(backend_message('Identidad antigua ambigua / Ambiguous legacy identity'))
    rows = []
    for identity in sorted(old.keys() | new.keys()):
        a, b = old.get(identity), new.get(identity)
        change = 'added' if a is None else 'removed' if b is None else 'unchanged' if a == b else 'modified'
        row = b or a
        rows.append(dict(identity=identity, identity_kind='uid' if row.get('uid') else 'legacy_id',
                         id=row.get('id', ''), title=row.get('title', ''), change=change,
                         before_status=a.get('status', 'open') if a else None,
                         after_status=b.get('status', 'open') if b else None))
    changes = [dict(path=entry['path'], finding_uid=entry['finding_uid'])
               for entry in workflows.compare(before, after)]
    return dict(summary={key: sum(row['change'] == key for row in rows)
                         for key in ('added', 'removed', 'modified', 'unchanged')},
                findings=rows, changes=changes,
                legacy_identity=any(row['identity_kind'] == 'legacy_id' for row in rows))


def read(directory, data, baseline=None):
    versions = candidates(directory)
    chosen, selection, reason = select_baseline(versions, baseline)
    result = dict(revision=revision(Path(directory) / 'engagement.yaml'),
                  candidates=versions, baseline=chosen, selection=selection,
                  state='ready' if chosen else selection, reason=reason,
                  provenance='local_snapshot_stage', export_success_verified=False,
                  recipient_delivery_verified=False)
    if chosen:
        # Verify every archived object before claiming this comparison exists.
        blobs = dict(history.snapshot_blobs(directory, history.get_snapshot(directory, chosen['id'])))
        before = load_yaml(blobs['engagement.yaml'])
        result.update(comparison(before, data))
    return result
