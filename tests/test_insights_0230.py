"""Optional reasoning must be explicit, bounded and revision-aware."""
from copy import deepcopy
from hashlib import sha256

import pytest
from PIL import Image

import app as api
import insights
import project_history
from storage import revision
import validate
import workflows
from wizard import dump_yaml
from _support import auth_client


def document():
    return workflows.normalize({
        'meta': {'report_title': 'Caso sintético', 'lang': 'es', 'theme': 'serio'},
        'findings': [{'id': 'F1', 'title': 'Lectura fuera de la cuenta', 'mode': 'vuln',
                      'severity': 'info', 'cvss': 0,
                      'description_md': 'Observación delimitada',
                      'impact_md': 'Impacto documentado', 'remediation_md': 'Propuesta'}],
        'assets': [{'name': 'Portal', 'target': 'portal.example', 'kind': 'web'}],
        'evidence': [{'title': 'Respuesta sintética', 'src': 'img/proof.png'}],
    })


def store(directory, data):
    (directory / 'img').mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (20, 15), 'green').save(directory / 'img/proof.png')
    dump_yaml(data, directory / 'engagement.yaml')


@pytest.fixture
def client(tmp_path, monkeypatch):
    directory = tmp_path / 'projects' / 'case'
    data = document()
    store(directory, data)
    monkeypatch.setattr(api, 'PROJECTS', directory.parent)
    return auth_client(api.app), directory, data


def post(client, body, tag=None):
    c, directory, _ = client
    return c.post('/api/projects/case/insights', json=body,
                  headers={'If-Match': tag or '"' + revision(directory / 'engagement.yaml') + '"'})


def claim_body(data, **extra):
    return dict(action='set_claim', finding_uid=data['findings'][0]['uid'],
                statement='Una cuenta leyó el documento de otra cuenta', kind='observed',
                demonstrates='Lectura de este documento', does_not_demonstrate='Lectura de todos los documentos',
                evidence_uids=[data['evidence'][0]['uid']], **extra)


def test_read_only_view_and_editorial_do_not_add_optional_fields(client):
    c, directory, data = client
    before = (directory / 'engagement.yaml').read_bytes()
    pristine = deepcopy(data)
    value = insights.view(data, directory)
    assert value['claims'] == value['risks'] == value['comments'] == value['reviews'] == []
    assert value['review_status']['state'] == 'not_reviewed'
    assert data == pristine and 'insights' not in data
    for route in ('insights', 'insights/editorial'):
        response = c.get('/api/projects/case/' + route)
        assert response.status_code == 200
        assert response.headers['ETag'] == '"' + sha256(before).hexdigest() + '"'
    assert (directory / 'engagement.yaml').read_bytes() == before
    assert not (directory / 'history').exists()


def test_actual_uid_map_with_retest_and_claim_links(client):
    _, directory, data = client
    finding = data['findings'][0]
    finding['asset_uids'] = [data['assets'][0]['uid']]
    finding['evidence_uids'] = [data['evidence'][0]['uid']]
    finding['retests'] = [dict(uid=workflows.new_uid(), result='fixed', tested_on='2026-10-08',
                                evidence_uids=[data['evidence'][0]['uid']])]
    updated = insights.mutate(data, claim_body(data), 'a' * 64, directory)
    relationships = insights.relationship_map(updated)
    assert {row['kind'] for row in relationships['links']} == {'asset', 'evidence', 'retest', 'claim'}
    assert all(not row['missing'] for row in relationships['links'])
    assert relationships['findings'][0]['retests'][0]['uid'] == finding['retests'][0]['uid']
    assert 'insights' not in data


def test_optional_risk_keeps_unagreed_tolerance_and_no_invented_numbers(client):
    _, directory, data = client
    result = insights.mutate(data, dict(action='set_risk', finding_uid=data['findings'][0]['uid'],
                                        service='Pagos', objective='Procesar pagos autorizados'),
                             'a' * 64, directory)
    risk = result['insights']['risks'][0]
    assert risk['priority'] == 'unassigned'
    assert 'tolerance' not in risk and 'source' not in risk and 'owner' not in risk
    assert not any(key in risk for key in ('loss', 'risk_score', 'cvss', 'likelihood', 'appetite'))
    assert result['findings'][0]['cvss'] == data['findings'][0]['cvss']


