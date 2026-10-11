"""PDF code presence rejects altered tokens and missing repeated logical lines."""
from lxml import html
import pytest
from weasyprint import HTML

import export_contract


@pytest.mark.parametrize('source,changed', [
    ('SELECT id FROM audit;', 'MALICIOUS_SELECT id FROM audit;'),
    ('Get-SyntheticAudit', 'Get-SyntheticAuditUnsafe'),
    ('enable-control --audit', 'enable-control --audit-disabled'),
    ('disable-control', 'sudo disable-control'),
    ('deny();', 'deny(); allow();'),
    ('0xC0FFEE', '0xC0FFEE00'),
    ('allow = false', 'allow = false; deny = false'),
])
def test_changed_pdf_command_is_not_accepted_as_a_substring(source, changed):
    with pytest.raises(ValueError, match='código|code'):
        export_contract._pdf_code_lines(source, changed)


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('source,changed', [
    ('<pre>STATUS approved</pre><pre>STATUS approved</pre>', '<pre>STATUS approved</pre>'),
    ('<pre>FIRST\nCOMMON</pre><pre>COMMON\nLAST</pre>', '<pre>FIRST\nCOMMON\nLAST</pre>'),
    ('<pre>FIRST\nCOMMON</pre><pre>COMMON\nLAST</pre>', '<pre>FIRST\nCOMMON\nCHANGED\nLAST</pre>'),
    ('<pre>STATUS approved</pre>', '<pre>STATUS approved-extra</pre>'),
])
def test_removed_or_altered_pdf_code_is_rejected(tmp_path, language, source, changed):
    prefix = f'<html lang="{language}"><head><style>pre{{font-family:monospace;white-space:pre-wrap}}</style></head><body>'
    expected = export_contract.from_tree(html.document_fromstring(prefix + source + '</body></html>'))
    original = tmp_path / 'original.pdf'
    HTML(string=prefix + source + '</body></html>').write_pdf(original)
    export_contract.inspect(original, 'pdf', expected)
    corrupted = tmp_path / 'corrupted.pdf'
    HTML(string=prefix + changed + '</body></html>').write_pdf(corrupted)
    with pytest.raises(ValueError, match='código|code'):
        export_contract.inspect(corrupted, 'pdf', expected)


@pytest.mark.parametrize('source,text,wrapped', [
    ('Get-SyntheticAudit', '\n  Get-SyntheticAudit\r\n', 0),
    ('Get-SyntheticAudit', 'HEADER\nGet-Synthe\nticAudit\nFOOTER', 1),
    ('allow = false', 'allow  =\n false', 1),
    ('\tGet-SyntheticAudit  \n\nSTATUS approved', 'Get-SyntheticAudit\n\nSTATUS approved', 0),
    ('áéíóú № １２', 'áéíóú № １２', 0),
])
def test_pdf_logical_code_lines_allow_physical_wraps_and_extracted_indentation(source, text, wrapped):
    checked, actual_wrapped = export_contract._pdf_code_lines(source, text)
    assert checked == len([line for line in source.splitlines() if line.strip()])
    assert actual_wrapped == wrapped
