"""The reference edge program of a watch tower (L5b, design-l5.md §3.2), on a recorded video [SIM]: about one frame a
second, the room's 3-of-5 rule, one signed event per label within the cool-down, the confirming frame as a JPEG, and
the same signature as the API and the gateway check."""

import base64
import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import av
import numpy as np
import pytest
from pydantic import ValidationError

from app import edge
from app.processing import Detection

KEY = "00" * 32
RED = (220, 40, 20)
GREY = (90, 90, 90)


def recorded(path: Path, colours: list[tuple[int, int, int]], fps: int = 2) -> Path:
    """A [SIM] recording: ``fps`` frames a second, one colour per second (red stands for fire)."""
    with av.open(str(path), "w") as container:
        stream = container.add_stream("mpeg4", rate=fps)
        stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
        for colour in colours:
            for _ in range(fps):
                picture = np.full((48, 64, 3), colour, dtype=np.uint8)
                for packet in stream.encode(av.VideoFrame.from_ndarray(picture, format="rgb24")):
                    container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


def fake_detect(frame: np.ndarray) -> list[Detection]:
    """Stands in for the ONNX detector: a red picture is a fire, nothing else is anything."""
    r, g = float(frame[..., 0].mean()), float(frame[..., 1].mean())
    return [Detection("fire", 0.82, (0.1, 0.1, 0.9, 0.9))] if r > 150 and g < 100 else []


def settings(source: Path, **extra: object) -> edge.EdgeSettings:
    return edge.EdgeSettings(
        tower="JND-TWR-1", key=KEY, source=str(source), gateway_url="http://10.0.0.5:8088", **extra
    )


def test_signature_matches_the_api_and_the_gateway() -> None:
    expected = "da3de1c6f641ec22d489b15c5bb21af095bb49ba96726ef0440bf02abb79d959"
    assert edge.sign(KEY, "TWR-1", "2026-10-28T20:00:00+00:00", "fire", "0.87", "3", "5", "") == expected


def test_settings_refuse_a_bad_key_or_gateway() -> None:
    with pytest.raises(ValidationError):
        edge.EdgeSettings(tower="T1", key="AB" * 32, source="x.mp4", gateway_url="http://10.0.0.5:8088")
    with pytest.raises(ValidationError):
        edge.EdgeSettings(tower="T1", key=KEY, source="x.mp4", gateway_url="ftp://10.0.0.5")


def test_three_of_five_and_cool_down() -> None:
    confirmer = edge.Confirmer(alert=0.6, cooldown_s=300)
    fire = [Detection("fire", 0.8, (0, 0, 1, 1))]
    smoke = [Detection("smoke", 0.5, (0, 0, 1, 1))]
    seen = [confirmer.add(d, float(t)) for t, d in enumerate([fire, [], fire, smoke, fire, fire, fire])]
    # Third hit at t=4 (frames 0..4), newest frame on fire; then rests; smoke under the alert never counts.
    assert seen[4] == {"fire": (0.8, 3)} and all(not s for i, s in enumerate(seen) if i != 4)
    # After the cool-down, the window (smoke and four fires) confirms again.
    assert confirmer.add(fire, 400.0) == {"fire": (0.8, 4)}


def test_watches_a_recorded_video_and_posts_one_signed_event(tmp_path: Path) -> None:
    video = recorded(tmp_path / "tower.mp4", [GREY] * 4 + [RED] * 7 + [GREY])
    posted: list[dict[str, str]] = []
    s = settings(video)
    at = datetime(2026, 10, 28, 20, 0, tzinfo=UTC)
    with edge.frames_of(str(video), 5.0) as frames:
        times: list[float] = []

        def spy() -> Iterator[tuple[float, edge.Callable[[], np.ndarray]]]:
            for t, decode in frames:
                times.append(t)
                yield t, decode

        sent = edge.watch(s, spy(), fake_detect, posted.append, "SIM", now=lambda: at)
    assert sent == 1 and len(posted) == 1
    body = posted[0]
    assert set(body) == {"tower", "at", "label", "confidence", "hits", "frames", "model", "frame_jpeg_b64", "sig"}
    assert (body["tower"], body["label"], body["confidence"], body["hits"], body["frames"]) == (
        "JND-TWR-1",
        "fire",
        "0.82",
        "3",
        "5",
    )
    frame = base64.b64decode(body["frame_jpeg_b64"])
    assert frame.startswith(b"\xff\xd8\xff")
    sha = hashlib.sha256(frame).hexdigest()
    fields = (body["tower"], body["at"], body["label"], body["confidence"], body["hits"], body["frames"], sha)
    assert body["sig"] == edge.sign(KEY, *fields) and body["at"] == "2026-10-28T20:00:00+00:00"
    # Two frames a second recorded, about one analysed: the whole video was read.
    assert len(times) == 24
