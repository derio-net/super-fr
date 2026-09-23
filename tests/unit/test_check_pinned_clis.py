"""scripts/check-pinned-clis.py — the scheduled check that pinned assets still match (gh#576)."""

from __future__ import annotations

import hashlib
import importlib.util
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
    rc = _load().check(PINS, BODIES.__getitem__)
    out = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert "OK aa 1.0 amd64" in out
    assert "OK aa 1.0 arm64" in out
    assert "OK bb 2.0 amd64" in out
    assert len([line for line in out if line.startswith("OK ")]) == 3


def test_a_mismatch_returns_one_and_names_both_sums(capsys: pytest.CaptureFixture[str]) -> None:
    bodies = {**BODIES, "https://example.test/a-arm64": b"tampered"}
    rc = _load().check(PINS, bodies.__getitem__)
    out = capsys.readouterr().out
    assert rc == 1
    assert f"MISMATCH aa 1.0 arm64 expected {_sha(b'a-arm64')} got {_sha(b'tampered')}" in out
    assert "OK bb 2.0 amd64" in out  # one bad asset does not hide the rest


def test_a_fetch_failure_returns_one(capsys: pytest.CaptureFixture[str]) -> None:
    def fetch(url: str) -> bytes:
        if url.endswith("b-amd64"):
            raise OSError("HTTP Error 404: Not Found")
        return BODIES[url]

    rc = _load().check(PINS, fetch)
    out = capsys.readouterr().out
    assert rc == 1
    assert "FETCH-FAILED bb 2.0 amd64" in out
    assert "404" in out
    assert "OK aa 1.0 amd64" in out


def test_the_default_pins_are_the_shipped_ones() -> None:
    from fr.isolation.scaffold import HOST_CLI_PINS

    assert _load().HOST_CLI_PINS is HOST_CLI_PINS
