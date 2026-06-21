"""fr isolation — Target protocol, state, profiles, and the local target.

All devcontainer/docker/gh calls go through the Runner seam; git calls hit
real throwaway repos (cheap, deterministic). Nothing here needs Docker.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fr.isolation.local import (
    LocalWorktreeDevcontainerTarget,
    branch_changes_present,
    subprocess_runner,
)
from fr.isolation.types import (
    IsolationError,
    IsolationState,
    delete_state,
    load_state,
    profiles_config,
    resolve_profile,
    save_state,
    secrets_env_file,
    state_path,
)


def make_repo(
    tmp_path: Path,
    profiles: list[str] | None = None,
    default: str | None = None,
    profiles_yaml: str = "fr-profiles.yaml",
    env_file_mount: str | None = None,
) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    (repo / "README.md").write_text("x\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            "init",
        ],
        check=True,
    )
    for name in profiles or []:
        d = repo / ".devcontainer" / name
        d.mkdir(parents=True)
        config: dict = {"image": "x"}
        if env_file_mount:
            config["runArgs"] = ["--env-file", env_file_mount]
        (d / "devcontainer.json").write_text(json.dumps(config) + "\n")
    if default:
        (repo / ".devcontainer" / profiles_yaml).write_text(
            f"default: {default}\nprofiles:\n  {default}:\n    purpose: test\n"
        )
    if profiles:
        # committed, as in real repos — worktrees check out .devcontainer/
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "user.email=t@t",
                "-c",
                "user.name=t",
                "commit",
                "-qm",
                "profiles",
            ],
            check=True,
        )
    return repo


def add_worktree(repo: Path, branch: str = "feat/x") -> Path:
    """Add a linked worktree of `repo` — its .git is a gitfile, not a dir."""
    wt = repo.parent / "wt"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-q", str(wt), "-b", branch],
        check=True,
    )
    return wt


def _git_out(repo: Path, *args: str) -> str:
    # Output-capturing git helper. Distinct from the fire-and-forget `_git` the
    # merge-config tests define later in this file — DON'T merge the two names.
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def make_repo_with_origin(
    tmp_path: Path,
    profiles: list[str] | None = None,
    default: str | None = None,
) -> tuple[Path, Path]:
    """A real repo wired to a real bare `origin`, with `main` pushed.

    FakeRunner delegates git to the real binary, so fetch / origin/<default>
    resolution must run against a real remote (spec "Testing"). Returns
    (repo, origin_dir).
    """
    repo = make_repo(tmp_path, profiles=profiles, default=default)
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(origin)], check=True)
    subprocess.run(["git", "-C", str(repo), "push", "-q", "origin", "main"], check=True)
    return repo, origin


def _commit_stray_feature_branch(repo: Path, branch: str = "stray-feature") -> str:
    """Park `repo` on a NEW feature branch carrying an un-merged commit.

    Returns the stray commit sha. Reproduces the incident's precondition: the
    base repo's HEAD is an un-merged commit that must NOT ride into a fresh
    isolation branch.
    """
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", branch], check=True)
    (repo / "stray.txt").write_text("unrelated\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            "stray",
        ],
        check=True,
    )
    return _git_out(repo, "rev-parse", "HEAD")


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant]
        ).returncode
        == 0
    )


class FakeRunner:
    """Records non-git argv; delegates git to the real binary."""

    def __init__(self, fail_on: str | None = None, stdout: dict[str, str] | None = None):
        self.calls: list[list[str]] = []
        self.git_calls: list[list[str]] = []
        self.captures: list[bool] = []
        self.fail_on = fail_on
        self.stdout = stdout or {}

    def __call__(
        self, argv: list[str], cwd: Path | None = None, check: bool = False, capture: bool = True
    ):
        self.captures.append(capture)
        if argv[0] == "git":
            # `gh` is faked, but git hits the real binary — record git argv too so
            # tests can assert mechanism (e.g. a fetch ran / did not run) on top of
            # the resulting repo state.
            self.git_calls.append(list(argv))
            return subprocess.run(argv, cwd=cwd, check=check, capture_output=True, text=True)
        self.calls.append(list(argv))
        rc = 1 if (self.fail_on and self.fail_on in argv[0:2]) else 0
        out = self.stdout.get(argv[0], "")
        return subprocess.CompletedProcess(argv, rc, stdout=out, stderr="")

    def argv_for(self, binary: str) -> list[list[str]]:
        return [c for c in self.calls if c[0] == binary]


# ---------- state ----------


def test_state_roundtrip(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["dev"], default="dev")
    st = IsolationState(
        repo_root=repo,
        branch="vk-iso/x",
        worktree=tmp_path / "wt",
        profile="dev",
        created_at="2026-06-04T00:00:00Z",
    )
    save_state(st)
    p = state_path(repo, "vk-iso/x")
    assert p.is_file() and str(p).startswith(str(repo / ".git"))
    assert load_state(repo, "vk-iso/x") == st


def test_state_path_sanitizes_branch_slash(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    assert "/" not in state_path(repo, "feat/x").name


def test_state_dir_worktree_safe(tmp_path: Path) -> None:
    # #292: in a linked worktree <wt>/.git is a gitfile, not a dir. State must
    # resolve under the shared (main) .git dir, identically from either path.
    repo = make_repo(tmp_path)
    wt = add_worktree(repo)
    common = repo / ".git"  # main checkout's real .git dir
    st = IsolationState(
        repo_root=wt,
        branch="feat/x",
        worktree=wt,
        profile="dev",
        created_at="2026-06-09T00:00:00Z",
    )
    save_state(st)  # must NOT raise NotADirectoryError
    p = state_path(wt, "feat/x")
    assert p.is_file()
    assert str(p).startswith(str(common / "fr" / "isolation"))
    # worktree-invariant key: main and worktree resolve to the same path
    assert state_path(wt, "feat/x") == state_path(repo, "feat/x")
    assert load_state(wt, "feat/x") == st
    delete_state(wt, "feat/x")
    assert load_state(wt, "feat/x") is None


def test_state_dir_resolves_symlinked_repo_root(tmp_path: Path) -> None:
    # #292 hardening: _git_common_dir resolves its own input, so a symlinked
    # repo path keys identically to the real path — closing the macOS
    # /tmp->/private/tmp realpath split-brain class regardless of caller.
    repo = make_repo(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(repo)
    assert state_path(link, "feat/x") == state_path(repo, "feat/x")


def test_target_normalizes_repo_root_from_worktree(tmp_path: Path) -> None:
    # #292: a Target built from a worktree path keys off the MAIN checkout, so
    # state + teardown survive the (possibly ephemeral) launch worktree.
    repo = make_repo(tmp_path, ["dev"], default="dev")
    wt = add_worktree(repo, "feat/y")
    t = LocalWorktreeDevcontainerTarget(wt)
    assert t.repo_root == repo.resolve()


def test_up_on_non_git_path_raises(tmp_path: Path) -> None:
    # #292: __init__ normalization must not swallow the friendly "not a git
    # repo" guard. _git_common_dir falls back to repo_root/.git for a non-repo,
    # so repo_root stays put and up() still raises IsolationError.
    t = LocalWorktreeDevcontainerTarget(tmp_path)
    with pytest.raises(IsolationError):
        t.up(profile=None, branch="x", path=None)


# ---------- profiles ----------


def test_resolve_profile_default(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["dev", "admin"], default="dev")
    assert resolve_profile(repo, None) == "dev"
    assert resolve_profile(repo, "admin") == "admin"


def test_resolve_profile_no_devcontainer_points_at_fr_init(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    with pytest.raises(IsolationError, match="fr-init"):
        resolve_profile(repo, None)


def test_resolve_profile_unknown_lists_available(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["dev"], default="dev")
    with pytest.raises(IsolationError, match="dev"):
        resolve_profile(repo, "nope")


def test_resolve_profile_no_default_single_profile(tmp_path: Path) -> None:
    """One profile dir, no vk-profiles.yaml → that profile is the default."""
    repo = make_repo(tmp_path, ["dev"])
    assert resolve_profile(repo, None) == "dev"


# ---------- dual-read renames (#272) ----------


def test_profiles_config_reads_fr_profiles(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    repo = make_repo(tmp_path, ["dev"], default="dev")  # writes fr-profiles.yaml
    assert profiles_config(repo)["default"] == "dev"
    assert "legacy" not in capsys.readouterr().err


def test_profiles_config_vk_fallback_warns(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    repo = make_repo(tmp_path, ["dev"], default="dev", profiles_yaml="vk-profiles.yaml")
    assert profiles_config(repo)["default"] == "dev"
    err = capsys.readouterr().err
    assert "legacy" in err and "vk-profiles.yaml" in err and "fr init migrate" in err


def test_profiles_config_fr_wins_over_vk(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    repo = make_repo(tmp_path, ["dev"], default="dev", profiles_yaml="vk-profiles.yaml")
    (repo / ".devcontainer" / "fr-profiles.yaml").write_text(
        "default: dev\nprofiles:\n  dev:\n    purpose: fr-side\n"
    )
    assert profiles_config(repo)["profiles"]["dev"]["purpose"] == "fr-side"
    assert "legacy" not in capsys.readouterr().err


def test_secrets_env_file_is_fr_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    p = secrets_env_file("myrepo", "dev")
    assert str(p).endswith(".config/fr/secrets/myrepo/dev.env")


def test_save_state_writes_fr_dir(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["dev"], default="dev")
    st = IsolationState(
        repo_root=repo,
        branch="feat/x",
        worktree=tmp_path / "wt",
        profile="dev",
        created_at="2026-06-07T00:00:00Z",
    )
    save_state(st)
    assert str(state_path(repo, "feat/x")).startswith(str(repo / ".git" / "fr" / "isolation"))


def test_load_state_legacy_vk_dir_warns(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    repo = make_repo(tmp_path, ["dev"], default="dev")
    legacy = repo / ".git" / "vk" / "isolation"
    legacy.mkdir(parents=True)
    st = IsolationState(
        repo_root=repo,
        branch="feat/x",
        worktree=tmp_path / "wt",
        profile="dev",
        created_at="2026-06-07T00:00:00Z",
    )
    (legacy / "feat__x.json").write_text(st.model_dump_json())
    assert load_state(repo, "feat/x") == st
    assert "legacy" in capsys.readouterr().err


def test_load_state_fr_wins_over_legacy(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    repo = make_repo(tmp_path, ["dev"], default="dev")
    legacy = repo / ".git" / "vk" / "isolation"
    legacy.mkdir(parents=True)
    old = IsolationState(
        repo_root=repo,
        branch="feat/x",
        worktree=tmp_path / "old-wt",
        profile="dev",
        created_at="2026-06-01T00:00:00Z",
    )
    (legacy / "feat__x.json").write_text(old.model_dump_json())
    new = old.model_copy(update={"worktree": tmp_path / "new-wt"})
    save_state(new)
    assert load_state(repo, "feat/x") == new
    assert "legacy" not in capsys.readouterr().err


# ---------- target.up ----------


def test_up_creates_worktree_envfile_and_devcontainer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(
        tmp_path,
        ["dev"],
        default="dev",
        env_file_mount="${localEnv:HOME}/.config/fr/secrets/repo/dev.env",
    )
    runner = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    st = target.up(profile=None, branch="vk-iso/test")

    assert st.worktree.is_dir() and (st.worktree / "README.md").is_file()
    assert str(st.worktree).startswith(
        str(tmp_path / "home" / ".cache" / "fr" / "worktrees")
    )  # ~/.cache/fr default
    env = tmp_path / "home" / ".config" / "fr" / "secrets" / "repo" / "dev.env"
    assert env.is_file()  # mount-followed: created when missing

    (up,) = runner.argv_for("devcontainer")
    assert up[1] == "up"
    assert f"--workspace-folder={st.worktree}" in up or str(st.worktree) in up
    joined = " ".join(up)
    assert ".devcontainer/dev/devcontainer.json" in joined
    # base .git mounted rw at the same absolute path
    assert f"source={repo / '.git'},target={repo / '.git'}" in joined
    assert load_state(repo, "vk-iso/test") == st


def test_up_uncommitted_profile_raises_actionable_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """super-fr#299 part 2: a profile written but NOT committed is absent from
    the worktree (cut from the committed tree). up() should explain that, not
    fail cryptically in `devcontainer up`."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path)  # committed README, no committed profile
    # Profile in the base working tree, UNCOMMITTED (as `scaffold --no-commit`
    # would leave it):
    d = repo / ".devcontainer" / "dev"
    d.mkdir(parents=True)
    (d / "devcontainer.json").write_text('{"image": "x"}\n')
    (repo / ".devcontainer" / "fr-profiles.yaml").write_text(
        "default: dev\nprofiles:\n  dev:\n    purpose: test\n"
    )
    runner = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)

    with pytest.raises(IsolationError) as ei:
        target.up(profile="dev", branch="feat/x")
    msg = str(ei.value)
    assert "not committed" in msg
    assert "fr init scaffold" in msg
    assert not runner.argv_for("devcontainer")  # never reached devcontainer up


