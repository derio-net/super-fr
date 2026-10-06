"""The GitHub adapter honours a host (spec 2026-10-06-forge-remainder §4.E,
Test Plan 3 and 4).

`RealGhClient(host=...)` runs every `gh` it spawns with `GH_HOST` set to that
host, through both of `fr.gh`'s subprocess paths (`_run_gh` and
`view_pr_body`); with no host, and for a bare `fr.gh` call made afterwards,
`env` stays `None` so the SaaS path is byte-for-byte what it was.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr import gh as _gh
from fr.real_ghclient import RealGhClient

_ISSUE_JSON = json.dumps({"state": "OPEN", "labels": [], "assignees": [], "body": ""})


class _Recorder:
    """A `subprocess.run` stand-in that records the `env` of every call."""

    def __init__(self, *, fail: bool = False) -> None:
        self.envs: list[dict[str, str] | None] = []
        self.fail = fail

    def __call__(self, argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.envs.append(kwargs.get("env"))
        if self.fail:
            raise subprocess.CalledProcessError(1, argv, output="", stderr="boom")
        out = "[]" if argv[1:3] == ["issue", "list"] else _ISSUE_JSON
        if argv[1:3] == ["pr", "view"]:
            out = "the body"
        return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    rec = _Recorder()
    monkeypatch.setattr(_gh.subprocess, "run", rec)
    return rec


def test_a_hosted_client_sets_gh_host_on_a_run_gh_path(recorder: _Recorder) -> None:
    RealGhClient(host="ghe.example").view_issue("o/r", 1)
    env = recorder.envs[-1]
    assert env is not None
    assert env["GH_HOST"] == "ghe.example"
    assert "PATH" in env  # a copy of os.environ, not a bare one-key env


def test_a_hosted_client_sets_gh_host_on_the_view_pr_body_path(
    recorder: _Recorder, tmp_path: Path
) -> None:
    assert RealGhClient(host="ghe.example").pr_body("3", cwd=tmp_path) == "the body"
    env = recorder.envs[-1]
    assert env is not None
    assert env["GH_HOST"] == "ghe.example"


def test_an_unhosted_client_passes_env_none_on_both_paths(
    recorder: _Recorder, tmp_path: Path
) -> None:
    client = RealGhClient()
    client.view_issue("o/r", 1)
    client.pr_body("3", cwd=tmp_path)
    assert recorder.envs == [None, None]


def test_the_host_does_not_leak_into_a_later_bare_call(recorder: _Recorder) -> None:
    RealGhClient(host="ghe.example").view_issue("o/r", 1)
    _gh.list_issues(repo="o/r", state="open", limit=5)
    assert recorder.envs[-1] is None


def test_the_host_does_not_leak_after_a_hosted_call_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failing = _Recorder(fail=True)
    monkeypatch.setattr(_gh.subprocess, "run", failing)
    with pytest.raises(_gh.GhError):
        RealGhClient(host="ghe.example").view_issue("o/r", 1)
    assert failing.envs[-1] is not None

    ok = _Recorder()
    monkeypatch.setattr(_gh.subprocess, "run", ok)
    _gh.list_issues(repo="o/r", state="open", limit=5)
    assert ok.envs == [None]


def test_every_gh_method_is_hosted() -> None:
    """A `RealGhClient` method that reaches `fr.gh` without `@_hosted` would
    silently run against gh's own host — the defect §4.E exists to close."""
    import inspect

    unhosted = [
        name
        for name, fn in vars(RealGhClient).items()
        if inspect.isfunction(fn)
        and not name.startswith("__")
        and "_gh." in inspect.getsource(fn)
        and not getattr(fn, "__fr_hosted__", False)
    ]
    assert unhosted == []
