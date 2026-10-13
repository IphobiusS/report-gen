"""Client deliveries built from one private, immutable source snapshot."""
from languages import normalize_language, language_index
from error_messages import message as backend_message
from error_messages import current_language
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import re
import zipfile

from lxml import html
import engine
import export
import workflows

from version import __version__ as VERSION
from export_formats import REGISTRY, get
FORMATS = tuple(REGISTRY)


def public_warnings(issues, language='es'):
    """Keep advisory counts and categories, never private diagnostic payloads.

    The author reviews complete messages in the editor. Those messages can
    interpolate excluded annex names, original redaction needles, private CSV
    history, or source text before redaction. The client manifest must not copy
    messages, paths, finding identities, or help strings across that boundary.
    """
    labels = {
        'findings': ('Aviso de hallazgo revisado', 'Finding warning reviewed', 'Aviso de achado revisado'),
        'coverage': ('Aviso de cobertura revisado', 'Coverage warning reviewed', 'Aviso de cobertura revisado'),
        'root_cause_groups': ('Aviso de causa raíz revisado', 'Root cause warning reviewed', 'Aviso de causa raiz revisado'),
        'attachments': ('Aviso de anexo revisado', 'Annex warning reviewed', 'Aviso de anexo revisado'),
        'publication': ('Aviso de publicación revisado', 'Publication warning reviewed', 'Aviso de publicação revisado'),
        'report': ('Aviso de validación revisado', 'Validation warning reviewed', 'Aviso de validação revisado'),
        'audience': ('Aviso de alcance del extracto revisado', 'Derivative scope warning reviewed', 'Aviso de escopo da versão derivada revisado'),
    }
    rows = []
    for issue in issues:
        # Only fixed categories leave the source context. Unknown/private paths
        # deliberately share a generic label rather than exposing field names.
        root = re.split(r'[.\[]', str(issue.get('path', '')), maxsplit=1)[0]
        label = labels.get(root, ('Aviso privado revisado', 'Private warning reviewed', 'Aviso privado revisado'))
        rows.append({'level': 'warning', 'category': root if root in labels else 'private',
                     'message': label[language_index(language)],
                     'details': ((('El detalle del diagnóstico permanece en el proyecto privado; la revisión no acredita validez técnica.', 'Diagnostic details remain in the private project; review does not establish technical validity.', 'Os detalhes do diagnóstico permanecem no projeto privado; a revisão não comprova validade técnica.')[language_index(language)]))})
    return rows


def capture(directory, target):
    """Caller holds the project lock; copy only resources of the enabled report."""
    data = deepcopy(engine.load_engagement(directory / 'engagement.yaml'))
    meta = data.get('meta')
    lang = meta.get('lang', 'es') if isinstance(meta, dict) else 'es'
    issues = workflows.preflight(data, directory, lang)
    if any(i['level'] == 'error' for i in issues):
        # Verification warnings retain the document language; an API failure is
        # author-facing prose and follows the independently selected UI language.
        errors = workflows.preflight(data, directory, current_language())
        raise ValueError('; '.join(i['message'] for i in errors if i['level'] == 'error'))
    import publication
    captured = publication.snapshot(directory, target, data=data)
    import attachments
    captured['attachments'] = attachments.capture(data,directory,target)
    captured['issues'] = issues
    return captured



def inspect_pdf(path, expected_images):
    """Check the exported file, including printed TOC numbers and destinations."""
    import pdfplumber
    from pypdf import PdfReader
    reader = PdfReader(path)
    if not reader.pages:
        raise ValueError(backend_message('El PDF no contiene páginas'))
    destinations = reader.named_destinations
    checked = 0
    images = 0
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(reader.pages):
            text = pdf.pages[number].extract_text() or ''
            if re.search(r'PGMK[A-Za-z0-9_.~%\-]+PGMK', re.sub(r'\s+', '', text)):
                raise ValueError(backend_message('El PDF conserva marcadores internos de paginación'))
            images += len(pdf.pages[number].images)
            for annotation in page.get('/Annots', []):
                entry = annotation.get_object()
                dest = entry.get('/Dest')
                if not isinstance(dest, str):
                    continue
                if dest not in destinations:
                    raise ValueError(backend_message('El PDF contiene un destino interno inexistente'))
                actual = reader.get_destination_page_number(destinations[dest]) + 1
                if not 1 <= actual <= len(reader.pages):
                    raise ValueError(backend_message('El PDF contiene una referencia fuera de sus páginas'))
                # TOC links enclose the entire row, ending in their printed page.
                x0, ya, x1, yb = map(float, entry['/Rect'])
                p = pdf.pages[number]
                area = (max(0, x0), max(0, p.height-max(ya, yb)-1),
                        min(p.width, x1), min(p.height, p.height-min(ya, yb)+1))
                if area[0] >= area[2] or area[1] >= area[3]:
                    continue
                line = p.crop(area).extract_text() or ''
                # Only links spanning most of the page are TOC rows. Finding
                # titles elsewhere may themselves end in a number.
                if x1-x0 > p.width * .75:
                    shown = re.search(r'(\d+)\s*$', line)
                    if shown:
                        if int(shown[1]) != actual:
                            raise ValueError(backend_message('Índice PDF incoherente: {p0}', p0=dest))
                        checked += 1
    if images < expected_images:
        raise ValueError(backend_message('Faltan imágenes en el PDF: {p0} de {p1}', p0=images, p1=expected_images))
    return {'pages': len(reader.pages), 'image_placements': images,
            'expected_image_placements': expected_images, 'toc_references_checked': checked}