def test_risk_priority_is_authored_and_editorial_advisory(client):
    _, directory, data = client
    result = insights.mutate(data, dict(action='set_risk', finding_uid=data['findings'][0]['uid'],
                                        service='Pagos', priority='P1'), 'a' * 64, directory)
    issue = insights.editorial(result)[0]
    assert issue['rule'] == 'priority_without_basis'
    assert issue['technical_verification'] is False and issue['level'] == 'warning'
    assert result['insights']['risks'][0]['priority'] == 'P1'


def test_review_is_bound_to_content_not_its_own_bookkeeping(client):
    _, directory, data = client
    approved = insights.mutate(data, dict(action='review', decision='approved', author='Nombre declarado', notes='Revisión editorial'),
                               'a' * 64, directory)
    value = insights.view(approved, directory)
    assert value['review_status']['state'] == 'approved'
    assert value['review_status']['local_self_declared'] is True
    assert approved['findings'] == data['findings']
    modified = deepcopy(approved)
    modified['findings'][0]['description_md'] += ' Nueva observación'
    assert insights.view(modified, directory)['review_status']['state'] == 'stale'
    assert modified['insights']['reviews'][0]['content_digest'] == value['digest']


def test_review_hash_detects_referenced_image_bytes(client):
    _, directory, data = client
    approved = insights.mutate(data, dict(action='review', decision='approved', author='Evaluador'), 'a' * 64, directory)
    assert insights.view(approved, directory)['review_status']['state'] == 'approved'
    Image.new('RGB', (20, 15), 'red').save(directory / 'img/proof.png')
    assert insights.view(approved, directory)['review_status']['state'] == 'stale'
    assert insights.view(approved, directory)['resources_complete'] is True


def test_first_legacy_review_refers_to_actual_normalized_saved_content(client):
    c, directory, data = client
    for key in ('schema_version', 'finding_sequence', 'coverage', 'report'):
        data.pop(key, None)
    dump_yaml(data, directory / 'engagement.yaml')
    response = post(client, dict(action='review', decision='approved', author='Revisión local'))
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['insights']['review_status']['state'] == 'approved'
    assert c.get('/api/projects/case/insights').get_json()['review_status']['state'] == 'approved'


def test_missing_or_unsafe_resources_prevent_new_approval(client):
    _, directory, data = client
    (directory / 'img/proof.png').unlink()
    assert insights.view(data, directory)['resources_complete'] is False
    with pytest.raises(ValueError, match='Missing resources'):
        insights.mutate(data, dict(action='review', decision='approved', author='Revisor'), 'a' * 64, directory)
    pending = insights.mutate(data, dict(action='review', decision='changes_requested', author='Revisor'), 'a' * 64, directory)
    assert pending['insights']['reviews'][0]['decision'] == 'changes_requested'


def test_comments_bind_revision_default_private_and_require_resolution(client):
    _, directory, data = client
    tagged = insights.mutate(data, dict(action='add_comment', finding_uid=data['findings'][0]['uid'],
                                        field='description_md', body='Acotar conclusión', author='Nombre local'), 'a' * 64, directory)
    row = tagged['insights']['comments'][0]
    assert row['visibility'] == 'private' and row['revision'] == 'a' * 64 and row['status'] == 'open'
    with pytest.raises(ValueError, match='Resolve open comments'):
        insights.mutate(tagged, dict(action='review', decision='approved', author='Revisor'), 'b' * 64, directory)
    resolved = insights.mutate(tagged, dict(action='resolve_comment', uid=row['uid'], author='Otro nombre local',
                                            resolution='Límite documentado en el campo'), 'b' * 64, directory)
    final = resolved['insights']['comments'][0]
    assert final['resolved_revision'] == 'b' * 64 and final['resolved_by'] == 'Otro nombre local'
    assert final['revision'] == 'a' * 64
    assert insights.content_digest(tagged, directory) == insights.content_digest(resolved, directory)
    with pytest.raises(ValueError, match='already resolved'):
        insights.mutate(resolved, dict(action='resolve_comment', uid=row['uid'], author='Revisor', resolution='Otra'), 'c' * 64, directory)


