"""Versioned client writing requirements; applying a profile preserves authored content."""
from copy import deepcopy
from pathlib import Path
import json
import re

from error_messages import message
from input_guard import load_json_file, ensure_data_tree
from storage import atomic_write
import sections
import workflows

MAX_PROFILES = 100
MAX_VERSIONS = 20
MAX_BYTES = 2 * 1024 * 1024


def invalid():
    return ValueError(message('Perfil de cliente inválido o fuera de los límites.', en='Invalid client profile or limits exceeded.', pt='Perfil de cliente inválido ou limites excedidos.'))


def text(value, maximum=200, required=False):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise invalid()
    ensure_data_tree(value)
    return value


def validate_profile(profile):
    if (not isinstance(profile, dict) or set(profile) != {'uid', 'version', 'name', 'client', 'terms', 'required_sections', 'acceptance_criteria', 'delivery'}
            or not isinstance(profile['uid'], str) or not workflows.UID.fullmatch(profile['uid'])
            or type(profile['version']) is not int or not 1 <= profile['version'] <= MAX_VERSIONS):
        raise invalid()
    for key in ('name', 'client'):
        text(profile[key], required=key == 'name')
    terms = profile['terms']
    if not isinstance(terms, list) or len(terms) > 100:
        raise invalid()
    seen = set()
    for term in terms:
        if not isinstance(term, dict) or set(term) != {'term', 'preferred'}:
            raise invalid()
        text(term['term'], 200, True)
        text(term['preferred'], 500, True)
        if term['term'].casefold() in seen:
            raise invalid()
        seen.add(term['term'].casefold())
    required = profile['required_sections']
    if (not isinstance(required, list) or len(required) > 100
            or any(not isinstance(key, str) or key not in sections.catalog_by_key() for key in required)
            or len(set(required)) != len(required)):
        raise invalid()
    criteria = profile['acceptance_criteria']
    if not isinstance(criteria, list) or len(criteria) > 100:
        raise invalid()
    for criterion in criteria:
        text(criterion, 2000, True)
    delivery = profile['delivery']
    if (not isinstance(delivery, dict) or set(delivery) != {'formats', 'audience', 'language'}
            or not isinstance(delivery['formats'], list) or not delivery['formats']
            or any(not isinstance(kind, str) or kind not in ('pdf', 'docx', 'md', 'html') for kind in delivery['formats'])
            or len(set(delivery['formats'])) != len(delivery['formats'])
            or not isinstance(delivery['audience'], str) or delivery['audience'] not in ('technical', 'executive', 'public')
            or not isinstance(delivery['language'], str) or delivery['language'] not in ('es', 'en', 'pt')):
        raise invalid()
    return profile


def validate_structure(data):
    if 'client_profile' not in data:
        return []
    try:
        validate_profile(data['client_profile'])
    except (ValueError, KeyError, TypeError) as exc:
        return [('error', 'client_profile: ' + str(exc))]
    return []


def load(path):
    path = Path(path)
    from workspace_paths import _no_links
    _no_links(path)
    if not path.exists():
        return dict(version=1, profiles=[])
    if path.stat().st_size > MAX_BYTES:
        raise invalid()
    catalog = load_json_file(path)
    if not isinstance(catalog, dict) or set(catalog) != {'version', 'profiles'} or type(catalog['version']) is not int or catalog['version'] != 1:
        raise invalid()
    rows = catalog['profiles']
    if not isinstance(rows, list) or len(rows) > MAX_PROFILES * MAX_VERSIONS:
        raise invalid()
    seen = set()
    for row in rows:
        validate_profile(row)
        key = row['uid'], row['version']
        if key in seen:
            raise invalid()
        seen.add(key)
    if len({row['uid'] for row in rows}) > MAX_PROFILES:
        raise invalid()
    return catalog


