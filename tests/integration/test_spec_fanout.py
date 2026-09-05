"""Multi-repo spec fan-out (spec §4.E, Phase 9) — `multi-repo-spec-fanout`.

Dispatching a `unit: spec` shape fans out **one item per target repo**
named in the spec's `## Implementation Plans` table, each parented to the
spec-level id. `fr_dispatch.item_graph.build_items` already decomposes a
`SpecMeta` this way (Phase 8); this file proves it end to end through
`fr_dispatch.tick`, exactly the way a shape actually gets dispatched.

Fixture choices are deliberate, not arbitrary (see the plan brief):
`HOME_REPO` is NOT the alphabetically-first repo in the table, and
`CROSS_REPO` doesn't merely differ from it by case or suffix — an
implementation that assumes "the local repo sorts/iterates first" or that
dedupes/collapses similarly-named repos would fail these assertions where
a same-shaped-but-lazier fixture would not.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fr.spec import parse_spec
from fr.workflow.model import parse_manifest

from tests.unit.fakes import FakeGhClient

HOME_REPO = "derio-net/zulu-ops"  # not alphabetically first among the two real rows
CROSS_REPO = "acme-org/widget-factory"  # a genuinely different name, not a case/suffix twin
SPEC_SLUG = "2026-08-14-rollout-design"

SPEC_SHAPE = parse_manifest(
    "workflow: rollout\nschema: 1\nunit: spec\n"
    "steps:\n  - id: implement\n    kind: agent\n    needs: [spec]\n    emits: [pr]\n"
)


def _spec_file(tmp_path: Path) -> Path:
    spec_dir = tmp_path / "docs" / "superpowers" / "specs"
    spec_dir.mkdir(parents=True)
    path = spec_dir / f"{SPEC_SLUG}.md"
    path.write_text(
        "# Rollout\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n"
        f"| Cross rollout | `{CROSS_REPO}` | `plans/cross` | — |\n"
        f"| Home rollout | `{HOME_REPO}` | `plans/home` | — |\n"
        "| Ops sweep | (operator action across `derio-net/*`) | — | Home rollout |\n"
    )
    return path


class FakeRunner:
    """Runner protocol v2 fake — no PR/Issue/plan knowledge required."""

    name = "fake-rollout"
    capabilities = frozenset({"git"})

    def __init__(self) -> None:
        self.dispatched: list[Any] = []

    def preflight(self, items: Any) -> str | None:
        return None

    def refresh(self) -> None:
        return None

    def slot_budget(self) -> int:
        return 5

    def existing_dispatches(self, items: Any) -> set[str]:
        return set()

    def can_dispatch(self, item: Any) -> bool:
        return True

    def dispatch(self, item: Any) -> None:
        self.dispatched.append(item)


def test_spec_dispatch_fans_out_one_item_per_target_repo_via_tick(tmp_path: Path) -> None:
    from fr_dispatch import tick

    spec = parse_spec(_spec_file(tmp_path))
    runner = FakeRunner()

    result = tick(spec, FakeGhClient(), runner, workflow=SPEC_SHAPE, repo=HOME_REPO)

    assert result.synced == 2
    assert result.errors == 0
    assert result.failures == ()
    assert [i.id for i in runner.dispatched] == [
        f"{CROSS_REPO}/{SPEC_SLUG}",
        f"{HOME_REPO}/{SPEC_SLUG}",
    ]
    assert {i.unit for i in runner.dispatched} == {"spec"}
    assert {i.repo for i in runner.dispatched} == {CROSS_REPO, HOME_REPO}

    spec_item_id = f"{HOME_REPO}/{SPEC_SLUG}"
    cross_item = next(i for i in runner.dispatched if i.id != spec_item_id)
    home_item = next(i for i in runner.dispatched if i.id == spec_item_id)
    assert cross_item.parent == spec_item_id
    assert home_item.parent is None  # the home repo's own item is a root, not its own parent


def test_the_manual_action_row_is_skipped_not_turned_into_an_item(tmp_path: Path) -> None:
    from fr_dispatch import tick

    spec = parse_spec(_spec_file(tmp_path))
    runner = FakeRunner()

    tick(spec, FakeGhClient(), runner, workflow=SPEC_SHAPE, repo=HOME_REPO)

    assert len(runner.dispatched) == 2
    assert all("operator action" not in i.repo for i in runner.dispatched)


def test_the_cross_repo_items_input_names_the_specs_home_repo_not_a_local_path(
    tmp_path: Path,
) -> None:
    """r-f2's finding, re-verified at the fan-out layer: the `spec` input is
    a coordinate in the repo the spec doc actually lives in (home), never a
    bare path attributed to the item's own (cross) repo."""
    from fr_dispatch import tick

    spec = parse_spec(_spec_file(tmp_path))
    runner = FakeRunner()

    tick(spec, FakeGhClient(), runner, workflow=SPEC_SHAPE, repo=HOME_REPO)

    cross_item = next(i for i in runner.dispatched if i.repo == CROSS_REPO)
    (ref,) = cross_item.inputs
    assert ref.kind == "spec"
    assert ref.repo == HOME_REPO  # the spec's OWN repo, not CROSS_REPO
    assert ref.path == f"docs/superpowers/specs/{SPEC_SLUG}.md"
    assert ":" not in ref.path  # a real repo-relative path, not "owner/repo:path" notation


def test_tick_makes_no_tracker_call_for_a_spec_unit_dispatch(tmp_path: Path) -> None:
    """Mirrors the no-PR-shape guarantee (Phase 8): a spec-unit shape has no
    `Plan` to observe/render/diff/apply, so tick must touch no tracker path."""
    from fr_dispatch import tick

    spec = parse_spec(_spec_file(tmp_path))
    gh = FakeGhClient()

    tick(spec, gh, FakeRunner(), workflow=SPEC_SHAPE, repo=HOME_REPO)

    assert gh.calls == []


def test_a_malformed_repo_cell_surfaces_as_a_tick_failure_not_a_silent_drop(
    tmp_path: Path,
) -> None:
    """The end-to-end version of the hazard `_spec_items` now closes: a
    typo'd Repo cell must not vanish the way a deliberate marker row does —
    it has to cost the operator a word in `TickResult.failures`, seen the
    same way any other per-row dispatch failure is."""
    from fr_dispatch import tick

    spec_dir = tmp_path / "docs" / "superpowers" / "specs"
    spec_dir.mkdir(parents=True)
    path = spec_dir / f"{SPEC_SLUG}.md"
    path.write_text(
        "# Rollout\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n"
        f"| Cross rollout | `{CROSS_REPO}` | `plans/cross` | — |\n"
        "| Ops sweep | (operator action across `derio-net/*`) | — | — |\n"
        "| Typo'd repo | acme-org widget-factory | `plans/typo` | — |\n"
    )
    spec = parse_spec(path)
    runner = FakeRunner()

    result = tick(spec, FakeGhClient(), runner, workflow=SPEC_SHAPE, repo=HOME_REPO)

    # The deliberate marker row is still silent; only the valid repo dispatches.
    assert [i.repo for i in runner.dispatched] == [CROSS_REPO]
    # The typo'd row is NOT silent: it shows up as a named tick failure.
    assert result.errors == 1
    assert any("Typo'd repo" in f and "acme-org widget-factory" in f for f in result.failures)
