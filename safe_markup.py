"""Markdown rendering shared by HTML, PDF and DOCX."""
from contextvars import ContextVar
from html import escape
import re
import markdown
import nh3
from markupsafe import Markup
from resources import relative_image

_BASE = ContextVar("report_image_base", default="")
IMG_RE = re.compile(r'!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+)(?:\s+"[^"]*")?\)(?:\{(?P<attrs>[^}]*)\})?')
WIDTH = re.compile(r"(?:\d+(?:\.\d+)?)(?:%|px|cm|mm|in|pt)")
TAGS = {"p", "br", "hr", "strong", "em", "b", "i", "del", "s", "code", "pre", "blockquote", "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "thead", "tbody", "tr", "th", "td", "a", "img", "figure", "figcaption"}


def set_img_base(base):
    _BASE.set(base or "")


def _image(match):
    alt = escape(match.group("alt").strip(), quote=True)
    src = match.group("src")
    try:
        path = relative_image(src)
    except ValueError:
        return escape(match.group(0))
    src = _BASE.get() + path.as_posix()
    width = re.search(r'width\s*=\s*"?([^"\s]+)', match.group("attrs") or "")
    style = f' style="width:{width[1]}"' if width and WIDTH.fullmatch(width[1]) else ""
    return f'<figure class="mdfig"><img src="{escape(src, quote=True)}" alt="{alt}"{style}><figcaption>{alt}</figcaption></figure>'


def _preprocess(text):
    lines, fence = [], None
    for line in str(text).split("\n"):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if marker:
            if fence is None:
                fence = marker[1]
            elif marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            lines.append(line)
        elif fence:
            lines.append(line)
        else:
            parts = re.split(r"(`+[^`]*`+)", line)
            lines.append("".join(p if p.startswith("`") else IMG_RE.sub(_image, p.replace("<", "&lt;").replace(">", "&gt;")) for p in parts))
    return "\n".join(lines)


def _attribute(tag, attr, value):
    if attr == "style":
        if tag == "img" and re.fullmatch(r"width:\s*\d+(?:\.\d+)?(?:%|px|cm|mm|in|pt);?", value):
            return value
        return None
    if tag == "img" and attr == "src":
        base = _BASE.get()
        try:
            relative_image(value[len(base):] if base and value.startswith(base) else value)
        except ValueError:
            return None
    return value


def md(text, img_base=None):
    token = _BASE.set(img_base) if img_base is not None else None
    try:
        converted = markdown.markdown(_preprocess(text or ""), extensions=["fenced_code", "tables", "sane_lists", "nl2br"], output_format="html5")
        cleaned = nh3.clean(converted, tags=TAGS,
            attributes={"a": {"href", "title"}, "img": {"src", "alt", "style"}, "figure": {"class"}, "code": {"class"}, "th": {"align"}, "td": {"align"}, "ol": {"start"}},
            attribute_filter=_attribute, url_schemes={"http", "https", "mailto", "file"},
            link_rel="noopener noreferrer", strip_comments=True)
        # File links are never navigable; file images only come from the trusted base.
        from lxml import html
        root = html.fragment_fromstring(cleaned, create_parent="div")
        for a in root.xpath(".//a[@href]"):
            if a.get("href", "").lower().startswith("file:"):
                del a.attrib["href"]
        return Markup((escape(root.text) if root.text else "") + "".join(html.tostring(c, encoding="unicode") for c in root))
    finally:
        if token is not None:
            _BASE.reset(token)


def md_inline(text):
    value = str(md(text)).strip()
    if value.startswith("<p>") and value.endswith("</p>") and value.count("<p>") == 1:
        value = value[3:-4]
    return Markup(value)
