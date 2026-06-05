"""Tests for vk.spec — parse_spec / compute_status / render_status_md."""

from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

FIXTURE_PLAN = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
FIXTURE_MULTI = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"


def _make_repo_with_spec(tmp_path: Path) -> Path:
    """Build a tmp repo with a spec referencing a local plan."""
    plans = tmp_path / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir()
    # copy the minimal plan fixture
    shutil.copytree(FIXTURE_PLAN, plans / "2026-05-10-fixture-spec-test")
    # write a spec referencing it
    spec_path = specs / "2026-05-10-fixture-spec.md"
    spec_path.write_text(
        "# Fixture spec\n\n"
        "## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n"
        "| Test plan A | `derio-net/superpowers-for-vk` | "
        "`docs/superpowers/plans/2026-05-10-fixture-spec-test/` | — |\n"
        "| Future plan B | `derio-net/willikins` | `docs/superpowers/plans/future-b/` | A |\n"
    )
    return tmp_path


def test_parse_spec_extracts_4col_table(tmp_path):
    from vk.spec import parse_spec

    repo = _make_repo_with_spec(tmp_path)
    spec_path = repo / "docs" / "superpowers" / "specs" / "2026-05-10-fixture-spec.md"
    meta = parse_spec(spec_path)
    assert meta.title == "Fixture spec"
    assert len(meta.plans) == 2
    assert meta.plans[0].name == "Test plan A"
    assert meta.plans[0].repo == "derio-net/superpowers-for-vk"
    assert meta.plans[0].file == "docs/superpowers/plans/2026-05-10-fixture-spec-test/"


def test_compute_status_aggregates_local_plan(tmp_path):
    from vk.spec import compute_status, parse_spec

    repo = _make_repo_with_spec(tmp_path)
    spec_path = repo / "docs" / "superpowers" / "specs" / "2026-05-10-fixture-spec.md"
    meta = parse_spec(spec_path)
    st = compute_status(meta, repo)
    assert st.aggregate.plans_total == 2
    # Plan A is local + Not Started; Plan B is unreachable (folder doesn't exist)
    plan_a = next(p for p in st.plans if p.plan_ref.name == "Test plan A")
    assert plan_a.state == "Not Started"
    assert plan_a.steps_total == 1
    plan_b = next(p for p in st.plans if p.plan_ref.name == "Future plan B")
    assert plan_b.state in ("Unreachable", "Missing")


def test_compute_status_complete_when_all_phases_complete(tmp_path):
    """All steps ticked + completion.at set on every phase → state == Complete."""
    import yaml

    from vk.spec import compute_status, parse_spec

    repo = _make_repo_with_spec(tmp_path)
    plan_dir = repo / "docs" / "superpowers" / "plans" / "2026-05-10-fixture-spec-test"
    # tick the only step + set completion.at
    raw = yaml.safe_load((plan_dir / "01.yaml").read_text())
    raw["state"]["steps"]["P1.T1.S1"]["state"] = "x"
    raw["state"]["completion"]["at"] = "2026-05-10T12:00:00Z"
    (plan_dir / "01.yaml").write_text(yaml.safe_dump(raw, sort_keys=False))

    meta = parse_spec(repo / "docs" / "superpowers" / "specs" / "2026-05-10-fixture-spec.md")
    st = compute_status(meta, repo)
    plan_a = next(p for p in st.plans if p.plan_ref.name == "Test plan A")
    assert plan_a.state == "Complete"
    assert st.aggregate.plans_complete == 1


def test_render_status_md_contains_table_and_aggregate(tmp_path):
    from vk.spec import compute_status, parse_spec, render_status_md

    repo = _make_repo_with_spec(tmp_path)
    spec_path = repo / "docs" / "superpowers" / "specs" / "2026-05-10-fixture-spec.md"
    meta = parse_spec(spec_path)
    st = compute_status(meta, repo)
    md = render_status_md(st)
    assert "Spec progress" in md
    assert "| Plan | Repo | Status |" in md
    assert "Test plan A" in md
    assert "Spec aggregate" in md


def test_vk_v2_spec_status_cli_prints_markdown(tmp_path, monkeypatch):
    from vk.cli import app

    repo = _make_repo_with_spec(tmp_path)
    monkeypatch.chdir(repo)
    runner = CliRunner()
    spec_path = repo / "docs" / "superpowers" / "specs" / "2026-05-10-fixture-spec.md"
    result = runner.invoke(app, ["spec", "status", str(spec_path)])
    assert result.exit_code == 0, result.output
    assert "Spec progress" in result.output
    assert "Test plan A" in result.output


def test_vk_v2_spec_status_all_walks_specs_dir(tmp_path, monkeypatch):
    from vk.cli import app

    repo = _make_repo_with_spec(tmp_path)
    monkeypatch.chdir(repo)
    runner = CliRunner()
    result = runner.invoke(app, ["spec", "status", "--all"])
    assert result.exit_code == 0, result.output
    assert "2026-05-10-fixture-spec.md" in result.output
    assert "Test plan A" in result.output


def test_resolve_local_plan_dir_falls_back_to_implemented_then_archived(tmp_path):
    """Spec tables are never rewritten on archive: a row recorded as
    docs/superpowers/plans/X must resolve to implemented/plans/X (canonical)
    or archived-plans/X (legacy) when the plans/ path is gone."""
    from vk.spec import PlanRef, _resolve_local_plan_dir

    ref = PlanRef(
        name="x", repo="derio-net/test", file="docs/superpowers/plans/2026-05-10-x", depends_on="—"
    )

    implemented = tmp_path / "docs" / "superpowers" / "implemented" / "plans" / "2026-05-10-x"
    implemented.mkdir(parents=True)
    assert _resolve_local_plan_dir(ref, tmp_path) == implemented

    # Legacy fallback comes after implemented/.
    shutil.rmtree(implemented.parent.parent)
    legacy = tmp_path / "docs" / "superpowers" / "archived-plans" / "2026-05-10-x"
    legacy.mkdir(parents=True)
    assert _resolve_local_plan_dir(ref, tmp_path) == legacy
