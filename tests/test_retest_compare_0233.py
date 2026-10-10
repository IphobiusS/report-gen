"""Real snapshot comparisons, publication boundary and zero-write API contract."""
from copy import deepcopy
from hashlib import sha256

import pytest
import app as api
import project_history as history
import retest_compare as compare
import workflows
from storage import revision
from wizard import dump_yaml
from _support import auth_client


def document():
    return {'meta': {'report_title': 'Synthetic comparison', 'theme': 'serio', 'lang': 'es'},
            'report': {'sections': [{'key': 'findings', 'title': 'Hallazgos'}]},
            'findings': [{'uid': workflows.new_uid(), 'id': 'F1', 'mode': 'vuln',
                          'title': 'Synthetic finding', 'severity': 'high', 'status': 'open',
                          'description_md': 'Documented fictional behavior.', 'walkthrough': []}]}


def tree(directory):
    return {str(path.relative_to(directory)): sha256(path.read_bytes()).hexdigest()
            for path in directory.rglob('*') if path.is_file()}


@pytest.fixture
def project(tmp_path, monkeypatch):
    projects = tmp_path / 'projects'; projects.mkdir()
    monkeypatch.setattr(api, 'PROJECTS', projects)
    directory = projects / 'synthetic'; directory.mkdir()
    data = document(); dump_yaml(data, directory / 'engagement.yaml')
    return auth_client(api.app), directory, data


def snapshot(directory, data, label='Synthetic baseline', stage='delivered', created=None):
    dump_yaml(data, directory / 'engagement.yaml')
    record = history.checkpoint(directory, label, stage, force=True)
    if created:
        record['created'] = created
        (directory / 'history/snapshots' / (record['id'] + '.json')).write_bytes(history.dumps(record))
    return record


def url(directory, baseline, **extra):
    return '/api/projects/synthetic/retest-diff/visual?revision=' + revision(directory / 'engagement.yaml') + '&baseline=' + baseline['id'] + '&baseline_sha256=' + sha256((directory / 'history/snapshots' / (baseline['id'] + '.json')).read_bytes()).hexdigest() + ''.join('&'+key+'='+value for key, value in extra.items())


def test_no_history_is_honest_and_does_not_write(project):
    client, directory, _ = project; before = tree(directory)
    response = client.get('/api/projects/synthetic/retest-diff')
    assert response.status_code == 200
    assert response.json['state'] == 'no_delivered_baseline'
    assert response.json['baseline'] is None and response.json['candidates'] == []
    assert response.json['export_success_verified'] is False
    assert response.json['recipient_delivery_verified'] is False
    assert response.headers['ETag'].strip('"') == response.json['revision']
    assert response.headers['Cache-Control'] == 'no-store'
    assert tree(directory) == before


def test_latest_uses_real_instants_not_strings_or_latest_any_stage(project):
    client, directory, data = project
    older = snapshot(directory, data, created='2026-10-09T04:00:00+08:00')
    latest = snapshot(directory, data, created='2026-10-08T22:00:00+00:00')
    snapshot(directory, data, stage='draft', created='2026-10-09T23:00:00+00:00')
    before = tree(directory); response = client.get('/api/projects/synthetic/retest-diff')
    assert response.status_code == 200
    assert response.json['baseline']['id'] == latest['id'] != older['id']
    assert response.json['selection'] == 'latest_recorded_delivery'
    assert tree(directory) == before


@pytest.mark.parametrize('created,reason', [('2026-10-08T22:00:00+00:00', 'same_timestamp'), ('2026-10-08T22:00:00', 'timestamp_without_timezone')])
def test_ambiguous_latest_requires_explicit_selection(project, created, reason):
    client, directory, data = project
    selected = snapshot(directory, data, created='2026-10-08T22:00:00+00:00')
    snapshot(directory, data, created=created)
    response = client.get('/api/projects/synthetic/retest-diff')
    assert response.json['state'] == 'ambiguous_latest' and response.json['reason'] == reason
    response = client.get('/api/projects/synthetic/retest-diff?baseline=' + selected['id'])
    assert response.json['state'] == 'ready' and response.json['selection'] == 'explicit'
    assert response.json['baseline']['id'] == selected['id']