def test_up_committed_profile_absent_on_old_branch_no_false_positive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pre-check must fire ONLY for a genuinely uncommitted profile. A
    profile committed on main but absent on an older target branch is a
    different situation — don't misreport it as 'not committed'."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path)  # README committed on main (C0)
    subprocess.run(["git", "-C", str(repo), "branch", "old"], check=True)  # old @ C0
    # Commit the profile on main (C1) — clean working tree afterwards:
    d = repo / ".devcontainer" / "dev"
    d.mkdir(parents=True)
    (d / "devcontainer.json").write_text('{"image": "x"}\n')
    (repo / ".devcontainer" / "fr-profiles.yaml").write_text(
        "default: dev\nprofiles:\n  dev:\n    purpose: test\n"
    )
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "p"],
        check=True,
    )
    runner = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    # up on the OLD branch (lacks the profile, but it IS committed on main):
    target.up(profile="dev", branch="old")
    assert runner.argv_for("devcontainer")  # reached devcontainer up — no false error


def test_up_from_worktree_mounts_main_git_and_keys_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#292 headline path: up() launched from a linked worktree mounts the
    MAIN .git (a real dir), persists main-keyed state, and buckets the spawned
    worktree under the real repo name — so teardown survives the launch wt."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")
    wt = add_worktree(repo, "feat/z")
    runner = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(wt, runner=runner)
    st = target.up(profile=None, branch="iso/work")
    (up,) = runner.argv_for("devcontainer")
    main_git = repo.resolve() / ".git"
    assert f"source={main_git},target={main_git}" in " ".join(up)
    assert st.repo_root == repo.resolve()
    assert str(st.worktree).startswith(
        str(tmp_path / "home" / ".cache" / "fr" / "worktrees" / repo.name)
    )


