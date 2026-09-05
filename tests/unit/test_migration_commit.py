"""The atomic commit — *only* the migrated paths (spec §3.D).

In-flight work is a dirty tree by definition; that is the case this feature
exists for. So every fixture here starts from a dirty tree, and the assertions
that carry the weight are about what is **not** in the commit:

- an unrelated **modified** file is still modified and still uncommitted;
- an unrelated **staged** file is not swept in.

A fixture with a clean tree would pass against `git add -A` and prove nothing,
which is the whole reason the spec spells this out. `git add -A` fails the
first; a plain `git commit -m` after a path-scoped `git add` fails the second,
because a plain commit records the *whole index*.

The migration these run is the real one (`MIGRATIONS`, the shipped registry):
a plan whose `fr_version` ceiling excludes the installed major. Nothing here
uses a fake report except where the point is a report with no changed paths.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from fr.artifacts import run_migrations, trigger
from fr.artifacts.commit import (
    CommitOutcome,
    commit_migration,
    migration_commit_message,
    on_default_branch,
    uncommitted_veto,
)
from fr.artifacts.runner import MigrationReport, PlannedAction
from fr.cli import app
from typer.testing import CliRunner

# --- fixtures ------------------------------------------------------------


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _plan(root: Path, slug: str = "p", *, fr_version: str = ">=3.0.0,<4.0.0") -> Path:
    d = root / "docs" / "superpowers" / "plans" / slug
    d.mkdir(parents=True, exist_ok=True)
    p = d / "_meta.yaml"
    p.write_text(
        f"schema_version: 2\nplan: {slug}\ntarget_repo: derio-net/super-fr\n"
        f"fr_version: '{fr_version}'\n"
    )
    return p


def _repo(tmp_path: Path, *, branch: str = "feat/in-flight") -> Path:
    """A real git repo with a stale plan and two unrelated tracked files.

    Seeded on `main` and then moved onto a FEATURE branch, because that is
    where the work this feature serves happens — and because `commit_migration`
    now refuses on the repository's default branch (an automatic commit on
    `main` is something the operator has to notice and undo). The
    default-branch refusal has its own tests below.
    """
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _plan(root)
    (root / "unrelated-modified.md").write_text("original\n")
    (root / "unrelated-staged.md").write_text("original\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")
    if branch != "main":
        _git(root, "checkout", "-q", "-b", branch)
    return root


def _dirty(root: Path) -> None:
    """In-flight work: one file modified, one modified AND staged."""
    (root / "unrelated-modified.md").write_text("in-flight edit\n")
    (root / "unrelated-staged.md").write_text("staged edit\n")
    _git(root, "add", "--", "unrelated-staged.md")


def _committed_paths(root: Path) -> list[str]:
    return sorted(_git(root, "show", "--name-only", "--format=", "HEAD").splitlines())


def _at_head(root: Path, path: str) -> str:
    """Verbatim blob at HEAD — unstripped, so a trailing newline still counts."""
    return subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _migrate(root: Path) -> MigrationReport:
    report = run_migrations(root, dry_run=False)
    assert report.ok and report.applied, "fixture drift: the shipped repair did not apply"
    return report


# --- the commit contains only the migrated paths -------------------------


def test_the_commit_contains_only_the_paths_the_migration_rewrote(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _dirty(root)
    before = _git(root, "rev-parse", "HEAD")

    outcome = commit_migration(root, _migrate(root))

    assert outcome.committed
    assert _git(root, "rev-parse", "HEAD") != before
    assert _committed_paths(root) == ["docs/superpowers/plans/p/_meta.yaml"]


def test_an_unrelated_modified_file_stays_modified_and_uncommitted(tmp_path: Path) -> None:
    """The assertion `git add -A` cannot survive."""
    root = _repo(tmp_path)
    _dirty(root)

    commit_migration(root, _migrate(root))

    assert (root / "unrelated-modified.md").read_text() == "in-flight edit\n", (
        "the operator's in-flight edit was altered"
    )
    assert _at_head(root, "unrelated-modified.md") == "original\n", (
        "the in-flight edit was swept into the migration commit"
    )
    unstaged = _git(root, "diff", "--name-only").splitlines()
    staged = _git(root, "diff", "--cached", "--name-only").splitlines()
    assert "unrelated-modified.md" in unstaged, "still modified in the working tree"
    assert "unrelated-modified.md" not in staged, "and still uncommitted, not even staged"


def test_an_unrelated_staged_file_is_not_swept_in(tmp_path: Path) -> None:
    """The assertion a plain `git commit -m` cannot survive.

    A plain commit records the whole index, so a file the operator staged
    before running the command would ride along. The commit has to be
    pathspec-scoped, not merely the staging.
    """
    root = _repo(tmp_path)
    _dirty(root)

    commit_migration(root, _migrate(root))

    assert _at_head(root, "unrelated-staged.md") == "original\n", (
        "a file the operator had staged was committed by the migration"
    )
    assert "unrelated-staged.md" in _git(root, "diff", "--cached", "--name-only"), (
        "the operator's staged change must survive, still staged"
    )


def test_the_migrated_content_is_what_landed(tmp_path: Path) -> None:
    """Path-scoping must not cost correctness: HEAD carries the new ceiling."""
    root = _repo(tmp_path)
    _dirty(root)

    commit_migration(root, _migrate(root))

    assert "<5.0.0" in _at_head(root, "docs/superpowers/plans/p/_meta.yaml")


# --- the cases that must not commit --------------------------------------


def test_not_a_git_repo_migrates_without_committing_and_does_not_crash(tmp_path: Path) -> None:
    root = tmp_path / "loose"
    root.mkdir()
    p = _plan(root)

    outcome = commit_migration(root, _migrate(root))

    assert isinstance(outcome, CommitOutcome)
    assert not outcome.committed
    assert "git" in outcome.reason.lower()
    assert "<5.0.0" in p.read_text(), "the migration itself must still have happened"


def test_nothing_changed_makes_no_empty_commit(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _dirty(root)
    before = _git(root, "rev-parse", "HEAD")

    outcome = commit_migration(root, MigrationReport(dry_run=False))

    assert not outcome.committed
    assert _git(root, "rev-parse", "HEAD") == before


def test_a_report_whose_paths_are_already_committed_makes_no_empty_commit(
    tmp_path: Path,
) -> None:
    """Second run, same report: the files match HEAD, so there is nothing to do.

    This is the commit half of idempotence — `fr migrate artifacts --yes`
    followed by an `fr` command must not leave two commits, one of them empty.
    """
    root = _repo(tmp_path)
    report = _migrate(root)
    assert commit_migration(root, report).committed
    before = _git(root, "rev-parse", "HEAD")

    outcome = commit_migration(root, report)

    assert not outcome.committed
    assert _git(root, "rev-parse", "HEAD") == before


def test_a_path_outside_the_repo_is_refused_rather_than_committed(tmp_path: Path) -> None:
    """Precondition, asserted rather than assumed: this writes to git history."""
    root = _repo(tmp_path)
    outside = tmp_path / "elsewhere.yaml"
    outside.write_text("x\n")
    report = MigrationReport(
        dry_run=False,
        applied=(PlannedAction(kind="plan", path=outside, summary="s", repair="r"),),
    )

    outcome = commit_migration(root, report)

    assert not outcome.committed
    assert "outside" in outcome.reason.lower()


# --- the generated message -----------------------------------------------


def test_the_message_names_the_kinds_and_the_transition() -> None:
    report = MigrationReport(
        dry_run=False,
        applied=(
            PlannedAction(
                kind="journal", path=Path("a.md"), summary="s", from_version=1, to_version=2
            ),
            PlannedAction(
                kind="journal", path=Path("b.md"), summary="s", from_version=1, to_version=2
            ),
            PlannedAction(kind="plan", path=Path("c.yaml"), summary="s", repair="widen-ceiling"),
        ),
    )

    message = migration_commit_message(report, fr_version="4.0.0")
    subject, body = message.split("\n", 1)

    assert subject == "chore(fr): migrate 3 artifacts to fr 4.0.0"
    assert "journal: schema 1 -> 2 (2 files)" in body
    assert "plan: repair widen-ceiling (1 file)" in body


def test_the_message_is_singular_for_one_artifact() -> None:
    report = MigrationReport(
        dry_run=False,
        applied=(PlannedAction(kind="plan", path=Path("c.yaml"), summary="s", repair="r"),),
    )
    assert migration_commit_message(report, fr_version="4.0.0").startswith(
        "chore(fr): migrate 1 artifact to fr 4.0.0"
    )


def test_the_real_commit_carries_the_generated_message(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _dirty(root)

    outcome = commit_migration(root, _migrate(root))

    subject = _git(root, "log", "-1", "--format=%s")
    assert subject.startswith("chore(fr): migrate 1 artifact to fr ")
    assert outcome.message is not None
    assert _git(root, "log", "-1", "--format=%B").strip() == outcome.message.strip()
    assert "plan: repair widen-fr-version-ceiling (1 file)" in _git(
        root, "log", "-1", "--format=%B"
    )


# --- wired to the CLI-entry gate -----------------------------------------


def test_the_cli_entry_gate_commits_the_migration_it_made(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The end-to-end shape of spec §3.C + §3.D, through the real typer app.

    Everything above tests `commit_migration` directly; this is the one that
    would fail if the gate stopped calling it, or called something else. The
    tree is dirty, as it always is in the case this feature exists for.
    """
    root = _repo(tmp_path)
    _dirty(root)
    before = _git(root, "rev-parse", "HEAD")

    monkeypatch.delenv("FR_SKIP_MIGRATION", raising=False)
    monkeypatch.delenv("CI", raising=False)
    # NOT `fr skills` any more: `skills` is read-only and therefore exempt from
    # the gate (review r4-f5). `models get` is an ordinary, non-exempt command.
    argv = ["models", "get", "--harness", "claude-code"]
    monkeypatch.setattr(sys, "argv", ["fr", *argv])
    monkeypatch.setattr(trigger, "is_interactive", lambda **k: True)
    result = CliRunner().invoke(app, argv, env={"VK_REPO_ROOT": str(root)})

    assert result.exit_code == 0, result.output
    assert "claude-code" in result.output, "the typed command must still run"
    assert _git(root, "rev-parse", "HEAD") != before
    assert _committed_paths(root) == ["docs/superpowers/plans/p/_meta.yaml"]
    assert _at_head(root, "unrelated-modified.md") == "original\n"
    assert _at_head(root, "unrelated-staged.md") == "original\n"


