#!/usr/bin/env python3
"""Accept the complete synthetic Aster case through report-gen's own delivery path.

All three authored languages and four registered formats are checked. This
runner inspects bounded fixture contracts, private-data exclusion, actual graph
placements, long-table rows and immutable inputs. Native LibreOffice inspection
is optional; Microsoft Word and universal correctness are never asserted.
"""
from __future__ import annotations

import base64
from collections import Counter
from hashlib import sha256
from io import BytesIO
import importlib.util
import json
from pathlib import Path
import posixpath
import re
import sys
import unicodedata
from urllib.parse import unquote_to_bytes
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import engine
from export_formats import get as export_format
import finding_instances


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


BUILDER = module('aster_acceptance_fixture', 'scripts/build-aster-case.py')
RUNNER = module('aster_shared_acceptance', 'scripts/audit-boreal-0410.py')
LANGUAGES = ('es', 'en', 'pt')
MAX_ARCHIVE_MEMBER = 160 * 1024 * 1024
MAX_ARCHIVE_TOTAL = 512 * 1024 * 1024


def compact(value):
    return unicodedata.normalize('NFKC', RUNNER.compact(value))


def fixture_contract(doc, language):
    """Require meaningful scenarios before trusting a successful export command."""
    facts = dict(vulnerabilities=sum(f.get('mode') != 'machine' for f in doc['findings']),
                 machines=sum(f.get('mode') == 'machine' for f in doc['findings']),
                 assets=len(doc['assets']), evidence=len(doc['evidence']), coverage=len(doc['coverage']),
                 test_cases=len(doc.get('test_cases', [])), http_pairs=len(doc.get('http_evidence', [])),
                 attack_paths=len(doc.get('attack_paths', [])))
    expected = dict(vulnerabilities=72, machines=6, assets=36, evidence=84, coverage=216,
                    test_cases=114, http_pairs=8, attack_paths=3)
    if facts != expected or engine.report_language(doc) != language:
        raise ValueError('Aster fixture contract mismatch: ' + json.dumps(facts))
    if {f['id'] for f in doc['findings']} != {f'F{n:02d}' for n in range(1, 73)} | {f'M{n:02d}' for n in range(1, 7)}:
        raise ValueError('Aster finding identities changed')
    for n, spec in enumerate(BUILDER.LONG_TABLES, 1):
        finding = next(f for f in doc['findings'] if f['id'] == spec['finding'])
        found = re.findall(fr'AST-T{n:02d}-R\d{{3}}', json.dumps(finding.get(spec['field']), ensure_ascii=False))
        expected_tokens = [f'AST-T{n:02d}-R{i:03d}' for i in range(1, spec['rows'] + 1)]
        if found != expected_tokens:
            raise ValueError('Aster table row changed, reordered or duplicated: ' + spec['finding'])
    instances = [f for f in doc['findings'] if f.get('instances')]
    if len(instances) != 1:
        raise ValueError('Aster needs exactly one multi-instance finding')
    summary = finding_instances.summary(instances[0], language)
    counts = {key: value for key, value in summary['counts'].items() if value}
    if summary['total'] != 18 or counts != {'open': 2, 'verified_fixed': 15, 'blocked': 1} or summary['status'] != 'in_progress':
        raise ValueError('Aster residual exposure was flattened or closed prematurely')
    rows = doc['test_cases']
    if ({row['test_id'] for row in rows} != {f'ASTER-TC-{n:03d}' for n in range(1, 115)}
            or {row['specialty'] for row in rows} != {'web', 'api', 'ad', 'cloud', 'mobile', 'ai', 'custom'}
            or Counter(row['specialty'] for row in rows)['api'] != 96
            or Counter(row['status'] for row in rows) != dict(passed=23, failed=23, pending=23, blocked=23, not_applicable=22)):
        raise ValueError('Aster methodology matrix is incomplete or lost a state')
    api = [row for row in rows if row['specialty'] == 'api']
    if len({(row['identity'], row['tenant'], row['operation']) for row in api}) != 96:
        raise ValueError('Aster role/tenant/operation matrix contains duplicates')
    for path in doc['attack_paths']:
        if len(path['nodes']) != 4 or len(path['edges']) != 3 or {edge['state'] for edge in path['edges']} != {'observed', 'inferred', 'blocked'}:
            raise ValueError('Aster path lost its uncertainty boundary')
    http = doc['http_evidence']
    if (sum(row['publication'] is not None for row in http) != 7
            or sum(row['original']['response'] is None for row in http) != 1
            or not any(row['original']['response'] and row['original']['response']['body_encoding'] == 'base64' for row in http)):
        raise ValueError('Aster HTTP cases must include reviewed, withheld, absent and binary responses')
    if not doc.get('client_profile') or not doc.get('review_exchange', {}).get('accepted'):
        raise ValueError('Aster lacks the client profile or accepted external review')
    return dict(facts, instances=summary, specialties=sorted({row['specialty'] for row in rows}),
                reviewed_http_pairs=7, withheld_http_pairs=1, long_tables=len(BUILDER.LONG_TABLES),
                long_table_rows=sum(row['rows'] for row in BUILDER.LONG_TABLES),
                external_review_acceptances=len(doc['review_exchange']['accepted']))


