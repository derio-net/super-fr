"""Bridge tick must NOT emit `IssueCreate` mutations.

`IssueCreate` is operator-only (via `vk apply --yes`). Regression
guard for the 2026-05-18 incident where the bridge auto-created 38
spurious GH Issues across two waves (sfv#196-#214, sfv#216-#234).

The fix adds `apply(..., skip_issue_create=True)` and flips the bridge
`tick()` callsite to use it. The default remains False so the operator
CLI path is unchanged.
"""

from __future__ import annotations

import logging
import textwrap
from pathlib import Path
from typing import Any

from tests.unit.fakes import FakeGhClient, FakeMcpClient

TARGET_REPO = "derio-net/superpowers-for-vk"


def _write_plan(plan_dir: Path, phases: list[dict[str, Any]]) -> None:
    """Materialise a v2 plan-folder. Same shape as test_bridge_e2e helper.

    Each phase entry: number, title, tag, depends_on, tracking_issue (optional).
    """
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "_meta.yaml").write_text(
        textwrap.dedent(
            f"""\
            schema_version: 2
            plan: 2026-05-18-no-issue-create-fixture
            target_repo: {TARGET_REPO}
            vk_version: ">=2.0.0,<3.0.0"
            created: "2026-05-18"
            """
        )
    )
    for p in phases:
        n = p["number"]
        tag = p.get("tag", "agentic")
        deps_yaml = "[" + ", ".join(str(d) for d in p.get("depends_on", [])) + "]"
        tracking = p.get("tracking_issue")
        tracking_yaml = f'"{tracking}"' if tracking else "null"
        (plan_dir / f"{n:02d}.yaml").write_text(
            textwrap.dedent(
                f"""\
                schema_version: 2
                phase:
                  number: {n}
                  title: {p["title"]}
                  tag: {tag}
                  depends_on: {deps_yaml}
                  tracking_issue: {tracking_yaml}
                tasks:
                  - number: 1
                    title: t
                    steps:
                      - id: P{n}.T1.S1
                        text: s
                state:
                  steps:
                    P{n}.T1.S1: {{ state: " ", ticked_at: null, note: null }}
                  completion: {{ at: null, note: null, observed_prs: [] }}
                """
            )
        )


def _preload_managed_labels(gh: FakeGhClient, repo: str, max_phase: int) -> None:
    """Pre-register the managed-label vocabulary that bridge edits touch.

    The real bridge runs RepoLabelEnsure first; pre-loading keeps these
    tests focused on the IssueCreate-filtering behavior rather than the
    ensure step's mechanics.
    """
    labels = {
        "vk-ready",
        "vk-blocked",
        "vk-synced",
        "in-progress",
        "pr-ready",
        "manual",
        "plan:2026-05-18-no-issue-create-fixture",
    }
    for n in range(1, max_phase + 1):
        labels.add(f"phase:{n}")
    gh.repo_labels.setdefault(repo, set()).update(labels)


def _count_issue_creates(gh: FakeGhClient) -> int:
    return sum(1 for name, _ in gh.calls if name == "create_issue")


def _count_skip_warnings(caplog: Any) -> int:
    return sum(
        1
        for r in caplog.records
        if r.levelno == logging.WARNING and "would have created Issue; skipping" in r.message
    )


# ── Scenario 1: the headline fix ──────────────────────────────────────────


def test_tick_emits_zero_issue_creates_when_partial_dispatch(tmp_path: Path, caplog: Any) -> None:
    """
    GIVEN  a plan with Phase 1 vk-ready + tracking_issue set AND
           Phases 2..N with tracking_issue=null
    WHEN   bridge tick runs
    THEN   the gh client receives ZERO IssueCreate calls
    AND    each null-tracking-issue phase logs a WARNING saying
           "would have created Issue; skipping (operator-only via
           `vk apply --yes`)"
    """
    from fr import parse
    from fr_dispatch import tick

    plan_dir = tmp_path / "plan"
    _write_plan(
        plan_dir,
        phases=[
            {
                "number": 1,
                "title": "Dispatched",
                "tag": "agentic",
                "depends_on": [],
                "tracking_issue": f"https://github.com/{TARGET_REPO}/issues/100",
            },
            {"number": 2, "title": "Pending two", "tag": "agentic", "depends_on": []},
            {"number": 3, "title": "Pending three", "tag": "agentic", "depends_on": []},
            {"number": 4, "title": "Pending four", "tag": "agentic", "depends_on": []},
        ],
    )
    plan = parse(plan_dir)

    gh = FakeGhClient()
    _preload_managed_labels(gh, TARGET_REPO, max_phase=4)
    gh.add_issue(
        TARGET_REPO,
        100,
        state="OPEN",
        labels={"vk-ready", "phase:1", "plan:2026-05-18-no-issue-create-fixture"},
    )
    mcp = FakeMcpClient()

    with caplog.at_level(logging.WARNING, logger="fr.apply"):
        tick(plan, gh, mcp)

    assert _count_issue_creates(gh) == 0, (
        f"bridge tick must NEVER create Issues; got {_count_issue_creates(gh)}"
    )
    assert _count_skip_warnings(caplog) == 3, (
        f"expected 3 skip-warnings (one per null-tracking phase), got "
        f"{_count_skip_warnings(caplog)}"
    )


