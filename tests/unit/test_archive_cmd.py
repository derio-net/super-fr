"""`fr archive` — gate, plan/spec moves, --all sweep (2026-06-05 spec, Phase 5).

Since #544 (spec 2026-09-23-archive-merge-evidence §3.C) the gate also needs
merge evidence: an undispatched agentic phase must be complete on the default
branch's remote-tracking ref. Every repo here is a real temp git repo whose
origin is a FILE PATH (`_seed`), and `fr.archive._fetch` is monkeypatched, so
nothing touches a network.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import archive_cmd
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient
from tests.unit.test_merge_evidence import _add_remote, _git, _publish, _write_plan, stub_fetch

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _repo(tmp_path: Path) -> Path:
    sp = tmp_path / "docs" / "superpowers"
    (sp / "plans").mkdir(parents=True)
    (sp / "specs").mkdir()
    (sp / "implemented" / "plans").mkdir(parents=True)
    return tmp_path


def _add_plan(repo: Path, slug: str, *, ticked: bool, spec_name: str | None = None) -> Path:
    plan_dir = repo / "docs" / "superpowers" / "plans" / slug
    shutil.copytree(FIXTURE, plan_dir)
    import yaml as _yaml

    meta = _yaml.safe_load((plan_dir / "_meta.yaml").read_text())
    meta["plan"] = slug
    if spec_name:
        meta["spec"] = f"docs/superpowers/specs/{spec_name}"
    (plan_dir / "_meta.yaml").write_text(_yaml.safe_dump(meta, sort_keys=False))
    if ticked:
        phase = plan_dir / "01.yaml"
        phase.write_text(phase.read_text().replace('state: " "', "state: x"))
    return plan_dir


def _add_spec(repo: Path, name: str, rows: list[tuple[str, str, str]]) -> Path:
    """rows: (plan-name, repo-cell, file-cell)."""
    spec = repo / "docs" / "superpowers" / "specs" / name
    lines = [
        f"# {name}\n",
        "## Implementation Plans\n",
        "| Plan | Repo | File | Depends on |",
        "|---|---|---|---|",
    ]
    for plan_name, repo_cell, file_cell in rows:
        lines.append(f"| {plan_name} | {repo_cell} | `{file_cell}` | — |")
    spec.write_text("\n".join(lines) + "\n")
    return spec


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Cut off operator git config and replace the network fetch with a
    recorder: `fr archive` must fetch once per invocation (spec §3.C)."""
    return stub_fetch(monkeypatch)


def _seed(repo: Path, *, landed: bool = True, remote: bool = True) -> None:
    """Commit the fixture repo and wire a FILE-PATH origin (#544).

    ``landed=True`` publishes the whole tree to ``origin/main``, so every
    plan in it counts as merged; ``landed=False`` publishes only an empty
    base commit, so the plans exist on the branch alone. ``remote=False``
    leaves the repo without a remote (merge state unknown). Later branch-only
    work goes through ``_commit``; ``_publish`` lands it.
    """
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "base")
    if remote:
        _add_remote(repo, repo.parent / f"{repo.name}.origin.git")
        if not landed:
            _publish(repo)
    _commit(repo, "seed")
    if remote and landed:
        _publish(repo)