# --- review r4-f5: never on the default branch ---------------------------


def test_the_commit_refuses_on_the_repositorys_default_branch(tmp_path: Path) -> None:
    """`fr` run in the base clone on `main` produced a real local commit on a
    protected branch — made automatically, before a command the operator typed
    for some other reason, and left for them to notice and undo.

    Everything else in this module is fail-closed for smaller reasons than
    this one. Migrating is the recoverable half; committing to `main` is not.
    """
    root = _repo(tmp_path, branch="main")
    before = _git(root, "rev-parse", "HEAD")

    outcome = commit_migration(root, _migrate(root))

    assert not outcome.committed
    assert "main" in outcome.reason and "default branch" in outcome.reason
    assert _git(root, "rev-parse", "HEAD") == before, "no commit on the default branch"


def test_on_default_branch_names_the_branch_or_returns_none(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    on_main = _repo(tmp_path / "a", branch="main")
    on_feature = _repo(tmp_path / "b", branch="feat/x")

    assert on_default_branch(on_main) == "main"
    assert on_default_branch(on_feature) is None
    assert on_default_branch(tmp_path / "not-a-repo") is None


def test_origin_head_outranks_the_well_known_names(tmp_path: Path) -> None:
    """A repo whose default branch is `trunk` must be protected as such, and a
    repo on `main` whose remote says otherwise must not be."""
    root = _repo(tmp_path, branch="trunk")
    _git(root, "remote", "add", "origin", str(root))
    _git(root, "update-ref", "refs/remotes/origin/trunk", "HEAD")
    _git(root, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")

    assert on_default_branch(root) == "trunk"

    _git(root, "checkout", "-q", "main")
    assert on_default_branch(root) is None, "origin/HEAD is the authority, not the name"


# --- review r4-f2: the operator's own edit to a migrated artifact ---------


def test_an_artifact_the_operator_is_editing_is_held_back_not_swept_in(tmp_path: Path) -> None:
    """The case this module most needs to handle, and the one it got wrong.

    `git add -- <path>` stages the WHOLE file. An operator half-way through
    editing a stale `_meta.yaml` who types any `fr` command therefore got their
    unfinished edit committed under `chore(fr): migrate ...`.

    Resolved by refusing to migrate a file that already has uncommitted
    changes, rather than by migrating it and leaving it out of the commit: the
    edit is the operator's, fr cannot know whether it is finished, and a
    migration silently rewritten into a file someone is typing in is worse than
    a refusal that names it. `FR_SKIP_MIGRATION=1` and `fr migrate artifacts`
    both remain available.
    """
    root = _repo(tmp_path)
    meta = root / "docs" / "superpowers" / "plans" / "p" / "_meta.yaml"
    meta.write_text(meta.read_text() + "workflow: fr-goal@1\n")  # half-typed, unsaved anywhere

    report = run_migrations(root, dry_run=False, veto=uncommitted_veto(root))

    assert report.applied == ()
    assert [f.path for f in report.failed] == [meta]
    assert "uncommitted" in report.failed[0].error
    assert "workflow: fr-goal@1" in meta.read_text(), "the operator's edit is untouched"
    assert "<4.0.0" in meta.read_text(), "and the artifact was not migrated under it"


def test_the_veto_only_holds_back_the_file_the_operator_touched(tmp_path: Path) -> None:
    """Invariant 3 again: one artifact's hold is one artifact's hold."""
    root = _repo(tmp_path)
    edited = root / "docs" / "superpowers" / "plans" / "p" / "_meta.yaml"
    untouched = _plan(root, "zzz-other")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "second plan")
    edited.write_text(edited.read_text() + "workflow: fr-goal@1\n")

    report = run_migrations(root, dry_run=False, veto=uncommitted_veto(root))

    assert [a.path for a in report.applied] == [untouched]
    assert [f.path for f in report.failed] == [edited]


def test_an_unrelated_dirty_file_does_not_hold_back_a_clean_artifact(tmp_path: Path) -> None:
    """The veto is path-scoped, like the commit. A dirty tree is the normal
    state for in-flight work; only a dirty ARTIFACT is a conflict."""
    root = _repo(tmp_path)
    _dirty(root)
    meta = root / "docs" / "superpowers" / "plans" / "p" / "_meta.yaml"

    report = run_migrations(root, dry_run=False, veto=uncommitted_veto(root))

    assert [a.path for a in report.applied] == [meta]
    assert report.failed == ()


def test_the_gate_never_commits_the_operators_edit_to_a_migrated_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """r4-f2, end to end through the real app and a real git repo.

    The scenario the reviewer named: an operator adding `workflow:` to a stale
    `_meta.yaml` types an `fr` command mid-edit. Before the veto, the gate
    migrated the file and `git add -- <path>` staged the whole thing, so their
    half-typed line landed in a `chore(fr): migrate ...` commit they never made.
    """
    root = _repo(tmp_path)
    meta = root / "docs" / "superpowers" / "plans" / "p" / "_meta.yaml"
    meta.write_text(meta.read_text() + "workflow: fr-goal@1\n")
    before_head = _git(root, "rev-parse", "HEAD")
    before_text = meta.read_text()

    argv = ["models", "get", "--harness", "claude-code"]
    monkeypatch.delenv("FR_SKIP_MIGRATION", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(sys, "argv", ["fr", *argv])
    monkeypatch.setattr(trigger, "is_interactive", lambda **k: True)
    result = CliRunner().invoke(app, argv, env={"VK_REPO_ROOT": str(root)})

    assert result.exit_code == 2, "a held-back artifact is a refusal, not a silent skip"
    assert _git(root, "rev-parse", "HEAD") == before_head, "nothing was committed"
    assert meta.read_text() == before_text, "and nothing was rewritten under the operator"


def test_the_gate_never_commits_on_the_default_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """r4-f5, end to end: the base clone on `main` is left exactly as it was."""
    root = _repo(tmp_path, branch="main")
    before_head = _git(root, "rev-parse", "HEAD")
    meta = root / "docs" / "superpowers" / "plans" / "p" / "_meta.yaml"
    before_text = meta.read_text()

    argv = ["models", "get", "--harness", "claude-code"]
    monkeypatch.delenv("FR_SKIP_MIGRATION", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(sys, "argv", ["fr", *argv])
    monkeypatch.setattr(trigger, "is_interactive", lambda **k: True)
    result = CliRunner().invoke(app, argv, env={"VK_REPO_ROOT": str(root)})

    assert result.exit_code == 2
    assert _git(root, "rev-parse", "HEAD") == before_head
    assert meta.read_text() == before_text


# =========================================================================
# `git_context` — the fail-closed boundary (review r5-c1/c2/c3, r5-e6)
# =========================================================================
#
# Before it, every predicate here shelled out for itself and swallowed its own
# failures, so "git is not on PATH" and "dubious ownership" were
# indistinguishable from "not a git repository": the default-branch guard
# vanished, the uncommitted-file veto returned an empty set (i.e. "your tree is
# clean"), and the reason string said "is not a git repository" about a repo
# that plainly was one.


def _ctx(root: Path):
    from fr.artifacts.commit import git_context

    return git_context(root)


def test_a_genuine_non_repo_directory_still_reads_as_no_repo(tmp_path: Path) -> None:
    """The one failure that must NOT become a refusal: an ordinary directory.
    The caller migrates it and simply does not commit."""
    from fr.artifacts.commit import NoRepo

    plain = tmp_path / "not-a-repo"
    plain.mkdir()

    assert isinstance(_ctx(plain), NoRepo)


def test_git_missing_from_path_refuses_without_claiming_there_is_no_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """r5-c2's headline: `_toplevel` returned None for ANY failure, so a
    missing git read as "not a repository" — and the message said so."""
    from fr.artifacts.commit import GitRefusal

    root = _repo(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))

    state = _ctx(root)

    assert isinstance(state, GitRefusal)
    assert "not a git repository" not in state.reason.lower()
    assert "PATH" in state.reason


def test_a_broken_repository_refuses_rather_than_reading_as_clean(tmp_path: Path) -> None:
    """A repo git recognises but cannot answer for — the class that includes
    `safe.directory` "dubious ownership", common in pods with a uid mismatch.
    A truncated `.git/config` reproduces it deterministically and without
    needing a second uid: git says `fatal: bad config line ...`, which is NOT
    "not a git repository"."""
    from fr.artifacts.commit import GitRefusal, NoRepo

    root = _repo(tmp_path)
    (root / ".git" / "config").write_text("[core\nrepositoryformatversion = 0\n")

    state = _ctx(root)

    assert not isinstance(state, NoRepo)
    assert isinstance(state, GitRefusal)
    assert "not a git repository" not in state.reason.lower()


def test_uncommitted_paths_raises_instead_of_reporting_a_clean_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The veto list is the one place an empty set is the most dangerous
    possible default: it means "nothing is being edited, migrate everything"."""
    from fr.artifacts.commit import GitUnavailableError, uncommitted_paths

    root = _repo(tmp_path)
    _dirty(root)
    assert uncommitted_paths(root), "fixture drift: the tree should be dirty"
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))

    with pytest.raises(GitUnavailableError):
        uncommitted_paths(root)


def test_a_linked_worktree_is_a_first_class_case(tmp_path: Path) -> None:
    """fr's OWN isolation workspace is a linked worktree, where `.git` is a
    FILE. Any logic that looked for a `.git` DIRECTORY would be broken in the
    primary use case (review r5-e6)."""
    from fr.artifacts.commit import GitContext

    root = _repo(tmp_path, branch="main")
    wt = tmp_path / "linked"
    _git(root, "worktree", "add", "-q", "-b", "feat/linked", str(wt))
    assert (wt / ".git").is_file(), "fixture drift: a linked worktree has a .git FILE"

    state = _ctx(wt)

    assert isinstance(state, GitContext)
    assert state.toplevel == wt.resolve()
    assert state.branch == "feat/linked"
    assert state.default_branch == "main"


def test_a_bare_repository_is_refused(tmp_path: Path) -> None:
    from fr.artifacts.commit import GitRefusal

    bare = tmp_path / "bare.git"
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)

    state = _ctx(bare)

    assert isinstance(state, GitRefusal)
    assert "bare" in state.reason


def test_a_nested_repository_resolves_to_the_inner_one(tmp_path: Path) -> None:
    from fr.artifacts.commit import GitContext

    outer = _repo(tmp_path)
    inner = outer / "vendor" / "thing"
    inner.mkdir(parents=True)
    _git(inner, "init", "-q", "-b", "main")

    state = _ctx(inner)

    assert isinstance(state, GitContext)
    assert state.toplevel == inner.resolve()


@pytest.mark.parametrize("var", ["GIT_DIR", "GIT_WORK_TREE"])
def test_an_overridden_git_scope_is_refused_not_silently_honoured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, var: str
) -> None:
    """ "Honour or refuse, never silently mis-scope" — fr refuses, because the
    next thing it would do is `git add` a path list computed against a
    different tree than the one git would commit from."""
    from fr.artifacts.commit import GitRefusal

    root = _repo(tmp_path)
    monkeypatch.setenv(var, str(tmp_path / "elsewhere"))

    state = _ctx(root)

    assert isinstance(state, GitRefusal)
    assert var in state.reason


def test_an_unborn_branch_is_reported_as_the_default(tmp_path: Path) -> None:
    """`git init -b main` with no commits: no ref exists, so "does the branch
    exist" cannot be asked — but HEAD points at it, so it IS the default."""
    from fr.artifacts.commit import GitContext

    root = tmp_path / "fresh"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")

    state = _ctx(root)

    assert isinstance(state, GitContext)
    assert state.branch == "main"
    assert state.default_branch == "main"
    assert state.has_head is False


def test_a_default_branch_with_a_slash_survives_prefix_stripping(tmp_path: Path) -> None:
    """`origin/release/main` must strip only the REMOTE prefix, once."""
    from fr.artifacts.commit import GitContext

    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "release/main", str(origin)], check=True)
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(origin), str(work))
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "T")
    (work / "seed.md").write_text("x\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "seed")
    _git(work, "push", "-q", "-u", "origin", "HEAD")
    _git(work, "remote", "set-head", "origin", "--auto")

    state = _ctx(work)

    assert isinstance(state, GitContext)
    assert state.default_branch == "release/main"


def test_init_default_branch_is_ignored_when_that_branch_does_not_exist(
    tmp_path: Path,
) -> None:
    """r5-c3, config one: a global `init.defaultBranch = main` in a repo that
    only has `master`. Trusting it reported `main`, so the guard that refuses
    on the default branch let an automatic commit land on `master`."""
    from fr.artifacts.commit import GitContext

    root = tmp_path / "master-only"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "init.defaultBranch", "main")
    (root / "seed.md").write_text("x\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")

    state = _ctx(root)

    assert isinstance(state, GitContext)
    assert state.default_branch == "master"