def test_decision_cycle_preserves_prior_review_and_latest_content(client):
    _, directory, data = client
    reviewed = insights.mutate(data, dict(action='review', decision='approved', author='Revisor'), 'a' * 64, directory)
    updated = insights.mutate(reviewed, claim_body(data), 'b' * 64, directory)
    assert insights.view(updated, directory)['review_status']['state'] == 'stale'
    requested = insights.mutate(updated, dict(action='review', decision='changes_requested', author='Revisor'), 'c' * 64, directory)
    assert len(requested['insights']['reviews']) == 2
    assert insights.view(requested, directory)['review_status']['state'] == 'changes_requested'


def test_new_objection_does_not_inherit_earlier_approval_after_resolution(client):
    _, directory, data = client
    approved = insights.mutate(data, dict(action='review', decision='approved', author='Revisor'), 'a' * 64, directory)
    comment = insights.mutate(approved, dict(action='add_comment', field='description_md',
                                             finding_uid=data['findings'][0]['uid'],
                                             body='Nueva objeción', author='Nombre local'), 'b' * 64, directory)
    assert insights.view(comment, directory)['review_status']['state'] == 'stale'
    uid = comment['insights']['comments'][0]['uid']
    resolved = insights.mutate(comment, dict(action='resolve_comment', uid=uid, resolution='Justificación registrada',
                                              author='Otro nombre local'), 'c' * 64, directory)
    assert insights.view(resolved, directory)['review_status']['state'] == 'stale'
    rereviewed = insights.mutate(resolved, dict(action='review', decision='approved', author='Revisor'), 'd' * 64, directory)
    assert insights.view(rereviewed, directory)['review_status']['state'] == 'approved'
    assert insights.content_digest(approved, directory) == insights.content_digest(rereviewed, directory)


def test_removing_all_reviewed_comments_invalidates_the_decision(client):
    _, directory, data = client
    commented = insights.mutate(data, dict(action='add_comment', field='report', body='Punto de revisión',
                                            author='Nombre local'), 'a' * 64, directory)
    uid = commented['insights']['comments'][0]['uid']
    resolved = insights.mutate(commented, dict(action='resolve_comment', uid=uid, resolution='Justificación',
                                               author='Nombre local'), 'b' * 64, directory)
    approved = insights.mutate(resolved, dict(action='review', decision='approved', author='Nombre local'), 'c' * 64, directory)
    assert insights.view(approved, directory)['review_status']['state'] == 'approved'
    approved['insights']['comments'] = []
    assert insights.view(approved, directory)['review_status']['state'] == 'stale'


@pytest.mark.parametrize('rule,text', [
    ('scope_absolute', 'Acceso total a todos los documentos'),
    ('scope_absolute', 'Total access to all documents'),
    ('security_absolute', 'Sistema completamente seguro'),
    ('security_absolute', 'Completely secure with no vulnerabilities'),
    ('fixed_without_retest', 'El problema está corregido'),
    ('fixed_without_retest', 'The issue is fixed'),
])
def test_editorial_rules_are_advisory_and_leave_text_exact(rule, text):
    data = document()
    data['findings'][0]['description_md'] = text
    pristine = deepcopy(data)
    issues = insights.editorial(data, 'en')
    assert rule in {issue['rule'] for issue in issues}
    assert all(issue['technical_verification'] is False for issue in issues)
    assert data == pristine


def test_documented_fixed_retest_avoids_unsupported_fixed_prompt():
    data = document()
    data['findings'][0].update(description_md='Corregido en el retest documentado', status='verified_fixed',
        retests=[dict(uid=workflows.new_uid(), result='fixed', tested_on='2026-10-08', evidence_uids=[data['evidence'][0]['uid']])])
    assert not any(issue['rule'] == 'fixed_without_retest' for issue in insights.editorial(data))


def test_editorial_uses_chronological_retest_with_existing_tie_break_contract():
    data = document()
    evidence_uid = data['evidence'][0]['uid']
    data['findings'][0].update(description_md='Corregido en el retest documentado', status='verified_fixed',
        retests=[dict(uid=workflows.new_uid(), result='fixed', tested_on='2026-10-08', evidence_uids=[evidence_uid]),
                 dict(uid=workflows.new_uid(), result='open', tested_on='2026-10-01', evidence_uids=[evidence_uid])])
    assert not any(issue['rule'] == 'fixed_without_retest' for issue in insights.editorial(data))
    data['findings'][0]['retests'][1]['tested_on'] = '2026-10-08'
    assert any(issue['rule'] == 'fixed_without_retest' for issue in insights.editorial(data))


