"""Private operational metadata survives backups, never publication projections."""
from copy import deepcopy
from io import BytesIO
import json
import zipfile

import pytest

import audience
import engine
import export
import project_history
import publication
import remediation_return
import validate
import workflows
import workspace_backup
from wizard import dump_yaml

PRIVATE_OWNER = 'PRIVATE_UNSELECTED_OWNER_0290'
PRIVATE_RETURN = 'PRIVATE_UNVERIFIED_RETURN_0290'
PRIVATE_DELIVERY = '2026-12-15'


def document():
    data = workflows.normalize({
        'meta': {'lang': 'en', 'theme': 'serio', 'report_title': 'Synthetic assessment'},
        'report': {'sections': [{'key': 'findings'}]},
        'findings': [
            {'id': 'F1', 'mode': 'vuln', 'title': 'Selected finding', 'severity': 'info',
             'description_md': 'Documented observation.', 'impact_md': 'Documented impact.',
             'remediation_md': 'Recommended action.', 'owner': 'Selected owner'},
            {'id': 'F2', 'mode': 'vuln', 'title': 'Excluded finding', 'severity': 'info',
             'description_md': 'Private observation.', 'impact_md': 'Private impact.',
             'remediation_md': 'Private action.', 'owner': PRIVATE_OWNER,
             'reported_remediation': PRIVATE_RETURN}]})
    data, _ = remediation_return.issue(data, 'private-project-0290', [data['findings'][1]['uid']])
    data['project_management'] = {'delivery_date': PRIVATE_DELIVERY, 'archived': True}
    # These valid literal rules would invalidate private operational fields if
    # those fields crossed the publication boundary and were substituted.
    data['publication'] = {'redactions': [
        {'needle': PRIVATE_OWNER, 'replacement': ''},
        {'needle': PRIVATE_DELIVERY, 'replacement': '[REDACTED]'}]}
    return data


def options(data, profile):
    selected = data['findings'][0]['uid']
    result = {'profile': profile, 'finding_uids': [selected]}
    if profile == 'public':
        result.update(client_alias='Fictional entity', aliases=[{'needle': 'Synthetic assessment', 'replacement': 'Public case'}],
                      review_confirmed=True, publish_consent=True, provenance_label='simulation',
                      approved_content=[{'finding_uid': selected, 'title': 'Approved finding',
                          'summary': 'Approved observation.', 'impact': 'Approved impact.',
                          'remediation': 'Approved action.'}])
    return result


def test_native_publication_drops_operational_metadata_before_literal_substitutions():
    source = document()
    before = deepcopy(source)
    projected = publication.project(source)
    assert 'project_management' not in projected and 'remediation_exchanges' not in projected
    assert not validate.structure_issues(projected)
    assert source == before
    assert source['remediation_exchanges'][0]['rows'][0]['base']['owner'] == PRIVATE_OWNER


@pytest.mark.parametrize('profile', ['technical', 'executive', 'public'])
def test_audience_projection_and_real_html_package_exclude_private_metadata(tmp_path, profile):
    source = document()
    source['unrecognized_private_metadata'] = {'private': 'UNKNOWN_PRIVATE_CANARY_0290'}
    before = deepcopy(source)
    projected, plan = audience.project(source, options(source, profile))
    assert 'remediation_exchanges' not in projected and 'project_management' not in projected
    assert len(projected['findings']) == 1 and plan['finding_count'] == 1
    assert PRIVATE_OWNER not in json.dumps(projected) and PRIVATE_RETURN not in json.dumps(projected)
    assert not validate.structure_issues(projected)
    if profile != 'technical':
        assert 'reported_remediation' not in projected['findings'][0]
        assert 'unrecognized_private_metadata' not in projected
    directory = tmp_path / 'source'
    directory.mkdir()
    dump_yaml(source, directory / 'engagement.yaml')
    snapshot = tmp_path / 'captured'
    captured = audience.capture(source, directory, snapshot, options(source, profile))
    snapshot_data = engine.load_engagement(snapshot / 'engagement.yaml')
    assert 'remediation_exchanges' not in snapshot_data and 'project_management' not in snapshot_data
    blob = audience.build(snapshot, ['html'], '0' * 64, 'Synthetic delivery', captured, tmp_path / 'outputs')
    with zipfile.ZipFile(BytesIO(blob)) as archive:
        assert any(name.endswith('.html') for name in archive.namelist())
        combined = '\n'.join(archive.read(name).decode('utf-8') for name in archive.namelist())
        for value in ('remediation_exchanges', 'project_management', PRIVATE_OWNER, PRIVATE_RETURN,
                      PRIVATE_DELIVERY, 'UNKNOWN_PRIVATE_CANARY_0290'):
            assert value not in combined
        manifest = json.loads(archive.read('verificacion.json'))
        assert manifest['audience']['profile'] == profile
    assert source == before


def test_ordinary_html_export_ignores_private_dates_and_batch_owner_redactions(tmp_path):
    source = document()
    dump_yaml(source, tmp_path / 'engagement.yaml')
    before = (tmp_path / 'engagement.yaml').read_bytes()
    output = export.export(tmp_path / 'engagement.yaml', 'html', tmp_path / 'report.html')
    html = output.read_text(encoding='utf-8')
    assert 'Selected finding' in html and 'Excluded finding' in html
    for value in ('remediation_exchanges', 'project_management', PRIVATE_OWNER, PRIVATE_RETURN, PRIVATE_DELIVERY):
        assert value not in html
    assert (tmp_path / 'engagement.yaml').read_bytes() == before


def test_integral_backup_and_restore_preserve_private_operational_metadata(tmp_path):
    source = document()
    directory = tmp_path / 'source/projects/private-project-0290'
    project_history.save(directory, source)
    project_history.checkpoint(directory, 'Before delivery', force=True)
    paths = (directory.parent, tmp_path / 'source/library/findings.json', tmp_path / 'source/library/designs.json')
    blob = workspace_backup.export_workspace(*paths)
    restored = tmp_path / 'restored'
    result = workspace_backup.restore_workspace(blob, restored / 'projects',
        restored / 'library/findings.json', restored / 'library/designs.json')
    target = restored / 'projects/private-project-0290'
    recovered = engine.load_engagement(target / 'engagement.yaml')
    assert result['projects'] == 1
    assert recovered['project_management'] == source['project_management']
    assert recovered['remediation_exchanges'] == source['remediation_exchanges']
    assert recovered['findings'][1]['reported_remediation'] == PRIVATE_RETURN
    assert project_history.history(target)
