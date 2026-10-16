#!/usr/bin/env python3
"""Check the full authored Atlas language catalogs without editing reports."""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
TECHNICAL_KEYS = frozenset({
    'case', 'key', 'version', 'date', 'host', 'ip', 'kind', 'severity', 'cwe',
    'asset', 'group', 'email', 'wordmark',
})
CORPORATE_NAME = 'Grupo Atlas Servicios Financieros'
IDENTICAL_TRANSLATIONS = {
    ('pt', 'assets.17.owner'): 'Plataforma',
    ('pt', 'assets.24.name'): 'Plataforma de eventos',
    ('en', 'strings.annex_asset_headers.2'): 'ipv4',
    ('en', 'strings.annex_control_headers.0'): 'control',
    ('en', 'strings.contract_table_headers.0'): 'Control',
    ('en', 'strings.literal_table_headers.1'): 'Literal',
    ('pt', 'strings.simulated'): '[SIMULADO]',
    ('pt', 'strings.allowed'): 'Permitida',
    ('pt', 'strings.image_before'): 'Antes',
    ('pt', 'strings.machine_ports'): '443/tcp, 8443/tcp [INVENTADOS]',
    ('pt', 'strings.evidence_title'): 'modelo documental',
    ('pt', 'strings.coverage_allowed'): 'Caso permitido',
    ('pt', 'strings.image_model'): 'MODELO SINTÉTICO',
    ('pt', 'strings.annex_names.3'): 'criterios-de-entrega.md',
    ('pt', 'strings.annex_names.4'): 'notas-internas.txt',
    ('pt', 'strings.annex_asset_headers.1'): 'destino',
    ('pt', 'strings.annex_asset_headers.2'): 'ipv4',
    ('pt', 'strings.annex_asset_headers.3'): 'tipo',
    ('pt', 'strings.annex_control_headers.2'): 'caso',
    ('pt', 'strings.annex_simulated'): 'SIMULADO',
    ('pt', 'strings.annex_retention_headers.3'): 'consumidores',
    ('pt', 'strings.annex_retention_rows.0.3'): 'Original, miniatura, índice',
    ('pt', 'strings.literal_table_headers.1'): 'Literal',
    ('pt', 'strings.contract_table_headers.2'): 'Contrato',
    ('pt', 'strings.literal_table_headers.0'): 'Identificador',
    ('pt', 'strings.literal_table_headers.2'): 'Contrato',
    ('pt', 'strings.severity_labels.critical'): 'Crítico',
    ('pt', 'strings.severity_labels.high'): 'Alto',
    ('pt', 'strings.severity_labels.info'): 'Informativo',
}
# These are valid Portuguese words, not Spanish-only markers.
PORTUGUESE_COGNATES = frozenset({'alcance', 'mediante', 'permitida'})
URL = re.compile(r'https?://[^\s<>\])]+')
DESTINATION = re.compile(r'\]\(([^)]*)\)')
PLACEHOLDER = re.compile(r'\{[A-Z][A-Z0-9_]*\}')
FENCED = re.compile(r'```[^\n]*\n.*?```', re.S)
MULTILINGUAL_LITERAL = ('> - Español: ejemplo ficticio.\n'
                       '> - English: fictional example.\n'
                       '> - Português: exemplo fictício.')
SPANISH = re.compile(
    r'\b(?:hallazgos?|ficticio|ficticia|ficticios|ficticias|pruebas?|'
    r'reintentos?|cuentas?|alcance|borrado|plazos?|proveedores?|equipo|'
    r'conservación|recuperación|autorización|remediación|solicitudes?|'
    r'rechazad[oa]s?|rechazo|cierre|evidencias|pérdida|datos|sesión|'
    r'ningún|ninguna|contiene|mediante|mientras|muestra|permitida|corrección)\b',
    re.I,
)


def at(path):
    return '.'.join(str(part) for part in path)


