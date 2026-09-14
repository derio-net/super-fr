"""Phase 3/5: SecretProvider wired into the devcontainer Target (up/exec/down)
+ the `fr isolation exec --secret` CLI. The provider_factory seam (like the
Runner seam) lets these run without a live Infisical.

Token dirs are per-workspace and follow the profile's mount (review I1/I2):
`~/.cache/fr/run-tokens/<repo>/<profile>/<worktree-basename>`."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import isolation_cmd
from fr.isolation.local import LocalWorktreeDevcontainerTarget
from fr.isolation.secrets import (
    CONTAINER_TOKEN_DIR,
    ExecWrap,
    InfisicalProvider,
    ProfileContext,
    UniversalAuth,
    canonical_token_dir,
)
from fr.isolation.types import IsolationError, IsolationState
from typer.testing import CliRunner

from tests.unit.test_isolation import FakeRunner as DockerFakeRunner
from tests.unit.test_isolation import _gc_env, make_repo

runner = CliRunner()


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, argv, cwd=None, check=False, capture=True):
        if argv[0] == "git":
            return subprocess.run(argv, cwd=cwd, check=check, capture_output=True, text=True)
        self.calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    def argv_for(self, binary: str) -> list[list[str]]:
        return [c for c in self.calls if c[0] == binary]


class _RecordingMinter:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, argv, env) -> str:
        self.calls += 1
        return "tok-secret"


def _fake_mint(argv, env) -> str:
    return "tok-secret"


def _infisical_factory(ctx: ProfileContext) -> InfisicalProvider:
    return InfisicalProvider(auth=UniversalAuth(minter=_fake_mint), validate=lambda c: None)


def _mount(repo: str, profile: str) -> str:
    return (
        f"type=bind,source=${{localEnv:HOME}}/.cache/fr/run-tokens/{repo}/{profile}/"
        f"${{localWorkspaceFolderBasename}},target={CONTAINER_TOKEN_DIR}"
    )


PROFILES_YAML = (
    "default: sec\n"
    "profiles:\n"
    "  sec:\n"
    "    secret_provider: infisical\n"
    "    secrets: [DEPLOY_KEY]\n"
    "    infisical:\n"
    "      project_id: p1\n"
    "      env: prod\n"
    "      path: /fr/x\n"
    "      auth:\n"
    "        method: universal-auth\n"
    "        client_id_env: FR_CID\n"
    "        client_secret_env: FR_CSEC\n"
)


def _write_infisical_profile(
    root: Path, repo_name: str, profiles_yaml: str = PROFILES_YAML
) -> None:
    d = root / ".devcontainer" / "sec"
    d.mkdir(parents=True, exist_ok=True)
    (d / "devcontainer.json").write_text(
        json.dumps({"image": "x", "runArgs": ["--mount", _mount(repo_name, "sec")]})
    )
    (root / ".devcontainer" / "fr-profiles.yaml").write_text(profiles_yaml)


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, IsolationState]:
    """A bare (non-git) repo dir + worktree dir carrying an infisical profile —
    enough for exec, which never touches git."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = tmp_path / "repo"
    repo.mkdir()
    wt = tmp_path / "wt"
    _write_infisical_profile(wt, "repo")
    st = IsolationState(repo_root=repo, branch="feat/s", worktree=wt, profile="sec", created_at="t")
    return repo, wt, st


def _token_dir(tmp_path: Path) -> Path:
    return canonical_token_dir("repo", "sec", tmp_path / "wt")


def _infisical_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A REAL git repo with a committed infisical profile, for up/down tests."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path)
    _write_infisical_profile(repo, repo.name)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "p"],
        check=True,
    )
    return repo


def test_exec_with_secret_prefixes_infisical_run_and_hides_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FR_CID", "id")
    monkeypatch.setenv("FR_CSEC", "secret-val")
    repo, _, st = _setup(tmp_path, monkeypatch)
    fr_ = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=fr_, provider_factory=_infisical_factory)

    rc = target.exec(st, ["pytest", "-q"], keys=["DEPLOY_KEY"])

    assert rc == 0
    (call,) = fr_.argv_for("devcontainer")
    flat = " ".join(call)
    assert "infisical" in flat and "run" in flat
    assert "--path /fr/x" in flat
    assert "tok-secret" not in flat  # token rides the mounted file, never argv
    assert call[-2:] == ["pytest", "-q"]  # user command preserved at the tail


