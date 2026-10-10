"""Remove project resources from reusable Markdown without rewriting literals.

Markdown's link processors identify candidate source spans. A single marked
render distinguishes prose from code and escapes; a final semantic comparison
refuses any transformation which changed unrelated rendered content.
"""
from error_messages import message as backend_message
from dataclasses import dataclass
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit
from uuid import uuid4

import markdown
from lxml import html
from markdown.blockprocessors import ReferenceProcessor
from markdown.inlinepatterns import (ImageInlineProcessor, ImageReferenceInlineProcessor,
    ShortImageReferenceInlineProcessor, LinkInlineProcessor, ReferenceInlineProcessor,
    ShortReferenceInlineProcessor, IMAGE_LINK_RE, LINK_RE)
from safe_markup import _WidthImage, _SourceControls, _ProseWhitespace, _parsed


def private_destination(value):
    """An anchor or local file belongs to its originating project."""
    # Whole URL variables are intentional template inputs. Instantiation runs
    # this projection again after filling them, when the destination is known.
    if re.fullmatch(r'\{\{\s*[A-Za-z_][A-Za-z0-9_]*\s*\}\}', value.strip()):
        return False
    if re.match(r'^[A-Za-z]:[\\/]', value.strip()):
        return True
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return True
    return parsed.scheme.lower() == 'file' or not (parsed.scheme or parsed.netloc)


def private_reference(value):
    """References rows also accept bibliography prose, not only URL targets.

    Remove clear local paths/anchors. A citation with spaces or an unrecognized
    suffix is ambiguous prose and remains available for the manual review.
    """
    text = value.strip()
    if text.startswith('#') and not re.search(r'\s', text):
        return True
    if re.match(r'^(?:\.{1,2}/|/(?!/)|[A-Za-z]:[\\/])', text):
        return True
    try:
        parsed = urlsplit(text)
    except ValueError:
        return False
    if parsed.scheme or parsed.netloc:
        return parsed.scheme.lower() == 'file'
    file_suffix = bool(re.search(
        r'\.(?:png|jpe?g|gif|webp|svg|html?|pdf|docx?|md|txt|csv|json|ya?ml)(?:[?#][^\s]*)?$', text, re.I))
    no_spaces = not re.search(r'\s', text)
    if re.match(r'^(?:img|originals|history|attachments|api/projects)/', text):
        return no_spaces or file_suffix
    return no_spaces and file_suffix


def _parse(source):
    parser = markdown.Markdown(extensions=['fenced_code', 'tables', 'sane_lists', 'nl2br'], output_format='html5')
    # Match the report parser's literal-code treatment. Raw HTML is enabled only
    # for this inspection, so prose <img>/<a> tags also lose project resources.
    parser.preprocessors.deregister('html_block')
    parser.preprocessors.register(parser.preprocessors['fenced_code_block'], 'fenced_code_block', 35)
    parser.preprocessors.register(_SourceControls(parser), 'source_controls', 40)
    parser.preprocessors.register(_ProseWhitespace(parser), 'normalize_whitespace', 30)
    parser.inlinePatterns.register(_WidthImage(IMAGE_LINK_RE, parser), 'image_link', 150)
    return parser, html.fragment_fromstring(parser.convert(source), create_parent='div')


def _project(tree):
    for node in tree.xpath('.//img[not(ancestor::code or ancestor::pre)]'):
        node.drop_tree()
    for node in tree.xpath('.//a[@href][not(ancestor::code or ancestor::pre)]'):
        if private_destination(node.get('href')):
            node.drop_tag()
    # Removing the only image can leave an empty paragraph or external link.
    for node in reversed(tree.xpath('.//p | .//a')):
        if len(node) == 0 and not (node.text or '').strip():
            node.drop_tree()
    if tree.text and not tree.text.strip():
        tree.text = None
    for node in tree.xpath('.//p'):
        if node.text:
            node.text = node.text.lstrip()
    for node in tree.iterdescendants():
        if (node.tail and not node.tail.strip() and node.getparent().tag in
                {'div', 'ul', 'ol', 'li', 'blockquote', 'table', 'thead', 'tbody', 'tr', 'td', 'th'}):
            node.tail = None
    return html.tostring(tree, encoding='unicode')


@dataclass
class _Span:
    start: int
    end: int
    replacement: str


def _text(data, index, budget=None):
    """Source coordinates, including escaped brackets not yet in a stash."""
    start = index
    depth = 1
    while index < len(data):
        if budget is not None:
            budget[0] -= 1
            if budget[0] < 0:
                raise ValueError(backend_message('Demasiado Markdown para analizar sus referencias; divide el contenido de la plantilla'))
        char = data[index]
        if char == '\\' and index + 1 < len(data):
            index += 2
            continue
        if char == '[':
            depth += 1
        elif char == ']':
            depth -= 1
            if depth == 0:
                return data[start:index], index + 1, True
        index += 1
    return '', index, False


