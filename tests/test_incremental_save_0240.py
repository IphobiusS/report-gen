"""R12 contracts: truthful incremental serialization, recovery and portable history."""
from copy import deepcopy
from datetime import date
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import zipfile

import pytest

import incremental_save as inc
import project_history as hist
from input_guard import load_yaml_file
from storage import revision
from workflows import normalize


def document(count=160):
    rows = []
    for n in range(count):
        rows.append(dict(uid=f'00000000-0000-4000-8000-{n:012d}', id=f'F{n + 1}', mode='vuln',
            title=f'Synthetic finding {n + 1}', severity='info',
            description_md=('Synthetic documentary text with Unicode: ñ 🐕.\n' * 25),
            impact_md='Synthetic impact.', remediation_md='Synthetic action.',
            walkthrough=[dict(text_md='A documented test; no external target.')]))
    return normalize(dict(meta=dict(report_title='Synthetic incremental project', lang='en'), findings=rows))


@pytest.fixture(autouse=True)
def clean_cache():
    inc.clear_cache()
    yield
    inc.clear_cache()


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_local_change_serializes_one_row_and_stores_one_new_fragment(tmp_path):
    root = tmp_path/'project'; data = document(); first = hist.save(root, data)
    assert first['serialized_rows'] == len(data['findings'])
    old = tree(root); data['findings'][73]['description_md'] += '\nA localized addition.'
    result = hist.save(root, data)
    assert result['cache_hit'] and result['serialized_rows'] == 1
    assert result['reused_rows'] == len(data['findings']) - 1
    assert result['objects_written'] == 1 and result['fragments_written'] == 1
    assert result['fragment_bytes_written'] < 4096
    assert result['object_bytes_written'] < result['yaml_bytes'] / 5
    assert load_yaml_file(root/'engagement.yaml') == data
    assert (root/'engagement.yaml.bak').read_bytes() == old['engagement.yaml']
    previous = hist.history(root)[1]
    assert hist.snapshot_data(root, previous['id'])['findings'][73]['description_md'] != data['findings'][73]['description_md']


