"""Validated bundled patterns; reading or copying never verifies a vulnerability.

The three authored JSON resources ship in the wheel. All returned data is copied,
so neither a project nor a private library can modify the in-process catalog.
"""
from copy import deepcopy
from datetime import date
from functools import lru_cache
from importlib.resources import files
import re
import unicodedata
from urllib.parse import urlsplit

from error_messages import message
import finding_library
from input_guard import load_json, ensure_data_tree
from languages import normalize_language, language_index

FILES = ('web-api.json', 'infrastructure.json', 'ai.json')
CATEGORIES = ('web', 'api', 'identity', 'infrastructure', 'cloud', 'mobile', 'ai')
PREFIXES = {'WEB': 'web', 'API': 'api', 'ID': 'identity', 'INF': 'infrastructure',
            'CLD': 'cloud', 'MOB': 'mobile', 'AI': 'ai'}
LOCALE_FIELDS = ('title', 'summary', 'description_md', 'impact_md', 'remediation_md',
                 'prerequisites', 'required_evidence', 'false_positives', 'retest', 'assessment_notes')
ENTRY_FIELDS = {'id', 'category', 'tags', 'cwe', 'reviewed_on', 'references', 'mappings', 'locales'}


def tr(es, en, pt):
    return message(es, en=en, pt=pt)


def language(value='es'):
    result = normalize_language(value, None)
    if result is None:
        raise ValueError(tr('Idioma del catálogo inválido: usa es, en o pt-BR',
                            'Invalid catalog language: use es, en or pt-BR',
                            'Idioma do catálogo inválido: use es, en ou pt-BR'))
    return result


def _invalid(path):
    raise ValueError(tr('Contenido de catálogo inválido', 'Invalid catalog content',
                        'Conteúdo do catálogo inválido') + ': ' + path)


def _text(value, path, maximum=16000, empty=False):
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        _invalid(path)
    return value


def _date(value, path):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        _invalid(path)
    try:
        date.fromisoformat(value)
    except ValueError:
        _invalid(path)


def validate_documents(documents):
    """Validate authored resources before any content is offered or persisted."""
    if not isinstance(documents, (list, tuple)) or not documents:
        _invalid('documents')
    seen = set()
    revision = None
    entries = []
    for doc in documents:
        ensure_data_tree(doc)
        if not isinstance(doc, dict) or set(doc) != {'format', 'schema_version', 'revision', 'entries'}:
            _invalid('document')
        if doc['format'] != 'report-gen-knowledge' or type(doc['schema_version']) is not int or doc['schema_version'] != 1:
            _invalid('schema_version')
        _text(doc['revision'], 'revision', 40)
        if revision is not None and revision != doc['revision']:
            _invalid('revision mismatch')
        revision = doc['revision']
        if not isinstance(doc['entries'], list) or not 1 <= len(doc['entries']) <= 500:
            _invalid('entries')
        for item in doc['entries']:
            if not isinstance(item, dict) or set(item) - ENTRY_FIELDS or ENTRY_FIELDS - {'cwe'} - set(item):
                _invalid('entry fields')
            identity = item['id']
            match = re.fullmatch(r'RG-(WEB|API|ID|INF|CLD|MOB|AI)-[0-9]{3}', identity) if isinstance(identity, str) else None
            if not match or identity in seen or item['category'] != PREFIXES[match[1]]:
                _invalid('id/category')
            seen.add(identity)
            tags = item['tags']
            if (not isinstance(tags, list) or not 1 <= len(tags) <= 30 or
                    any(not isinstance(tag, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+:-]{0,79}', tag) for tag in tags) or
                    len(set(tags)) != len(tags)):
                _invalid(identity + '.tags')
            _text(item.get('cwe', ''), identity + '.cwe', 12, empty=True)
            if item.get('cwe', '') and not re.fullmatch(r'CWE-[1-9][0-9]{0,5}', item['cwe']):
                _invalid(identity + '.cwe')
            _date(item['reviewed_on'], identity + '.reviewed_on')
            if not isinstance(item['references'], list) or not 1 <= len(item['references']) <= 15:
                _invalid(identity + '.references')
            for reference in item['references']:
                if not isinstance(reference, dict) or set(reference) != {'title', 'url', 'version', 'accessed_on'}:
                    _invalid(identity + '.references')
                _text(reference['title'], identity + '.reference.title', 300)
                _text(reference['version'], identity + '.reference.version', 160)
                _date(reference['accessed_on'], identity + '.reference.accessed_on')
                url = _text(reference['url'], identity + '.reference.url', 2000)
                try:
                    parsed = urlsplit(url)
                    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or '\\' in url or any(c.isspace() for c in url):
                        _invalid(identity + '.reference.url')
                    parsed.port  # Reject malformed port syntax as well.
                except ValueError:
                    _invalid(identity + '.reference.url')
            if not isinstance(item['mappings'], list) or len(item['mappings']) > 20:
                _invalid(identity + '.mappings')
            for mapping in item['mappings']:
                if not isinstance(mapping, dict) or set(mapping) != {'framework', 'version', 'id'}:
                    _invalid(identity + '.mappings')
                for key, value in mapping.items():
                    _text(value, identity + '.mapping.' + key, 160)
            if not isinstance(item['locales'], dict) or set(item['locales']) != {'es', 'en', 'pt'}:
                _invalid(identity + '.locales')
            for lang, authored in item['locales'].items():
                if not isinstance(authored, dict) or set(authored) != set(LOCALE_FIELDS):
                    _invalid(identity + '.locales.' + lang)
                for key, value in authored.items():
                    _text(value, identity + '.' + lang + '.' + key, 200 if key == 'title' else 16000)
                    if any(variable != 'objetivo' for variable in finding_library.VARIABLE.findall(value)):
                        _invalid(identity + '.' + lang + '.variables')
            entries.append(deepcopy(item))
    return {'format': 'report-gen-knowledge', 'schema_version': 1, 'revision': revision,
            'entries': sorted(entries, key=lambda item: item['id'])}


@lru_cache(maxsize=1)
def _bundled():
    directory = files('knowledge').joinpath('data')
    return validate_documents([load_json(directory.joinpath(name).read_bytes()) for name in FILES])


def _localized(item, lang):
    return {**deepcopy({key: value for key, value in item.items() if key != 'locales'}),
            **deepcopy(item['locales'][lang]), 'lang': lang, 'readonly': True}


def entry(identity, lang='es'):
    """Return an isolated localized record; a missing stable ID raises KeyError."""
    lang = language(lang)
    item = next((item for item in _bundled()['entries'] if item['id'] == identity), None)
    if item is None:
        raise KeyError(identity)
    return _localized(item, lang)


def _fold(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c))


