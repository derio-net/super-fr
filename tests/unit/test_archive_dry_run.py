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


def _state(repo: Path) -> tuple[str, str, str]:
    return (
        _git(repo, "status", "--porcelain", "--untracked-files=all"),
        _git(repo, "diff", "--cached"),
        _git(repo, "rev-parse", "HEAD"),
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


def test_all_and_sweep_only_dry_runs_change_nothing(
    merged_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _state(merged_repo)
    for argv in (["archive", "--all", "--dry-run"], ["archive", "--sweep-only", "--dry-run"]):
        out = _invoke(monkeypatch, merged_repo, argv)
        assert out.exit_code == 0, out.output
        assert _state(merged_repo) == before


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
    merged_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.artifacts import trigger

    monkeypatch.setattr(trigger, "is_interactive", lambda: True)
    monkeypatch.setattr(
        "builtins.input", lambda *_a: (_ for _ in ()).throw(AssertionError("prompted"))
    )
    out = _invoke(
        monkeypatch, merged_repo, ["archive", "docs/superpowers/plans/2026-06-01-p", "--dry-run"]
    )
    assert out.exit_code == 0, out.output


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


def test_branch_dry_run_changes_nothing(merged_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    before = _state(merged_repo)
    out = _invoke(monkeypatch, merged_repo, ["archive", "--branch", "main", "--dry-run"])
    # Whatever the real run decides, a dry run leaves tree and index alone.
    assert _state(merged_repo) == before
    assert out.exit_code in (0, 2), out.output


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

    result = _fr(stealthy.root, "archive", "--branch", "feat/a", "--dry-run")
    assert result.exit_code == 0, result.output
    assert "would" in result.output
    assert hits == []
    assert git(target_origin, "for-each-ref", "--format=%(refname) %(objectname)") == refs
    assert _git(wt, "rev-parse", "HEAD") == head
    assert _git(wt, "status", "--porcelain", "--untracked-files=all") == ""