def inspect_archive(path, fmt, images, expected_placements=None):
    with zipfile.ZipFile(path) as package:
        if package.testzip():
            raise ValueError(backend_message('La exportación contiene un archivo dañado'))
        if fmt == 'docx':
            from lxml import etree
            for name in ('word/document.xml', 'word/styles.xml', '[Content_Types].xml'):
                etree.fromstring(package.read(name), parser=etree.XMLParser(resolve_entities=False, no_network=True))
            tree=etree.fromstring(package.read('word/document.xml'),parser=etree.XMLParser(resolve_entities=False,no_network=True))
            ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            names=tree.xpath('//w:bookmarkStart/@w:name',namespaces=ns)
            anchors=tree.xpath('//w:hyperlink/@w:anchor',namespaces=ns)
            if len(names)!=len(set(names)) or not set(anchors)<=set(names):
                raise ValueError(backend_message('El DOCX contiene marcadores duplicados o enlaces internos sin destino'))
            placements=len(tree.xpath('//*[local-name()="blip"]'))
            if expected_placements is not None and placements < expected_placements:
                raise ValueError(backend_message('Faltan imágenes en el DOCX / Images missing from DOCX'))
            media_hashes=set()
            for name in package.namelist():
                if name.startswith('word/media/'):
                    from PIL import Image
                    blob=package.read(name);media_hashes.add(sha256(blob).hexdigest())
                    with Image.open(BytesIO(blob)) as image: image.verify()
            if not set(images.values())<=media_hashes:
                raise ValueError(backend_message('El DOCX no conserva una imagen publicada / DOCX is missing a published image'))
            return {'archive_integrity': True, 'editable_document': True, 'internal_references_checked':len(anchors), 'image_placements':placements, 'images_verified':len(images)}
        if 'report.md' not in package.namelist():
            raise ValueError(backend_message('Falta el documento Markdown'))
        # Verify every referenced image against the immutable capture. Generated
        # charts have separate source-derived contracts, added by inspect_export.
        from exporters.markdown import parse_exported
        tree = parse_exported(package.read('report.md').decode('utf-8'))
        from resources import relative_image
        refs = {relative_image(src).as_posix() for src in tree.xpath('.//img/@src')}
        for name in refs:
            if name not in images or sha256(package.read(name)).hexdigest() != images[name]:
                raise ValueError(backend_message('La copia Markdown no conserva una imagen del informe'))
        return {'archive_integrity': True, 'images_verified': len(refs)}


def inspect_html(path, expected_images):
    """Inspect the actual standalone artifact; an HTML file is not a ZIP."""
    from base64 import b64decode
    from urllib.parse import unquote
    from PIL import Image
    tree = html.document_fromstring(path.read_text(encoding='utf-8'))
    if tree.find('body') is None or not tree.xpath('//main'):
        raise ValueError(backend_message('El HTML no contiene el informe'))
    if tree.xpath('//script[@src]|//link[@href]'):
        raise ValueError(backend_message('El HTML requiere recursos externos'))
    for css in tree.xpath('//style/text()'):
        if any(not value.strip(' \"\'').startswith('data:')
               for value in re.findall(r'url\(([^)]*)\)', css, re.I)):
            raise ValueError(backend_message('El HTML requiere recursos de estilo externos'))
    images = tree.xpath('//img[@src]')
    for node in images:
        source = node.get('src')
        if not re.match(r'^data:image/(?:png|jpeg|gif|webp);base64,', source):
            raise ValueError(backend_message('El HTML contiene una imagen no incorporada'))
        try:
            with Image.open(BytesIO(b64decode(source.split(',', 1)[1], validate=True))) as image:
                image.verify()
        except Exception as exc:
            raise ValueError(backend_message('El HTML contiene una imagen dañada')) from exc
    if len(images) < expected_images:
        raise ValueError(backend_message('Faltan imágenes en el HTML'))
    ids = tree.xpath('//*[@id]/@id')
    if len(ids) != len(set(ids)):
        raise ValueError(backend_message('El HTML contiene identificadores duplicados'))
    references = tree.xpath('//a[starts-with(@href,"#")]/@href')
    if any(ref != '#' and unquote(ref[1:]) not in ids for ref in references):
        raise ValueError(backend_message('El HTML contiene un destino interno inexistente'))
    return {'standalone': True, 'read_only': True, 'image_placements': len(images),
            'internal_references_checked': len(references)}


