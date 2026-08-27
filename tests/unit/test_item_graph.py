"""`build_items` — the item graph, one shape at a time (spec §4.E, Phase 8).

The decomposition granularity is the shape's declared `unit`, not a
hardcoded assumption of the dispatcher. `build_items(workflow, source)` is
the ONE builder: `fr_dispatch._eligible_items` is a tracker-state filter
over it, never a second construction path (two builders is exactly how the
id grammar drifts — Phase 3's journal says so explicitly).

Identity is Phase 2's four-level grammar (`fr_dispatch.work_item`):

    run    <repo>/run/<run-id>                        unit: run
    spec   <repo>/<spec-slug>                          unit: spec
    plan   <repo>/<spec-slug>/<plan-slug>              (parent level only)
    phase  <repo>/<spec-slug>/<plan-slug>/phase/<n>    unit: phase
"""

from __future__ import annotations

from dataclasses import replace as dc_replace
from pathlib import Path

from fr.workflow.model import parse_manifest

MINIMAL = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
MULTI = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"

REPO = "derio-net/superpowers-for-vk"

RUN_SHAPE = parse_manifest(
    "workflow: fr-goal\nschema: 1\nunit: run\n"
    "steps:\n"
    "  - id: brainstorm\n    kind: agent\n    emits: [spec]\n"
    "  - id: plan\n    kind: agent\n    needs: [spec]\n    emits: [plan]\n"
    "  - id: implement\n    kind: agent\n    needs: [spec, plan]\n"
    "    for_each: phase\n    emits: [pr]\n"
)

PHASE_SHAPE = parse_manifest(
    "workflow: fr-goal\nschema: 1\nunit: phase\n"
    "steps:\n  - id: implement\n    kind: agent\n    needs: [spec, plan]\n    emits: [pr]\n"
)

SPEC_SHAPE = parse_manifest(
    "workflow: rollout\nschema: 1\nunit: spec\n"
    "steps:\n  - id: implement\n    kind: agent\n    needs: [spec]\n    emits: [pr]\n"
)


def _plan(fixture: Path = MINIMAL, repo: str = REPO):
    from fr import parse

    plan = parse(fixture)
    return dc_replace(plan, meta=plan.meta.model_copy(update={"target_repo": repo}))


def _tracked_plan(repo: str = REPO):
    """Minimal fixture with phase 1 carrying a tracking Issue URL."""
    plan = _plan(repo=repo)
    phase = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={"tracking_issue": f"https://github.com/{repo}/issues/42"}
            )
        }
    )
    return dc_replace(plan, phases=(phase,))


def _spec_file(tmp_path: Path, rows: str) -> Path:
    spec_dir = tmp_path / "docs" / "superpowers" / "specs"
    spec_dir.mkdir(parents=True)
    path = spec_dir / "2026-08-14-rollout-design.md"
    path.write_text(
        "# Rollout\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n" + rows + "\n"
    )
    return path


# ── unit: run ──────────────────────────────────────────────────────────


def test_run_unit_yields_exactly_one_item_keyed_on_the_run_id() -> None:
    from fr_dispatch.item_graph import build_items

    items = build_items(RUN_SHAPE, repo=REPO, run_id="2026-08-14-ticket-polling")

    assert len(items) == 1
    (item,) = items
    assert item.id == f"{REPO}/run/2026-08-14-ticket-polling"
    assert item.unit == "run"
    assert item.repo == REPO
    assert item.parent is None
    assert item.tracking is None


def test_a_run_item_declares_no_inputs_because_its_spec_and_plan_are_outputs() -> None:
    """§4.E: for `unit: run` the spec and plan are emitted, not needed."""
    from fr_dispatch.item_graph import build_items

    (item,) = build_items(RUN_SHAPE, repo=REPO, run_id="r1")

    assert item.inputs == ()


