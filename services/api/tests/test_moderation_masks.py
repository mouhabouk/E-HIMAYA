"""Offensive words hidden on the staff screens (moderation.masks) and the word list behind them."""

import csv
from pathlib import Path

import pytest

from app.modules.ai import lexicon
from app.modules.moderation.service import is_offensive, masks
from app.modules.moderation.terms import SOURCE, latin_spellings


def _shown(text: str) -> str:
    """``text`` as a screen shows it: each hidden part replaced by ■, each flagged part between ⟦ ⟧."""
    units = text.encode("utf-16-le")
    out, at = b"", 0
    for start, end, kind in masks(text):
        part = "■" if kind == "hide" else "⟦" + units[2 * start : 2 * end].decode("utf-16-le") + "⟧"
        out += units[2 * at : 2 * start] + part.encode("utf-16-le")
        at = end
    return (out + units[2 * at :]).decode("utf-16-le")


@pytest.mark.parametrize(
    ("text_", "shown"),
    [
        ("فما ناس محصورين، يا كلب زبي، النار تكبر", "فما ناس محصورين، ■ ■، النار تكبر"),
        ("ya 9a7ba!! fama 7ri9", "ya ■!! fama 7ri9"),
        ("QAHBA kahba ga7ba", "■ ■ ■"),
        ("«شرموطة» والقحبة", "«■» ■"),
        ("يلعن دين ربك علاش ما جيتوش", "■ علاش ما جيتوش"),
        ("F.U.C.K the fire is spreading", "■ the fire is spreading"),
        ("😀 fuck 😀", "😀 ■ 😀"),
        ("Bande de connards, venez vite", "Bande de ■, venez vite"),
        # Threats, incitement and terrorism stay readable, shaded red.
        ("قال لي باش نقتلك وهرب", "قال لي ⟦باش نقتلك⟧ وهرب"),
        ("on va te tuer, il a un couteau", "⟦on va te tuer⟧, il a un couteau"),
        ("اقتلوهم واحرقو ديارهم", "⟦اقتلوهم⟧ ⟦واحرقو ديارهم⟧"),
        ("el afar9a barra, a7r9ouhom", "⟦el afar9a barra⟧, ⟦a7r9ouhom⟧"),
        ("brûlez-les tous", "⟦brûlez-les⟧ tous"),
        ("فما واحد لابس حزام ناسف قدّام البنك", "فما واحد لابس ⟦حزام ناسف⟧ قدّام البنك"),
        # A word both hidden and flagged is hidden.
        ("يا كلب نذبحك", "■ ⟦نذبحك⟧"),
    ],
)
def test_masks_hide_exactly_the_words(text_: str, shown: str) -> None:
    assert _shown(text_) == shown


@pytest.mark.parametrize(
    "text_",
    [
        "كلب عضّ طفل صغير في الحومة",
        "البهايم ماتو في الفيضان",
        "حمار في وسط الطريق",
        "الماء وسخ وفيه زبلة",
        "عائلة زامل محاصرين في الدار",
        "a dog bite, the child is bleeding",
        "retard des secours",
        "zbib w kass",
        "الافارقة محصورين في الفلوكة",
        "",
    ],
)
def test_masks_keep_ordinary_words(text_: str) -> None:
    assert masks(text_) == []


def test_threats_and_incitement_are_refused_and_flagged_not_hidden() -> None:
    for text_ in ("on va te tuer", "اقتلوهم", "otrdouhom"):
        assert is_offensive(text_)
        assert [kind for _, _, kind in masks(text_)] == ["flag"], text_


def test_latin_spellings() -> None:
    assert latin_spellings("9a7ba") >= {"qahba", "kahba", "gahba", "9ahba", "ka7ba"}
    # A new digraph is never made: 9h is not kh or gh (ghab = absent), 7 after k is not h.
    assert "ghab" not in latin_spellings("9hab") and "khab" not in latin_spellings("9hab")
    assert "khalouch" not in latin_spellings("k7alouch")
    assert latin_spellings("louti") == {"louti", "loti", "luti"}


def _rows() -> list[dict[str, str]]:
    with SOURCE.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_word_list_is_well_formed() -> None:
    rows = _rows()
    assert len({r["id"] for r in rows}) == len(rows)
    for r in rows:
        assert r["refuse"] in ("yes", "no") and r["mask"] in ("hide", "flag", "no"), r["id"]
        assert r["severity"] in ("0", "1", "2", "3"), r["id"]
        assert r["forms_ar"] or r["forms_latn"] or r["forms_fr_en"], r["id"]
        assert (r["category"] == "excluded") == (r["refuse"] == r["mask"] == "no"), r["id"]


def test_excluded_words_are_never_hidden_alone() -> None:
    for r in _rows():
        if r["category"] != "excluded":
            continue
        for cell in ("forms_ar", "forms_latn", "forms_fr_en"):
            for word in filter(None, r[cell].split("|")):
                assert masks(word) == [], word


def test_emergency_keywords_are_never_hidden() -> None:
    groups = (lexicon.LIVES, lexicon.INJURED, lexicon.DEATHS, *lexicon.HAZARDS.values())
    for term in (t for group in groups for t in group):
        assert masks(term) == [], term


LEXICON = Path(__file__).resolve().parents[3] / "data" / "lexicon"


def test_derja_lexicon_and_examples_are_never_hidden() -> None:
    """The Derja of real reports (lexicon rows and labelled examples) keeps every word on screen."""
    with (LEXICON / "tunisian-derja-lexicon.csv").open(encoding="utf-8", newline="") as f:
        lexicon_rows = list(csv.DictReader(f))
    with (LEXICON / "derja-examples.csv").open(encoding="utf-8", newline="") as f:
        examples = list(csv.DictReader(f))
    assert len(lexicon_rows) > 200 and len(examples) > 40
    for row in lexicon_rows:
        for cell in ("derja_ar", "derja_latn", "msa", "fr", "example"):
            assert masks(row[cell].replace("|", " ")) == [], (row["id"], cell)
    for example in examples:
        assert masks(example["text"]) == [], example["id"]
