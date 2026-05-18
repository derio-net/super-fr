"""Unit tests for `vk.bridge.discover_plans`.

We build a fake repo checkout under `tmp_path`, point `VK_REPOS_DIR` at it,
and stub the GhClient via FakeGhClient. Discovery is yaml-only as of
2026-05-18 — the gh client is no longer consulted, but we still pass one
through to exercise the public signature.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_META_TEMPLATE = """\
schema_version: 2
plan: {slug}
spec: docs/superpowers/specs/2026-05-06-vk-rebuild-state-machine-design.md
target_repo: derio-net/test
vk_version: ">=1.0.0,<3.0.0"
created: 2026-05-09
"""


_PHASE_TEMPLATE = """\
schema_version: 2
phase:
  number: 1
  title: {title}
  tag: agentic
  depends_on: []
  tracking_issue: {tracking_issue}
tasks:
  - number: 1
    title: t
    steps:
      - id: P1.T1.S1
        text: s
state:
  steps:
    P1.T1.S1:
      state: " "
      ticked_at: null
      note: null
  completion:
    at: {completion_at}
    note: null
    observed_prs: []
"""


def _write_plan(
    repo_root: Path,
    slug: str,
    *,
    tracking_issue: str | None,
    title: str = "p",
    completion_at: str | None = None,
) -> Path:
    plans_dir = repo_root / "docs" / "superpowers" / "plans"
    plan_dir = plans_dir / slug
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "_meta.yaml").write_text(_META_TEMPLATE.format(slug=slug))
    tracking_value = f"'{tracking_issue}'" if tracking_issue else "null"
    completion_value = f"'{completion_at}'" if completion_at else "null"
    (plan_dir / "01.yaml").write_text(
        _PHASE_TEMPLATE.format(
            title=title, tracking_issue=tracking_value, completion_at=completion_value
        )
    )
    (plan_dir / "_prose.md").write_text("prose\n")
    return plan_dir


@pytest.fixture
def repo_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set VK_REPOS_DIR to tmp_path and create the `test/` checkout dir."""
    monkeypatch.setenv("VK_REPOS_DIR", str(tmp_path))
    (tmp_path / "test").mkdir()
    return tmp_path / "test"


def test_discover_plans_returns_only_incomplete(repo_layout: Path) -> None:
    """Discovery returns plans where at least one phase is incomplete
    (completion.at is None). Fully-shipped plans are skipped to avoid
    wasted observe/render/diff cycles per tick.
    """
    from tests.unit.fakes import FakeGhClient
    from vk import parse
    from vk.bridge import discover_plans

    # Plan A: phase incomplete (completion.at null) — should be discovered.
    plan_a_dir = _write_plan(
        repo_layout,
        "2026-05-09-plan-a",
        tracking_issue="https://github.com/derio-net/test/issues/1",
        title="A",
        completion_at=None,
    )
    # Plan B: phase complete (completion.at set) — should be filtered out.
    _write_plan(
        repo_layout,
        "2026-05-09-plan-b",
        tracking_issue="https://github.com/derio-net/test/issues/2",
        title="B",
        completion_at="2026-05-10T12:00:00Z",
    )

    found = discover_plans("derio-net/test", FakeGhClient())

    assert len(found) == 1
    expected = parse(plan_a_dir)
    assert found[0].dir == expected.dir
    assert found[0].meta.plan == expected.meta.plan


def test_discover_plans_returns_incomplete_plan_even_when_no_label_observed(
    repo_layout: Path,
) -> None:
    """Regression guard for the 2026-05-18 chicken-and-egg bug.

    Pre-fix: discover_plans called `_any_phase_is_vk_ready` which queried
    gh for the `vk-ready` label. If an operator stripped that label (e.g.,
    as race protection during a writeback PR), the plan would be
    quarantined from discovery — tick never ran, so the label could
    never be re-projected.

    Post-fix: discovery is yaml-only. A plan with at least one incomplete
    phase is always discovered, regardless of what labels the Issue
    happens to carry on gh. The bridge's tick can then re-project the
    correct label via render → diff → apply.
    """
    from tests.unit.fakes import FakeGhClient
    from vk.bridge import discover_plans

    _write_plan(
        repo_layout,
        "2026-05-09-no-label-plan",
        tracking_issue="https://github.com/derio-net/test/issues/42",
        completion_at=None,
    )

    gh = FakeGhClient()
    # Issue exists on gh but carries NO vk-ready label. Pre-fix this would
    # have caused discover_plans to filter the plan out (gating).
    gh.add_issue("derio-net/test", 42, state="OPEN", labels={"phase:1"})

    found = discover_plans("derio-net/test", gh)

    assert len(found) == 1, (
        "Plan with incomplete phase MUST be discovered even when "
        "no Issue carries vk-ready — otherwise tick can't self-heal "
        "label drift."
    )


