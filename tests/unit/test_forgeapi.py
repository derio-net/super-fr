"""`forge.api` selection (spec 2026-10-07-cloud-triage §A, R3; Test Plan 3)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr import forgeapi
from fr.forgeapi import ForgeApiError


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv(forgeapi.ENV, raising=False)

    def _no_subprocess(*_a: object, **_k: object) -> None:
        raise AssertionError("forge.api resolution must spawn no process")

    monkeypatch.setattr(subprocess, "run", _no_subprocess)
    monkeypatch.setattr(subprocess, "Popen", _no_subprocess)
    return tmp_path


def _write(home: Path, text: str) -> Path:
    path = home / ".config" / "fr" / "forge.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_config_path_sits_beside_the_host_id(_home: Path) -> None:
    from fr.triage.scope_config import host_id_path

    assert forgeapi.config_path() == _home / ".config" / "fr" / "forge.yaml"
    assert forgeapi.config_path().parent == host_id_path().parent


def test_nothing_set_resolves_graphql() -> None:
    assert forgeapi.resolve() == "graphql"


def test_env_var_selects_rest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(forgeapi.ENV, "rest")
    assert forgeapi.resolve() == "rest"


def test_host_file_alone_selects_rest(_home: Path) -> None:
    # A fresh shell with only the file set: no env var exported anywhere.
    _write(_home, "api: rest\n")
    assert forgeapi.resolve() == "rest"


def test_env_var_wins_over_the_file(_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(_home, "api: rest\n")
    monkeypatch.setenv(forgeapi.ENV, "graphql")
    assert forgeapi.resolve() == "graphql"


def test_invalid_env_value_names_the_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(forgeapi.ENV, "soap")
    with pytest.raises(ForgeApiError, match=forgeapi.ENV):
        forgeapi.resolve()


@pytest.mark.parametrize("text", ["api: soap\n", "- not a mapping\n", "api: [rest\n"])
def test_invalid_file_names_the_file(_home: Path, text: str) -> None:
    path = _write(_home, text)
    with pytest.raises(ForgeApiError, match=str(path)):
        forgeapi.resolve()


def test_a_file_without_the_key_resolves_graphql(_home: Path) -> None:
    _write(_home, "{}\n")
    assert forgeapi.resolve() == "graphql"


def test_write_default_writes_only_when_absent(_home: Path) -> None:
    assert forgeapi.write_default("rest") is True
    assert forgeapi.resolve() == "rest"
    assert forgeapi.write_default("graphql") is False
    assert forgeapi.resolve() == "rest"


def test_write_default_never_overwrites_an_existing_file(_home: Path) -> None:
    path = _write(_home, "api: graphql\n")
    assert forgeapi.write_default("rest") is False
    assert path.read_text() == "api: graphql\n"


def test_write_default_refuses_an_invalid_value() -> None:
    with pytest.raises(ForgeApiError):
        forgeapi.write_default("soap")  # type: ignore[arg-type]
