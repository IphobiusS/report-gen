"""Assessment results remain explicit, reference-bound and revision guarded."""
from copy import deepcopy
import json
import uuid
from xml.etree import ElementTree

import pytest
import test_plans as plans
import attack_paths as paths
from error_messages import language_scope


def uid(): return str(uuid.uuid4())


def source():
    asset, evidence, finding, http = uid(), uid(), uid(), uid()
    return {'meta': {'lang': 'en'}, 'findings': [{'uid': finding, 'id': 'F1', 'title': 'Authorization', 'mode': 'vuln', 'severity': 'info'}],
            'assets': [{'uid': asset, 'name': 'API', 'target': 'api.example.test'}],
            'evidence': [{'uid': evidence, 'src': 'img/proof.png', 'title': 'Proof'}],
            'http_evidence': [{'uid': http, 'title': 'PRIVATE HEADER'}]}


def test_case(data, **overrides):
    return plans.create({'title': 'Cross-tenant access', 'methodology': 'Internal API', 'methodology_version': '2026.1',
                         'test_id': 'AUTH-01', 'specialty': 'api', 'expected': 'Access denied', 'status': 'pending',
                         'asset_uids': [data['assets'][0]['uid']], **overrides})
# Helper must not be collected as a pytest test.
test_case.__test__ = False


def causal_path(data, state='observed'):
    a, b = uid(), uid()
    return paths.create({'title': 'Privilege path', 'description': 'Two explicit stages', 'consequence': 'Synthetic records exposed',
                         'nodes': [{'uid': a, 'title': 'Initial identity', 'privilege': 'reader', 'asset_uids': [data['assets'][0]['uid']]},
                                   {'uid': b, 'title': 'Protected data', 'finding_uids': [data['findings'][0]['uid']]}],
                         'edges': [{'uid': uid(), 'source_uid': a, 'target_uid': b, 'state': state,
                                    'preconditions': 'Authorized synthetic identities', 'observation': 'The response contains the controlled record',
                                    'evidence_uids': [data['evidence'][0]['uid']], 'mitigation': 'Enforce tenant authorization'}]})


def test_case_refs_and_explicit_results_are_validated():
    data = source(); data['test_cases'] = [test_case(data)]
    assert plans.structure_errors(data) == []
    data['test_cases'][0]['status'] = 'passed'
    assert any('.observed:' in message for _, message in plans.structure_errors(data))
    data['test_cases'][0]['observed'] = 'No cross-tenant response in these requests'
    assert plans.structure_errors(data) == []
    data['test_cases'][0]['evidence_uids'] = [uid()]
    assert any('.evidence_uids:' in message for _, message in plans.structure_errors(data))


@pytest.mark.parametrize('value', [None, {}, [None], [[[]]], ['unknown'], ['pending', 'pending']])
def test_malformed_reference_values_fail_without_exception(value):
    data = source(); row = test_case(data); row['asset_uids'] = value; data['test_cases'] = [row]
    assert plans.structure_errors(data)


def test_http_projection_references_preserve_validation_without_private_text():
    data = source(); row = test_case(data, http_evidence_uids=[data['http_evidence'][0]['uid']]); data['test_cases'] = [row]
    data['attack_paths'] = [causal_path(data)]; edge = data['attack_paths'][0]['edges'][0]
    edge['http_evidence_uids'] = row['http_evidence_uids']; edge['evidence_uids'] = []
    assert plans.structure_errors(data) == paths.structure_errors(data) == []
    data['http_evidence_refs'] = [{'uid': data['http_evidence'][0]['uid'], 'sha256': '0' * 64, 'published': False}]
    del data['http_evidence']
    assert plans.structure_errors(data) == paths.structure_errors(data) == []
    result = json.dumps(plans.report_sections(data) + paths.report_sections(data))
    assert 'content withheld' in result and 'PRIVATE HEADER' not in result
    del data['http_evidence_refs']
    assert plans.structure_errors(data) and paths.structure_errors(data)


