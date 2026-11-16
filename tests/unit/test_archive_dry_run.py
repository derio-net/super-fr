"""`fr archive --dry-run` (spec 2026-11-15-owed-archive-side-effects R10, R11, design §C):
the preview forge, the scratch checkout and the flag in every mode.

Negative evidence everywhere: a forge double that records every write, and
byte-identical `git status --porcelain` and `git diff --cached` around each dry run.
"""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr import archive_followups as af
from fr import archive_preview as ap
from fr.cli import app
from fr.commands import archive_cmd
from fr.ghclient import GhClient
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient
from tests.unit.test_archive_cmd import _add_plan, _commit, _hermetic, _repo  # noqa: F401
from tests.unit.test_archive_cmd import _seed as _seed_repo
from tests.unit.test_merge_evidence import _git, _publish

# --- Task 1: the preview forge ------------------------------------------------------


class _Recording:
    """A wrapped client that records every call it receives."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str) -> Any:
        def call(*a: Any, **k: Any) -> Any:
            self.calls.append(name)
            return f"real:{name}"

        return call


def test_every_protocol_method_is_in_exactly_one_set() -> None:
    methods = {
        n for n, v in inspect.getmembers(GhClient, predicate=callable) if not n.startswith("_")
    }
    assert ap.READS | ap.WRITES == methods
    assert not ap.READS & ap.WRITES


def test_reads_delegate_to_the_wrapped_client() -> None:
    inner = _Recording()
    forge = ap.PreviewForge(inner)
    assert forge.view_issue_record("o/r", 1) == "real:view_issue_record"
    assert forge.list_issues("o/r", "open", 5) == "real:list_issues"
    assert inner.calls == ["view_issue_record", "list_issues"]
    assert forge.writes == [] and forge.refused == []


def test_create_issue_answers_a_ref_the_follow_ups_accept() -> None:
    inner = _Recording()
    forge = ap.PreviewForge(inner)
    url1 = forge.create_issue("o/r", title="t", body="b", labels=frozenset())
    url2 = forge.create_issue("o/r", title="t2", body="b", labels=frozenset())
    assert url1 == "https://github.com/o/r/issues/900000"
    assert url2.endswith("/issues/900001")
    assert af._issue_ref("o/r", None, url1) == "o/r#900000"
    assert inner.calls == [] and len(forge.writes) == 2


def test_other_known_writes_are_recorded_and_not_called() -> None:
    inner = _Recording()
    forge = ap.PreviewForge(inner)
    assert forge.close_issue("o/r", 3, "done") is None
    assert forge.ensure_labels("o/r", []) is None
    assert inner.calls == []
    assert [w.split("(")[0] for w in forge.writes] == ["close_issue", "ensure_labels"]


def test_an_unknown_method_is_refused_and_never_reaches_the_wrapped_client() -> None:
    inner = _Recording()
    forge = ap.PreviewForge(inner)
    assert forge.brand_new_write("o/r") is None
    assert forge.refused == ["brand_new_write"]
    assert inner.calls == []


# --- Task 2: the scratch checkout ---------------------------------------------------


def _porcelain(repo: Path) -> str:
    return _git(repo, "status", "--porcelain")


def _world(tmp_path: Path) -> Path:
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("a\n")
    (repo / "b.txt").write_text("b\n")
    (repo / ".gitignore").write_text("ignored.txt\n")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "seed")
    return repo


def test_scratch_checkout_replays_staged_unstaged_and_untracked(tmp_path: Path) -> None:
    repo = _world(tmp_path)
    (repo / "a.txt").write_text("a staged\n")
    _git(repo, "add", "a.txt")
    (repo / "b.txt").write_text("b unstaged\n")
    (repo / "new.txt").write_text("untracked\n")
    (repo / "ignored.txt").write_text("secret\n")
    with ap.scratch_checkout(repo) as scratch:
        assert scratch != repo
        assert _porcelain(scratch) == _porcelain(repo)
        assert (scratch / "new.txt").read_text() == "untracked\n"
        assert not (scratch / "ignored.txt").exists()
        assert (scratch / "a.txt").read_text() == "a staged\n"
    assert not scratch.exists()
    assert "fr-archive-dry-run" not in _git(repo, "worktree", "list")


def test_scratch_checkout_is_removed_when_the_body_raises(tmp_path: Path) -> None:
    repo = _world(tmp_path)
    with pytest.raises(RuntimeError), ap.scratch_checkout(repo) as scratch:
        raise RuntimeError("boom")
    assert not scratch.exists()
    assert "fr-archive-dry-run" not in _git(repo, "worktree", "list")


def test_a_stale_scratch_worktree_is_pruned_first(tmp_path: Path) -> None:
    repo = _world(tmp_path)
    dead = subprocess.Popen(["true"])
    dead.wait()
    stale = Path(ap.scratch_root()) / f"fr-archive-dry-run-{dead.pid}"
    _git(repo, "worktree", "add", "-q", "--detach", str(stale), "HEAD")
    assert stale.exists()
    with ap.scratch_checkout(repo):
        assert not stale.exists()
    assert "fr-archive-dry-run" not in _git(repo, "worktree", "list")


# --- Task 3: the flag in every mode -------------------------------------------------


def _state(repo: Path) -> tuple[str, ...]:
    """Everything a dry run must leave as it was: tree, index, HEAD, every ref, the local
    config and the registered worktrees (review p3-r11)."""
    common = Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").strip())
    worktrees = common / "worktrees"
    listing = sorted(p.name for p in worktrees.iterdir()) if worktrees.is_dir() else []
    return (
        _git(repo, "status", "--porcelain", "--untracked-files=all"),
        _git(repo, "diff", "--cached"),
        _git(repo, "rev-parse", "HEAD"),
        _git(repo, "for-each-ref", "--format=%(refname) %(objectname)"),
        _git(repo, "config", "--list", "--local"),
        "\n".join(listing),
    )


class _Ledger(FakeGhClient):
    """A client that raises on any write: the dry run must never reach it."""

    def __getattribute__(self, name: str) -> Any:
        if name in ap.WRITES:
            raise AssertionError(f"the dry run reached the real client's {name}")
        return super().__getattribute__(name)


def _invoke(monkeypatch: pytest.MonkeyPatch, repo: Path, argv: list[str]) -> Any:
    monkeypatch.setattr(archive_cmd, "_make_gh_client", lambda: _Ledger())
    monkeypatch.chdir(repo)
    monkeypatch.setenv("FR_REPO_ROOT", str(repo))
    return CliRunner().invoke(app, argv)


@pytest.fixture
def merged_repo(tmp_path: Path, _hermetic: list[str]) -> Path:  # noqa: F811
    repo = _repo(tmp_path)
    _add_plan(repo, "2026-06-01-p", ticked=True)
    _seed_repo(repo)
    return repo


def test_plan_dry_run_matches_the_real_run_and_changes_nothing(
    merged_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = "docs/superpowers/plans/2026-06-01-p"
    before = _state(merged_repo)
    dry = _invoke(monkeypatch, merged_repo, ["archive", plan, "--dry-run"])
    assert dry.exit_code == 0, dry.output
    assert "archived:" in dry.output
    assert "would stage" in dry.output and "implemented/plans" in dry.output
    assert _state(merged_repo) == before
    assert (merged_repo / plan).is_dir()
    real = _invoke(monkeypatch, merged_repo, ["archive", plan])
    assert real.exit_code == dry.exit_code
    assert not (merged_repo / plan).exists()


def test_archive_reads_no_git_ignored_file(
    merged_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The scratch tree omits ignored files, so a dry run is only faithful if `fr archive`
    never reads one: a poisoned ignored file changes nothing in the output."""
    plan = "docs/superpowers/plans/2026-06-01-p"
    clean = _invoke(monkeypatch, merged_repo, ["archive", plan, "--dry-run"])
    (merged_repo / ".gitignore").write_text("poison.txt\n.fr-poison/\n")
    (merged_repo / "poison.txt").write_text("x" * 100)
    (merged_repo / ".fr-poison").mkdir()
    (merged_repo / ".fr-poison" / "a").write_text("y")
    _git(merged_repo, "add", ".gitignore")
    _commit(merged_repo, "ignore")
    _publish(merged_repo)
    poisoned = _invoke(monkeypatch, merged_repo, ["archive", plan, "--dry-run"])
    assert poisoned.output == clean.output
    assert poisoned.exit_code == clean.exit_code == 0


