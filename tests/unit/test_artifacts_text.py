"""`fr.artifacts.text`: an undecodable artifact is refused by name, and every reader that
already handled a decode error keeps handling it (spec 2026-11-17-batch-acceptance-edits
R5-R7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.artifacts.text import NotUtf8Error, decode_utf8, read_utf8


def test_the_reason_names_the_file_the_byte_and_its_offset() -> None:
    with pytest.raises(NotUtf8Error) as info:
        decode_utf8(b"ok\n\xff", "docs/x.md")
    assert str(info.value) == "docs/x.md is not UTF-8 text (byte 0xff at offset 3)"
    assert "codec" not in str(info.value)


def test_it_is_still_a_unicode_decode_error_for_every_existing_handler(tmp_path: Path) -> None:
    """Readers across fr catch `UnicodeDecodeError` around a read that now decodes
    here (`fr validate artifacts` among them); the named error must not escape them."""
    bad = tmp_path / "f.yaml"
    bad.write_bytes(b"a: \xfe\n")
    with pytest.raises(UnicodeDecodeError) as info:
        read_utf8(bad)
    assert isinstance(info.value, NotUtf8Error)
    assert str(info.value) == f"{bad} is not UTF-8 text (byte 0xfe at offset 3)"