def test_matrix_is_bounded_pending_unique_and_does_not_copy_results():
    body = {'roles': ['reader', 'editor'], 'tenants': ['A', 'B'], 'operations': ['GET object', 'PUT object'],
            'base': {'title': 'Tenant boundary', 'specialty': 'api', 'expected': 'Authorized access only'}}
    before = deepcopy(body); rows = plans.matrix(body)
    assert body == before and len(rows) == 8
    assert len({row['uid'] for row in rows}) == 8
    assert {(row['identity'], row['tenant'], row['operation']) for row in rows} == {(r, t, o) for r in body['roles'] for t in body['tenants'] for o in body['operations']}
    assert all(row['status'] == 'pending' and not row['evidence_uids'] for row in rows)
    for changed in [dict(body, roles=['reader', ' reader ']), dict(body, roles=['r' + str(i) for i in range(30)], tenants=['t' + str(i) for i in range(30)]), dict(body, base={'title': 'Bad', 'observed': 'Already passed'}), dict(body, base={'title': 'Bad', 'status': 'passed'}), dict(body, base={'title': 'Bad', 'http_evidence_uids': [uid()]})]:
        with pytest.raises(ValueError): plans.matrix(changed)


@pytest.mark.parametrize('lang', ['es', 'en', 'pt-BR'])
def test_catalog_is_local_versioned_and_not_presented_as_complete(lang):
    catalog = plans.catalog(lang)
    assert catalog['version'] == '1.0' and catalog['official_catalog'] is False
    assert {row['specialty'] for row in catalog['plans']} == {'web', 'api', 'ad', 'cloud', 'mobile', 'ai'}
    assert len(catalog['plans']) == 6 and sum(len(p['cases']) for p in catalog['plans']) == 12
    assert all(row['status'] == 'pending' for plan in catalog['plans'] for row in plan['cases'])


def test_paths_require_evidence_for_demonstrated_edges_and_preserve_inferences():
    data = source(); data['attack_paths'] = [causal_path(data)]
    assert paths.structure_errors(data) == []
    edge = data['attack_paths'][0]['edges'][0]; edge['evidence_uids'] = []
    assert any('demostrada' in message for _, message in paths.structure_errors(data))
    edge['state'] = 'inferred'; assert paths.structure_errors(data) == []
    text = paths.report_sections(data)[0]['body']; assert 'Inferred' in text and 'Demonstrated by the analyst' not in text
    edge['observation'] = ''; assert paths.structure_errors(data)


def test_causal_cycles_parallel_conflicts_and_missing_stages_are_rejected():
    data = source(); original = causal_path(data); data['attack_paths'] = [original]
    first = original['edges'][0]
    for second in [dict(first, uid=uid(), state='blocked'), dict(first, uid=uid(), source_uid=first['target_uid'], target_uid=first['source_uid']), dict(first, uid=uid(), source_uid=uid()), dict(first, uid=uid(), target_uid=first['source_uid'])]:
        original['edges'] = [first, second]
        assert paths.structure_errors(data)
    original['edges'] = [first, dict(first, uid=uid(), source_uid=first['target_uid'], target_uid=first['source_uid'])]
    with pytest.raises(ValueError, match='ciclo'): paths.topological_nodes(original)


def test_duplicate_identities_across_plans_and_paths_are_rejected():
    data = source(); data['test_cases'] = [test_case(data)]; path = causal_path(data)
    path['nodes'][0]['uid'] = data['test_cases'][0]['uid']; data['attack_paths'] = [path]
    assert paths.structure_errors(data)
    assert plans.structure_errors(data, [data['test_cases'][0]['uid']])


def test_deterministic_svg_escapes_author_text_and_report_projection_is_pure():
    data = source(); path = causal_path(data); path['title'] = '<script>alert("no")</script>'
    data['test_cases'] = [test_case(data, observed='Literal **asterisks** and | pipes', status='passed')]; data['attack_paths'] = [path]
    before = deepcopy(data); svg = paths.graph_svg(path, 'en')
    tree = ElementTree.fromstring(svg); assert not tree.findall('.//{http://www.w3.org/2000/svg}script')
    assert '&lt;script&gt;' in svg
    reversed_path = deepcopy(path); reversed_path['nodes'].reverse(); reversed_path['edges'].reverse()
    assert paths.graph_svg(reversed_path, 'en') == svg
    assert [x['uid'] for x in paths.topological_nodes(path)] == [path['edges'][0]['source_uid'], path['edges'][0]['target_uid']]
    assert plans.report_sections(data) and paths.report_sections(data)
    assert data == before
    data['report'] = {'workflow': {'include_test_cases': False, 'include_attack_paths': False}}
    assert plans.report_sections(data) == paths.report_sections(data) == []


@pytest.mark.parametrize('lang,phrase', [('es', 'estado'), ('en', 'status'), ('pt', 'status')])
def test_validation_localized(lang, phrase):
    data = source(); data['test_cases'] = [test_case(data, status='wrong')]
    with language_scope(lang):
        assert phrase in plans.structure_errors(data)[0][1]


