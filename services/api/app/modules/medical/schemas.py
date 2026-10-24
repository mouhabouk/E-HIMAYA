import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

# Standard base64 (with padding) of a binary value; lengths are checked once decoded.
B64 = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9+/]*={0,2}$", max_length=90_000)]
Via = Literal["gouvernorat", "committee", "referral"]


class KeyBackup(BaseModel):
    """The doctor's private key locked by their own code on the phone: Argon2id, then AES-256-GCM."""

    kdf: Literal["argon2id"]
    memory_kib: int = Field(ge=8192, le=262_144)
    iterations: int = Field(ge=1, le=10)
    parallelism: int = Field(ge=1, le=4)
    salt: Annotated[B64, StringConstraints(max_length=64)]
    nonce: Annotated[B64, StringConstraints(max_length=24)]
    ciphertext: Annotated[B64, StringConstraints(max_length=100)]


class DoctorKeyIn(BaseModel):
    public_key: Annotated[B64, StringConstraints(max_length=64)]
    backup: KeyBackup


class DoctorKeyOut(BaseModel):
    public_key: str
    backup: KeyBackup
    set_at: datetime


class Recipient(BaseModel):
    doctor_id: uuid.UUID
    public_key: str
    via: Literal["gouvernorat", "committee"]


class RecipientsOut(BaseModel):
    """Who the phone locks the file for: the Civil Protection doctors of the place's gouvernorat (or of the
    candidate gouvernorats while the place is uncertain), and the medical committee."""

    gouvernorat_codes: list[int]
    recipients: list[Recipient]


class WrappedKeyIn(BaseModel):
    doctor_id: uuid.UUID
    eph_public: Annotated[B64, StringConstraints(max_length=64)]
    nonce: Annotated[B64, StringConstraints(max_length=24)]
    wrapped: Annotated[B64, StringConstraints(max_length=100)]


class LockedFileIn(BaseModel):
    """The locked part of the medical file (AES-256-GCM, at most 64 KiB) and its key for each recipient."""

    nonce: Annotated[B64, StringConstraints(max_length=24)]
    ciphertext: B64
    keys: list[WrappedKeyIn] = Field(min_length=1, max_length=64)


class InboxItem(BaseModel):
    report_id: uuid.UUID
    tracking_code: str
    category: str
    gouvernorat_code: int | None
    received_at: datetime
    report_status: str
    via: Via
    opened_at: datetime | None


class OpenIn(BaseModel):
    # Required from a member of the medical committee who opens a file outside their gouvernorat.
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)] | None = None


class OpenedFile(BaseModel):
    """Everything the doctor's phone needs to open the file; the server cannot."""

    report_id: uuid.UUID
    via: Via
    nonce: str
    ciphertext: str
    eph_public: str
    key_nonce: str
    wrapped: str
    # The emergency card the reporter chose to leave readable (also seen by the operations room).
    card: dict[str, Any] | None
