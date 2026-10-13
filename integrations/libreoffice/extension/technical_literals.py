"""Optional Writer wrapping for explicitly marked, nonlinguistic ASCII literals.

MIT license; see LICENSE in the extension. No source text or link is rewritten.
The specific locale service avoids replacing any general qlt/Unicode iterator.
"""
from bisect import bisect_right
from functools import lru_cache
import re

import unohelper
from com.sun.star.i18n import XBreakIterator
from com.sun.star.lang import XServiceInfo

LANGUAGE_TAG = "zxx-ZZ-x-rgwrap"
SERVICE = "com.sun.star.i18n.BreakIterator_qlt_ZZ_zxx-ZZ-x-rgwrap"
IMPLEMENTATION = "org.reportgen.TechnicalLiteralBreakIterator"
_ASCII_TOKEN = re.compile(r"[!-~]{24,}")
_TECHNICAL_MARKER = re.compile(r"[0-9_/:]")
_URI = re.compile(r"(?:https?|ftps?)://", re.IGNORECASE)


@lru_cache(maxsize=1)
def _eligible_intervals(text):
    """Cache at most one paragraph; count its UTF-16 offsets in one forward pass."""
    starts, ends = [], []
    previous, units = 0, 0
    for match in _ASCII_TOKEN.finditer(text):
        token = match.group()
        units += len(text[previous:match.start()].encode("utf-16-le")) // 2
        first = units
        units += len(token)  # ASCII: one UTF-16 code unit each.
        previous = match.end()
        if _TECHNICAL_MARKER.search(token) and not (_URI.search(token) and len(token) < 32):
            starts.append(first)
            ends.append(units)
    return tuple(starts), tuple(ends)


def eligible_ascii_cut(text, start, minimum):
    """Check the available UTF-16 cut without splitting Unicode graphemes.

    Non-BMP prose before a token counts twice. Natural words containing letters
    alone remain untouched. A changed paragraph invalidates the one-entry cache.
    """
    if start <= minimum:
        return False
    starts, ends = _eligible_intervals(text)
    index = bisect_right(starts, start) - 1
    return index >= 0 and starts[index] < start < ends[index]


class TechnicalLiteralIterator(unohelper.Base, XBreakIterator, XServiceInfo):
    def __init__(self, context):
        self.delegate = context.ServiceManager.createInstanceWithContext(
            "com.sun.star.i18n.BreakIterator_Unicode", context)

    def getImplementationName(self):
        return IMPLEMENTATION

    def supportsService(self, name):
        return name == SERVICE

    def getSupportedServiceNames(self):
        return (SERVICE,)

    def getLineBreak(self, text, start, locale, minimum, hyphenation, options):
        result = self.delegate.getLineBreak(text, start, locale, minimum, hyphenation, options)
        if (locale.Language == "qlt" and locale.Country == "ZZ"
                and locale.Variant == LANGUAGE_TAG and eligible_ascii_cut(text, start, minimum)):
            result.breakIndex = start
            result.breakType = 0  # com.sun.star.i18n.LineBreakType.WORDBOUNDARY
            result.rHyphenatedWord = None
        return result

    def __getattr__(self, name):
        return getattr(self.delegate, name)


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(TechnicalLiteralIterator, IMPLEMENTATION, (SERVICE,))
