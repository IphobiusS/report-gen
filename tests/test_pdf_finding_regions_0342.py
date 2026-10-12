"""A TOC/summary or another finding cannot supply missing finding text."""
from copy import deepcopy

from lxml import html
import pytest

import engine
import export_contract as contract


def source(language='en', *, legacy=False, theme='corporativo'):
    data = {
        'meta': {'lang': language, 'report_title': 'Independent regional check', 'theme': theme},
        'findings': [
            {'id': 'F01', 'title': 'Repeated approval heading', 'severity': 'High',
             'description_md': 'Owner one narrative.', 'impact_md': 'Impact owner one.'},
            {'id': 'F02', 'title': 'Repeated approval heading', 'severity': 'Low',
             'description_md': 'Owner two narrative.', 'impact_md': 'Impact owner two.'},
        ],
    }
    if not legacy:
        data['report'] = {'sections': [{'key': 'findings_summary'}, {'key': 'findings'},
                                       {'key': 'strategic_recommendations'}]}
    return data


def markup(data, tmp_path):
    return engine.render_html(engine.build_env(), data, tmp_path, {}, False,
                              engine.load_lang(data['meta']['lang']))


def render(markup, tmp_path, name):
    path = tmp_path / (name + '.pdf')
    engine.render_pdf_weasyprint(markup, path, tmp_path)
    return path


@pytest.mark.parametrize('language', ['en', 'es'])
@pytest.mark.parametrize('legacy', [False, True])
def test_summary_and_toc_cannot_replace_finding_heading(tmp_path, language, legacy):
    original = markup(source(language, legacy=legacy), tmp_path)
    expected = contract.from_tree(html.document_fromstring(original))
    result = contract.inspect(render(original, tmp_path, 'original'), 'pdf', expected)
    assert result['pdf_finding_regions_checked'] == 2
    assert result['finding_association_checked'] is False
    assert result['verification_scope'] == 'text_presence_only'
    tree = html.document_fromstring(original)
    tree.get_element_by_id('F01').xpath('.//*[@class="f-title"]')[0].drop_tree()
    altered = html.tostring(tree, encoding='unicode')
    # The global copies are deliberately intact; this used to pass.
    assert altered.count('Repeated approval heading') >= 3
    with pytest.raises(ValueError, match='regi[oó]n|region'):
        contract.inspect(render(altered, tmp_path, 'removed-title'), 'pdf', expected)


@pytest.mark.parametrize('theme', ['serio', 'corporativo', 'htb', 'offsec', 'ejecutivo', 'laboratorio'])
def test_legacy_regions_work_with_every_theme(tmp_path, theme):
    original = markup(source(legacy=True, theme=theme), tmp_path)
    expected = contract.from_tree(html.document_fromstring(original))
    result = contract.inspect(render(original, tmp_path, theme), 'pdf', expected)
    assert result['pdf_finding_regions_checked'] == 2


@pytest.mark.parametrize('kind,one,two', [
    ('paragraph', 'Owner one narrative.', 'Owner two narrative.'),
    ('heading', '### Authored heading one', '### Authored heading two'),
    ('table', '| Control | Result |\n| --- | --- |\n| First | Approved |',
     '| Control | Result |\n| --- | --- |\n| Second | Denied |'),
    ('list', '- Control one\n- Control alpha', '- Control two\n- Control beta'),
    ('code', '```text\nOWNER_ONE=1\n```', '```text\nOWNER_TWO=2\n```'),
])
def test_text_moved_to_another_finding_is_rejected(tmp_path, kind, one, two):
    data = source()
    data['findings'][0]['description_md'] = one
    data['findings'][1]['description_md'] = two
    original = markup(data, tmp_path)
    expected = contract.from_tree(html.document_fromstring(original))
    contract.inspect(render(original, tmp_path, 'original'), 'pdf', expected)
    altered = deepcopy(data)
    altered['findings'][0]['description_md'] = two
    altered['findings'][1]['description_md'] = one
    with pytest.raises(ValueError):
        contract.inspect(render(markup(altered, tmp_path), tmp_path, kind), 'pdf', expected)


def test_next_nonfinding_section_cannot_supply_missing_last_finding_title(tmp_path):
    original = markup(source(), tmp_path)
    expected = contract.from_tree(html.document_fromstring(original))
    assert expected['pdf_regions'][-1]['end'] == 'strategic_recommendations'
    tree = html.document_fromstring(original)
    title = tree.get_element_by_id('F02').xpath('.//*[@class="f-title"]')[0]
    tree.get_element_by_id('strategic_recommendations').append(title)
    with pytest.raises(ValueError, match='regi[oó]n|region'):
        contract.inspect(render(html.tostring(tree, encoding='unicode'), tmp_path, 'moved'), 'pdf', expected)


