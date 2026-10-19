"""Field-level encryption of personal data at rest (NFR-05, law 2004-63) and keyed hashes for lookups.

Ciphertext layout: ``key version (1 byte) | nonce (12 bytes) | AES-256-GCM ciphertext+tag``. The column
(or purpose) is bound as associated data (``context``), so a value copied into another column does not
decrypt. Key rotation: ``FIELD_ENCRYPTION_KEYS`` adds versions, new values use the active one, every
configured version stays readable, and ``python -m app.modules.privacy.cli reencrypt`` moves old rows.

Blind indexes (exact-match lookups without decrypting) use a sub-key of FIELD_ENCRYPTION_KEY (version 1)
that does not change with rotation, so lookups keep working while rows are re-encrypted.
"""

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import unicodedata
from collections.abc import Mapping
from functools import lru_cache
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import LargeBinary
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

from app.core.config import get_settings, parse_keyring

_NONCE_BYTES = 12
SEARCH_TOKEN_BYTES = 12
_MAX_SEARCH_TERMS = 300


class FieldCipher:
    def __init__(self, keys: Mapping[int, bytes] | bytes, *, active: int | None = None) -> None:
        ring = {1: keys} if isinstance(keys, bytes) else dict(keys)
        if not ring or 1 not in ring:
            raise ValueError("key version 1 (FIELD_ENCRYPTION_KEY) is required")
        for version, key in ring.items():
            if not 1 <= version <= 255:
                raise ValueError("key versions are 1..255")
            if len(key) != 32:
                raise ValueError("field encryption keys must be 32 bytes")
        self.active = active if active is not None else max(ring)
        if self.active not in ring:
            raise ValueError("the active key version is not configured")
        self._aeads = {version: AESGCM(key) for version, key in ring.items()}
        # Independent sub-key for blind indexes, so the hash never reveals anything about the cipher key.
        self._index_key = hmac.new(ring[1], b"ehimaya/blind-index/v1", hashlib.sha256).digest()

    @property
    def versions(self) -> frozenset[int]:
        return frozenset(self._aeads)

    def encrypt(self, plaintext: str, *, context: str) -> bytes:
        nonce = os.urandom(_NONCE_BYTES)
        sealed = self._aeads[self.active].encrypt(nonce, plaintext.encode("utf-8"), context.encode("ascii"))
        return bytes([self.active]) + nonce + sealed

    def decrypt(self, blob: bytes, *, context: str) -> str:
        aead = self._aeads.get(blob[0]) if blob else None
        if aead is None:
            raise ValueError("unsupported ciphertext version")
        nonce, sealed = blob[1 : 1 + _NONCE_BYTES], blob[1 + _NONCE_BYTES :]
        return aead.decrypt(nonce, sealed, context.encode("ascii")).decode("utf-8")

    def blind_index(self, value: str, *, context: str) -> bytes:
        """Deterministic keyed hash, for uniqueness checks and exact-match search without decrypting."""
        return hmac.new(self._index_key, f"{context}:{value}".encode(), hashlib.sha256).digest()


def decode_key(encoded: str) -> bytes:
    try:
        return base64.b64decode(encoded, validate=True)
    except binascii.Error as exc:
        raise ValueError("field encryption key must be base64") from exc


@lru_cache
def get_cipher() -> FieldCipher:
    settings = get_settings()
    keys = {1: decode_key(settings.field_encryption_key.get_secret_value())}
    if settings.field_encryption_keys is not None:
        keys.update(parse_keyring(settings.field_encryption_keys.get_secret_value()))
    return FieldCipher(keys, active=settings.field_encryption_active_version)


def pseudonym(device_key: bytes) -> bytes:
    """Anonymous reporter pseudonym (BR-02): HMAC of the device key, not reversible to a person."""
    secret = get_settings().anon_pseudonym_secret.get_secret_value().encode()
    return hmac.new(secret, device_key, hashlib.sha256).digest()


# ---------------------------------------------------------------- encrypted columns


class EncryptedText(TypeDecorator[str]):
    """A ``bytea`` column holding an encrypted string; the ORM attribute is the clear text.

    Only equality with NULL is meaningful in SQL: never filter or sort on such a column.
    """

    impl = LargeBinary
    cache_ok = True

    def __init__(self, context: str) -> None:
        super().__init__()
        self.context = context

    def process_bind_param(self, value: str | None, dialect: Dialect) -> bytes | None:
        return None if value is None else get_cipher().encrypt(value, context=self.context)

    def process_result_value(self, value: Any, dialect: Dialect) -> str | None:
        return None if value is None else get_cipher().decrypt(bytes(value), context=self.context)


class EncryptedJSON(TypeDecorator[Any]):
    """A ``bytea`` column holding an encrypted JSON document (replace the value to change it)."""

    impl = LargeBinary
    cache_ok = True

    def __init__(self, context: str) -> None:
        super().__init__()
        self.context = context

    def process_bind_param(self, value: Any, dialect: Dialect) -> bytes | None:
        if value is None:
            return None
        return get_cipher().encrypt(json.dumps(value, ensure_ascii=False, default=str), context=self.context)

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:
        return None if value is None else json.loads(get_cipher().decrypt(bytes(value), context=self.context))


# ---------------------------------------------------------------- sealed JSON envelopes (domain events)

SEALED_KEY = "sealed"


def seal(payload: dict[str, Any], *, context: str) -> dict[str, str]:
    text = json.dumps(payload, default=str, ensure_ascii=False)
    return {SEALED_KEY: base64.b64encode(get_cipher().encrypt(text, context=context)).decode("ascii")}


def unseal(payload: dict[str, Any], *, context: str) -> dict[str, Any]:
    """Open an envelope made by ``seal``; any other document (written before sealing) is returned as is."""
    if set(payload) != {SEALED_KEY} or not isinstance(payload[SEALED_KEY], str):
        return payload
    opened: dict[str, Any] = json.loads(get_cipher().decrypt(base64.b64decode(payload[SEALED_KEY]), context=context))
    return opened


# ---------------------------------------------------------------- word search over encrypted text

_ARABIC_MARKS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_ARABIC_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})
_WORD = re.compile(r"\w{2,}")


def search_terms(text: str) -> list[str]:
    """Normalised words of a text: case, Latin accents, Arabic diacritics and letter variants folded."""
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(c for c in folded if not unicodedata.combining(c) or "؀" <= c <= "ۿ")
    folded = _ARABIC_MARKS.sub("", unicodedata.normalize("NFKC", folded)).translate(_ARABIC_FOLD)
    return list(dict.fromkeys(_WORD.findall(folded)))[:_MAX_SEARCH_TERMS]


def search_tokens(texts: list[str | None], *, context: str) -> list[bytes]:
    """Blind-index tokens of every word (whole-word search without storing the words)."""
    cipher = get_cipher()
    words = dict.fromkeys(w for t in texts if t for w in search_terms(t))
    return [cipher.blind_index(w, context=context)[:SEARCH_TOKEN_BYTES] for w in words]
