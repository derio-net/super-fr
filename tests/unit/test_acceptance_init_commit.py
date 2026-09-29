"""gh#775, reopened after take 10 (#817) — two independent causes, pinned apart.

- **A** — `fr acceptance init` was the one fr writer that never went through
  `commit_records` (gh#610): it wrote the matrix, the rule, the reports and a
  `.gitignore` line and committed none of them. The next command committed only
  its own paths (the matrix and reports), so the rule file and `.gitignore` sat
  dirty until close-out stashed them. It also filed the `.gitignore` it had only
  appended to under `created`.
- **B** — nothing refused a row whose "verification" was one of fr's own
  pipeline artifacts (take 10's `basket-single-phase` cited the plan's
  `01.yaml` as its unit test). Such a row states how the pipeline must run, not
  what the product does. A level ref into `docs/superpowers/` is now refused
  where rows are WRITTEN, so no existing matrix stops parsing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.acceptance.scaffold import init
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import make_repo, row

runner = CliRunner()


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def _repo_on_branch(tmp_path: Path, *, gitignore: str | None = None) -> Path:
    """A git repo with one commit on `main` and a feature branch checked out:
    fr refuses to commit on the default branch, as every run's workspace does not."""
    root = tmp_path / "demo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    _git(root, "remote", "add", "origin", "https://gitlab.com/example-org/demo.git")
    (root / "README.md").write_text("demo\n")
    if gitignore is not None:
        (root / ".gitignore").write_text(gitignore)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    _git(root, "checkout", "-q", "-b", "feat/x")
    return root


def _init(root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    return runner.invoke(app, ["acceptance", "init"])


# ── A: init commits every file it writes, and says created vs modified ─────


def test_init_commits_every_file_it_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo_on_branch(tmp_path, gitignore="node_modules/\n")
    result = _init(root, monkeypatch)
    assert result.exit_code == 0, result.output
    assert _git(root, "status", "--porcelain") == "", "init left its writes uncommitted"
    committed = set(_git(root, "show", "--name-only", "--format=", "HEAD").split())
    assert ".claude/rules/acceptance-matrix.md" in committed
    assert ".gitignore" in committed
    assert "docs/acceptance/matrix.yaml" in committed


def test_init_reports_an_appended_gitignore_as_modified_not_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo_on_branch(tmp_path, gitignore="node_modules/\n")
    result = _init(root, monkeypatch)
    assert result.exit_code == 0, result.output
    assert "modified .gitignore" in result.output
    assert "created .gitignore" not in result.output
    assert "created .claude/rules/acceptance-matrix.md" in result.output


def test_init_reports_a_new_gitignore_as_created(tmp_path: Path) -> None:
    root = _repo_on_branch(tmp_path)
    outcome = init(root, "example-org", "demo", backend="gitlab")
    assert ".gitignore" in outcome.created
    assert ".gitignore" not in outcome.modified


def test_rerunning_init_makes_no_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo_on_branch(tmp_path)
    assert _init(root, monkeypatch).exit_code == 0
    head = _git(root, "rev-parse", "HEAD")
    again = _init(root, monkeypatch)
    assert again.exit_code == 0, again.output
    assert _git(root, "rev-parse", "HEAD") == head


def test_init_on_the_default_branch_writes_but_says_it_did_not_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo_on_branch(tmp_path)
    _git(root, "checkout", "-q", "main")
    result = _init(root, monkeypatch)
    assert result.exit_code == 0, result.output  # losing the commit never loses the write
    assert (root / "docs/acceptance/matrix.yaml").is_file()
    assert "not committed" in result.output


# ── B: a pipeline artifact is not verification ─────────────────────────────


@pytest.mark.parametrize(
    "ref",
    [
        "own:docs/superpowers/plans/2026-09-29-basket/01.yaml",
        "own:docs/superpowers/runs/r1.yaml",
        "own:docs/superpowers/journals/plans/p.md",
        "own:docs/superpowers/specs/s.md",
    ],
)
def test_add_refuses_a_level_ref_into_the_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ref: str
) -> None:
    root = make_repo(tmp_path, "")
    before = (root / "docs/acceptance/matrix.yaml").read_text()
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    result = runner.invoke(
        app,
        [
            "acceptance", "add", "--id", "basket-single-phase", "--capability", "Cap",
            "--acceptance", "The run delivers the feature in one phase",
            "--origin", "own:docs/superpowers/specs/s.md", "--level", f"unit={ref}",
            "--status", "not-implemented",
        ],
    )  # fmt: skip
    assert result.exit_code == 2, result.output
    assert "process directive" in result.output
    assert (root / "docs/acceptance/matrix.yaml").read_text() == before


def test_set_status_refuses_adding_a_pipeline_level_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row(status="not-implemented"))
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    result = runner.invoke(
        app,
        [
            "acceptance", "set-status", "--id", "r1", "--status", "skipped",
            "--notes", "x", "--level", "int=own:docs/superpowers/plans/p/01.yaml",
        ],
    )  # fmt: skip
    assert result.exit_code == 2, result.output
    assert "process directive" in result.output


def test_live_evidence_under_docs_acceptance_is_still_a_level_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """This repo's own matrix cites `docs/acceptance/evidence/*.md` as `int`
    evidence — a captured live run, which IS verification."""
    root = make_repo(tmp_path, "")
    (root / "docs/acceptance/evidence").mkdir()
    (root / "docs/acceptance/evidence/live.md").write_text("# live\n")
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    result = runner.invoke(
        app,
        [
            "acceptance", "add", "--id", "r2", "--capability", "Cap",
            "--acceptance", "Operator can do Y", "--origin", "own:docs/superpowers/specs/s.md",
            "--level", "int=own:docs/acceptance/evidence/live.md", "--status", "skipped",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def test_a_legacy_pipeline_ref_does_not_block_moving_its_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refused where written, not where loaded: a row already carrying one can
    still move, so no existing matrix is stranded (no matrix version bump)."""
    root = make_repo(
        tmp_path,
        row(unit='"own:docs/superpowers/specs/s.md"', status="not-implemented"),
    )
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    result = runner.invoke(
        app, ["acceptance", "set-status", "--id", "r1", "--status", "skipped", "--notes", "x"]
    )
    assert result.exit_code == 0, result.output
