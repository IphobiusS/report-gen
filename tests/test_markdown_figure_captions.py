"""Valid empty and multiline captions survive portable Markdown export."""
from hashlib import sha256
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import html
import markdown
from PIL import Image
import pytest

import delivery
import export
import workflows
from exporters.markdown import _figure_caption, parse_exported
from wizard import dump_yaml


LONG = '\n'.join('' if index in (12, 13, 41) else f'Caption line {index:02}: café / literal * [x] & value'
                 for index in range(60))


def project(tmp_path, language, context, caption):
    root = tmp_path / 'source'
    root.mkdir()
    Image.new('RGB', (120, 180), '#327391').save(root / 'figure.png')
    figure = {'figure': {'src': 'figure.png', 'caption': caption}}
    finding = {'id': 'CAP-01', 'title': 'Synthetic caption check', 'mode': 'vuln',
               'severity': 'info', 'description_md': 'Unverified synthetic record.', 'walkthrough': [figure]}
    if context == 'machine':
        finding.update(mode='machine', host={'name': 'Synthetic host'}, phases=[{'name': 'Capture', 'steps': [figure]}])
        finding.pop('walkthrough')
    data = {'meta': {'report_title': 'Caption contract', 'lang': language, 'theme': 'corporativo'},
            'findings': [finding], 'report': {'sections': [{'key': 'findings'}]}}
    workflows.normalize(data)
    if context == 'legacy': data.pop('report', None)
    dump_yaml(data, root / 'engagement.yaml')
    hashes = {p.name: sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
    capture = delivery.capture(root, tmp_path / 'snapshot')
    output = export.export(root / 'engagement.yaml', 'md', tmp_path / 'report.zip')
    assert hashes == {p.name: sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
    return output, capture


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('context', ['sections', 'legacy', 'machine'])
@pytest.mark.parametrize('caption', ['', '   ', '  Plain *literal* [caption] & value  ', LONG])
def test_empty_whitespace_and_multiline_captions_pass_real_contract(tmp_path, language, context, caption):
    output, capture = project(tmp_path, language, context, caption)
    checks = delivery.inspect_export(output, 'md', capture)
    assert checks['images_verified'] == checks['evidence_associations_checked'] == 1
    with ZipFile(output) as package:
        source = package.read('report.md').decode()
    tree = parse_exported(source)
    label = 'Figura' if language == 'es' else 'Figure'
    paragraph = next(p for p in tree.xpath('.//p') if p.text_content().startswith(label + ' 1.'))
    assert paragraph.find('em') is not None
    assert len(paragraph.xpath('.//br')) == caption.count('\n')
    assert paragraph.text_content().strip().startswith(label + ' 1.')
    if caption == '': assert paragraph.text_content().strip() == label + ' 1.'


@pytest.mark.parametrize('caption', ['', '   ', LONG, '\nFirst\n\nLast\n'])
def test_standard_markdown_without_nl2br_preserves_each_caption_line(caption):
    source = _figure_caption('Figure', 1, caption)
    tree = html.fragment_fromstring(markdown.markdown(source), create_parent='main')
    assert len(tree) == 1 and tree[0].tag == 'p'
    assert tree[0].find('em') is not None
    breaks = tree.xpath('.//br')
    assert len(breaks) == caption.count('\n')
    # HTML serializer newlines are not visual breaks. Divide only at br and
    # compare every line separately so dropped/merged empty lines cannot pass.
    parts = ['']
    def visit(node):
        if node.tag == 'br': parts.append('')
        if node.text: parts[-1] += node.text
        for child in node:
            visit(child)
            if child.tail: parts[-1] += child.tail
    visit(tree[0])
    assert [part.strip() for part in parts] == [part.strip() for part in ('Figure 1. ' + caption).split('\n')]


@pytest.mark.parametrize('mutation', ['caption', 'image', 'paragraph'])
def test_caption_fix_does_not_accept_altered_or_detached_content(tmp_path, mutation):
    output, capture = project(tmp_path, 'en', 'sections', 'Original caption literal')
    delivery.inspect_export(output, 'md', capture)
    with ZipFile(output) as package:
        files = {name: package.read(name) for name in package.namelist()}
    source = files['report.md'].decode()
    original = source
    if mutation == 'caption': source = source.replace('Original caption literal', 'Changed caption')
    elif mutation == 'image': source = source.replace('![Original caption literal](figure.png)', '')
    else: source = source.replace('*Figure 1. Original caption literal*', '')
    assert source != original, 'Negative control must actually change the exported Markdown'
    files['report.md'] = source.encode()
    changed = tmp_path / 'changed.zip'
    with ZipFile(changed, 'w', ZIP_DEFLATED) as package:
        for name, value in files.items(): package.writestr(name, value)
    with pytest.raises(ValueError): delivery.inspect_export(changed, 'md', capture)
