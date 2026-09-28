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
        lines.append(f"| {slug} | derio-net/test | `docs/superpowers/plans/{slug}` | — |")
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


# --- Task 2: per-kind archiving with held lines --------------------------------

IMPL = SP / "implemented"
PLAN = "2026-09-28-thing"
SPEC = "2026-09-28-thing-design.md"
RUN = "2026-09-28-feat-thing"


def _merged(repo: Path, build) -> None:
    """Branch off main, let `build` write the branch's artifacts, commit,
    push, squash-merge, and stand in the housekeeping branch."""
    _branch(repo)
    build(repo)
    _commit(repo, "work")
    _push_branch(repo)
    _squash_merge(repo)


def test_branch_archives_every_kind_a_merged_branch_added(tmp_path, monkeypatch):
    repo = _base(tmp_path)

    def build(r: Path) -> None:
        _plan(r, PLAN, ticked=True, spec=SPEC)
        _spec(r, SPEC, [PLAN])
        _run_file(r, RUN, PLAN)
        _journal(r, "plans", PLAN)
        _journal(r, "specs", "2026-09-28-thing")
        _journal(r, "debug", "2026-09-28-bug")

    _merged(repo, build)
    result = _invoke(monkeypatch, repo, ["archive", "--branch", BRANCH])
    assert result.exit_code == 0, result.output
    assert "held:" not in result.output
    for live, archived in (
        (SP / "plans" / PLAN, IMPL / "plans" / PLAN),
        (SP / "specs" / SPEC, IMPL / "specs" / SPEC),
        (SP / "runs" / f"{RUN}.yaml", IMPL / "runs" / f"{RUN}.yaml"),
        (SP / "journals/plans" / f"{PLAN}.md", IMPL / "journals/plans" / f"{PLAN}.md"),
        (
            SP / "journals/specs/2026-09-28-thing.md",
            IMPL / "journals/specs/2026-09-28-thing.md",
        ),
        (SP / "journals/debug/2026-09-28-bug.md", IMPL / "journals/debug/2026-09-28-bug.md"),
    ):
        assert not (repo / live).exists(), live
        assert (repo / archived).exists(), archived
        assert f"archived: {live}" in result.output, live
    assert "moves staged via git mv" in result.output


def test_branch_archives_a_debug_journal_it_only_modified(tmp_path, monkeypatch):
    """d2: added and modified are alike — a debug journal that predates the
    branch is still the branch's to close out."""
    repo = _base(tmp_path, remote=False)
    _journal(repo, "debug", "2026-09-01-old", "# old\n")
    _commit(repo, "old journal")
    _add_remote(repo, tmp_path / "origin.git")
    _publish(repo)

    _merged(
        repo,
        lambda r: _write(r, SP / "journals/debug/2026-09-01-old.md", "# old\n\nmore\n"),
    )
    result = _invoke(monkeypatch, repo, ["archive", "--branch", BRANCH])
    assert result.exit_code == 0, result.output
    assert (repo / IMPL / "journals/debug/2026-09-01-old.md").is_file()
    assert "archived: docs/superpowers/journals/debug/2026-09-01-old.md" in result.output


def test_branch_holds_an_incomplete_plan_and_everything_following_it(tmp_path, monkeypatch):
    repo = _base(tmp_path)

    def build(r: Path) -> None:
        _plan(r, PLAN, ticked=False, spec=SPEC)
        _spec(r, SPEC, [PLAN])
        _run_file(r, RUN, PLAN)
        _write(r, SP / "usage" / f"{RUN}.yaml", "schema_version: 1\n")
        _journal(r, "plans", PLAN)
        _journal(r, "specs", "2026-09-28-thing")

    _merged(repo, build)
    result = _invoke(monkeypatch, repo, ["archive", "--branch", BRANCH])
    assert result.exit_code == 0, result.output
    out = result.output
    assert f"held: docs/superpowers/plans/{PLAN} — " in out
    assert "Phase 1" in out
    assert f"held: docs/superpowers/specs/{SPEC} — " in out
    assert (
        f"held: docs/superpowers/runs/{RUN}.yaml — follows plan docs/superpowers/plans/{PLAN}"
        in out
    )
    assert (
        f"held: docs/superpowers/usage/{RUN}.yaml — follows plan docs/superpowers/plans/{PLAN}"
        in out
    )
    assert f"held: docs/superpowers/journals/plans/{PLAN}.md — follows plan {PLAN}" in out
    assert (
        "held: docs/superpowers/journals/specs/2026-09-28-thing.md — follows spec "
        "2026-09-28-thing" in out
    )
    assert "archived:" not in out
    assert "moves staged" not in out
    assert _status(repo) == ""


def test_branch_no_spec_sweep_holds_the_spec(tmp_path, monkeypatch):
    repo = _base(tmp_path)

    def build(r: Path) -> None:
        _plan(r, PLAN, ticked=True, spec=SPEC)
        _spec(r, SPEC, [PLAN])

    _merged(repo, build)
    result = _invoke(monkeypatch, repo, ["archive", "--branch", BRANCH, "--no-spec-sweep"])
    assert result.exit_code == 0, result.output
    assert (repo / IMPL / "plans" / PLAN).is_dir()
    assert f"held: docs/superpowers/specs/{SPEC} — spec sweep skipped" in result.output
    assert (repo / SP / "specs" / SPEC).is_file()


def test_branch_moves_a_plan_journal_whose_plan_is_already_archived(tmp_path, monkeypatch):
    repo = _base(tmp_path, remote=False)
    _plan(repo, PLAN, ticked=True)
    _commit(repo, "plan")
    (repo / IMPL / "plans").mkdir(parents=True)
    _git(repo, "mv", str(SP / "plans" / PLAN), str(IMPL / "plans" / PLAN))
    _commit(repo, "archive plan")
    _add_remote(repo, tmp_path / "origin.git")
    _publish(repo)

    _merged(repo, lambda r: _journal(r, "plans", PLAN))
    result = _invoke(monkeypatch, repo, ["archive", "--branch", BRANCH])
    assert result.exit_code == 0, result.output
    assert (repo / IMPL / "journals/plans" / f"{PLAN}.md").is_file()
    assert f"archived: docs/superpowers/journals/plans/{PLAN}.md" in result.output


def test_branch_that_touched_no_artifact_is_a_clean_no_op(tmp_path, monkeypatch):
    repo = _base(tmp_path)
    _merged(repo, lambda r: _write(r, "src.txt", "code\n"))
    result = _invoke(monkeypatch, repo, ["archive", "--branch", BRANCH])
    assert result.exit_code == 0, result.output
    assert f"nothing to archive for {BRANCH}" in result.output
    assert _status(repo) == ""
