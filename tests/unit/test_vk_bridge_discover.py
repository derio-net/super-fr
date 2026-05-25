"""Unit tests for `vk.bridge.discover_plans`.

We build a fake repo checkout under `tmp_path`, point `VK_REPOS_DIR` at it,
and stub the GhClient via FakeGhClient so the test never touches the
network. `vk.parse()` is used to construct the expected Plans because that
pins the structure the bridge will see at runtime.
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
    at: null
    note: null
    observed_prs: []
"""


def _write_plan(
    repo_root: Path, slug: str, *, tracking_issue: str | None, title: str = "p"
) -> Path:
    plans_dir = repo_root / "docs" / "superpowers" / "plans"
    plan_dir = plans_dir / slug
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "_meta.yaml").write_text(_META_TEMPLATE.format(slug=slug))
    tracking_value = f"'{tracking_issue}'" if tracking_issue else "null"
    (plan_dir / "01.yaml").write_text(
        _PHASE_TEMPLATE.format(title=title, tracking_issue=tracking_value)
    )
    (plan_dir / "_prose.md").write_text("prose\n")
    return plan_dir


@pytest.fixture
def repo_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set VK_REPOS_DIR to tmp_path and create the `test/` checkout dir."""
    monkeypatch.setenv("VK_REPOS_DIR", str(tmp_path))
    (tmp_path / "test").mkdir()
    return tmp_path / "test"


def test_discover_plans_returns_only_vk_ready(repo_layout: Path) -> None:
    from tests.unit.fakes import FakeGhClient
    from vk import parse
    from vk.bridge import discover_plans

    # Plan A: phase dispatched (tracking_issue set) and labelled vk-ready.
    plan_a_dir = _write_plan(
        repo_layout,
        "2026-05-09-plan-a",
        tracking_issue="https://github.com/derio-net/test/issues/1",
        title="A",
    )
    # Plan B: phase already dispatched (vk-synced) — nothing for the bridge to
    # do, so it renders vk-ready-but-synced and is correctly excluded.
    _write_plan(
        repo_layout,
        "2026-05-09-plan-b",
        tracking_issue="https://github.com/derio-net/test/issues/2",
        title="B",
    )

    gh = FakeGhClient()
    gh.add_issue("derio-net/test", 1, state="OPEN", labels={"vk-ready", "phase:1"})
    gh.add_issue("derio-net/test", 2, state="OPEN", labels={"phase:1", "vk-synced"})

    found = discover_plans("derio-net/test", gh)

    assert len(found) == 1
    expected = parse(plan_a_dir)
    assert found[0].dir == expected.dir
    assert found[0].meta.plan == expected.meta.plan


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


def test_discover_plans_survives_view_issue_failure_for_one_phase(
    repo_layout: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """If `gh.view_issue` raises for a phase (e.g., the Issue was deleted
    or gh is briefly flaky), the bridge logs and treats the phase as
    not-ready rather than crashing the whole tick.
    """
    from tests.unit.fakes import FakeGhClient
    from vk.bridge import discover_plans

    _write_plan(
        repo_layout,
        "2026-05-09-plan-a",
        tracking_issue="https://github.com/derio-net/test/issues/999",  # not added to gh
    )

    gh = FakeGhClient()  # no Issues registered — view_issue will KeyError

    with caplog.at_level("WARNING", logger="vk.bridge"):
        found = discover_plans("derio-net/test", gh)

    assert found == []  # phase not ready (couldn't view its Issue)
    # Discovery now renders (observe -> render); an unviewable Issue raises out
    # of observe and is caught per-plan. The warning names the plan dir + the
    # failing (repo, number) tuple.
    assert any(
        "2026-05-09-plan-a" in rec.getMessage() and "999" in rec.getMessage()
        for rec in caplog.records
    )


def test_discover_plans_skips_unparseable_plan_and_keeps_going(
    repo_layout: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from tests.unit.fakes import FakeGhClient
    from vk.bridge import discover_plans

    # A valid vk-ready plan.
    _write_plan(
        repo_layout,
        "2026-05-09-good",
        tracking_issue="https://github.com/derio-net/test/issues/1",
    )
    # A broken plan: _meta.yaml exists but is invalid yaml/schema.
    bad_dir = repo_layout / "docs" / "superpowers" / "plans" / "2026-05-09-bad"
    bad_dir.mkdir()
    (bad_dir / "_meta.yaml").write_text("not: a valid meta\nschema_version: nope\n")

    gh = FakeGhClient()
    gh.add_issue("derio-net/test", 1, state="OPEN", labels={"vk-ready"})

    with caplog.at_level("WARNING", logger="vk.bridge"):
        found = discover_plans("derio-net/test", gh)

    assert len(found) == 1
    assert found[0].meta.plan == "2026-05-09-good"
    assert any("2026-05-09-bad" in rec.getMessage() for rec in caplog.records)


def test_discover_plans_includes_phase_unblocked_by_completed_dependency(
    repo_layout: Path,
) -> None:
    """Regression: a phase whose dependency just completed must be discovered
    even though its OBSERVED label is still the stale `vk-blocked`.

    Discovery must use the RENDERED projection (what `tick()` would dispatch),
    not the observed label. Otherwise the blocked->ready flip never happens:
    discovery skips the plan, so the tick never runs, so the label is never
    updated — a deadlock that strands every multi-phase plan after a phase
    completes.
    """
    from tests.unit.fakes import FakeGhClient
    from vk.bridge import discover_plans

    plans_dir = repo_layout / "docs" / "superpowers" / "plans"
    pdir = plans_dir / "2026-05-09-twophase"
    pdir.mkdir(parents=True)
    (pdir / "_meta.yaml").write_text(
        "schema_version: 2\n"
        "plan: 2026-05-09-twophase\n"
        "spec: docs/superpowers/specs/2026-05-06-vk-rebuild-state-machine-design.md\n"
        "target_repo: derio-net/test\n"
        'vk_version: ">=1.0.0,<3.0.0"\n'
        "created: 2026-05-09\n"
    )
    (pdir / "_prose.md").write_text("prose\n")
    # Phase 1: complete — CLOSED, completion.at set, linked merged PR.
    (pdir / "01.yaml").write_text(
        "schema_version: 2\n"
        "phase:\n  number: 1\n  title: one\n  tag: agentic\n  depends_on: []\n"
        "  tracking_issue: 'https://github.com/derio-net/test/issues/1'\n"
        "tasks:\n- number: 1\n  title: t\n  steps:\n  - id: P1.T1.S1\n    text: s\n"
        "state:\n  steps:\n    P1.T1.S1:\n      state: x\n      ticked_at: null\n      note: null\n"
        "  completion:\n    at: '2026-05-09T00:00:00+00:00'\n    note: null\n    observed_prs: []\n"
    )
    # Phase 2: depends on phase 1; OPEN; observed label still the stale vk-blocked.
    (pdir / "02.yaml").write_text(
        "schema_version: 2\n"
        "phase:\n  number: 2\n  title: two\n  tag: agentic\n  depends_on:\n  - 1\n"
        "  tracking_issue: 'https://github.com/derio-net/test/issues/2'\n"
        "tasks:\n- number: 1\n  title: t\n  steps:\n  - id: P2.T1.S1\n    text: s\n"
        "state:\n  steps:\n    P2.T1.S1:\n      state: ' '\n      ticked_at: null\n"
        "      note: null\n"
        "  completion:\n    at: null\n    note: null\n    observed_prs: []\n"
    )

    gh = FakeGhClient()
    gh.add_issue(
        "derio-net/test",
        1,
        state="CLOSED",
        labels={"phase:1", "vk-synced"},
        linked_prs=[
            {
                "url": "https://github.com/derio-net/test/pull/3",
                "state": "CLOSED",
                "merged": True,
                "ci": "PASS",
            }
        ],
    )
    gh.add_issue("derio-net/test", 2, state="OPEN", labels={"phase:2", "vk-blocked"})

    found = discover_plans("derio-net/test", gh)
    assert len(found) == 1, "phase unblocked by a completed dependency must be discoverable"
    assert found[0].meta.plan == "2026-05-09-twophase"


def test_discover_plans_skips_whole_plan_when_a_phase_issue_unviewable(
    repo_layout: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Discovery renders (observe -> render); observe raises on the first
    unviewable phase Issue, so the WHOLE plan is skipped for this tick (logged,
    not crashed). This is intentional and consistent with `tick()`, which also
    calls bare `observe()` and would fail to observe the same plan — so a
    per-phase 'continue' here would only let discovery surface a plan that tick
    then can't process. Transient: the next tick retries once the Issue is
    viewable again.
    """
    from tests.unit.fakes import FakeGhClient
    from vk.bridge import discover_plans

    plans_dir = repo_layout / "docs" / "superpowers" / "plans"
    pdir = plans_dir / "2026-05-09-twophase-badissue"
    pdir.mkdir(parents=True)
    (pdir / "_meta.yaml").write_text(
        "schema_version: 2\n"
        "plan: 2026-05-09-twophase-badissue\n"
        "spec: docs/superpowers/specs/2026-05-06-vk-rebuild-state-machine-design.md\n"
        "target_repo: derio-net/test\n"
        'vk_version: ">=1.0.0,<3.0.0"\n'
        "created: 2026-05-09\n"
    )
    (pdir / "_prose.md").write_text("prose\n")
    # Phase 1: tracking Issue #1 — registered and would render vk-ready.
    (pdir / "01.yaml").write_text(
        "schema_version: 2\n"
        "phase:\n  number: 1\n  title: one\n  tag: agentic\n  depends_on: []\n"
        "  tracking_issue: 'https://github.com/derio-net/test/issues/1'\n"
        "tasks:\n- number: 1\n  title: t\n  steps:\n  - id: P1.T1.S1\n    text: s\n"
        "state:\n  steps:\n    P1.T1.S1:\n      state: ' '\n      ticked_at: null\n"
        "      note: null\n"
        "  completion:\n    at: null\n    note: null\n    observed_prs: []\n"
    )
    # Phase 2: tracking Issue #999 — NOT registered; observe() will raise on it.
    (pdir / "02.yaml").write_text(
        "schema_version: 2\n"
        "phase:\n  number: 2\n  title: two\n  tag: agentic\n  depends_on: []\n"
        "  tracking_issue: 'https://github.com/derio-net/test/issues/999'\n"
        "tasks:\n- number: 1\n  title: t\n  steps:\n  - id: P2.T1.S1\n    text: s\n"
        "state:\n  steps:\n    P2.T1.S1:\n      state: ' '\n      ticked_at: null\n"
        "      note: null\n"
        "  completion:\n    at: null\n    note: null\n    observed_prs: []\n"
    )

    gh = FakeGhClient()
    gh.add_issue("derio-net/test", 1, state="OPEN", labels={"vk-ready", "phase:1"})
    # #999 intentionally not added → view_issue KeyErrors inside observe().

    with caplog.at_level("WARNING", logger="vk.bridge"):
        found = discover_plans("derio-net/test", gh)

    assert found == [], "one unviewable phase Issue skips the whole plan for this tick"
    assert any("2026-05-09-twophase-badissue" in rec.getMessage() for rec in caplog.records)
