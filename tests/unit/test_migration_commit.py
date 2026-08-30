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
from fr.artifacts.commit import CommitOutcome, commit_migration, migration_commit_message
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


def _repo(tmp_path: Path) -> Path:
    """A real git repo with a stale plan and two unrelated tracked files."""
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
    monkeypatch.setattr(sys, "argv", ["fr", "skills"])
    monkeypatch.setattr(trigger, "is_interactive", lambda **k: True)
    result = CliRunner().invoke(app, ["skills"], env={"VK_REPO_ROOT": str(root)})

    assert result.exit_code == 0, result.output
    assert "Commands" in result.output, "the typed command must still run"
    assert _git(root, "rev-parse", "HEAD") != before
    assert _committed_paths(root) == ["docs/superpowers/plans/p/_meta.yaml"]
    assert _at_head(root, "unrelated-modified.md") == "original\n"
    assert _at_head(root, "unrelated-staged.md") == "original\n"
