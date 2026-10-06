"""Host trust is a forge-adapter contract, not a gh-private one (gh#1014,
gh#1015, gh#1013; debug journal `2026-10-06-glab-host-trust`).

#994 gated the GitHub adapter: a threaded host gh is not logged into fails
closed before any process starts. Three parts of the same seam lacked it:

- the GitLab adapter threaded `GITLAB_HOST` with no gate at all, so a
  `GITLAB_TOKEN` could reach a host named by an MR URL or by a cloned repo's
  committed `fr-profiles.yaml` (gh#1014);
- an injected `CommandRunner` (the isolation lifecycle's) ran after the gate
  but was never handed the host, so gh/glab talked to whatever the checkout's
  remote named (gh#1015);
- the error classifier read the refusal as stderr text, so a refused host
  whose NAME happened to carry a transient word read as retryable (gh#1013).
"""

from __future__ import annotations

import inspect
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr import gh as _gh
from fr import glab as _glab
from fr.ghclient import HostRefusedError
from fr.gh import GhHostRefusedError
from fr.glab import GlabHostRefusedError
from fr.hostclient import client_for_backend, forge_error_kind
from fr.real_ghclient import RealGhClient
from fr.real_glabclient import RealGlabClient


class _Recorder:
    """A `subprocess.run` stand-in recording every call's argv and `env`."""

    def __init__(self, out: str = "{}") -> None:
        self.calls: list[tuple[list[str], dict[str, str] | None]] = []
        self.out = out

    def __call__(self, argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(argv), kwargs.get("env")))
        return subprocess.CompletedProcess(argv, 0, stdout=self.out, stderr="")


