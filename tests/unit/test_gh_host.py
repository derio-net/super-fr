"""The GitHub adapter honours a host (spec 2026-10-06-forge-remainder §4.E,
Test Plan 3 and 4).

`RealGhClient(host=...)` runs every `gh` it spawns with `GH_HOST` set to that
host, through both of `fr.gh`'s subprocess paths (`_run_gh` and
`view_pr_body`); with no host, and for a bare `fr.gh` call made afterwards,
`env` stays `None` so the SaaS path is byte-for-byte what it was.

The trust gate (plan journal `p1-gh-host-trust-gate`): `GH_HOST` makes gh send
`GH_ENTERPRISE_TOKEN` to that host, and the hosts fr threads come from URLs
and a cloned repo's committed config. So only a host gh is logged into (a key
of gh's own `hosts.yml`) is ever threaded; any other fails closed, before a
subprocess starts, and never falls back to github.com.
"""

from __future__ import annotations

import json
import re
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


@pytest.fixture(autouse=True)
def gh_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """gh's config dir, logged into `ghe.example` (and github.com) only."""
    d = tmp_path / "gh-config"
    d.mkdir()
    (d / "hosts.yml").write_text(
        "github.com:\n    user: someone\nghe.example:\n    user: someone\n"
    )
    monkeypatch.setenv("GH_CONFIG_DIR", str(d))
    return d


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
        and re.search(r"\b_gh\.|\bfrom fr\.gh import|\bfrom fr import gh\b", inspect.getsource(fn))
        and not getattr(fn, "__fr_hosted__", False)
    ]
    assert unhosted == []


_REFUSAL = (
    "GitHub host 'evil.example' is not one gh is logged into; run "
    "`gh auth login --hostname evil.example` (fr will not point gh, or its "
    "tokens, at an unknown host; a GH_ENTERPRISE_TOKEN alone does not "
    "count as a login)"
)


def test_an_unknown_host_fails_closed_on_the_run_gh_path(recorder: _Recorder) -> None:
    with pytest.raises(_gh.GhError) as exc:
        RealGhClient(host="evil.example").view_issue("o/r", 1)
    assert str(exc.value) == _REFUSAL
    assert recorder.envs == []  # no subprocess started


def test_an_unknown_host_fails_closed_on_the_view_pr_body_path(
    recorder: _Recorder, tmp_path: Path
) -> None:
    with pytest.raises(_gh.GhError, match="evil.example"):
        RealGhClient(host="evil.example").pr_body("3", cwd=tmp_path)
    assert recorder.envs == []


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("list_linked_prs", ("o/r", 1)),
        ("pr_status_by_url", ("https://evil.example/o/r/pull/1",)),
        ("file_exists", ("o/r", "x")),
        ("list_dir", ("o/r", "x")),
        ("issues_enabled", ("o/r",)),
    ],
)
def test_a_soft_fail_method_never_swallows_the_refusal(
    recorder: _Recorder, method: str, args: tuple[Any, ...]
) -> None:
    """Review p1-r1: these methods turn a `GhError` into "no PR" / "no file" /
    "unknown". A refused host must not read as a forge answer, and must start
    no subprocess (no silent github.com target, #892's wrong-target write)."""
    with pytest.raises(_gh.GhHostRefused) as exc:
        getattr(RealGhClient(host="evil.example"), method)(*args)
    assert str(exc.value) == _REFUSAL
    assert recorder.envs == []


def test_a_nested_host_scope_restores_the_outer_host(recorder: _Recorder) -> None:
    """Review p1-r3: `host_scope` restores the PREVIOUS value, not None."""
    with _gh.host_scope("ghe.example"):
        with _gh.host_scope(None):
            _gh.list_issues(repo="o/r", state="open", limit=1)
        _gh.list_issues(repo="o/r", state="open", limit=1)
    _gh.list_issues(repo="o/r", state="open", limit=1)
    assert recorder.envs[0] is None
    assert recorder.envs[1] is not None and recorder.envs[1]["GH_HOST"] == "ghe.example"
    assert recorder.envs[2] is None


def test_building_a_client_touches_no_filesystem(
    monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
) -> None:
    def boom() -> frozenset[str]:
        raise AssertionError("known_hosts read at construction")

    monkeypatch.setattr(_gh, "known_hosts", boom)
    RealGhClient(host="evil.example")
    RealGhClient()


def test_no_host_needs_no_login(
    monkeypatch: pytest.MonkeyPatch, recorder: _Recorder, tmp_path: Path
) -> None:
    monkeypatch.setenv("GH_CONFIG_DIR", str(tmp_path / "nowhere"))
    RealGhClient().view_issue("o/r", 1)
    assert recorder.envs == [None]


class TestKnownHosts:
    def test_reads_the_keys_of_gh_config_dir_hosts_yml(self) -> None:
        assert _gh.known_hosts() == frozenset({"github.com", "ghe.example"})

    def test_falls_back_to_xdg_config_home(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("GH_CONFIG_DIR")
        (tmp_path / "xdg" / "gh").mkdir(parents=True)
        (tmp_path / "xdg" / "gh" / "hosts.yml").write_text("ghe.xdg.example: {}\n")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        assert _gh.known_hosts() == frozenset({"ghe.xdg.example"})

    def test_falls_back_to_home_dot_config(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("GH_CONFIG_DIR")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        (tmp_path / ".config" / "gh").mkdir(parents=True)
        (tmp_path / ".config" / "gh" / "hosts.yml").write_text("ghe.home.example: {}\n")
        assert _gh.known_hosts() == frozenset({"ghe.home.example"})

    @pytest.mark.parametrize("body", [None, "", "- a list\n", "{unclosed: [\n"])
    def test_a_missing_or_unreadable_file_is_the_empty_set(
        self, gh_config: Path, body: str | None
    ) -> None:
        hosts = gh_config / "hosts.yml"
        if body is None:
            hosts.unlink()
        else:
            hosts.write_text(body)
        assert _gh.known_hosts() == frozenset()
