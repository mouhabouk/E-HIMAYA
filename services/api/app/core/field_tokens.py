"""Tokens of the field agents' phones (phase F, docs/phase-f/design-f.md §1).

A field agent activates their phone with their professional number and a one-time code from the room chief; the
platform then issues its own tokens instead of a Keycloak sign-in. They come from one issuer only
(``urn:ehimaya:field``), signed HS256 with a key derived from the platform secret: no other issuer is ever verified
with that key or that algorithm. The access token lives a few minutes; the refresh token is opaque, bound to the phone,
stored as a hash and replaced at each use. The two factors are the activated phone and the PIN that guards it.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import get_settings

ISSUER = "urn:ehimaya:field"
#: Its own audience: a field token is never mistaken for one of the identity provider's.
AUDIENCE = "urn:ehimaya:field:api"
ALGORITHM = "HS256"
ACCESS_TTL = timedelta(minutes=10)
#: The amr values of a field token: the activated phone (hardware key) and its PIN.
AMR = ["hwk", "pin"]


def _derived(label: bytes) -> bytes:
    secret = get_settings().anon_pseudonym_secret.get_secret_value().encode()
    return hmac.new(secret, b"ehimaya.field." + label, hashlib.sha256).digest()


def signing_key() -> bytes:
    return _derived(b"token.v1")


def fingerprint(value: str) -> str:
    """Hash of a code or refresh token as stored (never the value itself)."""
    return hmac.new(_derived(b"secret.v1"), value.encode(), hashlib.sha256).hexdigest()


def new_refresh() -> str:
    return secrets.token_urlsafe(32)


def issue(
    *,
    subject: str,
    name: str | None,
    username: str,
    roles: list[str],
    gouvernorat_code: int,
    device_id: str,
    now: datetime | None = None,
) -> tuple[str, datetime]:
    """An access token with the same claims the API reads from a staff Keycloak token."""
    now = now or datetime.now(UTC)
    expires = now + ACCESS_TTL
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "amr": AMR,
        "name": name,
        "preferred_username": username,
        "realm_access": {"roles": roles},
        "scope_level": "regional",
        "gouvernorat_code": gouvernorat_code,
        "device_id": device_id,
    }
    return jwt.encode(claims, signing_key(), algorithm=ALGORITHM), expires
