"""The scoped git answer cache (spec 2026-11-19-local-suite-cost R1, §3.A).

`fr.git.remote_name` and `fr.git.remote_default_ref` answer a repeated question
from a cache only inside `git_cache.scope()` (which `fr.cli`'s root group opens),
only while a fingerprint built from `os.stat` alone is unchanged, and never for a
repository the cache cannot fingerprint.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fr import git_cache
from fr.git import GitRefusal, GitUnavailableError, remote_default_ref, remote_name


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "T")
    (path / "f.txt").write_text("x\n")
    _git(path, "add", "f.txt")
    _git(path, "commit", "-qm", "init")
    return path


def _with_origin(tmp_path: Path) -> tuple[Path, Path]:
    """A checkout whose `origin` is a bare repo holding `main`; nothing fetched yet."""
    origin = tmp_path / "origin.git"
    seed = _repo(tmp_path / "seed")
    _git(tmp_path, "clone", "-q", "--bare", str(seed), str(origin))
    work = _repo(tmp_path / "work")
    _git(work, "remote", "add", "origin", str(origin))
    return work, origin


class GitStarts:
    """Counts git processes started through `subprocess.run` (the one seam fr uses)."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    @property
    def count(self) -> int:
        return len(self.calls)


@pytest.fixture
def git_starts(monkeypatch: pytest.MonkeyPatch) -> Iterator[GitStarts]:
    counter = GitStarts()
    real = subprocess.run

    def spy(args, *a, **kw):  # type: ignore[no-untyped-def]
        argv = [str(x) for x in args] if isinstance(args, (list, tuple)) else [str(args)]
        if argv and Path(argv[0]).name == "git":
            counter.calls.append(argv)
        return real(args, *a, **kw)

    monkeypatch.setattr(subprocess, "run", spy)
    yield counter


# --- the scope ---------------------------------------------------------------------


def test_outside_any_scope_there_is_no_cache() -> None:
    assert git_cache.active() is None


def test_a_scope_holds_an_entry_and_closes_with_it() -> None:
    with git_cache.scope():
        cache = git_cache.active()
        assert cache is not None
        cache[("k",)] = "v"
        assert git_cache.active() == {("k",): "v"}
    assert git_cache.active() is None


def test_scopes_nest_without_sharing_or_leaking() -> None:
    with git_cache.scope():
        outer = git_cache.active()
        assert outer is not None
        outer["a"] = 1
        with git_cache.scope():
            assert git_cache.active() == {}
        assert git_cache.active() is outer


# --- locate ------------------------------------------------------------------------


def test_locate_reads_a_git_directory(tmp_path: Path) -> None:
    root = _repo(tmp_path / "r")
    (root / "sub").mkdir()
    found = git_cache.locate(root / "sub")
    assert found is not None
    assert found.git_dir == (root / ".git").resolve()
    assert found.common_dir == (root / ".git").resolve()


def test_locate_follows_a_linked_worktrees_gitdir_and_commondir(tmp_path: Path) -> None:
    root = _repo(tmp_path / "r")
    wt = tmp_path / "wt"
    _git(root, "worktree", "add", "-q", "-b", "side", str(wt))
    found = git_cache.locate(wt)
    assert found is not None
    assert found.git_dir == (root / ".git" / "worktrees" / "wt").resolve()
    assert found.common_dir == (root / ".git").resolve()


def test_locate_gives_none_with_no_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    (tmp_path / "plain").mkdir()
    assert git_cache.locate(tmp_path / "plain") is None


@pytest.mark.parametrize("var", ["GIT_DIR", "GIT_COMMON_DIR"])
def test_locate_gives_none_under_a_git_dir_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, var: str
) -> None:
    root = _repo(tmp_path / "r")
    monkeypatch.setenv(var, str(root / ".git"))
    assert git_cache.locate(root) is None


def test_locate_gives_none_for_a_reftable_repository(tmp_path: Path) -> None:
    root = _repo(tmp_path / "r")
    (root / ".git" / "reftable").mkdir()
    assert git_cache.locate(root) is None


def test_locate_gives_none_with_worktree_config(tmp_path: Path) -> None:
    root = _repo(tmp_path / "r")
    _git(root, "config", "extensions.worktreeConfig", "true")
    assert git_cache.locate(root) is None


def test_locate_gives_none_under_the_legacy_git_config_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path / "r")
    other = tmp_path / "other.gitconfig"
    other.write_text("")
    monkeypatch.setenv("GIT_CONFIG", str(other))
    assert git_cache.locate(root) is None


def test_an_include_in_the_repository_config_is_followed(tmp_path: Path) -> None:
    root = _repo(tmp_path / "r")
    (root / ".git" / "extra.gitconfig").write_text("")
    with (root / ".git" / "config").open("a") as f:
        f.write("[include]\n\tpath = extra.gitconfig\n")
    found = git_cache.locate(root)
    assert found is not None
    assert (root / ".git" / "extra.gitconfig") in found.config_files