class _Runner:
    """An injected `CommandRunner`: records the env overlay it is handed."""

    def __init__(self, out: str = "") -> None:
        self.envs: list[dict[str, str] | None] = []
        self.out = out

    def __call__(
        self, argv: list[str], *, cwd: Path, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        self.envs.append(env)
        return subprocess.CompletedProcess(argv, 0, stdout=self.out, stderr="")


@pytest.fixture(autouse=True)
def configs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """gh logged into `ghe.example`, glab into `gitlab.example` — nothing else."""
    gh_dir = tmp_path / "gh"
    gh_dir.mkdir()
    (gh_dir / "hosts.yml").write_text("github.com: {}\nghe.example: {}\n")
    monkeypatch.setenv("GH_CONFIG_DIR", str(gh_dir))
    glab_dir = tmp_path / "glab"
    glab_dir.mkdir()
    (glab_dir / "config.yml").write_text(
        "host: gitlab.com\nhosts:\n    gitlab.com: {}\n    gitlab.example:\n        token: x\n"
    )
    monkeypatch.setenv("GLAB_CONFIG_DIR", str(glab_dir))
    return glab_dir


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    rec = _Recorder()
    monkeypatch.setattr(subprocess, "run", rec)
    return rec


# ---------------------------------------------------------------- gh#1014 --

_GLAB_REFUSAL = (
    "GitLab host 'evil.example' is not one glab is logged into; run "
    "`glab auth login --hostname evil.example` (fr will not point glab, or a "
    "GITLAB_TOKEN, at an unknown host; a GITLAB_TOKEN alone does not count as "
    "a login)"
)


def _glab_calls(tmp_path: Path) -> list[tuple[str, tuple[Any, ...], dict[str, Any]]]:
    """One call per public `RealGlabClient` method, with arguments that would
    reach `glab` if the gate let them."""
    mr = "https://evil.example/g/p/-/merge_requests/1"
    return [
        ("view_issue", ("g/p", 1), {}),
        ("list_linked_prs", ("g/p", 1), {}),
        ("pr_status_by_url", (mr,), {}),
        ("pr_body", ("3",), {"cwd": tmp_path}),
        ("edit_issue_labels", ("g/p", 1), {"add": frozenset({"a"}), "remove": frozenset()}),
        ("edit_issue_state", ("g/p", 1), {"state": "CLOSED"}),
        ("edit_issue_body", ("g/p", 1, "b"), {}),
        ("create_issue", ("g/p",), {"title": "t", "body": "b", "labels": frozenset()}),
        ("ensure_labels", ("g/p", ["a"]), {}),
        ("comment_issue", ("g/p", 1, "b"), {}),
        ("default_branch", (), {"cwd": tmp_path}),
        ("pr_for_branch", ("feat/x",), {"cwd": tmp_path}),
        ("issues_enabled", ("g/p",), {}),
        ("file_exists", ("g/p", "x"), {}),
        ("list_dir", ("g/p", "x"), {}),
        ("read_file", ("g/p", "x"), {}),
    ]


def test_the_glab_call_list_covers_every_public_method(tmp_path: Path) -> None:
    public = {
        name
        for name, fn in vars(RealGlabClient).items()
        if inspect.isfunction(fn) and not name.startswith("_")
    }
    assert {name for name, _, _ in _glab_calls(tmp_path)} == public


def test_every_public_glab_method_refuses_an_unknown_host_before_any_process(
    recorder: _Recorder, tmp_path: Path
) -> None:
    """Soft-fail methods (`list_linked_prs`, `pr_status_by_url`,
    `issues_enabled`, `file_exists`, `list_dir`) catch `GlabError`: a gate
    inside `_run_glab` would read a refused host as "no MR" / "no file". So
    the refusal must fire before every method body, and propagate."""
    client = RealGlabClient(host="evil.example")
    for name, args, kwargs in _glab_calls(tmp_path):
        with pytest.raises(GlabHostRefusedError) as exc:
            getattr(client, name)(*args, **kwargs)
        assert str(exc.value) == _GLAB_REFUSAL, name
    assert recorder.calls == []


def test_the_bare_glab_helpers_refuse_an_unknown_host_too(recorder: _Recorder) -> None:
    """`fr.glab`'s module helpers take `host=` directly: the one subprocess
    path, `_run_glab`, is gated as well, as `fr.gh._run_gh` is."""
    with pytest.raises(GlabHostRefusedError):
        _glab.view_issue("g/p", 1, host="evil.example")
    assert recorder.calls == []


def test_a_known_glab_host_is_threaded_as_gitlab_host(recorder: _Recorder) -> None:
    recorder.out = json.dumps({"state": "opened", "labels": [], "assignees": []})
    RealGlabClient(host="GitLab.Example").view_issue("g/p", 1)
    env = recorder.calls[-1][1]
    assert env is not None and env["GITLAB_HOST"] == "GitLab.Example"
    assert "PATH" in env


def test_no_glab_host_needs_no_login(
    recorder: _Recorder, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GLAB_CONFIG_DIR", str(tmp_path / "nowhere"))
    recorder.out = json.dumps({"state": "opened"})
    RealGlabClient().view_issue("g/p", 1)
    assert recorder.calls[-1][1] is None


def test_a_saas_gitlab_host_is_never_threaded() -> None:
    """As for github.com (review p1-r2): gitlab.com is glab's own default, and
    threading it would demand a config login that token-only CI lacks."""
    client = client_for_backend("gitlab", host="gitlab.com")
    assert isinstance(client, RealGlabClient)
    assert client._host is None


class TestGlabKnownHosts:
    """glab 1.89, probed live: `GLAB_CONFIG_DIR` is exclusive; otherwise glab
    uses the FIRST config it finds, `~/.config/glab-cli` ahead of
    `$XDG_CONFIG_HOME/glab-cli` (it warns, and ignores the second). The gate
    must read the file glab will actually use."""

    def test_reads_the_hosts_keys_of_glab_config_dir(self) -> None:
        assert _glab.known_hosts() == frozenset({"gitlab.com", "gitlab.example"})

    def test_glab_config_dir_is_exclusive(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, configs: Path
    ) -> None:
        (configs / "config.yml").unlink()
        home = tmp_path / "home"
        (home / ".config" / "glab-cli").mkdir(parents=True)
        (home / ".config" / "glab-cli" / "config.yml").write_text("hosts:\n  home.example: {}\n")
        monkeypatch.setenv("HOME", str(home))
        assert _glab.known_hosts() == frozenset()

    def test_home_dot_config_wins_over_xdg(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("GLAB_CONFIG_DIR")
        home, xdg = tmp_path / "home", tmp_path / "xdg"
        (home / ".config" / "glab-cli").mkdir(parents=True)
        (home / ".config" / "glab-cli" / "config.yml").write_text("hosts:\n  home.example: {}\n")
        (xdg / "glab-cli").mkdir(parents=True)
        (xdg / "glab-cli" / "config.yml").write_text("hosts:\n  xdg.example: {}\n")
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert _glab.known_hosts() == frozenset({"home.example"})

    def test_falls_back_to_xdg(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("GLAB_CONFIG_DIR")
        xdg = tmp_path / "xdg"
        (xdg / "glab-cli").mkdir(parents=True)
        (xdg / "glab-cli" / "config.yml").write_text("hosts:\n  xdg.example: {}\n")
        monkeypatch.setenv("HOME", str(tmp_path / "empty-home"))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert _glab.known_hosts() == frozenset({"xdg.example"})

    @pytest.mark.parametrize(
        "body", [None, "", "- a list\n", "{unclosed: [\n", "hosts: [a, b]\n", "host: x\n"]
    )
    def test_a_missing_or_malformed_file_is_the_empty_set(
        self, configs: Path, body: str | None
    ) -> None:
        cfg = configs / "config.yml"
        if body is None:
            cfg.unlink()
        else:
            cfg.write_text(body)
        assert _glab.known_hosts() == frozenset()


# ---------------------------------------------------------------- gh#1015 --


@pytest.mark.parametrize("lookup", ["default_branch", "pr_for_branch"])
def test_an_injected_runner_is_handed_gh_host(lookup: str, tmp_path: Path) -> None:
    run = _Runner()
    args: tuple[Any, ...] = ("feat/x",) if lookup == "pr_for_branch" else ()
    getattr(RealGhClient(host="ghe.example"), lookup)(*args, cwd=tmp_path, run=run)
    assert run.envs == [{"GH_HOST": "ghe.example"}]


@pytest.mark.parametrize("lookup", ["default_branch", "pr_for_branch"])
def test_an_injected_runner_is_handed_gitlab_host(lookup: str, tmp_path: Path) -> None:
    run = _Runner()
    args: tuple[Any, ...] = ("feat/x",) if lookup == "pr_for_branch" else ()
    getattr(RealGlabClient(host="gitlab.example"), lookup)(*args, cwd=tmp_path, run=run)
    assert run.envs == [{"GITLAB_HOST": "gitlab.example"}]


@pytest.mark.parametrize("client", [RealGhClient(), RealGlabClient()])
def test_no_host_hands_the_runner_no_overlay(client: Any, tmp_path: Path) -> None:
    run = _Runner()
    client.default_branch(cwd=tmp_path, run=run)
    assert run.envs == [None]


def test_the_glab_default_runner_carries_gitlab_host(recorder: _Recorder, tmp_path: Path) -> None:
    recorder.out = "main"
    RealGlabClient(host="gitlab.example").default_branch(cwd=tmp_path)
    env = recorder.calls[-1][1]
    assert env is not None and env["GITLAB_HOST"] == "gitlab.example"
    assert "PATH" in env


def test_the_isolation_lifecycle_applies_the_host_on_both_lookups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The lifecycle's runner gets the adapter's host on top of its own env:
    the PR lookup's, and the default-branch lookup's non-interactive network
    env (spec 2026-10-06-forge-remainder §4.B) — neither replaces the other."""
    from fr.isolation import local as local_mod
    from fr.isolation.local import LocalWorktreeDevcontainerTarget

    from tests.unit.test_isolation import FakeRunner, make_repo_with_origin

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path, ["dev"], default="dev")
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner(stdout={"docker": "cid"}))
    state = target.up(None, "feat/r")
    monkeypatch.setattr(local_mod, "client_for", lambda _root: RealGhClient(host="ghe.example"))

    seen: list[tuple[list[str], dict[str, str] | None]] = []
    real_run = target.run

    def run(argv: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        if argv[0] == "gh":
            seen.append((argv, kw.get("env")))
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        if argv[:2] == ["git", "symbolic-ref"]:
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")
        return real_run(argv, **kw)

    monkeypatch.setattr(target, "run", run)
    target._pr_from(state.worktree, state.branch)
    target._resolve_default_branch()

    assert [argv[:3] for argv, _ in seen] == [["gh", "pr", "view"], ["gh", "repo", "view"]]
    pr_env, branch_env = seen[0][1], seen[1][1]
    assert pr_env is not None and pr_env["GH_HOST"] == "ghe.example"
    assert branch_env is not None and branch_env["GH_HOST"] == "ghe.example"
    assert branch_env["GIT_TERMINAL_PROMPT"] == "0"  # the network env survives


# ---------------------------------------------------------------- gh#1013 --


def test_both_refusals_share_one_forge_neutral_type() -> None:
    assert issubclass(GhHostRefusedError, HostRefusedError)
    assert issubclass(GlabHostRefusedError, HostRefusedError)
    assert issubclass(GhHostRefusedError, _gh.GhError)
    assert issubclass(GlabHostRefusedError, _glab.GlabError)


# A host whose NAME carries the classifier's vocabulary: by text these read as a
# transient failure ("timeout", "connection refused") or a gone target ("404").
_TRICKY = ["git.timeout.example", "connection-refused.example", "404.example"]


@pytest.mark.parametrize("host", _TRICKY)
def test_a_refusal_is_classified_by_type_not_by_its_text(host: str) -> None:
    gh_refusal = GhHostRefusedError(f"GitHub host {host!r} is not one gh is logged into")
    glab_refusal = GlabHostRefusedError(f"GitLab host {host!r} is not one glab is logged into")
    for refusal in (gh_refusal, glab_refusal):
        assert forge_error_kind(refusal) == "unknown"
    assert _gh.classify(gh_refusal) == "unknown"
    assert not _gh.is_transient(gh_refusal)
    assert not _glab.is_transient(glab_refusal)
    assert not _glab.is_not_found(glab_refusal)


def test_a_refused_host_is_never_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def op() -> None:
        calls.append(1)
        raise GhHostRefusedError("GitHub host 'git.timeout.example' is not one gh is logged into")

    monkeypatch.setattr(_gh.time, "sleep", lambda _s: None)
    with pytest.raises(GhHostRefusedError):
        _gh.with_retry(op)
    assert calls == [1]


def test_a_raw_gh_failure_is_still_classified_by_its_text() -> None:
    assert _gh.classify(_gh.GhError("x", stderr="HTTP 403: API rate limit exceeded")) == (
        "rate_limit"
    )
    assert _gh.classify(_gh.GhError("connection reset")) == "warn"
