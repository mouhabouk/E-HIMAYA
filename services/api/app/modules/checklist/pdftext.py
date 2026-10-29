"""The text of a plan's PDF, page by page, for the reader (docs/phase-l/design-l5.md §2.3).

The file was checked when it was recorded (type and size, register/domain.py), but its content is still untrusted:
the reading has a page ceiling, a character ceiling per page and in all, and runs in the worker, never in a request.
Arabic letters in presentation forms (how many PDF writers store Arabic) are folded back to plain letters, so the
model reads, and the quoted passages are checked, on ordinary text.
"""

import io
import re
import unicodedata
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PyPdfError

MAX_PAGES = 300
MAX_PAGE_CHARS = 12_000
MAX_TOTAL_CHARS = 400_000

_SPACES = re.compile(r"[ \t ]+")
_LINES = re.compile(r"\n{3,}")
# Arabic diacritics and the tatweel, ignored when a quoted passage is looked for on its page.
_MARKS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_NOT_WORD = re.compile(r"[^\w]+")


class PlanUnreadable(Exception):
    """The PDF cannot be opened, is encrypted, or holds no text (a scan): the code is shown to the room."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class PlanText:
    pages: list[str]
    # Pages in the file; ``pages`` stops at MAX_PAGES or MAX_TOTAL_CHARS.
    total_pages: int


def clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("\r", "\n")
    text = "\n".join(_SPACES.sub(" ", line).strip() for line in text.split("\n"))
    return _LINES.sub("\n\n", text).strip()


def folded(text: str) -> str:
    """For comparisons only: no case, marks, punctuation or spacing, and the common Arabic letter variants merged."""
    text = _MARKS.sub("", unicodedata.normalize("NFKC", text).casefold())
    text = text.translate(str.maketrans("أإآٱىة", "اااايه"))
    return _NOT_WORD.sub("", text)


def extract(data: bytes) -> PlanText:
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise PlanUnreadable("plan_encrypted")
        total = len(reader.pages)
        pages: list[str] = []
        used = 0
        for page in reader.pages[:MAX_PAGES]:
            text = clean(page.extract_text() or "")[:MAX_PAGE_CHARS]
            if used + len(text) > MAX_TOTAL_CHARS:
                break
            pages.append(text)
            used += len(text)
    except PlanUnreadable:
        raise
    except (PyPdfError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
        raise PlanUnreadable("plan_unreadable") from exc
    if not any(len(p) >= 20 for p in pages):
        raise PlanUnreadable("plan_has_no_text")
    return PlanText(pages=pages, total_pages=total)
