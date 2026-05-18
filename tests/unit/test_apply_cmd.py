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

from pathlib import Path

from tests.unit.fakes import FakeGhClient
from vk.apply import ApplyResult
from vk.commands import apply_cmd
from vk.parser import parse


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
    `vk apply --yes` — the gate treated the literal cross-repo path
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