def test_exec_undeclared_secret_fails_fast(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _, st = _setup(tmp_path, monkeypatch)
    fr_ = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=fr_, provider_factory=_infisical_factory)

    with pytest.raises(IsolationError) as ei:
        target.exec(st, ["echo", "hi"], keys=["NOPE"])

    assert "NOPE" in str(ei.value)
    assert fr_.argv_for("devcontainer") == []  # fail-fast: nothing ran, nothing minted


def test_exec_secret_uses_no_remote_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The token is conveyed via the mounted file, NOT --remote-env (which is
    # host-ps-visible). Infisical's exec_env is empty → no --remote-env at all.
    monkeypatch.setenv("FR_CID", "id")
    monkeypatch.setenv("FR_CSEC", "secret-val")
    repo, _, st = _setup(tmp_path, monkeypatch)
    fr_ = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=fr_, provider_factory=_infisical_factory)
    target.exec(st, ["pytest"], keys=["DEPLOY_KEY"])
    (call,) = fr_.argv_for("devcontainer")
    assert "--remote-env" not in call


class _TokenDirWatcher(FakeRunner):
    """Snapshots the host token dir's contents AT exec time, so a test can
    prove the token existed while the command ran and is gone afterwards."""

    def __init__(self, token_dir: Path, fail: bool = False) -> None:
        super().__init__()
        self.token_dir = token_dir
        self.fail = fail
        self.seen: list[str] = []

    def __call__(self, argv, cwd=None, check=False, capture=True):
        if argv[0] == "devcontainer":
            self.seen = [p.read_text() for p in self.token_dir.iterdir()]
            if self.fail:
                raise RuntimeError("boom")  # simulate the exec aborting mid-run
        return super().__call__(argv, cwd=cwd, check=check, capture=capture)


def test_exec_clears_token_after_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FR_CID", "id")
    monkeypatch.setenv("FR_CSEC", "secret-val")
    repo, _, st = _setup(tmp_path, monkeypatch)
    d = _token_dir(tmp_path)
    watcher = _TokenDirWatcher(d)
    target = LocalWorktreeDevcontainerTarget(
        repo, runner=watcher, provider_factory=_infisical_factory
    )
    target.exec(st, ["pytest"], keys=["DEPLOY_KEY"])
    assert watcher.seen == ["tok-secret"]  # exactly one per-exec file, live during the run
    assert list(d.iterdir()) == []  # post_exec unlinked it after the command returned


def test_exec_clears_token_on_abort(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FR_CID", "id")
    monkeypatch.setenv("FR_CSEC", "secret-val")
    repo, _, st = _setup(tmp_path, monkeypatch)
    d = _token_dir(tmp_path)
    watcher = _TokenDirWatcher(d, fail=True)
    target = LocalWorktreeDevcontainerTarget(
        repo, runner=watcher, provider_factory=_infisical_factory
    )
    with pytest.raises(RuntimeError):
        target.exec(st, ["pytest"], keys=["DEPLOY_KEY"])
    assert watcher.seen == ["tok-secret"]
    assert list(d.iterdir()) == []  # finally → post_exec ran even though the exec aborted


class _LeakyProvider:
    """exec_wrap mints (writes a file) and THEN fails — the shape of a KeyError
    on a half-written profile after the token hit disk (review I3)."""

    def __init__(self, token_dir: Path) -> None:
        self.token_dir = token_dir
        self.events: list[str] = []

    def up_prepare(self, ctx: ProfileContext) -> None: ...

    def exec_wrap(self, ctx: ProfileContext, want_secrets: bool) -> ExecWrap:
        self.token_dir.mkdir(parents=True, exist_ok=True)
        (self.token_dir / "x.token").write_text("tok")
        raise KeyError("path")

    def post_exec(self, ctx: ProfileContext) -> None:
        self.events.append("post_exec")
        shutil.rmtree(self.token_dir, ignore_errors=True)

    def cleanup(self, ctx: ProfileContext) -> None: ...


def test_exec_wrap_failure_after_mint_still_runs_post_exec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, st = _setup(tmp_path, monkeypatch)
    d = _token_dir(tmp_path)
    leaky = _LeakyProvider(d)
    fr_ = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=fr_, provider_factory=lambda c: leaky)
    with pytest.raises(KeyError):
        target.exec(st, ["pytest"], keys=["DEPLOY_KEY"])
    assert leaky.events == ["post_exec"]  # exec_wrap is INSIDE the try/finally
    assert not d.exists()
    assert fr_.argv_for("devcontainer") == []