def test_noop_preserves_every_byte_inode_mtime_and_etag(tmp_path):
    root = tmp_path/'project'; data = document(); hist.save(root, data)
    before = tree(root); stat = {p.relative_to(root).as_posix():(p.stat().st_ino, p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
    tag = revision(root/'engagement.yaml')
    for _ in range(3):
        result = hist.save(root, deepcopy(data))
        assert result['unchanged'] and not result['transaction']
        assert result['serialized_rows'] == result['objects_written'] == result['fragments_written'] == 0
    assert tree(root) == before
    assert {p.relative_to(root).as_posix():(p.stat().st_ino,p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()} == stat
    assert revision(root/'engagement.yaml') == tag


@pytest.mark.parametrize('mutation,serialized', [('reorder',0),('add',1),('delete',0),('uid',1),('all',160)])
def test_identity_and_order_changes(tmp_path, mutation, serialized):
    root = tmp_path/'project'; data = document(); hist.save(root, data)
    if mutation == 'reorder': data['findings'].reverse()
    if mutation == 'add':
        row=deepcopy(data['findings'][0]); row.update(uid='ffffffff-ffff-4fff-8fff-ffffffffffff',id='F161',title='Added'); data['findings'].append(row)
    if mutation == 'delete': data['findings'].pop(20)
    if mutation == 'uid': data['findings'][20]['uid']='ffffffff-ffff-4fff-8fff-ffffffffffff'
    if mutation == 'all':
        for row in data['findings']: row['title'] += ' revised'
    result=hist.save(root,data)
    assert result['serialized_rows'] == serialized
    assert load_yaml_file(root/'engagement.yaml') == data
    assert all(dict(hist.snapshot_blobs(root, record)) for record in hist.history(root))


def test_external_mutation_same_inode_size_and_timestamp_does_not_use_cache(tmp_path):
    root=tmp_path/'project';data=document();hist.save(root,data)
    path=root/'engagement.yaml';before=path.read_bytes();stat=path.stat()
    external=before.replace(b'Synthetic impact.', b'EXTERNAL! impact.', 1)
    assert len(external)==len(before)
    path.write_bytes(external);os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns))
    assert path.stat().st_ino==stat.st_ino and path.stat().st_mtime_ns==stat.st_mtime_ns
    data['meta']['report_title']='Explicit edited state'
    result=hist.save(root,data)
    assert not result['cache_hit'] and result['cold_rows']==0
    assert result['serialized_rows']==len(data['findings'])
    assert (root/'engagement.yaml.bak').read_bytes()==external
    assert any(dict(hist.snapshot_blobs(root,r))['engagement.yaml']==external for r in hist.history(root))


def test_external_invalid_document_is_not_overwritten(tmp_path):
    root=tmp_path/'project';data=document();hist.save(root,data)
    (root/'engagement.yaml').write_bytes(b'meta: {}\nmeta: {}\n')
    before=tree(root)
    with pytest.raises(ValueError):hist.save(root,data)
    assert tree(root)==before
    assert not list(tmp_path.glob('.transaction-*'))


def test_scalar_types_are_not_collapsed_by_noop(tmp_path):
    root=tmp_path/'project';data=document(1);data['custom']=True;hist.save(root,data)
    data['custom']=1; result=hist.save(root,data)
    assert not result['unchanged'] and type(load_yaml_file(root/'engagement.yaml')['custom']) is int
    data['custom']=1.0;hist.save(root,data)
    assert type(load_yaml_file(root/'engagement.yaml')['custom']) is float


def test_dates_unicode_multiline_keys_and_aliases_roundtrip(tmp_path):
    root=tmp_path/'project';data=document(1)
    data['custom:\n🐕']=['yes','null','2026-10-09','🐕\n# quoted : value',date(2026,10,9)]
    row={'documentary':'same value'};data['opaque']=[row,row]
    hist.save(root,data)
    actual=load_yaml_file(root/'engagement.yaml')
    assert actual['custom:\n🐕'][-1]=='2026-10-09'
    assert actual['opaque']==[row,row] and actual['opaque'][0] is not actual['opaque'][1]


@pytest.mark.parametrize('fault', ['fragment','recipe','backup','yaml','journal','move'])
def test_failed_save_rolls_back_complete_project_and_context(tmp_path,monkeypatch,fault):
    root=tmp_path/'project';data=document();hist.save(root,data);before=tree(root)
    old_context=hist._STAGING.get();data['findings'][0]['title']='New title'
    original=inc.atomic_write
    def fail_fragment(path,blob,*args,**kwargs):
        if fault=='fragment' and 'fragments' in Path(path).parts:raise OSError(28,'synthetic ENOSPC')
        if fault=='recipe' and 'objects' in Path(path).parts and blob.startswith(inc.MAGIC):raise OSError(28,'synthetic ENOSPC')
        return original(path,blob,*args,**kwargs)
    monkeypatch.setattr(inc,'atomic_write',fail_fragment)
    import storage
    original_write=storage.atomic_write
    def fail_write(path,blob,*args,**kwargs):
        if fault=='backup' and Path(path).name=='engagement.yaml.bak':raise OSError(28,'synthetic ENOSPC')
        if fault=='yaml' and Path(path).name=='engagement.yaml':raise OSError(28,'synthetic ENOSPC')
        if fault=='journal' and Path(path).name.startswith('.commit-'):raise OSError(28,'synthetic ENOSPC')
        return original_write(path,blob,*args,**kwargs)
    monkeypatch.setattr(storage,'atomic_write',fail_write)
    monkeypatch.setattr(hist,'atomic_write',fail_write)
    original_rename=Path.rename
    def fail_move(path,destination):
        if fault=='move' and path.name.startswith('.transaction-'):raise OSError('synthetic activation failure')
        return original_rename(path,destination)
    monkeypatch.setattr(Path,'rename',fail_move)
    with pytest.raises(OSError):hist.save(root,data)
    assert tree(root)==before and hist._STAGING.get()==old_context
    assert not list(tmp_path.glob('.transaction-*')) and not list(tmp_path.glob('.commit-*'))
    with monkeypatch.context() as context:
        context.setattr(inc,'atomic_write',original);context.setattr(storage,'atomic_write',original_write)
        context.setattr(hist,'atomic_write',original_write);context.setattr(Path,'rename',original_rename)
        assert hist.save(root,data)['serialized_rows']==1


@pytest.mark.parametrize('fault', ['missing','tampered','symlink','wrong-key','count','bytes','duplicate','recursive'])
def test_recipe_and_fragment_integrity_limits(tmp_path,fault):
    root=tmp_path/'project';hist.save(root,document());record=hist.history(root)[0]
    key=record['files']['engagement.yaml'];target=root/'history/objects'/key
    recipe=json.loads(target.read_bytes()[len(inc.MAGIC):]);fragment=root/'history/fragments'/recipe['parts'][0]
    if fault=='missing':fragment.unlink()
    if fault=='tampered':fragment.write_bytes(fragment.read_bytes()+b'# altered')
    if fault=='symlink':
        outside=tmp_path/'outside';outside.write_bytes(fragment.read_bytes());fragment.unlink();fragment.symlink_to(outside)
    if fault=='wrong-key':recipe['sha256']='0'*64
    if fault=='count':recipe['parts']=['0'*64]*(inc.MAX_PARTS+1)
    if fault=='bytes':recipe['bytes']=inc.MAX_DOCUMENT_BYTES+1
    if fault=='recursive':
        blob=target.read_bytes();hashkey=sha256(blob).hexdigest();(root/'history/fragments'/hashkey).write_bytes(blob)
        recipe['parts']=[hashkey];recipe['bytes']=len(blob)
    if fault=='duplicate':
        target.write_bytes(inc.MAGIC+b'{"format":"report-gen-yaml-parts","format":"duplicate"}')
    elif fault not in ('missing','tampered','symlink'):
        target.write_bytes(inc.MAGIC+json.dumps(recipe).encode())
    before=tree(root)
    with pytest.raises(ValueError):hist.snapshot_data(root,record['id'])
    with pytest.raises(ValueError):hist.export_bundle(root)
    assert tree(root)==before


def test_portable_backup_materializes_every_legacy_object_and_restore_roundtrip(tmp_path):
    root=tmp_path/'project';data=document();hist.save(root,data);first=hist.history(root)[0]
    data['findings'][10]['title']='Updated';hist.save(root,data)
    before=tree(root);archive=hist.export_bundle(root)
    with zipfile.ZipFile(BytesIO(archive)) as source:
        assert not any(name.startswith('history/fragments/') for name in source.namelist())
        for name in source.namelist():
            if name.startswith('history/objects/'):
                assert sha256(source.read(name)).hexdigest()==name.rsplit('/',1)[1]
                assert not source.read(name).startswith(inc.MAGIC)
    assert tree(root)==before
    imported=tmp_path/'imported';hist.import_bundle(archive,imported)
    assert load_yaml_file(imported/'engagement.yaml')==data
    assert hist.snapshot_data(imported,first['id'])['findings'][10]['title']!='Updated'
    hist.restore(root,first['id'])
    assert load_yaml_file(root/'engagement.yaml')['findings'][10]['title']!='Updated'
    assert any(hist.snapshot_data(root,r['id'])['findings'][10]['title']=='Updated' for r in hist.history(root))


def test_noop_detects_image_resource_change_and_creates_recoverable_snapshot(tmp_path):
    from PIL import Image
    root=tmp_path/'project';data=document(1);hist.save(root,data)
    (root/'img').mkdir();Image.new('RGB',(4,4),'red').save(root/'img/proof.png')
    before=(root/'engagement.yaml').read_bytes();count=len(hist.history(root))
    result=hist.save(root,data)
    assert result['unchanged'] and result['transaction']
    assert (root/'engagement.yaml').read_bytes()==before and len(hist.history(root))==count+1
    assert dict(hist.snapshot_blobs(root,hist.history(root)[0]))['img/proof.png']==(root/'img/proof.png').read_bytes()


def test_cache_is_bounded_and_cold_restart_preserves_reuse_safety(tmp_path,monkeypatch):
    monkeypatch.setattr(inc,'CACHE_PROJECTS',2)
    for n in range(3):hist.save(tmp_path/str(n),document(1))
    assert len(inc._CACHE)==2
    root=tmp_path/'2';data=load_yaml_file(root/'engagement.yaml');inc.clear_cache()
    data['findings'][0]['title']='Cold edit';result=hist.save(root,data)
    assert not result['cache_hit'] and result['cold_rows']==0 and result['serialized_rows']==1


def test_cold_save_emits_current_rows_once_and_builds_a_verified_warm_cache(tmp_path, monkeypatch):
    import yaml
    root=tmp_path/'project';data=document();hist.save(root,data);inc.clear_cache()
    calls=[];original=yaml.dump
    def counted(value,*args,**kwargs):
        if isinstance(value,list) and value and isinstance(value[0],dict) and 'uid' in value[0]:
            calls.append(len(value))
        return original(value,*args,**kwargs)
    monkeypatch.setattr(yaml,'dump',counted)
    data['findings'][20]['title']='Cold modification';first=hist.save(root,data)
    assert calls==[len(data['findings'])] and first['cold_rows']==0
    assert first['serialized_rows']==len(data['findings'])
    calls.clear();data['findings'][21]['title']='Warm modification';second=hist.save(root,data)
    assert calls==[1] and second['cache_hit'] and second['serialized_rows']==1
    assert load_yaml_file(root/'engagement.yaml')==data


def test_large_writer_refuses_reader_size_limit_without_project_mutation(tmp_path):
    root=tmp_path/'project';data=document(1);hist.save(root,data);before=tree(root)
    data['findings'][0]['description_md']='x'*(inc.MAX_DOCUMENT_BYTES+1)
    with pytest.raises(ValueError):hist.save(root,data)
    assert tree(root)==before and not list(tmp_path.glob('.transaction-*'))


@pytest.mark.parametrize('member', ['history', 'history/objects', 'history/fragments', 'history/snapshots'])
def test_history_parent_symlinks_are_rejected_even_with_matching_leaf_bytes(tmp_path, member):
    import shutil
    root=tmp_path/'project';hist.save(root,document());record=hist.history(root)[0]
    path=root/member;outside=tmp_path/'external';shutil.copytree(path,outside)
    shutil.rmtree(path);path.symlink_to(outside,target_is_directory=True)
    before=tree(outside)
    with pytest.raises(ValueError):hist.snapshot_data(root,record['id'])
    with pytest.raises(ValueError):hist.export_bundle(root)
    assert tree(outside)==before


def test_failed_explicit_checkpoint_orphan_recipe_still_exports_valid_v1_backup(tmp_path, monkeypatch):
    import wizard
    root=tmp_path/'project';data=document();hist.save(root,data)
    data['findings'][4]['title']='Externally edited exact YAML'
    wizard.dump_yaml(data,root/'engagement.yaml')
    original=hist.atomic_write
    def full_disk(path,blob,*args,**kwargs):
        if Path(path).parent.name=='snapshots':raise OSError(28,'Synthetic full disk')
        return original(path,blob,*args,**kwargs)
    with monkeypatch.context() as context:
        context.setattr(hist,'atomic_write',full_disk)
        with pytest.raises(OSError):hist.checkpoint(root,'Explicit failed snapshot','draft')
    key=revision(root/'engagement.yaml');obj=root/'history/objects'/key
    assert obj.read_bytes().startswith(inc.MAGIC)
    assert not any(r['files']['engagement.yaml']==key for r in hist.history(root))
    before=tree(root);backup=hist.export_bundle(root)
    with zipfile.ZipFile(BytesIO(backup)) as archive:
        assert archive.read('history/objects/'+key)==(root/'engagement.yaml').read_bytes()
    assert tree(root)==before
    hist.import_bundle(backup,tmp_path/'restored')
    assert load_yaml_file(tmp_path/'restored/engagement.yaml')==data


def test_raw_unreferenced_object_starting_magic_is_not_treated_as_a_recipe(tmp_path):
    root=tmp_path/'project';hist.save(root,document())
    blob=inc.MAGIC+b'This is an opaque resource, not a JSON composition.\n'
    key=sha256(blob).hexdigest();(root/'history/objects'/key).write_bytes(blob)
    assert inc.read_object(root,key,document=None)==blob
    with zipfile.ZipFile(BytesIO(hist.export_bundle(root))) as archive:
        assert archive.read('history/objects/'+key)==blob


@pytest.mark.parametrize('first_role', ['document', 'resource'])
def test_yaml_and_text_annex_share_one_content_object_in_either_creation_order(tmp_path, first_role):
    from storage import atomic_write
    import wizard
    root=tmp_path/'project';data=document()
    if first_role=='document':
        hist.save(root,data);blob=(root/'engagement.yaml').read_bytes()
    else:
        root.mkdir();wizard.dump_yaml(data,root/'engagement.yaml')
        blob=(root/'engagement.yaml').read_bytes()
        atomic_write(root/'history/objects'/sha256(blob).hexdigest(),blob)
    key=sha256(blob).hexdigest();member='attachments/'+'a'*32+'.txt'
    atomic_write(root/member,blob)
    hist.save(root,data)
    shared=next(record for record in hist.history(root) if record['files'].get(member)==record['files']['engagement.yaml'])
    blobs=dict(hist.snapshot_blobs(root,shared))
    assert blobs['engagement.yaml']==blobs[member]==blob
    assert inc.read_object(root,key,document=False)==blob
    if first_role=='resource':assert (root/'history/objects'/key).read_bytes()==blob
    data['findings'][0]['title']='New documented state';hist.save(root,data)
    archive=hist.export_bundle(root)
    with zipfile.ZipFile(BytesIO(archive)) as source:
        assert source.read('history/objects/'+key)==blob
    target=tmp_path/'restored';hist.import_bundle(archive,target)
    hist.restore(target,shared['id'])
    assert (target/member).read_bytes()==blob


@pytest.mark.parametrize('trailing', [1, 2, 3])
@pytest.mark.parametrize('location', ['row', 'field'])
@pytest.mark.parametrize('temperature', ['cold', 'warm'])
def test_fragment_document_markers_preserve_exact_multiline_and_blank_tail(tmp_path,trailing,location,temperature):
    root=tmp_path/'project';data=document(2);hist.save(root,data)
    if temperature=='cold':inc.clear_cache()
    literal='Markdown\n- literal dash\n...\n🐕'+'\n'*trailing
    if location=='row':
        data['findings'][0]['author_nested']={'body':literal,'items':[[literal],[]]}
        data['findings'][0]['author_trailing']=literal
        data['findings'][1]['author_trailing']=literal
    else:data['author_last']=literal
    hist.save(root,data)
    assert load_yaml_file(root/'engagement.yaml')==data
    previous=hist.history(root)[0]
    data['meta']['report_title']='Later state';data['after_author']='Following a cached multiline field';hist.save(root,data)
    hist.restore(root,previous['id'])
    assert load_yaml_file(root/'engagement.yaml')['findings']==data['findings']
    if location=='field':assert load_yaml_file(root/'engagement.yaml')['author_last']==literal
    archive=hist.export_bundle(root);hist.import_bundle(archive,tmp_path/'imported')
    assert load_yaml_file(tmp_path/'imported/engagement.yaml')==load_yaml_file(root/'engagement.yaml')


@pytest.mark.parametrize('value', ['...\n', 'alpha\n...\n', '...\n\n', '\n\n'])
def test_indented_literal_end_dots_are_not_stripped(value):
    from input_guard import load_yaml
    assert load_yaml(inc._dump({'body':value}))=={'body':value}
    assert load_yaml(inc._dump([{'body':value}]))==[{'body':value}]
