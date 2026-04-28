"""Tests for `vk execute claim`."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from vk import gh, labels
from vk.commands.execute_cmd import execute_app

runner = CliRunner()


def _stub_run_gh(monkeypatch: pytest.MonkeyPatch, responses: list) -> list[list[str]]:
    """Configure gh._run_gh to return / raise the given responses in order.

    Each response is either a string (stdout) or an exception to raise.
    Captures the args of every call into the returned list.
    """
    calls: list[list[str]] = []
    iterator = iter(responses)

    def fake(args: list[str]) -> str:
        calls.append(args)
        r = next(iterator)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(gh, "_run_gh", fake)
    return calls


def _labels_json(*names: str) -> str:
    return json.dumps({"labels": [{"name": n} for n in names]})


class TestClaimColdStart:
    def test_flips_vk_ready_to_in_progress(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = _stub_run_gh(
            monkeypatch,
            [
                _labels_json("vk-ready", "plan:foo", "phase:1"),  # gh issue view
                "",  # gh label create --force (ensure in-progress)
                "",  # gh issue edit --add-label in-progress --remove-label vk-ready
            ],
        )
        result = runner.invoke(
            execute_app,
            ["claim", "--issue", "8", "--repo", "o/r"],
        )
        assert result.exit_code == 0, result.output
        last = calls[-1]
        assert "issue" in last and "edit" in last
        assert "--add-label" in last and "in-progress" in last
        assert "--remove-label" in last and "vk-ready" in last


class TestClaimIdempotent:
    def test_already_in_progress_is_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = _stub_run_gh(
            monkeypatch,
            [
                _labels_json("in-progress", "plan:foo", "phase:1"),
            ],
        )
        result = runner.invoke(
            execute_app,
            ["claim", "--issue", "8", "--repo", "o/r"],
        )
        assert result.exit_code == 0, result.output
        assert "already in-progress" in result.output.lower()
        assert len(calls) == 1  # only the view call, no edits


class TestClaimSelfHeal:
    def test_creates_in_progress_label_if_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = _stub_run_gh(
            monkeypatch,
            [
                _labels_json("vk-ready"),  # view
                "",  # ensure_label create
                "",  # swap edit
            ],
        )
        result = runner.invoke(
            execute_app,
            ["claim", "--issue", "8", "--repo", "o/r"],
        )
        assert result.exit_code == 0, result.output
        assert calls[1][:3] == ["label", "create", labels.IN_PROGRESS.name]
        assert "--force" in calls[1]
        assert "--color" in calls[1]


class TestClaimManualHardFail:
    def test_manual_label_present_aborts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_run_gh(
            monkeypatch,
            [
                _labels_json("manual", "plan:foo", "phase:1"),
            ],
        )
        result = runner.invoke(
            execute_app,
            ["claim", "--issue", "8", "--repo", "o/r"],
        )
        assert result.exit_code != 0
        assert "manual" in result.output.lower()


class TestClaimNetworkRetry:
    def test_retries_on_5xx_then_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gh.time, "sleep", lambda s: None)
        _stub_run_gh(
            monkeypatch,
            [
                _labels_json("vk-ready"),  # view
                "",  # ensure_label
                gh.GhError("x", stderr="HTTP 503", returncode=1),  # edit fail 1
                gh.GhError("x", stderr="HTTP 503", returncode=1),  # edit fail 2
                "",  # edit success
            ],
        )
        result = runner.invoke(
            execute_app,
            ["claim", "--issue", "8", "--repo", "o/r"],
        )
        assert result.exit_code == 0, result.output


class TestClaimHardFailOn403:
    def test_403_no_retry_exits_nonzero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gh.time, "sleep", lambda s: None)
        _stub_run_gh(
            monkeypatch,
            [
                _labels_json("vk-ready"),
                "",  # ensure_label
                gh.GhError("forbidden", stderr="HTTP 403", returncode=1),
            ],
        )
        result = runner.invoke(
            execute_app,
            ["claim", "--issue", "8", "--repo", "o/r"],
        )
        assert result.exit_code != 0
        out = result.output.lower()
        assert "403" in result.output or "forbidden" in out


class TestClaimHardFailRemediation:
    def test_prints_remediation_command_on_hard_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A hard-fail must print a copy-paste gh issue edit command so the
        operator can recover without manually hunting for Issue state."""
        monkeypatch.setattr(gh.time, "sleep", lambda s: None)
        _stub_run_gh(
            monkeypatch,
            [
                _labels_json("vk-ready"),
                "",  # ensure_label
                gh.GhError("forbidden", stderr="HTTP 403", returncode=1),
            ],
        )
        result = runner.invoke(
            execute_app,
            ["claim", "--issue", "42", "--repo", "owner/myrepo"],
        )
        assert result.exit_code != 0
        assert "gh issue edit 42" in result.output
        assert "owner/myrepo" in result.output
        assert "--add-label" in result.output
        assert labels.IN_PROGRESS.name in result.output
