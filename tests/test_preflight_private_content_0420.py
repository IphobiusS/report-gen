"""Private scanner/HTTP records cannot become delivery Markdown resources."""
from copy import deepcopy
import csv
from io import StringIO

from lxml import html
import pytest

import delivery
import export
import finding_imports
import http_evidence
import import_reconciliation
import publication
import validate
import workflows
from wizard import dump_yaml


def document():
    return workflows.normalize({
        'meta': {'report_title': 'Synthetic private content boundary', 'lang': 'en', 'theme': 'serio'},
        'findings': [{'id': 'F1', 'mode': 'vuln', 'title': 'Reviewed finding', 'severity': 'info', 'cvss': 0,
                      'description_md': 'Reviewed description', 'impact_md': 'Synthetic impact',
                      'remediation_md': 'Synthetic action', 'walkthrough': [{'text_md': 'Reviewed reproduction'}]}]})


def observation(text):
    data = document()
    stream = StringIO()
    writer = csv.writer(stream)
    writer.writerow(['title', 'severity', 'description_md'])
    writer.writerow(['Private scanner observation', 'info', text])
    body = {'format': 'csv', 'text': stream.getvalue(),
            'mapping': {'title': 'title', 'severity': 'severity', 'description_md': 'description_md'}}
    data, _ = import_reconciliation.apply({**body, 'decisions': [
        {'index': 0, 'action': 'attach', 'finding_uid': data['findings'][0]['uid'], 'fields': []}]}, data)
    return data, body


@pytest.mark.parametrize('text', ['PRIVATE_SCAN ![unpublished image](img/not-published.png)',
                                 'PRIVATE_SCAN numeric example &#31;'])
def test_private_observation_passes_actual_capture_and_export_without_source_changes(tmp_path, text):
    data, _ = observation(text)
    before = deepcopy(data)
    assert not validate.structure_issues(data, 'en')
    assert not [row for row in workflows.preflight(data, tmp_path, 'en') if row['level'] == 'error']
    assert validate.markdown_control_issues(data, 'en') == []
    dump_yaml(data, tmp_path / 'engagement.yaml')
    source_bytes = (tmp_path / 'engagement.yaml').read_bytes()
    snapshot = tmp_path / 'snapshot'
    delivery.capture(tmp_path, snapshot)
    result = export.export(snapshot / 'engagement.yaml', 'html', tmp_path / 'report.html')
    assert 'Reviewed description' in html.fromstring(result.read_bytes()).text_content()
    assert b'PRIVATE_SCAN' not in result.read_bytes()
    assert data == before and (tmp_path / 'engagement.yaml').read_bytes() == source_bytes


@pytest.mark.parametrize('text', ['![published image](img/not-published.png)', 'Published example &#31;'])
def test_same_content_in_published_markdown_remains_blocking(tmp_path, text):
    data, _ = observation('Private source')
    data['findings'][0]['description_md'] = text
    errors = [row for row in workflows.preflight(data, tmp_path, 'en') if row['level'] == 'error']
    assert errors and errors[0]['path'] == 'findings[0].description_md'
    dump_yaml(data, tmp_path / 'engagement.yaml')
    with pytest.raises(ValueError):
        delivery.capture(tmp_path, tmp_path / 'snapshot')


def test_source_structure_and_import_review_still_block_delivery(tmp_path):
    data, body = observation('Private source')
    data['findings'][0]['import_observations'][0]['selected_fields'] = ['status']
    assert any(row['level'] == 'error' for row in workflows.preflight(data, tmp_path, 'en'))
    imported, _ = finding_imports.apply({**body, 'selected': [0]}, document())
    assert any(row['level'] == 'error' and row['path'].endswith('.import_source')
               for row in workflows.preflight(imported, tmp_path, 'en'))


def test_http_original_is_private_and_reviewed_copy_is_still_checked_and_rendered(tmp_path):
    data = document()
    original = {'captured_at': '2026-10-17T10:00:00Z', 'identity': 'Private identity', 'source': 'manual',
                'request': {'method': 'GET', 'url': 'https://bank.example/private', 'http_version': 'HTTP/1.1',
                            'headers': [], 'body': '', 'body_encoding': 'utf-8'},
                'response': {'status': 200, 'http_version': 'HTTP/1.1', 'headers': [],
                             'body': 'PRIVATE_HTTP ![private](img/unpublished.png) &#31;', 'body_encoding': 'utf-8'}}
    data, identities = http_evidence.add(data, [{'original': original}], [data['findings'][0]['uid']])
    data = http_evidence.update(data, identities[0], {'ack_reviewed': True, 'publication': {
        'request_text': 'GET /reviewed HTTP/1.1', 'response_text': 'REVIEWED_HTTP ![literal](img/not-a-resource.png) &#31;',
        'caption': 'TODO: reviewed caption'}})
    before = deepcopy(data)
    assert validate.markdown_control_issues(data, 'en') == []
    issues = workflows.preflight(data, tmp_path, 'en')
    assert not [row for row in issues if row['level'] == 'error']
    assert any(row['path'].endswith('.text_md') and 'TODO' in row['message'] for row in issues)
    dump_yaml(data, tmp_path / 'engagement.yaml')
    delivery.capture(tmp_path, tmp_path / 'snapshot')
    tree = publication.render(data, tmp_path)
    content = tree.text_content()
    assert 'PRIVATE_HTTP' not in content and 'REVIEWED_HTTP' in content and '&#31;' in content
    assert not tree.xpath('//img[contains(@src,"not-a-resource")]')
    assert data == before