def test_an_include_if_in_the_global_config_is_followed_whatever_its_condition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path / "r")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    (home / "work.gitconfig").write_text("[include]\n\tpath = nested.gitconfig\n")
    glob = tmp_path / "global.gitconfig"
    glob.write_text(
        '[includeIf "gitdir:/nowhere/"]\n\tpath = ~/work.gitconfig\n'
        '[includeIf "gitdir:~/elsewhere/"] path = "~/absent.gitconfig"\n'
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(glob))
    found = git_cache.locate(root)
    assert found is not None
    assert {home / "work.gitconfig", home / "nested.gitconfig", home / "absent.gitconfig"} <= set(
        found.config_files
    )


@pytest.mark.parametrize(
    "value", ["%(prefix)/etc/x", "~someone/x", ""], ids=["prefix", "tilde-user", "empty"]
)
def test_an_include_path_that_cannot_be_resolved_declines(tmp_path: Path, value: str) -> None:
    root = _repo(tmp_path / "r")
    with (root / ".git" / "config").open("a") as f:
        f.write(f"[include]\n\tpath = {value}\n")
    assert git_cache.locate(root) is None


def test_an_include_cycle_hits_the_depth_limit_and_declines(tmp_path: Path) -> None:
    root = _repo(tmp_path / "r")
    (root / ".git" / "loop.gitconfig").write_text("[include]\n\tpath = loop.gitconfig\n")
    with (root / ".git" / "config").open("a") as f:
        f.write("[include]\n\tpath = loop.gitconfig\n")
    assert git_cache.locate(root) is None


def test_the_fingerprint_moves_when_a_consulted_ref_appears(tmp_path: Path) -> None:
    work, _ = _with_origin(tmp_path)
    found = git_cache.locate(work)
    assert found is not None
    before = git_cache.fingerprint(found, "origin", ("main",))
    _git(work, "fetch", "-q", "origin")
    assert git_cache.fingerprint(found, "origin", ("main",)) != before


def test_the_fingerprint_is_stable_when_nothing_changed(tmp_path: Path) -> None:
    work, _ = _with_origin(tmp_path)
    found = git_cache.locate(work)
    assert found is not None
    assert git_cache.fingerprint(found, "origin", ("main",)) == git_cache.fingerprint(
        found, "origin", ("main",)
    )


# --- remote_name / remote_default_ref through the cache --------------------------


def test_two_identical_questions_in_one_scope_start_git_once(
    tmp_path: Path, git_starts: GitStarts
) -> None:
    work, _ = _with_origin(tmp_path)
    _git(work, "fetch", "-q", "origin")
    with git_cache.scope():
        assert remote_default_ref(work) == "origin/main"
        first = git_starts.count
        assert first > 0
        assert remote_default_ref(work) == "origin/main"
        assert remote_name(work) == "origin"
        assert git_starts.count == first


def test_outside_a_scope_git_starts_every_time(tmp_path: Path, git_starts: GitStarts) -> None:
    work, _ = _with_origin(tmp_path)
    _git(work, "fetch", "-q", "origin")
    start = git_starts.count
    assert remote_default_ref(work) == "origin/main"
    first = git_starts.count - start
    assert first > 0
    assert remote_default_ref(work) == "origin/main"
    assert git_starts.count - start == 2 * first
    assert git_cache.active() is None


def _hit(git_starts: GitStarts, ask, expected) -> None:  # type: ignore[no-untyped-def]
    """Asking again answers *expected* from the cache: no git starts."""
    before = git_starts.count
    assert ask() == expected
    assert git_starts.count == before, git_starts.calls[before:]


def test_a_fetch_that_creates_the_default_ref_is_seen(
    tmp_path: Path, git_starts: GitStarts
) -> None:
    work, _ = _with_origin(tmp_path)
    with git_cache.scope():
        assert remote_default_ref(work) is None
        _hit(git_starts, lambda: remote_default_ref(work), None)
        _git(work, "fetch", "-q", "origin")
        assert remote_default_ref(work) == "origin/main"


def test_remote_set_head_is_seen(tmp_path: Path, git_starts: GitStarts) -> None:
    work, origin = _with_origin(tmp_path)
    _git(origin, "branch", "trunk", "main")
    _git(work, "fetch", "-q", "origin")
    with git_cache.scope():
        assert remote_default_ref(work) == "origin/main"
        _hit(git_starts, lambda: remote_default_ref(work), "origin/main")
        _git(work, "remote", "set-head", "origin", "trunk")
        assert remote_default_ref(work) == "origin/trunk"
        _hit(git_starts, lambda: remote_default_ref(work), "origin/trunk")
        _git(work, "remote", "set-head", "origin", "-a")
        assert remote_default_ref(work) == "origin/main"


