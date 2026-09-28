"""§A of the 2026-09-28-closeout-always spec: `branch_changed_paths` (the
first half of `branch_changes_present`, lifted out) and `fr.closeout.
branch_artifacts` (pure classification of the changed paths into live
artifacts). Real git throughout — no mocked git (#696/#727/#716 all hardened
`branch_changes_present`'s single diff path; a mock here could not catch a
drift from it)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fr.closeout import BranchArtifact, branch_artifacts
from fr.isolation.local import (
    branch_changed_paths,
    branch_changes_present,
    subprocess_runner,
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def _write(repo: Path, rel: str, content: str = "x\n") -> Path:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


def _commit(repo: Path, msg: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qm", msg)


def _repo(tmp_path: Path) -> Path:
    """A clone on `main`, with `origin/main` set up and an existing plan file
    plus an existing spec committed — the shape a feature branch forks from."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _write(repo, "docs/superpowers/plans/existing-plan/_meta.yaml", "schema_version: 2\n")
    _write(repo, "docs/superpowers/specs/existing-spec-design.md", "# existing\n")
    _commit(repo, "seed")
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "remote", "set-head", "origin", "main")
    return repo


def test_branch_changed_paths_matches_branch_changes_present(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feat")
    _write(repo, "docs/superpowers/journals/debug/x.md", "# x\n")
    _write(repo, "docs/superpowers/plans/existing-plan/_meta.yaml", "schema_version: 2\nx: 1\n")
    (repo / "docs/superpowers/specs/existing-spec-design.md").unlink()
    _commit(repo, "feat work")

    changed = branch_changed_paths(subprocess_runner, repo, "feat", "origin/main")
    verified = branch_changes_present(subprocess_runner, repo, "feat", "origin/main")

    assert sorted(changed) == sorted(verified.changed)
    assert sorted(changed) == sorted(
        [
            "docs/superpowers/journals/debug/x.md",
            "docs/superpowers/plans/existing-plan/_meta.yaml",
            "docs/superpowers/specs/existing-spec-design.md",
        ]
    )


def test_branch_artifacts_collapses_plan_dir_drops_deletions_and_non_artifacts(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feat")
    _write(repo, "docs/superpowers/plans/new-plan/_meta.yaml", "schema_version: 2\n")
    _write(repo, "docs/superpowers/plans/new-plan/01.yaml", "tasks: []\n")
    _write(repo, "docs/superpowers/specs/new-spec-design.md", "# new\n")
    _write(repo, "docs/superpowers/journals/specs/new-spec.md", "# journal\n")
    _write(repo, "docs/superpowers/journals/plans/new-plan.md", "# journal\n")
    _write(repo, "docs/superpowers/journals/debug/dbg.md", "# journal\n")
    _write(repo, "docs/superpowers/runs/2026-09-28-run.yaml", "run: x\n")
    _write(repo, "docs/superpowers/runs/2026-09-28-run.records/step.yaml", "outcome: done\n")
    _write(repo, "docs/superpowers/usage/2026-09-28-run.yaml", "usage: x\n")
    _write(repo, "packages/fr/src/fr/closeout.py", "# not an artifact\n")
    (repo / "docs/superpowers/specs/existing-spec-design.md").unlink()
    _commit(repo, "feat work")

    changed = branch_changed_paths(subprocess_runner, repo, "feat", "origin/main")
    artifacts = branch_artifacts(repo, changed)

    assert (
        BranchArtifact(kind="plan", path=Path("docs/superpowers/plans/new-plan"), owner="new-plan")
        in artifacts
    )
    assert (
        BranchArtifact(
            kind="spec", path=Path("docs/superpowers/specs/new-spec-design.md"), owner=None
        )
        in artifacts
    )
    assert (
        BranchArtifact(
            kind="journal", path=Path("docs/superpowers/journals/specs/new-spec.md"), owner="spec"
        )
        in artifacts
    )
    assert (
        BranchArtifact(
            kind="journal",
            path=Path("docs/superpowers/journals/plans/new-plan.md"),
            owner="plan",
        )
        in artifacts
    )
    assert (
        BranchArtifact(
            kind="journal", path=Path("docs/superpowers/journals/debug/dbg.md"), owner="debug"
        )
        in artifacts
    )
    assert (
        BranchArtifact(
            kind="run", path=Path("docs/superpowers/runs/2026-09-28-run.yaml"), owner=None
        )
        in artifacts
    )
    assert (
        BranchArtifact(
            kind="usage", path=Path("docs/superpowers/usage/2026-09-28-run.yaml"), owner=None
        )
        in artifacts
    )
    # exactly one plan artifact even though two files changed under it
    assert sum(1 for a in artifacts if a.kind == "plan") == 1
    # deleted spec, the records file, and the non-artifact path are all dropped
    kept_paths = {a.path for a in artifacts}
    assert Path("docs/superpowers/specs/existing-spec-design.md") not in kept_paths
    assert not any("records" in str(a.path) for a in artifacts)
    assert Path("packages/fr/src/fr/closeout.py") not in kept_paths
    assert len(artifacts) == 7


def test_every_journal_scope_is_classified(tmp_path: Path) -> None:
    """A journal scope added to fr.journal.model.SCOPE_DIRS is classified with
    no edit to fr.closeout: the scope map has one public owner."""
    from fr.journal.model import JOURNALS_REL, SCOPE_DIRS

    changed = []
    for dirname in SCOPE_DIRS.values():
        rel = JOURNALS_REL / dirname / "x.md"
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x\n")
        changed.append(str(rel))
    got = branch_artifacts(tmp_path, changed)
    assert sorted(a.owner or "" for a in got) == sorted(SCOPE_DIRS)
    assert all(a.kind == "journal" for a in got)
