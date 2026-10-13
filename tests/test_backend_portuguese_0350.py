"""Portuguese across request errors, immutable projections and private deliveries."""
import ast
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import csv
from io import StringIO
from pathlib import Path
from string import Formatter
import time

import pytest
import app as api
import delivery
import error_messages as messages
import insights
import readiness
import remediation_tasks as tasks
import report_compare
import retest_summary
import workflows
import validate
from _support import auth_client

ROOT = Path(__file__).resolve().parents[1]


def project():
    return workflows.normalize({'meta': {'lang': 'pt', 'report_title': 'Avaliação sintética — ação e proteção'},
        'report': {'sections': [{'key': 'findings'}]},
        'assets': [{'name': 'Servidor de conciliação', 'target': 'https://bank.example/ação', 'kind': 'server'}],
        'findings': [{'id': 'F1', 'title': 'Controle sintético, não comprovado', 'mode': 'vuln',
            'severity': 'high', 'description_md': 'Todo acesso exige autorização. Todo: evidência e contexto.',
            'impact_md': 'Hipótese a verificar.', 'remediation_md': 'Revisar o controle.',
            'status': 'reported_fixed', 'verification': 'unverified', 'owner': 'Equipe de proteção',
            'due_date': '2099-01-01'}], 'coverage': [{'test': 'Teste de segregação', 'status': 'pending'}]})


@pytest.fixture
def local(tmp_path, monkeypatch):
    projects = tmp_path / 'projects'; projects.mkdir()
    monkeypatch.setattr(api, 'PROJECTS', projects)
    monkeypatch.setitem(api.app.config, 'TESTING', True)
    monkeypatch.setitem(api.app.config, 'LIBRARY_PATH', str(tmp_path / 'findings.json'))
    monkeypatch.setitem(api.app.config, 'DESIGN_LIBRARY_PATH', str(tmp_path / 'designs.json'))
    return auth_client(api.app), projects


def test_portuguese_catalog_has_exact_field_parity_and_source_coverage():
    def fields(text):
        return sorted((key, spec, conv) for _, key, spec, conv in Formatter().parse(text) if key is not None)
    assert set(messages.CATALOG_PT) == set(messages.CATALOG)
    assert len(messages.CATALOG_PT) >= 765
    for source, translated in messages.CATALOG_PT.items():
        assert fields(source) == fields(translated), source
    for path in [*ROOT.glob('*.py'), *(ROOT / 'webapp').glob('*.py'), *(ROOT / 'exporters').glob('*.py')]:
        if path.name == 'error_messages.py':
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('message', 'backend_message'):
                source = node.args[0]
                assert isinstance(source, ast.Constant), (path, node.lineno)
                assert source.value in messages.CATALOG_PT or any(k.arg == 'pt' for k in node.keywords), (path, node.lineno, source.value)


@pytest.mark.parametrize('lang', ['pt', 'pt-BR', 'PT-br', ' pt '])
def test_error_language_alias_keeps_opaque_content_and_response_guards(local, lang):
    client, projects = local
    response = client.get('/api/projects/falta-evidencia', headers={'X-UI-Language': lang})
    assert response.status_code == 404
    assert response.get_json() == {'error': 'projeto não encontrado: falta-evidencia'}
    assert response.headers['Content-Language'] == 'pt-BR'
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert list(projects.iterdir()) == []
    assert messages.current_language() == 'es'


def test_api_validation_language_is_independent_of_document_and_never_rewrites_fields(local):
    client, _ = local
    data = project(); data['meta']['lang'] = 'es'
    data['findings'][0].update(id='falta evidencia {x} ação', severity='wrong')
    before = deepcopy(data)
    result = client.post('/api/validate', json=data, headers={'X-UI-Language': 'pt-BR'})
    assert result.status_code == 200
    assert any(row['message'] == "falta evidencia {x} ação: severidade inválida 'wrong'" for row in result.get_json()['issues'])
    assert data == before
    assert result.headers['Content-Language'] == 'pt-BR'


