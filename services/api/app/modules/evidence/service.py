"""Sealing, proofs and chain checks of the evidence anchors (phase 10 §4.3).

An anchor covers the stored media not anchored yet (their SHA-256, as Merkle leaves) and the head of the audit chain.
``anchor_hash`` = SHA-256 of the UTF-8 line::

    e-himaya-anchor-v1|<seq>|<from_at>|<to_at>|<media_count>|<media_root>|<audit_seq>|<audit_hash>|<prev_anchor_hash>

(timestamps in UTC ISO 8601 with microseconds, empty fields for nulls). The Ed25519 signature is over the ASCII of
``anchor_hash``; ``key_id`` names the key like the certificates do.
"""

import base64
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from sqlalchemy import exists, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.audit.models import AuditLog
from app.modules.evidence import merkle, tsa
from app.modules.evidence.models import Anchor, Leaf
from app.modules.orgs import certificate
from app.modules.reports.models import Media

log = structlog.get_logger()

FORMAT = "e-himaya-anchor-v1"
BATCH = 10_000
# Any constant shared by every sealer: one sealing at a time, whatever the number of worker processes.
_SEAL_LOCK = 0x45564944  # "EVID"


def signing_key() -> Ed25519PrivateKey | None:
    """``EVIDENCE_SIGNING_KEY``, else the certificate key (with a warning), else none (anchors sealed unsigned)."""
    settings = get_settings()
    secret = settings.evidence_signing_key
    if secret is None and settings.certificate_signing_key is not None:
        log.warning("evidence.certificate_key_fallback")
        secret = settings.certificate_signing_key
    if secret is None:
        return None
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(secret.get_secret_value()))


def known_public_keys() -> dict[str, Ed25519PublicKey]:
    """Keys whose anchor signatures are accepted: the evidence key and every certificate key, by key id."""
    keys = certificate.known_public_keys()
    current = signing_key()
    if current is not None:
        keys[certificate.key_id_of(current.public_key())] = current.public_key()
    return keys


def _ts(value: datetime | None) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds") if value is not None else ""


def _opt(value: object) -> str:
    return "" if value is None else str(value)


def canonical(anchor: Anchor) -> str:
    fields = (
        FORMAT,
        str(anchor.seq),
        _ts(anchor.from_at),
        _ts(anchor.to_at),
        str(anchor.media_count),
        _opt(anchor.media_root),
        _opt(anchor.audit_seq),
        _opt(anchor.audit_hash),
        _opt(anchor.prev_anchor_hash),
    )
    return "|".join(fields)


def compute_hash(anchor: Anchor) -> str:
    return hashlib.sha256(canonical(anchor).encode()).hexdigest()


def signature_valid(anchor: Anchor, keys: dict[str, Ed25519PublicKey] | None = None) -> bool:
    if anchor.signature is None or anchor.key_id is None:
        return False
    public = (keys if keys is not None else known_public_keys()).get(anchor.key_id)
    if public is None:
        return False
    try:
        public.verify(base64.b64decode(anchor.signature), anchor.anchor_hash.encode())
    except (InvalidSignature, ValueError):
        return False
    return True


# ---------------------------------------------------------------- sealing


async def seal(session: AsyncSession) -> Anchor | None:
    """Seal what is new since the last anchor (system scope, inside the caller's transaction). None if nothing is."""
    await session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _SEAL_LOCK})
    last = await session.scalar(select(Anchor).order_by(Anchor.seq.desc()).limit(1))
    media = (
        await session.execute(
            select(Media.id, Media.sha256)
            .where(
                Media.status == "stored",
                Media.sha256.is_not(None),
                ~exists().where(Leaf.media_id == Media.id),
            )
            .order_by(Media.created_at, Media.id)
            .limit(BATCH)
        )
    ).all()
    head = (await session.execute(select(AuditLog.seq, AuditLog.hash).order_by(AuditLog.seq.desc()).limit(1))).first()
    audit_seq, audit_hash = (head[0], head[1]) if head else (None, None)
    if not media and last is not None and last.audit_seq == audit_seq:
        return None

    leaves = [merkle.leaf_hash(m.id, m.sha256) for m in media]
    anchor = Anchor(
        seq=(last.seq + 1) if last else 1,
        from_at=last.to_at if last else None,
        to_at=await session.scalar(select(func.now())),
        media_count=len(media),
        media_root=merkle.root(leaves) if leaves else None,
        audit_seq=audit_seq,
        audit_hash=audit_hash,
        prev_anchor_hash=last.anchor_hash if last else None,
        tsa_url=get_settings().tsa_url,
    )
    anchor.anchor_hash = compute_hash(anchor)
    key = signing_key()
    if key is not None:
        anchor.signature = base64.b64encode(key.sign(anchor.anchor_hash.encode())).decode()
        anchor.key_id = certificate.key_id_of(key.public_key())
    else:
        log.warning("evidence.unsigned_anchor", seq=anchor.seq)
    session.add(anchor)
    await session.flush()
    session.add_all(Leaf(anchor_id=anchor.id, idx=i, media_id=m.id, sha256=m.sha256) for i, m in enumerate(media))
    await session.flush()
    return anchor