def test_up_mount_resolves_common_git_even_without_normalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#292 belt-and-suspenders: the .git mount resolves the shared common dir
    directly, so it stays correct even if repo_root somehow points at a
    worktree (a gitfile) — independent of __init__ normalization."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")
    wt = add_worktree(repo, "feat/z")
    runner = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    target.repo_root = wt.resolve()  # bypass __init__ normalization
    target.up(profile=None, branch="iso/work")
    (up,) = runner.argv_for("devcontainer")
    main_git = repo.resolve() / ".git"
    assert f"source={main_git},target={main_git}" in " ".join(up)


def test_up_follows_legacy_vk_mount_and_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Unmigrated repo: committed devcontainer.json still mounts the vk path —
    up() ensures THAT file (the one docker will read) and warns."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(
        tmp_path,
        ["dev"],
        default="dev",
        env_file_mount="${localEnv:HOME}/.config/vk/secrets/repo/dev.env",
    )
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner())
    target.up(profile=None, branch="vk-iso/test")
    env = tmp_path / "home" / ".config" / "vk" / "secrets" / "repo" / "dev.env"
    assert env.is_file()
    assert "legacy" in capsys.readouterr().err


def test_up_no_env_file_mount_creates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")  # no runArgs in fixture
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner())
    target.up(profile=None, branch="vk-iso/test")
    assert not (tmp_path / "home" / ".config").exists()


