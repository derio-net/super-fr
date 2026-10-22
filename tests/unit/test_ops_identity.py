"""Live identity references (spec 2026-10-22-fr-ops R5): read at check time,
never echoed — a failing reference is named, its output is not."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.ops.identity import IdentityError, LiveIdentities
from fr.ops.load import OpsConfig


def _config(cmd: str) -> OpsConfig:
    return OpsConfig.model_validate({"identities": {"admin": {"env": {"TOKEN": {"from": cmd}}}}})


def test_a_reference_is_read_live(tmp_path: Path) -> None:
    assert LiveIdentities(_config("echo tok-123"), tmp_path)("admin") == {"TOKEN": "tok-123"}


def test_an_unreadable_reference_names_the_identity_not_its_output(tmp_path: Path) -> None:
    resolve = LiveIdentities(_config("echo leaked-secret; exit 3"), tmp_path)
    with pytest.raises(IdentityError) as exc:
        resolve("admin")
    assert "admin" in str(exc.value) and "TOKEN" in str(exc.value)
    assert "leaked-secret" not in str(exc.value)


def test_an_unknown_identity_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(IdentityError, match="ghost"):
        LiveIdentities(_config("echo x"), tmp_path)("ghost")


def test_an_empty_value_is_unreadable(tmp_path: Path) -> None:
    with pytest.raises(IdentityError):
        LiveIdentities(_config("true"), tmp_path)("admin")


def test_a_reference_runs_with_the_minimal_env_and_no_stdin(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FR_TEST_LEAK", "leaked")
    resolve = LiveIdentities(_config('cat; echo "${FR_TEST_LEAK:-unset}"'), tmp_path)
    assert resolve("admin") == {"TOKEN": "unset"}


def test_a_reference_that_hangs_times_out(tmp_path: Path) -> None:
    resolve = LiveIdentities(_config("sleep 5; echo x"), tmp_path, timeout=1)
    with pytest.raises(IdentityError, match="timed out"):
        resolve("admin")


def test_resolution_is_memoised_per_invocation(tmp_path: Path) -> None:
    """p1-r8: two ops run as one identity read its references once."""
    counter = tmp_path / "count"
    resolve = LiveIdentities(_config(f"echo x >> {counter}; echo tok"), tmp_path)
    assert resolve("admin") == resolve("admin") == {"TOKEN": "tok"}
    assert counter.read_text().count("x") == 1
