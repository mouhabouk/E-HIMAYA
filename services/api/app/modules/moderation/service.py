"""Respectful-language filter (rule 4, docs/phase-a/design.md §2.6).

``check`` refuses (``422 offensive_text``) free text that contains a word of the built-in list or of the setting
``moderation.extra_terms``. It is used on non-emergency text only (profile names, address, later messages to the
Office and institution forms). It is **never** called on reports, report descriptions, SOS or anything a person in
danger writes: a frightened citizen must never be refused help because of the words used.

``masks`` is the other side: it never refuses anything and never changes the stored text. It says where the obscene
and insulting words of a report text are, so the staff screens show a shaded block in another colour in their place
(``hide``), and where threats, incitement to violence or hatred and terrorism are, which stay readable but shaded red
(``flag``): the operator must read what the citizen reported.
"""

from collections.abc import Iterable
from functools import lru_cache

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.moderation.normalize import located_tokens, tokens, variants
from app.modules.moderation.terms import BUILT_IN, FLAGGED, HIDDEN, MaskKind
from app.modules.settings import domain as settings_domain
from app.modules.settings import service as settings

OFFENSIVE_TEXT = "offensive_text"

# Single words, and several-word phrases.
Compiled = tuple[frozenset[str], tuple[tuple[str, ...], ...]]


def compile_terms(terms: Iterable[str]) -> Compiled:
    """Single words, and several-word phrases, normalised the same way as the text."""
    words: set[str] = set()
    phrases: list[tuple[str, ...]] = []
    for term in terms:
        normalised = tuple(tokens(term))
        if len(normalised) == 1:
            words.add(normalised[0])
        elif normalised:
            phrases.append(normalised)
    return frozenset(words), tuple(phrases)


@lru_cache(maxsize=1)
def _built_in() -> Compiled:
    return compile_terms(BUILT_IN)


@lru_cache(maxsize=1)
def _hidden() -> Compiled:
    return compile_terms(HIDDEN)


@lru_cache(maxsize=1)
def _flagged() -> Compiled:
    return compile_terms(FLAGGED)


def _matches(words: list[str], *lists: Compiled) -> list[tuple[int, int]]:
    """``(first, last)`` word indices of each match, a phrase's first word may carry an Arabic prefix (والعن ← العن)."""
    single: frozenset[str] = frozenset[str]().union(*(w for w, _ in lists))
    phrases = [p for _, ps in lists for p in ps]
    found: list[tuple[int, int]] = []
    for start, word in enumerate(words):
        forms = variants(word)
        if forms & single:
            found.append((start, start))
        for phrase in phrases:
            if phrase[0] in forms and tuple(words[start + 1 : start + len(phrase)]) == phrase[1:]:
                found.append((start, start + len(phrase) - 1))
    return found


def is_offensive(text: str, extra_terms: Iterable[str] = ()) -> bool:
    words = tokens(text)
    return bool(words) and bool(_matches(words, _built_in(), compile_terms(extra_terms)))


def _utf16(text: str, index: int) -> int:
    return len(text[:index].encode("utf-16-le")) // 2


def _merged(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def masks(text: str | None) -> list[tuple[int, int, MaskKind]]:
    """Where the words to hide (``hide``) or to shade red (``flag``) are in ``text``: sorted, non-overlapping
    ``(start, end, kind)`` offsets in UTF-16 code units (the string indices of the dashboard and of the app), end
    excluded. A word that is both is hidden. Empty when there is nothing."""
    if not text:
        return []
    located = located_tokens(text)
    words = [w for w, _, _ in located]

    def spans(terms: Compiled) -> list[tuple[int, int]]:
        return _merged([(located[first][1], located[last][2]) for first, last in _matches(words, terms)])

    hidden = spans(_hidden())
    flagged = [(s, e) for s, e in spans(_flagged()) if not any(s < he and hs < e for hs, he in hidden)]
    found: list[tuple[int, int, MaskKind]] = [(s, e, "hide") for s, e in hidden]
    found += [(s, e, "flag") for s, e in flagged]
    return [(_utf16(text, s), _utf16(text, e), kind) for s, e, kind in sorted(found)]


async def check(session: AsyncSession, *texts: str | None) -> None:
    """Raise ``422 offensive_text`` if one of ``texts`` is offensive. Never use on reports or SOS."""
    extra = await settings.get(session, settings_domain.MODERATION_EXTRA_TERMS)
    for text in texts:
        if text and is_offensive(text, extra or ()):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, OFFENSIVE_TEXT)
