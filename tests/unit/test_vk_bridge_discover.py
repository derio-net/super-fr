"""Unit tests for `fr_dispatch.discover_plans`.

We build a fake repo checkout under `tmp_path`, point `FR_REPOS_DIR` at it,
and stub the GhClient via FakeGhClient so the test never touches the
network. `vk.parse()` is used to construct the expected Plans because that
pins the structure the bridge will see at runtime.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr_dispatch.metrics import NullMetrics

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
    """Set FR_REPOS_DIR to tmp_path and create the `test/` checkout dir."""
    monkeypatch.setenv("FR_REPOS_DIR", str(tmp_path))
    (tmp_path / "test").mkdir()
    return tmp_path / "test"


def test_discover_plans_returns_only_fr_ready(repo_layout: Path) -> None:
    from fr import parse
    from fr_dispatch import discover_plans

    from tests.unit.fakes import FakeGhClient

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
    gh.add_issue("derio-net/test", 1, state="OPEN", labels={"fr:ready", "phase:1"})
    gh.add_issue("derio-net/test", 2, state="OPEN", labels={"phase:1", "fr:synced"})

    found = discover_plans("derio-net/test", gh)

    assert len(found) == 1
    expected = parse(plan_a_dir)
    assert found[0].dir == expected.dir
    assert found[0].meta.plan == expected.meta.plan


def test_discover_plans_returns_empty_when_checkout_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr_dispatch import discover_plans

    from tests.unit.fakes import FakeGhClient

    monkeypatch.setenv("FR_REPOS_DIR", str(tmp_path))  # checkout dir intentionally absent
    assert discover_plans("derio-net/missing", FakeGhClient()) == []


def test_discover_plans_returns_empty_when_plans_dir_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr_dispatch import discover_plans

    from tests.unit.fakes import FakeGhClient

    monkeypatch.setenv("FR_REPOS_DIR", str(tmp_path))
    (tmp_path / "test").mkdir()  # checkout exists but no docs/superpowers/plans/
    assert discover_plans("derio-net/test", FakeGhClient()) == []


def test_discover_plans_survives_view_issue_failure_for_one_phase(
    repo_layout: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """If `gh.view_issue` raises for a phase (e.g., the Issue was deleted
    or gh is briefly flaky), the bridge logs and treats the phase as
    not-ready rather than crashing the whole tick.
    """
    from fr_dispatch import discover_plans

    from tests.unit.fakes import FakeGhClient

    _write_plan(
        repo_layout,
        "2026-05-09-plan-a",
        tracking_issue="https://github.com/derio-net/test/issues/999",  # not added to gh
    )

    gh = FakeGhClient()  # no Issues registered — view_issue will KeyError

    with caplog.at_level("WARNING", logger="fr_dispatch"):
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
    from fr_dispatch import discover_plans

    from tests.unit.fakes import FakeGhClient

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
    gh.add_issue("derio-net/test", 1, state="OPEN", labels={"fr:ready"})

    with caplog.at_level("WARNING", logger="fr_dispatch"):
        found = discover_plans("derio-net/test", gh)

    assert len(found) == 1
    assert found[0].meta.plan == "2026-05-09-good"
    assert any("2026-05-09-bad" in rec.getMessage() for rec in caplog.records)


def test_discover_plans_refuses_stale_plan_loudly_and_keeps_going(
    repo_layout: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Phase 5 (spec §3.C/§3.E.1): a plan whose artifacts fail `parse()`
    (stale `fr_version` ceiling, or any other `PlanSchemaError`) must be a
    LOUD refusal — error logged, failure metric pushed, and reported to the
    caller via the `failures` outparam — not the old silent
    warn-and-continue. The I9 boundary still holds: a stale plan excludes
    only itself; a good plan alongside it is still discovered.
    """
    from fr_dispatch import discover_plans

    from tests.unit.fakes import FakeGhClient

    _write_plan(
        repo_layout,
        "2026-05-09-good",
        tracking_issue="https://github.com/derio-net/test/issues/1",
    )
    bad_dir = repo_layout / "docs" / "superpowers" / "plans" / "2026-05-09-stale"
    bad_dir.mkdir(parents=True)
    # schema_version is Literal[2] in PlanMeta; 99 is unreachable by any
    # registered migration and fails parse() exactly like a stale/incompatible
    # artifact would.
    (bad_dir / "_meta.yaml").write_text("schema_version: 99\nplan: 2026-05-09-stale\n")

    gh = FakeGhClient()
    gh.add_issue("derio-net/test", 1, state="OPEN", labels={"fr:ready"})

    pushed: list[str] = []

    class _RecordingMetrics(NullMetrics):
        def push_failure_total(self, *, reason: str) -> None:
            pushed.append(reason)

    failures: list[str] = []
    with caplog.at_level("ERROR", logger="fr_dispatch"):
        found = discover_plans("derio-net/test", gh, metrics=_RecordingMetrics(), failures=failures)

    assert len(found) == 1, "the good plan must still be discovered (I9 boundary)"
    assert found[0].meta.plan == "2026-05-09-good"
    assert pushed == ["stale_artifact"], "a failure metric must be pushed for the stale plan"
    assert len(failures) == 1, "errors must be reported to the caller so it can count them"
    assert "2026-05-09-stale" in failures[0]
    assert any(
        rec.levelname == "ERROR" and "2026-05-09-stale" in rec.getMessage()
        for rec in caplog.records
    ), "the refusal must be logged loudly (ERROR), not a warning"


