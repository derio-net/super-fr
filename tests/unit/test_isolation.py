"""fr isolation — Target protocol, state, profiles, and the local target.

All devcontainer/docker/gh calls go through the Runner seam; git calls hit
real throwaway repos (cheap, deterministic). Nothing here needs Docker.
"""

from __future__ import annotations

import json
import shutil
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
    """Records non-git argv; delegates git to the real binary.

    Stateful docker model (#354): a successful `docker rm <id>` records the id
    as removed, and subsequent `docker ps` output drops that id — so `down`'s
    post-condition re-query reflects reality. Fail the `rm` (`fail_on="rm"`) and
    the id survives → the re-query still sees it → `down` raises. This is what
    lets the same fixture exercise both the happy path and the transient-failure
    path without call-sequence stubbing.
    """

    def __init__(
        self,
        fail_on: str | None = None,
        stdout: dict[str, str] | None = None,
        docker_labels: list[tuple[str, str]] | None = None,
        pr_by_branch: dict[str, str] | None = None,
        docker_images: list[tuple[str, str]] | None = None,
        referenced_images: list[str] | None = None,
    ):
        self.calls: list[list[str]] = []
        self.git_calls: list[list[str]] = []
        self.captures: list[bool] = []
        self.fail_on = fail_on
        self.stdout = stdout or {}
        self.removed: set[str] = set()
        # gc host-wide discovery: (container_id, worktree_path) pairs the
        # `docker ps -a --filter label=... --format '{{.ID}}\t{{.Label ...}}'`
        # call returns (minus already-rm'd ids).
        self.docker_labels = docker_labels or []
        # gc classification: per-branch `gh pr view` JSON. A branch absent from
        # the map ⇒ gh returns nothing (no PR).
        self.pr_by_branch = pr_by_branch
        # gc image sweep: `docker images` listing (id, repo) and the set of
        # images referenced by a live container (`docker ps -a --format {{.Image}}`).
        self.docker_images = docker_images or []
        self.referenced_images = referenced_images or []

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
        if argv[0:2] == ["docker", "rm"] and rc == 0:
            self.removed.update(argv[2:])
        out = self.stdout.get(argv[0], "")
        if argv[0:2] == ["docker", "ps"]:
            if any(".Label" in a for a in argv):
                out = self._docker_labels_out()
            elif any(".Image" in a for a in argv):
                out = "".join(f"{ref}\n" for ref in self.referenced_images)
            else:
                out = self._ps_out()
        elif argv[0:2] == ["docker", "images"]:
            out = "".join(f"{i}\t{r}\n" for i, r in self.docker_images)
        elif argv[0:2] == ["docker", "inspect"]:
            out = self.stdout.get("docker_image", "")
        elif argv[0:3] == ["gh", "pr", "view"] and self.pr_by_branch is not None:
            body = self.pr_by_branch.get(argv[3], "")
            return subprocess.CompletedProcess(argv, 0 if body else 1, stdout=body, stderr="")
        return subprocess.CompletedProcess(argv, rc, stdout=out, stderr="")

    def _ps_out(self) -> str:
        """Per-state `docker ps` line, minus any container id already `rm`'d."""
        out = self.stdout.get("docker", "")
        first = out.split()[0] if out.split() else ""
        return "" if first in self.removed else out

    def _docker_labels_out(self) -> str:
        """gc discovery listing: `id\\tpath` per labelled container, minus rm'd."""
        return "".join(
            f"{cid}\t{path}\n" for cid, path in self.docker_labels if cid not in self.removed
        )

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


def test_up_logs_chosen_base_on_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The non-warning 'basing new branch …' line is informational → stdout
    (WARNING fallbacks go to stderr; this pins the split)."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path, ["dev"], default="dev")
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner())

    target.up(profile="dev", branch="feat/x")

    captured = capsys.readouterr()
    assert "basing new branch feat/x on origin/main (fetched)" in captured.out
    assert "WARNING" not in captured.err


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


