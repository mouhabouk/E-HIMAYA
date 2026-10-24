"""The phone's side of a locked medical file (docs/phase-c/design-medical-axis.md §12), for the tests.

The same format as apps/mobile/lib/core/crypto/medical_crypto.dart:

* file: AES-256-GCM with a random 32-byte key (DEK), 12-byte nonce, no associated data;
* key for one doctor: ephemeral X25519 with the doctor's public key, HKDF-SHA256 (salt = ephemeral public key ‖
  doctor public key, info = ``ehimaya-medical-v1``, 32 bytes), then AES-256-GCM of the DEK (48 bytes);
* doctor's backup: Argon2id of the code (16-byte salt), then AES-256-GCM of the 32-byte private key.
"""

import base64
import json
import os
import uuid
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

INFO = b"ehimaya-medical-v1"
RAW = serialization.Encoding.Raw


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode()


def raw_public(key: X25519PrivateKey | X25519PublicKey) -> bytes:
    public = key.public_key() if isinstance(key, X25519PrivateKey) else key
    return public.public_bytes(RAW, serialization.PublicFormat.Raw)


def _kek(shared: bytes, eph_public: bytes, doctor_public: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=eph_public + doctor_public, info=INFO).derive(shared)


def lock(data: dict[str, Any], doctors: list[tuple[uuid.UUID | str, bytes]]) -> dict[str, Any]:
    dek = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    keys = []
    for doctor_id, doctor_public in doctors:
        eph = X25519PrivateKey.generate()
        eph_public = raw_public(eph)
        kek = _kek(eph.exchange(X25519PublicKey.from_public_bytes(doctor_public)), eph_public, doctor_public)
        key_nonce = os.urandom(12)
        keys.append(
            {
                "doctor_id": str(doctor_id),
                "eph_public": b64(eph_public),
                "nonce": b64(key_nonce),
                "wrapped": b64(AESGCM(kek).encrypt(key_nonce, dek, None)),
            }
        )
    ciphertext = AESGCM(dek).encrypt(nonce, json.dumps(data).encode(), None)
    return {"nonce": b64(nonce), "ciphertext": b64(ciphertext), "keys": keys}


def open_file(opened: dict[str, Any], private: X25519PrivateKey) -> dict[str, Any]:
    eph_public = base64.b64decode(opened["eph_public"])
    kek = _kek(private.exchange(X25519PublicKey.from_public_bytes(eph_public)), eph_public, raw_public(private))
    dek = AESGCM(kek).decrypt(base64.b64decode(opened["key_nonce"]), base64.b64decode(opened["wrapped"]), None)
    plain = AESGCM(dek).decrypt(base64.b64decode(opened["nonce"]), base64.b64decode(opened["ciphertext"]), None)
    return json.loads(plain)  # type: ignore[no-any-return]


def backup(private: X25519PrivateKey, code: str, memory_kib: int = 8192, iterations: int = 1) -> dict[str, Any]:
    salt, nonce = os.urandom(16), os.urandom(12)
    kek = Argon2id(salt=salt, length=32, iterations=iterations, lanes=1, memory_cost=memory_kib).derive(code.encode())
    secret = private.private_bytes(RAW, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    return {
        "kdf": "argon2id",
        "memory_kib": memory_kib,
        "iterations": iterations,
        "parallelism": 1,
        "salt": b64(salt),
        "nonce": b64(nonce),
        "ciphertext": b64(AESGCM(kek).encrypt(nonce, secret, None)),
    }


def restore(saved: dict[str, Any], code: str) -> X25519PrivateKey:
    kek = Argon2id(
        salt=base64.b64decode(saved["salt"]),
        length=32,
        iterations=saved["iterations"],
        lanes=saved["parallelism"],
        memory_cost=saved["memory_kib"],
    ).derive(code.encode())
    secret = AESGCM(kek).decrypt(base64.b64decode(saved["nonce"]), base64.b64decode(saved["ciphertext"]), None)
    return X25519PrivateKey.from_private_bytes(secret)
