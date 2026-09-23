"""scripts/check-pinned-clis.py — the scheduled check that pinned assets still match (gh#576)."""

from __future__ import annotations

import hashlib
import importlib.util
from collections.abc import Callable, Iterator
from pathlib import Path
from types import MappingProxyType, ModuleType

import pytest
from fr.isolation.scaffold import HostCliPin

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check-pinned-clis.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_pinned_clis", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _chunked(bodies: dict[str, bytes]) -> Callable[[str], Iterator[bytes]]:
    """A fetch that streams each body in 3-byte chunks, like the real one does."""

    def fetch(url: str) -> Iterator[bytes]:
        body = bodies[url]
        for i in range(0, len(body), 3):
            yield body[i : i + 3]

    return fetch


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


BODIES = {
    "https://example.test/a-amd64": b"a-amd64",
    "https://example.test/a-arm64": b"a-arm64",
    "https://example.test/b-amd64": b"b-amd64",
}

PINS = {
    "one": HostCliPin(
        name="aa",
        version="1.0",
        assets=MappingProxyType(
            {
                "amd64": ("https://example.test/a-amd64", _sha(b"a-amd64")),
                "arm64": ("https://example.test/a-arm64", _sha(b"a-arm64")),
            }
        ),
        kind="tarball",
        tarball_member="bin/aa",
    ),
    "two": HostCliPin(
        name="bb",
        version="2.0",
        assets=MappingProxyType({"amd64": ("https://example.test/b-amd64", _sha(b"b-amd64"))}),
        kind="binary",
    ),
}


def test_all_matching_returns_zero_and_reports_each_asset(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = _load().check(PINS, _chunked(BODIES))
    out = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert "OK aa 1.0 amd64" in out
    assert "OK aa 1.0 arm64" in out
    assert "OK bb 2.0 amd64" in out
    assert len([line for line in out if line.startswith("OK ")]) == 3


def test_a_mismatch_returns_one_and_names_both_sums(capsys: pytest.CaptureFixture[str]) -> None:
    bodies = {**BODIES, "https://example.test/a-arm64": b"tampered"}
    rc = _load().check(PINS, _chunked(bodies))
    out = capsys.readouterr().out
    assert rc == 1
    assert f"MISMATCH aa 1.0 arm64 expected {_sha(b'a-arm64')} got {_sha(b'tampered')}" in out
    assert "OK bb 2.0 amd64" in out  # one bad asset does not hide the rest


def test_a_fetch_failure_returns_one(capsys: pytest.CaptureFixture[str]) -> None:
    def fetch(url: str) -> Iterator[bytes]:
        if url.endswith("b-amd64"):
            raise OSError("HTTP Error 404: Not Found")
        return _chunked(BODIES)(url)

    rc = _load().check(PINS, fetch)
    out = capsys.readouterr().out
    assert rc == 1
    assert "FETCH-FAILED bb 2.0 amd64" in out
    assert "404" in out
    assert "OK aa 1.0 amd64" in out


def test_the_default_pins_are_the_shipped_ones() -> None:
    from fr.isolation.scaffold import HOST_CLI_PINS

    assert _load().HOST_CLI_PINS is HOST_CLI_PINS


def test_a_failure_mid_stream_is_a_fetch_failure(capsys: pytest.CaptureFixture[str]) -> None:
    def fetch(url: str) -> Iterator[bytes]:
        yield b"a-"
        raise OSError("connection reset")

    rc = _load().check(PINS, fetch)
    out = capsys.readouterr().out
    assert rc == 1
    assert "FETCH-FAILED aa 1.0 amd64" in out and "connection reset" in out


def test_the_default_fetch_reads_in_bounded_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real fetch never asks for the whole asset in one read (p5r-f5)."""
    mod = _load()
    sizes: list[int] = []
    data = iter([b"x" * 10, b"y" * 5, b""])

    class Resp:
        def __enter__(self) -> Resp:
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def read(self, n: int = -1) -> bytes:
            sizes.append(n)
            return next(data)

    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda url, timeout: Resp())
    assert b"".join(mod.fetch_url("https://example.test/x")) == b"x" * 10 + b"y" * 5
    assert sizes and all(0 < n <= mod.CHUNK_BYTES for n in sizes)
