"""Occurrence-only evidence and every retest survive the shared export boundary."""
from copy import deepcopy

from lxml import html
from PIL import Image
import pytest

import delivery
import export
import export_contract
import finding_instances
import publication
import report_extensions
from safe_markup import md
import workflows
from wizard import dump_yaml


def document(directory, language='en'):
    images = directory / 'img'
    images.mkdir()
    evidence = []
    for name, color, caption in [('occurrence (initial).png', '#246a9b', 'Initial instance evidence'),
                                  ('historical-proof.png', '#db7c30', 'Historical partial correction evidence')]:
        Image.new('RGB', (180, 110), color).save(images / name)
        evidence.append({'uid': workflows.new_uid(), 'title': caption, 'caption': caption, 'src': 'img/' + name})
    instance = finding_instances.new_instance({'endpoint': '/accounts/controlled', 'owner': 'Synthetic team',
                                               'evidence_uids': [evidence[0]['uid']]})
    data = workflows.normalize({'meta': {'lang': language, 'theme': 'serio', 'report_title': 'Instance export regression'},
        'findings': [{'id': 'F1', 'title': 'Independent affected instance', 'severity': 'info', 'cvss': 0,
                      'description_md': 'Synthetic observation', 'impact_md': 'Synthetic impact',
                      'remediation_md': 'Synthetic action', 'status': 'open', 'instances': [instance]}],
        'evidence': evidence})
    finding = data['findings'][0]
    for when, result, assessor, note, proof in [
        ('2026-10-15', 'partial', 'Historical evaluator', 'Older observation retained in full.', evidence[1]),
        ('2026-10-17', 'fixed', 'Latest evaluator', 'Final observation for this one instance.', evidence[0])]:
        finding_instances.record_retest(data, finding, instance['uid'], {
            'tested_on': when, 'result': result, 'assessor': assessor, 'notes_md': note,
            'evidence_uids': [proof['uid']]}, when + 'T12:00:00+00:00')
    assert not finding.get('evidence_uids') and not finding.get('retests')
    assert not workflows.structure_errors(data)
    return data


@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
def test_instance_images_and_historical_results_survive_real_exports(tmp_path, fmt):
    data = document(tmp_path)
    before = deepcopy(data)
    dump_yaml(data, tmp_path / 'engagement.yaml')
    source = (tmp_path / 'engagement.yaml').read_bytes()
    tree = publication.render(data, tmp_path)
    assert len(tree.xpath('//img')) == 3
    captured = delivery.capture(tmp_path, tmp_path / 'snapshot')
    assert set(captured['images']) == {'img/occurrence (initial).png', 'img/historical-proof.png'}
    result = export.export(tmp_path / 'engagement.yaml', fmt, tmp_path / ('report.' + delivery.get(fmt).extension))
    delivery.inspect_export(result, fmt, captured)
    content = export_contract.profile(result, fmt)['text']
    for text in ('Historical evaluator', 'Partially fixed', 'Older observation retained in full.',
                 'Latest evaluator', 'Final observation for this one instance.',
                 'Initial instance evidence', 'Historical partial correction evidence'):
        assert text in content
    assert data == before and (tmp_path / 'engagement.yaml').read_bytes() == source


@pytest.mark.parametrize('language,result,assessor,evidence', [
    ('es', 'Corrección parcial', 'Evaluador', 'Evidencia'),
    ('en', 'Partially fixed', 'Assessor', 'Evidence'),
    ('pt-BR', 'Correção parcial', 'Avaliador', 'Evidência')])
def test_history_labels_and_values_share_a_paragraph(tmp_path, language, result, assessor, evidence):
    data = document(tmp_path, language)
    body = report_extensions.instance_sections(data)[0]['body']
    tree = html.fragment_fromstring(str(md(body)), create_parent='div')
    assert result in tree.text_content() and len(tree.xpath('.//img')) == 3
    assert any(node.text_content() == assessor + ': Historical evaluator' for node in tree.xpath('.//p'))
    assert any(node.text_content().startswith(evidence + ': Initial instance evidence') for node in tree.xpath('.//p'))
    assert not [node for node in tree.xpath('.//p') if node.text_content().strip() in (evidence, evidence + ':')]


def test_disabled_instance_appendix_does_not_publish_its_proof(tmp_path):
    data = document(tmp_path)
    data['report']['workflow'] = {'include_instances': False}
    assert report_extensions.instance_sections(data) == []
    tree = publication.render(data, tmp_path)
    assert not tree.xpath('//img')
    assert 'Historical evaluator' not in tree.text_content()