def text_corpus(outputs):
    """Extract actual rendered text; authored project strings are not export evidence."""
    import fitz
    from lxml import etree, html
    from exporters.markdown import parse_exported
    with fitz.open(outputs / 'informe.pdf') as pdf:
        pdf_text = '\n'.join(page.get_text() for page in pdf)
    with zipfile.ZipFile(outputs / 'informe.docx') as archive:
        document = etree.fromstring(archive.read('word/document.xml'))
    docx_text = '\n'.join(document.xpath('//w:t/text()', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}))
    html_tree = html.fromstring((outputs / 'informe.html').read_bytes())
    with zipfile.ZipFile(outputs / export_format('md').filename) as archive:
        markdown = archive.read('report.md').decode('utf-8')
    return {'pdf': pdf_text, 'docx': docx_text, 'html': html_tree.text_content(), 'md': parse_exported(markdown).text_content()}, html_tree


def private_tokens(doc):
    markers = [BUILDER.PRIVATE_MARKER, BUILDER.HTTP_PRIVATE_MARKER, BUILDER.METADATA_MARKER, BUILDER.REDACTION_MARKER,
               doc['client_profile']['uid'], *[row['uid'] for row in doc['review_exchange']['packages']]]
    return list(dict.fromkeys(markers + [base64.b64encode(marker.encode()).decode() for marker in markers]))


def reject_private(blob, tokens, label):
    if any(token.encode(encoding) in blob for token in tokens for encoding in ('utf-8', 'utf-16-le', 'utf-16-be')):
        raise ValueError('Private fixture content escaped into ' + label)


def inspect_archive(blob, tokens, label, *, depth=0, budget=None):
    """Inspect nested DOCX/Markdown archives without extracting paths to disk."""
    budget = [0, 0] if budget is None else budget
    reject_private(blob, tokens, label)
    stream = BytesIO(blob)
    if not zipfile.is_zipfile(stream):
        if blob.startswith(b'%PDF-'):
            import fitz
            with fitz.open(stream=blob, filetype='pdf') as pdf:
                reject_private(json.dumps(pdf.metadata).encode('utf-8'), tokens, label+' metadata')
                reject_private(pdf.get_xml_metadata().encode('utf-8'), tokens, label+' XMP')
                if pdf.embfile_count():
                    raise ValueError('Unexpected embedded PDF attachment: ' + label)
                decoded = 0
                for xref in range(1, pdf.xref_length()):
                    if pdf.xref_is_stream(xref):
                        value = pdf.xref_stream(xref)
                        decoded += len(value)
                        if decoded > MAX_ARCHIVE_TOTAL:
                            raise ValueError('PDF stream inspection budget exceeded: ' + label)
                        reject_private(value, tokens, label+' decoded PDF stream')
        return dict(members=0)
    if depth >= 4:
        raise ValueError('Unexpected archive nesting: ' + label)
    members = 0
    with zipfile.ZipFile(stream) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            budget[0] += info.file_size
            budget[1] += 1
            if (info.file_size > MAX_ARCHIVE_MEMBER or budget[0] > MAX_ARCHIVE_TOTAL
                    or budget[1] > 10000 or info.filename.startswith(('/', '\\'))
                    or '..' in Path(info.filename.replace('\\', '/')).parts):
                raise ValueError('Unexpected archive member or inspection budget: ' + label)
            path_parts = set(Path(info.filename.replace('\\', '/')).parts)
            if path_parts & {'private', 'originals'} or Path(info.filename).name == 'engagement.yaml':
                raise ValueError('Private project member was packaged: ' + label)
            child = archive.read(info)
            inspect_archive(child, tokens, label + '/' + info.filename, depth=depth + 1, budget=budget)
            members += 1
    return dict(members=members, expanded_bytes=budget[0], recursive_members=budget[1])