@pytest.fixture
def client(tmp_path, monkeypatch):
    import app as webapp
    from _support import auth_client
    monkeypatch.setattr(webapp, 'PROJECTS', tmp_path)
    # The root integration registers this module. During isolated development,
    # register once before this process starts handling requests.
    if 'assessment_case_create' not in webapp.app.view_functions:
        import assessment_api
        assessment_api.register(webapp)
    c = auth_client(webapp.app)
    assert c.post('/api/projects', json={'slug': 'assess', 'title': 'Assessment'}).status_code == 200
    return c, tmp_path / 'assess'


def call(c, path, body=None, method='POST', etag=None):
    tag = etag if etag is not None else c.get('/api/projects/assess').headers['ETag']
    return c.open('/api/projects/assess/assessment/' + path, method=method, json=body, headers={'If-Match': tag})


def test_api_case_lifecycle_cas_and_failed_write_atomicity(client):
    c, directory = client
    before = (directory / 'engagement.yaml').read_bytes()
    bad = call(c, 'test-cases', {'title': 'Result without observation', 'status': 'passed'})
    assert bad.status_code == 422 and (directory / 'engagement.yaml').read_bytes() == before
    stale = call(c, 'test-cases', {'title': 'Stale'}, etag='stale'); assert stale.status_code == 409
    missing = c.post('/api/projects/assess/assessment/test-cases', json={'title': 'Missing'})
    assert missing.status_code == 428
    created = call(c, 'test-cases', {'title': 'AuthZ', 'expected': 'Deny another tenant'})
    assert created.status_code == 200, created.get_json()
    row = created.get_json()['data']['test_cases'][0]; ident = row['uid']; old_tag = created.headers['ETag']
    row.update(status='failed', observed='Synthetic other-tenant record returned')
    updated = call(c, 'test-cases/' + ident, row, 'PUT')
    assert updated.status_code == 200
    assert call(c, 'test-cases/' + ident, row, 'PUT', old_tag).status_code == 409
    assert call(c, 'test-cases/' + ident, None, 'DELETE').status_code == 200
    assert not c.get('/api/projects/assess').get_json()['test_cases']
    assert list((directory / 'history' / 'snapshots').glob('*'))


def test_api_matrix_preview_never_mutates_and_batch_is_atomic(client):
    c, directory = client
    body = {'roles': ['A', 'B'], 'tenants': ['X'], 'operations': ['GET', 'POST'], 'base': {'title': 'Authorization'}}
    before = (directory / 'engagement.yaml').read_bytes()
    preview = call(c, 'matrix', dict(body, preview=True)); assert preview.status_code == 200 and preview.get_json()['count'] == 4
    assert (directory / 'engagement.yaml').read_bytes() == before
    applied = call(c, 'matrix', body); assert applied.status_code == 200 and len(applied.get_json()['data']['test_cases']) == 4
    before = (directory / 'engagement.yaml').read_bytes()
    result = call(c, 'test-cases/batch', {'cases': [{'title': 'Valid'}, {'title': 'Invalid', 'status': 'passed'}]})
    assert result.status_code == 422 and (directory / 'engagement.yaml').read_bytes() == before


def test_api_path_graph_and_cycle_rejection(client):
    c, directory = client
    a, b = uid(), uid()
    body = {'title': 'Declared path', 'nodes': [{'uid': a, 'title': 'A'}, {'uid': b, 'title': 'B'}], 'edges': [{'uid': uid(), 'source_uid': a, 'target_uid': b, 'state': 'inferred', 'observation': 'Requires separate confirmation'}]}
    result = call(c, 'attack-paths', body); assert result.status_code == 200, result.get_json()
    row = result.get_json()['data']['attack_paths'][0]
    graph = c.get('/api/projects/assess/assessment/attack-paths/' + row['uid'] + '/graph.svg?lang=en')
    assert graph.status_code == 200 and graph.mimetype == 'image/svg+xml'
    assert 'sandbox' in graph.headers['Content-Security-Policy']
    before = (directory / 'engagement.yaml').read_bytes()
    row['edges'].append({'uid': uid(), 'source_uid': b, 'target_uid': a, 'state': 'inferred', 'observation': 'Cycle'})
    result = call(c, 'attack-paths/' + row['uid'], row, 'PUT')
    assert result.status_code == 422 and (directory / 'engagement.yaml').read_bytes() == before
    assert call(c, 'attack-paths/' + row['uid'], None, 'DELETE').status_code == 200