@pytest.mark.parametrize('mutation', ['missing', 'reversed'])
def test_missing_or_reordered_finding_destinations_fail_closed(tmp_path, mutation):
    original = markup(source(), tmp_path)
    expected = contract.from_tree(html.document_fromstring(original))
    tree = html.document_fromstring(original)
    first, second = (tree.get_element_by_id(key) for key in ('F01', 'F02'))
    if mutation == 'missing':
        first.attrib.pop('id')
    else:
        first.addprevious(second)
    with pytest.raises(ValueError, match='[Rr]egi[oó]n|region'):
        contract.inspect(render(html.tostring(tree, encoding='unicode'), tmp_path, mutation), 'pdf', expected)


def test_multpage_region_retains_wrapped_urls_and_code(tmp_path):
    data = source()
    url = 'https://bank.example/' + '0123456789abcdef' * 35 + '?state=pending'
    data['findings'][0]['description_md'] = (
        '\n\n'.join(f'Control {n}: review this independent line before approval.' for n in range(100))
        + '\n\n' + url + '\n\n```text\nKEY=' + '0123456789abcdef' * 12 + '\n```')
    original = markup(data, tmp_path)
    expected = contract.from_tree(html.document_fromstring(original))
    result = contract.inspect(render(original, tmp_path, 'multipage'), 'pdf', expected)
    assert result['pdf_finding_regions_checked'] == 2


def test_old_and_noncanonical_contracts_keep_explicit_global_scope(tmp_path):
    original = markup(source(), tmp_path)
    expected = contract.from_tree(html.document_fromstring(original))
    expected.pop('pdf_regions')
    result = contract.inspect(render(original, tmp_path, 'old-contract'), 'pdf', expected)
    assert result['pdf_finding_regions_checked'] == 0
    assert result['finding_association_checked'] is False
    noncanonical = html.document_fromstring('<html><body><section class="finding" id="F01">'
                                            '<h2 class="f-title">Freeform title</h2></section></body></html>')
    assert contract.from_tree(noncanonical)['pdf_regions'] == []


def test_pdf_name_destination_spelling_is_supported(tmp_path):
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import TextStringObject
    original = markup(source(), tmp_path)
    expected = contract.from_tree(html.document_fromstring(original))
    path = render(original, tmp_path, 'string-destinations')
    writer = PdfWriter(clone_from=PdfReader(path))
    names = writer.root_object['/Names']['/Dests']['/Names']
    for index in range(0, len(names), 2):
        names[index] = TextStringObject('/' + str(names[index]))
    changed = tmp_path / 'name-destinations.pdf'
    writer.write(changed)
    result = contract.inspect(changed, 'pdf', expected)
    assert result['pdf_finding_regions_checked'] == 2


@pytest.mark.parametrize('mutation', ['unused-form', 'executed-form', 'changed-content'])
def test_unused_form_resources_do_not_invalidate_real_regional_hyphens(tmp_path, mutation):
    from pypdf import PdfWriter
    from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject
    import pypdfium2
    from weasyprint import HTML

    original = ('<html lang="en"><body><section class="frontsec" id="start">Start</section>'
                '<section class="finding" id="F01"><h2 class="f-title">First heading</h2>'
                '<p style="width:65px;font-family:DejaVu Sans;font-size:12px">'
                'recovery-assurance</p></section></body></html>')
    expected = contract.from_tree(html.document_fromstring(original))
    observed = original.replace('assurance', 'assurancX') if mutation == 'changed-content' else original
    plain = tmp_path / 'plain.pdf'
    HTML(string=observed).write_pdf(plain)
    writer = PdfWriter(clone_from=plain)
    page = writer.pages[0]
    form = DecodedStreamObject()
    form.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Form'),
                 NameObject('/BBox'): ArrayObject(page.mediabox),
                 NameObject('/Resources'): DictionaryObject({NameObject('/Font'): page['/Resources']['/Font']})})
    form.set_data(page.get_contents().get_data())
    page['/Resources'][NameObject('/XObject')] = DictionaryObject({NameObject('/SharedForm'): writer._add_object(form)})
    if mutation == 'executed-form':
        stream = DecodedStreamObject()
        stream.set_data(page.get_contents().get_data() + b'\n/SharedForm Do\n')
        page[NameObject('/Contents')] = writer._add_object(stream)
    target = tmp_path / (mutation + '.pdf')
    writer.write(target)
    with pypdfium2.PdfDocument(target) as document:
        pdfpage = document[0]
        textpage = pdfpage.get_textpage()
        try:
            assert '\x02' in textpage.get_text_bounded(errors='strict')
        finally:
            textpage.close()
            pdfpage.close()
    if mutation == 'unused-form':
        assert contract.inspect(target, 'pdf', expected)['pdf_finding_regions_checked'] == 1
    else:
        with pytest.raises(ValueError):
            contract.inspect(target, 'pdf', expected)