def test_up_outside_repo_exits_with_isolation_error(tmp_path: Path) -> None:
    with pytest.raises(IsolationError, match="git repo"):
        LocalWorktreeDevcontainerTarget(tmp_path / "nowhere", runner=FakeRunner()).up(None, "b")


def test_up_devcontainer_failure_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner(fail_on="devcontainer"))
    with pytest.raises(IsolationError, match="devcontainer up"):
        target.up(None, "vk-iso/test")


# ---------- cold-start base resolution (#322) ----------


def _fetched(git_calls: list[list[str]]) -> bool:
    return any(c[:2] == ["git", "fetch"] for c in git_calls)


def test_up_new_branch_bases_on_origin_default_not_local_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#322 headline: a NEW cold-start branch is cut from freshly-fetched
    origin/<default>, NOT the base repo's (feature-parked) HEAD."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path, ["dev"], default="dev")
    stray = _commit_stray_feature_branch(repo)  # base HEAD now != main
    runner = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)

    target.up(profile="dev", branch="feat/x")

    assert _is_ancestor(repo, "origin/main", "feat/x")  # cut from origin/main
    assert not _is_ancestor(repo, stray, "feat/x")  # stray did NOT ride in
    assert _fetched(runner.git_calls)  # the default path fetched


def test_up_base_head_forks_from_current_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--base HEAD opts back into 'fork from current checkout' (stacking)."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path, ["dev"], default="dev")
    stray = _commit_stray_feature_branch(repo)
    runner = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)

    target.up(profile="dev", branch="feat/x", base="HEAD")

    assert _is_ancestor(repo, stray, "feat/x")  # forked from current HEAD
    assert not _fetched(runner.git_calls)  # explicit base → no fetch


