"""Field-level encryption for sensitive personal data (NFR-05) and keyed hashes for lookups.

Ciphertext layout: ``version (1 byte) | nonce (12 bytes) | AES-256-GCM ciphertext+tag``.
The version byte lets a future key rotation re-encrypt rows progressively.
"""

import base64
import binascii
import hashlib
import hmac
import os
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

_VERSION = 1
_NONCE_BYTES = 12


class FieldCipher:
    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("field encryption key must be 32 bytes")
        self._aead = AESGCM(key)
        # Independent sub-key for blind indexes, so the hash never reveals anything about the cipher key.
        self._index_key = hmac.new(key, b"ehimaya/blind-index/v1", hashlib.sha256).digest()

    def encrypt(self, plaintext: str, *, context: str) -> bytes:
        nonce = os.urandom(_NONCE_BYTES)
        sealed = self._aead.encrypt(nonce, plaintext.encode("utf-8"), context.encode("ascii"))
        return bytes([_VERSION]) + nonce + sealed

    def decrypt(self, blob: bytes, *, context: str) -> str:
        if not blob or blob[0] != _VERSION:
            raise ValueError("unsupported ciphertext version")
        nonce, sealed = blob[1 : 1 + _NONCE_BYTES], blob[1 + _NONCE_BYTES :]
        return self._aead.decrypt(nonce, sealed, context.encode("ascii")).decode("utf-8")

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
    return FieldCipher(decode_key(get_settings().field_encryption_key.get_secret_value()))


def pseudonym(device_key: bytes) -> bytes:
    """Anonymous reporter pseudonym (BR-02): HMAC of the device key, not reversible to a person."""
    secret = get_settings().anon_pseudonym_secret.get_secret_value().encode()
    return hmac.new(secret, device_key, hashlib.sha256).digest()