async def stamp_pending(session: AsyncSession, *, limit: int = 20) -> int:
    """Ask the time-stamping authority for the anchors still without a token. Failures are recorded, never raised."""
    if not get_settings().tsa_url:
        return 0
    pending = (
        await session.scalars(
            select(Anchor)
            .where(Anchor.tsa_url.is_not(None), Anchor.tsa_token.is_(None))
            .order_by(Anchor.seq)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()
    stamped = 0
    for anchor in pending:
        try:
            anchor.tsa_token = await tsa.timestamp(anchor.anchor_hash)
            anchor.tsa_error = None
            stamped += 1
        except tsa.TsaError as exc:
            anchor.tsa_error = str(exc)
            log.warning("evidence.tsa_failed", seq=anchor.seq, error=str(exc))
    await session.flush()
    return stamped


# ---------------------------------------------------------------- proofs and checks


async def leaves_of(session: AsyncSession, anchor_id: int) -> list[Leaf]:
    return list((await session.scalars(select(Leaf).where(Leaf.anchor_id == anchor_id).order_by(Leaf.idx))).all())


def anchor_out(anchor: Anchor) -> dict[str, Any]:
    return {
        "seq": anchor.seq,
        "from_at": anchor.from_at,
        "to_at": anchor.to_at,
        "media_count": anchor.media_count,
        "media_root": anchor.media_root,
        "audit_seq": anchor.audit_seq,
        "audit_hash": anchor.audit_hash,
        "prev_anchor_hash": anchor.prev_anchor_hash,
        "anchor_hash": anchor.anchor_hash,
        "signature": anchor.signature,
        "key_id": anchor.key_id,
        "time_stamped": anchor.tsa_token is not None,
        "created_at": anchor.created_at,
    }


async def proof_of(session: AsyncSession, media_id: uuid.UUID) -> dict[str, Any] | None:
    """The Merkle path of a media hash and its anchor, or None while it is not anchored yet."""
    leaf = await session.scalar(select(Leaf).where(Leaf.media_id == media_id))
    if leaf is None:
        return None
    anchor = await session.get(Anchor, leaf.anchor_id)
    assert anchor is not None
    hashes = [merkle.leaf_hash(lf.media_id, lf.sha256) for lf in await leaves_of(session, anchor.id)]
    public = known_public_keys().get(anchor.key_id or "")
    return {
        "media_id": media_id,
        "sha256": leaf.sha256,
        "leaf_index": leaf.idx,
        "leaf_hash": hashes[leaf.idx].hex(),
        "path": merkle.proof(hashes, leaf.idx),
        "anchor": anchor_out(anchor),
        "anchor_line": canonical(anchor),
        "public_key": certificate.b64(public) if public is not None else None,
        "method": {
            "leaf": "sha256(0x00 || media_id[16] || sha256[32])",
            "node": "sha256(0x01 || left || right), odd last node goes up unchanged",
            "anchor_hash": "sha256(anchor_line)",
            "signature": "Ed25519 over the ASCII of anchor_hash",
        },
    }


@dataclass
class ChainReport:
    anchors: int = 0
    media: int = 0
    first_broken_seq: int | None = None
    problems: list[dict[str, Any]] = field(default_factory=list)
    # Anchors sealed without any signing key configured: not tampering, but not proof against the database owner.
    unsigned: list[int] = field(default_factory=list)

    @property
    def intact(self) -> bool:
        return not self.problems

    def add(self, seq: int, problem: str, **details: Any) -> None:
        if self.first_broken_seq is None:
            self.first_broken_seq = seq
        self.problems.append({"seq": seq, "problem": problem, **details})

    def as_dict(self) -> dict[str, Any]:
        return {
            "intact": self.intact,
            "anchors": self.anchors,
            "media": self.media,
            "first_broken_seq": self.first_broken_seq,
            "problems": self.problems,
            "unsigned": self.unsigned,
        }


async def verify_chain(session: AsyncSession) -> ChainReport:
    """Re-check every anchor: chain, hash, signature, Merkle root, the audit entry it names and the media still kept."""
    report = ChainReport()
    keys = known_public_keys()
    previous: Anchor | None = None
    for anchor in (await session.scalars(select(Anchor).order_by(Anchor.seq))).all():
        report.anchors += 1
        expected_seq = previous.seq + 1 if previous else 1
        if anchor.seq != expected_seq:
            report.add(anchor.seq, "sequence_gap", expected=expected_seq)
        if anchor.prev_anchor_hash != (previous.anchor_hash if previous else None):
            report.add(anchor.seq, "chain_broken")
        if compute_hash(anchor) != anchor.anchor_hash:
            report.add(anchor.seq, "hash_mismatch")
        if anchor.signature is None:
            report.unsigned.append(anchor.seq)
        elif not signature_valid(anchor, keys):
            report.add(anchor.seq, "bad_signature", key_id=anchor.key_id)
        leaves = await leaves_of(session, anchor.id)
        report.media += len(leaves)
        hashes = [merkle.leaf_hash(lf.media_id, lf.sha256) for lf in leaves]
        if len(leaves) != anchor.media_count or (merkle.root(hashes) if hashes else None) != anchor.media_root:
            report.add(anchor.seq, "media_root_mismatch")
        if anchor.audit_seq is not None:
            kept = await session.scalar(select(AuditLog.hash).where(AuditLog.seq == anchor.audit_seq))
            if kept != anchor.audit_hash:
                report.add(anchor.seq, "audit_head_changed", audit_seq=anchor.audit_seq)
        if leaves:
            current = dict(
                (
                    await session.execute(
                        select(Media.id, Media.sha256).where(Media.id.in_([lf.media_id for lf in leaves]))
                    )
                ).all()
            )
            for lf in leaves:
                if lf.media_id in current and current[lf.media_id] != lf.sha256:
                    report.add(anchor.seq, "media_changed", media_id=str(lf.media_id))
        previous = anchor
    return report
