"""Field columns stay inside the viewport with actual text resizing and large rems."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import portable_report
import workflows
from wizard import dump_yaml


@pytest.mark.parametrize('language',['es','en'])
@pytest.mark.parametrize('layout',['sections','legacy'])
def test_portable_field_columns_reflow_at_large_root_and_actual_text_sizes(tmp_path,language,layout):
    executable=os.environ.get('REPORT_GEN_CHROMIUM')
    if not executable or not Path(executable).is_file() or not shutil.which('node'):
        pytest.skip('Set REPORT_GEN_CHROMIUM and provide Node + Playwright for browser checks')
    data={'meta':{'report_title':'Actual text resize contract','theme':'corporativo','lang':language},
          'findings':[{'id':'F01','mode':'vuln','title':'Synthetic account authorization',
                       'severity':'high','cvss':8.1,'cvss_vector':'CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N',
                       'cwe':'CWE-862','affected':'srv.example.test',
                       'description_md':'SOURCE-PROSE-END remains readable in its narrative section.\n\n'
                       '| Phase | Value | Decision |\n| --- | --- | --- |\n| 01 | 4×4=16 | PENDING-DECISION-END |',
                       'impact_md':'No real client or execution.',
                       'remediation_md':'Keep every field available.'}]}
    if layout=='sections':data['report']={'sections':[{'key':'findings_summary'},{'key':'findings'}]}
    workflows.normalize(data)
    if layout=='legacy':data.pop('report',None)
    dump_yaml(data,tmp_path/'engagement.yaml')
    output=tmp_path/'report.html';output.write_text(portable_report.build(tmp_path))
    result=subprocess.run(['node',str(Path(__file__).with_name('portable_text_resize_final.cjs')),str(output)],
                          capture_output=True,text=True,timeout=60,env=os.environ.copy())
    if result.returncode==77:pytest.skip(result.stderr.strip())
    assert result.returncode==0,result.stdout+result.stderr
