"""Minimal RFC 3161 client: asks a time-stamping authority to time-stamp an anchor hash.

The request is built by hand (DER) so no ASN.1 library is needed. The response is stored as received; checking the
token's certificate chain is left to the verifier's tools (``openssl ts -verify``).
"""

import secrets

import httpx

from app.core.config import get_settings

# id-sha256 (2.16.840.1.101.3.4.2.1)
_SHA256_OID = bytes.fromhex("0609608648016503040201")


class TsaError(Exception):
    pass


def _tlv(tag: int, body: bytes) -> bytes:
    n = len(body)
    if n < 0x80:
        length = bytes([n])
    else:
        raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
        length = bytes([0x80 | len(raw)]) + raw
    return bytes([tag]) + length + body


def _integer(value: int) -> bytes:
    raw = value.to_bytes(max(1, (value.bit_length() + 8) // 8), "big")  # leading 0 keeps it positive
    return _tlv(0x02, raw)


def request(digest: bytes, nonce: int) -> bytes:
    """``TimeStampReq`` for a SHA-256 digest, with a nonce and ``certReq`` true."""
    algorithm = _tlv(0x30, _SHA256_OID + b"\x05\x00")
    imprint = _tlv(0x30, algorithm + _tlv(0x04, digest))
    return _tlv(0x30, _integer(1) + imprint + _integer(nonce) + b"\x01\x01\xff")


def granted(response: bytes) -> bool:
    """``PKIStatus`` of a ``TimeStampResp`` is granted (0) or grantedWithMods (1)."""
    # TimeStampResp ::= SEQUENCE { status PKIStatusInfo ::= SEQUENCE { status INTEGER, ... }, token ... }
    try:
        pos = 1
        pos += 1 + (response[pos] & 0x7F if response[pos] & 0x80 else 0)  # outer length
        if response[pos] != 0x30:
            return False
        pos += 1
        pos += 1 + (response[pos] & 0x7F if response[pos] & 0x80 else 0)  # PKIStatusInfo length
        if response[pos] != 0x02 or response[pos + 1] != 1:
            return False
        return response[pos + 2] in (0, 1)
    except IndexError:
        return False


async def timestamp(anchor_hash: str, *, transport: httpx.AsyncBaseTransport | None = None) -> bytes:
    """The authority's response for ``anchor_hash`` (hex); raises :class:`TsaError` on any failure."""
    settings = get_settings()
    if not settings.tsa_url:
        raise TsaError("not_configured")
    # The anchor hash is itself a SHA-256: it is the message imprint (``openssl ts -verify -digest <anchor_hash>``).
    body = request(bytes.fromhex(anchor_hash), secrets.randbits(63))
    try:
        async with httpx.AsyncClient(timeout=settings.tsa_timeout_s, transport=transport) as client:
            r = await client.post(
                settings.tsa_url, content=body, headers={"Content-Type": "application/timestamp-query"}
            )
    except httpx.HTTPError as exc:
        raise TsaError(type(exc).__name__) from exc
    if r.status_code != 200:
        raise TsaError(f"http_{r.status_code}")
    if not granted(r.content):
        raise TsaError("not_granted")
    return r.content