def test_a_remote_without_head_beats_a_local_well_known_name(tmp_path: Path) -> None:
    """r5-c3, config two: trunk is `trunk`, `origin/HEAD` is unset, and a
    local `main` exists. The old order answered `main`, so the automatic
    commit landed on the real trunk."""
    from fr.artifacts.commit import GitContext

    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "trunk", str(origin)], check=True)
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(origin), str(work))
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "T")
    (work / "seed.md").write_text("x\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "seed")
    _git(work, "push", "-q", "-u", "origin", "HEAD")
    _git(work, "checkout", "-q", "-b", "main")
    _git(work, "checkout", "-q", "trunk")
    # No `remote set-head`: this is a clone whose origin/HEAD was never set.
    subprocess.run(["git", "-C", str(work), "remote", "set-head", "origin", "-d"], check=False)

    state = _ctx(work)

    assert isinstance(state, GitContext)
    assert state.default_branch == "trunk"


def test_a_dangling_remote_head_is_not_trusted(tmp_path: Path) -> None:
    """A deleted default branch leaves `origin/HEAD` pointing at nothing."""
    from fr.artifacts.commit import GitContext

    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(origin)], check=True)
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(origin), str(work))
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "T")
    (work / "seed.md").write_text("x\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "seed")
    _git(work, "push", "-q", "-u", "origin", "HEAD")
    _git(work, "remote", "set-head", "origin", "--auto")
    (work / ".git" / "refs" / "remotes" / "origin" / "HEAD").write_text(
        "ref: refs/remotes/origin/gone\n"
    )

    state = _ctx(work)

    assert isinstance(state, GitContext)
    # Falls through to the remote well-knowns, which DO exist.
    assert state.default_branch == "main"


def test_a_single_non_origin_remote_is_used(tmp_path: Path) -> None:
    from fr.artifacts.commit import GitContext

    upstream = tmp_path / "upstream.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(upstream)], check=True)
    work = _repo(tmp_path, branch="feat/x")
    _git(work, "remote", "add", "upstream", str(upstream))
    _git(work, "push", "-q", "upstream", "main")
    _git(work, "fetch", "-q", "upstream")

    state = _ctx(work)

    assert isinstance(state, GitContext)
    assert state.default_branch == "main"


def test_two_remotes_with_no_default_remote_configured_refuses(tmp_path: Path) -> None:
    from fr.artifacts.commit import GitRefusal

    work = _repo(tmp_path, branch="feat/x")
    for name in ("alpha", "beta"):
        bare = tmp_path / f"{name}.git"
        subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(bare)], check=True)
        _git(work, "remote", "add", name, str(bare))

    state = _ctx(work)

    assert isinstance(state, GitRefusal)
    assert "checkout.defaultRemote" in state.reason


