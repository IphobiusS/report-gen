"""Explicit field review exchange. Portable baselines, never reviewer authentication."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
import re
import secrets

from error_messages import message
from input_guard import load_json, ensure_data_tree
from languages import language_index
import workflows

FORMAT = 'report-gen-editorial-review'
FIELDS = ('title', 'description_md', 'impact_md', 'remediation_md', 'references')
MAX_BYTES = 2 * 1024 * 1024
MAX_BATCHES = 10
MAX_ROWS = 500
MAX_FIELD = 24000
HASH = re.compile(r'^[0-9a-f]{64}$')


def fail():
    return ValueError(message('Paquete de revisión inválido, alterado o demasiado grande.', en='Invalid, altered or oversized review package.', pt='Pacote de revisão inválido, alterado ou muito grande.'))


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def digest(value):
    return sha256(packed(value)).hexdigest()


def text(value, maximum=MAX_FIELD):
    if not isinstance(value, str) or len(value.encode('utf-8')) > maximum:
        raise fail()
    ensure_data_tree(value)
    return value


def field_text(finding, field):
    value = finding.get(field, [] if field == 'references' else '')
    if field == 'references':
        if not isinstance(value, list) or any(not isinstance(row, str) for row in value):
            raise fail()
        return '\n'.join(value)
    return value


def validate_package(value):
    if (not isinstance(value, dict) or set(value) != {'format', 'version', 'uid', 'project_slug', 'revision', 'rows', 'digest'}
            or value.get('format') != FORMAT or type(value.get('version')) is not int or value['version'] != 1
            or not isinstance(value.get('uid'), str) or not workflows.UID.fullmatch(value['uid'])
            or not isinstance(value.get('project_slug'), str) or not re.fullmatch(r'[\w-]{1,80}', value['project_slug'])
            or not isinstance(value.get('revision'), str) or not HASH.fullmatch(value['revision'])
            or not isinstance(value.get('digest'), str) or not HASH.fullmatch(value['digest'])):
        raise fail()
    rows = value['rows']
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise fail()
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'finding_uid', 'finding_id', 'field', 'base'}
                or not isinstance(row.get('finding_uid'), str) or not workflows.UID.fullmatch(row['finding_uid'])
                or not isinstance(row.get('field'), str) or row['field'] not in FIELDS):
            raise fail()
        text(row['finding_id'], 200)
        text(row['base'])
        key = (row['finding_uid'], row['field'])
        if key in seen:
            raise fail()
        seen.add(key)
    if len(packed(value)) > MAX_BYTES // 2 - 8192 or digest({k: v for k, v in value.items() if k != 'digest'}) != value['digest']:
        raise fail()
    return value


def validate_structure(data):
    if 'review_exchange' not in data:
        return []
    try:
        model = data['review_exchange']
        if not isinstance(model, dict) or not {'version', 'packages'} <= set(model) or set(model) - {'version', 'packages', 'accepted', 'accepted_omitted'} or type(model['version']) is not int or model['version'] != 1:
            raise fail()
        packages = model['packages']
        if not isinstance(packages, list) or len(packages) > MAX_BATCHES or len(packed(packages)) > 2 * MAX_BYTES or len(packed(model)) > 4 * MAX_BYTES:
            raise fail()
        seen = set()
        for package in packages:
            validate_package(package)
            if package['uid'] in seen:
                raise fail()
            seen.add(package['uid'])
        receipts = model.get('accepted', [])
        omitted = model.get('accepted_omitted', 0)
        if not isinstance(receipts, list) or len(receipts) > 50 or type(omitted) is not int or not 0 <= omitted <= 1_000_000:
            raise fail()
        for receipt in receipts:
            if (not isinstance(receipt, dict) or set(receipt) != {'package_uid', 'reviewer', 'source_revision', 'at', 'changes'}
                    or not isinstance(receipt['package_uid'], str) or not workflows.UID.fullmatch(receipt['package_uid'])
                    or not isinstance(receipt['source_revision'], str) or not HASH.fullmatch(receipt['source_revision'])
                    or not isinstance(receipt['at'], str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z', receipt['at'])
                    or not isinstance(receipt['changes'], list) or not 1 <= len(receipt['changes']) <= MAX_ROWS):
                raise fail()
            datetime.strptime(receipt['at'], '%Y-%m-%dT%H:%M:%SZ')
            if not text(receipt['reviewer'], 200).strip():
                raise fail()
            destinations = set()
            for change in receipt['changes']:
                if (not isinstance(change, dict) or set(change) != {'finding_uid', 'field', 'before_sha256', 'after_sha256', 'note'}
                        or not isinstance(change['finding_uid'], str) or not workflows.UID.fullmatch(change['finding_uid'])
                        or not isinstance(change['field'], str) or change['field'] not in FIELDS
                        or any(not isinstance(change[key], str) or not HASH.fullmatch(change[key]) for key in ('before_sha256', 'after_sha256'))):
                    raise fail()
                destination = (change['finding_uid'], change['field'])
                if destination in destinations:
                    raise fail()
                destinations.add(destination)
                text(change['note'], 4000)
    except (ValueError, TypeError, KeyError) as exc:
        return [('error', 'review_exchange: ' + str(exc))]
    return []


def issue(data, slug, revision, finding_uids, fields):
    if validate_structure(data):
        raise fail()
    if (not isinstance(finding_uids, list) or not 1 <= len(finding_uids) <= MAX_ROWS
            or any(not isinstance(uid, str) for uid in finding_uids) or len(set(finding_uids)) != len(finding_uids)
            or not isinstance(fields, list) or not fields or any(not isinstance(f, str) or f not in FIELDS for f in fields)
            or len(set(fields)) != len(fields) or len(fields) * len(finding_uids) > MAX_ROWS):
        raise fail()
    findings = {f['uid']: f for f in data.get('findings', [])}
    if any(uid not in findings for uid in finding_uids):
        raise fail()
    package = dict(format=FORMAT, version=1, uid=workflows.new_uid(), project_slug=slug, revision=revision,
                   rows=[dict(finding_uid=uid, finding_id=findings[uid].get('id', ''), field=field,
                              base=field_text(findings[uid], field)) for uid in finding_uids for field in fields])
    package['digest'] = digest(package)
    validate_package(package)
    updated = deepcopy(data)
    model = updated.setdefault('review_exchange', dict(version=1, packages=[]))
    model['packages'].append(package)
    if validate_structure(updated):
        raise ValueError(message('Se alcanzó la retención de revisiones. Elimina un paquete antiguo antes de emitir otro.', en='Review retention limit reached. Remove an old package before issuing another.', pt='Limite de retenção atingido. Remova um pacote antigo antes de emitir outro.'))
    return updated, deepcopy(package)


def preview(data, slug, returned):
    if isinstance(returned, str):
        if len(returned.encode('utf-8')) > MAX_BYTES:
            raise fail()
        returned = load_json(returned.encode('utf-8'))
    if (not isinstance(returned, dict) or set(returned) != {'package', 'reviewer', 'changes'}
            or len(packed(returned)) > MAX_BYTES):
        raise fail()
    ensure_data_tree(returned)
    package = validate_package(returned['package'])
    reviewer = text(returned['reviewer'], 200).strip()
    if not reviewer or package['project_slug'] != slug or validate_structure(data):
        raise fail()
    stored = next((p for p in data.get('review_exchange', {}).get('packages', []) if p['uid'] == package['uid']), None)
    if stored is None or packed(stored) != packed(package):
        raise ValueError(message('El paquete no fue emitido por este proyecto o fue eliminado.', en='This project did not issue this package, or it was removed.', pt='Este projeto não emitiu este pacote ou ele foi removido.'))
    changes = returned['changes']
    if not isinstance(changes, list) or len(changes) > MAX_ROWS:
        raise fail()
    bases = {(r['finding_uid'], r['field']): r for r in package['rows']}
    findings = {f['uid']: f for f in data.get('findings', [])}
    result, seen = [], set()
    for change in changes:
        if not isinstance(change, dict) or set(change) != {'finding_uid', 'field', 'after', 'note'}:
            raise fail()
        if not isinstance(change['finding_uid'], str) or not isinstance(change['field'], str):
            raise fail()
        key = (change['finding_uid'], change['field'])
        if key not in bases or key in seen:
            raise fail()
        seen.add(key)
        after, note = text(change['after']), text(change['note'], 4000)
        base, finding = bases[key], findings.get(key[0])
        current = field_text(finding, key[1]) if finding else None
        if after == base['base'] and not note:
            continue
        result.append(dict(key=':'.join(key), finding_uid=key[0], finding_id=base['finding_id'], field=key[1],
                           base=base['base'], before=current, after=after, note=note,
                           conflict=current is not None and current != base['base'] and current != after,
                           missing=finding is None, unchanged=current == after))
    return dict(package_uid=package['uid'], source_revision=package['revision'], reviewer=reviewer,
                authenticated=False, changes=result)


def apply(data, proposal, selected):
    if (not isinstance(selected, list) or not selected or len(selected) > MAX_ROWS
            or any(not isinstance(key, str) for key in selected) or len(set(selected)) != len(selected)):
        raise fail()
    changes = {row['key']: row for row in proposal['changes']}
    if any(key not in changes for key in selected):
        raise fail()
    updated = deepcopy(data)
    findings = {f['uid']: f for f in updated.get('findings', [])}
    for key in selected:
        row = changes[key]
        finding = findings.get(row['finding_uid'])
        if finding is None or field_text(finding, row['field']) != row['before']:
            raise ValueError(message('El texto actual cambió; compara el paquete de nuevo.', en='Current text changed; preview the package again.', pt='O texto atual mudou; visualize o pacote novamente.'))
        finding[row['field']] = row['after'].splitlines() if row['field'] == 'references' else row['after']
    model = updated.setdefault('review_exchange', dict(version=1, packages=[]))
    receipts = model.setdefault('accepted', [])
    receipts.append(dict(package_uid=proposal['package_uid'], reviewer=proposal['reviewer'],
                         source_revision=proposal['source_revision'], at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                         changes=[dict(finding_uid=changes[key]['finding_uid'], field=changes[key]['field'],
                                       before_sha256=digest(changes[key]['before']), after_sha256=digest(changes[key]['after']),
                                       note=changes[key]['note']) for key in selected]))
    excess = max(0, len(receipts) - 50)
    while len(packed(receipts[excess:])) > 2 * MAX_BYTES and excess < len(receipts) - 1:
        excess += 1
    model['accepted_omitted'] = model.get('accepted_omitted', 0) + excess
    model['accepted'] = receipts[excess:]
    if validate_structure(updated):
        raise fail()
    return updated


def forget(data, uid):
    updated = deepcopy(data)
    packages = updated.get('review_exchange', {}).get('packages', [])
    if not isinstance(uid, str) or not any(p['uid'] == uid for p in packages):
        raise fail()
    updated['review_exchange']['packages'] = [p for p in packages if p['uid'] != uid]
    return updated


def editor_html(package, lang='es'):
    """Offline editor: only selected text is embedded; all returned markup is text."""
    validate_package(package)
    i = language_index(lang)
    labels = [
        ('Revisión editorial', 'Editorial review', 'Revisão editorial'),
        ('Revisor (declaración, no identidad autenticada)', 'Reviewer (declaration, not authenticated identity)', 'Revisor (declaração, não identidade autenticada)'),
        ('Original', 'Original', 'Original'), ('Propuesta', 'Proposal', 'Proposta'),
        ('Comentario', 'Comment', 'Comentário'), ('Descargar propuestas JSON', 'Download JSON proposals', 'Baixar propostas JSON'),
        ('Este archivo contiene los textos privados seleccionados. Conserva el original; devuelve el JSON al autor para revisión campo por campo.', 'This file contains selected private text. Keep the original; return the JSON to the author for field-by-field review.', 'Este arquivo contém os textos privados selecionados. Guarde o original; devolva o JSON ao autor para revisão campo a campo.'),
        ('Indica el nombre declarado del revisor.', 'Enter the declared reviewer name.', 'Informe o nome declarado do revisor.')]
    words = [row[i] for row in labels]
    nonce = secrets.token_urlsafe(24)
    payload = json.dumps(dict(package=package, words=words), ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    script = """'use strict';const value=JSON.parse(document.getElementById('payload').textContent),p=value.package,w=value.words,edits=[];const add=(tag,text,parent)=>{const e=document.createElement(tag);e.textContent=text;parent.append(e);return e;};document.title=w[0];add('h1',w[0],document.body);add('p',w[6],document.body);const label=add('label',w[1],document.body),reviewer=add('input','',label);reviewer.maxLength=200;for(const row of p.rows){const s=add('section','',document.body);add('h2',row.finding_id+' · '+row.field,s);add('h3',w[2],s);add('pre',row.base,s);const l=add('label',w[3],s),a=add('textarea','',l);a.value=row.base;const nl=add('label',w[4],s),n=add('textarea','',nl);n.maxLength=4000;edits.push({row,a,n});}const b=add('button',w[5],document.body);b.type='button';b.addEventListener('click',()=>{if(!reviewer.value.trim()){alert(w[7]);return;}const changes=edits.filter(x=>x.a.value!==x.row.base||x.n.value.trim()).map(x=>({finding_uid:x.row.finding_uid,field:x.row.field,after:x.a.value,note:x.n.value})),blob=new Blob([JSON.stringify({package:p,reviewer:reviewer.value.trim(),changes},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=add('a','',document.body);a.href=url;a.download='report-gen-review-return.json';a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);});"""
    return ('<!doctype html><html lang="'+ ('pt-BR' if i == 2 else 'en' if i == 1 else 'es') +'"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'nonce-'+nonce+'\'; style-src \'nonce-'+nonce+'\'; base-uri \'none\'; form-action \'none\'">'
            '<title>'+escape(words[0])+'</title><style nonce="'+nonce+'">body{max-width:1000px;margin:2rem auto;padding:1rem;font:16px system-ui;background:#121a22;color:#e9f3ee}section{border:1px solid #526078;padding:1rem;margin:1rem 0}label{display:block;margin:1rem 0}textarea,input{display:block;width:95%;padding:.6rem;background:#202c37;color:#fff;border:1px solid #728799}textarea{min-height:9rem}pre{white-space:pre-wrap;overflow-wrap:anywhere}button{padding:1rem;cursor:pointer}</style><body>'
            '<script nonce="'+nonce+'" id="payload" type="application/json">'+payload+'</script><script nonce="'+nonce+'">'+script+'</script></body></html>')
