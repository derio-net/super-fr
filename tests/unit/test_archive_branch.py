"""`fr archive --branch <b>` (2026-09-28-closeout-always spec §B).

Every repo here is a real temp git repo whose origin is a bare repo at a FILE
PATH, so the explicit-refspec branch fetch runs for real and never touches a
network. `fr.archive._fetch` (the default-branch fetch inside
`merge_evidence`) is stubbed exactly as in `test_archive_cmd.py`; the merge to
`origin/main` is a real squash merge pushed to the bare origin, then fetched.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from fr.cli import app
from fr.commands import archive_cmd
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient
from tests.unit.test_merge_evidence import _add_remote, _git, _publish, stub_fetch

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
BRANCH = "feat/thing"
SP = Path("docs/superpowers")


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    return stub_fetch(monkeypatch)


# --- fixture helpers ---------------------------------------------------------


def _write(repo: Path, rel: str | Path, text: str) -> Path:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def _commit(repo: Path, msg: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", msg)


def _base(tmp_path: Path, *, remote: bool = True) -> Path:
    """A repo on `main` with one base commit (and a README), published to a
    bare file-path origin when `remote`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _write(repo, "README.md", "base\n")
    _commit(repo, "base")
    if remote:
        _add_remote(repo, tmp_path / "origin.git")
        _publish(repo)
    return repo


def _branch(repo: Path, name: str = BRANCH) -> None:
    _git(repo, "checkout", "-q", "-b", name, "main")


def _push_branch(repo: Path, name: str = BRANCH) -> None:
    _git(repo, "push", "-q", "origin", f"{name}:refs/heads/{name}")


def _squash_merge(repo: Path, name: str = BRANCH) -> None:
    """Squash-merge `name` into main, publish main, then stand in a fresh
    housekeeping branch off `origin/main` — where a close-out runs."""
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--squash", name)
    _commit(repo, f"squash {name}")
    _publish(repo)
    _git(repo, "checkout", "-q", "-b", f"chore/closeout-{name.replace('/', '-')}", "origin/main")