def leaves(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaves(child, (*path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from leaves(child, (*path, index))
    else:
        yield path, value


def shape(value):
    if isinstance(value, dict):
        return {key: shape(child) for key, child in value.items()}
    if isinstance(value, list):
        return [shape(child) for child in value]
    return type(value).__name__


def check_catalogs(catalogs):
    """Return explicit per-locale failures; no probabilistic language claim."""
    source = catalogs['es']
    source_leaves = dict(leaves(source))
    results = {}
    for lang in ('en', 'pt'):
        target = catalogs[lang]
        errors = []
        counts = Counter()
        exceptions = []
        if shape(source) != shape(target):
            errors.append({'check': 'structure', 'path': '$'})
        target_leaves = dict(leaves(target))
        for path, original in source_leaves.items():
            if path not in target_leaves:
                errors.append({'check': 'missing_field', 'path': at(path)})
                continue
            translated = target_leaves[path]
            if type(original) is not type(translated):
                errors.append({'check': 'scalar_type', 'path': at(path)})
                continue
            if not isinstance(original, str) or path[-1] in TECHNICAL_KEYS:
                counts['technical_fields'] += 1
                if original != translated:
                    errors.append({'check': 'invariant', 'path': at(path)})
                continue
            if not original.strip():
                counts['empty_fields'] += 1
                if original != translated:
                    errors.append({'check': 'empty_field', 'path': at(path)})
                continue
            if original == CORPORATE_NAME:
                counts['proper_names'] += 1
                exceptions.append({'path': at(path), 'reason': 'corporate proper name'})
                if original != translated:
                    errors.append({'check': 'corporate_name', 'path': at(path)})
                continue
            counts['human_fields'] += 1
            identical_allowed = IDENTICAL_TRANSLATIONS.get((lang, at(path))) == original == translated
            if identical_allowed:
                counts['reviewed_identical_translations'] += 1
                exceptions.append({'path': at(path), 'reason': 'identical valid wording or technical notation', 'value': translated})
            elif original == translated:
                errors.append({'check': 'untranslated_field', 'path': at(path)})
            else:
                counts['changed_human_fields'] += 1
            if Counter(URL.findall(original)) != Counter(URL.findall(translated)):
                errors.append({'check': 'url_destinations', 'path': at(path)})
            if Counter(DESTINATION.findall(original)) != Counter(DESTINATION.findall(translated)):
                errors.append({'check': 'markdown_destinations', 'path': at(path)})
            if Counter(PLACEHOLDER.findall(original)) != Counter(PLACEHOLDER.findall(translated)):
                errors.append({'check': 'placeholders', 'path': at(path)})
            if FENCED.findall(original) != FENCED.findall(translated):
                errors.append({'check': 'inert_code', 'path': at(path)})
            prose = URL.sub('', FENCED.sub('', translated)).replace(CORPORATE_NAME, '')
            if at(path) == 'sections.21.body':
                if MULTILINGUAL_LITERAL not in translated:
                    errors.append({'check': 'multilingual_test_literal', 'path': at(path)})
                prose = prose.replace(MULTILINGUAL_LITERAL, '')
                exceptions.append({'path': at(path), 'reason': 'exact declared three-language interoperability literal only',
                                   'value': MULTILINGUAL_LITERAL})
            markers = sorted(set(match.group().lower() for match in SPANISH.finditer(prose)))
            if lang == 'pt':
                markers = [marker for marker in markers if marker not in PORTUGUESE_COGNATES]
            if markers:
                errors.append({'check': 'spanish_markers', 'path': at(path), 'markers': markers})
        results[lang] = {'passed': not errors, 'counts': dict(counts),
                         'reviewed_exceptions': exceptions, 'errors': errors}
    return {'schema': 'report-gen-atlas-localization/1',
            'passed': all(item['passed'] for item in results.values()),
            'scope': 'Authored input catalogs; deterministic coverage and marker checks, not universal language detection.',
            'source_scalar_fields': len(source_leaves), 'locales': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--content', type=Path, default=ROOT / 'scripts' / 'atlas-case-content')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    paths = {lang: args.content / f'{lang}.json' for lang in ('es', 'en', 'pt')}
    catalogs = {lang: json.loads(path.read_text(encoding='utf-8')) for lang, path in paths.items()}
    result = check_catalogs(catalogs)
    result['files'] = {lang: {'name': path.name, 'bytes': path.stat().st_size,
                              'sha256': sha256(path.read_bytes()).hexdigest()}
                       for lang, path in paths.items()}
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding='utf-8')
    print(rendered, end='')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