def test_concurrent_scopes_and_explicit_templates_do_not_translate_opaque_values():
    value = 'falta evidencia / Invalid text {p0} ação'
    def run(lang):
        with messages.language_scope(lang):
            return messages.message('Archivo no permitido en el respaldo: {p0}', p0=value)
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert list(pool.map(run, ['es', 'en', 'pt-BR'])) == [
            'Archivo no permitido en el respaldo: ' + value,
            'File is not allowed in the backup: ' + value,
            'Arquivo não permitido no backup: ' + value]
    assert messages.current_language() == 'es'
    with messages.language_scope('pt'):
        assert messages.message('Future detail: {value}', value=value) == 'Future detail: ' + value
        assert messages.message('Uno {value}', en='One {value}', pt='Um {value}', value=value) == 'Um ' + value


@pytest.mark.parametrize('lang', ['pt', 'pt-BR'])
def test_workflow_report_sections_and_tracking_are_portuguese_without_mutation(tmp_path, lang):
    data = project(); data['meta']['lang'] = lang; before = deepcopy(data)
    rendered = workflows.report_sections(data)
    assert [r['title'] for r in rendered] == ['Inventário de ativos', 'Cobertura e limitações', 'Acompanhamento de correções e reteste']
    assert 'Correção comunicada' in rendered[-1]['body']
    assert 'Não verificado' in rendered[-1]['body']
    reviewed = workflows.preflight(data, tmp_path, lang)
    assert any(row['message'].startswith('Teste pendente ou bloqueado: ') for row in reviewed)
    assert not any('Texto incompleto:' in row['message'] for row in reviewed)
    assert next(row for row in reviewed if row['path'].startswith('coverage'))['help'].startswith('Documente se o teste')
    assert data == before


@pytest.mark.parametrize('text', ['Todo acesso exige autorização.', 'todo o escopo', 'Todo: testes e registros.'])
@pytest.mark.parametrize('ui', ['es', 'en', 'pt'])
def test_portuguese_todo_is_an_ordinary_word(tmp_path, text, ui):
    data = project(); data['findings'][0]['description_md'] = text
    assert not any(r['path'].endswith('.description_md') and 'TODO' in r['message'] for r in workflows.review(data, tmp_path, ui))


@pytest.mark.parametrize('marker', ['TODO', 'TBD', 'FIXME', 'Pendente de preenchimento'])
def test_portuguese_explicit_editorial_markers_still_warn(tmp_path, marker):
    data = project(); data['findings'][0]['description_md'] = marker
    rows = workflows.review(data, tmp_path, 'pt')
    assert any(r['message'] == 'Texto incompleto: ' + marker for r in rows)


def test_readiness_and_retest_are_localized_read_only_facts(tmp_path):
    data = project()
    for index in range(2, 7):
        finding = deepcopy(data['findings'][0]); finding.update(id=f'F{index}', uid=workflows.new_uid())
        data['findings'].append(finding)
    before = deepcopy(data)
    matrix = retest_summary.summarize(data, 'pt-BR')
    assert len(matrix['rows']) == 6
    assert all(row['status_label'] == 'Correção comunicada' for row in matrix['rows'])
    assert matrix['result_labels']['not_run'] == 'Sem observações registradas'
    assert matrix['coverage']['labels']['pending'] == 'Pendente'
    assert matrix['technical_validation'] is False
    ready = readiness.checklist(data, tmp_path, workflows.preflight(data, tmp_path, 'pt'), 'pt-BR')
    assert ready['checks'][0]['title'] == 'Revisão do relatório'
    assert ready['checks'][-1]['title'] == 'Revisão humana'
    assert 'erros' in ready['checks'][0]['detail']
    assert data == before


