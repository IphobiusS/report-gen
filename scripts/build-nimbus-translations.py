#!/usr/bin/env python3
"""Build reproducible EN/PT editorial editions of the fictional Nimbus demo.

The Spanish original remains intact. Explicit locale JSON is the editable
source; diagrams are drawn from explicit bilingual data, never from real targets.
No network requests, credentials, exploit execution or automatic translation.
Run from any directory: python scripts/build-nimbus-translations.py [--check].
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
import resources  # noqa: E402
import validate  # noqa: E402
from incremental_save import serialized_yaml  # noqa: E402

SOURCE = ROOT / 'examples' / 'nimbus-locales'
DATE = (2026, 10, 15, 0, 0, 0)


def phrase(value, lang):
    return value if isinstance(value, str) else value[0 if lang == 'en' else 1]


def fonts(size, bold=False, mono=False):
    name = 'DejaVuSansMono.ttf' if mono else ('Carlito-Bold.ttf' if bold else 'Carlito-Regular.ttf')
    return ImageFont.truetype(str(ROOT / 'themes' / 'fonts' / name), size)


def wrapped(draw, text, max_width, font):
    """Wrap actual rendered glyph widths, including long literal values."""
    lines = []
    for paragraph in text.split('\n'):
        line = ''
        for word in paragraph.split():
            candidate = (line + ' ' + word).strip()
            if draw.textlength(candidate, font=font) <= max_width:
                line = candidate
                continue
            if line:
                lines.append(line)
            line = ''
            for char in word:
                if draw.textlength(line + char, font=font) > max_width:
                    lines.append(line)
                    line = ''
                line += char
        lines.append(line)
    return lines


def panel(identifier, spec, lang):
    width = 1600
    scratch = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    heading_font, body_font, label_font = fonts(32, True), fonts(26, mono=True), fonts(27)
    title = identifier.upper() + ' | ' + phrase(spec['title'], lang)
    headings = wrapped(scratch, title, width - 96, heading_font)
    rows = []
    for label, value in spec['rows']:
        left = wrapped(scratch, phrase(label, lang), 620, label_font)
        right = wrapped(scratch, phrase(value, lang), 800, body_font)
        rows.append((left, right, max(len(left), len(right)) * 36 + 24))
    footer = wrapped(scratch, phrase(spec['note'], lang), width - 96, label_font)
    header = 90 + len(headings) * 40
    height = header + sum(row[2] for row in rows) + 42 + len(footer) * 35 + 52
    image = Image.new('RGB', (width, height), '#ffffff')
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, header), fill='#e9f0f6')
    draw.text((48, 24), phrase(['FICTIONAL DEMO · SYNTHETIC REPRESENTATION',
                               'DEMONSTRAÇÃO FICTÍCIA · REPRESENTAÇÃO SINTÉTICA'], lang),
              fill='#235e93', font=fonts(23, True))
    for number, line in enumerate(headings):
        draw.text((48, 65 + number * 40), line, fill='#152b40', font=heading_font)
    y = header
    for number, (left, right, row_height) in enumerate(rows):
        draw.rectangle((32, y, width - 32, y + row_height), fill='#f1f5f8' if number % 2 == 0 else '#ffffff')
        for index, line in enumerate(left):
            draw.text((48, y + 10 + index * 36), line, fill='#152b40', font=label_font)
        for index, line in enumerate(right):
            draw.text((715, y + 10 + index * 36), line, fill='#152b40', font=body_font)
        y += row_height
    draw.line((48, y + 16, width - 48, y + 16), fill='#cbd5df', width=2)
    for number, line in enumerate(footer):
        draw.text((48, y + 32 + number * 35), line, fill='#33495d', font=label_font)
    draw.text((48, height - 42), phrase(['No requests were sent to real systems.',
                                       'Nenhuma requisição foi enviada a sistemas reais.'], lang),
              fill='#235e93', font=fonts(23, True))
    output = BytesIO()
    image.save(output, format='PNG', optimize=True)
    return output.getvalue()


def architecture(lang):
    """Same eight assets and documented trust boundaries, with localized labels."""
    image = Image.new('RGB', (1600, 850), '#ffffff')
    draw = ImageDraw.Draw(image)
    draw.text((48, 28), phrase(['Nimbus Commerce | Fictional architecture',
                               'Nimbus Commerce | Arquitetura fictícia'], lang),
              fill='#152b40', font=fonts(40, True))
    draw.text((48, 87), phrase(['Synthetic relationships. No real connections or intrusion.',
                               'Relações sintéticas. Nenhuma conexão ou intrusão real.'], lang),
              fill='#235e93', font=fonts(29))
    positions = {'PORTAL': (60, 190), 'API01': (610, 190), 'DB01': (1160, 190),
                 'AUTH01': (610, 390), 'FILES01': (1160, 390),
                 'CI01': (60, 610), 'DC01': (610, 610), 'WINAPP01': (1160, 610)}
    labels = {'PORTAL': ['Orders and support', 'Pedidos e suporte'],
              'API01': ['Authorization and integrations', 'Autorização e integrações'],
              'DB01': ['Synthetic data', 'Dados sintéticos'],
              'AUTH01': ['Recovery and sessions', 'Recuperação e sessões'],
              'FILES01': ['Attachments and internal service', 'Anexos e serviço interno'],
              'CI01': ['Artifacts and service identity', 'Artefatos e identidade de serviço'],
              'DC01': ['Groups and delegations', 'Grupos e delegações'],
              'WINAPP01': ['Local administration', 'Administração local']}
    # Direction describes the editorial architecture, not an executed attack.
    arrows = [((470, 250), (610, 250)), ((1020, 250), (1160, 250)),
              ((815, 450), (815, 310)), ((1020, 270), (1160, 450)),
              ((470, 670), (560, 670)), ((560, 670), (560, 290)),
              ((560, 290), (610, 290)), ((1020, 670), (1160, 670))]
    for start, end in arrows:
        draw.line((start, end), fill='#607e98', width=4)
        if start[0] < end[0]:
            draw.polygon((end, (end[0] - 13, end[1] - 7), (end[0] - 13, end[1] + 7)), fill='#607e98')
        elif start[1] > end[1]:
            draw.polygon((end, (end[0] - 7, end[1] + 13), (end[0] + 7, end[1] + 13)), fill='#607e98')
    for name, (x, y) in positions.items():
        draw.rectangle((x, y, x + 410, y + 120), fill='#f1f5f8', outline='#b3c3d1', width=2)
        draw.rectangle((x, y, x + 7, y + 120), fill='#235e93')
        draw.text((x + 20, y + 15), name, font=fonts(31, True), fill='#152b40')
        for index, line in enumerate(wrapped(draw, phrase(labels[name], lang), 375, fonts(25))):
            draw.text((x + 20, y + 58 + index * 30), line, font=fonts(25), fill='#33495d')
    draw.text((48, 789), phrase(['Internal paths start with supplied identities; no Internet-to-domain jump is implied.',
                               'Rotas internas partem de identidades fornecidas; não se presume um salto da Internet ao domínio.'], lang),
              font=fonts(26), fill='#33495d')
    output = BytesIO()
    image.save(output, format='PNG', optimize=True)
    return output.getvalue()


def build(lang):
    data = json.loads((SOURCE / (lang + '.json')).read_text(encoding='utf-8'))
    assert data['meta']['lang'] == lang
    validate.require_valid(data, final=True)
    diagrams = json.loads((SOURCE / 'diagrams.json').read_text(encoding='utf-8'))
    files = {'engagement.yaml': serialized_yaml(data)}
    for identifier, spec in diagrams.items():
        files['img/' + identifier + '.png'] = panel(identifier, spec, lang)
    files['img/arquitectura.png'] = architecture(lang)
    assert set(resources.referenced_images(data)) == set(files) - {'engagement.yaml'}
    manifest = {'format': 'report-gen-project', 'version': 1, 'created': '2026-10-15T00:00:00Z',
                'files': {name: sha256(blob).hexdigest() for name, blob in sorted(files.items())}}
    files['manifest.json'] = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')
    output = BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, blob in sorted(files.items()):
            info = zipfile.ZipInfo(name, DATE)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, blob, compresslevel=9)
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true', help='Verify committed bundles without rewriting them')
    args = parser.parse_args()
    for lang in ('en', 'pt'):
        blob = build(lang)
        path = ROOT / 'examples' / f'nimbus-demo-project-{lang}.zip'
        if args.check:
            if not path.is_file() or path.read_bytes() != blob:
                raise SystemExit(f'{path.name}: regenerate with this script')
        else:
            path.write_bytes(blob)
        print(f'{path.name}: {len(blob)} bytes; sha256 {sha256(blob).hexdigest()}')


if __name__ == '__main__':
    main()
