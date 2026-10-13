"""PDF-only machine route overview from the already published report copy.

The machine model records ordered phases, not causal edges. Arrows therefore
mean documentation order only. Figure references use the renderer's existing
numbering; linked evidence appended by workflow is kept outside the route.
"""
import re
import textwrap
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

from markupsafe import Markup
from PIL import ImageFont


WORDS = {
    'en': {
        'title': 'Documented route', 'phase': 'Phase', 'step': 'Step', 'steps': 'Recorded steps',
        'no_lead': 'No step heading recorded',
        'figures': 'Figures', 'no_figures': 'No numbered figure for this step',
        'empty_phase': 'Unnamed phase', 'no_phases': 'No phases recorded. No route is inferred.',
        'scope': 'The diagram groups recorded steps by phase. Arrows show documentation order, not proven causality '
                 'or successful exploitation. Shortened labels are marked with (...). Full headings and detailed '
                 'steps follow; commands are not used as diagram labels.',
        'part': 'Part', 'of': 'of', 'continued': 'Continued from the preceding part',
        'continues': 'Continues in the following part', 'evidence': 'Linked evidence outside the route',
        'evidence_scope': 'These figures were linked to this machine finding. Their collection is not an attack phase.',
        'alternative': 'Text version',
    },
    'pt': {
        'title': 'Percurso documentado', 'phase': 'Fase', 'step': 'Passo', 'steps': 'Passos registrados',
        'no_lead': 'Sem título de passo registrado',
        'figures': 'Figuras', 'no_figures': 'Sem figura numerada para este passo',
        'empty_phase': 'Fase sem nome', 'no_phases': 'Nenhuma fase registrada. Nenhum percurso é inferido.',
        'scope': 'O diagrama agrupa os passos registrados por fase. As setas mostram a ordem de documentação, '
                 'não causalidade comprovada nem exploração bem-sucedida. Os rótulos abreviados têm (...). '
                 'Os títulos completos e os passos detalhados aparecem a seguir; comandos não são usados como rótulos do diagrama.',
        'part': 'Parte', 'of': 'de', 'continued': 'Continuação da parte anterior',
        'continues': 'Continua na próxima parte', 'evidence': 'Evidência vinculada fora do percurso',
        'evidence_scope': 'Estas figuras foram vinculadas ao achado desta máquina. Sua coleta não é uma fase de ataque.',
        'alternative': 'Versão textual',
    },
    'es': {
        'title': 'Recorrido documentado', 'phase': 'Fase', 'step': 'Paso', 'steps': 'Pasos registrados',
        'no_lead': 'Sin encabezado de paso registrado',
        'figures': 'Figuras', 'no_figures': 'Sin figura numerada para este paso',
        'empty_phase': 'Fase sin nombre', 'no_phases': 'No hay fases registradas. No se infiere una ruta.',
        'scope': 'El diagrama agrupa los pasos registrados por fase. Las flechas muestran el orden de documentación, '
                 'no causalidad probada ni explotación exitosa. Las etiquetas abreviadas llevan (...). Después aparecen '
                 'los encabezados completos y los pasos detallados; los comandos no se usan como etiquetas del diagrama.',
        'part': 'Parte', 'of': 'de', 'continued': 'Continúa desde la parte anterior',
        'continues': 'Continúa en la parte siguiente', 'evidence': 'Evidencia vinculada fuera de la ruta',
        'evidence_scope': 'Estas figuras se vincularon al hallazgo de esta máquina. Su colección no es una fase de ataque.',
        'alternative': 'Versión textual',
    },
}


def _plain(value):
    # Labels are literal source text. Do not parse Markdown, links or resources.
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def _short(value, limit=82):
    value = _plain(value)
    return value if len(value) <= limit else value[:limit - 6].rstrip() + ' (...)'


@lru_cache(maxsize=4)
def _label_font(size):
    return ImageFont.truetype(str(Path(__file__).parent / 'fonts' / 'DejaVuSans.ttf'), size)


def _label_lines(value, width=44, pixel_width=644, size=14):
    """At most two lines; a word-boundary spill must also mark truncation."""
    original = _plain(value)
    wrapped = textwrap.wrap(_short(original), width=width)
    # Wide glyphs (WWW, non-Latin labels) must fit the actual node as well as
    # the character budget. Full source headings remain in native text below.
    font = _label_font(size)
    fitted = []
    for line in wrapped:
        while line and font.getlength(line) > pixel_width:
            cut = len(line) - 1
            while cut > 1 and font.getlength(line[:cut]) > pixel_width:
                cut -= 1
            fitted.append(line[:cut])
            line = line[cut:].lstrip()
        if line:
            fitted.append(line)
    wrapped = fitted
    lines = wrapped[:2]
    if lines and (len(original) > 82 or len(wrapped) > 2):
        if not lines[-1].endswith('(...)'):
            tail = lines[-1].rstrip()
            while tail and font.getlength(tail + ' (...)') > pixel_width:
                tail = tail[:-1].rstrip()
            lines[-1] = tail + ' (...)'
    return lines


def _figures(phase):
    return [step['figure']['number'] for step in phase.get('steps', [])
            if step.get('figure', {}).get('src') and step['figure'].get('number') is not None]