def test_resolve_default_branch_gitlab_backend(tmp_path: Path) -> None:
    """Backend-aware fallback (docs/superpowers/specs/
    2026-07-09-multi-backend-git-host-adapters-design.md §8): a
    GitLab-backed repo (no symbolic-ref, no `gh`) resolves via
    `glab repo view -F json --jq .default_branch`."""
    repo = make_repo(tmp_path)  # no origin → symbolic-ref fails
    (repo / ".devcontainer").mkdir()
    (repo / ".devcontainer" / "fr-profiles.yaml").write_text(
        "backend: gitlab\nprofiles:\n  dev:\n    purpose: x\n"
    )
    runner = FakeRunner(stdout={"glab": "develop\n"})
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    assert target._resolve_default_branch() == "develop"
    glab_calls = runner.argv_for("glab")
    assert glab_calls and glab_calls[0][:2] == ["glab", "repo"]


def test_resolve_default_branch_gitea_backend(tmp_path: Path) -> None:
    """A Gitea-backed repo resolves via `tea repos ... --output json`
    (field name `default_branch` — confirmed against Gitea's live
    swagger spec, Repository.default_branch — but the CLI's own JSON
    shape is reconfirmed against a live tea in Phase 9's manual
    verification)."""
    repo = make_repo(tmp_path)
    (repo / ".devcontainer").mkdir()
    (repo / ".devcontainer" / "fr-profiles.yaml").write_text(
        "backend: gitea\nprofiles:\n  dev:\n    purpose: x\n"
    )
    runner = FakeRunner(stdout={"tea": '{"default_branch": "develop"}'})
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    assert target._resolve_default_branch() == "develop"
    tea_calls = runner.argv_for("tea")
    assert tea_calls and tea_calls[0][:1] == ["tea"]


def test_resolve_default_branch_gitlab_backend_falls_back_on_failure(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / ".devcontainer").mkdir()
    (repo / ".devcontainer" / "fr-profiles.yaml").write_text(
        "backend: gitlab\nprofiles:\n  dev:\n    purpose: x\n"
    )
    runner = FakeRunner()  # glab yields empty stdout → falls through to "main"
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    assert target._resolve_default_branch() == "main"


def test_pr_from_gitlab_backend(tmp_path: Path) -> None:
    """A GitLab-backed repo's `_pr_from` uses `glab mr view <branch>
    --output json` (a single-shot query, like gh's) — verified against
    glab's own `--help` (`glab mr view {<id> | <branch>}` accepts a bare
    branch name directly, unlike its `mr view <url>` case)."""
    repo = make_repo(tmp_path)
    (repo / ".devcontainer").mkdir()
    (repo / ".devcontainer" / "fr-profiles.yaml").write_text(
        "backend: gitlab\nprofiles:\n  dev:\n    purpose: x\n"
    )
    runner = FakeRunner(
        stdout={
            "glab": '{"state": "merged", "web_url": "https://gitlab.com/g/p/-/merge_requests/1"}'
        }
    )
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    result = target._pr_from(repo, "feat/x")
    assert result is not None
    assert result["state"] == "MERGED"
    assert result["url"] == "https://gitlab.com/g/p/-/merge_requests/1"


def test_pr_from_gitlab_backend_no_mr_returns_none(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / ".devcontainer").mkdir()
    (repo / ".devcontainer" / "fr-profiles.yaml").write_text(
        "backend: gitlab\nprofiles:\n  dev:\n    purpose: x\n"
    )
    runner = FakeRunner()  # empty stdout, rc=0 by default — no MR
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    assert target._pr_from(repo, "feat/x") is None


