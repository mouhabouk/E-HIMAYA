import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True)]
Reason = Annotated[Text, StringConstraints(min_length=5, max_length=1000)]
Code = Annotated[int, Field(ge=11, le=83)]
Kind = Literal[
    "plan",
    "decision",
    "memo",
    "circular",
    "standing_instruction",
    "temporary_instruction",
    "recommendation",
    "minutes",
    "other",
]
LevelName = Literal["central", "regional"]
Status = Literal["draft", "in_force", "expired", "repealed"]
Access = Literal["all", "gouvernorat", "command", "restricted"]
Relation = Literal["repeals", "amends", "complements"]
RecommendationStatus = Literal["proposed", "in_progress", "done", "dropped"]
Topic = Annotated[Text, StringConstraints(min_length=2, max_length=60)]


class DocumentIn(BaseModel):
    reference: Annotated[Text, StringConstraints(max_length=300)] = ""
    kind: Kind
    level: LevelName
    gouvernorat_code: Code | None = None
    issuer: Annotated[Text, StringConstraints(min_length=2, max_length=200)]
    signatory: Annotated[Text, StringConstraints(max_length=200)] = ""
    title: Annotated[Text, StringConstraints(min_length=3, max_length=300)]
    summary: Annotated[Text, StringConstraints(max_length=4000)] = ""
    body: Annotated[Text, StringConstraints(max_length=100_000)] = ""
    topics: Annotated[list[Topic], Field(max_length=12)] = Field(default_factory=list)
    issued_on: date
    effective_from: date | None = None
    effective_to: date | None = None
    access: Access = "all"
    axis_ids: Annotated[list[uuid.UUID], Field(max_length=20)] = Field(default_factory=list)
    # Saved in force at once (otherwise a draft, published later).
    publish: bool = True


class DocumentPatch(DocumentIn):
    version: int
    reason: Reason
    publish: bool = False


class RepealIn(BaseModel):
    reason: Reason
    by_document_id: uuid.UUID | None = None


class LinkIn(BaseModel):
    to_id: uuid.UUID
    relation: Relation


class RecommendationIn(BaseModel):
    body: Annotated[Text, StringConstraints(min_length=3, max_length=2000)]
    responsible: Annotated[Text, StringConstraints(max_length=200)] = ""
    due_on: date | None = None


class RecommendationStatusIn(BaseModel):
    status: RecommendationStatus
    reason: Annotated[Text, StringConstraints(max_length=1000)] = ""


class RecommendationOut(BaseModel):
    id: str
    number: int
    body: str
    responsible: str
    due_on: date | None
    status: RecommendationStatus
    status_reason: str | None
    updated_by_name: str | None
    updated_at: datetime
    overdue: bool


class LinkOut(BaseModel):
    id: str
    number: str
    title: str
    kind: Kind
    status: Status
    relation: Relation
    # out: this document → the other; in: the other → this document.
    direction: Literal["out", "in"]


class AxisRef(BaseModel):
    id: str
    number: str
    name: str
    status: str


class DocumentOut(BaseModel):
    id: str
    number: str
    reference: str
    kind: Kind
    level: LevelName
    gouvernorat_code: int | None
    gouvernorat_name: str | None
    issuer: str
    signatory: str
    title: str
    summary: str
    topics: list[str]
    issued_on: date
    effective_from: date | None
    effective_to: date | None
    status: Status
    repeal_reason: str | None
    repealed_by: str | None
    access: Access
    source: Literal["manual", "axis"]
    signed: bool
    file_name: str | None
    file_type: str | None
    file_size: int | None
    file_sha256: str | None
    recommendations_open: int
    recommendations: int
    updated_by_name: str | None
    updated_at: datetime
    version: int
    # A short window of the text around the words searched, with <mark> (search results only).
    excerpt: str | None = None
    can_edit: bool