def test_explicit_draft_does_not_become_delivered(project):
    client, directory, data = project
    selected = snapshot(directory, data, stage='draft')
    response = client.get('/api/projects/synthetic/retest-diff?baseline=' + selected['id'])
    assert response.json['selection'] == 'explicit'
    assert response.json['baseline']['stage'] == 'draft'
    assert history.get_snapshot(directory, selected['id'])['stage'] == 'draft'


def test_uid_changes_and_removed_is_not_fixed(project):
    client, directory, data = project
    data['findings'].append({**deepcopy(data['findings'][0]), 'uid': workflows.new_uid(), 'id': 'F2', 'title': 'Removed finding'})
    data['findings'].append({**deepcopy(data['findings'][0]), 'uid': workflows.new_uid(), 'id': 'F3', 'title': 'Unchanged finding'})
    baseline = snapshot(directory, data)
    changed = deepcopy(data); changed['findings'].pop(1); changed['findings'][0]['status'] = 'reported_fixed'
    changed['findings'].append({**deepcopy(data['findings'][0]), 'uid': workflows.new_uid(), 'id': 'F4', 'title': 'Added finding'})
    changed['findings'].reverse(); dump_yaml(changed, directory / 'engagement.yaml')
    before = tree(directory); response = client.get('/api/projects/synthetic/retest-diff')
    assert response.status_code == 200 and response.json['baseline']['id'] == baseline['id']
    assert response.json['summary'] == {'added': 1, 'removed': 1, 'modified': 1, 'unchanged': 1}
    removed = next(row for row in response.json['findings'] if row['change'] == 'removed')
    assert removed['after_status'] is None and 'fixed' not in removed.values()
    assert all(set(row) == {'path', 'finding_uid'} for row in response.json['changes'])
    assert tree(directory) == before


def test_reordering_keeps_permanent_identity_and_is_not_removal():
    data = document(); data['findings'].append({**deepcopy(data['findings'][0]), 'uid': workflows.new_uid(), 'id': 'F2'})
    other = deepcopy(data); other['findings'].reverse()
    assert compare.comparison(data, other)['summary'] == {'added': 0, 'removed': 0, 'modified': 0, 'unchanged': 2}


def test_legacy_is_not_migrated_or_falsely_uid_matched(project):
    client, directory, data = project
    legacy = deepcopy(data); legacy['findings'][0].pop('uid')
    baseline = snapshot(directory, legacy)
    dump_yaml(data, directory / 'engagement.yaml'); before = tree(directory)
    response = client.get('/api/projects/synthetic/retest-diff?baseline=' + baseline['id'])
    assert response.json['summary'] == {'added': 1, 'removed': 1, 'modified': 0, 'unchanged': 0}
    assert response.json['legacy_identity'] is True
    assert tree(directory) == before and 'uid' not in history.snapshot_data(directory, baseline['id'])['findings'][0]


@pytest.mark.parametrize('operation', ['object', 'metadata', 'missing_object'])
def test_corrupt_baseline_is_rejected_without_fallback_or_write(project, operation):
    client, directory, data = project; baseline = snapshot(directory, data)
    metadata = directory / 'history/snapshots' / (baseline['id'] + '.json')
    key = baseline['files']['engagement.yaml']; obj = directory / 'history/objects' / key
    if operation == 'object': obj.write_bytes(b'altered')
    elif operation == 'missing_object': obj.unlink()
    else: metadata.write_text('{invalid')
    before = tree(directory); response = client.get('/api/projects/synthetic/retest-diff')
    assert response.status_code == 422 and tree(directory) == before


def test_revision_and_baseline_hash_bind_visual_to_reviewed_source(project):
    client, directory, data = project; baseline = snapshot(directory, data)
    target = url(directory, baseline)
    assert client.get('/api/projects/synthetic/retest-diff?revision=stale').status_code == 409
    assert client.get('/api/projects/synthetic/retest-diff/visual').status_code == 428
    assert client.get(target.replace(revision(directory / 'engagement.yaml'), 'stale')).status_code == 409
    wrong = target.rsplit('=', 1)[0] + '=' + '0' * 64
    assert client.get(wrong).status_code == 409
    record = history.get_snapshot(directory, baseline['id']); record['label'] = 'Changed label'
    (directory / 'history/snapshots' / (baseline['id'] + '.json')).write_bytes(history.dumps(record))
    assert client.get(target).status_code == 409


