"""Stable, explicit remediation groups; findings remain independent records."""
import re

from error_messages import message

UID = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')


def structure_errors(data, occupied=()):
    errors = []

    def fail(path, text):
        errors.append(('error', path + ': ' + text))

    groups = data.get('root_cause_groups', [])
    if not isinstance(groups, list) or len(groups) > 1000:
        fail('root_cause_groups', message('debe ser una lista de hasta 1000 grupos', en='must be a list of up to 1000 groups'))
        return errors
    used = set(occupied)
    identities = set()
    for index, group in enumerate(groups):
        path = f'root_cause_groups[{index}]'
        if not isinstance(group, dict):
            fail(path, message('debe ser un objeto', en='must be an object'))
            continue
        identity = group.get('uid')
        if not isinstance(identity, str) or not UID.fullmatch(identity) or identity in used:
            fail(path + '.uid', message('identidad permanente inválida o duplicada', en='invalid or duplicate permanent identity'))
        else:
            used.add(identity)
            identities.add(identity)
        for key, maximum in (('name', 200), ('cause_md', 16000), ('remediation_md', 16000)):
            value = group.get(key, '')
            if not isinstance(value, str) or len(value) > maximum:
                fail(path + '.' + key, message('texto inválido o demasiado largo', en='invalid or oversized text'))
    findings = data.get('findings', [])
    if isinstance(findings, list):
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                continue
            reference = finding.get('root_cause_uid', '')
            if not isinstance(reference, str) or reference and reference not in identities:
                fail(f'findings[{index}].root_cause_uid', message('grupo de causa raíz inexistente', en='root cause group does not exist'))
    return errors


def group_for_finding(data, finding):
    """Read a relationship without changing the finding or the group."""
    reference = finding.get('root_cause_uid')
    return next((group for group in data.get('root_cause_groups', [])
                 if reference and group.get('uid') == reference), None)


def resolved_action(data, finding):
    """Prefer a finding's specific action; use the shared action only if absent."""
    specific = finding.get('remediation_md') or ''
    if specific.strip():
        return specific
    return (group_for_finding(data, finding) or {}).get('remediation_md', '')


def selected_groups(data):
    """Groups with current members only; no stale finding snapshots are stored."""
    members = {}
    for finding in data.get('findings', []):
        reference = finding.get('root_cause_uid')
        if reference:
            members.setdefault(reference, []).append(finding)
    return [(group, members[group['uid']]) for group in data.get('root_cause_groups', [])
            if group.get('uid') in members]