def test_up_explicit_base_ref_used_verbatim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--base <ref> uses the named ref as-is — no fetch, no default resolution."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path, ["dev"], default="dev")
    v0 = _git_out(repo, "rev-parse", "HEAD")
    _git_out(repo, "tag", "v0")
    (repo / "more.txt").write_text("x\n")
    _git_out(repo, "add", "-A")
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            "more",
        ],
        check=True,
    )
    runner = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)

    target.up(profile="dev", branch="feat/x", base="v0")

    assert _git_out(repo, "rev-parse", "feat/x") == v0
    assert not _fetched(runner.git_calls)


def test_up_no_fetch_uses_local_tracking_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--no-fetch bases on the LOCAL origin/<default> tracking ref, no network."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path, ["dev"], default="dev")
    _git_out(repo, "fetch", "origin")  # tracking ref present, set up out-of-band
    stray = _commit_stray_feature_branch(repo)
    runner = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)

    target.up(profile="dev", branch="feat/x", no_fetch=True)

    assert _is_ancestor(repo, "origin/main", "feat/x")
    assert not _is_ancestor(repo, stray, "feat/x")
    assert not _fetched(runner.git_calls)  # --no-fetch issued no fetch


def test_up_no_fetch_missing_tracking_ref_falls_back_to_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path, ["dev"], default="dev")
    subprocess.run(["git", "-C", str(repo), "update-ref", "-d", "refs/remotes/origin/main"])
    stray = _commit_stray_feature_branch(repo)
    runner = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)

    target.up(profile="dev", branch="feat/x", no_fetch=True)

    assert _is_ancestor(repo, stray, "feat/x")  # no tracking ref → local HEAD
    assert "WARNING" in capsys.readouterr().err


