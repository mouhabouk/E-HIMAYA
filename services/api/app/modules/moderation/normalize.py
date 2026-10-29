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
    return [word for word, _, _ in located_tokens(text)]


_RAW_WORD = re.compile(r"\S+")
_EDGE = re.compile(r"^[^\w@$€]+|[^\w@$€]+$")


def located_tokens(text: str) -> list[tuple[str, int, int]]:
    """Normalised words of ``text`` with where they are in it: ``(word, start, end)``, string indices of ``text``.

    The place is that of the whole written word without its leading and trailing punctuation (``"زبي،"`` → the three
    letters), so the screens can hide exactly what the person wrote."""
    words: list[tuple[str, int, int]] = []
    for match in _RAW_WORD.finditer(text):
        raw = match.group()
        # Punctuation around a word is not part of it (and "!" there is not the "i" of "sh!t").
        edge = _EDGE.sub("", raw)
        if not edge:
            continue
        start = match.start() + raw.index(edge)
        end = start + len(edge)
        for folded in _fold(edge).split():
            word = _INNER_SEPARATORS.sub("", folded.translate(_LOOKALIKE))
            words.extend((_REPEATS.sub(r"\1", part), start, end) for part in _SPLIT.split(word) if part)
    # f u c k → fuck: a run of three or more one-letter words is read as one word.
    joined: list[tuple[str, int, int]] = []
    run: list[tuple[str, int, int]] = []
    for item in [*words, ("", 0, 0)]:
        if len(item[0]) == 1:
            run.append(item)
            continue
        if len(run) >= 3:
            joined.append(("".join(w for w, _, _ in run), run[0][1], run[-1][2]))
        else:
            joined.extend(run)
        run = []
        if item[0]:
            joined.append(item)
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
