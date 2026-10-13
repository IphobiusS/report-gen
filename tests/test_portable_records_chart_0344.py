"""One semantic table becomes readable records; chart paints are measured in situ."""
import os
from pathlib import Path
import shutil
import subprocess
import pytest
import portable_report
import workflows
from wizard import dump_yaml


@pytest.mark.parametrize('language',['es','en'])
def test_record_table_counter_and_actual_svg_paints(tmp_path,language):
    if not os.environ.get('REPORT_GEN_CHROMIUM') or not shutil.which('node'):
        pytest.skip('Provide Chromium and Node/Playwright')
    rows='| Asset | Value | State | Notes |\n| --- | ---: | :---: | --- |\n'
    rows+='\n'.join(f'| Entity {i} | {i} | Pending | Complete criterion {i} |'for i in range(1,73))
    body=rows+'\n\n2147483646. First extreme ordinal.\n2147483647. Last extreme ordinal.\n'
    data={'meta':{'report_title':'Responsive records contract','theme':'corporativo','lang':language},
          'report':{'sections':[{'key':'findings_summary'},{'key':'findings'}]},
          'findings':[{'id':'F01','mode':'vuln','title':'Synthetic records','severity':'high','description_md':body},
                      {'id':'F02','mode':'vuln','title':'Second hypothesis','severity':'medium','description_md':'Pending evidence.'}]}
    workflows.normalize(data);dump_yaml(data,tmp_path/'engagement.yaml')
    target=tmp_path/'report.html';target.write_text(portable_report.build(tmp_path))
    result=subprocess.run(['node',str(Path(__file__).with_name('portable_records_chart_0344.cjs')),str(target)],capture_output=True,text=True,timeout=120)
    if result.returncode==77:pytest.skip('Provide Playwright')
    assert result.returncode==0,result.stdout+result.stderr


def test_record_preparation_preserves_headers_values_and_complex_table_fallback():
    from lxml import html
    original='<main><table><thead><tr><th>Key</th><th>State &amp; decision</th></tr></thead><tbody><tr><th scope="row">K1</th><td>Pending &lt;review&gt;</td></tr></tbody></table><table><thead><tr><th colspan="2">Grouped</th><th>Decision</th></tr></thead><tbody><tr><td>A</td><td>B</td><td>C</td></tr></tbody></table></main>'
    tree=html.fromstring(original)
    values=[[cell.text_content()for cell in row]for row in tree.xpath('.//tr')]
    portable_report.prepare_tables(tree,en=True)
    assert [[cell.text_content()for cell in row]for row in tree.xpath('.//tr')]==values
    assert len(tree.xpath('.//table[contains(@class,"report-records")]'))==1
    assert not tree.xpath('.//table/@aria-colcount|.//table/@aria-rowcount')
    assert tree.xpath('.//tbody/tr/th')[0].get('role')=='rowheader'
    assert tree.xpath('.//tbody/tr/td')[0].get('data-column-label')=='State & decision'
    complex_table=tree.xpath('.//table')[1]
    assert 'report-records' not in complex_table.get('class')
    assert complex_table.xpath('string(./thead/tr/th/@colspan)')=='2'
    assert complex_table.getparent().get('role')=='region'