def inspect_export(path, fmt, captured):
    """Shared checks for individual downloads and complete deliveries."""
    # Native Word embeds supported encodings; WebP has an exact PNG conversion
    # captured before export. Both archive and scoped checks verify those bytes.
    inspection_capture = dict(captured, images=captured.get('docx_images', captured['images'])) if fmt == 'docx' else captured
    charts = (captured.get('contract') or {}).get('generated_charts', []) if fmt == 'md' else []
    if charts:
        inspection_capture = dict(captured, images={**captured['images'], **{c['path']: c['sha256'] for c in charts}})
    checks=get(fmt).inspect(path, inspection_capture)
    if charts:
        checks['images_verified'] -= len(charts)
        checks['generated_charts_verified'] = len(charts)
    from export_contract import inspect
    checks.update(inspect(path,fmt,captured.get('contract')))
    return checks


def build(snapshot, formats, identity, label, captured, output_dir, progress=lambda stage: None):
    if not isinstance(formats, list) or not formats or len(formats) > len(FORMATS) or any(
            not isinstance(f, str) or f not in FORMATS for f in formats) or len(set(formats)) != len(formats):
        raise ValueError(backend_message('Selecciona PDF, Word, Markdown o HTML, sin duplicados'))
    if not isinstance(label, str) or not label.strip() or len(label) > 120:
        raise ValueError(backend_message('Indica un nombre de entrega de 1 a 120 caracteres'))
    manifest = {'format': 'report-gen-delivery', 'version': 1, 'tool_version': VERSION,
                'label': label.strip(), 'created': datetime.now(timezone.utc).isoformat(),
                'source_revision': identity, 'files': {}}
    from design_library import guidance
    document=engine.load_engagement(snapshot / 'engagement.yaml')
    lang=normalize_language(document['meta'].get('lang'))
    manifest['warnings'] = public_warnings(captured['issues'], lang)
    guide=guidance(document)
    if guide: manifest["design_guidance"]=guide
    output_dir.mkdir()
    for fmt in FORMATS:
        if fmt not in formats:
            continue
        name = get(fmt).filename
        progress('rendering_' + fmt)
        out = export.export(snapshot / 'engagement.yaml', fmt, output_dir / name)
        progress('checking_' + fmt)
        checks = inspect_export(out, fmt, captured)
        blob = out.read_bytes()
        manifest['files'][name] = {'bytes': len(blob), 'sha256': sha256(blob).hexdigest(), 'checks': checks}
    for name, expected in captured.get('attachments',{}).items():
        blob=(snapshot/name).read_bytes()
        if len(blob)!=expected['bytes'] or sha256(blob).hexdigest()!=expected['sha256']:
            raise ValueError(backend_message('Anexo alterado tras la captura / Annex changed after capture'))
        destination=output_dir/name;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(blob)
        manifest['files'][name]=dict(expected,checks={'attachment':True})
    progress('packaging')
    result = BytesIO()
    with zipfile.ZipFile(result, 'w', zipfile.ZIP_DEFLATED) as package:
        for name in manifest['files']:
            package.write(output_dir / name, name)
        package.writestr('verificacion.json', json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
        package.writestr((('LEEME.txt', 'README.txt', 'LEIAME.txt')[language_index(lang)]),
                         (((('Entrega: ', 'Delivery: ', 'Entrega: ')[language_index(lang)]))+label.strip()+'\n'+
                          ((('Generada con report-gen ', 'Generated with report-gen ', 'Gerada com report-gen ')[language_index(lang)]))+VERSION+'\n'+
                          ((('Todos los formatos proceden de la misma revisión.\nEl registro verifica archivos y composición básica, no la validez técnica de los hallazgos.\nAvisos revisados: ', 'All formats come from the same saved revision.\nChecks cover files and basic layout, not the technical validity of findings.\nReviewed warnings: ', 'Todos os formatos vêm da mesma revisão salva.\nAs verificações cobrem os arquivos e a composição básica, não a validade técnica dos achados.\nAvisos revisados: ')[language_index(lang)]))+str(len(captured['issues']))+'\n'+
                          ((guide['name']+': '+guide['note']+'\n'+guide['source']+'\n'+((('Consultado: ', 'Checked: ', 'Consultado: ')[language_index(lang)]))+guide['checked']+'\n') if guide else '')))

    return result.getvalue()
