"""Client verification records never reintroduce private author diagnostics."""
from copy import deepcopy
from io import BytesIO
import json
import zipfile

import pytest

import audience
import delivery
import export_jobs
import remediation_return
import workflows
from wizard import dump_yaml


def private_document(language):
    data = workflows.normalize({
        'meta': {'lang': language, 'theme': 'serio', 'report_title': 'Synthetic report'},
        'report': {'sections': [{'key': 'findings'}]},
        'findings': [{'id': 'F1', 'mode': 'vuln', 'title': 'Synthetic finding',
                     'severity': 'info', 'description_md': 'Observed behavior.',
                     'impact_md': '{{SOURCE_TEXT_CANARY_030}}', 'remediation_md': 'Recommended action.',
                     'owner': '{{BATCH_OWNER_CANARY_030}}'}],
        'attachments': [{'uid': workflows.new_uid(), 'name': 'EXCLUDED_ANNEX_CANARY_030.txt',
                         'member': '', 'required': False, 'reviewed': False, 'include': False}],
        'publication': {'redactions': [
            {'needle': '{{SOURCE_TEXT_CANARY_030}}', 'replacement': 'Reviewed impact.'},
            {'needle': '{{BATCH_OWNER_CANARY_030}}', 'replacement': 'Delivery team.'},
            {'needle': '{{NEEDLE_ONLY_CANARY_030}}', 'replacement': '[REDACTED]'}]}})
    data, _ = remediation_return.issue(data, 'synthetic', [data['findings'][0]['uid']])
    return data


def assert_private_absent(blob):
    for marker in ('SOURCE_TEXT_CANARY_030', 'BATCH_OWNER_CANARY_030',
                   'EXCLUDED_ANNEX_CANARY_030', 'NEEDLE_ONLY_CANARY_030'):
        assert marker.encode() not in blob


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('profile', [None, 'technical'])
def test_real_delivery_zip_excludes_private_warning_payloads(tmp_path, language, profile):
    source = tmp_path / 'source'
    source.mkdir()
    data = private_document(language)
    original = deepcopy(data)
    dump_yaml(data, source / 'engagement.yaml')
    before = (source / 'engagement.yaml').read_bytes()
    private_review = workflows.preflight(data, source, language)
    diagnostic_text = json.dumps(private_review)
    # Actual author content is checked before redaction and must still produce
    # private diagnostics for the real delivery sanitizer to remove.
    for marker in ('EXCLUDED_ANNEX_CANARY_030', 'SOURCE_TEXT_CANARY_030', 'BATCH_OWNER_CANARY_030'):
        assert marker in diagnostic_text
    # An unused redaction needle is private configuration, never report prose
    # requiring an editorial placeholder warning. It remains a ZIP canary.
    assert 'NEEDLE_ONLY_CANARY_030' not in diagnostic_text
    assert not any(row['path'].startswith(('publication.', 'remediation_exchanges.')) for row in private_review)
    if profile:
        captured = audience.capture(data, source, tmp_path / 'snapshot', {'profile': profile})
        build = audience.build
    else:
        captured = delivery.capture(source, tmp_path / 'snapshot')
        build = delivery.build
        assert captured['issues'] == private_review
    blob = build(tmp_path / 'snapshot', ['html', 'md'], '0' * 64, 'Synthetic delivery',
                 captured, tmp_path / 'outputs')
    with zipfile.ZipFile(BytesIO(blob)) as package:
        for name in package.namelist():
            content = package.read(name)
            assert_private_absent(content)
            if name.endswith('.zip'):
                with zipfile.ZipFile(BytesIO(content)) as nested:
                    for member in nested.namelist():
                        assert_private_absent(nested.read(member))
        manifest = json.loads(package.read('verificacion.json'))
        assert len(manifest['warnings']) == len(captured['issues']) > 0
        assert any(row['category'] == 'attachments' for row in manifest['warnings'])
        assert all(set(row) == {'level', 'category', 'message', 'details'} for row in manifest['warnings'])
        assert ('private project' if language == 'en' else 'proyecto privado') in manifest['warnings'][0]['details']
        readme = package.read('README.txt' if language == 'en' else 'LEEME.txt').decode()
        assert str(len(captured['issues'])) in readme
    assert data == original and (source / 'engagement.yaml').read_bytes() == before


@pytest.mark.parametrize('language', ['es', 'en'])
def test_individual_export_worker_downloadable_checks_are_also_private(tmp_path, language):
    source = tmp_path / 'author'
    source.mkdir()
    dump_yaml(private_document(language), source / 'engagement.yaml')
    job = tmp_path / 'job'
    job.mkdir()
    captured = delivery.capture(source, job / 'source')
    (job / 'job.json').write_text(json.dumps({'kind': 'export', 'formats': ['md'],
        'revision': '0' * 64, 'filename': 'report.zip', 'captured': captured}), encoding='utf-8')
    assert export_jobs.worker(job) == 0
    record = (job / 'verification.json').read_bytes()
    assert_private_absent(record)
    assert len(json.loads(record)['warnings']) == len(captured['issues'])


def test_arbitrary_diagnostic_fields_never_cross_the_public_boundary():
    source = [{'level': 'warning', 'path': 'CUSTOM_PRIVATE_CANARY.field',
               'message': 'MESSAGE_PRIVATE_CANARY', 'finding_uid': 'IDENTITY_PRIVATE_CANARY',
               'help': 'HELP_PRIVATE_CANARY', 'extra': 'EXTRA_PRIVATE_CANARY'}]
    before = deepcopy(source)
    projected = delivery.public_warnings(source, 'en')
    assert 'CANARY' not in json.dumps(projected)
    assert projected[0]['category'] == 'private' and len(projected) == 1
    assert source == before
