"""The isolation lookups on every forge adapter (spec 2026-10-06-forge-remainder
§4.B, R2; Test Plan 6).

`default_branch` and `pr_for_branch` moved verbatim out of
`fr/isolation/local.py`: the argv each sends through the injected runner is
exactly what local.py sent, the PR record keeps its normalised
`{state: OPEN|MERGED|CLOSED, url, mergedAt}` shape, and every failure — a
non-zero exit, unparseable output, a missing binary — reads as `None`.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.ghclient import GhClient
from fr.real_ghclient import RealGhClient
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient


class _Scripted:
    """A `CommandRunner` that records each argv and answers with one result."""

    def __init__(self, rc: int = 0, out: str = "") -> None:
        self.rc = rc
        self.out = out
        self.calls: list[tuple[list[str], Path]] = []

    def __call__(self, argv: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(argv), cwd))
        return subprocess.CompletedProcess(argv, self.rc, stdout=self.out, stderr="")


_CLIENTS: dict[str, Any] = {
    "github": RealGhClient,
    "gitlab": RealGlabClient,
    "gitea": RealTeaClient,
}

_DEFAULT_BRANCH_ARGV = {
    "github": [
        "gh",
        "repo",
        "view",
        "--json",
        "defaultBranchRef",
        "--jq",
        ".defaultBranchRef.name",
    ],
    "gitlab": ["glab", "repo", "view", "-F", "json", "--jq", ".default_branch"],
    "gitea": ["tea", "repos", "--fields", "default_branch", "--output", "json"],
}

_DEFAULT_BRANCH_OUT = {
    "github": "trunk\n",
    "gitlab": "trunk\n",
    "gitea": json.dumps({"default_branch": "trunk"}),
}

_PR_ARGV = {
    "github": ["gh", "pr", "view", "feat/x", "--json", "state,url,mergedAt"],
    "gitlab": ["glab", "mr", "view", "feat/x", "--output", "json"],
    "gitea": [
        "tea", "pulls", "list", "--state", "all",
        "--fields", "state,merged,url,head", "--output", "json",
    ],
}  # fmt: skip


def _pr_out(backend: str, native_state: str) -> str:
    """One forge-native PR record for branch `feat/x` in *native_state*."""
    if backend == "github":
        merged_at = "2026-10-01T00:00:00Z" if native_state == "MERGED" else None
        return json.dumps({"state": native_state, "url": "u", "mergedAt": merged_at})
    if backend == "gitlab":
        merged_at = "2026-10-01T00:00:00Z" if native_state == "merged" else None
        return json.dumps({"state": native_state, "web_url": "u", "merged_at": merged_at})
    merged: Any = "2026-10-01T00:00:00Z" if native_state == "merged" else False
    state = "closed" if native_state in ("closed", "merged") else "open"
    return json.dumps(
        [
            {"state": "open", "merged": False, "url": "other", "head": {"label": "feat/y"}},
            {"state": state, "merged": merged, "url": "u", "head": {"label": "feat/x"}},
        ]
    )


_NATIVE = {
    "github": {"OPEN": "OPEN", "MERGED": "MERGED", "CLOSED": "CLOSED"},
    "gitlab": {"OPEN": "opened", "MERGED": "merged", "CLOSED": "closed"},
    "gitea": {"OPEN": "open", "MERGED": "merged", "CLOSED": "closed"},
}

BACKENDS = sorted(_CLIENTS)


def _client(backend: str) -> GhClient:
    client: GhClient = _CLIENTS[backend]()
    return client


@pytest.mark.parametrize("backend", BACKENDS)
def test_default_branch_sends_todays_argv_and_reads_the_bare_name(
    backend: str, tmp_path: Path
) -> None:
    run = _Scripted(out=_DEFAULT_BRANCH_OUT[backend])
    assert _client(backend).default_branch(cwd=tmp_path, run=run) == "trunk"
    assert run.calls == [(_DEFAULT_BRANCH_ARGV[backend], tmp_path)]


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize(("rc", "out"), [(1, "trunk"), (124, ""), (0, ""), (0, "  \n")])
def test_default_branch_is_none_on_a_failed_or_empty_answer(
    backend: str, rc: int, out: str, tmp_path: Path
) -> None:
    assert _client(backend).default_branch(cwd=tmp_path, run=_Scripted(rc, out)) is None


@pytest.mark.parametrize("out", ["not json", json.dumps(["trunk"]), json.dumps({"x": 1})])
def test_gitea_default_branch_is_none_on_unparseable_output(out: str, tmp_path: Path) -> None:
    assert RealTeaClient().default_branch(cwd=tmp_path, run=_Scripted(0, out)) is None


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("state", ["OPEN", "MERGED", "CLOSED"])
def test_pr_for_branch_sends_todays_argv_and_normalises_the_record(
    backend: str, state: str, tmp_path: Path
) -> None:
    run = _Scripted(out=_pr_out(backend, _NATIVE[backend][state]))
    pr = _client(backend).pr_for_branch("feat/x", cwd=tmp_path, run=run)
    merged_at = "2026-10-01T00:00:00Z" if state == "MERGED" else None
    assert pr == {"state": state, "url": "u", "mergedAt": merged_at}
    assert run.calls == [(_PR_ARGV[backend], tmp_path)]


def test_gitlab_locked_reads_as_closed(tmp_path: Path) -> None:
    run = _Scripted(out=json.dumps({"state": "locked", "web_url": "u"}))
    pr = RealGlabClient().pr_for_branch("feat/x", cwd=tmp_path, run=run)
    assert pr == {"state": "CLOSED", "url": "u", "mergedAt": None}


def test_gitea_finds_no_pr_for_an_unlisted_branch(tmp_path: Path) -> None:
    run = _Scripted(out=_pr_out("gitea", "open"))
    assert RealTeaClient().pr_for_branch("feat/z", cwd=tmp_path, run=run) is None


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize(("rc", "out"), [(1, "{}"), (0, ""), (0, "not json"), (0, "42")])
def test_pr_for_branch_is_none_on_a_failed_or_unparseable_answer(
    backend: str, rc: int, out: str, tmp_path: Path
) -> None:
    pr = _client(backend).pr_for_branch("feat/x", cwd=tmp_path, run=_Scripted(rc, out))
    assert pr is None


@pytest.fixture
def no_binary(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """`subprocess.run` as on a host where the forge CLI is not installed."""
    tried: list[list[str]] = []

    def missing(argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        tried.append(list(argv))
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(subprocess, "run", missing)
    return tried


@pytest.mark.parametrize("backend", BACKENDS)
def test_the_default_runner_reads_a_missing_binary_as_none(
    backend: str, no_binary: list[list[str]], tmp_path: Path
) -> None:
    client = _client(backend)
    assert client.default_branch(cwd=tmp_path) is None
    assert client.pr_for_branch("feat/x", cwd=tmp_path) is None
    assert [argv[0] for argv in no_binary] == [_PR_ARGV[backend][0]] * 2


class _EnvRecorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, argv: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append({"argv": list(argv), **kw})
        return subprocess.CompletedProcess(argv, 0, stdout="trunk\n", stderr="")


@pytest.fixture
def gh_logged_into_ghe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    d = tmp_path / "gh-config"
    d.mkdir()
    (d / "hosts.yml").write_text("github.com:\n    user: u\nghe.example:\n    user: u\n")
    monkeypatch.setenv("GH_CONFIG_DIR", str(d))


def test_the_github_default_runner_carries_gh_host(
    gh_logged_into_ghe: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rec = _EnvRecorder()
    monkeypatch.setattr(subprocess, "run", rec)
    assert RealGhClient(host="ghe.example").default_branch(cwd=tmp_path) == "trunk"
    (call,) = rec.calls
    assert call["argv"] == _DEFAULT_BRANCH_ARGV["github"]
    assert call["cwd"] == tmp_path
    assert call["env"]["GH_HOST"] == "ghe.example"
    assert "PATH" in call["env"]


def test_an_unhosted_github_default_runner_passes_env_none(
    gh_logged_into_ghe: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rec = _EnvRecorder()
    monkeypatch.setattr(subprocess, "run", rec)
    RealGhClient().pr_for_branch("feat/x", cwd=tmp_path)
    assert rec.calls[0]["env"] is None


def test_an_unknown_github_host_fails_closed_before_any_lookup(
    gh_logged_into_ghe: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from fr.gh import GhError

    rec = _EnvRecorder()
    monkeypatch.setattr(subprocess, "run", rec)
    with pytest.raises(GhError, match="evil.example"):
        RealGhClient(host="evil.example").default_branch(cwd=tmp_path)
    assert rec.calls == []