def test_exec_secret_with_incomplete_infisical_block_raises_before_mint_and_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FR_CID", "id")
    monkeypatch.setenv("FR_CSEC", "secret-val")
    repo, wt, st = _setup(tmp_path, monkeypatch)
    _write_infisical_profile(wt, "repo", PROFILES_YAML.replace("      path: /fr/x\n", ""))
    minter = _RecordingMinter()
    fr_ = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(
        repo,
        runner=fr_,
        provider_factory=lambda c: InfisicalProvider(auth=UniversalAuth(minter=minter)),
    )
    with pytest.raises(IsolationError, match="path"):
        target.exec(st, ["pytest"], keys=["DEPLOY_KEY"])
    assert minter.calls == 0
    assert fr_.argv_for("devcontainer") == []
    assert not _token_dir(tmp_path).exists()


def test_exec_without_secret_mints_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _, st = _setup(tmp_path, monkeypatch)  # FR_CID/FR_CSEC deliberately unset
    fr_ = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=fr_, provider_factory=_infisical_factory)
    assert target.exec(st, ["pytest"]) == 0
    (call,) = fr_.argv_for("devcontainer")
    assert "infisical" not in " ".join(call)  # no wrap
    assert not _token_dir(tmp_path).exists()  # no mint, no file


@pytest.mark.parametrize(
    "yaml_text",
    [
        "profiles: [unclosed\n",
        "profiles: null\n",
        "default: sec\nprofiles:\n  sec:\n    secret_provider: vaultt\n",
    ],
)
def test_plain_exec_never_reads_the_profile_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, yaml_text: str
) -> None:
    """Back-compat (review m1): without --secret, exec must not parse
    fr-profiles.yaml or build a provider — a malformed file, a null `profiles:`
    or a typo'd secret_provider must not break the exec that worked before."""
    repo, wt, st = _setup(tmp_path, monkeypatch)
    (wt / ".devcontainer" / "fr-profiles.yaml").write_text(yaml_text)
    fr_ = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=fr_)  # the REAL provider_for
    assert target.exec(st, ["echo", "hi"]) == 0
    (call,) = fr_.argv_for("devcontainer")
    assert call[-2:] == ["echo", "hi"]


class _SpyProvider:
    def __init__(self) -> None:
        self.events: list[str] = []

    def up_prepare(self, ctx: ProfileContext) -> None:
        self.events.append("up_prepare")

    def exec_wrap(self, ctx: ProfileContext, want_secrets: bool) -> ExecWrap:
        self.events.append("exec_wrap")
        return ExecWrap()

    def post_exec(self, ctx: ProfileContext) -> None:
        self.events.append("post_exec")

    def cleanup(self, ctx: ProfileContext) -> None:
        self.events.append("cleanup")


def test_up_and_down_run_provider_up_prepare_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A REAL repo + worktree: 4.x `down` verifies `git worktree remove`, so the
    # 3.x bare-directory fixture would raise after cleanup already ran.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["sec"], default="sec")
    spy = _SpyProvider()
    target = LocalWorktreeDevcontainerTarget(
        repo, runner=FakeRunner(), provider_factory=lambda c: spy
    )

    st = target.up(profile=None, branch="feat/s")
    assert spy.events == ["up_prepare"]
    target.down(st, force=True)

    assert spy.events == ["up_prepare", "cleanup"]
    assert not st.worktree.exists()