def test_a_default_remote_set_in_the_global_config_is_seen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_starts: GitStarts
) -> None:
    work, origin = _with_origin(tmp_path)
    _git(work, "remote", "add", "upstream", str(origin))
    glob = tmp_path / "global.gitconfig"
    glob.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(glob))
    with git_cache.scope():
        assert remote_name(work) == "origin"
        _hit(git_starts, lambda: remote_name(work), "origin")
        subprocess.run(
            ["git", "config", "--global", "checkout.defaultRemote", "upstream"], check=True
        )
        assert remote_name(work) == "upstream"


def test_a_remote_added_is_seen(tmp_path: Path, git_starts: GitStarts) -> None:
    work = _repo(tmp_path / "work")
    with git_cache.scope():
        assert remote_name(work) is None
        _hit(git_starts, lambda: remote_name(work), None)
        _git(work, "remote", "add", "elsewhere", str(tmp_path / "nowhere.git"))
        assert remote_name(work) == "elsewhere"


def test_a_ref_deleted_from_packed_refs_is_seen(tmp_path: Path, git_starts: GitStarts) -> None:
    work, _ = _with_origin(tmp_path)
    _git(work, "fetch", "-q", "origin")
    _git(work, "pack-refs", "--all")
    assert not (work / ".git" / "refs" / "remotes" / "origin" / "main").exists()
    with git_cache.scope():
        assert remote_default_ref(work) == "origin/main"
        _hit(git_starts, lambda: remote_default_ref(work), "origin/main")
        _git(work, "update-ref", "-d", "refs/remotes/origin/main")
        assert remote_default_ref(work) is None


def test_a_nested_default_branch_is_followed_and_its_ref_watched(
    tmp_path: Path, git_starts: GitStarts
) -> None:
    work, origin = _with_origin(tmp_path)
    _git(origin, "branch", "release/x/main", "main")
    _git(work, "fetch", "-q", "origin")
    _git(work, "remote", "set-head", "origin", "release/x/main")
    with git_cache.scope():
        assert remote_default_ref(work) == "origin/release/x/main"
        _hit(git_starts, lambda: remote_default_ref(work), "origin/release/x/main")
        _git(work, "update-ref", "-d", "refs/remotes/origin/release/x/main")
        assert remote_default_ref(work) == "origin/main"


def test_a_linked_worktree_reads_and_watches_the_common_dir(
    tmp_path: Path, git_starts: GitStarts
) -> None:
    work, _ = _with_origin(tmp_path)
    wt = tmp_path / "wt"
    _git(work, "worktree", "add", "-q", "-b", "side", str(wt))
    with git_cache.scope():
        assert remote_default_ref(wt) is None
        _hit(git_starts, lambda: remote_default_ref(wt), None)
        _git(work, "fetch", "-q", "origin")
        assert remote_default_ref(wt) == "origin/main"


