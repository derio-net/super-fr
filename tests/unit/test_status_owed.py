"""`fr status`'s owed blocks (2026-09-28-closeout-always spec §C): debug
journals present on the default ref, fully implemented specs, orphan plan/spec
journals, and orphan run cursors — each with its clearing command — plus the
`held live (spec): …` block for a spec `owed_artifacts` cannot yet clear.
Text and --json both exercised; today's plan blocks (merged/manual-open/
complete-unmerged/in-progress) are asserted unchanged.

Real git throughout, as in `test_status_sweep.py`: `origin/main` is a real
bare remote, `fr.archive._fetch` stubbed so nothing touches a network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import status_cmd
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient
from tests.unit.test_merge_evidence import _add_remote, _commit, _init, _publish, _write_plan

SP = Path("docs/superpowers")


def _write(repo: Path, rel: str | Path, text: str) -> Path:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def _archived_plan(repo: Path, slug: str) -> Path:
    """An `implemented/plans/<slug>` dir git can actually track — a bare
    `mkdir` creates an EMPTY directory, invisible to `git ls-tree` (and so
    never on a ref), so "this owner is archived" needs a real file inside."""
    return _write(repo, SP / "implemented" / "plans" / slug / "_meta.yaml", "schema_version: 2\n")


def _spec(repo: Path, name: str, rows: list[tuple[str, str]]) -> Path:
    lines = [
        f"# {name}\n",
        "## Implementation Plans\n",
        "| Plan | Repo | File | Depends on |",
        "|---|---|---|---|",
    ]
    for plan_name, file_cell in rows:
        lines.append(f"| {plan_name} | derio-net/test | {file_cell} | — |")
    return _write(repo, SP / "specs" / name, "\n".join(lines) + "\n")


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
def _hermetic(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setattr("fr.archive._fetch", lambda root, remote: None)


def _owed_repo(tmp_path: Path) -> Path:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")

    # A plan bucket entry too, to confirm today's block is unaffected.
    _write_plan(repo, "2026-01-01-merged-plan", [("agentic", True)])

    _write(repo, SP / "journals" / "debug" / "on-ref.md", "# on ref\n")

    _archived_plan(repo, "implemented-plan")
    _spec(
        repo,
        "2026-01-01-done-spec-design.md",
        [("done", "`docs/superpowers/implemented/plans/implemented-plan`")],
    )

    _spec(repo, "2026-01-01-held-spec-design.md", [("later", "pending")])

    _archived_plan(repo, "orphan-owner-plan")
    _write(repo, SP / "journals" / "plans" / "orphan-owner-plan.md", "# orphan plan journal\n")

    _archived_plan(repo, "run-owner-plan")
    _run_cursor(repo, "2026-01-01-run-owner", "docs/superpowers/plans/run-owner-plan")

    _commit(repo, "seed")
    _publish(repo)
    return repo


def _invoke(monkeypatch: pytest.MonkeyPatch, repo: Path, argv: list[str]):
    monkeypatch.setattr(status_cmd, "_make_gh_client", lambda: FakeGhClient())
    monkeypatch.chdir(repo)
    monkeypatch.setenv("VK_REPO_ROOT", str(repo))
    return CliRunner().invoke(app, argv)


# --- text ---------------------------------------------------------------


def test_status_text_lists_owed_debug_journal_with_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _owed_repo(tmp_path)
    result = _invoke(monkeypatch, repo, ["status"])
    assert result.exit_code == 0, result.output
    assert "docs/superpowers/journals/debug/on-ref.md" in result.output
    assert "fr archive --all" in result.output


def test_status_text_lists_owed_spec_with_sweep_only_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _owed_repo(tmp_path)
    result = _invoke(monkeypatch, repo, ["status"])
    assert "docs/superpowers/specs/2026-01-01-done-spec-design.md" in result.output
    assert "fr archive --sweep-only" in result.output


def test_status_text_lists_orphan_journal_and_orphan_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _owed_repo(tmp_path)
    result = _invoke(monkeypatch, repo, ["status"])
    assert "docs/superpowers/journals/plans/orphan-owner-plan.md" in result.output
    assert "docs/superpowers/runs/2026-01-01-run-owner.yaml" in result.output


def test_status_text_prints_held_spec_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _owed_repo(tmp_path)
    result = _invoke(monkeypatch, repo, ["status"])
    assert "held live (spec): 2026-01-01-held-spec-design.md" in result.output
    assert "pending" in result.output


def test_status_text_plan_block_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Today's "merged but not archived" plan block still exists, with its own
    `fr archive <plan-dir>` line — the new owed blocks add to the report,
    they don't replace this one."""
    repo = _owed_repo(tmp_path)
    result = _invoke(monkeypatch, repo, ["status"])
    assert "merged but not archived" in result.output
    assert "fr archive docs/superpowers/plans/2026-01-01-merged-plan" in result.output