def _svg(rows, words, part, parts, has_figures):
    # Three horizontal steps per phase row, three rows per graphic. This keeps
    # the usual 3-phase / 9-step route in one bounded panel, without shrinking
    # arbitrary inputs. Large routes continue as explicit numbered panels.
    width, stride, top, box_height = 700, 132, 24, 68
    height = top + len(rows) * stride + 16
    svg = ET.Element('svg', {
        'xmlns': 'http://www.w3.org/2000/svg', 'viewBox': f'0 0 {width} {height}',
        'width': str(width), 'height': str(height), 'class': 'machine-route-svg',
        'role': 'img', 'aria-label': f"{words['title']}: {words['part']} {part} {words['of']} {parts}",
    })
    ET.SubElement(svg, 'title').text = svg.get('aria-label')
    ET.SubElement(svg, 'desc').text = words['scope']
    # SVG text has a fixed dark ink. Its complete canvas must therefore remain
    # light, including continuation labels outside the node rectangles.
    ET.SubElement(svg, 'rect', {'x': '0', 'y': '0', 'width': str(width), 'height': str(height),
        'rx': '5', 'fill': '#ffffff', 'class': 'machine-route-canvas'})

    def text(x, y, value, size=15, weight='400'):
        node = ET.SubElement(svg, 'text', {'x': str(x), 'y': str(y), 'fill': '#193245',
            'font-size': str(size), 'font-family': 'DejaVu Sans, sans-serif', 'font-weight': weight})
        node.text = value

    if part > 1:
        text(18, 16, words['continued'], 12)
    for row_index, row in enumerate(rows):
        phase, nodes = row['phase'], row['steps']
        y = top + row_index * stride
        ET.SubElement(svg, 'rect', {'x': '14', 'y': str(y), 'width': '672', 'height': '120',
            'rx': '5', 'fill': '#e4edf2', 'stroke': '#547489', 'stroke-width': '1.4'})
        text(24, y + 16, f"{words['phase']} {phase['number']}  |  {words['steps']}: {phase['step_count']}", 12, '700')
        for line_index, line in enumerate(_label_lines(phase['name'], size=12)):
            text(24, y + 31 + line_index * 13, line, 12)
        for i, node in enumerate(nodes):
            x, card_y = 22 + i * 224, y + 50
            ET.SubElement(svg, 'rect', {'x': str(x), 'y': str(card_y), 'width': '208', 'height': str(box_height),
                'rx': '4', 'fill': '#ffffff', 'stroke': '#547489', 'stroke-width': '1'})
            text(x + 8, card_y + 16, f"{words['step']} {node['number']}", 12, '700')
            for line_index, line in enumerate(_label_lines(node['heading'], width=27, pixel_width=192, size=13)):
                text(x + 8, card_y + 33 + line_index * 15, line, 13)
            if node['figure'] is not None:
                text(x + 8, card_y + 64, f"{words['figures']}: {node['figure']}", 11)
            elif has_figures:
                # A short neutral mark; the full qualified wording is in the
                # native alternative, not an assertion that evidence is absent.
                text(x + 8, card_y + 64, f"{words['figures']}: -", 11)
            if i + 1 < len(nodes):
                ET.SubElement(svg, 'path', {'d': f'M{x + 211} {card_y + 36} H{x + 221} M{x + 217} {card_y + 32} L{x + 221} {card_y + 36} L{x + 217} {card_y + 40}',
                    'fill': 'none', 'stroke': '#547489', 'stroke-width': '1.5'})
    if part < parts:
        text(18, height - 6, words['continues'], 12)
    return Markup(ET.tostring(svg, encoding='unicode'))


def build(finding, documented_phase_count, lang='en'):
    """Consume only the final project_report copy, after figure numbering.

    documented_phase_count is a structural count captured before workflow adds
    its evidence collection. It contributes no source text or identity.
    """
    from languages import normalize_language
    words = WORDS[normalize_language(lang, default='en')]
    phases = finding.get('phases', [])
    nodes = []
    for i, phase in enumerate(phases[:documented_phase_count]):
        steps = []
        for j, step in enumerate(phase.get('steps', [])):
            figure = step.get('figure', {})
            steps.append({'number': f'{i + 1}.{j + 1}',
                          'heading': _plain(step.get('lead')) or words['no_lead'],
                          'figure': figure.get('number') if figure.get('src') else None})
        nodes.append({'number': i + 1, 'name': _plain(phase.get('name')) or words['empty_phase'],
                      'step_count': len(steps), 'steps': steps, 'figures': _figures(phase)})
    linked_figures = [number for phase in phases[documented_phase_count:] for number in _figures(phase)]
    rows = [{'phase': phase, 'steps': phase['steps'][i:i + 3]} for phase in nodes
              for i in (range(0, len(phase['steps']), 3) if phase['steps'] else [0])]
    groups = [rows[i:i + 3] for i in range(0, len(rows), 3)]
    has_figures = any(phase['figures'] for phase in nodes)
    native_length = sum(len(phase['name']) + sum(len(step['heading']) + (45 if has_figures else 0)
                        for step in phase['steps']) for phase in nodes)
    return {'words': words, 'nodes': nodes, 'linked_figures': linked_figures,
            'has_figures': has_figures,
            'compact': len(groups) == 1 and native_length <= 500 and not linked_figures,
            'chunks': [{'rows': group, 'part': i + 1, 'parts': len(groups),
                        'svg': _svg(group, words, i + 1, len(groups), has_figures)}
                       for i, group in enumerate(groups)]}