def test_pr_from_gitea_backend_list_and_filter_fallback(tmp_path: Path) -> None:
    """Gitea's CLI has no single-shot branch→PR query (unlike gh/glab) —
    verified during the multi-backend design's research (`tea pulls`
    only takes an index, not a branch). The adapter falls back to
    listing ALL PRs and matching `head.label` client-side. This is a
    real, bounded degradation vs. gh/glab's single-shot query, not a
    bug — documented in the design doc §8."""
    repo = make_repo(tmp_path)
    (repo / ".devcontainer").mkdir()
    (repo / ".devcontainer" / "fr-profiles.yaml").write_text(
        "backend: gitea\nprofiles:\n  dev:\n    purpose: x\n"
    )
    listing = (
        '[{"state": "open", "merged": false, "url": "https://gitea.example.com/o/r/pulls/1", '
        '"head": {"label": "other-branch"}}, '
        '{"state": "open", "merged": false, "url": "https://gitea.example.com/o/r/pulls/2", '
        '"head": {"label": "feat/x"}}]'
    )
    runner = FakeRunner(stdout={"tea": listing})
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    result = target._pr_from(repo, "feat/x")
    assert result is not None
    assert result["url"] == "https://gitea.example.com/o/r/pulls/2"
    assert result["state"] == "OPEN"


def test_pr_from_gitea_backend_merged_state(tmp_path: Path) -> None:
    """A merged Gitea PR coerces to the shared "MERGED" vocabulary
    (Gitea's `state` field alone would say "closed" — the separate
    `merged: true` boolean is what distinguishes it, per Gitea's own
    PullRequest schema, verified against its live swagger spec)."""
    repo = make_repo(tmp_path)
    (repo / ".devcontainer").mkdir()
    (repo / ".devcontainer" / "fr-profiles.yaml").write_text(
        "backend: gitea\nprofiles:\n  dev:\n    purpose: x\n"
    )
    listing = (
        '[{"state": "closed", "merged": true, "url": "https://gitea.example.com/o/r/pulls/2", '
        '"head": {"label": "feat/x"}}]'
    )
    runner = FakeRunner(stdout={"tea": listing})
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    result = target._pr_from(repo, "feat/x")
    assert result is not None
    assert result["state"] == "MERGED"


def test_pr_from_gitea_backend_no_matching_branch_returns_none(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / ".devcontainer").mkdir()
    (repo / ".devcontainer" / "fr-profiles.yaml").write_text(
        "backend: gitea\nprofiles:\n  dev:\n    purpose: x\n"
    )
    listing = '[{"state": "open", "merged": false, "url": "u", "head": {"label": "other-branch"}}]'
    runner = FakeRunner(stdout={"tea": listing})
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    assert target._pr_from(repo, "feat/x") is None


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


def _orphan_worktree(repo: Path, st: IsolationState, *, keep_dir: bool) -> None:
    """Remove the worktree from git out-of-band. keep_dir=True leaves a stray
    directory at the path (so real `git worktree remove` fails while the dir
    still exists); keep_dir=False leaves nothing behind."""
    shutil.rmtree(st.worktree)
    subprocess.run(["git", "-C", str(repo), "worktree", "prune"], check=True)
    if keep_dir:
        st.worktree.mkdir(parents=True)


def test_down_raises_when_container_survives_stop_rm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A transient docker failure: `docker rm` fails, so the re-query still sees
    # the container. down() must raise and LEAVE state + marker + worktree in
    # place, so `fr isolation status` still sees the workspace.
    repo, runner, target, st = _upped(
        tmp_path,
        monkeypatch,
        fail_on="rm",
        stdout={"docker": "abc123 running\n", "gh": '{"state": "MERGED", "url": "u"}'},
    )
    with pytest.raises(IsolationError, match="still present"):
        target.down(st, force=False)
    assert load_state(repo, "vk-iso/test") is not None, "state must survive"
    assert (st.worktree / ".fr-isolation").exists(), "marker must survive"
    assert st.worktree.is_dir(), "worktree must be untouched"


