"""Regression guard for the apply_cmd -> apply(plan=...) propagation bug
surfaced during the v2-bridge-rebuild dispatch on 2026-05-17.

Without `plan=` being forwarded, `apply()` skips
`_rerender_dependent_creates` and every `IssueCreate` mutation keeps the
phase-number-fallback body (`- Blocked by #1` instead of
`- Blocked by #<actual-issue-N>`). Any body-parsing consumer (the legacy
bridge until Phase 6, plus any future tool) is then misled and can
dispatch phases out of order.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from fr.apply import ApplyResult
from fr.commands import apply_cmd
from fr.parser import parse

from tests.unit.fakes import FakeGhClient


def test_apply_cmd_propagates_plan_to_apply(monkeypatch):
    """
    GIVEN a multi-phase plan loaded via vk.parser.parse
    WHEN  apply_cmd._apply_one runs with --yes (apply() mocked to capture kwargs)
    THEN  the call includes plan=<plan-instance>, ensuring the renderer's
          phase_to_issue map is built and dependent bodies are re-rendered
          with the correct issue numbers (NOT the phase-number fallback).
    """
    fixture = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan = parse(fixture)

    captured: dict = {}

    def fake_apply(d, gh, **kwargs):
        captured["kwargs"] = kwargs
        return ApplyResult(
            applied=(),
            failures=(),
            created_issues={},
            dry_run=False,
        )

    monkeypatch.setattr(apply_cmd, "apply", fake_apply)
    monkeypatch.setattr(
        apply_cmd, "_check_plan_reachable_on_origin_head", lambda plan, repo_root: []
    )

    rc, _text, _json_out = apply_cmd._apply_one(fixture, FakeGhClient(), yes=True)

    assert rc == 0, f"_apply_one returned rc={rc}"
    assert "kwargs" in captured, "apply() was not called"
    assert "plan" in captured["kwargs"], (
        "apply_cmd must pass plan= to apply() so dependent bodies "
        "re-render with correct issue numbers"
    )
    assert captured["kwargs"]["plan"].meta.plan == plan.meta.plan


def test_check_plan_reachable_skips_cross_repo_spec(monkeypatch):
    """Cross-repo spec refs (`<owner>/<repo>:path/to/spec.md`) must NOT
    be flagged as missing from the local repo's `origin/HEAD`.

    Surfaced 2026-05-18 when the agent-images cutover plan (whose spec
    lives in superpowers-for-vk) couldn't be dispatched via
    `fr apply --yes` — the gate treated the literal cross-repo path
    as a same-repo filename, `git ls-tree` returned empty, gate refused.
    """
    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    plan = parse(fixture)
    # Override spec on the loaded plan to be a cross-repo ref. The fixture's
    # spec is a same-repo ref, which would still hit `file_on_ref`.
    cross_repo_spec = "derio-net/superpowers-for-vk:docs/superpowers/specs/some-other-design.md"
    plan_with_cross_repo_spec = plan.__class__(
        dir=plan.dir,
        meta=plan.meta.model_copy(update={"spec": cross_repo_spec}),
        phases=plan.phases,
        repo_root=plan.repo_root,
    )

    # Track all file_on_ref calls so we can assert the cross-repo path
    # is never passed to it.
    checked_paths: list[str] = []

    def fake_file_on_ref(ref, path, cwd=None):
        checked_paths.append(path)
        return True  # pretend every checked file exists

    monkeypatch.setattr(apply_cmd, "file_on_ref", fake_file_on_ref)

    missing = apply_cmd._check_plan_reachable_on_origin_head(
        plan_with_cross_repo_spec, plan.repo_root or plan.dir
    )

    assert missing == [], f"Cross-repo spec should not be flagged as missing; got: {missing}"
    # Cross-repo spec path must NEVER be passed to file_on_ref
    assert cross_repo_spec not in checked_paths, (
        f"Cross-repo spec should not be checked via local file_on_ref; got checks: {checked_paths}"
    )


def test_check_plan_reachable_still_checks_same_repo_spec(monkeypatch):
    """The skip only fires for cross-repo notation. Same-repo specs
    must continue to be reachability-checked (regression guard against
    over-eager skipping)."""
    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    plan = parse(fixture)

    # Same-repo spec path (no `:` separator)
    same_repo_spec = "docs/superpowers/specs/v2-bridge-rebuild-design.md"
    plan_same_repo = plan.__class__(
        dir=plan.dir,
        meta=plan.meta.model_copy(update={"spec": same_repo_spec}),
        phases=plan.phases,
        repo_root=plan.repo_root,
    )

    checked_paths: list[str] = []

    def fake_file_on_ref(ref, path, cwd=None):
        checked_paths.append(path)
        return True

    monkeypatch.setattr(apply_cmd, "file_on_ref", fake_file_on_ref)

    apply_cmd._check_plan_reachable_on_origin_head(plan_same_repo, plan.repo_root or plan.dir)

    assert same_repo_spec in checked_paths, (
        f"Same-repo spec MUST be checked via file_on_ref; got checks: {checked_paths}"
    )


def test_apply_legacy_layout_hard_stops_before_archived_refusal(tmp_path, monkeypatch):
    """A repo still on archived-plans/ trips the LAYOUT guard first — the
    #246 archived-plan refusal can no longer be reached on legacy layouts.
    Its protection lives on for the canonical layout via
    `test_apply_refuses_implemented_plan` below.
    """
    from fr.cli import app
    from typer.testing import CliRunner

    archived = tmp_path / "docs" / "superpowers" / "archived-plans" / "2026-05-10-done"
    archived.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))

    result = CliRunner().invoke(app, ["apply", "docs/superpowers/archived-plans/2026-05-10-done"])
    assert result.exit_code == 2, result.output
    assert "fr migrate dirs" in result.output


# --- 2026-06-05 stale-plan dispatch guard (completion guard in apply) ---


def _ticked_plan_repo(tmp_path: Path) -> Path:
    """Copy the minimal fixture into a fresh git repo with its one step
    ticked — the bookmarks-incident shape (locally complete, never
    dispatched). Returns the plan dir."""
    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    plan_dir = tmp_path / "docs" / "superpowers" / "plans" / "2026-05-09-fixture-minimal"
    shutil.copytree(fixture, plan_dir)
    phase = plan_dir / "01.yaml"
    phase.write_text(phase.read_text().replace('state: " "', "state: x"))
    for cmd in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
    ):
        subprocess.run(cmd, cwd=tmp_path, check=True)
    return plan_dir


def test_apply_dry_run_reports_suppression_and_header(tmp_path):
    plan_dir = _ticked_plan_repo(tmp_path)
    rc, text, json_out = apply_cmd._apply_one(plan_dir, FakeGhClient(), yes=False)
    assert rc == 0
    # Factual header line: created date, age, tick counts, dispatch state.
    assert "created 2026-05-09 (" in text
    assert "days ago)" in text
    assert "1/1 steps" in text
    assert "never dispatched" in text
    # Suppression rendered, with the --force hint.
    assert "would refuse" in text.lower() or "refusing" in text.lower()
    assert "--force" in text
    assert json_out["suppressed"] == [
        {"phase_number": 1, "reason": json_out["suppressed"][0]["reason"]}
    ]
    assert "1/1" in json_out["suppressed"][0]["reason"]


def test_apply_yes_all_suppressed_exits_2_with_archive_hint(tmp_path):
    plan_dir = _ticked_plan_repo(tmp_path)
    gh = FakeGhClient()
    rc, text, _json_out = apply_cmd._apply_one(plan_dir, gh, yes=True)
    assert rc == 2, text
    assert "fr archive" in text
    creates = [c for c in gh.calls if c[0] == "create_issue"]
    assert creates == [], "guard must prevent Issue creation"


def test_apply_yes_force_creates_issues(tmp_path, monkeypatch):
    plan_dir = _ticked_plan_repo(tmp_path)
    monkeypatch.setattr(
        apply_cmd, "_check_plan_reachable_on_origin_head", lambda plan, repo_root: []
    )
    gh = FakeGhClient()
    rc, text, json_out = apply_cmd._apply_one(plan_dir, gh, yes=True, force=True)
    assert rc == 0, text
    assert json_out["created_issues"], "with --force the Issue must be created"


def test_apply_cli_exposes_force_flag(tmp_path, monkeypatch):
    """Strip ANSI before asserting: rich styles --help differently across
    environments (CI injected escape codes inside the option token)."""
    import re

    from fr.cli import app
    from typer.testing import CliRunner

    result = CliRunner().invoke(app, ["apply", "--help"])
    assert result.exit_code == 0
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert "--force" in plain


def test_apply_dry_run_json_suppressed_alongside_real_mutations(tmp_path):
    """Mixed plan: the JSON `suppressed` array coexists with IssueCreate
    mutations for the incomplete phases (downstream-consumer shape)."""
    fixture = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    plan_dir = tmp_path / "docs" / "superpowers" / "plans" / "multi"
    shutil.copytree(fixture, plan_dir)
    phase = plan_dir / "01.yaml"
    phase.write_text(phase.read_text().replace('state: " "', "state: x"))
    rc, _text, json_out = apply_cmd._apply_one(plan_dir, FakeGhClient(), yes=False)
    assert rc == 0
    assert {s["phase_number"] for s in json_out["suppressed"]} == {1}
    created_phases = {
        m["phase_number"] for m in json_out["mutations"] if m["kind"] == "IssueCreate"
    }
    assert created_phases and 1 not in created_phases


def test_apply_refuses_implemented_plan(tmp_path, monkeypatch):
    """implemented/plans/ is terminal exactly like legacy archived-plans/."""
    from fr.cli import app
    from typer.testing import CliRunner

    done = tmp_path / "docs" / "superpowers" / "implemented" / "plans" / "2026-05-10-done"
    done.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        app, ["apply", "docs/superpowers/implemented/plans/2026-05-10-done"]
    )
    assert result.exit_code == 2, result.output
    assert "implemented" in result.output.lower() or "archived" in result.output.lower()


def test_check_plan_reachable_uses_resolved_spec_path(monkeypatch):
    """Slug-form (canonical) spec refs must be reachability-checked at
    their RESOLVED repo path, not the raw slug — otherwise every
    repaired plan would be refused dispatch (2026-06-06 dogfood find)."""
    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    plan = parse(fixture)

    plan_slug_spec = plan.__class__(
        dir=plan.dir,
        meta=plan.meta.model_copy(update={"spec": "x-design.md"}),
        phases=plan.phases,
        repo_root=plan.repo_root,
        spec_path="docs/superpowers/implemented/specs/x-design.md",  # parse-time resolution
    )

    checked_paths: list[str] = []

    def fake_file_on_ref(ref, path, cwd=None):
        checked_paths.append(path)
        return True

    monkeypatch.setattr(apply_cmd, "file_on_ref", fake_file_on_ref)
    apply_cmd._check_plan_reachable_on_origin_head(plan_slug_spec, plan.repo_root or plan.dir)

    assert "docs/superpowers/implemented/specs/x-design.md" in checked_paths
    assert "x-design.md" not in checked_paths


def test_apply_to_unknown_runner_exits_2(tmp_path, monkeypatch):
    """--to with an unregistered name names the registered runners."""
    from fr.cli import app
    from typer.testing import CliRunner

    sp = tmp_path / "docs" / "superpowers" / "plans"
    sp.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    result = CliRunner().invoke(app, ["apply", "--all", "--to", "nope"])
    assert result.exit_code == 2
    combined = result.output + (result.stderr or "")
    assert "unknown runner 'nope'" in combined
    assert "vk" in combined  # the registered runner is listed


def test_apply_to_requires_fr_dispatch(tmp_path, monkeypatch):
    """The sanctioned soft point: --to without fr-dispatch installed
    exits 2 with the install hint."""
    import importlib.util

    from fr.cli import app
    from typer.testing import CliRunner

    real = importlib.util.find_spec

    def fake_find_spec(name, *a, **kw):
        if name == "fr_dispatch":
            return None
        return real(name, *a, **kw)

    monkeypatch.setattr("importlib.util.find_spec", fake_find_spec)
    sp = tmp_path / "docs" / "superpowers" / "plans"
    sp.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    result = CliRunner().invoke(app, ["apply", "--all", "--to", "vk"])
    assert result.exit_code == 2
    assert "requires fr-dispatch" in (result.output + (result.stderr or ""))