def _escaped(source, position):
    start = position
    while start and source[start - 1] == '\\':
        start -= 1
    return (position - start) % 2 == 1


class _Tags(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source, self.spans, self.anchors = source, [], []
        self.lines = [0] + [m.end() for m in re.finditer('\n', source)]

    def position(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag, attrs):
        start = self.position()
        end = start + len(self.get_starttag_text())
        if tag == 'img':
            self.spans.append(_Span(start, end, ''))
        if tag == 'a':
            destination = dict(attrs).get('href')
            private = destination is not None and private_destination(destination)
            self.anchors.append(private)
            if private:
                self.spans.append(_Span(start, end, ''))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == 'a' and self.anchors and self.anchors.pop():
            start = self.position()
            self.spans.append(_Span(start, self.source.index('>', start) + 1, ''))


def _spans(source, parser, tree):
    scan_budget = [32 * 1024 * 1024]
    def source_text(data, index):
        return _text(data, index, scan_budget)
    processors = [cls(IMAGE_LINK_RE if image else LINK_RE, parser)
        for image, classes in ((True, (ImageInlineProcessor, ImageReferenceInlineProcessor, ShortImageReferenceInlineProcessor)),
                               (False, (LinkInlineProcessor, ReferenceInlineProcessor, ShortReferenceInlineProcessor)))
        for cls in classes]
    for processor in processors:
        processor.getText = source_text
    spans = []
    for bracket in re.finditer(r'\[', source):
        if _escaped(source, bracket.start()):
            continue
        position = bracket.start()
        image = position > 0 and source[position - 1] == '!' and not _escaped(source, position - 1)
        match = re.compile(r'!?\[').match(source, position - 1 if image else position)
        label, _, handled = source_text(source, match.end())
        if not handled:
            continue
        for processor in processors[:3] if image else processors[3:]:
            node, start, end = processor.handleMatch(match, source)
            if node is not None:
                if image or private_destination(node.get('href', '')):
                    if image:
                        attrs = re.match(r'\{[^}]*\}', source[end:])
                        if attrs:
                            end += attrs.end()
                    spans.append(_Span(start, end, '' if image else label))
                break
    image_urls = {node.get('src') for node in tree.xpath('.//img')}
    link_urls = {node.get('href') for node in tree.xpath('.//a[@href]')}
    for match in ReferenceProcessor.RE.finditer(source):
        destination = match[2].lstrip('<').rstrip('>')
        if private_destination(destination) or (destination in image_urls and destination not in link_urls):
            spans.append(_Span(match.start(), match.end(), ''))
    tags = _Tags(source)
    tags.feed(source)
    spans.extend(tags.spans)
    # An outer internal link is unwrapped first; its image label is removed on
    # the next pass. The parser, rather than overlapping substitutions, decides.
    selected = []
    for span in sorted(spans, key=lambda x: (x.start, -x.end)):
        if not selected or span.start >= selected[-1].end:
            selected.append(span)
    return selected


def _apply(source, spans, replacements):
    pieces, position = [], 0
    for span, replacement in zip(spans, replacements):
        pieces.extend((source[position:span.start], replacement))
        position = span.end
    return ''.join(pieces) + source[position:]


def sanitize_markdown(source):
    """Preserve labels and exact source code; fail closed on ambiguous syntax."""
    if not source:
        return source
    parser, tree = _parse(source)
    expected = _project(tree)
    budget = 128 * 1024 * 1024
    for _ in range(8):
        budget -= 3 * len(source.encode('utf-8'))
        if budget < 0:
            raise ValueError(backend_message('Demasiado Markdown para sanearlo de forma segura; divide el contenido de la plantilla'))
        parser, tree = _parse(source)
        spans = _spans(source, parser, tree)
        if len(spans) > 4096:
            raise ValueError(backend_message('Demasiadas referencias en la plantilla; divide el contenido'))
        if not spans:
            break
        markers = ['RGREUSABLE' + uuid4().hex for _ in spans]
        _, probe = _parse(_apply(source, spans, markers))
        prose = ''.join(probe.xpath('.//text()[not(ancestor::code or ancestor::pre)]'))
        active = [(span, marker) for span, marker in zip(spans, markers) if marker in prose]
        if not active:
            break
        source = _apply(source, [span for span, _ in active], [span.replacement for span, _ in active])
    _, final = _parse(source)
    # HTML <code> is not a literal fence in the report parser, which displays
    # raw HTML as text. Verify its real projection too before accepting output.
    report = html.fragment_fromstring(_parsed(source), create_parent='div')
    if (final.xpath('.//img[not(ancestor::code or ancestor::pre)]') or any(private_destination(node.get('href')) for node in final.xpath('.//a[@href][not(ancestor::code or ancestor::pre)]'))
            or report.xpath('.//img') or any(private_destination(node.get('href')) for node in report.xpath('.//a[@href]'))
            or _project(final) != expected):
        raise ValueError(backend_message('No se puede retirar la referencia sin alterar el texto; revisa el Markdown de la plantilla'))
    return source
