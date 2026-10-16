"""Atlas source must preserve privacy and identity across full translations."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path

import engine
import publication
import pytest
import workflows


@pytest.fixture(scope='module')
def builder():
    path = Path(__file__).resolve().parents[1] / 'scripts/build-atlas-case.py'
    spec = importlib.util.spec_from_file_location('atlas_fixture_builder', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def case(builder, tmp_path_factory):
    root = tmp_path_factory.mktemp('atlas') / 'case'
    return root, builder.build_case(root)


def test_full_translations_preserve_relationships_but_not_spanish_narrative(case):
    root, manifest = case
    docs = [engine.load_engagement(root / 'projects' / lang / 'engagement.yaml') for lang in ('es', 'en', 'pt')]
    for doc in docs:
        assert not workflows.structure_errors(doc)
        assert len(doc['findings']) == 67
        assert sum(len(f.get('retests', [])) for f in doc['findings']) == 31
        assert len({f['uid'] for f in doc['findings']}) == 67
        for finding in doc['findings']:
            assert set(finding['asset_uids']) <= {a['uid'] for a in doc['assets']}
            assert set(finding['evidence_uids']) <= {e['uid'] for e in doc['evidence']}
    for translated in docs[1:]:
        for source, target in zip(docs[0]['findings'], translated['findings']):
            for key in ('id', 'uid', 'mode', 'asset_uids', 'evidence_uids', 'root_cause_uid', 'cvss_vector'):
                assert source.get(key) == target.get(key)
            assert source['title'] != target['title']
            if source['mode'] == 'vuln':
                for key in ('description_md', 'impact_md', 'remediation_md'):
                    assert source[key] != target[key]
            else:
                for original_phase, localized_phase in zip(source['phases'], target['phases']):
                    assert original_phase['steps'][0]['text_md'] != localized_phase['steps'][0]['text_md']
        assert translated['report']['sections'][3]['summary'] != docs[0]['report']['sections'][3]['summary']
    assert manifest['prose_languages'] == ['es', 'en', 'pt']
    for row in manifest['projects'].values():
        assert row['validation_errors'] == 0 and not row['validation_warnings']
        # Deliberate negative coverage states and the excluded private annex
        # must remain visible; they are not exporter failures or silent passes.
        issues = row['preflight_issues']
        assert len(issues) == 61 and {i['level'] for i in issues} == {'warning'}
        assert sum(i['path'].startswith('coverage[') for i in issues) == 60
        assert sum(i['path'] == 'attachments' for i in issues) == 1


def test_native_publication_excludes_known_controls_without_mutating_sources(case, builder, tmp_path):
    for language in ('es', 'en', 'pt'):
        source = case[0] / 'projects' / language
        before = {p.relative_to(source).as_posix(): sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
        destination = tmp_path / language
        receipt = publication.snapshot(source, destination)
        public = engine.load_engagement(destination / 'engagement.yaml')
        assert not public.get('capture_inbox')
        assert not (destination / 'originals').exists()
        assert not (destination / 'private').exists()
        for path in destination.rglob('*'):
            if path.is_file():
                blob = path.read_bytes()
                assert all(marker.encode() not in blob for marker in (builder.PRIVATE_MARKER, builder.REDACTION_MARKER, builder.METADATA_MARKER, builder.UNLINKED_MARKER))
        assert receipt['image_placements']
        assert before == {p.relative_to(source).as_posix(): sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}


def test_builder_manifest_binds_inputs_and_does_not_author_report_outputs(case):
    root, manifest = case
    assert manifest['reports_generated_by_builder'] is False
    assert manifest['network_to_scenario_targets'] is False
    for name, record in manifest['files'].items():
        blob = (root / name).read_bytes()
        assert (len(blob), sha256(blob).hexdigest()) == (record['bytes'], record['sha256'])
        assert Path(name).suffix not in ('.pdf', '.docx', '.html')
    assert {x['format'] for x in manifest['import_previews'].values()} == {'csv', 'burp', 'nuclei', 'nmap', 'sarif'}
    assert manifest['import_previews']['findings.csv']['counts']['duplicates'] == 1


def test_incomplete_translation_fails_before_creating_output(builder, tmp_path, monkeypatch):
    directory = tmp_path / 'content'
    directory.mkdir()
    incomplete = deepcopy(builder.load_content('es'))
    incomplete['machine_specs'] = []
    (directory / 'en.json').write_text(json.dumps(incomplete), encoding='utf-8')
    monkeypatch.setattr(builder, 'CONTENT', directory)
    output = tmp_path / 'output'
    with pytest.raises(ValueError, match='Incomplete localized Atlas content: en'):
        builder.build_case(output, ('en',))
    assert not output.exists()


@pytest.mark.parametrize(('language', 'expected'), [('es', 'CRÍTICO'), ('en', 'CRITICAL'), ('pt', 'CRÍTICO')])
def test_synthetic_image_localizes_human_severity_without_changing_enum(builder, tmp_path, monkeypatch, language, expected):
    content = builder.load_content(language)
    original = deepcopy(content)
    drawn = []
    render = builder.draw_wrapped

    def record_and_draw(draw, value, xy, **kwargs):
        drawn.append(value)
        return render(draw, value, xy, **kwargs)

    monkeypatch.setattr(builder, 'draw_wrapped', record_and_draw)
    builder.evidence_image(tmp_path / (language + '.png'), 1, content)
    assert expected + ' / ' + content['strings']['image_classification_suffix'] in drawn
    assert content == original
    assert content['findings'][0]['severity'] == 'critical'


@pytest.mark.parametrize('language', ('es', 'en', 'pt'))
def test_machine_evidence_depicts_the_same_asset_in_every_language(builder, language):
    content = builder.load_content(language)
    machines = builder.machines(content)
    expected_images = (13, 7, 20, 25, 31, 37, 44)
    for machine, spec, image_number in zip(machines, content['machine_specs'], expected_images):
        assert content['findings'][image_number - 1]['asset'] == spec['asset']
        assert machine['evidence_uids'] == [builder.uid('evidence-' + str(image_number))]
        assert machine['asset_uids'] == [builder.uid('asset-' + str(spec['asset']))]


def test_machine_without_matching_evidence_fails_instead_of_using_unrelated_image(builder):
    content = deepcopy(builder.load_content('es'))
    unmatched = next(i for i in range(len(content['assets'])) if all(f['asset'] != i for f in content['findings']))
    content['machine_specs'][0]['asset'] = unmatched
    with pytest.raises(ValueError, match='Machine asset has no matching evidence: M01'):
        builder.machines(content)