def test_discover_plans_returns_incomplete_plan_when_tracking_issue_null(
    repo_layout: Path,
) -> None:
    """Sibling regression: a plan that just got created via `vk apply --yes`
    on the operator's machine but whose writeback PR hasn't merged yet
    has `tracking_issue: null` on the bridge's local checkout. Pre-fix
    this caused _any_phase_is_vk_ready to skip the phase, filter the
    plan out, and never tick — even though the gh Issue already exists
    and is waiting for dispatch.
    """
    from tests.unit.fakes import FakeGhClient
    from vk.bridge import discover_plans

    _write_plan(
        repo_layout,
        "2026-05-09-no-tracking-plan",
        tracking_issue=None,  # writeback hasn't merged yet on bridge's checkout
        completion_at=None,
    )

    found = discover_plans("derio-net/test", FakeGhClient())

    assert len(found) == 1, (
        "Plan with incomplete phase + null tracking_issue MUST still be "
        "discovered so tick can run and possibly emit IssueCreate."
    )


def test_discover_plans_skips_fully_complete_plan(repo_layout: Path) -> None:
    """All phases complete → plan is shipped → no tick needed → skip.
    Perf optimization that doesn't regress in the new yaml-only filter.

    Also pins the "no gh API calls during discovery" contract: future
    refactors that re-introduce a per-phase `gh.view_issue` would fail
    this test even if the filter outcome stayed correct.
    """
    from tests.unit.fakes import FakeGhClient
    from vk.bridge import discover_plans

    _write_plan(
        repo_layout,
        "2026-05-09-shipped-plan",
        tracking_issue="https://github.com/derio-net/test/issues/1",
        completion_at="2026-05-10T12:00:00Z",
    )

    gh = FakeGhClient()
    # Wrap view_issue to count calls — discover_plans must make ZERO
    # gh API calls (yaml-only) regardless of plan state.
    view_issue_calls = 0
    original_view_issue = gh.view_issue

    def counting_view_issue(repo: str, number: int) -> dict[str, object]:
        nonlocal view_issue_calls
        view_issue_calls += 1
        return original_view_issue(repo, number)

    gh.view_issue = counting_view_issue  # type: ignore[method-assign]

    assert discover_plans("derio-net/test", gh) == []
    assert view_issue_calls == 0, (
        f"discover_plans MUST be yaml-only (zero gh API calls); "
        f"got {view_issue_calls} view_issue calls"
    )


def test_discover_plans_returns_empty_when_checkout_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.fakes import FakeGhClient
    from vk.bridge import discover_plans

    monkeypatch.setenv("VK_REPOS_DIR", str(tmp_path))  # checkout dir intentionally absent
    assert discover_plans("derio-net/missing", FakeGhClient()) == []


def test_discover_plans_returns_empty_when_plans_dir_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.fakes import FakeGhClient
    from vk.bridge import discover_plans

    monkeypatch.setenv("VK_REPOS_DIR", str(tmp_path))
    (tmp_path / "test").mkdir()  # checkout exists but no docs/superpowers/plans/
    assert discover_plans("derio-net/test", FakeGhClient()) == []


def test_discover_plans_skips_unparseable_plan_and_keeps_going(
    repo_layout: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from tests.unit.fakes import FakeGhClient
    from vk.bridge import discover_plans

    # A valid incomplete plan.
    _write_plan(
        repo_layout,
        "2026-05-09-good",
        tracking_issue="https://github.com/derio-net/test/issues/1",
        completion_at=None,
    )
    # A broken plan: _meta.yaml exists but is invalid yaml/schema.
    bad_dir = repo_layout / "docs" / "superpowers" / "plans" / "2026-05-09-bad"
    bad_dir.mkdir()
    (bad_dir / "_meta.yaml").write_text("not: a valid meta\nschema_version: nope\n")

    with caplog.at_level("WARNING", logger="vk.bridge"):
        found = discover_plans("derio-net/test", FakeGhClient())

    assert len(found) == 1
    assert found[0].meta.plan == "2026-05-09-good"
    assert any("2026-05-09-bad" in rec.getMessage() for rec in caplog.records)