def image_fingerprint(blob):
    from PIL import Image
    with Image.open(BytesIO(blob)) as image:
        pixels = image.convert('RGB')
        return (pixels.width, pixels.height, sha256(pixels.tobytes()).hexdigest())


def image_data_url(source):
    if not isinstance(source, str) or not source.startswith('data:image/') or ',' not in source:
        return None
    header, content = source.split(',', 1)
    return base64.b64decode(content, validate=True) if ';base64' in header else unquote_to_bytes(content)


def inspect_graphs(outputs, snapshot, doc, html_tree):
    """Prove each generated causal diagram is placed in every actual output."""
    import fitz
    published = engine.load_engagement(snapshot / 'engagement.yaml')
    figures = published.get('attack_path_figures', [])
    expected_uids = {path['uid'] for path in doc['attack_paths']}
    if (len(figures) != 3 or {row['path_uid'] for row in figures} != expected_uids
            or any(row['part'] != 1 or row['parts'] != 1 for row in figures)):
        raise ValueError('Aster capture did not stage all three causal diagrams')
    fingerprints = {}
    for row in figures:
        blob = (snapshot / row['src']).read_bytes()
        if sha256(blob).hexdigest() != row['sha256']:
            raise ValueError('Staged graph bytes differ from recorded digest')
        fingerprints[image_fingerprint(blob)] = row
    if len(fingerprints) != 3:
        raise ValueError('Three different Aster paths produced identical diagrams')
    located = {kind: set() for kind in ('pdf', 'docx', 'md', 'html')}
    graph_pages = {row['path_uid']: set() for row in figures}
    dimensions = {(key[0], key[1]) for key in fingerprints}
    cache = {}
    with fitz.open(outputs / 'informe.pdf') as pdf:
        for page_number, page in enumerate(pdf, 1):
            for image in page.get_images(full=True):
                xref = image[0]
                if (image[2], image[3]) not in dimensions:
                    continue
                if xref not in cache:
                    cache[xref] = image_fingerprint(pdf.extract_image(xref)['image'])
                fingerprint = cache[xref]
                if fingerprint in fingerprints and page.get_image_rects(xref):
                    uid = fingerprints[fingerprint]['path_uid']
                    located['pdf'].add(uid)
                    graph_pages[uid].add(page_number)
    from lxml import etree
    from exporters.markdown import parse_exported
    for kind, filename in (('docx', 'informe.docx'), ('md', export_format('md').filename)):
        with zipfile.ZipFile(outputs / filename) as archive:
            if kind == 'docx':
                document = etree.fromstring(archive.read('word/document.xml'))
                relationships = etree.fromstring(archive.read('word/_rels/document.xml.rels'))
                ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
                      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
                placed = set(document.xpath('//a:blip/@r:embed', namespaces=ns))
                members = {posixpath.normpath(posixpath.join('word', row.get('Target', '')))
                           for row in relationships if row.get('Id') in placed and row.get('TargetMode') != 'External'}
            else:
                tree = parse_exported(archive.read('report.md').decode('utf-8'))
                members = set(tree.xpath('//img/@src'))
            for name in members:
                if not name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    continue
                fingerprint = image_fingerprint(archive.read(name))
                if fingerprint in fingerprints:
                    located[kind].add(fingerprints[fingerprint]['path_uid'])
    for source in html_tree.xpath('//img/@src'):
        blob = image_data_url(source)
        if blob is None:
            continue
        fingerprint = image_fingerprint(blob)
        if fingerprint in fingerprints:
            located['html'].add(fingerprints[fingerprint]['path_uid'])
    for kind, actual in located.items():
        if actual != expected_uids:
            raise ValueError(kind.upper() + ' omitted or altered a causal graph image')
    return dict(status='passed', graph_count=3, comparison='Decoded RGB pixel hashes and actual PDF image placements',
                outputs={kind: sorted(values) for kind, values in located.items()},
                pdf_pages={uid: sorted(pages) for uid, pages in graph_pages.items()})