def test_graph_panels_remain_bounded_and_staging_is_pure_idempotent(tmp_path):
    from io import BytesIO
    from hashlib import sha256
    from PIL import Image
    data = source(); nodes = [{'uid': uid(), 'title': 'Stage ' + str(i) + ' WWW '*25, 'privilege': 'reader'} for i in range(40)]
    edges = [{'uid': uid(), 'source_uid': nodes[a]['uid'], 'target_uid': nodes[b]['uid'], 'state': 'inferred', 'observation': 'Explicit hypothesis'} for a in range(40) for b in range(a+1,40)][:100]
    data['attack_paths'] = [paths.create({'title': 'A bounded 100-transition synthetic path', 'nodes': nodes, 'edges': edges})]
    before = deepcopy(data)
    panels = paths.graph_panels(data['attack_paths'][0], 'pt')
    assert len(panels) == 34
    for panel in panels:
        with Image.open(BytesIO(panel['blob'])) as image:
            assert image.width == 1400 and image.height <= 763
    staged = paths.stage_graphs(data, tmp_path / 'published')
    assert data == before and len(staged['attack_path_figures']) == 34
    assert paths.structure_errors(staged) == []
    files = {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob('*.png')}
    repeated = paths.stage_graphs(staged, tmp_path / 'published')
    assert repeated == staged
    assert files == {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob('*.png')}
    for figure in staged['attack_path_figures']:
        assert figure['sha256'] == sha256((tmp_path / 'published' / figure['src']).read_bytes()).hexdigest()
    assert all(figure['src'] in paths.report_sections(staged)[0]['body'] for figure in staged['attack_path_figures'])


def test_graph_metadata_rejects_traversal_missing_parts_and_symlink(tmp_path):
    data = source(); data['attack_paths'] = [causal_path(data)]
    staged = paths.stage_graphs(data, tmp_path / 'published'); row = staged['attack_path_figures'][0]
    row['src'] = '../private.png'
    assert paths.structure_errors(staged)
    staged = paths.stage_graphs(data, tmp_path / 'published'); staged['attack_path_figures'][0]['parts'] = 2
    assert paths.structure_errors(staged)
    target = tmp_path / 'symlink'; target.mkdir(); (target / 'img').symlink_to(tmp_path / 'published' / 'img', target_is_directory=True)
    with pytest.raises(ValueError): paths.stage_graphs(data, target)


@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
def test_generated_causal_diagram_survives_real_export_and_contract(tmp_path, fmt):
    import delivery
    import export
    import workflows
    from wizard import dump_yaml
    data = {'meta': {'lang': 'en', 'theme': 'serio', 'report_title': 'Synthetic assessment with diagram'},
            'findings': [], 'assets': [], 'evidence': []}
    nodes = [{'uid': uid(), 'title': label} for label in ('Reader identity', 'Protected service', 'Synthetic records')]
    path = paths.create({'title': 'Explicit unverified route', 'nodes': nodes, 'edges': [
        {'uid': uid(), 'source_uid': nodes[0]['uid'], 'target_uid': nodes[1]['uid'], 'state': 'inferred', 'observation': 'The relationship still requires verification.'},
        {'uid': uid(), 'source_uid': nodes[1]['uid'], 'target_uid': nodes[2]['uid'], 'state': 'blocked', 'observation': 'No test identity for the destination.', 'mitigation': 'Enforce authorization.'}]})
    data['attack_paths'] = [path]; data['test_cases'] = [plans.create({'title': 'Blocked authorization case', 'status': 'blocked', 'observed': 'No destination test identity', 'expected': 'Authorized identities only'})]
    data = workflows.normalize(data); dump_yaml(data, tmp_path / 'engagement.yaml')
    before = (tmp_path / 'engagement.yaml').read_bytes()
    captured = delivery.capture(tmp_path, tmp_path / 'snapshot')
    assert len([key for key in captured['images'] if key.startswith('img/rg-attack-')]) == 1
    assert (tmp_path / 'engagement.yaml').read_bytes() == before and not (tmp_path / 'img').exists()
    output = export.export(tmp_path / 'engagement.yaml', fmt, tmp_path / ('report.' + delivery.get(fmt).extension))
    result = delivery.inspect_export(output, fmt, captured)
    assert result
    assert (tmp_path / 'engagement.yaml').read_bytes() == before and not (tmp_path / 'img').exists()
