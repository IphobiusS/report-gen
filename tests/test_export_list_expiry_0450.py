"""A listing must not purge again while iterating its owned job snapshot."""
import pytest

import export_jobs


@pytest.mark.parametrize('expiring_owner', ['owner', 'other-session'])
def test_ttl_crossing_during_listing_cannot_mutate_the_iteration(monkeypatch, expiring_owner):
    queue = export_jobs.ExportQueue(ttl=1)
    try:
        with queue.lock:
            for key, owner, updated in [('retained', 'owner', 10000), ('expiring', expiring_owner, 0)]:
                root = queue.root / key
                root.mkdir()
                (root / 'result').write_bytes(b'Synthetic completed result')
                queue.jobs[key] = dict(id=key, owner=owner, root=root, stage='done', updated=updated,
                                       label=key, revision='saved', error=None, filename='result.pdf',
                                       verification=None)
            calls = []

            def clock():
                calls.append(None)
                # Both jobs survive the initial purge; another purge would
                # expire the second during the listing's dictionary iteration.
                return 0 if len(calls) <= 2 else 2

            monkeypatch.setattr(export_jobs.time, 'time', clock)
            rows = queue.list('owner')
            assert [row['id'] for row in rows] == (['retained', 'expiring'] if expiring_owner == 'owner' else ['retained'])
            assert len(calls) == 2
            assert all(row['stage'] == 'done' and row['position'] == 0 for row in rows)
            # The next request still expires old records; the fix is not a TTL bypass.
            assert [row['id'] for row in queue.list('owner')] == ['retained']
            assert 'expiring' not in queue.jobs
            assert not (queue.root / 'expiring').exists()
    finally:
        queue.close()