def test_observed_claim_without_evidence_is_a_prompt_not_a_fabricated_record(client):
    _, directory, data = client
    body = claim_body(data)
    body['evidence_uids'] = []
    result = insights.mutate(data, body, 'a' * 64, directory)
    assert insights.editorial(result)[0]['rule'] == 'claim_without_evidence'
    assert result['insights']['claims'][0]['evidence_uids'] == []


@pytest.mark.parametrize('body', [
    {'action': 'set_claim', 'finding_uid': {}},
    {'action': 'set_risk', 'finding_uid': []},
    {'action': 'set_claim', 'finding_uid': 'missing', 'statement': 'Texto'},
    {'action': 'review', 'decision': [], 'author': 'Revisor'},
    {'action': 'review', 'decision': 'technical_passed', 'author': 'Revisor'},
    {'action': 'review', 'decision': 'approved', 'author': ''},
    {'action': 'add_comment', 'field': '../../yaml', 'body': 'Texto', 'author': 'Revisor'},
    {'action': 'delete_claim', 'uid': workflows.new_uid()},
    {'action': 'delete_risk', 'uid': workflows.new_uid()},
    {'action': 'resolve_comment', 'uid': workflows.new_uid()},
    {'action': 'unknown'},
    {'action': 'review', 'decision': 'approved', 'author': 'Nombre local', 'technical_verified': True},
])
def test_invalid_actions_return_controlled_error_and_no_save(client, body):
    _, directory, _ = client
    before = (directory / 'engagement.yaml').read_bytes()
    response = post(client, body)
    assert response.status_code == 422, response.get_json()
    assert (directory / 'engagement.yaml').read_bytes() == before


@pytest.mark.parametrize('alter', [
    lambda body: body.update(kind='verified'),
    lambda body: body.update(statement='x' * 4001),
    lambda body: body.update(evidence_uids=[workflows.new_uid()]),
    lambda body: body.update(evidence_uids=[{}]),
    lambda body: body.update(evidence_uids='not a list'),
    lambda body: body.update(evidence_uids=body['evidence_uids'] * 2),
])
def test_claim_limits_and_reference_guards(client, alter):
    _, directory, data = client
    before = (directory / 'engagement.yaml').read_bytes()
    body = claim_body(data)
    alter(body)
    assert post(client, body).status_code == 422
    assert (directory / 'engagement.yaml').read_bytes() == before


def test_writes_require_csrf_and_exact_current_etag(client):
    c, directory, data = client
    path = '/api/projects/case/insights'
    body = claim_body(data)
    plain = api.app.test_client()
    before = (directory / 'engagement.yaml').read_bytes()
    assert plain.post(path, json=body, headers={'If-Match': revision(directory / 'engagement.yaml')}).status_code == 403
    assert c.post(path, json=body).status_code == 428
    assert post(client, body, '"' + 'a' * 64 + '"').status_code == 409
    assert (directory / 'engagement.yaml').read_bytes() == before
    saved = post(client, body)
    assert saved.status_code == 200
    assert saved.headers['ETag'] != '"' + sha256(before).hexdigest() + '"'
    assert post(client, body, '"' + sha256(before).hexdigest() + '"').status_code == 409


def test_saved_data_and_view_are_consistent_and_persisted(client):
    c, directory, data = client
    saved = post(client, claim_body(data))
    assert saved.status_code == 200, saved.get_json()
    value = saved.get_json()
    assert len(value['data']['insights']['claims']) == 1
    assert value['insights']['claims'] == value['data']['insights']['claims']
    assert c.get('/api/projects/case/insights').get_json()['digest'] == value['insights']['digest']
    assert project_history.history(directory)
    current = c.get('/api/projects/case').get_json()
    assert current['insights'] == value['data']['insights']


def test_explicit_update_and_delete_claim_preserve_other_fields(client):
    _, directory, data = client
    created = post(client, claim_body(data)).get_json()['data']
    row = created['insights']['claims'][0]
    body = claim_body(data)
    body.update(uid=row['uid'], statement='Lectura específica del documento')
    edited = post(client, body).get_json()['data']
    assert edited['insights']['claims'][0]['uid'] == row['uid']
    assert edited['insights']['claims'][0]['statement'] == body['statement']
    deleted = post(client, dict(action='delete_claim', uid=row['uid'])).get_json()['data']
    assert deleted['insights']['claims'] == []
    assert deleted['findings'] == data['findings']
    assert directory.is_dir()