def test_down_raises_when_worktree_remove_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Container tears down cleanly, but the worktree remove fails while the dir
    # still exists (a stray dir git no longer tracks) → raise, keep state.
    repo, runner, target, st = _upped(
        tmp_path,
        monkeypatch,
        stdout={"docker": "abc123 running\n", "gh": '{"state": "MERGED", "url": "u"}'},
    )
    _orphan_worktree(repo, st, keep_dir=True)
    with pytest.raises(IsolationError, match="worktree remove failed"):
        target.down(st, force=False)
    assert load_state(repo, "vk-iso/test") is not None, "state must survive a worktree failure"


def test_down_completes_when_worktree_already_gone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Worktree removed out of band: `git worktree remove` fails but the dir is
    # gone, so the post-condition holds → down completes and deletes state.
    repo, runner, target, st = _upped(
        tmp_path, monkeypatch, stdout={"gh": '{"state": "MERGED", "url": "u"}'}
    )
    _orphan_worktree(repo, st, keep_dir=False)
    target.down(st, force=False)
    assert load_state(repo, "vk-iso/test") is None


def test_down_force_still_verifies_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # --force bypasses the open-PR guard, NOT the container-gone verification.
    repo, runner, target, st = _upped(
        tmp_path,
        monkeypatch,
        fail_on="rm",
        stdout={"docker": "abc123 running\n", "gh": '{"state": "OPEN", "url": "u"}'},
    )
    with pytest.raises(IsolationError, match="still present"):
        target.down(st, force=True)
    assert load_state(repo, "vk-iso/test") is not None


def test_down_raises_when_docker_query_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `docker ps` ITSELF failing (daemon unreachable) must not be read as "no
    # container" — down must raise and keep state, or it re-opens the #354 leak
    # (delete state while a container survives once docker recovers).
    repo, runner, target, st = _upped(
        tmp_path,
        monkeypatch,
        fail_on="ps",
        stdout={"docker": "abc123 running\n", "gh": '{"state": "MERGED", "url": "u"}'},
    )
    with pytest.raises(IsolationError, match="docker ps failed"):
        target.down(st, force=False)
    assert load_state(repo, "vk-iso/test") is not None
    assert not any(c[1] in ("stop", "rm") for c in runner.argv_for("docker"))


def test_down_reclaims_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, runner, target, st = _upped(
        tmp_path,
        monkeypatch,
        stdout={
            "docker": "abc123 running\n",
            "docker_image": "vsc-img-sha\n",
            "gh": '{"state": "MERGED", "url": "u"}',
        },
    )
    target.down(st, force=False)
    assert not st.worktree.exists()
    assert ["docker", "rmi", "vsc-img-sha"] in runner.argv_for("docker")


def test_down_rmi_failure_is_non_fatal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A shared / in-use image failing `docker rmi` must NOT fail a teardown
    # whose container is already gone.
    repo, runner, target, st = _upped(
        tmp_path,
        monkeypatch,
        fail_on="rmi",
        stdout={
            "docker": "abc123 running\n",
            "docker_image": "vsc-img-sha\n",
            "gh": '{"state": "MERGED", "url": "u"}',
        },
    )
    target.down(st, force=False)  # no raise
    assert load_state(repo, "vk-iso/test") is None


def test_down_no_container_skips_rmi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, runner, target, st = _upped(
        tmp_path, monkeypatch, stdout={"gh": '{"state": "MERGED", "url": "u"}'}
    )
    target.down(st, force=False)
    assert not any(c[0:2] == ["docker", "rmi"] for c in runner.argv_for("docker"))


# ---------- target.gc — host-wide reconciliation (#354 Task B) ----------


