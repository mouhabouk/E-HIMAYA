"""The drone position reader (L5b, design-l5.md §3.3): MISB ST 0601 packets decoded (the standard's own example values,
the checksum, a missing position), a recorded MPEG-TS with a KLV data stream read like a MediaMTX stream [SIM], the
points batched to the API, and the [SIM] track."""

import fractions
from datetime import UTC, datetime
from pathlib import Path

import av
import numpy as np
import pytest

from app import klv, telemetry

AT = datetime(2026, 10, 28, 20, 0, tzinfo=UTC)
FIELDS = klv.Fields(at=AT, lat=36.78, lon=8.69, alt_m=120.0, heading_deg=90.0, sensor_az_deg=45.0, sensor_hfov_deg=60.0)


def test_scaling_matches_the_standard_examples() -> None:
    body = b"".join(
        bytes([tag, len(raw)]) + raw
        for tag, raw in (
            (klv.TIMESTAMP, bytes.fromhex("000459F4A6AA4AA8")),
            (klv.HEADING, bytes.fromhex("71C2")),
            (klv.LAT, bytes.fromhex("5595B66D")),
            (klv.LON, bytes.fromhex("5B5360C4")),
            (klv.HFOV, bytes.fromhex("CD9C")),
        )
    )
    body += bytes([klv.CHECKSUM, 2])
    head = klv.UAS_LS_KEY + bytes([len(body) + 2])
    fields = klv.decode(head + body + klv.checksum(head + body).to_bytes(2, "big"))
    assert fields is not None
    assert fields.at == datetime(2008, 10, 24, 0, 13, 29, 913000, tzinfo=UTC)
    assert fields.heading_deg == pytest.approx(159.9744, abs=1e-3)
    assert fields.lat == pytest.approx(60.17682296, abs=1e-6)
    assert fields.lon == pytest.approx(128.42675904, abs=1e-6)
    assert fields.sensor_hfov_deg == pytest.approx(144.5713, abs=1e-3)


def test_round_trip_checksum_and_unknown_position() -> None:
    packet = klv.encode(FIELDS)
    fields = klv.decode(packet)
    assert fields is not None and fields.at == AT
    assert fields.lat == pytest.approx(36.78, abs=1e-6) and fields.lon == pytest.approx(8.69, abs=1e-6)
    assert fields.alt_m == pytest.approx(120.0, abs=0.5) and fields.sensor_az_deg == pytest.approx(45.0, abs=1e-6)
    # One flipped byte, or no checksum at all: the packet is dropped.
    broken = bytearray(packet)
    broken[30] ^= 0x01
    assert klv.decode(bytes(broken)) is None
    assert klv.decode(packet[:-4]) is None and klv.decode(b"\x00" * 40) is None
    # Without a position the packet is read, but gives no point.
    unknown = klv.decode(klv.encode(klv.Fields(at=AT)))
    assert unknown is not None and unknown.lat is None and telemetry.point_of(unknown) is None
    # Several packets in one chunk, with noise between them.
    chunk = b"noise" + packet + b"\x00\x01" + klv.encode(FIELDS) + packet[:10]
    assert len(list(klv.packets(chunk))) == 2
    point = telemetry.point_of(fields)
    assert point is not None and point["at"] == AT.isoformat() and point["heading_deg"] == 90.0


def recorded(path: Path, seconds: int = 6) -> Path:
    """A [SIM] MPEG-TS like a drone's: a picture and a KLV data stream, one packet a second."""
    with av.open(str(path), "w", format="mpegts") as container:
        video = container.add_stream("mpeg2video", rate=1)
        video.width, video.height, video.pix_fmt = 64, 48, "yuv420p"
        data = container.add_data_stream("klv")
        for i in range(seconds):
            frame = av.VideoFrame.from_ndarray(np.zeros((48, 64, 3), np.uint8), format="rgb24")
            frame.pts = i
            for packet in video.encode(frame):
                container.mux(packet)
            fields = klv.Fields(at=AT.replace(second=i), lat=36.78 + i / 1000, lon=8.69, alt_m=100.0)
            packet = av.Packet(klv.encode(fields))
            packet.stream = data
            packet.pts = packet.dts = i * 90_000
            packet.time_base = fractions.Fraction(1, 90_000)
            container.mux(packet)
        for packet in video.encode():
            container.mux(packet)
    return path


def test_reads_a_recorded_stream_and_posts_batches(tmp_path: Path) -> None:
    source = recorded(tmp_path / "drone.ts")
    posted: list[tuple[str, list[telemetry.Point]]] = []
    ticks = iter(range(100))
    with telemetry.data_of(str(source), 5.0) as chunks:
        sent = telemetry.follow(
            "d1", telemetry.points_of(chunks), lambda d, p: posted.append((d, p)), 2.0, lambda: float(next(ticks))
        )
    assert sent == 6 and all(d == "d1" for d, _ in posted)
    points = [p for _, batch in posted for p in batch]
    assert [p["lat"] for p in points] == pytest.approx([36.78 + i / 1000 for i in range(6)], abs=1e-6)
    assert len(posted) > 1 and all(len(batch) <= telemetry.MAX_POINTS for _, batch in posted)


def test_a_video_without_klv_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "plain.ts"
    with av.open(str(path), "w", format="mpegts") as container:
        video = container.add_stream("mpeg2video", rate=1)
        video.width, video.height, video.pix_fmt = 64, 48, "yuv420p"
        for packet in video.encode(av.VideoFrame.from_ndarray(np.zeros((48, 64, 3), np.uint8), format="rgb24")):
            container.mux(packet)
        for packet in video.encode():
            container.mux(packet)
    with pytest.raises(LookupError), telemetry.data_of(str(path), 5.0):
        pass


def test_simulated_track_is_a_lap_with_the_battery_running_down() -> None:
    track = list(telemetry.simulated_track(36.78, 8.69, AT, minutes=2, every_s=2))
    assert len(track) == 60
    first, last = track[0], track[-1]
    assert first[1] == 60.0 and last[1] == 15.0
    assert first[0].lat == pytest.approx(36.78 + 1500 / 111_320) and first[0].heading_deg == 90.0
    for fields, _ in track:
        decoded = klv.decode(klv.encode(fields))
        assert decoded is not None and telemetry.point_of(decoded) is not None