def test_down_of_one_workspace_leaves_sibling_workspace_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review I1: two workspaces on ONE profile each own a token dir; tearing A
    down must not touch B's dir (B's container has it bind-mounted and may have
    an exec in flight)."""
    repo = _infisical_repo(tmp_path, monkeypatch)
    target = LocalWorktreeDevcontainerTarget(
        repo, runner=FakeRunner(), provider_factory=_infisical_factory
    )
    a = target.up(profile=None, branch="feat/a")
    b = target.up(profile=None, branch="feat/b")
    dir_a = canonical_token_dir(repo.name, "sec", a.worktree)
    dir_b = canonical_token_dir(repo.name, "sec", b.worktree)
    assert dir_a.is_dir() and dir_b.is_dir() and dir_a != dir_b  # up_prepare, per workspace
    (dir_b / "inflight.token").write_text("tok-b")

    target.down(a, force=True)

    assert not dir_a.exists()
    assert (dir_b / "inflight.token").read_text() == "tok-b"  # B untouched


def test_up_prepare_follows_the_committed_mount_not_the_runtime_repo_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review I2: the mount was baked with the scaffold-time repo name
    (`other-clone`); the runtime target's repo_root is `repo`. The host dir the
    provider prepares must be the one the container will actually bind-mount."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path)
    _write_infisical_profile(repo, "other-clone")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "p"],
        check=True,
    )
    target = LocalWorktreeDevcontainerTarget(
        repo, runner=FakeRunner(), provider_factory=_infisical_factory
    )
    st = target.up(profile=None, branch="feat/x")
    assert canonical_token_dir("other-clone", "sec", st.worktree).is_dir()
    assert not canonical_token_dir("repo", "sec", st.worktree).exists()


@pytest.mark.parametrize("config", ["missing", "corrupt"])
def test_down_removes_token_dir_even_when_profile_config_is_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config: str
) -> None:
    """Review finding I1 (June): with the REAL provider_for, a missing
    fr-profiles.yaml falls back to env-file (whose cleanup is a no-op) and a
    corrupt one raises — either way the provider path would skip the token dir.
    The devcontainer teardown removes this workspace's canonical token dir
    unconditionally (the mount is unreadable too — an env-file devcontainer.json
    — so the canonical layout is the fallback)."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["sec"], default="sec")  # no secret_provider key
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner())
    st = target.up(profile=None, branch="feat/s")
    cfg = st.worktree / ".devcontainer" / "fr-profiles.yaml"
    if config == "missing":
        cfg.unlink()
    else:
        cfg.write_text("profiles: [unclosed\n")
    d = canonical_token_dir("repo", "sec", st.worktree)
    d.mkdir(parents=True)
    (d / "leftover.token").write_text("tok-old")  # a crash left a token behind

    target.down(st, force=True)

    assert not d.exists()
    assert not st.worktree.exists()  # the teardown itself was not blocked