class DocumentDetail(BaseModel):
    document: DocumentOut
    body: str
    axes: list[AxisRef]
    links: list[LinkOut]
    recommendations: list[RecommendationOut]
    created_by_name: str | None
    created_at: datetime


class Facet(BaseModel):
    key: str
    count: int


class SearchOut(BaseModel):
    items: list[DocumentOut]
    total: int
    facets: dict[str, list[Facet]]
    can_create: bool
    can_create_central: bool


class RevisionOut(BaseModel):
    version: int
    change: str
    reason: str | None
    created_by_name: str | None
    created_at: datetime
    snapshot: dict[str, object]


class FileOut(BaseModel):
    url: str


# --- Directives and notices (design §8) -----------------------------------------------------------------------------

DispatchKind = Literal["directive", "notice"]
Audience = Literal["all", "targeted", "centre"]
Urgency = Literal["normal", "urgent", "flash"]


class DispatchIn(BaseModel):
    kind: DispatchKind
    # Directives: every gouvernorat ("all") or those listed ("targeted"). Notices go to the centre.
    audience: Literal["all", "targeted"] = "all"
    gouvernorats: Annotated[list[Code], Field(max_length=24)] = Field(default_factory=list)
    urgency: Urgency = "normal"
    subject: Annotated[Text, StringConstraints(min_length=3, max_length=300)]
    body: Annotated[Text, StringConstraints(max_length=20_000)] = ""
    topics: Annotated[list[Topic], Field(max_length=12)] = Field(default_factory=list)
    incident_id: uuid.UUID | None = None
    axis_id: uuid.UUID | None = None
    reply_required: bool = True
    reply_due_at: datetime | None = None


class ReplyIn(BaseModel):
    body: Annotated[Text, StringConstraints(max_length=20_000)] = ""
    # The thread written in (the centre names it; a gouvernorat writes in its own).
    gouvernorat_code: Code | None = None


class AttachmentOut(BaseModel):
    id: str
    file_name: str
    content_type: str
    size: int
    sha256: str
    created_at: datetime


class TargetOut(BaseModel):
    gouvernorat_code: int
    gouvernorat_name: str | None
    seen_at: datetime | None
    seen_by_name: str | None
    replied_at: datetime | None
    replies: int
    overdue: bool


class ReplyOut(BaseModel):
    id: str
    gouvernorat_code: int
    side: Literal["centre", "regional"]
    body: str
    created_by_name: str | None
    created_at: datetime
    attachments: list[AttachmentOut]
    mine: bool


class DispatchOut(BaseModel):
    id: str
    number: str
    kind: DispatchKind
    audience: Audience
    origin_gouvernorat: int | None
    origin_name: str | None
    urgency: Urgency
    subject: str
    body: str
    topics: list[str]
    incident_id: str | None
    axis_id: str | None
    reply_required: bool
    reply_due_at: datetime | None
    status: Literal["open", "closed"]
    closed_at: datetime | None
    created_by_name: str | None
    created_at: datetime
    # The gouvernorats the caller sees (the centre: all of them; a gouvernorat: its own).
    targets: int
    seen: int
    replied: int
    # For the receiving side: not opened yet by it.
    unread: bool
    overdue: bool
    attachments: int
    excerpt: str | None = None


class ThreadOut(BaseModel):
    gouvernorat_code: int
    gouvernorat_name: str | None
    replies: list[ReplyOut]


class DispatchDetail(BaseModel):
    dispatch: DispatchOut
    attachments: list[AttachmentOut]
    targets: list[TargetOut]
    threads: list[ThreadOut]
    can_reply: bool
    can_close: bool
    can_attach: bool
    # The caller's side: the centre (every thread) or a gouvernorat (its own thread).
    viewer_side: Literal["centre", "regional"]
    # The reply just written (its files follow).
    reply_id: str | None = None


class DispatchPage(BaseModel):
    items: list[DispatchOut]
    total: int
    unread: int
    can_direct: bool
    can_notify: bool