def save(path, authored, expected_version):
    catalog = load(path)
    if not isinstance(authored, dict) or set(authored) != {'uid', 'name', 'client', 'terms', 'required_sections', 'acceptance_criteria', 'delivery'}:
        raise invalid()
    profile = deepcopy(authored)
    uid = profile['uid']
    if uid is None:
        if expected_version != 0 or type(expected_version) is not int:
            raise invalid()
        uid = workflows.new_uid()
    if not isinstance(uid, str):
        raise invalid()
    current = max((row['version'] for row in catalog['profiles'] if row['uid'] == uid), default=0)
    if type(expected_version) is not int or expected_version != current or (authored['uid'] is not None and not current):
        raise ValueError(message('El perfil cambió. Recarga su última versión antes de guardar.', en='The profile changed. Reload its latest version before saving.', pt='O perfil mudou. Recarregue a última versão antes de salvar.'))
    profile.update(uid=uid, version=current + 1)
    validate_profile(profile)
    catalog['profiles'].append(profile)
    blob = json.dumps(catalog, ensure_ascii=False, indent=2).encode('utf-8')
    if len(blob) > MAX_BYTES or len({r['uid'] for r in catalog['profiles']}) > MAX_PROFILES:
        raise invalid()
    atomic_write(path, blob)
    return profile


def get(path, uid, version):
    if not isinstance(uid, str) or type(version) is not int:
        raise invalid()
    profile = next((row for row in load(path)['profiles'] if row['uid'] == uid and row['version'] == version), None)
    if profile is None:
        raise invalid()
    return profile


def preview(data, profile):
    validate_profile(profile)
    current = data.get('report', {}).get('sections')
    if current is None:
        current = sections.default_enabled()
    keys = {section['key'] for section in current}
    changes = [dict(key='profile', before=data.get('client_profile'), after=deepcopy(profile))]
    if data.get('meta', {}).get('client', '') != profile['client']:
        changes.append(dict(key='client', before=data.get('meta', {}).get('client', ''), after=profile['client']))
    for key in profile['required_sections']:
        if key not in keys:
            changes.append(dict(key='section:'+key, before=None, after={'key': key}))
    return dict(profile_uid=profile['uid'], profile_version=profile['version'], changes=changes,
                automatic_text_replacement=False, delivery_is_preference=True)


def apply(data, proposal, selected):
    if (not isinstance(selected, list) or not selected or any(not isinstance(key, str) for key in selected)
            or len(set(selected)) != len(selected)):
        raise invalid()
    changes = {row['key']: row for row in proposal['changes']}
    if any(key not in changes for key in selected):
        raise invalid()
    updated = deepcopy(data)
    for key in selected:
        row = changes[key]
        if key == 'profile':
            updated['client_profile'] = deepcopy(row['after'])
        elif key == 'client':
            updated.setdefault('meta', {})['client'] = row['after']
        else:
            active = updated.setdefault('report', {}).setdefault('sections', sections.default_enabled())
            if not any(section['key'] == row['after']['key'] for section in active):
                active.append(deepcopy(row['after']))
    return updated


def requirements(data):
    profile = data.get('client_profile')
    if profile is None:
        return dict(active=False, missing_sections=[], terminology=[], acceptance_criteria=[])
    validate_profile(profile)
    active = data.get('report', {}).get('sections')
    keys = {section['key'] for section in (active if active is not None else sections.default_enabled())}
    issues = []
    for finding in data.get('findings', []):
        for field in ('title', 'description_md', 'impact_md', 'remediation_md'):
            source = finding.get(field, '')
            for term in profile['terms']:
                if re.search(r'(?<!\w)'+re.escape(term['term'])+r'(?!\w)', source, re.I):
                    issues.append(dict(finding_uid=finding['uid'], finding_id=finding.get('id',''), field=field, **term))
                    if len(issues) >= 500:
                        break
            if len(issues) >= 500:
                break
        if len(issues) >= 500:
            break
    return dict(active=True, profile_uid=profile['uid'], version=profile['version'],
                missing_sections=[key for key in profile['required_sections'] if key not in keys],
                terminology=issues, acceptance_criteria=profile['acceptance_criteria'], delivery=profile['delivery'])
