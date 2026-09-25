"""End-to-end: a delivered, squash-merged run closes out without fr refusing
its own state (spec `2026-09-25-fr-goal-closeout-defects-design.md` §3.C/§3.D,
Test Plan item 4, gh#610 phase 5 P5.T1.S1).

Real git throughout: a bare `origin` whose default branch is `master`, a
`base` clone on `master`, and a linked worktree `workspace` on a feature
branch — the shape `fr run start` requires already in place, mirroring
`test_run_cli.py`'s `_repo()`. On that branch: `fr plan edit --tick`,
`fr journal add`, and a full `fr run start` -> ... -> `resolve --step
deliver` each leave a real `chore(fr):` commit. The branch is pushed,
squash-merged into `master` by plumbing (no PR host involved — the same
`_squash_merge` shape `test_isolation.py` uses), and `master` is pushed back
to `origin`.

The ONE piece that genuinely needs a live forge is the PR-state lookup
`verify_merge` makes (`gh pr view` or equivalent) — monkeypatched on a REAL
target instance, exactly as `test_isolation_cmd.py`'s `_RecordingTarget`
tests do it, so every git operation this test makes assertions about is real.

Assertions are outcome-based — clean record paths, no dirty-worktree or
unlanded-content hazard fr's own commits caused — never commit counts (the
plan's own steer, `docs/superpowers/journals/plans/*p3-steer*`).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import archive_cmd, isolation_cmd
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.local import subprocess_runner
from fr.isolation.types import IsolationState, save_state
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient

runner_cli = CliRunner()

FIXTURE_PLAN = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
SLUG = "2026-09-30-e2e"

_SHAPE = """
workflow: closeout-e2e
schema: 1
unit: run
steps:
  - id: brainstorm
    kind: agent
    emits: [spec]
  - id: plan
    kind: agent
    needs: [spec]
    emits: [plan]
  - id: deliver
    kind: agent
    needs: [spec, plan]
    emits: [pr]
"""


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def _git_out(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _invoke(repo: Path, shipped: Path, argv: list[str]):
    env = {**os.environ, "VK_REPO_ROOT": str(repo), "FR_SHIPPED_WORKFLOWS_DIR": str(shipped)}
    return runner_cli.invoke(app, argv, env=env)


@pytest.fixture()
def fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    """`(base, workspace, origin)` — a bare origin (default `master`), a
    real clone on `master`, and a linked worktree on branch `b` carrying the
    `.fr-isolation` marker `fr run start` requires."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "master", str(origin)], check=True)

    base = tmp_path / "base"
    base.mkdir()
    _git(base, "init", "-q", "-b", "master")
    _git(base, "config", "user.email", "t@example.com")
    _git(base, "config", "user.name", "T")
    for d in ("plans", "specs", "implemented/plans"):
        (base / "docs" / "superpowers" / d).mkdir(parents=True, exist_ok=True)
    (base / "docs" / "superpowers" / "plans" / ".gitkeep").write_text("")
    _git(base, "add", "-A")
    _git(base, "commit", "-qm", "seed")
    _git(base, "remote", "add", "origin", str(origin))
    _git(base, "push", "-q", "origin", "master")
    _git(base, "remote", "set-head", "origin", "master")

    workspace = tmp_path / "workspace"
    _git(base, "worktree", "add", "-q", "-b", "b", str(workspace))
    (workspace / "docs" / "superpowers" / "workflows").mkdir(parents=True, exist_ok=True)
    (workspace / ".fr-isolation").write_text(
        json.dumps(
            {
                "toplevel": str(workspace.resolve()),
                "branch": "b",
                "mode": "worktree",
                "created_at": "2026-09-25T00:00:00+00:00",
            }
        )
    )
    return base, workspace, origin


