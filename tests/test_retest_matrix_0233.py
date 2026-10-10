"""R09 projection: recorded observations, unique identities and no mutation."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

import app as webapp
import engine
import retest_summary
import workflows
from storage import revision
from wizard import dump_yaml
from _support import auth_client


def project():
    return workflows.normalize(dict(meta={'report_title': 'Synthetic retest matrix', 'lang': 'es'},
        report={'sections': [{'key': 'findings'}]}, assets=[], evidence=[], coverage=[], findings=[
            dict(id='F01', title='Synthetic authorization finding', mode='vuln', severity='high',
                 description_md='Observed synthetic result.', impact_md='Synthetic impact.',
                 remediation_md='Check authorization.', status='reported_fixed', verification='confirmed')]))


def observed(data, result='fixed', tested_on='2026-10-09', **values):
    row=dict(uid=workflows.new_uid(), tested_on=tested_on, result=result, assessor='Synthetic assessor', evidence_uids=[])
    row.update(values)
    data['findings'][0].setdefault('retests', []).append(row)
    return row


def row(data, lang='es'):
    return retest_summary.summarize(data, lang)['rows'][0]


def test_reported_fixed_is_separate_from_result_and_technical_verification():
    data=project();before=deepcopy(data)
    result=retest_summary.summarize(data)
    finding=result['rows'][0]
    assert finding['status']=='reported_fixed' and finding['verification']=='confirmed'
    assert finding['outcome']=='not_run' and finding['latest'] is None
    assert result['result_counts']['fixed']==0 and result['result_counts']['not_run']==1
    assert any(notice['key']=='reported_fix' for notice in finding['notices'])
    assert result['technical_validation'] is False and result['exported_content_unchanged'] is True
    assert data==before and 'retests' not in data['findings'][0]


def test_latest_uses_valid_iso_date_then_registration_order_like_workflows():
    data=project()
    observed(data, 'open', '2026-09-01')
    chosen=observed(data, 'partial', '2026-10-08')
    assert row(data)['latest']['uid']==chosen['uid']
    tied=observed(data, 'fixed', '2026-10-08')
    assert row(data)['latest']['uid']==tied['uid']
    assert row(data)['latest']['uid']==workflows.latest_retest(data['findings'][0])['uid']
    older_append=observed(data, 'not_verified', '2025-01-01')
    assert row(data)['latest']['uid']!=older_append['uid']
    assert row(data)['latest']['record_index']==2


@pytest.mark.parametrize('bad_date', ['2026-02-30', '9999-99-99', '20261009', '2026-1-1', None, ''])
def test_invalid_or_missing_dates_never_override_a_dated_observation(bad_date):
    data=project();chosen=observed(data, 'open', '2026-10-08')
    observed(data, 'fixed', bad_date)
    finding=row(data)
    assert finding['latest']['uid']==chosen['uid'] and finding['outcome']=='open'
    assert finding['observations']==2 and finding['excluded_dates']==1
    assert any(item['key']=='excluded_dates' for item in finding['notices'])


def test_undated_legacy_records_are_visible_without_invented_uids_or_verification():
    data=project();finding=data['findings'][0]
    finding.pop('uid');finding.pop('verification');finding['status']='not_verified'
    finding['retests']=[dict(result='fixed', tested_on='', notes_md='Synthetic private procedure')]
    before=deepcopy(data);result=row(data)
    assert result['finding_uid'] is None and result['identity_status']=='missing'
    assert result['status']=='not_verified' and result['verification']=='unrecorded'
    assert result['outcome']=='undated' and result['observations']==1 and result['latest'] is None
    assert data==before and 'uid' not in finding and 'verification' not in finding


@pytest.mark.parametrize('unknown', ['not_run', 'unrecognized', ['fixed'], None])
def test_latest_unrecognized_result_does_not_reveal_earlier_fixed(unknown):
    data=project();observed(data, 'fixed', '2026-10-08')
    latest=observed(data, unknown, '2026-10-09')
    finding=row(data)
    # `not_run` is a presentation bucket for absence, not a valid model result.
    assert finding['outcome']=='invalid_result'
    assert finding['latest']['uid']==latest['uid']
    assert finding['latest']['result']==(unknown if isinstance(unknown, str) else '')


def test_verified_fixed_status_contradiction_and_missing_retest_links_are_explicit():
    data=project();data['findings'][0]['status']='verified_fixed'
    observed(data, 'open')
    assert any(item['key']=='contradictory_status' for item in row(data)['notices'])
    data['findings'][0]['retests'][-1]['result']='fixed'
    finding=row(data)
    assert finding['outcome']=='fixed'
    assert any(item['key']=='fixed_without_linked_evidence' for item in finding['notices'])
    assert not any(item['key']=='contradictory_status' for item in finding['notices'])
    assert finding['verification']=='confirmed'


def test_duplicate_uids_never_choose_a_finding_or_evidence_arbitrarily():
    data=project();finding=data['findings'][0]
    data['findings'].append(deepcopy(finding))
    uid=workflows.new_uid();data['evidence']=[dict(uid=uid, title='First synthetic evidence'), dict(uid=uid, title='Second synthetic evidence')]
    finding['evidence_uids']=[uid]
    result=retest_summary.summarize(data)
    assert all(item['identity_status']=='duplicate' for item in result['rows'])
    assert result['rows'][0]['original_evidence']['ambiguous']==1
    assert result['rows'][0]['original_evidence']['registered']==0
    assert result['rows'][0]['original_evidence']['items']==[]


def test_associations_count_unique_registry_links_not_proof_or_file_bytes():
    data=project();finding=data['findings'][0]
    asset_uid=workflows.new_uid();image_uid=workflows.new_uid();missing=workflows.new_uid()
    data['assets']=[dict(uid=asset_uid, name='Synthetic server', target='synthetic.invalid')]
    data['evidence']=[dict(uid=image_uid, title='Synthetic registry image', src='img/does-not-exist.png')]
    finding.update(asset_uids=[asset_uid, asset_uid, missing], evidence_uids=[image_uid,image_uid,missing,'invalid'], proof=[{'value':'Legacy inline proof'}])
    observed(data, evidence_uids=[image_uid])
    finding=row(data)
    assert finding['assets']['registered']==1 and finding['assets']['missing']==1
    assert finding['original_evidence']['registered']==1 and finding['original_evidence']['missing']==1 and finding['original_evidence']['invalid']==1
    assert finding['retest_evidence']['registered']==1
    assert finding['original_evidence']['items']==[dict(uid=image_uid,label='Synthetic registry image')]
    data['assets'][0]['uid']=image_uid
    finding=row(data)
    assert finding['original_evidence']['ambiguous']==1 and finding['retest_evidence']['ambiguous']==1


def test_scope_and_filters_follow_author_data_without_invented_defaults_or_private_content():
    data=project();data['findings'][0].pop('severity');data['findings'][0].pop('status')
    observed(data, notes_md='SYNTHETIC_PRIVATE_NOTES')
    data['coverage']=[dict(uid=workflows.new_uid(), status='blocked', test='Synthetic test'),dict(uid=workflows.new_uid(), test='Legacy coverage')]
    data['capture_inbox']=[dict(raw_text='SYNTHETIC_PRIVATE_CAPTURE')]
    data['insights']={'comments':[dict(body='SYNTHETIC_PRIVATE_COMMENT')]}
    before=deepcopy(data);result=retest_summary.summarize(data, 'en')
    assert result['filters']['statuses']==[dict(key='unrecorded', label='No recorded status')]
    assert result['filters']['severities']==[dict(key='unrecorded', label='Pending assessment')]
    assert result['coverage']['counts']['blocked']==1 and result['coverage']['counts']['unrecorded']==1 and result['coverage']['counts']['done']==0
    assert all(needle not in json.dumps(result) for needle in ('SYNTHETIC_PRIVATE_NOTES','SYNTHETIC_PRIVATE_CAPTURE','SYNTHETIC_PRIVATE_COMMENT'))
    assert 'not added to PDF' in result['scope'][-1] and data==before


def test_invalid_structure_is_not_reported_as_an_empty_matrix():
    for change in ({'findings':'invalid'}, {'assets':[None]}):
        data=project();data.update(change)
        with pytest.raises(ValueError, match='structure'): retest_summary.summarize(data)
    data=project();data['findings'][0]['retests']=[None]
    with pytest.raises(ValueError, match='structure'): retest_summary.summarize(data)


def test_executive_screen_does_not_change_the_existing_export_projection():
    data=project();data['report']['workflow']={'include_retest':False}
    observed(data, 'fixed', notes_md='Synthetic retest author procedure')
    before=workflows.project_report(data)
    result=retest_summary.summarize(data)
    after=workflows.project_report(data)
    assert before==after and data['report']['workflow']['include_retest'] is False
    assert result['result_counts']['fixed']==1
    assert not any(section.get('key')=='rg_retest' for section in after['report']['sections'])
    assert 'executive' not in json.dumps(after).lower()


def test_api_read_is_revision_bound_bilingual_and_leaves_all_saved_bytes_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, 'PROJECTS', tmp_path)
    data=project();observed(data, 'partial')
    directory=tmp_path/'matrix';directory.mkdir();engagement=directory/'engagement.yaml'
    dump_yaml(data, engagement)
    def files(): return {str(path.relative_to(tmp_path)):sha256(path.read_bytes()).hexdigest() for path in tmp_path.rglob('*') if path.is_file()}
    before=files();client=auth_client(webapp.app);tag=revision(engagement)
    response=client.get('/api/projects/matrix/retest-matrix?revision='+tag+'&lang=en')
    assert response.status_code==200
    payload=response.get_json()
    assert payload['revision']==tag and payload['project_slug']=='matrix'
    assert response.headers['ETag']=='"'+tag+'"'
    assert payload['matrix']['rows'][0]['outcome_label']=='Partially fixed'
    assert payload['matrix']['rows'][0]['status_label']=='Reported fixed'
    assert client.get('/api/projects/matrix/retest-matrix?revision='+'0'*64).status_code==409
    assert files()==before and engine.load_engagement(engagement)==data

