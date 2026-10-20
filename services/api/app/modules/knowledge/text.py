"""Text helpers of the events library: Arabic/French normalisation, query terms, safe highlighted excerpts.

Excerpts are HTML built here, never by the search engine: the text is escaped and only ``<mark>`` / ``</mark>`` are
added around matched words, so nothing a citizen or an engine wrote can reach the dashboard as markup.
"""

import html
import re
import unicodedata

from app.core.crypto import search_terms

EXCERPT_CHARS = 280
MAX_TERMS = 12
# Sentinels the OpenSearch highlighter puts around fragments (control characters never found in stored text).
HL_OPEN, HL_CLOSE = "\x02", "\x03"
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_AR_PREFIXES = ("وال", "بال", "فال", "كال", "لل", "ال")
_ARABIC_MARKS = "[ؐ-ًؚ-ٰٟۖ-ۭـ]*"
# Letters matched together in excerpts (same folding as the blind index and ``normalise``).
_EQUIVALENT = {
    "ا": "اأإآٱ",
    "ي": "يىئ",
    "ه": "هة",
    "و": "وؤ",
    "a": "aàâä",
    "c": "cç",
    "e": "eéèêë",
    "i": "iîï",
    "o": "oôö",
    "u": "uùûü",
}


_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})
_MARKS_RE = re.compile(_ARABIC_MARKS.removesuffix("*"))
_WORD = re.compile(r"\w{2,}")


def normalise(text: str) -> str:
    """Folded words of ``text`` (case, Latin accents, Arabic diacritics and letter variants), in order: the same
    folding as the blind index of encrypted texts (``crypto.search_terms``), without its de-duplication."""
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(c for c in folded if not unicodedata.combining(c) or "\u0600" <= c <= "\u06ff")
    folded = _MARKS_RE.sub("", unicodedata.normalize("NFKC", folded)).translate(_FOLD)
    return " ".join(_WORD.findall(folded))


def query_terms(query: str) -> list[str]:
    """Folded words of a query, with the Arabic article stripped as an extra variant ("الحريق" → "حريق")."""
    terms: list[str] = []
    for word in search_terms(query):
        if word.isdigit() and len(word) < 4:
            continue
        variants = [word]
        for prefix in _AR_PREFIXES:
            if word.startswith(prefix) and len(word) - len(prefix) >= 3:
                variants.append(word[len(prefix) :])
                break
        for variant in variants:
            if variant not in terms:
                terms.append(variant)
    return terms[:MAX_TERMS]


def _pattern(term: str) -> str:
    parts = []
    for char in term:
        options = _EQUIVALENT.get(char)
        parts.append((f"[{options}]" if options else re.escape(char)) + _ARABIC_MARKS)
    return "".join(parts)


def term_regex(terms: list[str]) -> re.Pattern[str] | None:
    if not terms:
        return None
    alternatives = sorted({_pattern(t) for t in terms}, key=len, reverse=True)
    # Whole words or word starts (Arabic and French words carry suffixes); prefixes "و/ب/ف/ل/ال" may precede.
    return re.compile(r"(?<!\w)(?:[وبفكل]?(?:ال)?)(?:" + "|".join(alternatives) + r")\w*", re.IGNORECASE)


def _clean(text: str) -> str:
    return _CONTROL.sub(" ", " ".join(text.split()))


def excerpt(text: str, terms: list[str], limit: int = EXCERPT_CHARS) -> str:
    """An escaped window of ``text`` around the first match, matches wrapped in <mark>."""
    text = _clean(unicodedata.normalize("NFC", text))
    regex = term_regex(terms)
    first = regex.search(text) if regex else None
    start = 0
    if first is not None and first.start() > limit // 3:
        start = text.rfind(" ", 0, first.start() - limit // 3) + 1
    end = min(len(text), start + limit)
    if end < len(text):
        space = text.rfind(" ", start, end)
        end = space if space > start + limit // 2 else end
    window = text[start:end]
    out: list[str] = ["…" if start > 0 else ""]
    position = 0
    if regex is not None:
        for match in regex.finditer(window):
            out.append(html.escape(window[position : match.start()], quote=False))
            out.append("<mark>" + html.escape(match.group(0), quote=False) + "</mark>")
            position = match.end()
    out.append(html.escape(window[position:], quote=False))
    if end < len(text):
        out.append("…")
    return "".join(out)


def from_highlight(fragment: str) -> str:
    """OpenSearch fragment with sentinel tags → escaped HTML with <mark> only."""
    pieces: list[str] = []
    for index, chunk in enumerate(re.split(f"[{HL_OPEN}{HL_CLOSE}]", fragment)):
        escaped = html.escape(_CONTROL.sub(" ", chunk), quote=False)
        pieces.append(f"<mark>{escaped}</mark>" if index % 2 == 1 and escaped else escaped)
    return " ".join("".join(pieces).split())