def test_discover_plans_still_enforces_fr_version(
    repo_layout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phase 8 (spec §3.E.1): the bridge is `fr_dispatch`, an execution path
    (it dispatches phases to a runner) — `discover_plans`'s `parse()` call
    must keep enforcing `fr_version` at its unspecified (True) default.
    `enforce_fr_version=False` is reserved for `fr.spec.compute_status`
    alone. Uses a fixture whose ceiling genuinely excludes the installed
    version (monkeypatched `INSTALLED_FR_VERSION`), matching Phase 5's
    stale-plan refusal path exactly."""
    from fr_dispatch import discover_plans

    from tests.unit.fakes import FakeGhClient

    plan_dir = _write_plan(
        repo_layout,
        "2026-05-09-fr-version-excluded",
        tracking_issue="https://github.com/derio-net/test/issues/1",
    )
    meta = (plan_dir / "_meta.yaml").read_text()
    (plan_dir / "_meta.yaml").write_text(meta + 'fr_version: ">=9.0.0,<10.0.0"\n')
    monkeypatch.setattr("fr.parser.INSTALLED_FR_VERSION", "3.0.0")

    gh = FakeGhClient()
    gh.add_issue("derio-net/test", 1, state="OPEN", labels={"fr:ready"})

    failures: list[str] = []
    found = discover_plans("derio-net/test", gh, failures=failures)

    assert found == [], "an fr_version-excluded plan must not be dispatched"
    assert len(failures) == 1
    assert "requires fr_version" in failures[0]


def test_discover_plans_never_shells_out_when_refusing_a_stale_plan(
    repo_layout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The daemon must never auto-commit (#286): the bridge checkout is
    hard-reset every tick, so a commit made here would be silently discarded.
    Discovery refuses the stale plan loudly but never shells out to git (or
    anything else) to do so."""
    from fr_dispatch import discover_plans

    from tests.unit.fakes import FakeGhClient

    bad_dir = repo_layout / "docs" / "superpowers" / "plans" / "2026-05-09-stale"
    bad_dir.mkdir(parents=True)
    (bad_dir / "_meta.yaml").write_text("schema_version: 99\nplan: 2026-05-09-stale\n")

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("discover_plans must never shell out (no auto-commit)")

    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(subprocess, "Popen", _boom)

    found = discover_plans("derio-net/test", FakeGhClient())
    assert found == []


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
    from fr_dispatch import discover_plans

    from tests.unit.fakes import FakeGhClient

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
        labels={"phase:1", "fr:synced"},
        linked_prs=[
            {
                "url": "https://github.com/derio-net/test/pull/3",
                "state": "CLOSED",
                "merged": True,
                "ci": "PASS",
            }
        ],
    )
    gh.add_issue("derio-net/test", 2, state="OPEN", labels={"phase:2", "fr:blocked"})

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
    from fr_dispatch import discover_plans

    from tests.unit.fakes import FakeGhClient

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
    gh.add_issue("derio-net/test", 1, state="OPEN", labels={"fr:ready", "phase:1"})
    # #999 intentionally not added → view_issue KeyErrors inside observe().

    with caplog.at_level("WARNING", logger="fr_dispatch"):
        found = discover_plans("derio-net/test", gh)

    assert found == [], "one unviewable phase Issue skips the whole plan for this tick"
    assert any("2026-05-09-twophase-badissue" in rec.getMessage() for rec in caplog.records)