def test_task_csv_card_and_comparison_use_localized_chrome_keep_authored_values():
    data = project(); before = deepcopy(data)
    fields, lang = tasks.options({'fields': ['id', 'finding_uid', 'title', 'status'], 'lang': 'pt-BR', 'ack_private': True})
    assert lang == 'pt'
    rows = tasks.rows(data, fields, lang)
    csv_rows = list(csv.reader(StringIO(tasks.csv_bytes(rows, fields, lang).decode('utf-8-sig'))))
    assert csv_rows[0] == ['ID do achado', 'Referência permanente', 'Título', 'Estado registrado']
    assert csv_rows[1][-1] == 'Correção comunicada'
    html = tasks.card_html(rows[0], fields, 'pt-BR').decode()
    assert '<html lang="pt-BR">' in html and 'Tarefa de remediação' in html
    assert data['findings'][0]['title'] in html
    changed = deepcopy(data); changed['findings'][0]['title'] = 'Novo título sintético'
    compared = report_compare.render(data, changed, {}, {}, 'antes', 'depois', 'pt-BR')
    assert '<html lang="pt-BR">' in compared and 'Comparação de entregas' in compared
    assert 'Referência técnica' in compared and 'Novo' in compared
    assert data == before


def test_delivery_public_warnings_localize_without_private_details():
    source = [{'level': 'warning', 'path': 'findings[0].title', 'message': 'SECRET', 'help': 'PRIVATE'},
              {'level': 'warning', 'path': 'unknown.private.field', 'message': 'SECRET'}]
    rows = delivery.public_warnings(source, 'pt-BR')
    assert rows[0]['message'] == 'Aviso de achado revisado'
    assert rows[1]['message'] == 'Aviso privado revisado'
    assert all('projeto privado' in row['details'] for row in rows)
    assert 'SECRET' not in str(rows) and 'PRIVATE' not in str(rows)


def test_editorial_portuguese_claims_are_advisory_and_preserve_text():
    data = project(); data['findings'][0]['description_md'] = 'Acesso total a todos os documentos; completamente seguro e sem vulnerabilidades; corrigido.'
    before = deepcopy(data); rows = insights.editorial(data, 'pt-BR')
    assert {'scope_absolute', 'security_absolute', 'fixed_without_retest'} <= {row['rule'] for row in rows}
    assert all(row['technical_verification'] is False and 'Revise o contexto' in row['help'] for row in rows)
    assert data == before


def test_portuguese_worker_error_keeps_submission_language():
    from export_jobs import ExportQueue
    queue = ExportQueue(timeout=20)
    def prepare(target):
        target.mkdir(); (target / 'engagement.yaml').write_text('meta: {lang: en, report_title: authored}\nfindings: []\n')
        return {}
    try:
        with messages.language_scope('pt-BR'):
            record = queue.submit('owner', prepare, dict(kind='export', formats=['not-a-format'], label='falta evidencia', revision='saved', filename='literal.pdf'))
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with messages.language_scope('en'):
                result = queue.status('owner', record['id'])
            if result['stage'] in {'done', 'error', 'cancelled'}:
                break
            time.sleep(.05)
        assert result['stage'] == 'error', result
        assert 'Formato incompatível' in result['error']
        assert result['label'] == 'falta evidencia' and result['filename'] == 'literal.pdf'
        assert messages.current_language() == 'es'
    finally:
        queue.close()


def test_portuguese_csv_intake_recognizes_headers_and_severity_without_translating_evidence():
    import finding_imports
    data = project(); before = deepcopy(data)
    text = 'Título;Severidade;Alvo;Descrição;Remediação;Referências\nControle de sessão;Média;https://example.test/ação;Evidência literal {x};Corrigir autorização;https://example.test/ref\n'
    with messages.language_scope('pt'):
        result = finding_imports.preview({'format': 'csv', 'text': text}, data)
    finding = result['rows'][0]['finding']
    assert finding['severity'] == 'medium'
    assert finding['description_md'] == 'Evidência literal {x}'
    assert finding['remediation_md'] == 'Corrigir autorização'
    assert result['rows'][0]['errors'] == []
    assert data == before


def test_portuguese_import_errors_and_assistant_warning_use_request_language(local):
    import finding_imports
    client, _ = local
    with messages.language_scope('pt'):
        result = finding_imports.preview({'format': 'csv', 'text': 'title,severity\n,invalid\n'}, project())
    assert result['rows'][0]['errors'] == ['Título ausente', 'Severidade desconhecida']
    response = client.get('/api/assistant/capabilities', headers={'X-UI-Language': 'pt'})
    assert response.status_code == 200
    assert response.get_json()['cloud_warning'].startswith('Desative a nuvem')
    assert response.get_json()['auto_send'] is False


