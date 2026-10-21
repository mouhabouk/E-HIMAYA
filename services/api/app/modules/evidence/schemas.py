import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AnchorOut(BaseModel):
    seq: int
    from_at: datetime | None
    to_at: datetime
    media_count: int
    media_root: str | None
    audit_seq: int | None
    audit_hash: str | None
    prev_anchor_hash: str | None
    anchor_hash: str
    signature: str | None
    key_id: str | None
    time_stamped: bool
    created_at: datetime


class AnchorPage(BaseModel):
    items: list[AnchorOut]
    next_before_seq: int | None


class ProofStep(BaseModel):
    side: Literal["left", "right"]
    hash: str


class ProofOut(BaseModel):
    """Everything a third party needs to recompute the root, the anchor hash and check the signature."""

    media_id: uuid.UUID
    sha256: str
    leaf_index: int
    leaf_hash: str
    path: list[ProofStep]
    anchor: AnchorOut
    anchor_line: str
    public_key: str | None
    method: dict[str, str]
