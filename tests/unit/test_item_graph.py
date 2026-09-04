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
    reading, and an item built from one would carry a malformed id. Only the
    first two are DELIBERATE markers (§4.E) and stay silent; the bare-name
    legacy form is `—`-shaped in what it produces (no item) but not in how
    it's treated — see the next test."""
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


def test_a_malformed_repo_cell_is_reported_not_silently_dropped(tmp_path: Path) -> None:
    """The hazard: a deliberate marker cell (em-dash, parenthetical prose)
    and a TYPO of a real repo name both fail `_REPO_CELL_RE`, but only the
    former is an intentional §4.E marker. A typo must cost the operator a
    word, not just an item — silently matching the deliberate-skip behavior
    would make a malformed repo indistinguishable from an omitted one."""
    from fr.spec import parse_spec
    from fr_dispatch.item_graph import build_items

    path = _spec_file(
        tmp_path,
        "| P1 | `derio-net/alpha` | `plans/p1` | — |\n"
        "| Manual sweep | — | — | — |\n"
        "| Org rollout | (operator action across `derio-net/*`) | — | P1 |\n"
        "| Typo'd repo | derionet-superfr | `plans/p4` | — |\n",
    )

    failures: list[str] = []
    items = build_items(SPEC_SHAPE, parse_spec(path), repo="derio-net/home", failures=failures)

    # Only the valid repo produced an item — the em-dash and parenthetical
    # rows are still silently skipped.
    assert [i.id for i in items] == ["derio-net/alpha/2026-08-14-rollout-design"]
    # But the malformed cell is NOT silent: exactly one failure, naming the
    # row and the offending cell, not the two deliberate marker rows.
    assert len(failures) == 1
    assert "Typo'd repo" in failures[0]
    assert "derionet-superfr" in failures[0]
    assert "owner/name" in failures[0]


def test_a_repeated_repo_across_rows_dedupes_silently_not_an_error(tmp_path: Path) -> None:
    """A duplicate repo is a normal spec shape (the same repo can own more
    than one plan row) — deduping is intentional and must NOT be reported
    as a failure, unlike a malformed cell."""
    from fr.spec import parse_spec
    from fr_dispatch.item_graph import build_items

    path = _spec_file(
        tmp_path,
        "| P1 | `derio-net/alpha` | `plans/p1` | — |\n"
        "| P2 | `derio-net/alpha` | `plans/p2` | P1 |\n",
    )

    failures: list[str] = []
    items = build_items(SPEC_SHAPE, parse_spec(path), repo="derio-net/home", failures=failures)

    assert [i.id for i in items] == ["derio-net/alpha/2026-08-14-rollout-design"]
    assert failures == []


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


# ── review fixes (r2) ──────────────────────────────────────────────────


def test_a_cross_repo_dependency_id_names_the_dependencys_own_repo() -> None:
    """r2-f6: each `depends_on` id must be the DEPENDENCY's id.

    A plan whose phase 1 is tracked in repo A and phase 2 in repo B used to
    compose phase 2's dependency as `B/<spec>/<plan>/phase/1` — an id no
    item has, because phase 1's item is keyed on A. Cross-repo phases are a
    supported concept (`render.py` builds cross-repo Issue URLs), so the
    edge has to survive the repo change.
    """
    from fr_dispatch.item_graph import build_items

    a, b = "org/repo-a", "org/repo-b"
    plan = _plan(MULTI)
    tracked = tuple(
        phase.model_copy(update={"phase": phase.phase.model_copy(update={"tracking_issue": url})})
        if url
        else phase
        for phase, url in zip(
            plan.phases,
            (f"https://github.com/{a}/issues/1", f"https://github.com/{b}/issues/2", None),
            strict=True,
        )
    )
    plan = dc_replace(plan, phases=tracked)

    first, second, tenth = build_items(PHASE_SHAPE, plan)

    assert first.id.startswith(f"{a}/")
    assert second.id.startswith(f"{b}/")
    # phase 2 lives in B and depends on phase 1, which lives in A.
    assert second.payload["depends_on"] == (first.id,)
    # phase 10 is untracked (target_repo) and depends on phase 2, in B.
    assert tenth.id.startswith(f"{REPO}/")
    assert tenth.payload["depends_on"] == (second.id,)


def test_a_dependency_with_a_malformed_tracking_url_falls_back_to_the_target_repo() -> None:
    """The DEPENDING phase must not fail for a *dependency's* bad URL — that
    phase already fails itself (see the failures-sink test above)."""
    from fr_dispatch.item_graph import build_items

    plan = _plan(MULTI)
    broken = plan.phases[0].model_copy(
        update={"phase": plan.phases[0].phase.model_copy(update={"tracking_issue": "not-a-url"})}
    )
    plan = dc_replace(plan, phases=(broken, plan.phases[1], plan.phases[2]))

    failures: list[str] = []
    second, tenth = build_items(PHASE_SHAPE, plan, failures=failures)

    assert len(failures) == 1  # phase 1 only
    assert second.payload["depends_on"] == (
        f"{REPO}/_no-spec/2026-05-09-fixture-multi-phase/phase/1",
    )