def test_a_named_branch_changed_while_git_answers_is_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The before-stamp covers the branch `refs/remotes/<remote>/HEAD` names (p1-r4)."""
    import fr.git as fr_git

    work, origin = _with_origin(tmp_path)
    _git(origin, "branch", "stable", "main")
    _git(work, "fetch", "-q", "origin")
    _git(work, "remote", "set-head", "origin", "stable")
    real = fr_git._default_ref_of
    raced = {"done": False}

    def racing(root, remote):  # type: ignore[no-untyped-def]
        answer = real(root, remote)
        if not raced["done"]:
            raced["done"] = True
            # A bare unlink: `update-ref -d` also rewrites packed-refs, which the
            # well-known before-stamp would catch on its own.
            (work / ".git" / "refs" / "remotes" / "origin" / "stable").unlink()
        return answer

    monkeypatch.setattr(fr_git, "_default_ref_of", racing)
    with git_cache.scope():
        assert remote_default_ref(work) == "origin/stable"
        assert remote_default_ref(work) == "origin/main"


def test_a_refusal_is_not_cached(tmp_path: Path, git_starts: GitStarts) -> None:
    work, origin = _with_origin(tmp_path)
    _git(work, "remote", "add", "upstream", str(origin))
    _git(work, "remote", "rename", "origin", "first")
    with git_cache.scope():
        assert isinstance(remote_name(work), GitRefusal)
        first = git_starts.count
        assert isinstance(remote_name(work), GitRefusal)
        assert git_starts.count > first


def test_git_unavailable_is_not_cached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    work, _ = _with_origin(tmp_path)
    real = subprocess.run
    broken = {"on": True}

    def flaky(args, *a, **kw):  # type: ignore[no-untyped-def]
        if broken["on"] and "checkout.defaultRemote" in [str(x) for x in args]:
            raise FileNotFoundError("git")
        return real(args, *a, **kw)

    monkeypatch.setattr(subprocess, "run", flaky)
    with git_cache.scope():
        with pytest.raises(GitUnavailableError):
            remote_name(work)
        broken["on"] = False
        assert remote_name(work) == "origin"


def test_a_root_that_is_not_a_repository_is_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_starts: GitStarts
) -> None:
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    plain = tmp_path / "plain"
    plain.mkdir()
    with git_cache.scope():
        first = remote_name(plain)
        n = git_starts.count
        assert remote_name(plain) == first
        assert git_starts.count > n


def test_a_global_include_if_config_is_cached_and_its_included_file_watched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_starts: GitStarts
) -> None:
    work, origin = _with_origin(tmp_path)
    _git(work, "remote", "add", "upstream", str(origin))
    included = tmp_path / "x.gitconfig"
    included.write_text("")
    glob = tmp_path / "global.gitconfig"
    glob.write_text(f'[includeIf "gitdir:{work}/"]\n\tpath = {included}\n')
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(glob))
    with git_cache.scope():
        assert remote_name(work) == "origin"
        _hit(git_starts, lambda: remote_name(work), "origin")
        included.write_text("[checkout]\n\tdefaultRemote = upstream\n")
        assert remote_name(work) == "upstream"


def test_a_relative_include_in_the_repository_config_is_watched(
    tmp_path: Path, git_starts: GitStarts
) -> None:
    work, origin = _with_origin(tmp_path)
    _git(work, "remote", "add", "upstream", str(origin))
    extra = work / ".git" / "extra.gitconfig"
    extra.write_text("")
    with (work / ".git" / "config").open("a") as f:
        f.write("[include]\n\tpath = extra.gitconfig\n")
    with git_cache.scope():
        assert remote_name(work) == "origin"
        _hit(git_starts, lambda: remote_name(work), "origin")
        extra.write_text("[checkout]\n\tdefaultRemote = upstream\n")
        assert remote_name(work) == "upstream"


def test_an_onbranch_include_flips_with_a_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_starts: GitStarts
) -> None:
    work, origin = _with_origin(tmp_path)
    _git(work, "remote", "add", "upstream", str(origin))
    _git(work, "branch", "other")
    included = tmp_path / "onbranch.gitconfig"
    included.write_text("[checkout]\n\tdefaultRemote = upstream\n")
    with (work / ".git" / "config").open("a") as f:
        f.write(f'[includeIf "onbranch:other"]\n\tpath = {included}\n')
    with git_cache.scope():
        assert remote_name(work) == "origin"
        _hit(git_starts, lambda: remote_name(work), "origin")
        _git(work, "checkout", "-q", "other")
        assert remote_name(work) == "upstream"


def test_the_system_config_path_is_asked_once_per_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_starts: GitStarts
) -> None:
    monkeypatch.delenv("GIT_CONFIG_NOSYSTEM", raising=False)
    monkeypatch.delenv("GIT_CONFIG_SYSTEM", raising=False)
    monkeypatch.setattr(git_cache, "_SYSTEM_MEMO", {})
    work, _ = _with_origin(tmp_path)
    for _ in range(2):
        with git_cache.scope():
            remote_name(work)
    probes = [c for c in git_starts.calls if "--system" in c]
    assert len(probes) == 1, probes


def test_a_reftable_repository_is_never_cached(tmp_path: Path, git_starts: GitStarts) -> None:
    work = tmp_path / "rt"
    work.mkdir()
    done = subprocess.run(
        ["git", "-C", str(work), "init", "-q", "--ref-format=reftable"],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        pytest.skip(f"this git cannot make a reftable repository: {done.stderr.strip()}")
    _git(work, "remote", "add", "origin", str(tmp_path / "nowhere.git"))
    with git_cache.scope():
        start = git_starts.count
        assert remote_name(work) == "origin"
        n = git_starts.count - start
        assert remote_name(work) == "origin"
        assert git_starts.count - start == 2 * n


def test_the_cli_entry_opens_a_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_FrGroup.invoke` wraps every command in `git_cache.scope()`, and closes it."""
    import fr.cli as cli
    from typer.testing import CliRunner

    seen: list[object] = []
    real_invoke = cli.TyperGroup.invoke

    def spy_invoke(self, ctx):  # type: ignore[no-untyped-def]
        seen.append(git_cache.active())
        return real_invoke(self, ctx)

    monkeypatch.setattr(cli.TyperGroup, "invoke", spy_invoke)
    CliRunner().invoke(cli.app, ["skills"])
    assert seen and seen[0] is not None
    assert git_cache.active() is None
