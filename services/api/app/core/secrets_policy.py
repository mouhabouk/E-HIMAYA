"""Start-up refusal of weak or example secrets when APP_ENV=production (A3).

Every SecretStr setting is checked, plus the passwords embedded in the database, Valkey and NATS URLs, so a secret
added later is covered without touching this module. A value is refused when it still carries an example marker
from .env.example ("change-me"…), is shorter than 16 characters, or has too little variety to be random (a base64
key is judged on its decoded bytes). The messages name the setting, never the value.
"""

import base64
import binascii
import math
import re
from collections import Counter
from collections.abc import Iterator
from urllib.parse import urlsplit

from pydantic import BaseModel, SecretStr

MIN_LENGTH = 16
# Bits per character (text) or per byte (decoded key) below which a value is not random enough.
MIN_TEXT_ENTROPY = 3.0
MIN_KEY_ENTROPY = 3.5
MIN_DISTINCT = 8
_MARKERS = (
    "change-me",
    "changeme",
    "change_me",
    "replace-me",
    "example",
    "placeholder",
    "password",
    "secret-here",
    "test-secret",
    "ci-only",
    "sim-sms-token",
)
_URL_SETTINGS = ("database_url", "migration_database_url", "valkey_url", "nats_url")
_KEYRING_ENTRY = re.compile(r"^\s*\d{1,3}\s*:\s*(\S+)\s*$")


def shannon_entropy(data: str | bytes) -> float:
    """Bits per symbol of ``data`` (0 for empty)."""
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    return -sum(n / total * math.log2(n / total) for n in counts.values())


def _decoded_key(value: str) -> bytes | None:
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None
    return raw if len(raw) == 32 else None


def weak_reason(value: str) -> str | None:
    """Why ``value`` is not acceptable as a production secret, or None."""
    lowered = value.lower()
    for marker in _MARKERS:
        if marker in lowered:
            return f'contains the example marker "{marker}"'
    # Key rings ("2:<base64>,3:<base64>") are judged key by key.
    entries = [m.group(1) for part in value.split(",") if (m := _KEYRING_ENTRY.match(part))]
    if entries and len(entries) == len([p for p in value.split(",") if p.strip()]):
        for entry in entries:
            reason = weak_reason(entry)
            if reason:
                return reason
        return None
    key = _decoded_key(value)
    if key is not None:
        if shannon_entropy(key) < MIN_KEY_ENTROPY or len(set(key)) < MIN_DISTINCT:
            return "is a 32-byte key with too little randomness (openssl rand -base64 32)"
        return None
    if len(value) < MIN_LENGTH:
        return f"is shorter than {MIN_LENGTH} characters"
    if shannon_entropy(value) < MIN_TEXT_ENTROPY or len(set(value)) < MIN_DISTINCT:
        return "has too little variety to be random (openssl rand -hex 32)"
    return None


def _secrets(settings: BaseModel) -> Iterator[tuple[str, str]]:
    for name in type(settings).model_fields:
        value = getattr(settings, name)
        if isinstance(value, SecretStr):
            yield name, value.get_secret_value()
        elif name in _URL_SETTINGS and isinstance(value, str) and value:
            password = urlsplit(value).password
            if password is not None:
                yield f"{name} (password)", password


def production_problems(settings: BaseModel) -> list[str]:
    """One line per weak secret, ready for the start-up error."""
    problems: list[str] = []
    for name, secret in _secrets(settings):
        reason = weak_reason(secret)
        if reason:
            problems.append(f"{name.upper()} {reason}")
    return problems
