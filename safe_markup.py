"""One Markdown parser for code, image references and all report formats."""
from error_messages import message as backend_message
from contextvars import ContextVar
from html import escape
import re
import markdown
from markdown.preprocessors import Preprocessor
from markdown.treeprocessors import Treeprocessor
from markdown.inlinepatterns import ImageInlineProcessor, IMAGE_LINK_RE
import nh3
from markupsafe import Markup
from resources import relative_image
from urllib.parse import quote

_BASE = ContextVar('report_image_base', default='')
WIDTH = re.compile(r'(?:\d+(?:\.\d+)?)(?:%|px|cm|mm|in|pt)')
_NUMERIC_REFERENCE = re.compile(r'&#(?:[xX]([0-9a-fA-F]+)|([0-9]+));')
TAGS = {'p', 'br', 'hr', 'strong', 'em', 'b', 'i', 'del', 's', 'code', 'pre', 'blockquote', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'a', 'img', 'figure', 'figcaption'}


def ordered_list_start(node):
    """Keep counters within the range shared by browser and Word consumers."""
    value = node.get('start', '1').lstrip('0') or '0'
    limit = 2**31 - 1
    message = backend_message('Lista: la numeración excede 2147483647. Reinicia la lista o '
               'presenta esos identificadores como texto. / List numbering '
               'exceeds 2147483647; restart the list or use plain-text identifiers.')
    if (not value.isascii() or not value.isdigit() or len(value) > 10
            or (len(value) == 10 and value > str(limit))):
        raise ValueError(message)
    start = int(value)
    count = sum(child.tag == 'li' for child in node)
    if start + max(0, count - 1) > limit:
        raise ValueError(message)
    return start


def set_img_base(base):
    _BASE.set(base or '')


class _WidthImage(ImageInlineProcessor):
    def handleMatch(self, match, data):
        element, start, end = super().handleMatch(match, data)
        if element is not None and end is not None:
            attrs = re.match(r'\{([^}]*)\}', data[end:])
            if attrs:
                width = re.search(r'width\s*=\s*"?([^"\s]+)', attrs[1])
                if width and WIDTH.fullmatch(width[1]): element.set('style', 'width:'+width[1])
                end += attrs.end()
        return element, start, end


class _SourceControls(Preprocessor):
    def run(self, lines):
        # User text cannot forge the parser's stash delimiters.
        return [line.replace('\x02', '').replace('\x03', '') for line in lines]


class _ProseWhitespace(Preprocessor):
    def run(self, lines):
        # Fenced blocks are already escaped in htmlStash. Expand only prose;
        # retain the parser-generated stash delimiters so code is restored.
        source = ('\n'.join(lines) + '\n\n').expandtabs(self.md.tab_length)
        return re.sub(r'(?<=\n) +\n', '\n', source).split('\n')


def _literal_fence(source, language, class_name, options, parser, **kwargs):
    """Emit inert code only; SuperFences owns nesting and source tokenization."""
    language_class = ' class="language-' + escape(language, quote=True) + '"' if language else ''
    # SuperFences joins content lines without their final newline. Its 12.2
    # line_count distinguishes zero lines from one empty line, both source=''.
    # Pin that version: this parser detail is covered by literal-boundary tests.
    final_newline = '\n' if parser.preprocessors['fenced_code_block'].line_count else ''
    return '<pre><code' + language_class + '>' + escape(source) + final_newline + '</code></pre>'


def markdown_parser(*, raw_inline_html=False):
    """Shared parser for publication and reusable-resource inspection."""
    parser = markdown.Markdown(
        extensions=['pymdownx.superfences', 'tables', 'sane_lists', 'nl2br'],
        extension_configs={'tables': {'use_align_attribute': True}, 'pymdownx.superfences': {
            'custom_fences': [{'name': '*', 'class': '', 'format': _literal_fence}],
        }}, output_format='html5')
    if not raw_inline_html:
        parser.inlinePatterns.deregister('html')
    parser.preprocessors.deregister('html_block')
    # Protect complete fences before prose normalization, just as the former
    # root-only fenced_code parser did. SuperFences owns nesting and indentation.
    # Do not use preserve_tabs: its raw-stash pass adds a line to empty fences.
    parser.preprocessors.register(parser.preprocessors['fenced_code_block'], 'fenced_code_block', 35)
    parser.preprocessors.register(_SourceControls(parser), 'source_controls', 40)
    parser.preprocessors.register(_ProseWhitespace(parser), 'normalize_whitespace', 30)
    parser.inlinePatterns.register(_WidthImage(IMAGE_LINK_RE, parser), 'image_link', 150)
    parser.treeprocessors.register(_NestingLimit(parser), 'nesting_limit', 5)
    return parser