def test_checkout_default_remote_picks_the_remote(tmp_path: Path) -> None:
    from fr.artifacts.commit import GitContext

    work = _repo(tmp_path, branch="feat/x")
    for name, head in (("alpha", "alpha-trunk"), ("beta", "main")):
        bare = tmp_path / f"{name}.git"
        subprocess.run(["git", "init", "--bare", "-q", "-b", head, str(bare)], check=True)
        _git(work, "remote", "add", name, str(bare))
    _git(work, "push", "-q", "beta", "main")
    _git(work, "fetch", "-q", "beta")
    _git(work, "config", "checkout.defaultRemote", "beta")

    state = _ctx(work)

    assert isinstance(state, GitContext)
    assert state.default_branch == "main"


# --- C1: a detached HEAD must not get an automatic commit -----------------


def test_a_detached_head_is_refused_by_commit_migration(tmp_path: Path) -> None:
    """The old comment claimed a detached HEAD "never reaches the automatic
    commit path anyway". `git rebase -i` stops detached, and so does
    `git bisect` — both interactive, both with a TTY."""
    root = _repo(tmp_path)
    _plan(root, "q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "second")
    report = _migrate(root)
    _git(root, "checkout", "-q", "--detach")

    outcome = commit_migration(root, report)

    assert outcome.committed is False
    assert "detached" in outcome.reason


def test_the_gate_refuses_on_a_detached_head(tmp_path: Path) -> None:
    """And the gate refuses BEFORE migrating, so the rebase's tree is not
    rewritten under it either."""
    root = _repo(tmp_path)
    plan = root / "docs" / "superpowers" / "plans" / "p" / "_meta.yaml"
    before = plan.read_text()
    _git(root, "checkout", "-q", "--detach")

    with pytest.raises(SystemExit if False else Exception) as e:  # typer.Exit
        trigger.ensure_artifacts_current(
            argv=["apply"],
            invoked_subcommand="apply",
            env={},
            repo_root=root,
            interactive=True,
            commit=lambda r, report: None,
        )

    assert getattr(e.value, "exit_code", None) == 2
    assert plan.read_text() == before


def test_on_default_branch_stays_a_thin_boolean_wrapper(tmp_path: Path) -> None:
    """Kept for callers that want the one fact. It cannot express a refusal,
    which is exactly why the gate calls `git_context` instead."""
    root = _repo(tmp_path, branch="main")
    assert on_default_branch(root) == "main"
    _git(root, "checkout", "-q", "-b", "feat/y")
    assert on_default_branch(root) is None