def test_shareable_projection_redacts_current_and_history_and_private_requires_ack(project):
    client, directory, data = project
    secret = 'SYNTHETIC-SECRET-7932'; private = 'PRIVATE-DRAFT-9384'
    data['findings'][0]['description_md'] += ' ' + secret
    data['findings'][0]['private_draft'] = private
    baseline = snapshot(directory, data, label=secret + ' private label')
    data['publication'] = {'redactions': [{'needle': secret, 'replacement': '[REDACTED]'}], 'exceptions': []}
    dump_yaml(data, directory / 'engagement.yaml'); target = url(directory, baseline); before = tree(directory)
    response = client.get(target + '&download=1')
    text = response.data.decode()
    assert response.status_code == 200 and 'attachment;' in response.headers['Content-Disposition']
    assert secret not in text and private not in text
    assert 'Compartible' in text and 'Retirado significa' in text
    assert response.headers['ETag'].strip('"') == revision(directory / 'engagement.yaml')
    assert client.get(target + '&privacy=private').status_code == 422
    assert client.get(target + '&privacy=private&download=1').status_code == 422
    response = client.get(target + '&privacy=private&ack_private=1&download=1')
    assert response.status_code == 200 and secret in response.data.decode()
    assert 'comparison-private.html' in response.headers['Content-Disposition']
    assert tree(directory) == before


@pytest.mark.parametrize('query', ['profile=public', 'privacy=unknown', 'revision=x&revision=y', 'lang=xx', 'download=yes', 'ack_private=yes'])
def test_unknown_or_ambiguous_options_are_rejected(project, query):
    client, directory, data = project; baseline = snapshot(directory, data)
    assert client.get(url(directory, baseline) + '&' + query).status_code == 422


def test_cross_site_reads_do_not_expose_private_project(project):
    client, _, _ = project
    assert client.get('/api/projects/synthetic/retest-diff', headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
    assert client.get('/api/projects/synthetic/retest-diff', headers={'Origin': 'https://other.invalid'}).status_code == 403


@pytest.mark.parametrize('disjoint', [False, True])
def test_two_valid_200_decision_snapshots_are_comparable_without_union_schema(disjoint):
    import report_compare
    old = document(); new = deepcopy(old)
    first = [{'needle': f'OLD_SECRET_{i:03}', 'replacement': f'old-redacted-{i:03}'} for i in range(200)]
    second = [{'needle': f'NEW_SECRET_{i:03}', 'replacement': f'new-redacted-{i:03}'} for i in range(200)] if disjoint else deepcopy(first)
    text = ' '.join(row['needle'] for row in first + second)
    old['findings'][0]['description_md'] = text
    new['findings'][0]['description_md'] = text + ' changed'
    old['publication'] = {'redactions': first}
    new['publication'] = {'redactions': second}
    original = deepcopy((old, new))
    markup = report_compare.render(old, new, {}, {}, 'old', 'new')
    assert all(row['needle'] not in markup for row in second)
    assert all(row['replacement'] in markup for row in first)
    assert (old, new) == original


def test_comparison_keeps_non_idempotent_redaction_order_and_structural_ids():
    import report_compare
    old = document(); new = deepcopy(old)
    old['findings'][0]['description_md'] = 'AAAA'
    new['findings'][0]['description_md'] = 'AAAA changed'
    old['publication'] = {'redactions': [{'needle': 'AAAA', 'replacement': 'AAAAX'}]}
    new['publication'] = {'redactions': [{'needle': 'AAAA', 'replacement': 'AAAAX'}]}
    markup = report_compare.render(old, new, {}, {}, 'old', 'new')
    assert 'AAAAXX' in markup  # the baseline and current literal decisions both apply
    assert old['findings'][0]['uid'] in markup


def test_historical_redaction_intermediate_expansion_keeps_16_mib_guard():
    import report_compare
    old = document(); new = deepcopy(old)
    old['findings'][0]['description_md'] = 'AAAA' * 5000
    old['publication'] = {'redactions': [{'needle': 'AAAA', 'replacement': 'BBBB' * 1000}]}
    new['publication'] = {'redactions': [{'needle': 'BBBB', 'replacement': 'x'}]}
    with pytest.raises(ValueError, match='16 MiB'):
        report_compare.render(old, new, {}, {}, 'old', 'new')