def test_a_run_item_of_a_shape_that_needs_a_spec_declares_it() -> None:
    """The rule is data, not the unit: a run shape that does NOT emit its
    spec still declares it as an input."""
    from fr_dispatch.item_graph import build_items

    shape = parse_manifest(
        "workflow: rerun\nschema: 1\nunit: run\n"
        "steps:\n  - id: implement\n    kind: agent\n    needs: [spec]\n    emits: [pr]\n"
    )
    plan = _plan()

    (item,) = build_items(shape, plan, run_id="r1")

    assert [(r.kind, r.path) for r in item.inputs] == [
        ("spec", "docs/superpowers/specs/fixture-spec-design.md")
    ]


# ── unit: phase ────────────────────────────────────────────────────────


def test_phase_unit_yields_one_item_per_plan_phase() -> None:
    from fr_dispatch.item_graph import build_items

    plan = _plan(MULTI)

    items = build_items(PHASE_SHAPE, plan)

    assert [i.id for i in items] == [
        f"{REPO}/_no-spec/2026-05-09-fixture-multi-phase/phase/1",
        f"{REPO}/_no-spec/2026-05-09-fixture-multi-phase/phase/2",
        f"{REPO}/_no-spec/2026-05-09-fixture-multi-phase/phase/10",
    ]
    assert {i.unit for i in items} == {"phase"}
    assert all(i.parent == f"{REPO}/_no-spec/2026-05-09-fixture-multi-phase" for i in items)


def test_phase_items_carry_depends_on_as_item_ids() -> None:
    """§4.E: concurrency is a consequence of the item graph, so the DAG
    edge must survive onto the item — as an item id, not a bare number."""
    from fr_dispatch.item_graph import build_items

    first, second, tenth = build_items(PHASE_SHAPE, _plan(MULTI))

    assert first.payload["depends_on"] == ()
    assert second.payload["depends_on"] == (first.id,)
    # Phase 10 depends on 2 — the edge is the DEPENDENCY's id, not the
    # previous item in list order (which alphabetical/positional guessing
    # would get right for `second` and wrong here).
    assert tenth.payload["depends_on"] == (second.id,)


def test_phase_items_of_a_tracked_phase_carry_the_issue_coordinates() -> None:
    from fr_dispatch.item_graph import build_items

    plan = _tracked_plan()

    (item,) = build_items(PHASE_SHAPE, plan)

    assert item.tracking == f"https://github.com/{REPO}/issues/42"
    assert item.payload["issue_number"] == 42
    assert item.payload["plan"] is plan
    assert item.payload["phase"] is plan.phases[0]


def test_an_untracked_phase_still_gets_an_item_with_no_tracker_coordinates() -> None:
    """The graph exists before any tracker call — that is the whole premise
    of §4.D identity. An untracked phase is an item without an Issue, not a
    missing item."""
    from fr_dispatch.item_graph import build_items

    (item,) = build_items(PHASE_SHAPE, _plan())

    assert item.tracking is None
    assert "issue_number" not in item.payload
    assert item.repo == REPO  # falls back to the plan's target repo


def test_a_tracked_phase_is_keyed_on_the_issues_repo_not_the_plans() -> None:
    """Phase 3's derivation 1: `can_dispatch(item)` reads `item.repo`, so a
    cross-repo phase must carry the repo it actually executes in."""
    from fr_dispatch.item_graph import build_items

    plan = _tracked_plan(repo=REPO)
    other = "other-org/other-repo"
    phase = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={"tracking_issue": f"https://github.com/{other}/issues/7"}
            )
        }
    )
    plan = dc_replace(plan, phases=(phase,))

    (item,) = build_items(PHASE_SHAPE, plan)

    assert item.repo == other
    assert item.id.startswith(f"{other}/")


def test_a_phase_whose_item_cannot_be_built_fails_only_itself() -> None:
    from fr_dispatch.item_graph import build_items

    plan = _plan(MULTI)
    broken = plan.phases[0].model_copy(
        update={"phase": plan.phases[0].phase.model_copy(update={"tracking_issue": "not-a-url"})}
    )
    plan = dc_replace(plan, phases=(broken, plan.phases[1], plan.phases[2]))

    failures: list[str] = []
    items = build_items(PHASE_SHAPE, plan, failures=failures)

    assert [i.id for i in items] == [
        f"{REPO}/_no-spec/2026-05-09-fixture-multi-phase/phase/2",
        f"{REPO}/_no-spec/2026-05-09-fixture-multi-phase/phase/10",
    ]
    assert len(failures) == 1
    assert failures[0].startswith(f"{REPO}/_no-spec/2026-05-09-fixture-multi-phase/phase/1: ")