def test_up_no_origin_falls_back_to_head_with_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")  # NO origin remote
    stray = _commit_stray_feature_branch(repo)
    runner = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)

    target.up(profile="dev", branch="feat/x")  # never aborts

    assert _is_ancestor(repo, stray, "feat/x")  # local HEAD fallback
    assert "WARNING" in capsys.readouterr().err
    assert not _fetched(runner.git_calls)  # no origin → fetch never attempted


def test_up_fetch_failure_falls_back_to_head_with_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", str(tmp_path / "does-not-exist.git")],
        check=True,
    )
    stray = _commit_stray_feature_branch(repo)
    runner = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)

    target.up(profile="dev", branch="feat/x")  # fetch fails → graceful fallback

    assert _is_ancestor(repo, stray, "feat/x")
    assert "WARNING" in capsys.readouterr().err


def test_resolve_default_branch_symbolic_ref(tmp_path: Path) -> None:
    repo, _origin = make_repo_with_origin(tmp_path)
    subprocess.run(["git", "-C", str(repo), "fetch", "origin"], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "set-head", "origin", "--auto"], check=True)
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner())
    assert target._resolve_default_branch() == "main"


def test_resolve_default_branch_gh_fallback(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)  # no origin → symbolic-ref fails
    runner = FakeRunner(stdout={"gh": "trunk\n"})
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    assert target._resolve_default_branch() == "trunk"


def test_resolve_default_branch_main_fallback(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)  # no origin, gh yields nothing
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner())
    assert target._resolve_default_branch() == "main"


def test_up_reuse_existing_worktree_never_fetches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path, ["dev"], default="dev")
    runner = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    target.up(profile="dev", branch="feat/x")  # first up creates + fetches
    runner.git_calls.clear()

    target.up(profile="dev", branch="feat/x")  # reuse: worktree already exists

    assert not _fetched(runner.git_calls)  # corner case #1: reuse never rebases


def test_up_reuse_existing_branch_no_fetch_no_rebase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path, ["dev"], default="dev")
    branch_tip = _git_out(repo, "rev-parse", "HEAD")
    subprocess.run(["git", "-C", str(repo), "branch", "feat/pre"], check=True)
    runner = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)

    target.up(profile="dev", branch="feat/pre")  # existing branch → checkout as-is

    assert _git_out(repo, "rev-parse", "feat/pre") == branch_tip  # tip unchanged
    assert not _fetched(runner.git_calls)


# ---------- target.exec / status / down ----------


def _upped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **runner_kw):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")
    runner = FakeRunner(**runner_kw)
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    st = target.up(None, "vk-iso/test")
    runner.calls.clear()
    return repo, runner, target, st