def _seed_plan_and_spec(workspace: Path) -> tuple[Path, Path]:
    """A real, undispatched, agentic-tagged plan + its spec — the same shape
    `test_archive_cmd.py::test_archive_moves_ticked_undispatched_plan` uses,
    copied rather than hand-typed so the fixture stays in lockstep with the
    schema. Left un-ticked; P1.T1.S1 is ticked via `fr plan edit` below so
    that tick is one of fr's own `chore(fr):` commits, not a fixture detail."""
    plan_dir = workspace / "docs" / "superpowers" / "plans" / SLUG
    shutil.copytree(FIXTURE_PLAN, plan_dir)
    import yaml

    meta = yaml.safe_load((plan_dir / "_meta.yaml").read_text())
    meta["plan"] = SLUG
    meta["spec"] = f"docs/superpowers/specs/{SLUG}-design.md"
    (plan_dir / "_meta.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))

    spec_path = workspace / "docs" / "superpowers" / "specs" / f"{SLUG}-design.md"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        f"# {SLUG}\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n|---|---|---|---|\n"
        f"| {SLUG} | (this repo) | `docs/superpowers/plans/{SLUG}` | — |\n"
    )
    _git(workspace, "add", "-A")
    _git(workspace, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed plan+spec")
    return plan_dir, spec_path


@pytest.mark.usefixtures("complete_live_pr")
def test_squash_merged_delivery_leaves_no_hazard_fr_caused(
    fixture: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    base, workspace, origin = fixture
    plan_dir, spec_path = _seed_plan_and_spec(workspace)
    plan_rel = plan_dir.relative_to(workspace).as_posix()
    spec_rel = spec_path.relative_to(workspace).as_posix()
    shipped = workspace.parent / "shipped"
    (shipped).mkdir(parents=True, exist_ok=True)
    (shipped / "closeout-e2e.yaml").write_text(_SHAPE)

    # --- fr's own record writes on the branch: plan tick, journal, run cursor ---
    tick = _invoke(workspace, shipped, ["plan", "edit", str(plan_dir), "--tick", "P1.T1.S1"])
    assert tick.exit_code == 0, tick.output

    journal = _invoke(
        workspace,
        shipped,
        [
            "journal",
            "add",
            "--scope",
            "plan",
            "--slug",
            SLUG,
            "--kind",
            "discovery",
            "--title",
            "e2e fixture note",
            "--phase",
            "1",
        ],
    )
    assert journal.exit_code == 0, journal.output

    start = _invoke(
        workspace, shipped, ["run", "start", "closeout-e2e", "--branch", "b", "--run-id", "r1"]
    )
    assert start.exit_code == 0, start.output
    _invoke(workspace, shipped, ["run", "advance", "r1"])  # brainstorm: running
    resolved_spec = _invoke(
        workspace,
        shipped,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "brainstorm",
            "--state",
            "done",
            "--emitted",
            f"spec={spec_rel}",
        ],
    )
    assert resolved_spec.exit_code == 0, resolved_spec.output
    _invoke(workspace, shipped, ["run", "advance", "r1"])  # plan: running
    resolved_plan = _invoke(
        workspace,
        shipped,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "plan",
            "--state",
            "done",
            "--emitted",
            f"plan={plan_rel}",
        ],
    )
    assert resolved_plan.exit_code == 0, resolved_plan.output
    _invoke(workspace, shipped, ["run", "advance", "r1"])  # deliver: running
    resolved_deliver = _invoke(
        workspace,
        shipped,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "deliver",
            "--state",
            "done",
            "--emitted",
            "pr=https://example.invalid/pull/1",
        ],
    )
    assert resolved_deliver.exit_code == 0, resolved_deliver.output
    assert "cursor committed as" in resolved_deliver.stdout, resolved_deliver.output

    # The branch worktree must be clean — every fr write above landed a
    # chore(fr): commit, nothing left staged-not-committed (defect 4).
    assert _git_out(workspace, "status", "--porcelain") == ""

    # --- push, then squash-merge into the default branch by plumbing ---
    _git(workspace, "push", "-q", "origin", "b")
    _git(base, "merge", "--squash", "b")
    _git(base, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "squash: b")
    _git(base, "push", "-q", "origin", "master")

    # --- 1. `fr isolation verify-merge --branch b`, no flags, host-worktree target ---
    state = IsolationState(
        repo_root=base,
        branch="b",
        worktree=workspace,
        profile="host",
        target="worktree",
        created_at="2026-09-25T00:00:00+00:00",
    )
    save_state(state)
    real_target = HostWorktreeTarget(base, runner=subprocess_runner)
    # The one piece that needs a live forge — everything else here is real git.
    monkeypatch.setattr(
        real_target,
        "_pr",
        lambda _state: {"state": "MERGED", "url": "https://example.invalid/pull/1"},
    )
    monkeypatch.setattr(isolation_cmd, "_target_for", lambda _root, _state: real_target)
    verify = runner_cli.invoke(
        app, ["isolation", "verify-merge", "--repo", str(base), "--branch", "b"]
    )
    assert verify.exit_code == 0, verify.output
    assert "origin/master" in verify.output

    # --- 2. `fr archive <plan-dir>` does not refuse as dirty ---
    monkeypatch.setattr(archive_cmd, "_make_gh_client", lambda: FakeGhClient())
    monkeypatch.chdir(base)
    monkeypatch.setenv("VK_REPO_ROOT", str(base))
    archived_plan_dir = base / "docs" / "superpowers" / "plans" / SLUG
    archive = runner_cli.invoke(app, ["archive", str(archived_plan_dir)])
    assert "dirty" not in archive.output.lower(), archive.output
    assert archive.exit_code == 0, archive.output
    assert not archived_plan_dir.exists()

    # --- 3. the reap-hazard check fr's own `down`/`gc` guard makes reports
    # no dirty-worktree or unlanded-content hazard for the branch's worktree ---
    hazard = real_target._reap_hazard(state)
    assert hazard is None, hazard
