"""Tests for vk.plan_ops — create / tick / complete_phase / rework / self_review."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def _make_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with a docs/superpowers/ tree."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "plans").mkdir()
    (tmp_path / "docs" / "superpowers" / "archived-plans").mkdir()
    return tmp_path


def _make_spec(repo: Path, slug: str = "test-spec") -> Path:
    """Create a spec file with an empty Implementation Plans table."""
    spec_path = repo / "docs" / "superpowers" / "specs" / f"2026-05-10-{slug}.md"
    spec_path.write_text(
        "# Test spec\n\n"
        "## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n"
    )
    return spec_path


# ---------------------------------------------------------------------------
# vk.plan.create


def test_create_scaffolds_folder_and_appends_spec_row(tmp_path):
    from vk.plan_ops import PhaseSpec, create

    repo = _make_repo(tmp_path)
    spec_path = _make_spec(repo)

    plan = create(
        repo_root=repo,
        slug="2026-05-10-fixture-create",
        spec=str(spec_path.relative_to(repo)),
        target_repo="derio-net/test",
        vk_version=">=1.0.0,<3.0.0",
        phases=[
            PhaseSpec(
                number=1,
                title="First",
                tag="agentic",
                tasks=({"number": 1, "title": "t", "steps": [{"id": "P1.T1.S1", "text": "s"}]},),
            )
        ],
        prose="# Test create\n",
    )
    assert plan.meta.plan == "2026-05-10-fixture-create"
    assert (repo / "docs" / "superpowers" / "plans" / plan.meta.plan / "_meta.yaml").exists()
    assert (repo / "docs" / "superpowers" / "plans" / plan.meta.plan / "01.yaml").exists()
    # Spec table now has the row
    assert plan.meta.plan in spec_path.read_text()


def test_create_rejects_existing_folder(tmp_path):
    from vk.plan_ops import PhaseSpec, PlanEditError, create

    repo = _make_repo(tmp_path)
    spec_path = _make_spec(repo)
    args = dict(
        repo_root=repo,
        slug="2026-05-10-dup",
        spec=str(spec_path.relative_to(repo)),
        target_repo="derio-net/test",
        vk_version=">=1.0.0,<3.0.0",
        phases=[PhaseSpec(number=1, title="t", tasks=())],
        prose="# x\n",
    )
    create(**args)
    with pytest.raises(PlanEditError, match="already exists"):
        create(**args)


# ---------------------------------------------------------------------------
# vk.plan.tick


def test_tick_marks_step_and_records_timestamp(tmp_path):
    from vk import parse
    from vk.plan_ops import tick

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = tmp_path / "v2_plan_minimal"
    shutil.copytree(fixture, dest)

    tick(dest, "P1.T1.S1")

    plan = parse(dest)
    s = plan.phases[0].state.steps["P1.T1.S1"]
    assert s.state == "x"
    assert s.ticked_at is not None


def test_tick_idempotent(tmp_path):
    from vk import parse
    from vk.plan_ops import tick

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = tmp_path / "v2_plan_minimal"
    shutil.copytree(fixture, dest)

    tick(dest, "P1.T1.S1")
    first_ts = parse(dest).phases[0].state.steps["P1.T1.S1"].ticked_at
    tick(dest, "P1.T1.S1")  # idempotent
    second_ts = parse(dest).phases[0].state.steps["P1.T1.S1"].ticked_at
    assert first_ts == second_ts


def test_tick_skipped_requires_note(tmp_path):
    from vk.plan_ops import PlanEditError, tick

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = tmp_path / "v2_plan_minimal"
    shutil.copytree(fixture, dest)

    with pytest.raises(PlanEditError, match="requires.*note"):
        tick(dest, "P1.T1.S1", state="-")


def test_tick_unknown_step_id(tmp_path):
    from vk.plan_ops import PlanEditError, tick

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = tmp_path / "v2_plan_minimal"
    shutil.copytree(fixture, dest)

    with pytest.raises(PlanEditError, match="not found"):
        tick(dest, "P9.T9.S9")


# ---------------------------------------------------------------------------
# vk.plan.complete_phase


def test_complete_phase_agentic_refuses_unticked(tmp_path):
    from vk.plan_ops import PlanEditError, complete_phase

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = tmp_path / "v2_plan_minimal"
    shutil.copytree(fixture, dest)

    with pytest.raises(PlanEditError, match="unticked steps"):
        complete_phase(dest, 1)


def test_complete_phase_agentic_succeeds_after_ticking(tmp_path):
    from vk import parse
    from vk.plan_ops import complete_phase, tick

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = tmp_path / "v2_plan_minimal"
    shutil.copytree(fixture, dest)

    tick(dest, "P1.T1.S1")
    complete_phase(dest, 1)

    plan = parse(dest)
    assert plan.phases[0].state.completion.at is not None


def test_complete_phase_manual_requires_note(tmp_path):
    from vk.plan_ops import PlanEditError, complete_phase

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    dest = tmp_path / "v2_plan_multi_phase"
    shutil.copytree(fixture, dest)

    # Phase 10 in multi_phase fixture is manual
    with pytest.raises(PlanEditError, match="manual.*note"):
        complete_phase(dest, 10)


def test_complete_phase_manual_succeeds_with_note(tmp_path):
    from vk import parse
    from vk.plan_ops import complete_phase

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    dest = tmp_path / "v2_plan_multi_phase"
    shutil.copytree(fixture, dest)

    complete_phase(dest, 10, note="ran the runbook")

    plan = parse(dest)
    manual = next(p for p in plan.phases if p.phase.tag == "manual")
    assert manual.state.completion.at is not None
    assert manual.state.completion.note == "ran the runbook"


# ---------------------------------------------------------------------------
# vk.plan.rework_create


def _make_archived_parent_plan(repo: Path, slug: str, spec_path: Path) -> Path:
    """Copy minimal fixture into archived-plans/ as a 'completed parent'."""
    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = repo / "docs" / "superpowers" / "archived-plans" / slug
    shutil.copytree(fixture, dest)
    # Update _meta to reference the new spec
    import yaml as _yaml

    meta = _yaml.safe_load((dest / "_meta.yaml").read_text())
    meta["plan"] = slug
    meta["spec"] = str(spec_path.relative_to(repo))
    (dest / "_meta.yaml").write_text(_yaml.safe_dump(meta, sort_keys=False))
    return dest


def test_rework_create_scaffolds_sibling_with_parent_link(tmp_path):
    from vk.plan_ops import rework_create

    repo = _make_repo(tmp_path)
    spec = _make_spec(repo)
    parent = _make_archived_parent_plan(repo, "2026-05-08-parent", spec)

    rework = rework_create(parent)
    assert rework.meta.parent_plan is not None
    assert "2026-05-08-parent" in rework.meta.parent_plan
    assert rework.meta.origin_items == []
    # Spec table got the rework row
    assert "2026-05-08-parent-rework-1" in spec.read_text()


def test_rework_create_collision_check_across_directories(tmp_path):
    from vk.plan_ops import PlanEditError, rework_create

    repo = _make_repo(tmp_path)
    spec = _make_spec(repo)
    parent = _make_archived_parent_plan(repo, "2026-05-08-parent", spec)

    # Create a fake `-rework-1` in BOTH plans/ and archived-plans/ to trigger collision
    (repo / "docs" / "superpowers" / "plans" / "2026-05-08-parent-rework-1").mkdir()
    (repo / "docs" / "superpowers" / "archived-plans" / "2026-05-08-parent-rework-1").mkdir()

    with pytest.raises(PlanEditError, match="ambiguous rework state"):
        rework_create(parent)


# ---------------------------------------------------------------------------
# vk.plan.rework_add_origin


def test_rework_add_origin_appends_with_auto_id(tmp_path):
    from vk import parse
    from vk.plan_ops import rework_add_origin, rework_create

    repo = _make_repo(tmp_path)
    spec = _make_spec(repo)
    parent = _make_archived_parent_plan(repo, "2026-05-08-parent", spec)
    rework = rework_create(parent)

    id1 = rework_add_origin(rework.dir, item="first item", source="PR review", track="development")
    id2 = rework_add_origin(rework.dir, item="second", source="demo", track="operations")
    assert id1 == 1
    assert id2 == 2

    plan = parse(rework.dir)
    assert len(plan.meta.origin_items) == 2
    assert plan.meta.origin_items[1].track == "operations"


def test_rework_add_origin_rejects_non_rework_plan(tmp_path):
    from vk.plan_ops import PlanEditError, rework_add_origin

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = tmp_path / "v2_plan_minimal"
    shutil.copytree(fixture, dest)

    with pytest.raises(PlanEditError, match="not a rework plan"):
        rework_add_origin(dest, item="x", source="y", track="development")


# ---------------------------------------------------------------------------
# vk.plan.rework_list


def test_rework_list_filters_by_parent_plan(tmp_path):
    from vk.plan_ops import rework_create, rework_list

    repo = _make_repo(tmp_path)
    spec = _make_spec(repo)
    parent = _make_archived_parent_plan(repo, "2026-05-08-parent", spec)
    rework_create(parent)

    # Also place a non-rework plan in plans/ (the multi_phase fixture)
    fixture = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    shutil.copytree(fixture, repo / "docs" / "superpowers" / "plans" / "non-rework")

    records = rework_list(repo)
    assert len(records) == 1
    assert records[0].parent_slug == "2026-05-08-parent"
    assert records[0].rework_number == 1
    assert records[0].status == "Not Started"  # no steps in rework yet
    assert records[0].origin_item_count == 0


# ---------------------------------------------------------------------------
# vk.plan.self_review


def test_yaml_dump_coerces_step_text_to_literal_block(tmp_path):
    """After any write (tick, complete, create), step text must use `|-`.

    yaml.safe_load returns plain str, so round-tripped phase files would
    regress to plain/quoted scalars without _coerce_step_texts in _yaml_dump.
    """
    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = tmp_path / "v2_plan_minimal"
    shutil.copytree(fixture, dest)

    from vk.plan_ops import tick

    tick(dest, "P1.T1.S1")

    phase_text = (dest / "01.yaml").read_text()
    assert "text: |-" in phase_text, "step text must use `|-` after round-trip write"


def test_self_review_clean_plan_has_no_issues(tmp_path):
    from vk import parse
    from vk.plan_ops import self_review

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = tmp_path / "v2_plan_minimal"
    shutil.copytree(fixture, dest)

    plan = parse(dest)
    assert self_review(plan) == []


def test_self_review_detects_manual_complete_without_note(tmp_path):
    from vk import parse
    from vk.plan_ops import self_review

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    dest = tmp_path / "v2_plan_multi_phase"
    shutil.copytree(fixture, dest)

    # Manually mutate phase 10 (manual) to have completion.at but no note
    import yaml as _yaml

    phase_path = dest / "10.yaml"
    raw = _yaml.safe_load(phase_path.read_text())
    raw["state"]["completion"]["at"] = "2026-05-10T12:00:00Z"
    phase_path.write_text(_yaml.safe_dump(raw, sort_keys=False))

    plan = parse(dest)
    issues = self_review(plan)
    assert any("manual" in issue.message and "note" in issue.message for issue in issues)
    assert any(issue.severity == "error" for issue in issues)