def test_exec_passthrough(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, runner, target, st = _upped(tmp_path, monkeypatch)
    rc = target.exec(st, ["pytest", "-q", "--no-cov"])
    assert rc == 0
    (call,) = runner.argv_for("devcontainer")
    assert call[1] == "exec"
    assert call[-3:] == ["pytest", "-q", "--no-cov"]
    assert runner.captures[-1] is False, "exec must inherit stdio (stream output live)"


def test_status_reports_worktree_container_pr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, runner, target, st = _upped(
        tmp_path,
        monkeypatch,
        stdout={"docker": "abc123 running\n", "gh": '{"state": "OPEN", "url": "u"}'},
    )
    s = target.status(st)
    assert s["worktree"] == str(st.worktree) and s["worktree_exists"] is True
    assert s["container"] == "running"
    assert s["pr"] == {"state": "OPEN", "url": "u"}


def test_down_refuses_open_pr_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, runner, target, st = _upped(
        tmp_path, monkeypatch, stdout={"gh": '{"state": "OPEN", "url": "u"}'}
    )
    with pytest.raises(IsolationError, match="open"):
        target.down(st, force=False)
    assert st.worktree.is_dir()  # untouched


def test_down_force_removes_worktree_and_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, runner, target, st = _upped(
        tmp_path,
        monkeypatch,
        stdout={"docker": "abc123 running\n", "gh": '{"state": "OPEN", "url": "u"}'},
    )
    target.down(st, force=True)
    assert not st.worktree.exists()
    assert load_state(repo, "vk-iso/test") is None
    stops = [c for c in runner.argv_for("docker") if c[1] in ("stop", "rm")]
    assert stops, "container should be stopped/removed"


def test_down_merged_pr_cleans_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, runner, target, st = _upped(
        tmp_path, monkeypatch, stdout={"gh": '{"state": "MERGED", "url": "u"}'}
    )
    target.down(st, force=False)
    assert not st.worktree.exists()


def test_up_twice_is_idempotent_on_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-running up() must not fail on the existing worktree (re-entrant runs)."""
    repo, runner, target, st1 = _upped(tmp_path, monkeypatch)
    st2 = target.up(None, "vk-iso/test")
    assert st2.worktree == st1.worktree
    assert st2.worktree.is_dir()
    # second up still (re)starts the devcontainer but adds no second worktree
    (up_call,) = runner.argv_for("devcontainer")
    assert up_call[1] == "up"


def test_pr_malformed_gh_json_is_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, runner, target, st = _upped(tmp_path, monkeypatch, stdout={"gh": "not-json {"})
    assert target.status(st)["pr"] is None


# ---------- merge-config verification (#320 review follow-up) ----------
# The content check must be correct across EVERY merge strategy (squash,
# merge-commit, rebase) — these hit real throwaway repos, base_ref is a local
# ref so no remote/network is needed.


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _commit(repo: Path, path: str, content: str, msg: str) -> None:
    (repo / path).write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg)


def _squash_merge(repo: Path, branch: str, msg: str) -> None:
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "--squash", branch)
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg)


def _state(repo: Path, branch: str) -> IsolationState:
    return IsolationState(
        repo_root=repo, branch=branch, worktree=repo, profile="dev", created_at="t"
    )


def test_branch_changes_present_squash(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "fix.py", "fixed\n", "fix")
    _squash_merge(repo, "feature", "squash fix")
    res = branch_changes_present(subprocess_runner, repo, "feature", "main")
    assert res.changes_present
    assert res.missing == []


def test_branch_changes_present_merge_commit(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "fix.py", "fixed\n", "fix")
    _git(repo, "checkout", "-q", "main")
    _git(
        repo, "-c", "user.email=t@t", "-c", "user.name=t", "merge", "--no-ff", "-m", "m", "feature"
    )
    res = branch_changes_present(subprocess_runner, repo, "feature", "main")
    assert res.changes_present


def test_branch_changes_present_rebase(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "fix.py", "fixed\n", "fix")
    sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "feature"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _git(repo, "checkout", "-q", "main")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "cherry-pick", sha)
    res = branch_changes_present(subprocess_runner, repo, "feature", "main")
    assert res.changes_present


def test_branch_changes_present_orphan(tmp_path: Path) -> None:
    # fix1 squash-merged; fix2 pushed to the branch AFTER the merge (#320).
    repo = make_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "fix1.py", "one\n", "fix1")
    _squash_merge(repo, "feature", "squash fix1")
    _git(repo, "checkout", "-q", "feature")
    _commit(repo, "fix2.py", "two\n", "fix2 after merge")
    res = branch_changes_present(subprocess_runner, repo, "feature", "main")
    assert not res.changes_present
    assert "fix2.py" in res.missing
    assert "fix1.py" not in res.missing


def test_branch_changes_present_main_diverged_other_path(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "fix.py", "fixed\n", "fix")
    _squash_merge(repo, "feature", "squash fix")
    _commit(repo, "other.py", "unrelated\n", "other on main")  # main moves on a different file
    res = branch_changes_present(subprocess_runner, repo, "feature", "main")
    assert res.changes_present


def test_branch_changes_present_multi_file_squash(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    (repo / "a.py").write_text("a\n")
    (repo / "b.py").write_text("b\n")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "two files")
    _squash_merge(repo, "feature", "squash two files")
    res = branch_changes_present(subprocess_runner, repo, "feature", "main")
    assert res.changes_present
    assert res.missing == []


def test_branch_changes_present_deletion_squash(tmp_path: Path) -> None:
    # make_repo seeds README.md; the branch deletes it.
    repo = make_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _git(repo, "rm", "-q", "README.md")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "delete readme")
    _squash_merge(repo, "feature", "squash delete")
    res = branch_changes_present(subprocess_runner, repo, "feature", "main")
    assert res.changes_present


def test_branch_changes_present_multi_commit_rebase(tmp_path: Path) -> None:
    # GitHub rebase-merge replays ALL branch commits onto main; model with a
    # range cherry-pick of two commits.
    repo = make_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "a.py", "1\n", "c1")
    _commit(repo, "b.py", "2\n", "c2")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "cherry-pick", "main..feature")
    res = branch_changes_present(subprocess_runner, repo, "feature", "main")
    assert res.changes_present
    assert res.missing == []


def _with_origin(repo: Path) -> None:
    """Add a bare remote and push main so `git fetch origin main` succeeds —
    verify_merge requires a fresh fetch, so the verdict tests need a real one."""
    remote = repo.parent / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "origin", "main")


def test_verify_merge_verified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "fix.py", "fixed\n", "fix")
    _squash_merge(repo, "feature", "squash")
    _with_origin(repo)
    _git(repo, "checkout", "-q", "feature")
    target = LocalWorktreeDevcontainerTarget(repo, runner=subprocess_runner)
    monkeypatch.setattr(target, "_pr", lambda state: {"state": "MERGED", "url": "u"})
    res = target.verify_merge(_state(repo, "feature"), default_branch="main")
    assert res["verified"] is True
    assert res["changes_present"] is True
    assert res["fetched"] is True
    assert res["pr_state"] == "MERGED"


def test_verify_merge_orphan_not_verified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "fix1.py", "one\n", "fix1")
    _squash_merge(repo, "feature", "squash fix1")
    _with_origin(repo)
    _git(repo, "checkout", "-q", "feature")
    _commit(repo, "fix2.py", "two\n", "fix2 after merge")
    target = LocalWorktreeDevcontainerTarget(repo, runner=subprocess_runner)
    monkeypatch.setattr(target, "_pr", lambda state: {"state": "MERGED", "url": "u"})
    res = target.verify_merge(_state(repo, "feature"), default_branch="main")
    assert res["verified"] is False
    assert "fix2.py" in res["missing"]


def test_verify_merge_fetch_failure_not_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Content present + PR MERGED, but NO remote → fetch fails → NOT verified
    # (a stale origin/main must never green-light — the false-positive guard).
    repo = make_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "fix.py", "fixed\n", "fix")
    _squash_merge(repo, "feature", "squash")
    _git(repo, "update-ref", "refs/remotes/origin/main", "main")  # ref exists, but no remote
    _git(repo, "checkout", "-q", "feature")
    target = LocalWorktreeDevcontainerTarget(repo, runner=subprocess_runner)
    monkeypatch.setattr(target, "_pr", lambda state: {"state": "MERGED", "url": "u"})
    res = target.verify_merge(_state(repo, "feature"), default_branch="main")
    assert res["fetched"] is False
    assert res["changes_present"] is True
    assert res["verified"] is False


def test_verify_merge_unknown_pr_state_not_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # gh unavailable (pr_state None) must NOT pass — PR-MERGED is the tiebreak.
    repo = make_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "fix.py", "fixed\n", "fix")
    _squash_merge(repo, "feature", "squash")
    _with_origin(repo)
    _git(repo, "checkout", "-q", "feature")
    target = LocalWorktreeDevcontainerTarget(repo, runner=subprocess_runner)
    monkeypatch.setattr(target, "_pr", lambda state: None)
    res = target.verify_merge(_state(repo, "feature"), default_branch="main")
    assert res["changes_present"] is True
    assert res["fetched"] is True
    assert res["pr_state"] is None
    assert res["verified"] is False
