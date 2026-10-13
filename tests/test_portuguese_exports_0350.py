"""Third-language report contracts, independent from interface language."""
from copy import deepcopy
from pathlib import Path
import re
import zipfile

from lxml import etree, html
import pytest

import delivery
import engine
import export
import export_contract
from error_messages import language_scope
from exporters.machine_graph import WORDS, build as machine_graph
from wizard import dump_yaml

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://audit.example.invalid/controle-de-acesso/' + 'identificador_0350_' * 8 + '?acao=remediacao&versao=3#evidencia'


def leaves(value, prefix=()):
    if isinstance(value, dict):
        return {path: leaf for key, child in value.items() for path, leaf in leaves(child, (*prefix, key)).items()}
    if isinstance(value, list):
        return {path: leaf for index, child in enumerate(value) for path, leaf in leaves(child, (*prefix, index)).items()}
    return {prefix: value}


def document(language='pt'):
    return {'meta': {'lang': language, 'report_title': 'Avaliação de segurança: conciliação e autorização',
                     'client': 'Banco Sintético Açor', 'assessor': 'Equipe de exercício', 'theme': 'corporativo'},
            'report': {'sections': [{'key': 'findings_summary'}, {'key': 'findings'}, {'key': 'appendix'}]},
            'findings': [
                {'id': 'ACH-01', 'mode': 'vuln', 'title': 'Hipótese não verificada de autorização inconsistente',
                 'severity': 'high', 'description_md': 'Exercício fictício; nenhuma intrusão foi executada.\n\n'
                    '| Operação | Observação |\n|---|---|\n| Conciliação | Ação pendente |\n\n'
                    + f'Referência literal: [{URL}]({URL})\n\n1000000. Verificar a autorização.\n1000001. Registrar o resultado.',
                 'remediation_md': 'Revisar a autorização e preservar os registros.'},
                {'id': 'ACH-02', 'mode': 'vuln', 'title': 'Avaliação de criptografia ainda pendente',
                 'description_md': 'Não foi coletada evidência suficiente para atribuir severidade.'},
                {'id': 'MAQ-01', 'mode': 'machine', 'title': 'Servidor de conciliação sintético',
                 'host': {'name': 'SERVIDOR-AÇOR', 'ip': '192.0.2.50'},
                 'phases': [{'name': 'Revisão documental', 'steps': [{'lead': 'Solicitar registros',
                        'text_md': 'Passo planejado; não executado.'}]}],
                 'proof': [{'name': 'referencia-ficticia.txt', 'value': 'SYNTHETIC-NOT-EVIDENCE'}]}
            ]}


@pytest.mark.parametrize('lang', ['es', 'en', 'pt'])
def test_report_catalogs_have_identical_keys_placeholders_and_nonempty_strings(lang):
    base = leaves(engine.load_lang('en'))
    actual = leaves(engine.load_lang(lang))
    assert actual.keys() == base.keys()
    for path, value in actual.items():
        assert isinstance(value, str) and value.strip(), path
        assert sorted(re.findall(r'\{[^{}]+\}', value)) == sorted(re.findall(r'\{[^{}]+\}', base[path])), path
    assert WORDS[lang].keys() == WORDS['en'].keys()


@pytest.mark.parametrize('lang', ['pt', 'pt-BR', 'PT-br'])
def test_report_locale_alias_preserves_author_data_and_sets_portuguese_tag(lang, tmp_path):
    import publication
    data = document(lang); before = deepcopy(data)
    tree = publication.render(data, tmp_path)
    assert tree.get('lang') == 'pt-BR'
    assert engine.report_language(data) == 'pt'
    assert 'Resumo dos achados' in tree.text_content()
    assert 'Avaliação pendente' in tree.text_content()
    assert 'Arquivo de evidência no alvo' in tree.text_content()
    assert data == before


