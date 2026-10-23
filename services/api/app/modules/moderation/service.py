"""Respectful-language filter (rule 4, docs/phase-a/design.md §2.6).

``check`` refuses (``422 offensive_text``) free text that contains a word of the built-in list or of the setting
``moderation.extra_terms``. It is used on non-emergency text only (profile names, address, later messages to the
Office and institution forms). It is **never** called on reports, report descriptions, SOS or anything a person in
danger writes: a frightened citizen must never be refused help because of the words used.
"""

from collections.abc import Iterable
from functools import lru_cache

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.moderation.normalize import tokens, variants
from app.modules.moderation.terms import BUILT_IN
from app.modules.settings import domain as settings_domain
from app.modules.settings import service as settings

OFFENSIVE_TEXT = "offensive_text"


def compile_terms(terms: Iterable[str]) -> tuple[frozenset[str], tuple[tuple[str, ...], ...]]:
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
def _built_in() -> tuple[frozenset[str], tuple[tuple[str, ...], ...]]:
    return compile_terms(BUILT_IN)


def is_offensive(text: str, extra_terms: Iterable[str] = ()) -> bool:
    words = tokens(text)
    if not words:
        return False
    built_words, built_phrases = _built_in()
    extra_words, extra_phrases = compile_terms(extra_terms)
    single = built_words | extra_words
    if any(variants(w) & single for w in words):
        return True
    joined = " ".join(words)
    for phrase in (*built_phrases, *extra_phrases):
        if f" {' '.join(phrase)} " in f" {joined} ":
            return True
        # The first word of a phrase may carry an Arabic prefix (والعن ← العن).
        for start, word in enumerate(words):
            if phrase[0] in variants(word) and tuple(words[start + 1 : start + len(phrase)]) == phrase[1:]:
                return True
    return False


async def check(session: AsyncSession, *texts: str | None) -> None:
    """Raise ``422 offensive_text`` if one of ``texts`` is offensive. Never use on reports or SOS."""
    extra = await settings.get(session, settings_domain.MODERATION_EXTRA_TERMS)
    for text in texts:
        if text and is_offensive(text, extra or ()):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, OFFENSIVE_TEXT)
