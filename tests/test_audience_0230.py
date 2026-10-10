"""Audience outputs contain selected bytes, never merely CSS-hidden source data."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import zipfile

import pytest
from PIL import Image, PngImagePlugin

import app as api
import audience
import workflows
from wizard import dump_yaml
from _support import auth_client

CANARIES = ('PRIVATE_COMMAND_0230', 'PRIVATE_IMAGE_0230', 'PRIVATE_ORIGINAL_0230',
            'PRIVATE_HISTORY_0230', 'PRIVATE_CONTACT_0230', 'PRIVATE_METADATA_0230',
            'PRIVATE_TITLE_0230', 'PRIVATE_TARGET_0230', 'PRIVATE_COMMENT_0230',
            'PRIVATE_UNSELECTED_0230', 'PRIVATE_RETEST_0230', 'PRIVATE_ANNEX_0230')


def fixture_data():
    return workflows.normalize({'meta': {'report_title': CANARIES[6], 'client': 'Private Bank 0230',
        'lang': 'es', 'theme': 'serio', 'assessor': CANARIES[5],
        'contacts': {'client': [{'name': CANARIES[4], 'email': 'private@example.test'}]},
        'extra': CANARIES[5]},
        'report': {'sections': [{'key': 'findings'}, {'key': 'private-notes', 'title': 'Private notes',
                                 'body': CANARIES[3]}]},
        'findings': [{'id': 'PRIVATE-ID-0230', 'title': 'Control documentado', 'mode': 'vuln',
            'cvss': 0, 'severity': 'info', 'description_md': 'Conclusión documentada. `PRIVATE_COMMAND_0230`\n\n````\nPRIVATE_COMMAND_0230\n````',
            'impact_md': 'Consecuencia de negocio observada.', 'remediation_md': 'Corrección propuesta.',
            'affected': CANARIES[7], 'walkthrough': [{'command': CANARIES[0],
                'text_md': 'Reproducción reservada', 'figure': {'src': 'img/private.png', 'caption': CANARIES[1]}}]},
            {'id': 'F2', 'title': CANARIES[9], 'mode': 'vuln', 'severity': 'info', 'cvss': 0,
             'description_md': CANARIES[9], 'impact_md': 'Impacto', 'remediation_md': 'Acción'}]})


def save(directory, data):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'img').mkdir(exist_ok=True)
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text('Comment', CANARIES[1])
    Image.new('RGB', (30, 20), 'blue').save(directory / 'img/private.png', pnginfo=png_info)
    (directory / 'originals').mkdir(exist_ok=True)
    (directory / 'originals/private.txt').write_text(CANARIES[2])
    (directory / 'history').mkdir(exist_ok=True)
    (directory / 'history/private.txt').write_text(CANARIES[3])
    dump_yaml(data, directory / 'engagement.yaml')


@pytest.fixture
def client(tmp_path, monkeypatch):
    directory = tmp_path / 'projects' / 'private-bank-0230'
    data = fixture_data()
    save(directory, data)
    monkeypatch.setattr(api, 'PROJECTS', directory.parent)
    return auth_client(api.app), directory, data


def public_options(data):
    uid = data['findings'][0]['uid']
    return {'profile': 'public', 'finding_uids': [uid], 'title': 'Caso público revisado',
            'client_alias': 'Entidad ficticia', 'aliases': [{'needle': 'Private Bank 0230', 'replacement': 'Entidad ficticia'}],
            'review_confirmed': True, 'publish_consent': True, 'provenance_label': 'simulation',
            'approved_content': [{'finding_uid': uid, 'title': 'Control público', 'summary': 'Observación pública documentada.',
                                  'impact': 'Consecuencia expresamente revisada.', 'remediation': 'Mitigación propuesta.'}]}


def all_texts(blob, name):
    if name.endswith('.pdf'):
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(blob))
        return '\n'.join(page.extract_text() or '' for page in reader.pages) + '\n' + str(reader.metadata)
    if name.endswith(('.docx', '.zip')):
        with zipfile.ZipFile(BytesIO(blob)) as package:
            return '\n'.join(all_texts(package.read(member), member) for member in package.namelist())
    text = blob.decode('utf-8', errors='ignore')
    if name == 'report.md':
        from exporters.markdown import parse_exported
        return parse_exported(text).text_content() + '\n' + text
    if name.endswith('.html'):
        from lxml import html
        return html.document_fromstring(text).text_content() + '\n' + text
    if name.endswith('.xml'):
        from lxml import etree
        root = etree.fromstring(blob, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        return ''.join(root.itertext()) + '\n' + text
    return text


def preview_response(c, directory, options):
    tag = '"' + sha256((directory / 'engagement.yaml').read_bytes()).hexdigest() + '"'
    return c.post('/api/projects/private-bank-0230/audiences/preview', json=options, headers={'If-Match': tag})


def export_response(c, directory, options, chosen_formats=None, **extra):
    body = dict(options, formats=chosen_formats or ['html', 'docx', 'md', 'pdf'], label='Extracto revisado', acknowledge_warnings=True)
    body.update(extra)
    tag = '"' + sha256((directory / 'engagement.yaml').read_bytes()).hexdigest() + '"'
    return c.post('/api/projects/private-bank-0230/audiences/export', json=body, headers={'If-Match': tag})


@pytest.mark.parametrize('profile', ['technical', 'executive', 'public'])
def test_projection_is_pure_and_preview_matches_real_selected_content(client, profile):
    c, directory, data = client
    before = deepcopy(data)
    source = (directory / 'engagement.yaml').read_bytes()
    options = public_options(data) if profile == 'public' else {'profile': profile, 'finding_uids': [data['findings'][0]['uid']]}
    result = audience.preview(data, directory, options)
    assert data == before
    assert result['profile'] == profile and result['plan']['finding_count'] == 1
    assert result['plan']['originals'] is False
    assert CANARIES[9] not in result['content_text']
    assert (directory / 'engagement.yaml').read_bytes() == source
    response = preview_response(c, directory, options)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['revision'] == sha256(source).hexdigest()
    assert 'data' not in response.get_json()
    assert response.get_json()['content_text'] == result['content_text']


@pytest.mark.parametrize('language', ['es', 'en'])
def test_public_canaries_absent_in_all_four_native_formats_and_metadata(client, language):
    c, directory, data = client
    data['meta']['lang'] = language
    save(directory, data)
    before = (directory / 'engagement.yaml').read_bytes()
    response = export_response(c, directory, public_options(data))
    assert response.status_code == 200, response.get_json()
    assert 'caso-publico.zip' in response.headers['Content-Disposition']
    assert 'private-bank' not in response.headers['Content-Disposition']
    with zipfile.ZipFile(BytesIO(response.data)) as package:
        assert package.testzip() is None
        assert set(package.namelist()) == {'informe.html', 'informe.docx', 'markdown.zip', 'informe.pdf',
                                          'verificacion.json', 'README.txt' if language == 'en' else 'LEEME.txt'}
        manifest = json.loads(package.read('verificacion.json'))
        assert manifest['audience']['profile'] == 'public'
        assert manifest['audience']['public_permission_declared'] is True
        assert manifest['audience']['provenance_label'] == 'simulation'
        assert manifest['source_revision'] == sha256(before).hexdigest()
        for name in package.namelist():
            text = all_texts(package.read(name), name)
            assert all(canary not in text for canary in CANARIES), name
            assert 'Private Bank 0230' not in text, name
            assert 'PRIVATE-ID-0230' not in text, name
            assert data['findings'][0]['uid'] not in text, name
            if name in {'informe.pdf', 'informe.docx', 'markdown.zip', 'informe.html'}:
                assert 'Control público' in text, name
                assert 'SIMULACIÓN' in text or 'SIMULATION' in text, name
                assert 'Mitigación propuesta.' in text, name
        assert manifest['files']['informe.html']['checks']['standalone'] is True
        assert all(row['checks']['contract_version'] == 3 for row in manifest['files'].values())
    assert (directory / 'engagement.yaml').read_bytes() == before


def test_executive_retains_business_decision_but_excludes_technical_resources(client):
    c, directory, data = client
    uid = data['findings'][0]['uid']
    data['insights'] = {'version': 1, 'claims': [], 'comments': [{
        'uid': workflows.new_uid(), 'body': '{{' + CANARIES[8] + '}}', 'field': 'report', 'author': 'Editor local',
        'visibility': 'private', 'status': 'open', 'created': '2026-10-08T00:00:00Z', 'revision': 'a' * 64}], 'reviews': [],
        'risks': [{'uid': workflows.new_uid(), 'finding_uid': uid, 'service': 'Servicio de pagos', 'consequence': 'Interrupción documentada',
                   'priority': 'P1', 'rationale': 'Continuidad prioritaria', 'owner': 'Equipo de servicio'}]}
    save(directory, data)
    response = export_response(c, directory, {'profile': 'executive', 'finding_uids': [uid]})
    assert response.status_code == 200, response.get_json()
    with zipfile.ZipFile(BytesIO(response.data)) as package:
        for name in package.namelist():
            text = all_texts(package.read(name), name)
            assert all(canary not in text for canary in CANARIES), name
            assert 'PRIVATE-ID-0230' not in text
            if name in {'informe.pdf', 'informe.docx', 'markdown.zip', 'informe.html'}:
                assert 'Control documentado' in text
                assert 'Servicio de pagos' in text
                assert 'No acordado' in text
                assert 'Continuidad prioritaria' in text
        manifest = json.loads(package.read('verificacion.json'))
        assert manifest['audience']['plan']['attachments'] is False
        assert all('anexos/' not in name for name in manifest['files'])


def test_technical_actual_selection_and_cleaned_image_metadata(client):
    c, directory, data = client
    uid = data['findings'][0]['uid']
    response = export_response(c, directory, {'profile': 'technical', 'finding_uids': [uid], 'section_keys': ['findings']}, ['html', 'md'])
    assert response.status_code == 200, response.get_json()
    with zipfile.ZipFile(BytesIO(response.data)) as package:
        html_text = package.read('informe.html').decode()
        assert CANARIES[0] in html_text
        assert CANARIES[9] not in html_text
        assert CANARIES[3] not in html_text
        with zipfile.ZipFile(BytesIO(package.read('markdown.zip'))) as md:
            assert set(md.namelist()) == {'report.md', 'img/private.png'}
            with Image.open(BytesIO(md.read('img/private.png'))) as image:
                assert 'Comment' not in image.info
        manifest = json.loads(package.read('verificacion.json'))
        assert manifest['audience']['profile'] == 'technical'
        assert 'originals' in manifest['audience']['plan']['excluded']


@pytest.mark.parametrize('key,value', [('review_confirmed', False), ('publish_consent', False),
    ('review_confirmed', 'true'), ('publish_consent', 1), ('provenance_label', 'client'),
    ('client_alias', ''), ('aliases', []), ('approved_content', []), ('finding_uids', [])])
def test_public_permissions_and_authored_content_are_required(client, key, value):
    c, directory, data = client
    options = public_options(data)
    options[key] = value
    before = (directory / 'engagement.yaml').read_bytes()
    response = export_response(c, directory, options, ['md'])
    assert response.status_code == 422
    assert (directory / 'engagement.yaml').read_bytes() == before


@pytest.mark.parametrize('key', ['review_confirmed', 'publish_consent', 'provenance_label', 'client_alias', 'aliases', 'approved_content', 'finding_uids'])
def test_missing_public_requirements_do_not_get_assumed(client, key):
    c, directory, data = client
    options = public_options(data)
    del options[key]
    assert export_response(c, directory, options, ['md']).status_code == 422


@pytest.mark.parametrize('malformed', [None, True, 42, {}, [], 'all'])
def test_invalid_profile_is_controlled_value_error(client, malformed):
    c, directory, data = client
    with pytest.raises(ValueError):
        audience.project(data, {'profile': malformed})


@pytest.mark.parametrize('uids', [[], ['missing'], ['not-a-uuid'], [None], 'all', True])
def test_selection_never_silently_falls_back_to_all(client, uids):
    c, directory, data = client
    with pytest.raises(ValueError):
        audience.project(data, {'profile': 'technical', 'finding_uids': uids})


def test_duplicate_selection_and_public_unknown_fields_rejected(client):
    c, directory, data = client
    uid = data['findings'][0]['uid']
    with pytest.raises(ValueError):
        audience.project(data, {'profile': 'technical', 'finding_uids': [uid, uid]})
    options = public_options(data)
    options['approved_content'][0]['walkthrough'] = 'not-public'
    assert export_response(c, directory, options, ['md']).status_code == 422


@pytest.mark.parametrize('profile', ['executive', 'public'])
def test_secret_detection_blocks_included_prose_not_just_hides_it(client, profile):
    c, directory, data = client
    if profile == 'public':
        options = public_options(data)
        options['approved_content'][0]['summary'] = 'password=Sup3rSensitive0230'
    else:
        data['findings'][0]['description_md'] = 'password=Sup3rSensitive0230'
        save(directory, data)
        options = {'profile': 'executive', 'finding_uids': [data['findings'][0]['uid']]}
    preview = preview_response(c, directory, options)
    assert preview.status_code == 200
    assert any(issue['level'] == 'error' for issue in preview.get_json()['issues'])
    assert export_response(c, directory, options, ['md']).status_code == 422


def test_alias_substitution_does_not_mutate_original(client):
    c, directory, data = client
    before = deepcopy(data)
    options = public_options(data)
    options['approved_content'][0]['summary'] = 'Private Bank 0230 confirmó el contexto.'
    derived, _ = audience.project(data, options)
    assert 'Private Bank 0230' not in json.dumps(derived)
    assert 'Entidad ficticia' in derived['findings'][0]['description_md']
    assert data == before


def test_public_plain_text_cannot_embed_images_html_links_or_commands(client):
    c, directory, data = client
    options = public_options(data)
    options['approved_content'][0]['summary'] = '<script>alert(1)</script> ![x](img/private.png) [read](https://private.test/path) `literal`'
    derived, _ = audience.project(data, options)
    tree = audience.publication.render(derived, directory)
    assert not tree.xpath('//script|//img|//a[starts-with(@href,"https://private.test")]')
    assert not tree.xpath('//pre[contains(@class,"cmd")]|//code')
    assert '<script>alert(1)</script>' in audience.publication.rendered_text(tree)


def test_removed_reference_is_blocked_instead_of_silent_dangling_link(client):
    c, directory, data = client
    data['findings'][0]['description_md'] = '[Otra conclusión](#F2)'
    save(directory, data)
    options = {'profile': 'technical', 'finding_uids': [data['findings'][0]['uid']], 'section_keys': ['findings']}
    result = audience.preview(data, directory, options)
    assert any(issue['level'] == 'error' and 'referencias' in issue['message'] for issue in result['issues'])
    assert export_response(c, directory, options, ['md']).status_code == 422


def test_warnings_ack_revision_and_csrf_protect_export(client):
    c, directory, data = client
    options = public_options(data)
    assert export_response(c, directory, options, ['md'], acknowledge_warnings=False).status_code == 422
    body = dict(options, formats=['md'], label='Protected', acknowledge_warnings=True)
    assert c.post('/api/projects/private-bank-0230/audiences/export', json=body).status_code == 428
    assert c.post('/api/projects/private-bank-0230/audiences/export', json=body, headers={'If-Match': '"stale"'}).status_code == 409
    with api.app.test_client() as raw:
        assert raw.post('/api/projects/private-bank-0230/audiences/export', json=body).status_code == 403
        token = raw.get('/api/session').get_json()['csrf']
        assert raw.post('/api/projects/private-bank-0230/audiences/preview', json=options,
                        headers={'X-CSRF-Token': token, 'Origin': 'https://evil.example'}).status_code == 403


@pytest.mark.parametrize('extra', [{'oops': 'unknown'}, {'formats': []}, {'formats': ['html', 'html']},
    {'formats': ['unknown']}, {'formats': [None]}, {'label': ''}, {'label': 1}, {'acknowledge_warnings': 1}])
def test_export_request_budgets_and_types(client, extra):
    c, directory, data = client
    assert export_response(c, directory, public_options(data), ['md'], **extra).status_code == 422


def test_source_can_change_after_capture_without_changing_rendered_derivative(client, monkeypatch):
    c, directory, data = client
    original = audience.build
    def later_edit(snapshot, formats, identity, label, captured, outputs):
        changed = deepcopy(data)
        changed['findings'][0]['title'] = 'POST_CAPTURE_CHANGE_0230'
        dump_yaml(changed, directory / 'engagement.yaml')
        return original(snapshot, formats, identity, label, captured, outputs)
    monkeypatch.setattr(audience, 'build', later_edit)
    response = export_response(c, directory, public_options(data), ['html'])
    assert response.status_code == 200
    with zipfile.ZipFile(BytesIO(response.data)) as package:
        assert 'POST_CAPTURE_CHANGE_0230' not in package.read('informe.html').decode()
        assert 'Control público' in package.read('informe.html').decode()


def test_alias_rules_and_text_budgets_are_bounded(client):
    c, directory, data = client
    options = public_options(data)
    options['approved_content'][0]['summary'] = 'x' * (audience.MAX_TEXT + 1)
    with pytest.raises(ValueError):
        audience.project(data, options)
    options = public_options(data)
    options['aliases'] *= 201
    with pytest.raises(ValueError):
        audience.project(data, options)


@pytest.mark.parametrize('profile', ['executive', 'public'])
@pytest.mark.parametrize('decision_source', ['aliases', 'source_redactions'])
def test_literal_privacy_decisions_precede_markup_escaping_in_all_formats(client, profile, decision_source):
    c, directory, data = client
    private = 'PRIVATE_PROSE_CANARY_0230 private_name.example'
    rules = [{'needle': 'PRIVATE_PROSE_CANARY_0230', 'replacement': 'Texto revisado'},
             {'needle': 'private_name.example', 'replacement': 'public.example'}]
    uid = data['findings'][0]['uid']
    data['findings'][0]['description_md'] = private
    if decision_source == 'source_redactions':
        data['publication'] = {'redactions': rules}
    save(directory, data)
    options = public_options(data) if profile == 'public' else {'profile': 'executive', 'finding_uids': [uid]}
    if profile == 'public':
        options['approved_content'][0]['summary'] = private
    if decision_source == 'aliases':
        options.setdefault('aliases', []).extend(rules)
    result = export_response(c, directory, options)
    assert result.status_code == 200, result.get_json()
    with zipfile.ZipFile(BytesIO(result.data)) as package:
        for name in ('informe.html', 'informe.docx', 'markdown.zip', 'informe.pdf'):
            text = all_texts(package.read(name), name)
            assert 'PRIVATE_PROSE_CANARY_0230' not in text, name
            assert 'private_name.example' not in text, name
            assert 'Texto revisado' in text and 'public.example' in text, name


@pytest.mark.parametrize('profile', ['executive', 'public'])
def test_alias_replacement_cannot_introduce_private_resource_or_executable_markup(client, profile):
    c, directory, data = client
    uid = data['findings'][0]['uid']
    data['findings'][0]['description_md'] = 'REPLACE_ME_0230'
    save(directory, data)
    options = public_options(data) if profile == 'public' else {'profile': 'executive', 'finding_uids': [uid]}
    if profile == 'public':
        options['approved_content'][0]['summary'] = 'REPLACE_ME_0230'
    options.setdefault('aliases', []).append({'needle': 'REPLACE_ME_0230',
        'replacement': '![PRIVATE_IMAGE](img/private.png) <script>alert(1)</script> `PRIVATE_COMMAND`'})
    derived, _ = audience.project(data, options)
    tree = audience.publication.render(derived, directory)
    assert not tree.xpath('//img|//script|//pre|//code')
    result = export_response(c, directory, options, ['html', 'md'])
    assert result.status_code == 200, result.get_json()
    with zipfile.ZipFile(BytesIO(result.data)) as package:
        with zipfile.ZipFile(BytesIO(package.read('markdown.zip'))) as md:
            assert md.namelist() == ['report.md']


def test_explicit_secret_redaction_is_accepted_without_false_block(client):
    c, directory, data = client
    options = public_options(data)
    options['approved_content'][0]['summary'] = 'password=Sup3rSensitive0230'
    options['aliases'].append({'needle': 'Sup3rSensitive0230', 'replacement': '[censurado]'})
    response = export_response(c, directory, options, ['html'])
    assert response.status_code == 200, response.get_json()
    with zipfile.ZipFile(BytesIO(response.data)) as package:
        text = all_texts(package.read('informe.html'), 'informe.html')
        assert 'Sup3rSensitive0230' not in text
        assert 'password=[censurado]' in text


def test_preview_requires_same_saved_revision_as_export(client):
    c, directory, data = client
    options = public_options(data)
    assert c.post('/api/projects/private-bank-0230/audiences/preview', json=options).status_code == 428
    assert c.post('/api/projects/private-bank-0230/audiences/preview', json=options,
                  headers={'If-Match': '"stale"'}).status_code == 409


def test_machine_executive_uses_summary_prose_without_host_or_phases(client):
    c, directory, data = client
    uid = data['findings'][0]['uid']
    data['findings'][0] = {'uid': uid, 'id': 'TOASTER', 'mode': 'machine', 'title': 'Máquina sintética',
        'summary_md': 'Conclusión delimitada de máquina. `PRIVATE_MACHINE_COMMAND_0230`',
        'host': {'ip': 'PRIVATE_MACHINE_HOST_0230', 'name': 'PRIVATE_MACHINE_HOST_0230'},
        'phases': [{'name': 'Acceso', 'steps': [{'command': 'PRIVATE_MACHINE_PHASE_0230', 'text_md': 'Ejecución privada'}]}]}
    save(directory, data)
    options = {'profile': 'executive', 'finding_uids': [uid]}
    response = export_response(c, directory, options)
    assert response.status_code == 200, response.get_json()
    with zipfile.ZipFile(BytesIO(response.data)) as package:
        for name in ('informe.html', 'informe.docx', 'markdown.zip', 'informe.pdf'):
            text = all_texts(package.read(name), name)
            assert 'Conclusión delimitada de máquina.' in text, name
            assert all(needle not in text for needle in ('PRIVATE_MACHINE_COMMAND_0230', 'PRIVATE_MACHINE_HOST_0230', 'PRIVATE_MACHINE_PHASE_0230')), name
