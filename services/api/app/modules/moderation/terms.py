"""Word lists of the respectful-language filter (rule 4): obscenities, insults, hate, threats and terrorism.

The source is ``offensive_terms.csv`` beside this file, one row per word family: its spellings in Arabic script
(standard and Tunisian), Tunisian in Latin script (Arabizi), French and English, its MSA and French equivalents, a
category and a severity. Two columns say what the row is used for:

* ``refuse``: the word is refused in non-emergency free text (profile names, address, messages to the Office),
  ``422 offensive_text``;
* ``mask``: what the staff screens (report text, its translation, transcripts) do with the word. ``hide``: a shaded
  block in another colour is shown in its place (obscenities, insults, slurs). ``flag``: the word stays readable,
  shaded red (threats, incitement to violence or hatred, terrorism): the operator must read what the citizen
  reported. ``no``: nothing.

Words that are also names or ordinary words (كلب in "a dog bit", بهايم for livestock, زامل, طحان, Dick, Isis, French
"retard", English "bite") are only listed inside a phrase (يا كلب) or in the ``excluded`` rows, which document the
choice and are never used. The system administrator adds words in the dashboard (setting ``moderation.extra_terms``)
without a new release. Several-word entries match the words in order.
"""

import csv
from itertools import pairwise, product
from pathlib import Path
from typing import Literal

SOURCE = Path(__file__).with_name("offensive_terms.csv")

# What a staff screen does with a word: hide it behind a shaded block, or keep it readable and shade it red.
MaskKind = Literal["hide", "flag"]

# Tunisian Latin script writes some Arabic letters with digits; people also write them with letters. A Latin form
# written with the digit is expanded to the letter spellings (9a7ba → qahba, kahba, ga7ba ...). Letters are never
# expanded to digits or to one another (k → 9 would turn "kalb" into "9alb", heart).
_LATIN_CLASSES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ch", ("ch", "sh")),
    ("ou", ("ou", "o", "u")),
    ("9", ("9", "q", "g", "k")),
    ("7", ("7", "h")),
    ("5", ("5", "kh")),
    ("8", ("8", "gh")),
)
_MAX_SPELLINGS = 256
_QAF = dict(_LATIN_CLASSES)["9"]
_HA = dict(_LATIN_CLASSES)["7"]


def latin_spellings(form: str) -> set[str]:
    """``form`` and its spellings with the digits written as letters (and ch/sh, ou/o/u).

    A letter that would make a new digraph with its neighbour is not used: 9 followed by h is never written k or g
    (kh = خ, gh = غ: "9hab" must not become "ghab", absent), and 7 after c, s, k or g is never written h."""
    pieces: list[tuple[str, ...]] = []
    i = 0
    while i < len(form):
        for key, options in _LATIN_CLASSES:
            if form.startswith(key, i):
                pieces.append(options)
                i += len(key)
                break
        else:
            pieces.append((form[i],))
            i += 1
    found: set[str] = set()
    for combination in product(*pieces):
        if any(
            (pieces[k] == _QAF and a in ("k", "g") and b.startswith("h"))
            or (pieces[k + 1] == _HA and b == "h" and a[-1:] in ("c", "s", "k", "g"))
            for k, (a, b) in enumerate(pairwise(combination))
        ):
            continue
        found.add("".join(combination))
        if len(found) >= _MAX_SPELLINGS:
            break
    return found


def _split(cell: str) -> list[str]:
    return [part.strip() for part in cell.split("|") if part.strip()]


def _load() -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    refuse: list[str] = []
    hide: list[str] = []
    flag: list[str] = []
    with SOURCE.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            forms = _split(row["forms_ar"]) + _split(row["forms_fr_en"])
            for latin in _split(row["forms_latn"]):
                forms.extend(sorted(latin_spellings(latin)))
            if row["refuse"] == "yes":
                refuse.extend(forms)
            if row["mask"] == "hide":
                hide.extend(forms)
            elif row["mask"] == "flag":
                flag.extend(forms)
    return tuple(dict.fromkeys(refuse)), tuple(dict.fromkeys(hide)), tuple(dict.fromkeys(flag))


# BUILT_IN: refused in non-emergency free text; HIDDEN and FLAGGED: hidden, or shaded red, on the staff screens.
BUILT_IN, HIDDEN, FLAGGED = _load()