def _gc_env(tmp_path, monkeypatch, **runner_kw):
    """A repo + runner sharing one HOME cache, plus an `up(branch)` helper that
    returns the created worktree path. gc discovers across the whole HOME."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")
    runner = FakeRunner(**runner_kw)
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)

    def up(branch: str) -> Path:
        st = target.up(None, branch)
        return st.worktree

    return repo, runner, target, up


def test_gc_discovers_label_and_worktree_union(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, runner, target, up = _gc_env(tmp_path, monkeypatch)
    wt = up("feat/a")
    gone = tmp_path / "home" / ".cache" / "fr" / "worktrees" / "other" / "gone"
    runner.docker_labels = [("cA", str(wt)), ("cOrph", str(gone))]
    recs = {r.worktree: r for r in target._discover_workspaces()}
    assert set(recs) == {wt, gone}
    assert recs[wt].container_id == "cA"
    assert recs[wt].state is not None and recs[wt].state.branch == "feat/a"
    assert recs[gone].container_id == "cOrph" and recs[gone].state is None


def test_gc_classifies_and_reaps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, runner, target, up = _gc_env(
        tmp_path,
        monkeypatch,
        pr_by_branch={
            "feat/merged": '{"state": "MERGED", "url": "u"}',
            "feat/open": '{"state": "OPEN", "url": "u"}',
            # feat/nopr intentionally absent → no PR
        },
    )
    wt_m, wt_o, wt_n = up("feat/merged"), up("feat/open"), up("feat/nopr")
    gone = tmp_path / "home" / ".cache" / "fr" / "worktrees" / "other" / "gone"
    nostate = tmp_path / "home" / ".cache" / "fr" / "worktrees" / "x" / "nostate"
    nostate.mkdir(parents=True)
    runner.docker_labels = [("cOrph", str(gone))]

    by_wt = {a.worktree: a for a in target.gc()}
    assert by_wt[str(wt_m)].action == "reaped" and not wt_m.exists()
    assert load_state(repo, "feat/merged") is None
    assert by_wt[str(wt_o)].verdict == "open" and by_wt[str(wt_o)].action == "skipped"
    assert wt_o.is_dir()
    assert by_wt[str(wt_n)].verdict == "no-pr" and by_wt[str(wt_n)].action == "warned"
    assert wt_n.is_dir()
    assert by_wt[str(gone)].action == "reaped"
    assert ["docker", "rm", "cOrph"] in runner.argv_for("docker")
    assert by_wt[str(nostate)].verdict == "no-state" and by_wt[str(nostate)].action == "warned"


def test_gc_one_failure_does_not_abort_sweep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two merged workspaces whose container survives `docker rm` (fail_on='rm')
    # → both down() raise; the sweep records both and does not abort.
    repo, runner, target, up = _gc_env(
        tmp_path,
        monkeypatch,
        fail_on="rm",
        stdout={"docker": "cX running\n"},
        pr_by_branch={
            "feat/m1": '{"state": "MERGED", "url": "u"}',
            "feat/m2": '{"state": "MERGED", "url": "u"}',
        },
    )
    up("feat/m1")
    up("feat/m2")
    actions = target.gc()
    reap_failed = [a for a in actions if a.verdict == "merged"]
    assert len(reap_failed) == 2
    assert all(a.action == "reap-failed" for a in reap_failed)


def test_gc_dry_run_mutates_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, runner, target, up = _gc_env(
        tmp_path,
        monkeypatch,
        pr_by_branch={"feat/merged": '{"state": "MERGED", "url": "u"}'},
    )
    wt = up("feat/merged")
    (action,) = [a for a in target.gc(dry_run=True) if a.branch == "feat/merged"]
    assert action.action == "would-reap"
    assert wt.is_dir() and load_state(repo, "feat/merged") is not None
    assert not any(c[0:2] == ["docker", "rm"] for c in runner.argv_for("docker"))


def test_gc_merged_reap_unexpected_error_does_not_abort_sweep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An UNEXPECTED error (not IsolationError) from a sibling down() must be
    # caught per-workspace, not abort the whole host-wide sweep.
    repo, runner, target, up = _gc_env(
        tmp_path,
        monkeypatch,
        pr_by_branch={
            "feat/m": '{"state": "MERGED", "url": "u"}',
            "feat/o": '{"state": "OPEN", "url": "u"}',
        },
    )
    up("feat/m")
    up("feat/o")

    def boom(self, state, force=False):  # noqa: ANN001, ANN202
        raise RuntimeError("unexpected teardown failure")

    monkeypatch.setattr(LocalWorktreeDevcontainerTarget, "down", boom)
    by_branch = {a.branch: a for a in target.gc()}
    assert by_branch["feat/m"].action == "reap-failed"
    assert by_branch["feat/o"].action == "skipped"  # sweep continued past the failure


def test_gc_corrupt_state_does_not_abort_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.isolation.types import state_path

    repo, runner, target, up = _gc_env(tmp_path, monkeypatch)
    wt = up("feat/a")
    state_path(repo, "feat/a").write_text("{ not valid json")  # corrupt
    recs = target._discover_workspaces()  # must not raise
    rec = next(r for r in recs if r.worktree == wt)
    assert rec.state is None  # degrades to no-state (warned, never blindly reaped)


def test_gc_sweeps_dangling_vsc_images(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # vsc-a is referenced by a live container (keep); vsc-b is dangling (rmi);
    # ubuntu is not a devcontainer image (ignore).
    repo, runner, target, up = _gc_env(
        tmp_path,
        monkeypatch,
        docker_images=[("img-a", "vsc-a"), ("img-b", "vsc-b"), ("img-u", "ubuntu")],
        referenced_images=["img-a"],
    )
    images = [a for a in target.gc() if a.verdict == "dangling-image"]
    assert [a.detail for a in images] == ["img-b"]
    assert ["docker", "rmi", "img-b"] in runner.argv_for("docker")
    assert not any(c == ["docker", "rmi", "img-a"] for c in runner.argv_for("docker"))
    assert not any(c == ["docker", "rmi", "img-u"] for c in runner.argv_for("docker"))


def test_gc_image_rmi_failure_is_non_fatal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, runner, target, up = _gc_env(
        tmp_path,
        monkeypatch,
        fail_on="rmi",
        docker_images=[("img-b", "vsc-b")],
    )
    (img,) = [a for a in target.gc() if a.verdict == "dangling-image"]  # no raise
    assert img.action == "reap-failed"


# ---------- opportunistic gc spawn + flock (#354 Task B) ----------


def _spawn_target(tmp_path, monkeypatch, spawner, **runner_kw):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")
    runner = FakeRunner(**runner_kw)
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner, gc_spawner=spawner)
    return repo, runner, target


def test_up_spawns_background_gc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spawns: list[int] = []
    _, _, target = _spawn_target(tmp_path, monkeypatch, lambda: spawns.append(1))
    target.up(None, "feat/a")
    assert spawns == [1], "up() fires exactly one background gc after its work"


def test_down_spawns_background_gc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spawns: list[int] = []
    repo, runner, target = _spawn_target(
        tmp_path, monkeypatch, lambda: spawns.append(1), stdout={"gh": '{"state": "MERGED"}'}
    )
    st = target.up(None, "feat/a")
    spawns.clear()
    target.down(st, force=False)
    assert spawns == [1], "down() fires exactly one background gc after teardown"


def test_spawn_failure_does_not_break_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise RuntimeError("no fork today")

    _, _, target = _spawn_target(tmp_path, monkeypatch, boom)
    st = target.up(None, "feat/a")  # must not raise
    assert st.worktree.is_dir()


def test_default_target_does_not_spawn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The library default spawner is a no-op — a directly-constructed Target
    # (as in tests, and gc's own sibling teardowns) never forks a real sweep.
    from fr.isolation.local import _noop_gc_spawn

    target = LocalWorktreeDevcontainerTarget(make_repo(tmp_path, ["dev"], default="dev"))
    assert target._gc_spawner is _noop_gc_spawn


def test_gc_second_concurrent_sweep_noops(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, runner, target, up = _gc_env(
        tmp_path,
        monkeypatch,
        pr_by_branch={"feat/merged": '{"state": "MERGED", "url": "u"}'},
    )
    up("feat/merged")
    held = target._acquire_gc_lock()  # simulate a concurrent sweep holding the lock
    try:
        assert target.gc() == [], "a second concurrent sweep short-circuits"
        assert not any(c[0:2] == ["docker", "rm"] for c in runner.argv_for("docker"))
    finally:
        held.close()


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


# ---------- .fr-isolation marker lifecycle (#328 Task 3) ----------


def _exclude_lines(repo: Path) -> list[str]:
    exclude = repo / ".git" / "info" / "exclude"
    return exclude.read_text().splitlines() if exclude.is_file() else []


def test_up_writes_isolation_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner())
    st = target.up(profile=None, branch="feat/x")

    marker = st.worktree / ".fr-isolation"
    assert marker.is_file()
    data = json.loads(marker.read_text())
    assert data["toplevel"] == str(st.worktree.resolve())
    assert data["branch"] == "feat/x"
    assert data["mode"] == "worktree"
    assert isinstance(data["created_at"], str) and data["created_at"]


def test_up_adds_marker_to_info_exclude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner())
    target.up(profile=None, branch="feat/x")
    assert ".fr-isolation" in _exclude_lines(repo)


def test_up_marker_exclude_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner())
    st = target.up(profile=None, branch="feat/x")
    # Re-writing the marker must not duplicate the exclude line.
    target._write_isolation_marker(st.worktree, "feat/x")
    assert _exclude_lines(repo).count(".fr-isolation") == 1


def test_remove_isolation_marker_unit(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner())
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".fr-isolation").write_text("{}\n")
    target._remove_isolation_marker(wt)
    assert not (wt / ".fr-isolation").exists()
    target._remove_isolation_marker(wt)  # idempotent — no error when absent


def test_down_removes_isolation_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner())
    st = target.up(profile=None, branch="feat/x")
    assert (st.worktree / ".fr-isolation").is_file()

    removed: list[Path] = []
    orig = target._remove_isolation_marker
    monkeypatch.setattr(
        target,
        "_remove_isolation_marker",
        lambda wt: (removed.append(wt), orig(wt))[1],
    )
    target.down(st, force=True)
    assert removed == [st.worktree]  # down retires the marker


class TestClearRepoSentinels:
    """#341 Task 2A: clear_repo_sentinels owns the Python side of the sentinel
    contract shared with fr-pipeline-sentinel.sh (writer) and
    fr-isolation-guard.sh (reader): $FR_SENTINEL_DIR/<session>.json files each
    carrying {"repo_root": ...}. `fr isolation down --all` uses it to drop
    session state explicitly."""

    def test_removes_only_matching_repo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from fr.isolation.types import clear_repo_sentinels

        sdir = tmp_path / "sentinels"
        sdir.mkdir()
        repo = tmp_path / "repo"
        repo.mkdir()
        other = tmp_path / "other"
        other.mkdir()
        monkeypatch.setenv("FR_SENTINEL_DIR", str(sdir))
        (sdir / "s1.json").write_text(json.dumps({"repo_root": str(repo)}))
        (sdir / "s2.json").write_text(json.dumps({"repo_root": str(other)}))
        (sdir / "bad.json").write_text("{ not json")

        n = clear_repo_sentinels(repo)

        assert n == 1
        assert not (sdir / "s1.json").exists()
        assert (sdir / "s2.json").exists(), "foreign-repo sentinel untouched"
        assert (sdir / "bad.json").exists(), "malformed sentinel skipped, not removed"

    def test_absent_dir_returns_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from fr.isolation.types import clear_repo_sentinels

        monkeypatch.setenv("FR_SENTINEL_DIR", str(tmp_path / "nope"))
        assert clear_repo_sentinels(tmp_path / "repo") == 0


# ---------- target.restart / target.stats (#341 Task 3) ----------


def _target_state(tmp_path: Path, runner: FakeRunner) -> tuple:
    repo = make_repo(tmp_path, ["dev"], default="dev")
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    st = IsolationState(
        repo_root=repo,
        branch="feat/x",
        worktree=tmp_path / "wt",
        profile="dev",
        created_at="2026-07-03T00:00:00Z",
    )
    return target, st


class TestRestart:
    def test_graceful_restart(self, tmp_path: Path) -> None:
        runner = FakeRunner(stdout={"docker": "cid1 running"})
        target, st = _target_state(tmp_path, runner)
        target.restart(st)
        restarts = [c for c in runner.argv_for("docker") if c[1:2] == ["restart"]]
        assert restarts == [["docker", "restart", "cid1"]]

    def test_force_restart_uses_time_zero(self, tmp_path: Path) -> None:
        runner = FakeRunner(stdout={"docker": "cid1 running"})
        target, st = _target_state(tmp_path, runner)
        target.restart(st, force=True)
        restarts = [c for c in runner.argv_for("docker") if c[1:2] == ["restart"]]
        assert restarts == [["docker", "restart", "--time=0", "cid1"]]

    def test_no_container_errors(self, tmp_path: Path) -> None:
        runner = FakeRunner(stdout={})  # docker ps → "" → no container
        target, st = _target_state(tmp_path, runner)
        with pytest.raises(IsolationError, match="nothing to restart"):
            target.restart(st)

    def test_failure_suggests_force(self, tmp_path: Path) -> None:
        runner = FakeRunner(fail_on="restart", stdout={"docker": "cid1 running"})
        target, st = _target_state(tmp_path, runner)
        with pytest.raises(IsolationError, match="--force"):
            target.restart(st)


class _DockerRunner:
    """Runner distinguishing `docker ps` from `docker stats` (FakeRunner keys
    stdout by argv[0] only, so it can't give the two docker calls different
    output). git hits the real binary."""

    def __init__(self, ps: str = "cid running", stats: str = "", stats_rc: int = 0):
        self.ps = ps
        self.stats = stats
        self.stats_rc = stats_rc
        self.calls: list[list[str]] = []

    def __call__(self, argv, cwd=None, check=False, capture=True):
        if argv[0] == "git":
            return subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
        self.calls.append(list(argv))
        if argv[:2] == ["docker", "ps"]:
            return subprocess.CompletedProcess(argv, 0, stdout=self.ps, stderr="")
        if argv[:2] == ["docker", "stats"]:
            return subprocess.CompletedProcess(argv, self.stats_rc, stdout=self.stats, stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")


class TestStats:
    def _target_state(self, tmp_path: Path, runner) -> tuple:
        repo = make_repo(tmp_path, ["dev"], default="dev")
        target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
        st = IsolationState(
            repo_root=repo,
            branch="feat/x",
            worktree=tmp_path / "wt",
            profile="dev",
            created_at="2026-07-03T00:00:00Z",
        )
        return target, st

    def test_running_container_parses_pipe_row(self, tmp_path: Path) -> None:
        r = _DockerRunner(ps="cid running", stats="12.5%|1.2GiB / 4GiB|30.0%")
        target, st = self._target_state(tmp_path, r)
        assert target.stats(st) == {"cpu": "12.5%", "mem": "1.2GiB / 4GiB", "mem_perc": "30.0%"}
        # id + state come from ONE `docker ps`, not two (state check + id lookup).
        assert len([c for c in r.calls if c[:2] == ["docker", "ps"]]) == 1

    def test_exited_container_returns_none_without_stats_call(self, tmp_path: Path) -> None:
        r = _DockerRunner(ps="cid exited")
        target, st = self._target_state(tmp_path, r)
        assert target.stats(st) is None
        assert not any(c[:2] == ["docker", "stats"] for c in r.calls)

    def test_no_container_returns_none(self, tmp_path: Path) -> None:
        r = _DockerRunner(ps="")
        target, st = self._target_state(tmp_path, r)
        assert target.stats(st) is None

    def test_stats_command_failure_returns_none(self, tmp_path: Path) -> None:
        r = _DockerRunner(ps="cid running", stats="", stats_rc=1)
        target, st = self._target_state(tmp_path, r)
        assert target.stats(st) is None
