"""Generated step leads survive format-specific heading/paragraph boundaries."""
from copy import deepcopy

from lxml import html
import pytest

import delivery
import export_semantics
from test_release_0211 import edit_zip
from test_release_0212 import fixture, prepare


@pytest.mark.parametrize('fmt', ['html', 'md', 'docx'])
@pytest.mark.parametrize('length', [12, 197, 200, 260])
def test_short_step_prose_retains_inline_lead_evidence_context(tmp_path, fmt, length):
    data = fixture(tmp_path)
    data['meta']['lang'] = 'en'
    data['findings'][0]['walkthrough'] = [{
        'lead': 'Evaluate the control boundary', 'text_md': 'x' * length,
        'figure': {'src': 'img/e1.png', 'caption': 'Short control evidence'},
    }]
    data['findings'][1]['walkthrough'] = []
    out, captured = prepare(tmp_path, fmt, data)
    checked = delivery.inspect_export(out, fmt, captured)
    assert checked['evidence_associations_checked'] == 1
    expected = next(s for s in captured['contract']['scopes'] if s['id'] == 'F01')
    suffix = expected['semantic']['images'][0]['preceding_text']
    assert suffix == ('Evaluate the control boundary ' + 'x' * length)[-200:]


@pytest.mark.parametrize('level', range(1, 7))
def test_all_html_heading_levels_start_the_same_visible_context(level):
    tree = html.fromstring('<section><p>Unrelated preceding paragraph.</p>'
                           f'<h{level}>Control boundary</h{level}>'
                           '<figure><img src="proof.png"><figcaption>Evidence</figcaption></figure></section>')
    expected = export_semantics.dom(tree, lambda _src: 'synthetic-digest')
    actual = export_semantics.dom(deepcopy(tree), lambda _src: 'synthetic-digest', markdown=True)
    assert expected['images'][0]['preceding_text'] == 'Control boundary'
    scope = {'id': 'F01', 'semantic': expected}
    export_semantics.check(scope, actual, 'md')


@pytest.mark.parametrize('mutation', ['move-image', 'remove-lead', 'change-prose'])
def test_markdown_context_still_rejects_real_placement_or_text_changes(tmp_path, mutation):
    data = fixture(tmp_path)
    data['findings'][0]['walkthrough'] = [
        {'lead': 'Boundary alpha', 'text_md': 'Shared short prose.',
         'figure': {'src': 'img/e1.png', 'caption': 'Evidence alpha'}},
        {'lead': 'Boundary beta', 'text_md': 'Shared short prose.',
         'figure': {'src': 'img/e2.png', 'caption': 'Evidence beta'}},
    ]
    data['findings'][1]['walkthrough'] = []
    out, captured = prepare(tmp_path, 'md', data)
    delivery.inspect_export(out, 'md', captured)

    def change(blob):
        text = blob.decode()
        if mutation == 'move-image':
            start = text.index('![Evidence alpha]')
            end = text.index('\n', start)
            image = text[start:end]
            text = text[:start] + text[end:]
            text = text.replace('![Evidence beta]', image + '\n\n![Evidence beta]', 1)
        elif mutation == 'remove-lead':
            text = text.replace('Boundary alpha', 'Removed lead', 1)
        else:
            text = text.replace('Shared short prose.', 'Different short prose.', 1)
        return text.encode()

    edit_zip(out, 'report.md', change)
    # The generated lead is now an explicit paragraph, so altered prose is
    # rejected by the content contract before evidence association is checked.
    # Moving an unchanged image must still fail the association contract.
    diagnosis = ('evidencia|Evidence' if mutation == 'move-image'
                 else 'Párrafo.*ausente o alterado|Missing or changed paragraph')
    with pytest.raises(ValueError, match=diagnosis):
        delivery.inspect_export(out, 'md', captured)