def _plan(repo: Path, slug: str, *, ticked: bool, spec: str | None = None) -> Path:
    plan_dir = repo / SP / "plans" / slug
    shutil.copytree(FIXTURE, plan_dir)
    meta = yaml.safe_load((plan_dir / "_meta.yaml").read_text())
    meta["plan"] = slug
    if spec:
        meta["spec"] = f"docs/superpowers/specs/{spec}"
    (plan_dir / "_meta.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))
    if ticked:
        phase = plan_dir / "01.yaml"
        phase.write_text(phase.read_text().replace('state: " "', "state: x"))
    return plan_dir


def _spec(repo: Path, name: str, plan_rows: list[str]) -> Path:
    lines = [
        f"# {name}\n",
        "## Implementation Plans\n",
        "| Plan | Repo | File | Depends on |",
        "|---|---|---|---|",
    ]
    for slug in plan_rows:
        lines.append(f"| {slug} | this | `docs/superpowers/plans/{slug}/` | — |")
    return _write(repo, SP / "specs" / name, "\n".join(lines) + "\n")


def _run_file(repo: Path, run_id: str, plan_slug: str) -> Path:
    return _write(
        repo,
        SP / "runs" / f"{run_id}.yaml",
        f"run: {run_id}\n"
        "workflow: fr-goal@1\n"
        f"branch: {BRANCH}\n"
        "started: '2026-09-28T09:00:00Z'\n"
        "cursor: plan-review\n"
        "steps:\n"
        "  isolate: {state: done}\n"
        "  plan:\n"
        "    state: done\n"
        f"    emitted: {{plan: docs/superpowers/plans/{plan_slug}}}\n"
        "  plan-review: {state: pending}\n",
    )


def _journal(repo: Path, scope_dir: str, slug: str, body: str = "# journal\n") -> Path:
    return _write(repo, SP / "journals" / scope_dir / f"{slug}.md", body)


def _invoke(monkeypatch: pytest.MonkeyPatch, repo: Path, argv: list[str]):
    monkeypatch.setattr(archive_cmd, "_make_gh_client", lambda: FakeGhClient())
    monkeypatch.chdir(repo)
    monkeypatch.setenv("VK_REPO_ROOT", str(repo))
    return CliRunner().invoke(app, argv)


def _status(repo: Path) -> str:
    return _git(repo, "status", "--porcelain")


# --- Task 1: refusals and ref resolution --------------------------------------


@pytest.mark.parametrize(
    ("extra", "name"),
    [
        (["docs/superpowers/plans/x"], "plan_dir"),
        (["--all"], "--all"),
        (["--sweep-only"], "--sweep-only"),
        (["--force"], "--force"),
    ],
)
def test_branch_refuses_each_conflicting_mode(tmp_path, monkeypatch, extra, name):
    repo = _base(tmp_path)
    result = _invoke(monkeypatch, repo, ["archive", "--branch", BRANCH, *extra])
    assert result.exit_code == 2, result.output
    assert f"--branch takes no {name}" in result.output


def test_branch_refuses_without_a_default_ref(tmp_path, monkeypatch):
    repo = _base(tmp_path, remote=False)
    _branch(repo)
    _journal(repo, "debug", "2026-09-28-bug")
    _commit(repo, "journal")
    result = _invoke(monkeypatch, repo, ["archive", "--branch", BRANCH])
    assert result.exit_code == 2, result.output
    assert "no git remote" in result.output
    assert (repo / SP / "journals" / "debug" / "2026-09-28-bug.md").exists()


def test_branch_refuses_a_branch_that_resolves_nowhere(tmp_path, monkeypatch):
    repo = _base(tmp_path)
    result = _invoke(monkeypatch, repo, ["archive", "--branch", "feat/ghost"])
    assert result.exit_code == 2, result.output
    assert "resolves neither locally nor as origin/feat/ghost" in result.output
    assert _status(repo) == ""


def test_branch_refuses_an_unmerged_line_and_moves_nothing(tmp_path, monkeypatch):
    repo = _base(tmp_path)
    _branch(repo)
    _journal(repo, "debug", "2026-09-28-bug")
    _commit(repo, "journal")
    _push_branch(repo)
    _squash_merge(repo)
    # A post-merge push to the branch: a line origin/main never received.
    _git(repo, "checkout", "-q", BRANCH)
    _write(repo, "src.txt", "late line\n")
    _commit(repo, "late")
    _push_branch(repo)
    _git(repo, "checkout", "-q", "chore/closeout-feat-thing")

    result = _invoke(monkeypatch, repo, ["archive", "--branch", BRANCH])
    assert result.exit_code == 2, result.output
    assert "src.txt" in result.output
    assert f"fr isolation verify-merge --branch {BRANCH}" in result.output
    assert (repo / SP / "journals" / "debug" / "2026-09-28-bug.md").exists()
    assert _status(repo) == ""


def test_branch_checks_the_remote_ref_even_when_local_is_merged(tmp_path, monkeypatch):
    """Only origin/<b> carries the late line (pushed from another clone): the
    local ref alone would pass, so every resolving ref must be checked."""
    repo = _base(tmp_path)
    _branch(repo)
    _journal(repo, "debug", "2026-09-28-bug")
    _commit(repo, "journal")
    _push_branch(repo)
    _squash_merge(repo)
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", "-b", BRANCH, str(tmp_path / "origin.git"), str(other))
    _write(other, "late.txt", "from elsewhere\n")
    _commit(other, "late")
    _git(other, "push", "-q", "origin", BRANCH)

    result = _invoke(monkeypatch, repo, ["archive", "--branch", BRANCH])
    assert result.exit_code == 2, result.output
    assert "late.txt" in result.output
    assert _status(repo) == ""
