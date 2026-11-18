"""Reading an artifact's bytes as text, refusing by name when they are not UTF-8.

A spec or matrix that is not valid UTF-8 used to fail every migration read with
Python's codec message (`UnicodeDecodeError: 'utf-8' codec can't decode byte ...`),
which names neither the file nor the fix (super-fr#1390, spec
`2026-11-17-batch-acceptance-edits` R5-R7). Such a file still refuses: fr cannot
know what it holds, and unknown state is not current. It refuses with one plain
reason, `<path> is not UTF-8 text (byte 0x<hh> at offset <n>)`, which the runner's
`describe` prints alone.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["NotUtf8Error", "decode_utf8", "read_utf8"]


class NotUtf8Error(UnicodeDecodeError):
    """An artifact's bytes are not valid UTF-8. Its text is the whole reason.

    A `UnicodeDecodeError` subclass, not a bare `ValueError`: readers all over fr
    already catch `UnicodeDecodeError` around reads that now decode here (`fr validate
    artifacts`' stamp and structure reads among them), and each keeps catching it. Only
    the text changes, from the codec's message to one naming the file."""

    def __init__(self, path: Path | str, error: UnicodeDecodeError) -> None:
        super().__init__(error.encoding, error.object, error.start, error.end, error.reason)
        self.path = str(path)

    def __str__(self) -> str:
        return (
            f"{self.path} is not UTF-8 text "
            f"(byte 0x{self.object[self.start]:02x} at offset {self.start})"
        )


def decode_utf8(data: bytes, path: Path | str) -> str:
    """*data* decoded as UTF-8, or `NotUtf8Error` naming *path* and the first bad byte."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise NotUtf8Error(path, e) from None


def read_utf8(path: Path, *, translate_newlines: bool = False) -> str:
    """*path*'s text through `decode_utf8`.

    With no translation (the default) a CRLF file stays CRLF, as a writer that
    puts the text back needs. `translate_newlines=True` reads as `Path.read_text()`
    does (universal newlines), for a reader that replaced one.
    """
    text = decode_utf8(path.read_bytes(), path)
    if translate_newlines:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text
