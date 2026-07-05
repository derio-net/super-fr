"""`fr archive` — gate, plan/spec moves, --all sweep (2026-06-05 spec, Phase 5)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from fr.cli import app
from fr.commands import archive_cmd
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient

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


def _git_seed(repo: Path) -> None:
    for cmd in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        [
            "git",
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            "seed",
            "--allow-empty",
        ],
    ):
        subprocess.run(cmd, cwd=repo, check=True)


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
    _git_seed(repo)
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
    _git_seed(repo)
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 2, result.output
    assert "Phase 1" in result.output
    assert plan_dir.exists()


def test_archive_force_overrides_gate(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    plan_dir = _add_plan(repo, "2026-06-01-known-done", ticked=False)
    _git_seed(repo)
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
    _git_seed(repo)
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
    _git_seed(repo)
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
    _git_seed(repo)
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
    _git_seed(repo)
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
    _git_seed(repo)
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
    _git_seed(repo)
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
    _git_seed(repo)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all", "--force"])
    assert result.exit_code == 2, result.output


def test_apply_dry_run_prints_archive_nudge(tmp_path, monkeypatch):
    """apply's dry-run nudges toward fr archive when the gate passes."""
    from fr.commands import apply_cmd

    repo = _repo(tmp_path)
    plan_dir = _add_plan(repo, "2026-05-25-bookmarks", ticked=True)
    _git_seed(repo)
    rc, text, _json = apply_cmd._apply_one(plan_dir, FakeGhClient(), yes=False)
    assert rc == 0
    assert "fr archive" in text


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
    _git_seed(repo)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    sp = repo / "docs" / "superpowers"
    assert (sp / "implemented" / "specs" / "2026-05-01-a-design.md").is_file()


def test_archive_refuses_plan_dir_outside_repo(tmp_path, monkeypatch):
    """Out-of-repo plan dir: clean exit 2, not a ValueError traceback."""
    repo = _repo(tmp_path / "repo-a")
    _git_seed(repo)
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
    _git_seed(repo)
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
    _git_seed(repo)
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