@pytest.mark.parametrize("argv", [["archive", "--all"], ["archive", "--sweep-only"]])
def test_all_and_sweep_only_dry_runs_change_nothing_and_exit_as_the_real_run(
    merged_repo: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> None:
    before = _state(merged_repo)
    dry = _invoke(monkeypatch, merged_repo, [*argv, "--dry-run"])
    assert _state(merged_repo) == before
    if argv[1] == "--all":
        assert "archived:" in dry.output and "would stage" in dry.output
    real = _invoke(monkeypatch, merged_repo, argv)
    assert dry.exit_code == real.exit_code, (dry.output, real.output)


def test_a_refused_plan_exits_with_the_real_runs_code(
    merged_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = merged_repo / "docs/superpowers/plans/2026-06-01-p"
    (plan / "01.yaml").write_text((plan / "01.yaml").read_text().replace("state: x", 'state: " "'))
    _commit(merged_repo, "unfinish")
    _publish(merged_repo)
    before = _state(merged_repo)
    rel = "docs/superpowers/plans/2026-06-01-p"
    dry = _invoke(monkeypatch, merged_repo, ["archive", rel, "--dry-run"])
    real = _invoke(monkeypatch, merged_repo, ["archive", rel])
    assert dry.exit_code == real.exit_code == 2
    assert _state(merged_repo) == before


def test_dry_run_never_prompts_and_lists_the_open_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.artifacts import trigger

    from tests.unit.test_archive_open_ends import SLUG, _open_ends_repo

    repo = _open_ends_repo(tmp_path)
    monkeypatch.setattr(trigger, "is_interactive", lambda **_k: True)
    monkeypatch.setattr(
        "builtins.input", lambda *_a: (_ for _ in ()).throw(AssertionError("prompted"))
    )
    before = _state(repo)
    out = _invoke(monkeypatch, repo, ["archive", f"docs/superpowers/plans/{SLUG}", "--dry-run"])
    assert out.exit_code == 0, out.output
    assert f"plan/{SLUG}/f1: first open" in out.output
    assert f"plan/{SLUG}/f2: second, scoped out" in out.output
    assert "create_issue" not in out.output
    assert _state(repo) == before


def test_an_unknown_forge_call_exits_one_naming_it(
    merged_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_sweep = archive_cmd.spec_archive_sweep

    def sweep(root: Path, gh: Any) -> Any:
        gh.future_method("o/r")  # a forge call the dry run does not know as a read
        return real_sweep(root, gh)

    monkeypatch.setattr(archive_cmd, "spec_archive_sweep", sweep)
    before = _state(merged_repo)
    out = _invoke(monkeypatch, merged_repo, ["archive", "--sweep-only", "--dry-run"])
    assert out.exit_code == 1, out.output
    assert "future_method" in " ".join(out.output.split())
    assert _state(merged_repo) == before


def test_branch_dry_run_previews_the_moves_and_exits_as_the_real_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit import test_archive_branch as tb

    repo = tb._base(tmp_path)
    plan = "2026-09-28-thing"
    tb._merged(repo, lambda r: tb._plan(r, plan, ticked=True))
    before = _state(repo)
    dry = _invoke(monkeypatch, repo, ["archive", "--branch", tb.BRANCH, "--dry-run"])
    assert f"archived: docs/superpowers/plans/{plan}" in dry.output, dry.output
    assert "would stage" in dry.output and f"implemented/plans/{plan}" in dry.output
    assert _state(repo) == before
    real = _invoke(monkeypatch, repo, ["archive", "--branch", tb.BRANCH])
    assert f"archived: docs/superpowers/plans/{plan}" in real.output, real.output
    assert dry.exit_code == real.exit_code == 0


# --- quiet and stealth: the record is previewed, never written -----------------------


from tests.unit.test_placement_merged import (  # noqa: E402
    Product,
    _home,
    quiet,
    stealthy,
)
from tests.unit.test_placement_merged_archive import _seed, git  # noqa: E402

__all__ = ["_home", "quiet", "stealthy"]


def _sentinels(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    hits: list[str] = []

    def boom(name: str) -> Any:
        def fn(*a: Any, **k: Any) -> Any:
            hits.append(name)
            raise AssertionError(f"{name} was reached by a dry run")

        return fn

    from fr.artifacts import commit as commit_mod
    from fr.git_policy import push as push_mod
    from fr.placement import merged as merged_status
    from fr.placement import stealth

    monkeypatch.setattr(merged_status, "append_record", boom("append_record"))
    monkeypatch.setattr(archive_cmd, "_commit_merged_record", boom("_commit_merged_record"))
    monkeypatch.setattr(archive_cmd, "_push_fr", boom("_push_fr"))
    monkeypatch.setattr(stealth, "commit_and_push", boom("commit_and_push"))
    monkeypatch.setattr(commit_mod, "commit_paths", boom("commit_paths"))
    monkeypatch.setattr(push_mod, "atomic_push", boom("atomic_push"))
    return hits


def _quiet_dry(product: Product, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.unit.test_placement_merged_archive import _fr

    product.feature("a")
    _seed(product, "a", product.space.root, push="origin fr")
    product.merge("a")
    hits = _sentinels(monkeypatch)
    wt = product.space.root
    before = (
        _git(wt, "status", "--porcelain", "--untracked-files=all"),
        _git(wt, "rev-parse", "HEAD"),
        _git(product.root, "status", "--porcelain", "--untracked-files=all"),
        _git(product.root, "diff", "--cached"),
    )
    result = _fr(product.root, "archive", "--branch", "feat/a", "--dry-run")
    assert result.exit_code == 0, result.output
    assert "would" in result.output
    assert hits == []
    after = (
        _git(wt, "status", "--porcelain", "--untracked-files=all"),
        _git(wt, "rev-parse", "HEAD"),
        _git(product.root, "status", "--porcelain", "--untracked-files=all"),
        _git(product.root, "diff", "--cached"),
    )
    assert after == before
    assert not (product.feature_root("a") / "merged.yaml").exists()


def test_quiet_branch_dry_run_previews_the_record_and_writes_nothing(
    quiet: Product, monkeypatch: pytest.MonkeyPatch
) -> None:
    _quiet_dry(quiet, monkeypatch)


def test_stealth_branch_dry_run_previews_the_record_and_writes_nothing(
    stealthy: Product, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.placement import stealth

    stealthy.feature("a")
    wt = stealth.tracking_root(stealthy.space)
    _seed(stealthy, "a", wt, push="origin main")
    stealthy.merge("a")
    hits = _sentinels(monkeypatch)
    target_origin = Path(git(stealthy.ops, "remote", "get-url", "origin").strip())
    refs = git(target_origin, "for-each-ref", "--format=%(refname) %(objectname)")
    head = _git(wt, "rev-parse", "HEAD")
    from tests.unit.test_placement_merged_archive import _fr

    stealth.reset_caches()  # a new process: nothing reached or synced yet
    result = _fr(stealthy.root, "archive", "--branch", "feat/a", "--dry-run")
    assert result.exit_code == 0, result.output
    assert "would" in result.output
    assert hits == []
    assert git(target_origin, "for-each-ref", "--format=%(refname) %(objectname)") == refs
    assert _git(wt, "rev-parse", "HEAD") == head
    assert _git(wt, "status", "--porcelain", "--untracked-files=all") == ""


# --- review p3: the scratch removes only its own, and replays faithfully ------------


def _porcelain_z(repo: Path) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain=v2", "-z", "--untracked-files=all"],
        check=True,
        capture_output=True,
    ).stdout.replace(b"0000000000000000000000000000000000000000", b"")


def _without_shas(z: bytes) -> list[bytes]:
    """Porcelain v2 records with their object names dropped (the scratch's index stat
    differs, the content does not)."""
    out = []
    for rec in z.split(b"\0"):
        fields = rec.split(b" ")
        if rec.startswith(b"1 ") and len(fields) >= 9:
            out.append(b" ".join([*fields[:3], *fields[8:]]))
        else:
            out.append(rec)
    return out


def test_scratch_never_deregisters_another_worktree(tmp_path: Path) -> None:
    """Review p3-r2 (pr1431-n1): no global `git worktree prune`. A worktree whose
    directory is not there (in a devcontainer: a host worktree that is not mounted)
    stays registered."""
    repo = _world(tmp_path)
    other = tmp_path / "unmounted"
    _git(repo, "worktree", "add", "-q", "--detach", str(other), "HEAD")
    import shutil

    shutil.rmtree(other)
    with ap.scratch_checkout(repo):
        pass
    assert str(other) in _git(repo, "worktree", "list", "--porcelain").replace(
        "/private/", "/"
    ) or str(other.resolve()) in _git(repo, "worktree", "list", "--porcelain")


def test_a_stale_scratch_whose_directory_is_gone_is_forgotten_by_its_own_path(
    tmp_path: Path,
) -> None:
    repo = _world(tmp_path)
    dead = subprocess.Popen(["true"])
    dead.wait()
    stale = Path(ap.scratch_root()) / f"fr-archive-dry-run-{dead.pid}"
    _git(repo, "worktree", "add", "-q", "--detach", str(stale), "HEAD")
    import shutil

    shutil.rmtree(stale)
    with ap.scratch_checkout(repo):
        pass
    assert "fr-archive-dry-run" not in _git(repo, "worktree", "list", "--porcelain")


def test_scratch_copies_an_untracked_nested_repository(tmp_path: Path) -> None:
    repo = _world(tmp_path)
    nested = repo / "vendor" / "lib"
    nested.mkdir(parents=True)
    _git(nested, "init", "-q", "-b", "main")
    (nested / "x").write_text("x\n")
    (repo / "loose").mkdir()
    (repo / "loose" / "y").write_text("y\n")
    with ap.scratch_checkout(repo) as scratch:
        assert _porcelain_z(scratch) == _porcelain_z(repo)
        assert (scratch / "vendor" / "lib" / "x").read_text() == "x\n"


def test_scratch_replays_a_name_that_is_not_utf8(tmp_path: Path) -> None:
    import os

    repo = _world(tmp_path)
    name = os.fsdecode(b"caf\xe9.txt")
    try:
        (repo / name).write_text("untracked\n")
    except OSError:
        pytest.skip("this filesystem refuses a name that is not UTF-8 (APFS)")
    tracked = os.fsdecode(b"na\xefve.txt")
    (repo / tracked).write_text("one\n")
    _git(repo, "add", "--", tracked)
    with ap.scratch_checkout(repo) as scratch:
        assert _porcelain_z(scratch) == _porcelain_z(repo)
        assert (scratch / name).read_text() == "untracked\n"


def test_scratch_replays_names_git_would_quote(tmp_path: Path) -> None:
    repo = _world(tmp_path)
    odd = "café\tnew\nline.txt"
    (repo / odd).write_text("untracked\n")
    (repo / "naïve.txt").write_text("staged\n")
    _git(repo, "add", "naïve.txt")
    with ap.scratch_checkout(repo) as scratch:
        assert _porcelain_z(scratch) == _porcelain_z(repo)
        assert (scratch / odd).read_text() == "untracked\n"


def test_scratch_keeps_intent_to_add_entries(tmp_path: Path) -> None:
    repo = _world(tmp_path)
    (repo / "later.txt").write_text("later\n")
    _git(repo, "add", "-N", "later.txt")
    with ap.scratch_checkout(repo) as scratch:
        assert _porcelain(scratch) == _porcelain(repo)
        assert "1 .A " in _git(scratch, "status", "--porcelain=v2")
        assert (scratch / "later.txt").read_text() == "later\n"


def test_scratch_replays_whitespace_errors_under_apply_whitespace_error(tmp_path: Path) -> None:
    repo = _world(tmp_path)
    _git(repo, "config", "apply.whitespace", "error")
    (repo / "a.txt").write_text("a staged   \n")
    _git(repo, "add", "a.txt")
    (repo / "b.txt").write_text("b unstaged\t\n")
    with ap.scratch_checkout(repo) as scratch:
        assert _porcelain(scratch) == _porcelain(repo)
        assert (scratch / "b.txt").read_text() == "b unstaged\t\n"


def test_scratch_runs_no_hook_and_no_lfs_smudge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review p3-r7: `worktree add` would run the repo's post-checkout hook and LFS
    smudge."""
    repo = _world(tmp_path)
    marker = tmp_path / "hook-ran"
    hook = repo / ".git" / "hooks" / "post-checkout"
    hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
    hook.chmod(0o755)
    seen: list[tuple[list[str], dict[str, str]]] = []
    real_run = subprocess.run

    def spy(argv: Any, *a: Any, **k: Any) -> Any:
        if isinstance(argv, list) and "worktree" in argv and "add" in argv:
            seen.append((list(argv), dict(k.get("env") or {})))
        return real_run(argv, *a, **k)

    monkeypatch.setattr(ap.subprocess, "run", spy)
    with ap.scratch_checkout(repo):
        pass
    assert not marker.exists()
    ((argv, env),) = seen
    assert "core.hooksPath=/dev/null" in argv
    assert env.get("GIT_LFS_SKIP_SMUDGE") == "1"


# --- review p3-r10: the preview URL takes the forge's own shape ----------------------


def test_preview_urls_take_the_forges_shape(tmp_path: Path) -> None:
    lab = ap.PreviewForge(_Recording(), host="gitlab.example.org", backend="gitlab")
    assert (
        lab.create_issue("g/p", title="t", body="b", labels=frozenset())
        == "https://gitlab.example.org/g/p/-/issues/900000"
    )
    repo = _world(tmp_path)
    _git(repo, "remote", "add", "origin", "https://gitlab.com/g/p.git")
    assert ap.forge_of(repo) == ("gitlab", "gitlab.com")


# --- review p3-r4: the scratch answers "on the default branch" as the checkout does ---


def test_a_dry_run_on_the_default_branch_previews_the_owed_entries_the_real_run_would(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.test_archive_owed import PLAN, ListingGh, _manual_repo

    repo = _manual_repo(tmp_path)  # HEAD is main, which origin/main names
    gh = ListingGh()
    monkeypatch.setattr(archive_cmd, "_make_gh_client", lambda: gh)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("FR_REPO_ROOT", str(repo))
    before = _state(repo)
    dry = CliRunner().invoke(app, ["archive", "--all", "--dry-run"])
    assert dry.exit_code == 0, dry.output
    assert f"would record owed: plan:{PLAN}#p2 — " in dry.output
    assert "create_issue" not in dry.output and "owed actions:" not in dry.output
    assert not [n for n, _ in gh.calls if n == "create_issue"]
    assert _state(repo) == before
    real = CliRunner().invoke(app, ["archive", "--all"])
    assert f"would record owed: plan:{PLAN}#p2 — " in real.output
    assert real.exit_code == dry.exit_code


# --- review p3-r8: the output names the real checkout, never the scratch -------------


@pytest.mark.parametrize("absolute", [False, True])
def test_dry_run_output_names_no_scratch_path(
    merged_repo: Path, monkeypatch: pytest.MonkeyPatch, absolute: bool
) -> None:
    plan = "docs/superpowers/plans/2026-06-01-p"
    arg = str(merged_repo / plan) if absolute else plan
    out = _invoke(monkeypatch, merged_repo, ["archive", arg, "--dry-run"])
    assert out.exit_code == 0, out.output
    assert "archived:" in out.output
    assert "fr-archive-dry-run-" not in out.output
    assert "moves staged via git mv" not in out.output


# --- review p3-r9: a crash still names the refused forge call ------------------------


def test_a_crash_after_a_refused_call_still_names_it_and_exits_one(
    merged_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def sweep(root: Path, gh: Any) -> Any:
        gh.future_method("o/r")
        raise RuntimeError("the sweep broke")

    monkeypatch.setattr(archive_cmd, "spec_archive_sweep", sweep)
    before = _state(merged_repo)
    out = _invoke(monkeypatch, merged_repo, ["archive", "--sweep-only", "--dry-run"])
    assert out.exit_code == 1, out.output
    assert "future_method" in " ".join(out.output.split())
    assert "dry run — nothing was written." in out.output
    assert _state(merged_repo) == before


# --- review p3-r1: under quiet and stealth, every forge call is previewed -------------


class _NoWrites(FakeGhClient):
    """The real client of a quiet dry run: any write it receives fails the test."""

    def __getattribute__(self, name: str) -> Any:
        if name in ap.WRITES:
            raise AssertionError(f"the dry run reached the real client's {name}")
        return super().__getattribute__(name)


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


def test_quiet_issues_dry_run_previews_the_filing_and_writes_nothing(
    quiet: Product, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.journal.model import JournalEntry, append_journal_entry, journal_path

    from tests.unit.test_placement_merged_archive import _fr

    quiet.feature("a")
    _seed(quiet, "a", quiet.space.root, push="origin fr")
    quiet.merge("a")
    slug = "2026-11-15-thing"
    jpath = journal_path(quiet.root, "plan", slug)
    append_journal_entry(
        jpath,
        slug,
        JournalEntry(
            kind="finding",
            scope="plan",
            id="f1",
            created="2026-11-15T00:00:00+00:00",
            state="open",
            title="an open end",
            body="why",
        ),
    )
    wt = quiet.space.root
    git(wt, "add", "-A")
    git(wt, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "journal")
    monkeypatch.setattr("fr.settings.require_forge", lambda *a, **k: None)
    monkeypatch.setattr(archive_cmd, "_repo_slug", lambda root: "acme/widgets")
    monkeypatch.setattr(archive_cmd, "_make_gh_client", lambda: _NoWrites())
    hits = _sentinels(monkeypatch)
    before = (
        _git(wt, "status", "--porcelain", "--untracked-files=all"),
        _git(wt, "rev-parse", "HEAD"),
        _tree_bytes(wt),
        _state(quiet.root),
    )
    result = _fr(
        quiet.root, "archive", "--branch", "feat/a", "--issues", f"plan/{slug}/f1", "--dry-run"
    )
    assert result.exit_code == 0, result.output
    assert hits == []
    assert "would defer plan/" in result.output
    assert "create_issue('acme/widgets'" in result.output
    after = (
        _git(wt, "status", "--porcelain", "--untracked-files=all"),
        _git(wt, "rev-parse", "HEAD"),
        _tree_bytes(wt),
        _state(quiet.root),
    )
    assert after == before


# --- review p3-r5: a preview that cannot see refuses by name --------------------------


def test_quiet_dry_run_with_no_fr_worktree_yet_refuses_by_name(
    quiet: Product, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.test_placement_merged_archive import _fr

    quiet.feature("a")
    _seed(quiet, "a", quiet.space.root, push="origin fr")
    quiet.merge("a")
    wt = quiet.space.root
    git(quiet.root, "worktree", "remove", "--force", str(wt))
    before = _state(quiet.root)
    result = _fr(quiet.root, "archive", "--branch", "feat/a", "--dry-run")
    assert result.exit_code == 2, result.output
    flat = " ".join(result.output.split())
    assert "dry run cannot tell" in flat and "no `fr` worktree yet" in flat
    assert "nothing to archive" not in flat
    assert not wt.exists()
    assert _state(quiet.root) == before


def _stealth_merged(stealthy: Product) -> Path:
    """A merged stealth feature, the process's caches reset as a new `fr` would start."""
    from fr.placement import stealth

    stealthy.feature("a")
    wt = stealth.tracking_root(stealthy.space)
    _seed(stealthy, "a", wt, push="origin main")
    stealthy.merge("a")
    stealth.reset_caches()
    return wt


def test_stealth_dry_run_with_the_tracking_clone_gone_refuses_by_name(
    stealthy: Product, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    from tests.unit.test_placement_merged_archive import _fr

    wt = _stealth_merged(stealthy)
    shutil.rmtree(wt)
    result = _fr(stealthy.root, "archive", "--branch", "feat/a", "--dry-run")
    assert result.exit_code == 2, result.output
    flat = " ".join(result.output.split())
    assert "dry run cannot tell" in flat and "is gone" in flat
    assert not wt.exists()


def test_stealth_dry_run_with_an_unreachable_tracking_repo_refuses_by_name(
    stealthy: Product, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.placement import stealth
    from fr.settings import SettingsError

    from tests.unit.test_placement_merged_archive import _fr

    _stealth_merged(stealthy)

    def unreachable(ref: Any, cwd: Path) -> None:
        raise SettingsError("placement stealth: the tracking repo x is unreachable (down)")

    monkeypatch.setattr(stealth, "check_reachable", unreachable)
    result = _fr(stealthy.root, "archive", "--branch", "feat/a", "--dry-run")
    assert result.exit_code == 2, result.output
    assert "unreachable" in " ".join(result.output.split())


def test_stealth_dry_run_with_a_clone_behind_its_tip_refuses_by_name(
    stealthy: Product, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.test_placement_merged_archive import _fr

    wt = _stealth_merged(stealthy)
    git(wt, "reset", "-q", "--hard", "HEAD~1")
    head = _git(wt, "rev-parse", "HEAD")
    result = _fr(stealthy.root, "archive", "--branch", "feat/a", "--dry-run")
    assert result.exit_code == 2, result.output
    assert "not synced" in " ".join(result.output.split())
    assert _git(wt, "rev-parse", "HEAD") == head


def test_the_gate_refuses_a_quiet_dry_run_before_it_creates_the_fr_worktree(
    quiet: Product,
) -> None:
    import typer
    from fr.artifacts import trigger

    quiet.feature("a")
    _seed(quiet, "a", quiet.space.root, push="origin fr")
    quiet.merge("a")
    wt = quiet.space.root
    git(quiet.root, "worktree", "remove", "--force", str(wt))
    lines: list[str] = []
    with pytest.raises(typer.Exit) as done:
        trigger.ensure_artifacts_current(
            argv=["archive", "--branch", "feat/a", "--dry-run"],
            invoked_subcommand="archive",
            env={},
            repo_root=quiet.root,
            err=lines.append,
        )
    assert done.value.exit_code == 2
    assert "dry run cannot tell" in " ".join(lines)
    assert not wt.exists()