class _NestingLimit(Treeprocessor):
    def run(self, root):
        # libxml's recovery parser silently discards nodes beyond its nesting
        # limit. Reject deeply nested authored structure before serializing it,
        # leaving room for report wrappers and preserving source text on disk.
        pending = [(root, 0)]
        while pending:
            node, depth = pending.pop()
            if depth > 128:
                raise ValueError(backend_message(
                    'Markdown: demasiados niveles de anidación; reduce las citas o listas anidadas',
                    en='Markdown: too many nesting levels; reduce nested quotes or lists'))
            pending.extend((child, depth + 1) for child in node)


def _parsed(text):
    parser = markdown_parser()
    rendered = parser.convert(str(text or '').replace('\r\n', '\n').replace('\r', '\n'))
    # Code spans/fences have already escaped their ampersands. Inspect only
    # real character references, before HTML sanitizers can replace NUL or
    # invalid Unicode silently and before Word attempts to build XML text.
    from input_guard import NONPORTABLE_TEXT
    for match in _NUMERIC_REFERENCE.finditer(rendered):
        digits = (match[1] or match[2]).lstrip('0') or '0'
        base = 16 if match[1] is not None else 10
        # Avoid Python's integer-string limit for untrusted oversized entities.
        value = int(digits, base) if len(digits) <= (6 if base == 16 else 7) else 0x110000
        if value > 0x10FFFF or NONPORTABLE_TEXT.fullmatch(chr(value)):
            raise ValueError(backend_message(
                'Markdown contiene una referencia a un carácter no compatible con los informes. Escríbela como código o escapa el ampersand para mostrarla literalmente.',
                en='Markdown contains a character reference that reports do not support. Use code formatting or escape the ampersand to display it literally.'))
    return rendered


def validate_character_references(text):
    """Validate decoded Markdown controls without rejecting literal examples."""
    if '&#' in text:
        _parsed(text)


def raw_image_sources(text):
    """Rendered destinations before URL normalization, excluding code examples."""
    from lxml import html
    root = html.fragment_fromstring(_parsed(text), create_parent='div')
    return {node.get('src') for node in root.xpath('.//img[@src]')}


def replace_image_destinations(text, old, new):
    """Edit source destinations only; prove that all other rendered data is intact.

    Unique probe URLs identify source occurrences used by the Markdown parser.
    A semantic comparison protects code, labels and prose, including nested
    blocks. Reference labels which themselves contain a filename need the
    bounded individual-probe fallback. No regex attempts to parse code blocks.
    """
    from lxml import html
    from uuid import uuid4
    canonical = relative_image(old)
    def same(source):
        try: return relative_image(source) == canonical
        except ValueError: return False
    budget = 128 * 1024 * 1024
    def parse(source):
        nonlocal budget
        budget -= len(source.encode('utf-8'))
        if budget < 0:
            raise ValueError(backend_message('Demasiadas referencias para una edición segura; divide el campo Markdown'))
        return html.fragment_fromstring(_parsed(source), create_parent='div')
    def destinations(tree):
        return [(node, 'src' if node.tag == 'img' else 'href')
                for node in tree.xpath('.//img[@src] | .//a[@href]')]
    def fingerprint(tree):
        for node, attr in destinations(tree):
            if same(node.get(attr)): node.set(attr, new)
        return html.tostring(tree, encoding='unicode')
    initial = parse(text)
    original_html = html.tostring(initial, encoding='unicode')
    sources = {node.get(attr) for node, attr in destinations(initial) if same(node.get(attr))}
    if not sources: return text
    expected = fingerprint(initial)
    aliases = sources | {old, canonical.as_posix(), quote(canonical.as_posix(), safe='/')}
    pattern = re.compile(r'(?<![\w./%:+-])(?:' + '|'.join(re.escape(x) for x in sorted(aliases, key=len, reverse=True)) + r')(?![\w./%:+-])')
    matches = list(pattern.finditer(text))
    if len(matches) > 4096:
        raise ValueError(backend_message('Demasiadas referencias para una edición segura'))
    def apply(indices, values=None):
        result = []; position = 0
        for i in sorted(indices):
            match = matches[i]
            result.extend((text[position:match.start()], values[i] if values else new))
            position = match.end()
        return ''.join(result) + text[position:]
    markers = {i: 'img/rg-probe-' + uuid4().hex + '.png' for i in range(len(matches))}
    probe_sources = {node.get(attr) for node, attr in destinations(parse(apply(markers, markers)))}
    selected = {i for i, marker in markers.items() if marker in probe_sources}
    result = apply(selected)
    tree = parse(result)
    complete = not any(same(node.get(attr)) for node, attr in destinations(tree))
    if complete and fingerprint(tree) == expected: return result
    # A filename used as a reference label cannot be replaced by a unique
    # marker at every occurrence without breaking that reference's identity.
    selected = set()
    for i in range(len(matches)):
        candidate = parse(apply({i}))
        changed = html.tostring(candidate, encoding='unicode') != original_html
        if changed and fingerprint(candidate) == expected:
            selected.add(i)
    result = apply(selected)
    final = parse(result)
    if (any(same(node.get(attr)) for node, attr in destinations(final))
            or fingerprint(final) != expected):
        raise ValueError(backend_message('No se puede actualizar la referencia sin alterar el texto; el proyecto se conserva'))
    return result


