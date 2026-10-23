"""Text normalisation of the respectful-language filter (rule 4, docs/phase-a/design.md §2.6).

Both the words of the lists and the text people write go through ``tokens``: the same spelling tricks then compare
equal. Handled: case, Arabic diacritics and tatweel, letter variants (alef, ya, ta marbuta, hamza), Latin accents,
a few look-alike symbols (@ → a, $ → s, 0 → o, 1 → i), letters repeated for emphasis, separators inside a word
(f.u.c.k, ك-ل-ب) and words spelled one letter at a time (f u c k).
"""

import re
import unicodedata

_ARABIC_MARKS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_ARABIC_LETTERS = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ئ": "ي",
        "ؤ": "و",
        "ة": "ه",
        "گ": "ك",
        "ڨ": "ق",
        "ڤ": "ف",
    }
)
# Only symbols that never carry a sound in Tunisian Latin script (3, 5, 7, 9 do: ع, خ, ح, ق).
_LOOKALIKE = str.maketrans({"@": "a", "$": "s", "0": "o", "1": "i", "!": "i", "€": "e"})
_INNER_SEPARATORS = re.compile(r"[.\-_*'’`~+|/\\]+")
_SPLIT = re.compile(r"[^\w]+", re.UNICODE)
_REPEATS = re.compile(r"(.)\1+")


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = _ARABIC_MARKS.sub("", text).translate(_ARABIC_LETTERS)
    # Latin accents: é → e, ç → c (Arabic letters have no combining marks left at this point).
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    """Normalised words of ``text``, in order."""
    words: list[str] = []
    for raw in _fold(text).split():
        word = _INNER_SEPARATORS.sub("", raw.translate(_LOOKALIKE))
        words.extend(part for part in _SPLIT.split(word) if part)
    words = [_REPEATS.sub(r"\1", w) for w in words]
    # f u c k → fuck: a run of three or more one-letter words is read as one word.
    joined: list[str] = []
    run: list[str] = []
    for word in [*words, ""]:
        if len(word) == 1:
            run.append(word)
            continue
        if len(run) >= 3:
            joined.append("".join(run))
        else:
            joined.extend(run)
        run = []
        if word:
            joined.append(word)
    return joined


# Arabic clitics written attached to a word: and, the, with, for, o (vocative), your/his suffixes are not removed.
_ARABIC_PREFIXES = ("وال", "بال", "فال", "كال", "لل", "ال", "يا", "و", "ب", "ف", "ل")


def variants(word: str) -> set[str]:
    """The word and the word without one attached Arabic prefix."""
    found = {word}
    for prefix in _ARABIC_PREFIXES:
        if word.startswith(prefix) and len(word) - len(prefix) >= 2:
            found.add(word[len(prefix) :])
    return found