def test_teardown_keeps_token_dir_until_the_container_is_verified_gone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review m2: if `docker rm` fails verification the workspace is KEPT (state
    intact, container still up) — its bind-mount source must still exist."""
    repo = _infisical_repo(tmp_path, monkeypatch)
    docker = DockerFakeRunner(fail_on="rm", stdout={"docker": "cid running"})
    target = LocalWorktreeDevcontainerTarget(
        repo, runner=docker, provider_factory=_infisical_factory
    )
    st = target.up(profile=None, branch="feat/s")
    d = canonical_token_dir(repo.name, "sec", st.worktree)
    assert d.is_dir()

    with pytest.raises(IsolationError, match="still present"):
        target.down(st, force=True)

    assert d.is_dir()  # not removed ahead of a teardown that did not complete
    assert st.worktree.exists()


def _committed_profile(repo: Path, mount_source: str) -> None:
    d = repo / ".devcontainer" / "sec"
    d.mkdir(parents=True, exist_ok=True)
    (d / "devcontainer.json").write_text(
        json.dumps(
            {
                "image": "x",
                "runArgs": [
                    "--mount",
                    f"type=bind,source={mount_source},target={CONTAINER_TOKEN_DIR}",
                ],
            }
        )
    )
    (repo / ".devcontainer" / "fr-profiles.yaml").write_text(PROFILES_YAML)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "p"],
        check=True,
    )


def test_down_with_home_as_mount_source_deletes_nothing_in_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verification V1: a committed (PR-reachable) mount whose source is $HOME
    must never make `down` truncate the dotfiles in $HOME. The workspace is
    brought up through a spy provider (the real one refuses at up_prepare —
    provider tests cover that) and torn down with the REAL infisical provider."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path)
    _committed_profile(repo, "${localEnv:HOME}")
    st = LocalWorktreeDevcontainerTarget(
        repo, runner=FakeRunner(), provider_factory=lambda c: _SpyProvider()
    ).up(profile=None, branch="feat/s")
    home = tmp_path / "home"
    (home / ".bashrc").write_text("sentinel")
    before = sorted(p.name for p in home.iterdir())

    LocalWorktreeDevcontainerTarget(
        repo, runner=FakeRunner(), provider_factory=_infisical_factory
    ).down(st, force=True)

    assert (home / ".bashrc").read_text() == "sentinel"
    assert sorted(p.name for p in home.iterdir()) == before
    assert not st.worktree.exists()  # the teardown itself completed


def test_down_follows_a_mount_that_differs_from_the_canonical_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verification V8: the committed mount names `other-clone`; `down` removes
    THAT dir and leaves a canonical-layout sibling (keyed on the runtime repo
    name) alone."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path)
    _write_infisical_profile(repo, "other-clone")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "p"],
        check=True,
    )
    target = LocalWorktreeDevcontainerTarget(
        repo, runner=FakeRunner(), provider_factory=_infisical_factory
    )
    st = target.up(profile=None, branch="feat/x")
    mounted = canonical_token_dir("other-clone", "sec", st.worktree)
    assert mounted.is_dir()
    sibling = canonical_token_dir(repo.name, "sec", st.worktree)
    sibling.mkdir(parents=True)
    (sibling / "keep.token").write_text("x")

    target.down(st, force=True)

    assert not mounted.exists()
    assert (sibling / "keep.token").read_text() == "x"


def test_gc_orphan_token_glob_skips_empty_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verification V2: a docker label path of `/` has an empty basename and
    parent name — the pattern would be `*/`, matching every repo dir."""
    from fr.isolation.local import GcWorkspace

    repo, _docker, target, _up = _gc_env(tmp_path, monkeypatch)
    live = canonical_token_dir(repo.name, "dev", tmp_path / "feat__live")
    live.mkdir(parents=True)
    (live / "live.token").write_text("tok")

    target._reap_orphan_tokens(GcWorkspace(worktree=Path("/"), container_id="c", state=None))

    assert (live / "live.token").read_text() == "tok"