def search(*, lang='es', q='', category='', tag='', offset=0, limit=24):
    lang = language(lang)
    if (not isinstance(q, str) or len(q) > 200 or not isinstance(category, str) or
            (category and category not in CATEGORIES) or not isinstance(tag, str) or len(tag) > 80 or
            type(offset) is not int or not 0 <= offset <= 100000 or
            type(limit) is not int or not 1 <= limit <= 100):
        raise ValueError(tr('Filtros o paginación del catálogo inválidos', 'Invalid catalog filters or pagination',
                            'Filtros ou paginação do catálogo inválidos'))
    source = _bundled()
    matches = []
    terms = _fold(q).split()
    for item in source['entries']:
        if category and item['category'] != category:
            continue
        if tag and tag.casefold() not in {value.casefold() for value in item['tags']}:
            continue
        localized = _localized(item, lang)
        searchable = _fold(' '.join([item['id'], item.get('cwe', ''), item['category'], *item['tags'],
                                     *item['locales'][lang].values(),
                                     *(str(value) for mapping in item['mappings'] for value in mapping.values())]))
        if all(term in searchable for term in terms):
            matches.append({key: localized.get(key, '') for key in
                            ('id', 'category', 'tags', 'cwe', 'reviewed_on', 'title', 'summary')})
    return {**{key: source[key] for key in ('format', 'schema_version', 'revision')}, 'lang': lang,
            'readonly': True, 'total': len(matches), 'offset': offset, 'limit': limit,
            'categories': [{'key': key, 'count': sum(item['category'] == key for item in source['entries'])}
                           for key in CATEGORIES],
            'tags': sorted({tag for item in source['entries'] for tag in item['tags']}),
            'entries': matches[offset:offset + limit]}


def template(identity, lang='es'):
    """Prepare an editable private-library copy without scores or observed facts."""
    item = entry(identity, lang)
    index = language_index(item['lang'])
    labels = {
        'prerequisites': ('Condiciones previas', 'Prerequisites', 'Pré-requisitos'),
        'false_positives': ('Posibles falsos positivos', 'Possible false positives', 'Possíveis falsos positivos'),
        'assessment_notes': ('Notas para la evaluación', 'Assessment guidance', 'Orientações para a avaliação'),
        'required_evidence': ('Evidencias por recopilar (pendiente)', 'Evidence to collect (pending)', 'Evidências a coletar (pendente)'),
        'retest': ('Criterios para el retest (pendiente)', 'Retest criteria (pending)', 'Critérios para o reteste (pendente)'),
    }
    content = {key: item[key] for key in ('title', 'description_md', 'impact_md', 'remediation_md')}
    for field in ('prerequisites', 'false_positives', 'assessment_notes'):
        content['description_md'] += '\n\n### ' + labels[field][index] + '\n\n' + item[field]
    content['remediation_md'] += '\n\n### ' + labels['retest'][index] + '\n\n' + item['retest']
    content['walkthrough'] = [{'lead': labels['required_evidence'][index], 'text_md': item['required_evidence']}]
    content.update(mode='vuln', references=[reference['url'] for reference in item['references']])
    if item.get('cwe'):
        content['cwe'] = item['cwe']
    return finding_library.validate_entry({'name': item['title'], 'tags': [identity, *item['tags'][:29]],
                                           'content': content})


def instantiate(identity, values, lang='es'):
    """Produce an unverified, unrated finding; the caller allocates its project ID."""
    if (not isinstance(values, dict) or set(values) - {'objetivo'} or
            any(not isinstance(value, str) or len(value) > 2000 for value in values.values())):
        raise ValueError(tr('Objetivo del catálogo inválido', 'Invalid catalog target', 'Alvo do catálogo inválido'))
    ensure_data_tree(values)
    return finding_library.instantiate(template(identity, lang), values)
