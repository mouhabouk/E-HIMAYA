"""Where a drone is, from the KLV metadata in its own video (MISB ST 0601, the UAS Datalink Local Set).

A drone or its ground station that follows MISB ST 0601 carries, beside the picture, a small packet a few times a
second: a 16-byte universal key, a BER length, then tag/length/value items. Only the items the room needs are read:

==  ===========================  =========  =========================================
 2  precision time stamp          uint64     microseconds since 1970-01-01 UTC
 5  platform heading              uint16     0..360 degrees
13  sensor latitude               int32      ±90 degrees (0x80000000: not known)
14  sensor longitude              int32      ±180 degrees (0x80000000: not known)
15  sensor true altitude          uint16     -900..19000 m
16  sensor horizontal field       uint16     0..180 degrees
18  sensor relative azimuth       uint32     0..360 degrees, from the heading
 1  checksum                      uint16     last item; a packet whose sum is wrong is dropped
==  ===========================  =========  =========================================

This module only reads. ``encode`` exists for the tests and the [SIM] track simulator.
"""

import struct
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

UAS_LS_KEY = bytes.fromhex("060E2B34020B01010E01030101000000")
CHECKSUM, TIMESTAMP, HEADING, LAT, LON, ALT, HFOV, AZIMUTH, VERSION = 1, 2, 5, 13, 14, 15, 16, 18, 65
_INT32_MAX = 2**31 - 1
_UNKNOWN = -(2**31)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class Fields:
    at: datetime | None = None
    lat: float | None = None
    lon: float | None = None
    alt_m: float | None = None
    heading_deg: float | None = None
    sensor_az_deg: float | None = None
    sensor_hfov_deg: float | None = None


def checksum(data: bytes) -> int:
    """The 16-bit running sum of ST 0601: even bytes in the high half, odd bytes in the low half."""
    total = 0
    for i, byte in enumerate(data):
        total += byte << (8 * ((i + 1) % 2))
    return total & 0xFFFF


def _ber_length(data: bytes, at: int) -> tuple[int, int]:
    """(length, offset after it) of a BER length; raises ValueError when it runs past the data."""
    first = data[at]
    if first < 0x80:
        return first, at + 1
    count = first & 0x7F
    if not 1 <= count <= 4 or at + 1 + count > len(data):
        raise ValueError("bad BER length")
    return int.from_bytes(data[at + 1 : at + 1 + count], "big"), at + 1 + count


def _ber_oid(data: bytes, at: int) -> tuple[int, int]:
    value = 0
    for i in range(at, min(at + 4, len(data))):
        value = (value << 7) | (data[i] & 0x7F)
        if data[i] < 0x80:
            return value, i + 1
    raise ValueError("bad tag")


def packets(data: bytes) -> Iterator[bytes]:
    """Every whole UAS Datalink packet in a chunk of the data stream (key, length and value)."""
    at = data.find(UAS_LS_KEY)
    while at >= 0:
        try:
            length, start = _ber_length(data, at + len(UAS_LS_KEY))
        except (ValueError, IndexError):
            return
        end = start + length
        if end > len(data):
            return
        yield data[at:end]
        at = data.find(UAS_LS_KEY, end)


def _scaled(raw: bytes, signed: bool, low: float, high: float) -> float | None:
    if signed:
        value = int.from_bytes(raw, "big", signed=True)
        if value == _UNKNOWN:
            return None
        return value * high / _INT32_MAX
    return low + int.from_bytes(raw, "big") * (high - low) / ((1 << (8 * len(raw))) - 1)


def decode(packet: bytes) -> Fields | None:
    """The fields of one packet, or None when it is not a UAS Datalink packet or its checksum is wrong."""
    if not packet.startswith(UAS_LS_KEY):
        return None
    try:
        length, at = _ber_length(packet, len(UAS_LS_KEY))
        end = at + length
        if end > len(packet):
            return None
        items: dict[int, bytes] = {}
        while at < end:
            tag, at = _ber_oid(packet, at)
            size, at = _ber_length(packet, at)
            if at + size > end:
                return None
            if tag == CHECKSUM:
                if size != 2 or at + size != end or checksum(packet[:at]) != int.from_bytes(packet[at:end], "big"):
                    return None
                break
            items[tag] = packet[at : at + size]
            at += size
        else:
            return None  # ST 0601 requires the checksum
    except (ValueError, IndexError):
        return None
    when = None
    if len(items.get(TIMESTAMP, b"")) == 8:
        (micros,) = struct.unpack(">Q", items[TIMESTAMP])
        when = datetime.fromtimestamp(micros / 1_000_000, UTC)

    def item(tag: int, size: int, signed: bool, low: float, high: float) -> float | None:
        raw = items.get(tag)
        return _scaled(raw, signed, low, high) if raw is not None and len(raw) == size else None

    heading = item(HEADING, 2, False, 0, 360)
    azimuth = item(AZIMUTH, 4, False, 0, 360)
    hfov = item(HFOV, 2, False, 0, 180)
    return Fields(
        at=when,
        lat=item(LAT, 4, True, -90, 90),
        lon=item(LON, 4, True, -180, 180),
        alt_m=item(ALT, 2, False, -900, 19000),
        heading_deg=None if heading is None else heading % 360,
        sensor_az_deg=None if azimuth is None else azimuth % 360,
        sensor_hfov_deg=hfov if hfov else None,
    )


def _ber(length: int) -> bytes:
    if length < 0x80:
        return bytes([length])
    raw = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(raw)]) + raw


def _unsigned(value: float, size: int, low: float, high: float) -> bytes:
    top = (1 << (8 * size)) - 1
    return min(max(round((value - low) / (high - low) * top), 0), top).to_bytes(size, "big")


def encode(fields: Fields) -> bytes:
    """A UAS Datalink packet of ``fields`` (tests and the [SIM] simulator only)."""
    items: list[tuple[int, bytes]] = []
    if fields.at is not None:
        micros = round((fields.at - _EPOCH).total_seconds() * 1_000_000)
        items.append((TIMESTAMP, struct.pack(">Q", micros)))
    if fields.heading_deg is not None:
        items.append((HEADING, _unsigned(fields.heading_deg % 360, 2, 0, 360)))
    for tag, value, high in ((LAT, fields.lat, 90), (LON, fields.lon, 180)):
        raw = _UNKNOWN if value is None else round(value / high * _INT32_MAX)
        items.append((tag, raw.to_bytes(4, "big", signed=True)))
    if fields.alt_m is not None:
        items.append((ALT, _unsigned(fields.alt_m, 2, -900, 19000)))
    if fields.sensor_hfov_deg is not None:
        items.append((HFOV, _unsigned(fields.sensor_hfov_deg, 2, 0, 180)))
    if fields.sensor_az_deg is not None:
        items.append((AZIMUTH, _unsigned(fields.sensor_az_deg % 360, 4, 0, 360)))
    items.append((VERSION, bytes([19])))
    body = b"".join(bytes([tag]) + _ber(len(value)) + value for tag, value in items)
    body += bytes([CHECKSUM, 2])
    head = UAS_LS_KEY + _ber(len(body) + 2)
    return head + body + checksum(head + body).to_bytes(2, "big")
