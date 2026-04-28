"""Tests for `vk execute pr-opened`."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from vk import gh
from vk.commands.execute_cmd import execute_app

runner = CliRunner()


def _stub_run_gh(monkeypatch: pytest.MonkeyPatch, responses: list) -> list[list[str]]:
    calls: list[list[str]] = []
    it = iter(responses)

    def fake(args: list[str]) -> str:
        calls.append(args)
        r = next(it)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(gh, "_run_gh", fake)
    return calls


def _labels_json(*names: str) -> str:
    return json.dumps({"labels": [{"name": n} for n in names]})


class TestPrOpenedHappyPath:
    def test_in_progress_to_pr_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = _stub_run_gh(
            monkeypatch,
            [
                _labels_json("in-progress", "plan:foo", "phase:1"),  # view
                "",  # ensure pr-ready
                "",  # swap edit
            ],
        )
        result = runner.invoke(
            execute_app,
            [
                "pr-opened",
                "--issue",
                "8",
                "--repo",
                "o/r",
                "--pr-url",
                "https://github.com/o/r/pull/14",
            ],
        )
        assert result.exit_code == 0, result.output
        last = calls[-1]
        assert "--add-label" in last and "pr-ready" in last
        assert "--remove-label" in last and "in-progress" in last


class TestPrOpenedSkippedClaim:
    def test_vk_ready_directly_to_pr_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cover the case where claim was never run — Issue still on
        vk-ready when PR opens. vk-ready gets removed; pr-ready is added."""
        calls = _stub_run_gh(
            monkeypatch,
            [
                _labels_json("vk-ready", "plan:foo"),  # view
                "",  # ensure
                "",  # swap
            ],
        )
        result = runner.invoke(
            execute_app,
            ["pr-opened", "--issue", "8", "--repo", "o/r"],
        )
        assert result.exit_code == 0, result.output
        last = calls[-1]
        assert "--remove-label" in last and "vk-ready" in last


class TestPrOpenedAlreadyPrReady:
    def test_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = _stub_run_gh(
            monkeypatch,
            [
                _labels_json("pr-ready", "plan:foo"),
            ],
        )
        result = runner.invoke(
            execute_app,
            ["pr-opened", "--issue", "8", "--repo", "o/r"],
        )
        assert result.exit_code == 0, result.output
        assert "already pr-ready" in result.output.lower()
        assert len(calls) == 1


class TestPrOpenedHardFailPrintsPrUrl:
    def test_403_includes_pr_url_and_remediation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gh.time, "sleep", lambda s: None)
        _stub_run_gh(
            monkeypatch,
            [
                _labels_json("in-progress"),
                "",
                gh.GhError("forbidden", stderr="HTTP 403", returncode=1),
            ],
        )
        result = runner.invoke(
            execute_app,
            [
                "pr-opened",
                "--issue",
                "8",
                "--repo",
                "o/r",
                "--pr-url",
                "https://github.com/o/r/pull/14",
            ],
        )
        assert result.exit_code != 0
        assert "https://github.com/o/r/pull/14" in result.output
        assert "gh issue edit 8" in result.output


class TestPrOpenedNetworkRetry:
    def test_retries_then_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gh.time, "sleep", lambda s: None)
        _stub_run_gh(
            monkeypatch,
            [
                _labels_json("in-progress"),
                "",
                gh.GhError("x", stderr="HTTP 503", returncode=1),
                "",
            ],
        )
        result = runner.invoke(
            execute_app,
            ["pr-opened", "--issue", "8", "--repo", "o/r"],
        )
        assert result.exit_code == 0, result.output
