"""How a probe runs (spec 2026-10-22-fr-ops R5, p1-r5/p1-r6): a minimal env, stdin
closed, a bounded timeout. These run real `bash`."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fr.ops.engine import TIMED_OUT, ShellRunner, status
from fr.ops.load import LoadedOp, OpsConfig
from fr.ops.model import Op

from tests.unit.test_ops_engine import FakeIdentities, FakeJournal


def test_a_probe_gets_only_the_minimal_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FR_TEST_LEAK", "leaked")
    monkeypatch.setenv("HOME", "/home/someone")
    run = ShellRunner(tmp_path)
    assert run('echo "${FR_TEST_LEAK:-unset}"', {}) == (0, "unset")
    assert run('echo "$HOME"', {}) == (0, "/home/someone")
    assert run("command -v bash >/dev/null && echo found", {}) == (0, "found")


def test_env_passthrough_names_extra_variables(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FR_TEST_PASS", "through")
    run = ShellRunner(tmp_path, passthrough=("FR_TEST_PASS",))
    assert run('echo "$FR_TEST_PASS"', {}) == (0, "through")


def test_the_identity_env_is_added(tmp_path: Path) -> None:
    assert ShellRunner(tmp_path)('echo "$TOKEN"', {"TOKEN": "t"}) == (0, "t")


def test_stdin_is_closed(tmp_path: Path) -> None:
    start = time.monotonic()
    assert ShellRunner(tmp_path, timeout=5)("cat; echo eof", {}) == (0, "eof")
    assert time.monotonic() - start < 4


def test_a_probe_that_hangs_times_out(tmp_path: Path) -> None:
    rc, line = ShellRunner(tmp_path, timeout=1)("sleep 5", {})
    assert rc == TIMED_OUT and "timed out" in line


def test_a_timed_out_check_is_cannot_verify(tmp_path: Path) -> None:
    lo = LoadedOp(Op(id="a", summary="s", phase="pre-merge", check="sleep 5"), tmp_path, 1)
    (row,) = status(
        [lo],
        runner=ShellRunner(tmp_path, timeout=1),
        identities=FakeIdentities({}),
        journal=FakeJournal(),
    )
    assert row.state == "CANNOT-VERIFY" and "timed out" in (row.reason or "")


def test_ops_config_reads_passthrough_and_timeout() -> None:
    config = OpsConfig.model_validate({"env_passthrough": ["KUBECONFIG"], "timeout_seconds": 5})
    assert config.env_passthrough == ("KUBECONFIG",) and config.timeout_seconds == 5
    assert OpsConfig().timeout_seconds == 60
    with pytest.raises(ValueError):
        OpsConfig.model_validate({"timeout_seconds": 0})
