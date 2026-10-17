"""Legacy contacts remain an internal destination before people are entered."""
from copy import deepcopy
import zipfile

from lxml import etree, html
import pytest

import delivery
import engine
import export
from exporters.markdown import parse_exported
from exporters.navigation import reference_name
from export_contract import NS, W
from wizard import dump_yaml


@pytest.mark.parametrize('language', ['es', 'en', 'pt'])
@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
def test_empty_legacy_contacts_link_has_a_real_destination(tmp_path, language, fmt):
    data = {'meta': {'report_title': 'Fictional contact navigation', 'lang': language},
            'findings': [{'id': 'F1', 'title': 'Synthetic navigation',
                          'description_md': '[Contact navigation](#sec-contacts)'}]}
    source = tmp_path / 'engagement.yaml'
    dump_yaml(data, source)
    before = source.read_bytes()
    captured = delivery.capture(tmp_path, tmp_path / 'snapshot')
    output = export.export(source, fmt, tmp_path / ('report.' + fmt))
    result = delivery.inspect_export(output, fmt, captured)
    assert result
    assert source.read_bytes() == before
    title = engine.load_lang(language)['labels']['contacts']
    if fmt == 'html':
        tree = html.document_fromstring(output.read_bytes())
        assert title in tree.xpath('string(//*[@id="sec-contacts"])')
        assert tree.xpath('//a[@href="#sec-contacts" and text()="Contact navigation"]')
    elif fmt == 'md':
        with zipfile.ZipFile(output) as archive:
            tree = parse_exported(archive.read('report.md').decode('utf-8'))
        assert title in tree.xpath('string(./h2[@data-rg-anchor="sec-contacts"])')
        assert tree.xpath('//a[@href="#sec-contacts" and text()="Contact navigation"]')
    elif fmt == 'docx':
        with zipfile.ZipFile(output) as archive:
            tree = etree.fromstring(archive.read('word/document.xml'))
        name = reference_name('sec-contacts')
        bookmarks = tree.xpath('//w:bookmarkStart[@w:name=$name]', namespaces=NS, name=name)
        assert len(bookmarks) == 1
        assert title in ''.join(bookmarks[0].getparent().itertext())
        assert tree.xpath('//w:hyperlink[@w:anchor=$name]', namespaces=NS, name=name)
        # Mutating away the real destination still fails the delivery contract.
        with zipfile.ZipFile(output) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        broken = deepcopy(tree)
        for bookmark in broken.xpath('//w:bookmarkStart[@w:name=$name]', namespaces=NS, name=name):
            bookmark.set(W + 'name', 'removed-contact-destination')
        members['word/document.xml'] = etree.tostring(broken)
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            for member, blob in members.items():
                archive.writestr(member, blob)
        with pytest.raises(ValueError, match='enlaces internos sin destino'):
            delivery.inspect_export(output, fmt, captured)
