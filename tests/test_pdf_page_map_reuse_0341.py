"""Page maps reuse verified PDF text without changing pagination or safeguards."""
from argparse import Namespace
from urllib.parse import quote

import pytest

import engine
import export_contract
import pdf_pagination
from wizard import dump_yaml
import workflows


def test_reused_map_matches_independent_reader_for_wrapped_and_encoded_markers(tmp_path):
    keys = ['Appendix A', 'AppendixA', 'Annexe %41', 'Sección Ω / café', 'sec-conf', 'conf']
    chunks = []
    for index, key in enumerate(keys):
        marker = 'PGMK' + quote(key, safe='') + 'PGMK'
        # Split even within a %-encoded sequence: both readers must recover the same key.
        wrapped = '<br>'.join(marker[offset:offset+7] for offset in range(0, len(marker), 7))
        chunks.append(f'<section><h1>Sección Ω café {index}</h1><div>{wrapped}</div></section>')
    source = ('<html><head><meta charset="utf-8"><style>'
              '@page { size:A4; margin:20mm } body {font-family:DejaVu Sans}'
              'section {break-before:page} section:first-child{break-before:auto}'
              '</style></head><body>' + ''.join(chunks) + '</body></html>')
    output = tmp_path / 'markers.pdf'
    verified = engine.render_pdf_weasyprint(source, output, tmp_path)
    assert verified == export_contract.pdf_text_pages(output)
    fresh = engine.read_page_map(output, keys + ['missing'])
    reused = engine.read_page_map(output, keys + ['missing'], text_pages=verified)
    assert reused == fresh == {key:index+1 for index,key in enumerate(keys)}


def test_real_two_pass_export_reuses_only_current_first_pass_and_keeps_validation(tmp_path, monkeypatch):
    data = workflows.normalize({
        'meta': {'report_title':'Current source', 'theme':'serio', 'lang':'en'},
        'findings': [],
        'report': {'sections':[
            {'key':'Appendix A', 'title':'Space key', 'body':'CURRENT_SPACE_CANARY'},
            {'key':'AppendixA', 'title':'Compact key', 'body':'CURRENT_COMPACT_CANARY'},
        ]},
    })
    source = tmp_path / 'engagement.yaml'
    dump_yaml(data, source)
    calls = {'draw':0, 'text':0, 'tables':0, 'code':0, 'map':0}

    def count(owner, name, key):
        original = getattr(owner, name)
        def observed(*args, **kwargs):
            calls[key] += 1
            return original(*args, **kwargs)
        monkeypatch.setattr(owner, name, observed)

    from weasyprint.document import Document
    count(Document, 'write_pdf', 'draw')
    count(export_contract, 'pdf_text_pages', 'text')
    count(pdf_pagination, 'verify_finding_tables', 'tables')
    count(engine, '_verify_pdf_code_lines', 'code')
    original_map = engine.read_page_map
    maps = []
    def inspect_map(path, keys, *, text_pages=None):
        calls['map'] += 1
        assert text_pages is not None
        assert any('CURRENT_SPACE_CANARY' in page for page in text_pages)
        actual = original_map(path, keys, text_pages=text_pages)
        assert actual == original_map(path, keys)
        maps.append(actual)
        return actual
    monkeypatch.setattr(engine, 'read_page_map', inspect_map)
    output = tmp_path / 'final.pdf'
    engine._run(Namespace(engagement=str(source), out=str(output), only=None, lang=None,
                          theme=None, html=False, backend='weasyprint'))
    assert calls == {'draw':2, 'text':2, 'tables':2, 'code':2, 'map':1}
    assert all(key in maps[0] for key in ['Appendix A', 'AppendixA'])
    final_text = '\n'.join(export_contract.pdf_text_pages(output))
    assert 'CURRENT_SPACE_CANARY' in final_text and 'CURRENT_COMPACT_CANARY' in final_text
    assert 'PGMK' not in final_text


def test_failed_text_validation_does_not_publish_or_return_unverified_pages(tmp_path, monkeypatch):
    target = tmp_path / 'existing.pdf'
    target.write_bytes(b'previous verified export')
    def reject(_payload):
        raise ValueError('controlled ambiguous PDF text')
    monkeypatch.setattr(export_contract, 'pdf_text_pages', reject)
    with pytest.raises(ValueError, match='controlled ambiguous PDF text'):
        engine.render_pdf_weasyprint('<p>Text remains subject to extraction checks.</p>', target, tmp_path)
    assert target.read_bytes() == b'previous verified export'