# ── unit: spec ─────────────────────────────────────────────────────────


def test_spec_unit_yields_one_item_per_distinct_target_repo(tmp_path: Path) -> None:
    from fr.spec import parse_spec
    from fr_dispatch.item_graph import build_items

    path = _spec_file(
        tmp_path,
        "| P1 | `derio-net/alpha` | `plans/p1` | — |\n"
        "| P2 | `derio-net/beta` | `plans/p2` | P1 |\n"
        "| P3 | `derio-net/alpha` | `plans/p3` | P1 |\n",
    )

    items = build_items(SPEC_SHAPE, parse_spec(path), repo="derio-net/home")

    assert [i.id for i in items] == [
        "derio-net/alpha/2026-08-14-rollout-design",
        "derio-net/beta/2026-08-14-rollout-design",
    ]
    assert {i.unit for i in items} == {"spec"}


def test_spec_unit_items_point_at_the_spec_level_id_as_their_parent(tmp_path: Path) -> None:
    from fr.spec import parse_spec
    from fr_dispatch.item_graph import build_items

    path = _spec_file(tmp_path, "| P1 | `derio-net/alpha` | `plans/p1` | — |\n")

    (item,) = build_items(SPEC_SHAPE, parse_spec(path), repo="derio-net/home")

    assert item.parent == "derio-net/home/2026-08-14-rollout-design"


def test_the_home_repos_own_spec_item_is_a_root_not_its_own_parent(tmp_path: Path) -> None:
    from fr.spec import parse_spec
    from fr_dispatch.item_graph import build_items

    path = _spec_file(tmp_path, "| P1 | `derio-net/home` | `plans/p1` | — |\n")

    (item,) = build_items(SPEC_SHAPE, parse_spec(path), repo="derio-net/home")

    assert item.id == "derio-net/home/2026-08-14-rollout-design"
    assert item.parent is None


def test_manual_and_placeholder_rows_are_skipped_not_turned_into_items(tmp_path: Path) -> None:
    """A Repo cell of `—`, an operator-action string, or a bare repo name
    with no owner names no dispatchable repo — skipping is the only honest
    reading, and an item built from one would carry a malformed id."""
    from fr.spec import parse_spec
    from fr_dispatch.item_graph import build_items

    path = _spec_file(
        tmp_path,
        "| P1 | `derio-net/alpha` | `plans/p1` | — |\n"
        "| Manual sweep | — | — | — |\n"
        "| Org rollout | (operator action across `derio-net/*`) | — | P1 |\n"
        "| Legacy | superpowers-for-vk | `plans/p4` | — |\n",
    )

    items = build_items(SPEC_SHAPE, parse_spec(path), repo="derio-net/home")

    assert [i.id for i in items] == ["derio-net/alpha/2026-08-14-rollout-design"]


def test_spec_items_declare_the_spec_as_a_repo_relative_input(tmp_path: Path) -> None:
    from fr.spec import parse_spec
    from fr_dispatch.item_graph import build_items

    path = _spec_file(tmp_path, "| P1 | `derio-net/alpha` | `plans/p1` | — |\n")

    (item,) = build_items(SPEC_SHAPE, parse_spec(path), repo="derio-net/home")

    (ref,) = item.inputs
    assert ref.kind == "spec"
    assert ref.repo == "derio-net/home"
    assert ref.path == "docs/superpowers/specs/2026-08-14-rollout-design.md"


# ── one builder, not two ───────────────────────────────────────────────


def test_eligible_items_is_a_filter_over_build_items_not_a_second_builder() -> None:
    """Phase 3's handoff: generalize the phase-unit builder, never add a
    second one beside it."""
    import inspect

    import fr_dispatch

    src = inspect.getsource(fr_dispatch._eligible_items)
    assert "build_items(" in src
    assert "WorkItem(" not in src, "the tick must not construct items of its own"
