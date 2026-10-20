import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from app.modules.reports.domain import Category

Text = Annotated[str, StringConstraints(strip_whitespace=True)]
MAX_SECTION = 20_000

AccessLevel = Literal["national", "gouvernorat", "committee"]
EntryStatus = Literal["draft", "in_review", "published", "archived"]
LibraryKind = Literal["memory", "report_doc", "incident", "report", "transcript", "procedure"]


class Title(BaseModel):
    ar: Annotated[Text, StringConstraints(min_length=3, max_length=200)]
    fr: Annotated[Text, StringConstraints(min_length=3, max_length=200)]


class Section(BaseModel):
    """One Markdown section in both languages (either may be empty while drafting)."""

    ar: Annotated[Text, StringConstraints(max_length=MAX_SECTION)] = ""
    fr: Annotated[Text, StringConstraints(max_length=MAX_SECTION)] = ""


class SourceRef(BaseModel):
    title: Annotated[Text, StringConstraints(min_length=1, max_length=300)]
    url: Annotated[str, StringConstraints(max_length=2000)] | None = None
    media_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _one_target(self) -> "SourceRef":
        if (self.url is None) == (self.media_id is None):
            raise ValueError("a source has either a url or a media_id")
        if self.url is not None and not self.url.startswith("https://"):
            raise ValueError("source urls must be https")
        return self


class Geometry(BaseModel):
    """GeoJSON area of the event (Polygon or MultiPolygon, WGS 84)."""

    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list[Any]


class EntryFields(BaseModel):
    title: Title
    event_type: Category
    started_at: datetime
    ended_at: datetime | None = None
    gouvernorats: Annotated[list[Annotated[int, Field(ge=11, le=83)]], Field(max_length=24)] = Field(
        default_factory=list
    )
    geometry: Geometry | None = None
    incident_ids: Annotated[list[uuid.UUID], Field(max_length=50)] = Field(default_factory=list)
    summary: Section = Field(default_factory=Section)
    strengths: Section = Field(default_factory=Section)
    weaknesses: Section = Field(default_factory=Section)
    lessons: Section = Field(default_factory=Section)
    recommendations: Section = Field(default_factory=Section)
    sources: Annotated[list[SourceRef], Field(max_length=50)] = Field(default_factory=list)
    access: AccessLevel = "national"

    @field_validator("gouvernorats")
    @classmethod
    def _distinct(cls, value: list[int]) -> list[int]:
        return sorted(set(value))

    @model_validator(mode="after")
    def _period(self) -> "EntryFields":
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at is before started_at")
        return self


class EntryIn(EntryFields):
    pass


class EntryPatch(BaseModel):
    """Partial update; ``version`` is the version the editor started from (optimistic locking)."""

    version: int = Field(ge=1)
    title: Title | None = None
    event_type: Category | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    gouvernorats: Annotated[list[Annotated[int, Field(ge=11, le=83)]], Field(max_length=24)] | None = None
    geometry: Geometry | None = None
    incident_ids: Annotated[list[uuid.UUID], Field(max_length=50)] | None = None
    summary: Section | None = None
    strengths: Section | None = None
    weaknesses: Section | None = None
    lessons: Section | None = None
    recommendations: Section | None = None
    sources: Annotated[list[SourceRef], Field(max_length=50)] | None = None
    access: AccessLevel | None = None


class TransitionIn(BaseModel):
    to: EntryStatus
    note: Annotated[Text, StringConstraints(max_length=2000)] | None = None
    version: int = Field(ge=1)


class Person(BaseModel):
    id: str
    name: str | None = None


class Review(BaseModel):
    id: str
    name: str | None = None
    decision: Literal["approved", "changes_requested"]
    note: str | None = None
    at: datetime
    version: int


class EntryOut(EntryFields):
    id: uuid.UUID
    status: EntryStatus
    version: int
    published_version: int | None
    author: Person
    updated_by: Person
    reviewers: list[Review]
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    # What the caller may do (the dashboard hides the other buttons; the API checks again).
    can_edit: bool = False
    can_review: bool = False


class EntrySummary(BaseModel):
    id: uuid.UUID
    title: Title
    event_type: Category
    started_at: datetime
    ended_at: datetime | None
    gouvernorats: list[int]
    access: AccessLevel
    status: EntryStatus
    version: int
    published_version: int | None
    author: Person
    updated_at: datetime


class EntryPage(BaseModel):
    items: list[EntrySummary]
    next_cursor: str | None


class VersionSummary(BaseModel):
    version: int
    status: EntryStatus
    change: str
    note: str | None
    created_at: datetime
    created_by: Person


class VersionList(BaseModel):
    items: list[VersionSummary]


class VersionOut(VersionSummary):
    entry: EntryFields


# ---------------------------------------------------------------- events library


class Hit(BaseModel):
    kind: LibraryKind
    id: str
    title: str
    # HTML: the text is escaped and only <mark>…</mark> around matched words is kept.
    excerpt: str
    date: datetime | None
    gouvernorat: int | None
    gouvernorats: list[int]
    category: str | None
    incident_id: uuid.UUID | None
    score: float


class FacetValue(BaseModel):
    key: str
    count: int


class Facets(BaseModel):
    kind: list[FacetValue]
    year: list[FacetValue]
    gouvernorat: list[FacetValue]
    category: list[FacetValue]


class SearchOut(BaseModel):
    items: list[Hit]
    facets: Facets
    backend: Literal["opensearch", "postgres"]
    # True when e5 vectors took part (AI service reachable).
    semantic: bool
    next_cursor: str | None


class Day(BaseModel):
    date: date
    count: int


class CalendarOut(BaseModel):
    year: int
    month: int
    days: list[Day]


class TreeNode(BaseModel):
    key: str
    label: dict[str, str] | None = None
    count: int
    children: list["TreeNode"] = Field(default_factory=list)


class TreeOut(BaseModel):
    by: Literal["period", "type", "gouvernorat"]
    nodes: list[TreeNode]


class MediaLink(BaseModel):
    id: uuid.UUID
    kind: str
    content_type: str | None
    duration_s: float | None
    url: str | None


class ItemOut(BaseModel):
    kind: LibraryKind
    id: str
    title: str
    date: datetime | None
    gouvernorat: int | None
    gouvernorats: list[int]
    category: str | None
    incident_id: uuid.UUID | None
    body: str
    fields: dict[str, Any] = Field(default_factory=dict)
    media: list[MediaLink] = Field(default_factory=list)