# ── Scenario 2: operator path still works (default skip_issue_create=False) ──


def test_operator_apply_default_still_creates_issues(tmp_path: Path) -> None:
    """
    GIVEN  the same plan as Scenario 1
    WHEN   `apply()` runs WITHOUT skip_issue_create (operator default)
    THEN   the gh client receives 3 IssueCreate calls (Phases 2..4)
    AND    the returned ApplyResult.created_issues maps each phase to a URL
    """
    from fr import parse
    from fr.apply import apply
    from fr.diff import diff
    from fr.observe import observe
    from fr.render import render

    plan_dir = tmp_path / "plan"
    _write_plan(
        plan_dir,
        phases=[
            {
                "number": 1,
                "title": "Dispatched",
                "tag": "agentic",
                "depends_on": [],
                "tracking_issue": f"https://github.com/{TARGET_REPO}/issues/100",
            },
            {"number": 2, "title": "Pending two", "tag": "agentic", "depends_on": []},
            {"number": 3, "title": "Pending three", "tag": "agentic", "depends_on": []},
            {"number": 4, "title": "Pending four", "tag": "agentic", "depends_on": []},
        ],
    )
    plan = parse(plan_dir)

    gh = FakeGhClient()
    _preload_managed_labels(gh, TARGET_REPO, max_phase=4)
    gh.add_issue(TARGET_REPO, 100, state="OPEN", labels={"vk-ready"})

    obs = observe(plan, gh)
    d = diff(render(plan, obs), obs, plan=plan)
    result = apply(d, gh, plan=plan)  # default skip_issue_create=False

    assert _count_issue_creates(gh) == 3, (
        f"operator apply must create Issues for the 3 undispatched phases; "
        f"got {_count_issue_creates(gh)}"
    )
    assert sorted(result.created_issues.keys()) == [2, 3, 4]
    for url in result.created_issues.values():
        assert url.startswith("https://github.com/")


# ── Scenario 3: mixed-state plan, label sync still happens ──────────────


def test_tick_mixed_state_syncs_labels_and_state_but_skips_create(
    tmp_path: Path, caplog: Any
) -> None:
    """
    GIVEN  a plan where:
             Phase 1 = vk-ready + tracking_issue set
             Phase 2 = vk-blocked (deps not satisfied) + tracking_issue set
             Phase 3 = tracking_issue=null
    WHEN   bridge tick runs
    THEN   Phase 2's labels are sync'd (IssueLabelChange OK — drift fixed)
    AND    Phase 3 produces ZERO IssueCreate
    AND    Phase 3 logs the WARNING about pending dispatch
    """
    from fr import parse
    from fr_dispatch import tick

    plan_dir = tmp_path / "plan"
    _write_plan(
        plan_dir,
        phases=[
            {
                "number": 1,
                "title": "Ready",
                "tag": "agentic",
                "depends_on": [],
                "tracking_issue": f"https://github.com/{TARGET_REPO}/issues/100",
            },
            {
                "number": 2,
                "title": "Blocked by 1",
                "tag": "agentic",
                "depends_on": [1],
                "tracking_issue": f"https://github.com/{TARGET_REPO}/issues/200",
            },
            {
                "number": 3,
                "title": "Undispatched",
                "tag": "agentic",
                "depends_on": [],
            },
        ],
    )
    plan = parse(plan_dir)

    gh = FakeGhClient()
    _preload_managed_labels(gh, TARGET_REPO, max_phase=3)
    # Phase 1 — already projecting vk-ready
    gh.add_issue(
        TARGET_REPO,
        100,
        state="OPEN",
        labels={"vk-ready", "phase:1", "plan:2026-05-18-no-issue-create-fixture"},
    )
    # Phase 2 — observed with stale vk-ready (should be sync'd to vk-blocked)
    gh.add_issue(
        TARGET_REPO,
        200,
        state="OPEN",
        labels={"vk-ready", "phase:2", "plan:2026-05-18-no-issue-create-fixture"},
    )
    mcp = FakeMcpClient()

    with caplog.at_level(logging.WARNING, logger="fr.apply"):
        tick(plan, gh, mcp)

    # Headline assertion
    assert _count_issue_creates(gh) == 0
    # Phase 2 label drift IS sync'd
    p2_labels = gh.issues[(TARGET_REPO, 200)].labels
    assert "vk-blocked" in p2_labels, "phase 2 must be projected vk-blocked"
    assert "vk-ready" not in p2_labels, "phase 2 stale vk-ready must be removed"
    # Phase 3 produced a warning
    assert _count_skip_warnings(caplog) == 1