def test_a_run_unit_shape_with_no_run_id_accumulates_instead_of_raising() -> None:
    """r2-f9: `tick`'s docstring says "all failure paths accumulate", but the
    run branch raised straight out of `build_items` — through
    `_eligible_items`, which calls it outside any `try` — and took the whole
    cron iteration with it."""
    from fr_dispatch.item_graph import build_items

    failures: list[str] = []
    items = build_items(RUN_SHAPE, repo=REPO, failures=failures)

    assert items == []
    assert len(failures) == 1
    assert "run_id" in failures[0]
    assert REPO in failures[0]


def test_a_run_unit_shape_with_no_repo_and_no_source_accumulates() -> None:
    from fr_dispatch.item_graph import build_items

    failures: list[str] = []
    assert build_items(RUN_SHAPE, run_id="r1", failures=failures) == []
    assert len(failures) == 1
    assert "repo" in failures[0]


def test_a_phase_unit_shape_with_no_plan_accumulates() -> None:
    from fr_dispatch.item_graph import build_items

    failures: list[str] = []
    assert build_items(PHASE_SHAPE, None, failures=failures) == []
    assert len(failures) == 1
    assert "Plan" in failures[0]


def test_a_spec_unit_shape_with_no_repo_accumulates(tmp_path: Path) -> None:
    from fr.spec import parse_spec
    from fr_dispatch.item_graph import build_items

    path = _spec_file(tmp_path, "| P | derio-net/x | plans/p | — |")
    failures: list[str] = []

    assert build_items(SPEC_SHAPE, parse_spec(path), failures=failures) == []
    assert len(failures) == 1
    assert "repo" in failures[0]


def test_without_a_sink_every_one_of_those_still_raises() -> None:
    """A caller that wants to know still does — the sink is opt-in, and its
    absence must not silently swallow a malformed call."""
    import pytest
    from fr_dispatch.item_graph import build_items

    with pytest.raises(ValueError, match="run_id"):
        build_items(RUN_SHAPE, repo=REPO)
    with pytest.raises(ValueError, match="Plan"):
        build_items(PHASE_SHAPE, None)


def test_a_wrong_source_type_still_raises_even_with_a_sink(tmp_path: Path) -> None:
    """The split is deliberate: DATA-shaped failures accumulate; handing a
    `SpecMeta` to a phase-unit shape is a programming error in the caller,
    not a bad plan on disk, and must not be counted as one plan's problem."""
    import pytest
    from fr.spec import parse_spec
    from fr_dispatch.item_graph import build_items

    spec = parse_spec(_spec_file(tmp_path, "| P | derio-net/x | plans/p | — |"))
    with pytest.raises(TypeError):
        build_items(PHASE_SHAPE, spec, failures=[])


# ── the reserved spec slug goes through the sink (review r5-a4) ────────


def test_a_spec_named_run_accumulates_instead_of_raising_through_tick(tmp_path: Path) -> None:
    """`item_id` rejects the slug `run` — it collides with the run-item
    form. That call sat OUTSIDE the `failures` sink, so a spec file named
    `run.md` raised straight out of `build_items` and, since
    `_eligible_items` calls it outside any `try`, out of `tick` itself."""
    from fr.spec import parse_spec
    from fr_dispatch.item_graph import build_items

    spec_dir = tmp_path / "docs" / "superpowers" / "specs"
    spec_dir.mkdir(parents=True)
    path = spec_dir / "run.md"
    path.write_text(
        "# Run\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n"
        f"| p1 | `{REPO}` | p1 | — |\n"
    )
    spec = parse_spec(path)

    failures: list[str] = []
    items = build_items(SPEC_SHAPE, spec, repo=REPO, failures=failures)

    assert items == []
    assert len(failures) == 1
    assert "run" in failures[0]


def test_without_a_sink_the_reserved_slug_still_raises(tmp_path: Path) -> None:
    import pytest
    from fr.spec import parse_spec
    from fr_dispatch.item_graph import build_items

    spec_dir = tmp_path / "docs" / "superpowers" / "specs"
    spec_dir.mkdir(parents=True)
    path = spec_dir / "run.md"
    path.write_text(
        "# Run\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n"
        f"| p1 | `{REPO}` | p1 | — |\n"
    )

    with pytest.raises(ValueError, match="reserved"):
        build_items(SPEC_SHAPE, parse_spec(path), repo=REPO)