def test_gc_orphan_token_glob_escapes_metacharacters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verification V2: a worktree basename with glob metacharacters must match
    only itself — `feat__[x]` unescaped would match `feat__x` (a live sibling)."""
    repo, docker, target, _up = _gc_env(tmp_path, monkeypatch)
    gone = tmp_path / "home" / ".cache" / "fr" / "worktrees" / repo.name / "feat__[x]"
    docker.docker_labels = [("cOrph", str(gone))]
    orphan = canonical_token_dir(repo.name, "dev", gone)
    orphan.mkdir(parents=True)
    (orphan / "left.token").write_text("tok")
    live = canonical_token_dir(repo.name, "dev", tmp_path / "feat__x")
    live.mkdir(parents=True)
    (live / "live.token").write_text("tok")

    target.gc()

    assert not orphan.exists()
    assert (live / "live.token").read_text() == "tok"


def test_gc_orphan_token_reap_continues_past_a_refused_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """W4: matches are visited in sorted order, each in its own try. `aaa/<base>`
    is reached through a symlinked profile dir (refused by containment, target
    untouched); `dev/<base>` after it must still be reaped."""
    repo, docker, target, _up = _gc_env(tmp_path, monkeypatch)
    gone = tmp_path / "home" / ".cache" / "fr" / "worktrees" / repo.name / "feat__gone"
    docker.docker_labels = [("cOrph", str(gone))]
    elsewhere = tmp_path / "elsewhere" / gone.name
    elsewhere.mkdir(parents=True)
    (elsewhere / "precious").write_text("keep")
    root = tmp_path / "home" / ".cache" / "fr" / "run-tokens" / repo.name
    root.mkdir(parents=True)
    (root / "aaa").symlink_to(elsewhere.parent)  # refused: a symlink in the path
    good = canonical_token_dir(repo.name, "dev", gone)
    good.mkdir(parents=True)
    (good / "left.token").write_text("tok")

    target.gc()

    assert (elsewhere / "precious").read_text() == "keep" and (root / "aaa").is_symlink()
    assert not good.exists()


def test_gc_label_orphan_leaves_tokens_when_the_container_survives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verification V3: like m2 for `down` — tokens go only once the container
    is confirmed absent. A `docker rm` that did not take leaves the dir alone."""
    repo, docker, target, _up = _gc_env(
        tmp_path, monkeypatch, fail_on="rm", stdout={"docker": "cOrph running"}
    )
    gone = tmp_path / "home" / ".cache" / "fr" / "worktrees" / repo.name / "feat__gone"
    docker.docker_labels = [("cOrph", str(gone))]
    d = canonical_token_dir(repo.name, "dev", gone)
    d.mkdir(parents=True)
    (d / "left.token").write_text("tok")

    target.gc()

    assert (d / "left.token").read_text() == "tok"  # container still present → left alone


def test_gc_stale_state_reap_removes_the_orphan_token_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review m3: a worktree removed out of band leaves its token dir behind;
    retiring the stale state record also reaps that dir (canonical layout — the
    mount cannot be read once the worktree is gone)."""
    repo, _runner, target, up = _gc_env(tmp_path, monkeypatch)
    wt = up("feat/gone")
    d = canonical_token_dir(repo.name, "dev", wt)
    d.mkdir(parents=True)
    (d / "left.token").write_text("tok")
    shutil.rmtree(wt)

    (action,) = [a for a in target.gc() if a.branch == "feat/gone"]

    assert action.action == "reaped"
    assert not d.exists()


def test_gc_label_orphan_reap_removes_the_orphan_token_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review m3, the other orphan path: a container found only by docker label
    (worktree AND state gone). Without a state record the profile is unknown, so
    every `<repo>/<profile>/<worktree-basename>` match under the canonical root is reaped."""
    repo, docker, target, _up = _gc_env(tmp_path, monkeypatch)
    gone = tmp_path / "home" / ".cache" / "fr" / "worktrees" / repo.name / "feat__gone"
    docker.docker_labels = [("cOrph", str(gone))]
    d = canonical_token_dir(repo.name, "dev", gone)
    d.mkdir(parents=True)
    (d / "left.token").write_text("tok")

    actions = [a for a in target.gc() if a.verdict == "orphan"]

    assert actions and actions[0].action == "reaped"
    assert not d.exists()


def test_cli_secret_undeclared_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(r)], check=True)
    d = r / ".devcontainer" / "dev"  # env-file profile, no secrets declared
    d.mkdir(parents=True)
    (d / "devcontainer.json").write_text('{"image": "x"}')
    subprocess.run(["git", "-C", str(r), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(r), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"],
        check=True,
    )
    calls: list[list[str]] = []

    def run(argv, cwd=None, check=False, capture=True):
        if argv[0] == "git":
            return subprocess.run(argv, cwd=cwd, check=check, capture_output=True, text=True)
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(isolation_cmd, "_runner", run)
    runner.invoke(app, ["isolation", "up", "--repo", str(r), "--branch", "feat/s"])

    res = runner.invoke(
        app,
        [
            "isolation",
            "exec",
            "--repo",
            str(r),
            "--branch",
            "feat/s",
            "--secret",
            "NOPE",
            "--",
            "echo",
            "hi",
        ],
    )

    assert res.exit_code == 2, res.output
    assert "NOPE" in res.output
    assert not any(c[:2] == ["devcontainer", "exec"] for c in calls)  # fail-fast