# ── Scenario 4: fully-dispatched plan, no IssueCreates and no warnings ──


def test_tick_fully_dispatched_plan_no_creates_no_warnings(tmp_path: Path, caplog: Any) -> None:
    """
    GIVEN  a plan where every phase has tracking_issue set
    WHEN   bridge tick runs
    THEN   ZERO IssueCreate calls (no nulls to create)
    AND    ZERO warnings (nothing to skip)
    """
    from fr import parse
    from fr_dispatch import tick

    plan_dir = tmp_path / "plan"
    _write_plan(
        plan_dir,
        phases=[
            {
                "number": n,
                "title": f"Phase {n}",
                "tag": "agentic",
                "depends_on": [],
                "tracking_issue": f"https://github.com/{TARGET_REPO}/issues/{100 + n}",
            }
            for n in range(1, 4)
        ],
    )
    plan = parse(plan_dir)

    gh = FakeGhClient()
    _preload_managed_labels(gh, TARGET_REPO, max_phase=3)
    for n in range(1, 4):
        gh.add_issue(
            TARGET_REPO,
            100 + n,
            state="OPEN",
            labels={
                "vk-ready",
                f"phase:{n}",
                "plan:2026-05-18-no-issue-create-fixture",
            },
        )
    mcp = FakeMcpClient()

    with caplog.at_level(logging.WARNING, logger="fr.apply"):
        tick(plan, gh, mcp)

    assert _count_issue_creates(gh) == 0
    assert _count_skip_warnings(caplog) == 0


# ── Scenario 5: regression guard for today's incident shape ──


def test_tick_stoa_company_shape_emits_no_creates_and_one_warning_per_phase(
    tmp_path: Path, caplog: Any
) -> None:
    """
    GIVEN  the stoa-company-creation plan shape (one phase with vk-ready +
           tracking_issue set, 8 phases with tracking_issue=null)
    WHEN   bridge tick runs ON THIS PLAN
    THEN   ZERO IssueCreate calls
    AND    8 WARNING log messages, one per undispatched phase

    Regression guard for the 2026-05-18 incident which created 19 spurious
    Issues per wave, 38 in total (sfv#196-#214 wave 1, sfv#216-#234 wave 2).
    """
    from fr import parse
    from fr_dispatch import tick

    plan_dir = tmp_path / "plan"
    phases = [
        {
            "number": 1,
            "title": "Phase 1 dispatched",
            "tag": "agentic",
            "depends_on": [],
            "tracking_issue": f"https://github.com/{TARGET_REPO}/issues/100",
        },
    ]
    for n in range(2, 10):  # phases 2..9 — 8 undispatched
        phases.append(
            {
                "number": n,
                "title": f"Phase {n} undispatched",
                "tag": "agentic",
                "depends_on": [],
            }
        )
    _write_plan(plan_dir, phases=phases)
    plan = parse(plan_dir)

    gh = FakeGhClient()
    _preload_managed_labels(gh, TARGET_REPO, max_phase=9)
    gh.add_issue(
        TARGET_REPO,
        100,
        state="OPEN",
        labels={"vk-ready", "phase:1", "plan:2026-05-18-no-issue-create-fixture"},
    )
    mcp = FakeMcpClient()

    with caplog.at_level(logging.WARNING, logger="fr.apply"):
        tick(plan, gh, mcp)

    assert _count_issue_creates(gh) == 0, (
        f"regression: bridge tick must NOT create Issues; got "
        f"{_count_issue_creates(gh)} create_issue calls"
    )
    assert _count_skip_warnings(caplog) == 8, (
        f"expected one warning per undispatched phase (8); got {_count_skip_warnings(caplog)}"
    )