def _attribute(tag, attr, value):
    if attr == 'style':
        return value if tag == 'img' and re.fullmatch(r'width:\s*\d+(?:\.\d+)?(?:%|px|cm|mm|in|pt);?', value) else None
    if tag == 'img' and attr == 'src':
        try: relative_image(value)
        except ValueError: return None
    return value


def md(text, img_base=None):
    token = _BASE.set(img_base) if img_base is not None else None
    try:
        cleaned = nh3.clean(_parsed(text), tags=TAGS,
            attributes={'a': {'href', 'title'}, 'img': {'src', 'alt', 'style'}, 'figure': {'class'}, 'code': {'class'}, 'th': {'align'}, 'td': {'align'}, 'ol': {'start'}},
            attribute_filter=_attribute, url_schemes={'http', 'https', 'mailto', 'file'},
            link_rel='noopener noreferrer', strip_comments=True)
        from lxml import html
        root = html.fragment_fromstring(cleaned, create_parent='div')
        # These markers originate in the shared parser, not in accepted HTML.
        # Delivery checks use them to distinguish authored headings from the
        # report's generated titles and verify that they survive every export.
        for heading in root.xpath('.//h1|.//h2|.//h3|.//h4|.//h5|.//h6'):
            heading.set('data-rg-authored-heading', 'true')
        # Preserve Markdown's colon alignment without accepting source CSS.
        # Word reads the align attribute; browsers and WeasyPrint need the
        # explicit generated style to override theme header defaults reliably.
        for cell in root.xpath('.//th[@align]|.//td[@align]'):
            alignment = cell.get('align')
            if alignment in {'left', 'center', 'right'}:
                cell.set('style', 'text-align:' + alignment)
            else:
                del cell.attrib['align']
        for ordered in root.xpath('.//ol'):
            start = ordered_list_start(ordered)
            # WeasyPrint ignores HTML presentational hints by default. This
            # generated value preserves authored starts without accepting CSS
            # from source text or enabling unrelated presentational hints.
            if start != 1:
                ordered.set('style', 'counter-reset:list-item ' + str(start - 1))
        for link in root.xpath('.//a[@href]'):
            if link.get('href', '').lower().startswith('file:'): del link.attrib['href']
        for img in root.xpath('.//img'):
            if 'src' not in img.attrib:
                img.drop_tag()
                continue
            path = relative_image(img.get('src'))
            img.set('src', _BASE.get()+quote(path.as_posix(), safe='/'))
            figure = html.Element('figure', {'class': 'mdfig'})
            caption = html.Element('figcaption'); caption.text = img.get('alt', '')
            parent = img.getparent()
            if parent.tag == 'p' and len(parent) == 1 and not (parent.text or '').strip() and not (img.tail or '').strip():
                figure.tail = parent.tail
                parent.getparent().replace(parent, figure)
                img.tail = None
            else:
                figure.tail = img.tail; img.tail = None
                parent.replace(img, figure)
            figure.append(img); figure.append(caption)
        return Markup((escape(root.text) if root.text else '')+''.join(html.tostring(c, encoding='unicode') for c in root))
    finally:
        if token is not None: _BASE.reset(token)


def md_inline(text):
    value = str(md(text)).strip()
    if value.startswith('<p>') and value.endswith('</p>') and value.count('<p>') == 1:
        value = value[3:-4]
    return Markup(value)