def test_status_exits_zero_with_owed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _owed_repo(tmp_path)
    result = _invoke(monkeypatch, repo, ["status"])
    assert result.exit_code == 0, result.output


def test_status_text_no_owed_block_when_nothing_owed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")
    _publish(repo)
    result = _invoke(monkeypatch, repo, ["status"])
    assert result.exit_code == 0, result.output
    assert "fr archive --all" not in result.output
    assert "held live" not in result.output


# --- json -----------------------------------------------------------------


def test_status_json_has_owed_and_held_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _owed_repo(tmp_path)
    result = _invoke(monkeypatch, repo, ["status", "--format", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    kinds = {o["kind"] for o in data["owed"]}
    assert {"debug_journal", "spec", "orphan_journal", "orphan_run"} <= kinds
    assert any(h["spec"] == "2026-01-01-held-spec-design.md" for h in data["held"])


# --- negative: branch-only artifacts/owners never appear (review #1/#2/#4) --


def _branch_only_repo(tmp_path: Path) -> Path:
    """Every owner/artifact below is written AFTER `_publish` — on the
    branch only, never on the default ref."""
    repo = _init(tmp_path / "r")
    _add_remote(repo, tmp_path / "o.git")
    _archived_plan(repo, "on-ref-journal-owner")
    _run_cursor(repo, "2026-01-01-on-ref-run", "docs/superpowers/plans/on-ref-run-owner")
    _commit(repo, "seed")
    _publish(repo)

    # This PR's own spec, still only on the branch.
    _spec(repo, "2026-01-01-branch-only-spec-design.md", [("x", "pending")])
    # A journal on the branch whose owner (published above) IS on the ref —
    # but the journal itself is not, so it must not be owed.
    _write(
        repo,
        SP / "journals" / "plans" / "on-ref-journal-owner.md",
        "# journal written after publish\n",
    )
    # A run cursor on the branch whose emitted plan is archived only on the
    # branch too.
    _archived_plan(repo, "on-ref-run-owner")
    return repo


def test_status_ignores_branch_only_spec_journal_and_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _branch_only_repo(tmp_path)
    result = _invoke(monkeypatch, repo, ["status", "--format", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    owed_paths = {o["path"] for o in data["owed"]}
    held_specs = {h["spec"] for h in data["held"]}
    assert "docs/superpowers/journals/plans/on-ref-journal-owner.md" not in owed_paths
    assert "docs/superpowers/runs/2026-01-01-on-ref-run.yaml" not in owed_paths
    assert "2026-01-01-branch-only-spec-design.md" not in held_specs
    assert "2026-01-01-branch-only-spec-design.md" not in {
        o["path"].rsplit("/", 1)[-1] for o in data["owed"]
    }


def test_status_json_keeps_existing_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing json keys (archivable, merged_manual_open, ...) are unchanged;
    `owed`/`held` are added alongside them."""
    repo = _owed_repo(tmp_path)
    result = _invoke(monkeypatch, repo, ["status", "--format", "json"])
    data = json.loads(result.output)
    assert "docs/superpowers/plans/2026-01-01-merged-plan".split("/")[-1] in data["archivable"]
    assert "merged_manual_open" in data
    assert "complete_unmerged" in data
    assert "in_progress" in data