def _commit(repo: Path, msg: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", msg)


def _invoke(monkeypatch, repo, gh, argv):
    monkeypatch.setattr(archive_cmd, "_make_gh_client", lambda: gh)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("VK_REPO_ROOT", str(repo))
    return CliRunner().invoke(app, argv)


# --- T1: gate + plan move ---


def test_archive_moves_ticked_undispatched_plan(tmp_path, monkeypatch):
    """The bookmarks shape archives: all steps ticked, never dispatched."""
    repo = _repo(tmp_path)
    plan_dir = _add_plan(repo, "2026-05-25-bookmarks", ticked=True)
    _seed(repo)
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 0, result.output
    assert not plan_dir.exists()
    moved = repo / "docs" / "superpowers" / "implemented" / "plans" / "2026-05-25-bookmarks"
    assert moved.is_dir()
    # git mv staged the rename
    porcelain = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout
    assert "R " in porcelain


def test_archive_refuses_incomplete_plan_with_reasons(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    plan_dir = _add_plan(repo, "2026-06-01-active", ticked=False)
    _seed(repo)
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 2, result.output
    assert "Phase 1" in result.output
    assert plan_dir.exists()


def test_archive_force_overrides_gate(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    plan_dir = _add_plan(repo, "2026-06-01-known-done", ticked=False)
    _seed(repo)
    result = _invoke(
        monkeypatch,
        repo,
        FakeGhClient(),
        ["archive", str(plan_dir.relative_to(repo)), "--force"],
    )
    assert result.exit_code == 0, result.output
    assert not plan_dir.exists()


def test_archive_refuses_dirty_plan_paths(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    plan_dir = _add_plan(repo, "2026-05-25-bookmarks", ticked=True)
    _seed(repo)
    (plan_dir / "01.yaml").write_text((plan_dir / "01.yaml").read_text() + "# dirty\n")
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 2, result.output
    assert "dirty" in result.output.lower()
    assert plan_dir.exists()


# --- T2: spec decision + cross-repo gh resolution ---


def test_archive_moves_spec_when_last_local_plan_archives(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    plan_dir = _add_plan(
        repo, "2026-05-25-bookmarks", ticked=True, spec_name="2026-05-25-bm-design.md"
    )
    _add_spec(
        repo,
        "2026-05-25-bm-design.md",
        [("bm", "derio-net/test", "docs/superpowers/plans/2026-05-25-bookmarks")],
    )
    _seed(repo)
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 0, result.output
    sp = repo / "docs" / "superpowers"
    assert (sp / "implemented" / "specs" / "2026-05-25-bm-design.md").is_file()
    assert not (sp / "specs" / "2026-05-25-bm-design.md").exists()


def test_archive_leaves_spec_with_active_plan(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    plan_dir = _add_plan(
        repo, "2026-05-25-bookmarks", ticked=True, spec_name="2026-05-25-bm-design.md"
    )
    _add_plan(repo, "2026-06-01-second", ticked=False, spec_name="2026-05-25-bm-design.md")
    _add_spec(
        repo,
        "2026-05-25-bm-design.md",
        [
            ("bm", "derio-net/test", "docs/superpowers/plans/2026-05-25-bookmarks"),
            ("second", "derio-net/test", "docs/superpowers/plans/2026-06-01-second"),
        ],
    )
    _seed(repo)
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 0, result.output
    assert (repo / "docs" / "superpowers" / "specs" / "2026-05-25-bm-design.md").is_file()


def test_archive_resolves_cross_repo_row_via_gh(tmp_path, monkeypatch):
    """A cross-repo row counts as implemented when the remote plan dir
    resolves under implemented/plans/ via the gh contents API."""
    repo = _repo(tmp_path)
    plan_dir = _add_plan(
        repo, "2026-05-25-bookmarks", ticked=True, spec_name="2026-05-25-bm-design.md"
    )
    _add_spec(
        repo,
        "2026-05-25-bm-design.md",
        [
            ("bm", "derio-net/test", "docs/superpowers/plans/2026-05-25-bookmarks"),
            ("remote", "derio-net/other", "docs/superpowers/plans/2026-05-02-remote-plan"),
        ],
    )
    _seed(repo)
    gh = FakeGhClient()
    gh.remote_files.add(
        ("derio-net/other", "docs/superpowers/implemented/plans/2026-05-02-remote-plan")
    )
    result = _invoke(monkeypatch, repo, gh, ["archive", str(plan_dir.relative_to(repo))])
    assert result.exit_code == 0, result.output
    sp = repo / "docs" / "superpowers"
    assert (sp / "implemented" / "specs" / "2026-05-25-bm-design.md").is_file()


def test_archive_keeps_spec_when_cross_repo_row_unresolved(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    plan_dir = _add_plan(
        repo, "2026-05-25-bookmarks", ticked=True, spec_name="2026-05-25-bm-design.md"
    )
    _add_spec(
        repo,
        "2026-05-25-bm-design.md",
        [
            ("bm", "derio-net/test", "docs/superpowers/plans/2026-05-25-bookmarks"),
            ("remote", "derio-net/other", "docs/superpowers/plans/2026-05-02-remote-plan"),
        ],
    )
    _seed(repo)
    gh = FakeGhClient()  # remote_files empty -> unresolved
    result = _invoke(monkeypatch, repo, gh, ["archive", str(plan_dir.relative_to(repo))])
    assert result.exit_code == 0, result.output
    assert (repo / "docs" / "superpowers" / "specs" / "2026-05-25-bm-design.md").is_file()
    assert "confirm and re-run" in result.output or "unresolved" in result.output


# --- T3: --all sweep + apply nudge ---


def test_archive_all_sweeps_and_decides_specs_at_end(tmp_path, monkeypatch):
    """Two complete plans of one spec archive in one sweep; the spec moves
    because the decision runs after the walk (order independence)."""
    repo = _repo(tmp_path)
    _add_plan(repo, "2026-05-01-a", ticked=True, spec_name="2026-05-01-ab-design.md")
    _add_plan(repo, "2026-05-02-b", ticked=True, spec_name="2026-05-01-ab-design.md")
    _add_plan(repo, "2026-06-01-active", ticked=False)
    _add_spec(
        repo,
        "2026-05-01-ab-design.md",
        [
            ("a", "derio-net/test", "docs/superpowers/plans/2026-05-01-a"),
            ("b", "derio-net/test", "docs/superpowers/plans/2026-05-02-b"),
        ],
    )
    _seed(repo)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    sp = repo / "docs" / "superpowers"
    assert (sp / "implemented" / "plans" / "2026-05-01-a").is_dir()
    assert (sp / "implemented" / "plans" / "2026-05-02-b").is_dir()
    assert (sp / "implemented" / "specs" / "2026-05-01-ab-design.md").is_file()
    # The incomplete plan is skipped with a reason, not archived.
    assert (sp / "plans" / "2026-06-01-active").is_dir()
    assert "skipped" in result.output


def test_archive_all_refuses_force(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _seed(repo)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all", "--force"])
    assert result.exit_code == 2, result.output


def test_apply_dry_run_prints_archive_nudge(tmp_path, monkeypatch):
    """apply's dry-run nudges toward fr archive when the gate passes (the
    plan has landed on origin/main: `_seed`)."""
    from fr.commands import apply_cmd

    repo = _repo(tmp_path)
    plan_dir = _add_plan(repo, "2026-05-25-bookmarks", ticked=True)
    _seed(repo)
    rc, text, _json = apply_cmd._apply_one(plan_dir, FakeGhClient(), yes=False)
    assert rc == 0
    assert "plan complete — run `fr archive" in text


# --- Phase 7 (2026-08-14 workflow-shapes-and-workitem-dispatch): run state ---


def test_archive_moves_run_state_file_alongside_its_plan(tmp_path, monkeypatch):
    """A run file archives to implemented/runs/ in the same operation as the
    plan its `plan` step emitted, mirroring `_archive_journal`.

    The run id and the plan slug are DELIBERATELY UNRELATED here — a run id
    is `<date>-<flattened-branch>` (fr.commands.run_cmd.derive_run_id) while
    a plan slug is authored independently, so this fixture would fail
    against a name-keyed lookup even though it is exactly the realistic
    case (spec §4.B, corrected in the Phase 7 review: a name-equality
    fixture would have hidden that bug rather than catching it). Matching
    is by the DATA the run file already carries — the `plan` step's
    recorded `emitted.plan` path — never by any slug convention.
    """
    repo = _repo(tmp_path)
    plan_dir = _add_plan(repo, "2026-08-20-goal-output", ticked=True)
    runs_dir = repo / "docs" / "superpowers" / "runs"
    runs_dir.mkdir(parents=True)
    run_id = "2026-08-24-feat-fr-goal-composable-workflow"
    run_file = runs_dir / f"{run_id}.yaml"
    run_file.write_text(
        "run: 2026-08-24-feat-fr-goal-composable-workflow\n"
        "workflow: fr-goal@1\n"
        "branch: feat/fr-goal-composable-workflow\n"
        "started: '2026-08-24T09:00:00Z'\n"
        "cursor: plan-review\n"
        "steps:\n"
        "  isolate: {state: done}\n"
        "  brainstorm:\n"
        "    state: done\n"
        "    emitted: {spec: docs/superpowers/specs/2026-08-20-goal-output-design.md}\n"
        "  plan:\n"
        "    state: done\n"
        "    emitted: {plan: docs/superpowers/plans/2026-08-20-goal-output}\n"
        "  plan-review: {state: pending}\n"
    )
    _seed(repo)
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 0, result.output
    assert not run_file.exists()
    moved = repo / "docs" / "superpowers" / "implemented" / "runs" / f"{run_id}.yaml"
    assert moved.is_file()
    assert "plan: docs/superpowers/plans/2026-08-20-goal-output" in moved.read_text()


def test_archive_does_not_move_an_unrelated_run_file_of_the_same_name(tmp_path, monkeypatch):
    """A run file that happens to share the plan's slug but was never
    resolved to it (no `emitted.plan` pointing at this plan) is untouched —
    proof the lookup is data-keyed, not name-keyed."""
    repo = _repo(tmp_path)
    plan_dir = _add_plan(repo, "2026-08-20-goal-output", ticked=True)
    runs_dir = repo / "docs" / "superpowers" / "runs"
    runs_dir.mkdir(parents=True)
    decoy = runs_dir / "2026-08-20-goal-output.yaml"
    decoy.write_text(
        "run: 2026-08-20-goal-output\n"
        "workflow: fr-goal@1\n"
        "branch: some/other/branch\n"
        "started: '2026-01-01T00:00:00Z'\n"
        "cursor: isolate\n"
        "steps:\n"
        "  isolate: {state: pending}\n"
    )
    _seed(repo)
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 0, result.output
    assert decoy.exists()
    assert not (repo / "docs" / "superpowers" / "implemented" / "runs").exists()


def test_archive_is_a_no_op_when_no_run_file_exists(tmp_path, monkeypatch):
    """Back-compat: a plan with no matching run file archives exactly as it
    did before this phase — no `implemented/runs/` directory materializes."""
    repo = _repo(tmp_path)
    plan_dir = _add_plan(repo, "2026-05-25-bookmarks", ticked=True)
    _seed(repo)
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 0, result.output
    assert not (repo / "docs" / "superpowers" / "implemented" / "runs").exists()


# --- 2026-06-06 review fixes ---


def test_archive_all_sweeps_stranded_spec_with_no_plan_moves(tmp_path, monkeypatch):
    """A spec whose plans all archived in PRIOR runs must still be swept by
    a later `fr archive --all` (review finding: the sweep ran only when a
    plan moved this run, diverging from `fr migrate dirs`)."""
    repo = _repo(tmp_path)
    # Plan already archived; spec left behind (e.g. unresolved back then).
    implemented = repo / "docs" / "superpowers" / "implemented" / "plans" / "2026-05-01-a"
    shutil.copytree(FIXTURE, implemented)
    _add_spec(
        repo,
        "2026-05-01-a-design.md",
        [("a", "derio-net/test", "docs/superpowers/plans/2026-05-01-a")],
    )
    _seed(repo)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    sp = repo / "docs" / "superpowers"
    assert (sp / "implemented" / "specs" / "2026-05-01-a-design.md").is_file()


def test_archive_refuses_plan_dir_outside_repo(tmp_path, monkeypatch):
    """Out-of-repo plan dir: clean exit 2, not a ValueError traceback."""
    repo = _repo(tmp_path / "repo-a")
    _seed(repo)
    other = tmp_path / "repo-b" / "docs" / "superpowers" / "plans" / "2026-05-25-elsewhere"
    shutil.copytree(FIXTURE, other)
    phase = other / "01.yaml"
    phase.write_text(phase.read_text().replace('state: " "', "state: x"))
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", str(other)])
    assert result.exit_code == 2, result.output
    assert "not under this repo" in result.output
    assert other.exists()


# ── 2026-06-06 spec-path-repair: repair in passing ──────────────────


def test_archive_repairs_stale_refs_in_passing(tmp_path, monkeypatch):
    """After archiving, the repo has zero stale-form refs: the spec row
    that recorded the plan's active path is normalized to the bare slug
    in the same operation."""
    repo = _repo(tmp_path)
    spec = _add_spec(
        repo,
        "2026-06-06-fixture-spec.md",
        [("Plan X", "`derio-net/test`", "docs/superpowers/plans/2026-06-06-done/")],
    )
    plan_dir = _add_plan(repo, "2026-06-06-done", ticked=True, spec_name=spec.name)
    _seed(repo)
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 0, result.output
    # spec moved too (single row, now implemented) — find it wherever it lives
    moved_spec = repo / "docs" / "superpowers" / "implemented" / "specs" / spec.name
    text = (moved_spec if moved_spec.exists() else spec).read_text()
    assert "| `2026-06-06-done` |" in text
    assert "docs/superpowers/plans/2026-06-06-done" not in text


# --- --no-spec-sweep flag (2026-07-05 spec-sweep slice guard, #351) ---


def test_no_spec_sweep_flag_skips_sweep(tmp_path, monkeypatch):
    """`--no-spec-sweep` archives the plan but leaves the spec sweep unrun:
    a spec that a normal run WOULD move to implemented/specs/ stays put."""
    repo = _repo(tmp_path)
    plan_dir = _add_plan(
        repo, "2026-05-25-bookmarks", ticked=True, spec_name="2026-05-25-bm-design.md"
    )
    # Only row points at THIS plan; after archive it resolves to
    # implemented/plans/, so without the flag the spec would sweep.
    _add_spec(
        repo,
        "2026-05-25-bm-design.md",
        [("bm", "derio-net/test", "docs/superpowers/plans/2026-05-25-bookmarks")],
    )
    _seed(repo)
    result = _invoke(
        monkeypatch,
        repo,
        FakeGhClient(),
        ["archive", str(plan_dir.relative_to(repo)), "--no-spec-sweep"],
    )
    assert result.exit_code == 0, result.output
    sp = repo / "docs" / "superpowers"
    # plan archived …
    assert (sp / "implemented" / "plans" / "2026-05-25-bookmarks").is_dir()
    assert not plan_dir.exists()
    # … but the spec was NOT swept
    assert (sp / "specs" / "2026-05-25-bm-design.md").is_file()
    assert not (sp / "implemented" / "specs" / "2026-05-25-bm-design.md").exists()
    assert "spec sweep skipped" in result.output


# --- --sweep-only: re-run the spec sweep with no plan dir ---


def _strand_plan(repo: Path, slug: str) -> None:
    """Simulate a prior run's plan move, committed: the plan already lives
    under implemented/plans/ (as when a TBD stub blocked the spec sweep, was
    removed afterwards, and no CLI could finish the job)."""
    import subprocess

    src = repo / "docs" / "superpowers" / "plans" / slug
    dst = repo / "docs" / "superpowers" / "implemented" / "plans" / slug
    subprocess.run(["git", "-C", str(repo), "mv", str(src), str(dst)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            "strand",
            "--allow-empty",
        ],
        check=True,
    )


def test_sweep_only_archives_stranded_eligible_spec(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _add_plan(repo, "2026-05-25-bookmarks", ticked=True, spec_name="2026-05-25-bm-design.md")
    _add_spec(
        repo,
        "2026-05-25-bm-design.md",
        # Row already points at the ARCHIVED plan — the stranded state.
        [("bm", "derio-net/test", "docs/superpowers/implemented/plans/2026-05-25-bookmarks")],
    )
    _seed(repo)
    # Seed AFTER the fixture so the tree is clean (moves stage changes).
    _strand_plan(repo, "2026-05-25-bookmarks")
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--sweep-only"])

    assert result.exit_code == 0, result.output
    sp = repo / "docs" / "superpowers"
    assert (sp / "implemented" / "specs" / "2026-05-25-bm-design.md").is_file()
    assert not (sp / "specs" / "2026-05-25-bm-design.md").exists()


def test_sweep_only_leaves_ineligible_spec_with_a_note(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _add_plan(repo, "2026-05-25-bookmarks", ticked=True, spec_name="2026-05-25-bm-design.md")
    _add_plan(repo, "2026-06-01-active", ticked=False, spec_name="2026-05-25-bm-design.md")
    _add_spec(
        repo,
        "2026-05-25-bm-design.md",
        [
            ("bm", "derio-net/test", "docs/superpowers/implemented/plans/2026-05-25-bookmarks"),
            ("second", "derio-net/test", "docs/superpowers/plans/2026-06-01-active"),
        ],
    )
    _seed(repo)
    _strand_plan(repo, "2026-05-25-bookmarks")

    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--sweep-only"])

    assert result.exit_code == 0, result.output
    assert (repo / "docs" / "superpowers" / "specs" / "2026-05-25-bm-design.md").is_file()


def test_sweep_only_refuses_plan_dir_and_all_and_force(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _seed(repo)
    for argv in (
        ["archive", "--sweep-only", "docs/superpowers/plans/x"],
        ["archive", "--sweep-only", "--all"],
        ["archive", "--sweep-only", "--force"],
        ["archive", "--sweep-only", "--no-spec-sweep"],
    ):
        result = _invoke(monkeypatch, repo, FakeGhClient(), argv)
        assert result.exit_code == 2, (argv, result.output)


# --- #544: the gate requires landed evidence (spec 2026-09-23 §3.C, §5 item 6) ---


def test_archive_refuses_a_plan_that_is_complete_locally_but_not_on_the_ref(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    plan_dir = _add_plan(repo, "2026-06-01-unmerged", ticked=True)
    _seed(repo, landed=False)
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 2, result.output
    assert "Phase 1: complete locally, not on origin/main; merge the PR first" in result.output
    assert plan_dir.exists()


def test_archive_refuses_a_plan_whose_newest_phase_exists_only_locally(tmp_path, monkeypatch):
    """Phase 1 merged; phase 2 was added and ticked on the branch afterwards.
    `landed` is per phase, so the local-only phase 2 blocks (f-p2-local-phases)."""
    repo = _repo(tmp_path)
    _write_plan(repo, "2026-06-01-grown", [("agentic", True)])
    _seed(repo)
    plan_dir = _write_plan(repo, "2026-06-01-grown", [("agentic", True), ("agentic", True)])
    _commit(repo, "phase 2 on the branch")
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 2, result.output
    assert "Phase 2: complete locally, not on origin/main" in result.output
    assert "Phase 1" not in result.output
    assert plan_dir.exists()


def test_archive_refuses_when_the_merge_state_is_unknown(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    plan_dir = _add_plan(repo, "2026-06-01-no-remote", ticked=True)
    _seed(repo, remote=False)
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 2, result.output
    assert "merge state unknown (" in result.output
    assert "add a remote or use --force" in result.output
    assert plan_dir.exists()


def test_archive_all_skips_unlanded_plans_and_archives_landed_ones(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _add_plan(repo, "2026-05-01-landed", ticked=True)
    _seed(repo)
    _add_plan(repo, "2026-05-02-unmerged", ticked=True)
    _commit(repo, "branch-only plan")
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    sp = repo / "docs" / "superpowers"
    assert (sp / "implemented" / "plans" / "2026-05-01-landed").is_dir()
    assert (sp / "plans" / "2026-05-02-unmerged").is_dir()
    assert "2026-05-02-unmerged: skipped" in result.output
    assert "not on origin/main" in result.output


def test_archive_moves_a_landed_plan_whose_manual_phase_is_ticked_only_locally(
    tmp_path, monkeypatch
):
    """The fr-goal close-out: the trailing manual phase merged unticked and
    was ticked after merge on the operator's checkout."""
    repo = _repo(tmp_path)
    name = "2026-06-01-closeout"
    _write_plan(repo, name, [("agentic", True), ("manual", False)])
    _seed(repo)
    plan_dir = _write_plan(repo, name, [("agentic", True), ("manual", True)])
    _commit(repo, "close-out: tick the manual phase")
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 0, result.output
    assert not plan_dir.exists()
    assert (repo / "docs" / "superpowers" / "implemented" / "plans" / name).is_dir()


def test_archive_force_still_archives_a_single_unlanded_plan(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    plan_dir = _add_plan(repo, "2026-06-01-unmerged", ticked=True)
    _seed(repo, landed=False)
    result = _invoke(
        monkeypatch,
        repo,
        FakeGhClient(),
        ["archive", str(plan_dir.relative_to(repo)), "--force"],
    )
    assert result.exit_code == 0, result.output
    assert not plan_dir.exists()


def test_archive_all_computes_merge_evidence_once_per_invocation(tmp_path, monkeypatch, _hermetic):
    repo = _repo(tmp_path)
    for slug in ("2026-05-01-a", "2026-05-02-b", "2026-05-03-c"):
        _add_plan(repo, slug, ticked=True)
    _seed(repo)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    assert _hermetic == ["origin"]


def test_archive_single_plan_fetches_once(tmp_path, monkeypatch, _hermetic):
    repo = _repo(tmp_path)
    plan_dir = _add_plan(repo, "2026-05-01-a", ticked=True)
    _seed(repo)
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 0, result.output
    assert _hermetic == ["origin"]


# --- scoped repair (2026-09-26 archive-repair-scope) ---


def _live_plan_with_full_spec(repo: Path, slug: str) -> Path:
    spec = repo / "docs" / "superpowers" / "specs" / "other-design.md"
    spec.write_text("# other\n")
    return _add_plan(repo, slug, ticked=False, spec_name=spec.name)


def test_single_plan_archive_leaves_other_live_plans_byte_identical(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    done = _add_plan(repo, "2026-09-01-done", ticked=True)
    other = _live_plan_with_full_spec(repo, "2026-09-02-other")
    _seed(repo)
    before = (other / "_meta.yaml").read_bytes()
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", str(done.relative_to(repo))])
    assert result.exit_code == 0, result.output
    assert (other / "_meta.yaml").read_bytes() == before


def test_single_plan_archive_canonicalizes_the_archived_plans_own_spec(tmp_path, monkeypatch):
    """#686 r2-f3: the positive half of scoping — the archived plan's own
    full-path `spec:` is still repaired to the bare form."""
    repo = _repo(tmp_path)
    spec = repo / "docs" / "superpowers" / "specs" / "done-design.md"
    spec.write_text("# done\n")
    done = _add_plan(repo, "2026-09-01-done", ticked=True, spec_name=spec.name)
    _seed(repo)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", str(done.relative_to(repo))])
    assert result.exit_code == 0, result.output
    archived = repo / "docs" / "superpowers" / "implemented" / "plans" / done.name
    assert "spec: done-design.md\n" in (archived / "_meta.yaml").read_text()


def test_archive_all_still_repairs_repo_wide(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _add_plan(repo, "2026-09-01-done", ticked=True)
    other = _live_plan_with_full_spec(repo, "2026-09-02-other")
    _seed(repo)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    assert "spec: other-design.md" in (other / "_meta.yaml").read_text()


def test_sweep_only_still_repairs_repo_wide(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    spec = _add_spec(
        repo, "2026-09-fixture.md", [("Plan X", "`derio-net/test`", "2026-09-03-gone")]
    )
    (repo / "docs/superpowers/implemented/plans/2026-09-03-gone").mkdir()
    other = _live_plan_with_full_spec(repo, "2026-09-02-other")
    _seed(repo)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--sweep-only"])
    assert result.exit_code == 0, result.output
    assert (repo / "docs/superpowers/implemented/specs" / spec.name).exists()
    assert "spec: other-design.md" in (other / "_meta.yaml").read_text()