def inspect_workflows(outputs, language, doc, snapshot, delivery_zip):
    """Review new workflow semantics and private-data boundaries after generation."""
    texts, html_tree = text_corpus(outputs)
    normalized = {kind: compact(text) for kind, text in texts.items()}
    finding = next(row for row in doc['findings'] if row.get('instances'))
    summary = finding_instances.summary(finding, language)
    expected_cases = [f'ASTER-TC-{n:03d}' for n in range(1, 115)]
    http_tokens = [f'ASTER-HTTP-{n:02d}' for n in range(1, 8)]
    accepted_note = doc['review_exchange']['accepted'][-1]['changes'][0]['note']
    for kind, text in normalized.items():
        for token in expected_cases:
            if text.count(token) != 1:
                raise ValueError(kind.upper() + ' test case is missing or duplicated: ' + token)
        for instance in finding['instances']:
            if compact(instance['endpoint']) not in text:
                raise ValueError(kind.upper() + ' omitted an affected instance destination')
        for key, count in summary['counts'].items():
            if count and compact(summary['labels'][key] + ': ' + str(count)) not in text:
                raise ValueError(kind.upper() + ' omitted residual exposure count: ' + key)
        for token in http_tokens:
            if token not in text:
                raise ValueError(kind.upper() + ' omitted a reviewed HTTP copy: ' + token)
        if 'ASTER-HTTP-08' in text:
            raise ValueError(kind.upper() + ' published the unreviewed HTTP case')
        for path in doc['attack_paths']:
            if compact(path['title']) not in text:
                raise ValueError(kind.upper() + ' omitted an attack-path narrative')
        if compact(accepted_note) not in text:
            raise ValueError(kind.upper() + ' omitted the accepted review text')
    tokens = private_tokens(doc)
    for kind, text in texts.items():
        reject_private(text.encode('utf-8'), tokens, kind + ' extracted text')
    published = engine.load_engagement(snapshot / 'engagement.yaml')
    if {'review_exchange', 'client_profile', 'http_evidence'} & set(published):
        raise ValueError('Private workflow records remain in the publication snapshot')
    for file in snapshot.rglob('*'):
        if file.is_file():
            reject_private(file.read_bytes(), tokens, 'snapshot/' + file.relative_to(snapshot).as_posix())
    # HTML images are base64, so inspect decoded bytes as well as visible text.
    for source in html_tree.xpath('//img/@src'):
        blob = image_data_url(source)
        if blob is not None:
            reject_private(blob, tokens, 'HTML embedded image')
    privacy = {}
    for file in sorted(outputs.rglob('*')):
        if file.is_file():
            privacy[file.relative_to(outputs).as_posix()] = inspect_archive(file.read_bytes(), tokens, file.name)
    privacy['delivery.zip'] = inspect_archive(delivery_zip.read_bytes(), tokens, 'delivery.zip')
    graphs = inspect_graphs(outputs, snapshot, doc, html_tree)
    artifacts = {file.relative_to(outputs.parent).as_posix(): dict(bytes=file.stat().st_size,
                 sha256=sha256(file.read_bytes()).hexdigest()) for file in sorted(outputs.rglob('*')) if file.is_file()}
    artifacts[delivery_zip.name] = dict(bytes=delivery_zip.stat().st_size, sha256=sha256(delivery_zip.read_bytes()).hexdigest())
    return dict(status='passed', semantic_formats=sorted(texts), test_case_ids_each_format=114,
                specialties=7, instance_destinations_each_format=18, instance_status_counts=summary['counts'],
                reviewed_http_markers_each_format=7, unreviewed_http_marker_absent=True,
                accepted_review_text_present=True, private_canaries_and_internal_ids_absent=True,
                private_snapshot_models_absent=True, archive_checks=privacy, causal_graphs=graphs,
                artifacts=artifacts, scope='Checks the complete synthetic Aster contract; not all possible projects or technical validity.')


def main():
    return RUNNER.main(builder=BUILDER, case_key='aster', contract=fixture_contract, token_prefix='AST',
                       extra_inspection=inspect_workflows, description=__doc__, harness_paths=(
                           Path(__file__).resolve(), ROOT / 'scripts/build-aster-case.py',
                           *sorted(BUILDER.CONTENT.glob('*.json'))))


if __name__ == '__main__':
    sys.exit(main())