@pytest.mark.parametrize('fmt', ['pdf', 'docx', 'md', 'html'])
@pytest.mark.parametrize('lang', ['pt', 'pt-BR'])
def test_four_exports_keep_portuguese_accented_text_long_url_and_inspection(tmp_path, lang, fmt):
    data = document(lang)
    source = tmp_path / 'engagement.yaml'
    dump_yaml(data, source)
    original = source.read_bytes()
    # Backend messages follow English, while the authored report remains PT.
    with language_scope('en'):
        captured = delivery.capture(tmp_path, tmp_path / 'capture')
        artifact = export.export(source, fmt, tmp_path / ('relatorio.' + ('zip' if fmt == 'md' else fmt)))
        delivery.inspect_export(artifact, fmt, captured)
    text = (html.document_fromstring(artifact.read_text()).text_content() if fmt == 'html'
            else export_contract.profile(artifact, fmt)['text'])
    for expected in ['Resumo dos achados', 'Avaliação pendente',
                     'Remediação', 'Arquivo de evidência no alvo', 'Conciliação', 'Ação pendente']:
        assert expected in text
    assert source.read_bytes() == original
    if fmt == 'pdf':
        assert 'Percurso documentado' in text
        assert 'ordem de documentação' in text
    elif fmt == 'html':
        tree = html.document_fromstring(artifact.read_text())
        assert tree.get('lang') == 'pt-BR'
        assert tree.xpath('//nav/@aria-label') == ['Leitura do relatório']
        assert tree.xpath('//a[@href=$url]', url=URL)
        assert 'Tabela de dados' in ' '.join(tree.xpath('//*[@class="report-table-region"]/@aria-label'))
        assert all('Role horizontalmente' in hint for hint in tree.xpath('//*[@data-scroll-hint]/@data-scroll-hint'))
        assert 'Relatório completo' in tree.text_content()
        assert 'Scroll horizontally' not in artifact.read_text()
    elif fmt == 'docx':
        with zipfile.ZipFile(artifact) as package:
            core = etree.fromstring(package.read('docProps/core.xml'))
            assert core.xpath('string(*[local-name()="language"])') == 'pt-BR'
            styles = etree.fromstring(package.read('word/styles.xml'))
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            assert styles.xpath('//w:docDefaults/w:rPrDefault/w:rPr/w:lang/@w:val', namespaces=ns) == ['pt-BR']
            document_xml = etree.fromstring(package.read('word/document.xml'))
            assert document_xml.xpath('//w:r[w:rPr/w:lang[@w:val="zxx-ZZ-x-rgwrap"]]', namespaces=ns)
            rels = etree.fromstring(package.read('word/_rels/document.xml.rels'))
            assert URL in rels.xpath('/*/*/@Target')
    elif fmt == 'md':
        with zipfile.ZipFile(artifact) as package:
            markdown = package.read('report.md').decode()
            assert URL in markdown
            assert 'Avaliação de segurança' in markdown


def test_machine_diagram_and_text_alternative_are_portuguese_without_translating_source():
    finding = document()['findings'][-1]
    before = deepcopy(finding)
    graph = machine_graph(finding, 1, 'pt-BR')
    assert graph['words']['title'] == 'Percurso documentado'
    assert 'ordem de documentação' in graph['words']['scope']
    assert 'Percurso documentado' in str(graph['chunks'][0]['svg'])
    assert graph['nodes'][0]['name'] == 'Revisão documental'
    assert finding == before


def test_registry_and_wizard_offer_portuguese_without_overwriting_existing_language():
    import export_formats
    import wizard
    assert all(row['label_pt'] for row in export_formats.catalog())
    assert len([key for key in wizard.MODELS if key.endswith('-pt')]) == 6
    assert all(model['lang'] == 'pt' for key, model in wizard.MODELS.items() if key.endswith('-pt'))
    assert wizard.MODELS['corporativo-en']['lang'] == 'en'
    before = wizard.UI_LANGUAGE
    try:
        wizard.UI_LANGUAGE = 'pt'
        assert wizard.tr('Titulo del informe') == 'Título do relatório'
        assert wizard.tr('Fase: {name}', name='Private untouched English source') == 'Fase: Private untouched English source'
        wizard.UI_LANGUAGE = 'en'
        assert wizard.tr('Titulo del informe') == 'Report title'
    finally:
        wizard.UI_LANGUAGE = before


@pytest.mark.parametrize('lang', ['es', 'en', 'pt'])
def test_section_based_markdown_keeps_appendix_intro_in_all_languages(tmp_path, lang):
    data = document(lang)
    source = tmp_path / 'engagement.yaml'
    dump_yaml(data, source)
    captured = delivery.capture(tmp_path, tmp_path / 'capture')
    artifact = export.export(source, 'md', tmp_path / 'appendix.zip')
    delivery.inspect_export(artifact, 'md', captured)
    with zipfile.ZipFile(artifact) as package:
        assert engine.load_lang(lang)['appendix_intro'] in package.read('report.md').decode()


@pytest.mark.parametrize('invalid', ['fr', 'pt-PT', 'unsupported'])
def test_unknown_report_language_does_not_silently_fall_back(invalid, tmp_path):
    import publication
    data = document(invalid)
    with pytest.raises(ValueError):
        publication.render(data, tmp_path)


def test_wizard_static_prompts_have_explicit_english_and_portuguese():
    import ast
    import wizard
    tree = ast.parse((ROOT / 'wizard.py').read_text())
    prompt_functions = {'ask', 'ask_block', 'ask_choice', 'section'}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in prompt_functions and node.args
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            assert node.args[0].value in wizard.UI_TEXT, node.args[0].value
    for source, translations in wizard.UI_TEXT.items():
        assert len(translations) == 2
        for value in translations:
            assert value
            assert sorted(re.findall(r'\{[^{}]+\}', source)) == sorted(re.findall(r'\{[^{}]+\}', value))


def test_portuguese_inspection_error_uses_localized_generated_scope_but_keeps_authored_ids():
    with language_scope('pt'):
        with pytest.raises(ValueError, match='relatório'):
            export_contract._paragraphs(['missing'], [], '')
        with pytest.raises(ValueError, match='PRIVATE_UNCHANGED_ID'):
            export_contract._paragraphs(['missing'], [], 'PRIVATE_UNCHANGED_ID')
