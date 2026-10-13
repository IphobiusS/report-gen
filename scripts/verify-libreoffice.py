#!/usr/bin/env python3
"""Render the existing synthetic acceptance corpus in LibreOffice, not Word.

Content/geometry checks are automated acceptance. The captured page images still
need visual inspection; this command never marks that separate review complete.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import unicodedata
from tempfile import TemporaryDirectory
import zipfile

import fitz
from lxml import etree
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import delivery


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_version(version):
    """A distro-maintained release counts; a development build does not."""
    return bool(re.match(r'^LibreOffice\s+\d+(?:\.\d+)+\b', version.strip())) and not re.search(
        r'(?i)(?:dev|alpha|beta|rc\d)', version)


def convert(executable, source, folder, *, timeout=90):
    """A fresh private profile prevents reuse of an unrelated office process."""
    folder.mkdir(parents=True, exist_ok=False)
    target = folder / (source.stem + '.pdf')
    with TemporaryDirectory(prefix='report-gen-lo-profile-') as profile:
        command = [str(executable), '-env:UserInstallation=' + Path(profile).as_uri(),
                   '--headless', '--nologo', '--nodefault', '--norestore',
                   '--convert-to', 'pdf:writer_pdf_Export', '--outdir', str(folder), str(source)]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   start_new_session=os.name == 'posix',
                                   env={**os.environ, 'SAL_USE_VCLPLUGIN': 'svp'})
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            # communicate has not reaped the timed-out child, so its PID cannot
            # have been recycled while addressing the private process group.
            if os.name == 'posix':
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            stdout, stderr = process.communicate()
            (folder / 'conversion.json').write_text(json.dumps({
                'status': 'timeout', 'timeout_seconds': timeout,
                'stdout': stdout, 'stderr': stderr}, indent=2) + '\n')
            raise ValueError(f'LibreOffice conversion timed out: {source.name}') from exc
    (folder / 'conversion.json').write_text(json.dumps({
        'status': 'completed', 'returncode': process.returncode,
        'stdout': stdout, 'stderr': stderr}, indent=2) + '\n')
    # Some LibreOffice failures return zero, so a new nonempty PDF is mandatory.
    if process.returncode or not target.is_file() or target.stat().st_size == 0:
        raise ValueError(f'LibreOffice did not produce a PDF: {source.name}')
    return target


def inspect_geometry(path, images):
    """Detect empty body pages, out-of-page ink and invalid link destinations.

    The 20 mm body band is the default Word report margin. A cover is exempt
    from the body-content requirement but not from physical page boundaries.
    This is not a judgment of visual spacing or URL line-fill quality.
    """
    images.mkdir(parents=True, exist_ok=False)
    pages, internal_links, external_links = [], 0, 0
    with fitz.open(path) as document:
        if not len(document):
            raise ValueError('LibreOffice produced no PDF pages')
        for number, page in enumerate(document, 1):
            body = fitz.Rect(0, 56.69, page.rect.width, page.rect.height - 56.69)
            text = page.get_text(clip=body).strip()
            pictures = page.get_image_info()
            if number > 1 and not text and not any(body.intersects(fitz.Rect(x['bbox'])) for x in pictures):
                raise ValueError(f'Empty body on PDF page {number}')
            bounds = page.rect + (-1, -1, 1, 1)
            for block in page.get_text('dict')['blocks']:
                if block['type'] != 0:
                    continue
                for line in block['lines']:
                    for span in line['spans']:
                        if span['text'].strip() and not bounds.contains(fitz.Rect(span['bbox'])):
                            raise ValueError(f'Text outside PDF page {number}: {span["text"]!r}')
            for picture in pictures:
                if not bounds.contains(fitz.Rect(picture['bbox'])):
                    raise ValueError(f'Image outside PDF page {number}')
            for link in page.get_links():
                if link['kind'] == fitz.LINK_GOTO:
                    if not 0 <= link.get('page', -1) < len(document):
                        raise ValueError(f'Invalid internal link on PDF page {number}')
                    internal_links += 1
                elif link['kind'] == fitz.LINK_URI:
                    external_links += 1
            raster = images / f'page-{number:03}.png'
            page.get_pixmap(dpi=110, alpha=False).save(raster)
            pages.append({'page': number, 'body_characters': len(text),
                          'image_placements': len(pictures), 'png': raster.name,
                          'png_sha256': sha256(raster)})
    return {'pages': pages, 'internal_links': internal_links, 'external_links': external_links,
            'no_empty_body_pages': True, 'no_outside_page_content': True}


def normalized_uri(value):
    # RFC 3986 sections 2.3 and 6.2.2.2: percent-encoded unreserved ASCII
    # characters are equivalent to their literal form. Never decode reserved
    # separators, percent signs, non-ASCII bytes or more than one level.
    def character(match):
        decoded = chr(int(match[0][1:], 16))
        return decoded if decoded in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~' else match[0].upper()
    return re.sub(r'%[0-9a-fA-F]{2}', character, value)


def inspect_links(source, pdf, geometry):
    """Preserve destinations, recording native unreserved-escape normalization."""
    with zipfile.ZipFile(source) as archive:
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        document = etree.fromstring(archive.read('word/document.xml'), parser)
        relationships = etree.fromstring(archive.read('word/_rels/document.xml.rels'), parser)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
          'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
    targets = {rel.get('Id'): rel.get('Target') for rel in relationships
               if rel.get('Type', '').endswith('/hyperlink') and rel.get('TargetMode') == 'External'}
    expected = Counter(targets[rid] for rid in document.xpath('//w:hyperlink/@r:id', namespaces=ns))
    actual = Counter()
    for page in PdfReader(pdf).pages:
        for annotation in page.get('/Annots', []):
            action = annotation.get_object().get('/A')
            if action:
                action = action.get_object()
                if action.get('/S') == '/URI':
                    actual[str(action.get('/URI', ''))] += 1
    expected_normalized, actual_normalized = Counter(), Counter()
    for value, count in expected.items():
        expected_normalized[normalized_uri(value)] += count
    for value, count in actual.items():
        actual_normalized[normalized_uri(value)] += count
    if expected_normalized - actual_normalized:
        raise ValueError('LibreOffice lost an external hyperlink destination: ' + repr(dict(expected_normalized - actual_normalized)))
    normalizations = [{'source': value, 'rendered': sorted(target for target in actual
                                                        if normalized_uri(target) == normalized_uri(value))}
                      for value in expected if value not in actual]
    # A wrapped external URL can generate several annotations. Internal anchors
    # can also span lines; require at least their authored placement count.
    anchors = len(document.xpath('//w:hyperlink/@w:anchor', namespaces=ns))
    if geometry['internal_links'] < anchors:
        raise ValueError(f'LibreOffice lost internal links: {geometry["internal_links"]} of {anchors}')
    return {'external_targets_checked': len(expected), 'exact_external_targets': len(set(expected) & set(actual)),
            'native_uri_normalizations': normalizations,
            'uri_comparison': 'RFC 3986 unreserved escapes and escape hex case only; no reserved separator decoding.',
            'native_uri_warning': ('LibreOffice rewrote the listed destination bytes. They are standard-equivalent, '
                                   'but a server comparing raw request encodings can distinguish them; '
                                   'the original DOCX retains the exact authored destination.' if normalizations else None),
            'authored_external_placements': sum(expected.values()),
            'authored_internal_placements': anchors, 'rendered_external_placements': sum(actual.values())}


def inspect_native_content(source, pdf, captured):
    docx_checks = delivery.inspect_export(source, 'docx', captured)
    # Word bookmark names are not the WeasyPrint region destination names.
    # Preserve the full DOCX association check, then apply the existing global
    # PDF checks with a copied viewer-specific contract. Do not pretend that
    # this establishes finding-region association in a third-party renderer.
    contract = dict(captured['contract'], pdf_regions=[])
    native_capture = dict(captured, contract=contract)
    pdf_checks = delivery.inspect_export(pdf, 'pdf', native_capture)
    return {'source_docx': docx_checks, 'native_pdf': pdf_checks,
            'native_pdf_finding_regions': 'not_verified',
            'scope': 'DOCX scoped content plus native PDF global text, metadata and image presence.'}


def inspect_contents(source, pdf):
    """Check live Word page references against the actual native PDF layout.

    Read the entry list from the DOCX, never infer it from the renderer's
    output. The title link and the numeric PAGEREF link must resolve to the
    same location, whose heading must match the source entry.
    """
    with zipfile.ZipFile(source) as archive:
        tree = etree.fromstring(archive.read('word/document.xml'),
                                etree.XMLParser(resolve_entities=False, no_network=True))
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    entries = []
    for paragraph in tree.xpath('//w:sdt[w:sdtPr/w:tag[@w:val="report-gen-contents"]]/w:sdtContent/w:p',
                                namespaces=ns):
        links = paragraph.xpath('./w:hyperlink', namespaces=ns)
        if len(links) != 1:
            raise ValueError('Contents entry must have one title hyperlink')
        title = ''.join(links[0].xpath('.//w:t/text()', namespaces=ns))
        anchor = links[0].get('{'+ns['w']+'}anchor')
        codes = paragraph.xpath('.//w:instrText/text()', namespaces=ns)
        if len(codes) != 1 or codes[0].strip() != f'PAGEREF {anchor} \\h':
            raise ValueError('Contents entry must retain its native page-reference field')
        entries.append({'title': title, 'anchor': anchor})
    if not entries:
        raise ValueError('DOCX has no report-gen contents entries')

    def normal(text):
        return ' '.join(unicodedata.normalize('NFKC', text).split())

    rows = []
    with fitz.open(pdf) as document:
        groups = {}
        for page_number, page in enumerate(document):
            for link in page.get_links():
                if link['kind'] != fitz.LINK_GOTO or 'to' not in link:
                    continue
                text = normal(page.get_textbox(link['from']))
                if not text:
                    continue
                key = (page_number, link['page'], round(link['to'].x, 1), round(link['to'].y, 1))
                groups.setdefault(key, []).append((link['from'], text))
        used = set()
        for entry in entries:
            candidates = []
            for key, parts in groups.items():
                titles = [(rect, text) for rect, text in parts
                          if not (text.isascii() and text.isdigit())]
                # Rectangles are ordered by reading position, not annotation
                # order; LibreOffice may write those in reverse order.
                titles.sort(key=lambda item: (round(item[0].y0, 1), item[0].x0))
                if normal(' '.join(text for _, text in titles)) == normal(entry['title']):
                    candidates.append((key, parts))
            if len(candidates) != 1:
                raise ValueError(f'Contents title is absent or ambiguous in native PDF: {entry["title"]}')
            key, parts = candidates[0]
            if key in used:
                raise ValueError('Two contents entries resolved to one rendered row')
            used.add(key)
            source_page, target_page, target_x, target_y = key
            numbers = [(rect, text) for rect, text in parts if text.isascii() and text.isdigit()]
            if len(numbers) != 1:
                raise ValueError(f'Contents page number is missing or ambiguous: {entry["title"]}')
            rect, shown = numbers[0]
            title_rects = [box for box, text in parts if not (text.isascii() and text.isdigit())]
            last_title_line = max(title_rects, key=lambda box: (box.y0, box.x0))
            title_middle = (last_title_line.y0 + last_title_line.y1) / 2
            number_middle = (rect.y0 + rect.y1) / 2
            tolerance = max(2, min(rect.height, last_title_line.height) / 4)
            if abs(title_middle - number_middle) > tolerance:
                raise ValueError(f'Contents page number is not on its title row: {entry["title"]}')
            if rect.x0 < document[source_page].rect.width / 2 or int(shown) != target_page + 1:
                raise ValueError(f'Incorrect contents page number: {entry["title"]}: {shown} != {target_page + 1}')
            if not 0 <= target_page < len(document):
                raise ValueError('Contents destination falls outside native PDF')
            # Inspect the text immediately following the destination, not a
            # duplicate title elsewhere (such as in the index itself).
            target = document[target_page]
            lines = [line for block in target.get_text('dict')['blocks'] if block['type'] == 0
                     for line in block['lines'] if line['bbox'][3] >= target_y - 2]
            lines.sort(key=lambda line: (round(line['bbox'][1], 1), line['bbox'][0]))
            destination_text = normal(' '.join(span['text'] for line in lines[:8] for span in line['spans']))
            if normal(entry['title']) not in destination_text:
                raise ValueError(f'Contents destination does not point to its heading: {entry["title"]}')
            rows.append(dict(entry, contents_page=source_page + 1, shown=int(shown), actual=target_page + 1))
    return {'entries_checked': len(entries), 'page_numbers_match_native_layout': True,
            'title_and_number_destinations_match': True, 'rows': rows}


def run(destination, executable, require_stable=False):
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Use an empty output directory; existing evidence is preserved')
    destination.mkdir(parents=True, exist_ok=True)
    version = subprocess.run([str(executable), '--version'], check=True, capture_output=True,
                             text=True, timeout=15).stdout.strip()
    result = {'schema': 1, 'renderer': 'LibreOffice', 'renderer_version': version,
              'distribution_stable': stable_version(version), 'status': 'running',
              'recorded_at': datetime.now(timezone.utc).isoformat(), 'documents': [],
              'visual_review': 'pending', 'microsoft_word': 'not_run',
              'scope': 'Synthetic DOCX conversions, source-bound content checks, images, links and page geometry. '
                       'Not Microsoft Word or human usability acceptance; URL line-fill quality requires visual review.'}
    receipt = destination / 'libreoffice-validation.json'

    def save():
        receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    save()
    try:
        if require_stable and not result['distribution_stable']:
            raise ValueError('A stable LibreOffice release is required; development builds are not accepted')
        spec = importlib.util.spec_from_file_location('external_acceptance', ROOT / 'scripts/prepare-external-acceptance.py')
        preparation = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preparation)
        prepared = preparation.prepare(destination / 'kit')
        result.update(commit=prepared['commit'], source_state=prepared['source_state'], version=prepared['version'])
        for document in prepared['documents']:
            case = document['case']
            source = destination / 'kit' / document['docx']
            before = sha256(source)
            if before != document['docx_sha256']:
                raise ValueError(f'Prepared input changed: {case}')
            pdf = convert(executable, source, destination / 'rendered' / case)
            with TemporaryDirectory(prefix='report-gen-lo-capture-') as temporary:
                captured = delivery.capture(destination / 'kit/synthetic-projects' / case,
                                            Path(temporary) / 'snapshot')
                content = inspect_native_content(source, pdf, captured)
            geometry = inspect_geometry(pdf, pdf.parent / 'pages')
            links = inspect_links(source, pdf, geometry)
            contents = inspect_contents(source, pdf)
            if sha256(source) != before:
                raise ValueError(f'LibreOffice changed the original DOCX: {case}')
            result['documents'].append({'case': case, 'docx_sha256': before,
                                        'pdf': str(pdf.relative_to(destination)), 'pdf_sha256': sha256(pdf),
                                        'content_checks': content, 'links': links, 'contents': contents,
                                        'geometry': geometry})
            save()
        result['status'] = 'passed'
        return result
    except Exception as exc:
        result.update(status='failed', error=str(exc))
        raise
    finally:
        save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--executable', default=shutil.which('libreoffice') or shutil.which('soffice'))
    parser.add_argument('--require-stable', action='store_true')
    args = parser.parse_args()
    if not args.executable:
        parser.error('LibreOffice is required; provide --executable')
    try:
        result = run(args.output, args.executable, args.require_stable)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'LibreOffice acceptance failed: {exc}\n')
    print(json.dumps({'status': result['status'], 'renderer_version': result['renderer_version'],
                      'documents': len(result['documents']), 'visual_review': result['visual_review']}))


if __name__ == '__main__':
    main()