@pytest.mark.parametrize('model', [
    None, [], {'version': True}, {'version': 2}, {'version': 1, 'unknown': 'x'},
    {'version': 1, 'claims': 'x'}, {'version': 1, 'claims': [{}]},
    {'version': 1, 'reviews': [{'uid': workflows.new_uid(), 'decision': []}]},
    {'version': 1, 'comments': [None]},
])
def test_optional_model_malformed_import_is_structurally_rejected(model):
    data = document()
    data['insights'] = model
    assert insights.validate_structure(data)
    assert validate.structure_issues(data)


@pytest.mark.parametrize('group,limit', list(insights.GROUP_LIMITS.items()))
def test_collection_budget_is_bounded(group, limit):
    data = document()
    data['insights'] = dict(version=1, **{group: [{}] * (limit + 1)})
    assert any(group in message for _, message in insights.validate_structure(data))


def test_optional_record_identity_cannot_collide_with_existing_entity():
    data = document()
    row = dict(uid=data['evidence'][0]['uid'], finding_uid=data['findings'][0]['uid'],
               statement='Observación', kind='observed', evidence_uids=[])
    data['insights'] = dict(version=1, claims=[row])
    assert any('duplicate identity' in message for _, message in insights.validate_structure(data))


@pytest.mark.parametrize('group', ['findings', 'assets', 'evidence', 'coverage'])
@pytest.mark.parametrize('bad', [None, 1, {}, 'bad'])
def test_optional_validation_does_not_crash_when_parent_fields_are_malformed(group, bad):
    data = document()
    data['insights'] = {'version': 1}
    data[group] = bad
    assert validate.structure_issues(data)


def test_removed_historical_references_remain_visible_without_blocking_edit(client):
    _, directory, data = client
    result = insights.mutate(data, claim_body(data), 'a' * 64, directory)
    result['findings'] = []
    result['evidence'] = []
    assert not insights.validate_structure(result)
    value = insights.view(result, directory)
    assert any(link['missing'] for link in value['map']['links'])
    assert any(issue['rule'] == 'missing_reference' for issue in value['editorial'])


def test_optional_private_model_survives_verified_backup_import(client, tmp_path):
    _, directory, data = client
    response = post(client, dict(action='add_comment', field='report', body='Comentario privado', author='Nombre local'))
    assert response.status_code == 200
    backup = project_history.export_bundle(directory)
    restored = tmp_path / 'restored'
    project_history.import_bundle(backup, restored)
    import engine
    imported = engine.load_engagement(restored / 'engagement.yaml')
    assert imported['insights'] == response.get_json()['data']['insights']
    assert imported['insights']['comments'][0]['visibility'] == 'private'


def test_unregistered_external_ai_is_not_advertised(client):
    c, _, _ = client
    value = c.get('/api/projects/case/insights').get_json()
    assert value['capabilities'] == {'local_editorial_rules': True, 'optional_local_ai': True, 'external_ai': False}
    assert c.get('/api/projects/case/insights/editorial').get_json()['rules'] == insights.RULES


def test_private_comment_never_becomes_client_warning_or_publication_source(client, tmp_path):
    _, directory, data = client
    import delivery
    import publication
    private = insights.mutate(data, dict(action='add_comment', field='description_md',
                                          finding_uid=data['findings'][0]['uid'],
                                          body='{{PRIVATE_REVIEW_CANARY}}', author='PRIVATE_AUTHOR_CANARY'),
                              'a' * 64, directory)
    dump_yaml(private, directory / 'engagement.yaml')
    issues = workflows.preflight(private, directory)
    assert all('PRIVATE_REVIEW_CANARY' not in issue['message'] for issue in issues)
    assert 'insights' not in publication.project(private)
    captured = delivery.capture(directory, tmp_path / 'captured')
    assert all('PRIVATE_REVIEW_CANARY' not in issue['message'] for issue in captured['issues'])
    source = (tmp_path / 'captured' / 'engagement.yaml').read_text()
    assert 'PRIVATE_REVIEW_CANARY' not in source and 'PRIVATE_AUTHOR_CANARY' not in source
