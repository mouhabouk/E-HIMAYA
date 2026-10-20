import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    LargeBinary,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.crypto import EncryptedText
from app.core.db import Base


class MemoryEntry(Base):
    """National memory (FR-C-22): the after-action record of an event, reviewed by a second staff member.

    The row is the working copy; ``published_version`` names the snapshot of ``memory_entry_version`` that readers,
    the events library and the incident assistant see (an edit of a published entry does not hide it).
    """

    __tablename__ = "memory_entry"
    __table_args__ = {"schema": "knowledge"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    # {"ar": ..., "fr": ...}
    title: Mapped[dict[str, str]] = mapped_column(JSONB)
    event_type: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gouvernorats: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), server_default="{}")
    geometry: Mapped[object | None] = mapped_column(Geometry("GEOMETRY", srid=4326, spatial_index=False))
    incident_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), server_default="{}")
    # Markdown sections, each {"ar": ..., "fr": ...}.
    summary: Mapped[dict[str, str]] = mapped_column(JSONB)
    strengths: Mapped[dict[str, str]] = mapped_column(JSONB)
    weaknesses: Mapped[dict[str, str]] = mapped_column(JSONB)
    lessons: Mapped[dict[str, str]] = mapped_column(JSONB)
    recommendations: Mapped[dict[str, str]] = mapped_column(JSONB)
    # [{"title": ..., "url": "https://..." | null, "media_id": "<uuid>" | null}]
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    access: Mapped[str] = mapped_column(Text, server_default="national")
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    author: Mapped[str] = mapped_column(Text)
    author_name: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[str] = mapped_column(Text)
    updated_by_name: Mapped[str | None] = mapped_column(Text)
    # [{"id", "name", "decision": "approved"|"changes_requested", "note", "at", "version"}]
    reviewers: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    published_version: Mapped[int | None] = mapped_column(Integer)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemoryEntryVersion(Base):
    """Full history: one snapshot per saved change and per workflow transition."""

    __tablename__ = "memory_entry_version"
    __table_args__ = {"schema": "knowledge"}

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge.memory_entry.id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Content fields of the entry at that version (geometry as GeoJSON).
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text)
    change: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    created_by_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SearchDoc(Base):
    """One searchable item of the events library, derived from its source table by the indexer.

    PostgreSQL copy of what goes to OpenSearch: it serves the full-text fallback, the pgvector part of the search and
    the scope check of every hit. Texts that are encrypted at their source (report texts, transcripts) stay encrypted
    here (``body_enc``) and are searchable through blind-index ``tokens`` only; the others are kept in clear with their
    normalised form (``norm``) for the 'simple' full-text vector and the pg_trgm index.
    """

    __tablename__ = "search_doc"
    __table_args__ = (UniqueConstraint("kind", "ref_id", name="uq_search_doc_kind_ref"), {"schema": "knowledge"})

    # Surrogate key (key rotation re-encrypts ``body_enc`` row by row through a single-column key).
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    ref_id: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    body_enc: Mapped[str | None] = mapped_column("body_enc", EncryptedText("knowledge.search_doc.body"))
    norm: Mapped[str | None] = mapped_column(Text)
    tokens: Mapped[list[bytes]] = mapped_column(ARRAY(LargeBinary), server_default="{}")
    lang: Mapped[str | None] = mapped_column(Text)
    date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gouvernorats: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), server_default="{}")
    access: Mapped[str] = mapped_column(Text)
    categories: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    incident_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    checksum: Mapped[str] = mapped_column(Text)
    search: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple'::regconfig, coalesce(norm, ''))"), deferred=True
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), deferred=True)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    # Tombstone: the source is gone or no longer searchable; removed once OpenSearch forgot it.
    deleted: Mapped[bool] = mapped_column(Boolean, server_default="false")
    # Changed since the last successful push to OpenSearch.
    os_dirty: Mapped[bool] = mapped_column(Boolean, server_default="true")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IndexState(Base):
    """Progress of the indexer: outbox cursor, sweep watermarks, index version (one row per key)."""

    __tablename__ = "index_state"
    __table_args__ = {"schema": "knowledge"}

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
