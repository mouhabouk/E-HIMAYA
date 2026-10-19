import pytest

from app.modules.reports import sniff


@pytest.mark.parametrize(
    ("declared", "head", "detected"),
    [
        ("image/jpeg", b"\xff\xd8\xff\xe1\x00\x18Exif", "jpeg"),
        ("image/png", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", "png"),
        ("image/webp", b"RIFF\x24\x00\x00\x00WEBPVP8 ", "webp"),
        ("image/heic", b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00", "heif"),
        ("image/heif", b"\x00\x00\x00\x18ftypmif1\x00\x00\x00\x00", "heif"),
        ("video/mp4", b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00", "iso-bmff"),
        ("video/quicktime", b"\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00", "iso-bmff"),
        ("video/3gpp", b"\x00\x00\x00\x18ftyp3gp4\x00\x00\x00\x00", "iso-bmff"),
        ("audio/mp4", b"\x00\x00\x00\x20ftypM4A \x00\x00\x00\x00", "iso-bmff"),
        ("video/webm", b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81", "webm"),
        ("audio/webm", b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81", "webm"),
        ("audio/ogg", b"OggS\x00\x02\x00\x00", "ogg"),
        ("audio/wav", b"RIFF\x24\x08\x00\x00WAVEfmt ", "wav"),
        ("audio/mpeg", b"ID3\x04\x00\x00\x00\x00", "mp3"),
        ("audio/mpeg", b"\xff\xfb\x90\x64\x00", "mp3"),
        ("audio/aac", b"\xff\xf1\x50\x80\x02\x1f", "aac"),
    ],
)
def test_allowed_formats_are_recognised(declared: str, head: bytes, detected: str) -> None:
    result = sniff.verify(declared, head)
    assert result.reason is None and result.verified_type == declared and result.detected == detected


@pytest.mark.parametrize(
    "head",
    [
        b"<!DOCTYPE html><html>",
        b'<svg xmlns="http://www.w3.org/2000/svg">',
        b"%PDF-1.7\n",
        b"PK\x03\x04\x14\x00",
        b"MZ\x90\x00",
        b"\x00\x00\x00\x1cftypavif\x00\x00\x00\x00",
        b"",
    ],
)
def test_other_content_is_disallowed(head: bytes) -> None:
    assert sniff.verify("image/jpeg", head) == sniff.Verification(None, "disallowed_type", None)


def test_declared_type_of_another_format_is_a_mismatch() -> None:
    result = sniff.verify("image/png", b"\xff\xd8\xff\xe0")
    assert (result.verified_type, result.reason, result.detected) == (None, "type_mismatch", "jpeg")
    assert sniff.verify("audio/ogg", b"\x00\x00\x00\x20ftypisom").reason == "type_mismatch"
    assert sniff.verify(None, b"\xff\xd8\xff\xe0").reason == "type_mismatch"
