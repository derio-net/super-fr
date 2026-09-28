"""`fr archive --all` learns debug journals, orphan journals and orphan run
cursors (+ usage) — 2026-09-28-closeout-always spec §C, after the plan loop
and spec sweep, unaffected by `--no-spec-sweep` (they are not specs).

Real git throughout, as `test_archive_cmd.py`: `origin/main` is a real bare
remote at a file path, `fr.archive._fetch` stubbed so nothing touches a
network.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient
from tests.unit.test_archive_cmd import _invoke, _repo, _seed
from tests.unit.test_merge_evidence import stub_fetch

SP = Path("docs") / "superpowers"

runner = CliRunner()


def _write(repo: Path, rel: Path, text: str) -> Path:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def _archived_plan(repo: Path, slug: str) -> Path:
    """An `implemented/plans/<slug>` dir git can actually track — a bare
    `mkdir` creates an EMPTY directory, invisible to `git ls-tree` (and so
    never on a ref), so "this owner is archived" needs a real file inside."""
    return _write(repo, SP / "implemented" / "plans" / slug / "_meta.yaml", "schema_version: 2\n")


def _run_cursor(repo: Path, run_id: str, plan_rel: str) -> Path:
    return _write(
        repo,
        SP / "runs" / f"{run_id}.yaml",
        f"run: {run_id}\n"
        "workflow: fr-goal@1\n"
        "branch: feat/x\n"
        "started: '2026-01-01T09:00:00Z'\n"
        "cursor: deliver\n"
        "steps:\n"
        "  isolate: {state: done}\n"
        "  plan:\n"
        "    state: done\n"
        f"    emitted: {{plan: {plan_rel}}}\n"
        "  deliver: {state: done}\n",
    )


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    return stub_fetch(monkeypatch)


def _build(tmp_path: Path) -> Path:
    repo = _repo(tmp_path)

    _write(repo, SP / "journals" / "debug" / "on-ref.md", "# on ref\n")

    _archived_plan(repo, "orphan-owner-plan")
    _write(repo, SP / "journals" / "plans" / "orphan-owner-plan.md", "# orphan plan journal\n")

    _archived_plan(repo, "run-owner-plan")
    _run_cursor(repo, "2026-01-01-run-owner", "docs/superpowers/plans/run-owner-plan")
    _write(repo, SP / "usage" / "2026-01-01-run-owner.yaml", "captures: []\n")

    _seed(repo)  # commits everything above and publishes it to origin/main

    # Branch-only debug journal: written AFTER the publish, never committed —
    # not on the default ref, so `--all` must leave it alone.
    _write(repo, SP / "journals" / "debug" / "branch-only.md", "# branch only\n")

    return repo


def test_all_moves_debug_journal_present_on_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _build(tmp_path)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    assert not (repo / SP / "journals" / "debug" / "on-ref.md").exists()
    assert (repo / SP / "implemented" / "journals" / "debug" / "on-ref.md").exists()


def test_all_leaves_branch_only_debug_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _build(tmp_path)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    assert (repo / SP / "journals" / "debug" / "branch-only.md").exists()
    assert not (repo / SP / "implemented" / "journals" / "debug" / "branch-only.md").exists()


def test_all_moves_orphan_plan_journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _build(tmp_path)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    assert not (repo / SP / "journals" / "plans" / "orphan-owner-plan.md").exists()
    assert (repo / SP / "implemented" / "journals" / "plans" / "orphan-owner-plan.md").exists()


def test_all_moves_orphan_run_cursor_and_its_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _build(tmp_path)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    assert not (repo / SP / "runs" / "2026-01-01-run-owner.yaml").exists()
    assert (repo / SP / "implemented" / "runs" / "2026-01-01-run-owner.yaml").exists()
    assert not (repo / SP / "usage" / "2026-01-01-run-owner.yaml").exists()
    assert (repo / SP / "implemented" / "usage" / "2026-01-01-run-owner.yaml").exists()


def test_no_spec_sweep_does_not_stop_debug_or_orphan_moves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _build(tmp_path)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all", "--no-spec-sweep"])
    assert result.exit_code == 0, result.output
    assert (repo / SP / "implemented" / "journals" / "debug" / "on-ref.md").exists()
    assert (repo / SP / "implemented" / "journals" / "plans" / "orphan-owner-plan.md").exists()
    assert (repo / SP / "implemented" / "runs" / "2026-01-01-run-owner.yaml").exists()


def test_all_reports_the_moves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _build(tmp_path)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert "on-ref.md" in result.output
    assert "orphan-owner-plan.md" in result.output
    assert "2026-01-01-run-owner.yaml" in result.output


# --- negative: an owner or artifact only on the branch is never moved -------


def _build_branch_only_owners(tmp_path: Path) -> Path:
    repo = _repo(tmp_path)

    # An on-ref journal whose owner will only be archived on the branch.
    _write(repo, SP / "journals" / "plans" / "branch-archives-owner.md", "# owner comes later\n")
    # An on-ref run cursor whose owner plan will only be archived on the branch.
    _run_cursor(
        repo, "2026-01-01-branch-archives-owner", "docs/superpowers/plans/branch-only-run-owner"
    )
    # An on-ref archived owner whose journal is only written on the branch.
    _archived_plan(repo, "branch-writes-journal")
    # An on-ref archived owner whose run cursor is only written on the branch.
    _archived_plan(repo, "branch-writes-run")

    _seed(repo)

    _archived_plan(repo, "branch-only-run-owner")  # branch-only owner (journal's owner test)
    _write(repo, SP / "journals" / "plans" / "branch-writes-journal.md", "# branch-only journal\n")
    _run_cursor(repo, "2026-01-01-branch-writes-run", "docs/superpowers/plans/branch-writes-run")

    return repo


def test_all_does_not_move_journal_whose_owner_is_branch_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _build_branch_only_owners(tmp_path)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    assert (repo / SP / "journals" / "plans" / "branch-archives-owner.md").exists()
    assert not (
        repo / SP / "implemented" / "journals" / "plans" / "branch-archives-owner.md"
    ).exists()


def test_all_does_not_move_run_whose_owner_is_branch_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _build_branch_only_owners(tmp_path)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    assert (repo / SP / "runs" / "2026-01-01-branch-archives-owner.yaml").exists()
    assert not (
        repo / SP / "implemented" / "runs" / "2026-01-01-branch-archives-owner.yaml"
    ).exists()


def test_all_does_not_move_branch_only_journal_even_with_on_ref_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _build_branch_only_owners(tmp_path)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    assert (repo / SP / "journals" / "plans" / "branch-writes-journal.md").exists()
    assert not (
        repo / SP / "implemented" / "journals" / "plans" / "branch-writes-journal.md"
    ).exists()


def test_all_does_not_move_branch_only_run_even_with_on_ref_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _build_branch_only_owners(tmp_path)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    assert (repo / SP / "runs" / "2026-01-01-branch-writes-run.yaml").exists()
    assert not (repo / SP / "implemented" / "runs" / "2026-01-01-branch-writes-run.yaml").exists()
