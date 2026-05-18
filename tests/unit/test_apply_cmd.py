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
