"""Observe authored list markers, including portable Word sequence fields.

These checks read native numbering and visible field results. They do not trust
hidden annotations and do not certify a consumer's rendered page geometry.
"""
import re

from error_messages import message

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
NS = {'w': W[1:-1]}


def invalid():
    raise ValueError(message('Numeración de lista alterada', en='List numbering changed'))


def dom_markers(root):
    """Map native li elements to their effective HTML decimal marker."""
    result = {}
    for group in root.xpath('.//ol|.//ul'):
        items = [child for child in group if child.tag == 'li']
        if group.tag == 'ul':
            result.update((item, None) for item in items)
            continue
        if group.get('type', '1') != '1':
            result.update((item, 'non-decimal') for item in items)
            continue
        direction = -1 if 'reversed' in group.attrib else 1
        try:
            value = int(group.get('start', str(len(items) if direction < 0 else 1)))
            for item in items:
                value = int(item.get('value', str(value)))
                result[item] = value
                value += direction
        except (ValueError, OverflowError):
            invalid()
    return result


def word_markers(tree, numbering):
    """Validate native numbering/SEQ results, then remove only visible markers.

    The caller owns this parsed copy. Source archive bytes are never modified.
    Removing a validated SEQ marker lets ordinary content checks compare the
    authored prose; returned ordinals are independently matched to the source.
    """
    def identity(value):
        if not value or not re.fullmatch(r'[0-9]{1,10}', value) or int(value) > 2147483647:
            invalid()
        return str(int(value))

    def indexed(nodes, attribute):
        result = {}
        for node in nodes:
            key = identity(node.get(W+attribute))
            if key in result:
                invalid()
            result[key] = node
        return result

    abstracts = indexed(numbering.findall(W+'abstractNum'), 'abstractNumId')
    nums = indexed(numbering.findall(W+'num'), 'numId')
    levels = {key: indexed(node.findall(W+'lvl'), 'ilvl') for key, node in abstracts.items()}
    overrides = {key: indexed(node.findall(W+'lvlOverride'), 'ilvl') for key, node in nums.items()}
    positions = {}
    sequences = {}
    result = {}

    def value(parent, name, default=None):
        nodes = parent.findall(W+name)
        if len(nodes) > 1:
            invalid()
        return nodes[0].get(W+'val') if nodes else default

    for paragraph in tree.iter(W+'p'):
        props = paragraph.find(W+'pPr/'+W+'numPr')
        if props is None:
            continue
        num_id = identity(value(props, 'numId'))
        level_id = identity(value(props, 'ilvl', '0'))
        try:
            num = nums[num_id]
            abstract_id = identity(value(num, 'abstractNumId'))
            level = levels[abstract_id][level_id]
            override = overrides[num_id].get(level_id)
            if override is not None and override.find(W+'lvl') is not None:
                if len(override.findall(W+'lvl')) != 1:
                    invalid()
                level = override.find(W+'lvl')
            start = int(value(override, 'startOverride', value(level, 'start', '1')) if override is not None else value(level, 'start', '1'))
        except (KeyError, ValueError):
            invalid()
        kind = value(level, 'numFmt')
        key = (num_id, level_id)
        position = positions.get(key, start)
        positions[key] = position + 1
        if kind == 'bullet':
            result[paragraph] = None
            continue
        if kind == 'decimal' and value(level, 'lvlText') == '%1.':
            result[paragraph] = position
            continue
        if kind != 'none':
            result[paragraph] = 'non-decimal'
            continue

        # Only this precise, visible and independently validated field form is
        # eligible for stripping. Arbitrary field text remains ordinary prose.
        children = [node for node in paragraph if node.tag != W+'pPr']
        if len(children) < 2 or children[0].tag != W+'fldSimple' or children[1].tag != W+'r':
            invalid()
        field, delimiter = children[:2]
        match = re.fullmatch(r'\s*SEQ (RGList[0-9]+) \\(r ([0-9]+)|n) \\\* ARABIC\s*', field.get(W+'instr', ''))
        if not match or match[1] != 'RGList'+num_id:
            invalid()
        if (level_id != '0' or start != 1 or value(level, 'lvlText') != ''
                or value(level, 'suff') != 'nothing'):
            invalid()
        sequence = match[1]
        if match[3] is not None:
            if sequence in sequences:
                invalid()
            ordinal = int(match[3])
        else:
            if sequence not in sequences:
                invalid()
            ordinal = sequences[sequence] + 1
        if not 0 <= ordinal <= 2147483647:
            invalid()
        if (len(field) != 1 or field[0].tag != W+'r'
                or [n.tag for n in field[0] if n.tag != W+'rPr'] != [W+'t']
                or ''.join(field.itertext()) != str(ordinal)
                or field.xpath('.//w:vanish|.//w:instrText', namespaces=NS)):
            invalid()
        visible_delimiter = [n for n in delimiter if n.tag != W+'rPr']
        if ([n.tag for n in visible_delimiter] != [W+'t', W+'tab']
                or visible_delimiter[0].text != '.'
                or delimiter.xpath('.//w:vanish', namespaces=NS)):
            invalid()
        sequences[sequence] = ordinal
        result[paragraph] = ordinal
        paragraph.remove(field)
        paragraph.remove(delimiter)
    return result