def test_portuguese_nmap_generated_notes_keep_native_observations():
    import finding_imports
    data = project(); before = deepcopy(data)
    xml = '<nmaprun><host><status state="up"/><address addr="192.0.2.8" addrtype="ipv4"/><ports><port portid="443" protocol="tcp"><state state="open"/><service name="https" product="Produto literal"/></port></ports></host></nmaprun>'
    with messages.language_scope('pt'):
        preview = finding_imports.preview({'format': 'nmap', 'text': xml}, data)
        updated, count = finding_imports.apply({'format': 'nmap', 'text': xml, 'selected': [0]}, data)
    assert preview['notice'].startswith('Inventário aguardando revisão')
    assert count == 1 and updated['coverage'][-1]['test'] == 'Nmap: inventário de serviços'
    assert 'Endereços: 192.0.2.8' in updated['coverage'][-1]['notes']
    assert 'Produto literal' in updated['coverage'][-1]['notes']
    assert updated['coverage'][-1]['status'] == 'pending' and data == before


def test_portuguese_audience_omission_labels_are_localized_without_mutation():
    import audience
    data = project(); data['findings'][0]['description_md'] = 'Contexto https://private.invalid/secret e /home/private/token.'
    before = deepcopy(data)
    output, _ = audience.project(data, {'profile': 'executive', 'finding_uids': [data['findings'][0]['uid']]})
    assert output['meta']['lang'] == 'pt'
    assert output['meta']['report_title'] == 'Resumo executivo'
    description = output['findings'][0]['description_md']
    assert 'detalhe técnico omitido' in description and 'caminho omitido' in description
    assert 'private.invalid' not in description and '/home/private' not in description
    assert data == before


def test_portuguese_service_schema_errors_and_all_validation_catalogs():
    data = project(); data['coverage'][0]['services'] = [{'port': -1, 'protocol': 'invalid'}]
    with messages.language_scope('pt'):
        problems = workflows.structure_errors(data)
    assert any('porta inválida' in text for _, text in problems)
    assert any('protocolo inválido' in text for _, text in problems)
    for variants in validate._MSG.values():
        assert set(variants) == {'es', 'en', 'pt'}
        fields = lambda text: sorted((k, spec, conv) for _, k, spec, conv in Formatter().parse(text) if k is not None)
        assert fields(variants['es']) == fields(variants['pt'])


def test_portuguese_project_creation_preserves_selected_report_language(local):
    client, _ = local
    result = client.post('/api/projects', json={'slug': 'portugues', 'model': 'corporativo-pt'}, headers={'X-UI-Language': 'en'})
    assert result.status_code == 200
    saved = client.get('/api/projects/portugues').get_json()
    assert saved['meta']['lang'] == 'pt'
    assert saved['meta']['report_title'] == 'Novo relatório'
    assert saved['meta']['report_subtitle']


@pytest.mark.parametrize('method,path,expected,status', [
    ('get', '/api/not-a-real-route', 'Recurso não encontrado', 404),
    ('delete', '/api/session', 'Método não permitido', 405),
    ('get', '/api/privacy/not-a-route', 'Recurso não encontrado', 404)])
def test_framework_default_errors_are_portuguese(local, method, path, expected, status):
    client, _ = local
    result = getattr(client, method)(path, headers={'X-UI-Language': 'pt-BR'})
    assert result.status_code == status
    assert result.get_json()['error'] == expected
    assert result.headers['Content-Language'] == 'pt-BR'


def test_body_limit_default_error_localizes_without_exposing_request(local, monkeypatch):
    client, _ = local
    monkeypatch.setitem(api.app.config, 'MAX_CONTENT_LENGTH', 3)
    result = client.post('/api/projects', data='{"private":"literal"}', content_type='application/json', headers={'X-UI-Language': 'pt'})
    assert result.status_code == 413 and result.get_json() == {'error': 'Solicitação grande demais'}
    assert 'private' not in result.get_data(as_text=True)
