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
    from fr.plan_ops import PhaseSpec, create

    repo = _make_repo(tmp_path)
    spec_path = _make_spec(repo)

    plan = create(
        repo_root=repo,
        slug="2026-05-10-fixture-create",
        spec=str(spec_path.relative_to(repo)),
        target_repo="derio-net/test",
        fr_version=">=1.0.0,<5.0.0",
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


def test_create_rejects_existing_folder_with_mismatched_content(tmp_path):
    """A slug reused for *different* content is a real collision — still rejected."""
    from fr.plan_ops import PhaseSpec, PlanEditError, create

    repo = _make_repo(tmp_path)
    spec_path = _make_spec(repo)
    args = dict(
        repo_root=repo,
        slug="2026-05-10-dup",
        spec=str(spec_path.relative_to(repo)),
        target_repo="derio-net/test",
        fr_version=">=1.0.0,<5.0.0",
        phases=[PhaseSpec(number=1, title="t", tasks=())],
        prose="# x\n",
    )
    create(**args)
    # Same slug, different prose → not the same plan → collision.
    with pytest.raises(PlanEditError, match="already exists"):
        create(**{**args, "prose": "# totally different\n"})


def test_create_appends_row_even_when_spec_body_backticks_the_slug(tmp_path):
    """Regression: `_append_spec_row`'s idempotence guard used to scan the WHOLE
    spec, so a spec whose prose mentions its own plan slug in backticks (e.g. a
    `**Slug:** `<slug>`` header, exactly what fr-goal emits) matched, and the
    function returned early having written NO row — while `create` still
    reported success. That empty table then breaks `fr archive`'s spec-sweep.
    The guard must key off the TABLE region only.
    """
    from fr.plan_ops import PhaseSpec, create

    repo = _make_repo(tmp_path)
    slug = "2026-05-10-backtick-slug"
    spec_path = repo / "docs" / "superpowers" / "specs" / "2026-05-10-design.md"
    # The slug appears backticked in the body, BEFORE the (empty) table.
    spec_path.write_text(
        f"# Design\n\n**Slug:** `{slug}`\n\n"
        "## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n"
    )

    create(
        repo_root=repo,
        slug=slug,
        spec=str(spec_path.relative_to(repo)),
        target_repo="derio-net/test",
        fr_version=">=1.0.0,<5.0.0",
        phases=[PhaseSpec(number=1, title="t", tasks=())],
        prose="# x\n",
    )

    text = spec_path.read_text()
    table = text.split("## Implementation Plans", 1)[1]
    assert f"| {slug} |" in table, (
        "the plan row must be appended to the Implementation Plans table even "
        "though the slug already appears (backticked) elsewhere in the spec"
    )


def test_append_spec_row_idempotent_within_table(tmp_path):
    """The scoped guard must still be idempotent: re-appending the same file
    row is a no-op (exactly one data row), and a same-named row OUTSIDE the
    table must not suppress the append."""
    from fr.plan_ops import _append_spec_row

    repo = _make_repo(tmp_path)
    spec_path = repo / "docs" / "superpowers" / "specs" / "s.md"
    spec_path.write_text(
        "# S\n\nMentions `plan-x` in prose.\n\n"
        "## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n"
    )
    kw = dict(plan_name="plan-x", repo="derio-net/test", file="plan-x", depends_on="—")
    _append_spec_row(spec_path, **kw)
    _append_spec_row(spec_path, **kw)  # idempotent

    table = spec_path.read_text().split("## Implementation Plans", 1)[1]
    assert table.count("| plan-x |") == 1, "second append must be a no-op, not a duplicate"


def test_create_preflight_validates_spec_before_creating_folder(tmp_path):
    """#133: a spec missing '## Implementation Plans' must fail BEFORE any
    folder is created, so a re-run isn't blocked by a half-built folder."""
    from fr.plan_ops import PhaseSpec, PlanEditError, create

    repo = _make_repo(tmp_path)
    # Spec exists but has NO '## Implementation Plans' section.
    spec_path = repo / "docs" / "superpowers" / "specs" / "2026-05-10-no-section.md"
    spec_path.write_text("# Test spec\n\nSome prose but no plans table.\n")

    slug = "2026-05-10-preflight"
    with pytest.raises(PlanEditError, match="Implementation Plans"):
        create(
            repo_root=repo,
            slug=slug,
            spec=str(spec_path.relative_to(repo)),
            target_repo="derio-net/test",
            fr_version=">=1.0.0,<5.0.0",
            phases=[PhaseSpec(number=1, title="t", tasks=())],
            prose="# x\n",
        )
    # The crux of #133: no folder was created, so a fixed re-run is unblocked.
    assert not (repo / "docs" / "superpowers" / "plans" / slug).exists()


def test_create_rejects_spec_with_mislabeled_table_header(tmp_path):
    """A header that doesn't match 'Plan | Repo | File | Depends on' must fail
    preflight — `_append_spec_row` writes repo/file/depends-on into columns
    2-4 unconditionally, so a differently-labeled header (e.g. a stray
    'Phases | Status | Created') would silently mislabel the appended row."""
    from fr.plan_ops import PhaseSpec, PlanEditError, create

    repo = _make_repo(tmp_path)
    spec_path = repo / "docs" / "superpowers" / "specs" / "2026-05-10-bad-header.md"
    spec_path.write_text(
        "# Test spec\n\n"
        "## Implementation Plans\n\n"
        "| Plan | Phases | Status | Created |\n"
        "|------|--------|--------|---------|\n"
    )

    slug = "2026-05-10-bad-header-plan"
    with pytest.raises(PlanEditError, match="table header"):
        create(
            repo_root=repo,
            slug=slug,
            spec=str(spec_path.relative_to(repo)),
            target_repo="derio-net/test",
            fr_version=">=1.0.0,<5.0.0",
            phases=[PhaseSpec(number=1, title="t", tasks=())],
            prose="# x\n",
        )
    # Preflight failure — no folder created, and the spec's bad header
    # untouched (no row silently written under the wrong labels).
    assert not (repo / "docs" / "superpowers" / "plans" / slug).exists()
    assert slug not in spec_path.read_text()


def test_create_repairs_matching_existing_folder_idempotently(tmp_path):
    """#133: re-running create with matching content finishes the job (appends
    the missing spec row) instead of dead-ending at 'already exists'."""
    from fr.plan_ops import PhaseSpec, create

    repo = _make_repo(tmp_path)
    spec_path = _make_spec(repo)
    args = dict(
        repo_root=repo,
        slug="2026-05-10-repair",
        spec=str(spec_path.relative_to(repo)),
        target_repo="derio-net/test",
        fr_version=">=1.0.0,<5.0.0",
        phases=[PhaseSpec(number=1, title="t", tasks=())],
        prose="# x\n",
    )
    create(**args)
    # Simulate a partial-success state: folder exists, but the spec row is gone.
    spec_path.write_text(
        "# Test spec\n\n"
        "## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n"
    )
    # Re-run must succeed (idempotent repair), not raise.
    plan = create(**args)
    assert plan.meta.plan == "2026-05-10-repair"
    # The missing row was re-appended exactly once (no duplicate rows).
    assert spec_path.read_text().count("| 2026-05-10-repair |") == 1


def test_create_rejects_existing_folder_with_stale_extra_phase(tmp_path):
    """#133 review: a re-run that DROPS a phase must not silently 'repair' and
    leave the orphaned phase file behind — that's a real content mismatch, so
    it must raise rather than yield a plan with a phase the operator removed."""
    from fr.plan_ops import PhaseSpec, PlanEditError, create

    repo = _make_repo(tmp_path)
    spec_path = _make_spec(repo)
    base = dict(
        repo_root=repo,
        slug="2026-05-10-stale",
        spec=str(spec_path.relative_to(repo)),
        target_repo="derio-net/test",
        fr_version=">=1.0.0,<5.0.0",
        prose="# x\n",
    )
    create(
        **base,
        phases=[PhaseSpec(number=1, title="a", tasks=()), PhaseSpec(number=2, title="b", tasks=())],
    )
    folder = repo / "docs" / "superpowers" / "plans" / "2026-05-10-stale"
    assert (folder / "02.yaml").exists()
    # Re-run for phase 1 only — 02.yaml would become a stale orphan.
    with pytest.raises(PlanEditError, match="already exists"):
        create(**base, phases=[PhaseSpec(number=1, title="a", tasks=())])


# ---------------------------------------------------------------------------
# vk.plan.tick


def test_tick_marks_step_and_records_timestamp(tmp_path):
    from fr import parse
    from fr.plan_ops import tick

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = tmp_path / "v2_plan_minimal"
    shutil.copytree(fixture, dest)

    tick(dest, "P1.T1.S1")

    plan = parse(dest)
    s = plan.phases[0].state.steps["P1.T1.S1"]
    assert s.state == "x"
    assert s.ticked_at is not None


def test_tick_idempotent(tmp_path):
    from fr import parse
    from fr.plan_ops import tick

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = tmp_path / "v2_plan_minimal"
    shutil.copytree(fixture, dest)

    tick(dest, "P1.T1.S1")
    first_ts = parse(dest).phases[0].state.steps["P1.T1.S1"].ticked_at
    tick(dest, "P1.T1.S1")  # idempotent
    second_ts = parse(dest).phases[0].state.steps["P1.T1.S1"].ticked_at
    assert first_ts == second_ts


def test_tick_skipped_requires_note(tmp_path):
    from fr.plan_ops import PlanEditError, tick

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = tmp_path / "v2_plan_minimal"
    shutil.copytree(fixture, dest)

    with pytest.raises(PlanEditError, match="requires.*note"):
        tick(dest, "P1.T1.S1", state="-")


def test_tick_unknown_step_id(tmp_path):
    from fr.plan_ops import PlanEditError, tick

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = tmp_path / "v2_plan_minimal"
    shutil.copytree(fixture, dest)

    with pytest.raises(PlanEditError, match="not found"):
        tick(dest, "P9.T9.S9")


# ---------------------------------------------------------------------------
# vk.plan.complete_phase


def test_complete_phase_agentic_refuses_unticked(tmp_path):
    from fr.plan_ops import PlanEditError, complete_phase

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = tmp_path / "v2_plan_minimal"
    shutil.copytree(fixture, dest)

    with pytest.raises(PlanEditError, match="unticked steps"):
        complete_phase(dest, 1)


def test_complete_phase_agentic_succeeds_after_ticking(tmp_path):
    from fr import parse
    from fr.plan_ops import complete_phase, tick

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = tmp_path / "v2_plan_minimal"
    shutil.copytree(fixture, dest)

    tick(dest, "P1.T1.S1")
    complete_phase(dest, 1)

    plan = parse(dest)
    assert plan.phases[0].state.completion.at is not None


def test_complete_phase_manual_requires_note(tmp_path):
    from fr.plan_ops import PlanEditError, complete_phase

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_multi_phase"
    dest = tmp_path / "v2_plan_multi_phase"
    shutil.copytree(fixture, dest)

    # Phase 10 in multi_phase fixture is manual
    with pytest.raises(PlanEditError, match="manual.*note"):
        complete_phase(dest, 10)


def test_complete_phase_manual_succeeds_with_note(tmp_path):
    from fr import parse
    from fr.plan_ops import complete_phase

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
    from fr.plan_ops import rework_create

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
    from fr.plan_ops import PlanEditError, rework_create

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
    from fr import parse
    from fr.plan_ops import rework_add_origin, rework_create

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
    from fr.plan_ops import PlanEditError, rework_add_origin

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = tmp_path / "v2_plan_minimal"
    shutil.copytree(fixture, dest)

    with pytest.raises(PlanEditError, match="not a rework plan"):
        rework_add_origin(dest, item="x", source="y", track="development")


# ---------------------------------------------------------------------------
# vk.plan.rework_list


def test_rework_list_filters_by_parent_plan(tmp_path):
    from fr.plan_ops import rework_create, rework_list

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

    from fr.plan_ops import tick

    tick(dest, "P1.T1.S1")

    phase_text = (dest / "01.yaml").read_text()
    assert "text: |-" in phase_text, "step text must use `|-` after round-trip write"


def test_self_review_minimal_plan_raises_only_its_sole_skeleton(tmp_path):
    """Was `..._clean_plan_has_no_issues`. The minimal fixture is ONE agentic
    phase marked skeleton — exactly the shape 2026-09-21 debug journal C2 made
    an error (a skeleton with no work after it is the whole plan wearing the
    marker). The fixture is shared by ten test files, so it keeps its shape;
    what this test still guarantees is that the minimal plan raises NOTHING
    else."""
    from fr import parse
    from fr.plan_ops import self_review

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = tmp_path / "v2_plan_minimal"
    shutil.copytree(fixture, dest)

    plan = parse(dest)
    issues = self_review(plan)
    assert [(i.severity, "only agentic phase" in i.message) for i in issues] == [("error", True)]


def test_self_review_detects_manual_complete_without_note(tmp_path):
    from fr import parse
    from fr.plan_ops import self_review

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


# ---------------------------------------------------------------------------
# vk.plan.self_review — agentic-purity gate (#252)


def _purity_plan(tmp_path, *, phase1_tag="agentic", step_text="Run the test suite"):
    """Scaffold a two-phase plan for purity-lint tests.

    Phase 1 (`phase1_tag`) holds P1.T1.S1 with `step_text`; phase 2 is the
    manual collection phase. Returns (plan_dir, parse-callable).
    """
    from fr.plan_ops import PhaseSpec, create

    repo = _make_repo(tmp_path)
    spec_path = _make_spec(repo)
    create(
        repo_root=repo,
        slug="2026-06-04-purity",
        spec=str(spec_path.relative_to(repo)),
        target_repo="derio-net/test",
        fr_version=">=3.0.0,<5.0.0",
        phases=[
            PhaseSpec(
                number=1,
                title="Build",
                tag=phase1_tag,
                tasks=(
                    {
                        "number": 1,
                        "title": "t",
                        "steps": [{"id": "P1.T1.S1", "text": step_text}],
                    },
                ),
            ),
            PhaseSpec(
                number=2,
                title="Deploy",
                tag="manual",
                tasks=(
                    {
                        "number": 1,
                        "title": "t",
                        "steps": [{"id": "P2.T1.S1", "text": "Deploy and verify"}],
                    },
                ),
            ),
        ],
        prose="# x\n",
    )
    return repo / "docs" / "superpowers" / "plans" / "2026-06-04-purity"


def _purity_issues(plan_dir):
    from fr import parse
    from fr.plan_ops import self_review

    return [i for i in self_review(parse(plan_dir)) if "manual phase" in i.message]


def test_self_review_errors_on_step_deferred_to_later_phase(tmp_path):
    """#252 motivating case: an agentic-phase step skipped with a note
    deferring it forward ('Executed in Phase 5') is a mis-scoped manual step."""
    from fr.plan_ops import tick

    plan_dir = _purity_plan(tmp_path)
    tick(plan_dir, "P1.T1.S1", state="-", note="Executed in Phase 2")
    issues = _purity_issues(plan_dir)
    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert "P1.T1.S1" in issues[0].message


def test_self_review_errors_on_defer_phrase_without_phase_number(tmp_path):
    from fr.plan_ops import tick

    plan_dir = _purity_plan(tmp_path)
    tick(plan_dir, "P1.T1.S1", state="-", note="defer to the deploy phase")
    issues = _purity_issues(plan_dir)
    assert len(issues) == 1
    assert issues[0].severity == "error"


def test_self_review_ignores_backward_phase_reference(tmp_path):
    """'ported from Phase 1' on a later phase is history, not deferral."""
    import yaml as _yaml

    plan_dir = _purity_plan(tmp_path)
    # Renumber phase 1's note target: put the '-' step on phase 2? No —
    # backward ref means the note points at an EARLIER phase. Make phase 1
    # agentic with a note referencing phase 1 itself is meaningless; instead
    # rewrite the plan so the agentic phase is number 2 and the note says
    # "ported from Phase 1".
    p1 = plan_dir / "01.yaml"
    p2 = plan_dir / "02.yaml"
    raw1 = _yaml.safe_load(p1.read_text())
    raw2 = _yaml.safe_load(p2.read_text())
    raw1["phase"]["tag"] = "manual"  # phase 1 becomes the manual phase
    raw2["phase"]["tag"] = "agentic"  # phase 2 becomes the agentic phase
    raw2["state"]["steps"]["P2.T1.S1"] = {
        "state": "-",
        "ticked_at": "2026-06-04T00:00:00+00:00",
        "note": "ported from Phase 1",
    }
    p1.write_text(_yaml.safe_dump(raw1, sort_keys=False))
    p2.write_text(_yaml.safe_dump(raw2, sort_keys=False))
    assert _purity_issues(plan_dir) == []


def test_self_review_ignores_deferred_note_in_manual_phase(tmp_path):
    from fr.plan_ops import tick

    plan_dir = _purity_plan(tmp_path, phase1_tag="manual")
    tick(plan_dir, "P1.T1.S1", state="-", note="Executed in Phase 2")
    assert _purity_issues(plan_dir) == []


@pytest.mark.parametrize(
    "phrase",
    [
        "Set the secret manually in the admin panel",
        "Rotate the key by hand after deploy",
        "Configure the OIDC client via the UI",
        "Toggle the feature flag in the UI",
        "Click the approve button on the dashboard",
        "Encrypt the secret with SOPS and commit",
        "The operator sets the client secret",
        "The operator provides the API token",
    ],
)
def test_self_review_errors_on_manual_verb_in_agentic_step(tmp_path, phrase):
    """#252 part 2: manual-operation language in a pending agentic step is a
    mis-scoped manual step — caught at authoring time, before any deferral."""
    plan_dir = _purity_plan(tmp_path, step_text=phrase)
    issues = _purity_issues(plan_dir)
    assert len(issues) == 1, [str(i) for i in _purity_issues(plan_dir)]
    assert issues[0].severity == "error"
    assert "P1.T1.S1" in issues[0].message


def test_self_review_manual_verb_respects_word_boundaries(tmp_path):
    plan_dir = _purity_plan(tmp_path, step_text="Analyze the clickstream data export")
    assert _purity_issues(plan_dir) == []


def test_self_review_manual_verb_ignores_manual_phase_steps(tmp_path):
    plan_dir = _purity_plan(tmp_path, phase1_tag="manual", step_text="Click the approve button")
    assert _purity_issues(plan_dir) == []


def test_self_review_manual_verb_exempts_completed_steps(tmp_path):
    """A ticked ('x') step already proved agent-completable; only pending or
    skipped steps gate. Keeps historical plans (and plans whose step text
    QUOTES the phrases) from retro-erroring."""
    from fr.plan_ops import tick

    plan_dir = _purity_plan(tmp_path, step_text="Set the secret manually in the panel")
    tick(plan_dir, "P1.T1.S1")  # state 'x'
    assert _purity_issues(plan_dir) == []


# ---------------------------------------------------------------------------
# fr plan self-review — agentic dispatch-verb gate (#428)
#
# The executor has no Agent tool (OpenCode: `task: deny`), so a step telling
# it to dispatch a subagent is unexecutable by construction. Mirrors the #252
# gate above: same loop, same agentic-only and `state == "x"` exemptions.


def _all_issues(plan_dir):
    from fr import parse
    from fr.plan_ops import self_review

    return self_review(parse(plan_dir))


def _dispatch_issues(plan_dir):
    """Only the #428 gate's issues — the token is the stable filter."""
    return [i for i in _all_issues(plan_dir) if "#428" in i.message]


def _assert_exactly_one_new_issue(tmp_path, step_text):
    """The step yields ONE dispatch issue and no other change to the verdict.

    Filtering on "#428" alone cannot see a detector that fires twice on
    one step, or one that drags an unrelated lint in with it. The baseline
    plan is identical but for the step text, so the whole issue list is
    comparable and "exactly one" means exactly one.
    """
    baseline = _purity_plan(tmp_path / "baseline", step_text="Run the test suite")
    plan_dir = _purity_plan(tmp_path / "subject", step_text=step_text)
    issues = _dispatch_issues(plan_dir)
    assert len(issues) == 1, [str(i) for i in issues]
    assert issues[0].severity == "error"
    assert "P1.T1.S1" in issues[0].message
    assert len(_all_issues(plan_dir)) == len(_all_issues(baseline)) + 1, [
        str(i) for i in _all_issues(plan_dir)
    ]
    return issues[0]


@pytest.mark.parametrize(
    "step_text",
    [
        # Pattern 1 — imperative head + agent-shaped object.
        # The observed defect, verbatim (spec §2.E, derio-net/frank).
        "Dispatch `blog-craft:post-researcher` per post",
        "Dispatch the cold-reader agent over the draft",
        "Dispatch one `general-purpose` subagent per file",
        "Spawn a subagent to gather evidence",
        "Delegate to the code-reviewer agent",
        # The verb follows a sentence boundary AND a connective, which a
        # naive head-anchor misses. In the list because the brainstorm
        # probe missed it.
        "RED: write the test. Then dispatch `blog-craft:post-researcher` to gather evidence.",
        # Pattern 2 — the explicit mechanism, in an instructional frame.
        # Without these three the whole of §4.A pattern 2 is deletable in
        # silence: it can be replaced by a never-matching regex and the
        # rest of the suite stays green.
        "Use the fr-phase-executor agent for each phase",
        "Call the Task tool with subagent_type: general-purpose",
        "Invoke the code-reviewer subagent on the diff",
    ],
)
def test_self_review_errors_on_dispatch_verb_in_agentic_step(tmp_path, step_text):
    """#428: a pending agentic step instructing the executor to dispatch."""
    _assert_exactly_one_new_issue(tmp_path, step_text)


@pytest.mark.parametrize(
    "step_text",
    [
        # Real super-fr step shapes. This is a repo ABOUT dispatch: the
        # literal `\bdispatch\b` of #428 flags 292 of these (spec §2.D).
        "GREEN: implement fr_dispatch.tick() so it dispatches phases to the runner",
        "Add a test asserting `fr apply --yes` refuses to dispatch an unreachable plan",
        "RED: assert the dispatch brief names the fr-phase-executor agent",
        "Dispatch phase 3 to the vk runner via fr apply",
        "Write docs describing how Claude Code dispatches the fr-phase-executor",
        # `agent` as a MODIFIER, not the head of the noun phrase — the
        # literal shape of phase 3's own work. Pattern 2 arm A requires a
        # non-empty modifier between `the` and the role word precisely so
        # that "the agent frontmatter" cannot read as naming an agent.
        "Use the agent frontmatter in plugins/super-fr/agents/fr-phase-executor.md",
        # Phase 4's own work: an inflected verb, mid-sentence. The
        # boundary anchors position; the bare stem anchors mood.
        "Explain why calling the Agent tool is impossible here",
        # A boundary, a bare stem — and still not an instruction, because
        # the stem is the SUBJECT ("dispatch is") or a NOUN ("dispatch of").
        "Note: dispatch is described in the agent docs",
        "Add a bullet: dispatch of a subagent belongs in a [manual] phase",
        # Abbreviations satisfy `(?<=[.;:!?])\s+` while continuing the
        # same sentence, so they are not instruction boundaries.
        "Cf. dispatch to the fr-phase-executor agent",
        "RED: add a test. e.g. dispatch to the cold-reader agent stays unflagged",
        # A soft wrap is not a boundary. This is the exact text of this
        # feature's own phase-3 step, which an earlier cut flagged.
        '"...spawn or\nhand off to a subagent is a BLOCKER"',
        # `word:word` tokens with no role word: the 42-hit false-positive
        # class §2.D measured. Every object arm requires a role word —
        # including the backticked one, which is why the third of these
        # puts a real imperative dispatch verb in front of the token.
        "Record the plan ref as `plan:my-slug` and the label as `fr:synced`",
        "Assert `fr.tracker:GithubTracker` is the only adapter; dispatch is unchanged",
        "Dispatch the range `start:end` to the worker pool",
        # An inflected verb AT a boundary: position is right, mood is not.
        # Only the bare-stem rule refuses these two.
        "Add a test: dispatching to the fr-phase-executor agent is refused",
        "Note: using the fr-phase-executor agent is impossible here",
        # A bare verb NOT at a boundary: mood is right, position is not.
        # Only the instruction anchor on pattern 2 refuses this one.
        "Explain why you cannot use the fr-phase-executor agent here",
    ],
)
def test_self_review_dispatch_gate_ignores_descriptive_dispatch_prose(tmp_path, step_text):
    """The head anchor separates INSTRUCTING a dispatch from DESCRIBING one."""
    plan_dir = _purity_plan(tmp_path, step_text=step_text)
    assert _dispatch_issues(plan_dir) == []


def test_self_review_dispatch_gate_does_not_look_across_a_line_break(tmp_path):
    """A PRICED recall gap, pinned so it cannot be widened by accident.

    The window between verb and object excludes `\n`. The cost is real:
    a verb and object split by a hard wrap go unflagged. The alternative
    costs more — a window that spans newlines lets an object on an
    unrelated wrapped line manufacture a hit, which is the soft-wrap
    defect one level down. Precision first: a gate that fires on prose
    gets switched off; a gate that misses a wrapped instruction still
    catches the next unwrapped one.
    """
    plan_dir = _purity_plan(tmp_path, step_text="Dispatch the\ncold-reader agent over the draft")
    assert _dispatch_issues(plan_dir) == []


def test_self_review_dispatch_message_quotes_the_whole_backticked_agent(tmp_path):
    """The reported match is the COMPLETE token, closing backtick included.

    This is what the backticked object arm is for. Drop it and the role
    word alone still matches, but the message truncates to
    "Dispatch `blog-craft:post-researcher" — an author scanning their own
    step for the quoted text would not find it.
    """
    issue = _assert_exactly_one_new_issue(
        tmp_path, "Dispatch `blog-craft:post-researcher` per post"
    )
    assert "'Dispatch `blog-craft:post-researcher`'" in issue.message


def test_self_review_dispatch_gate_catches_a_glued_plugin_name(tmp_path):
    """The colon arm, defended.

    `blog-craft:postresearcher` has no word boundary before `researcher`,
    so the role-word arm cannot see it; only the `plugin:name` arm can.
    """
    _assert_exactly_one_new_issue(tmp_path, "Dispatch blog-craft:postresearcher per post")


def test_self_review_dispatch_gate_ignores_manual_phase_steps(tmp_path):
    """Decision d3: the `[manual]` phase IS the escape route.

    A dispatch that genuinely needs an Agent tool is not forbidden — it is
    work for an actor that has one, and a manual phase is where that actor
    is the operator's own main loop. So the gate must never fire there,
    or the escape the error message offers would not exist.
    """
    plan_dir = _purity_plan(
        tmp_path,
        phase1_tag="manual",
        step_text="Dispatch `blog-craft:post-researcher` per post",
    )
    assert _dispatch_issues(plan_dir) == []


def test_self_review_dispatch_gate_exempts_completed_steps(tmp_path):
    """Mirrors `test_self_review_manual_verb_exempts_completed_steps`.

    A ticked step already ran; the exemption keeps historical plans (and
    plans whose step text QUOTES a dispatch instruction) from
    retro-erroring. 1827 of the corpus's 2113 agentic steps are ticked —
    which is also why the corpus measurement is taken over ALL steps, not
    over the subset this exemption leaves.
    """
    from fr.plan_ops import tick

    plan_dir = _purity_plan(tmp_path, step_text="Dispatch `blog-craft:post-researcher` per post")
    tick(plan_dir, "P1.T1.S1")  # state 'x'
    assert _dispatch_issues(plan_dir) == []


def test_self_review_dispatch_gate_strips_fences_but_not_inline_backticks(tmp_path):
    """A fenced block is content being WRITTEN, not an instruction.

    Inline backticks are the opposite: the backticked agent name IS the
    object the detector keys on, so stripping them would turn the observed
    defect into "Dispatch   per post" and blind the gate (spec §4.A).
    """
    from fr.plan_ops import _RE_DISPATCH_HEAD

    # The fenced instruction carries its own list-marker boundary, so it
    # DOES match the head pattern on the raw text — verified, because a
    # fixture the strip is not load-bearing for would pass with
    # `_strip_fenced_code` deleted.
    fenced = _purity_plan(
        tmp_path / "fenced",
        step_text=(
            "Quote the rejected wording in the skill's example block:\n\n"
            "```\n"
            "- Dispatch the cold-reader agent over the draft\n"
            "```"
        ),
    )
    assert _RE_DISPATCH_HEAD.search("```\n- Dispatch the cold-reader agent over the draft\n```"), (
        "fixture no longer exercises the strip"
    )
    assert _dispatch_issues(fenced) == []

    inline = _purity_plan(
        tmp_path / "inline",
        step_text=(
            "Dispatch `blog-craft:post-researcher` per post, writing each "
            "result to:\n\n"
            "```\n"
            "docs/research/<slug>.md\n"
            "```"
        ),
    )
    issues = _dispatch_issues(inline)
    assert len(issues) == 1, [str(i) for i in issues]
    assert "blog-craft:post-researcher" in issues[0].message


def test_self_review_dispatch_gate_pairs_a_four_backtick_fence(tmp_path):
    """A fence is closed by a run AT LEAST AS LONG as its opener.

    Phases 3 and 4 must quote a rejected step into SKILL.md, which means a
    ````markdown block wrapping a ```-fenced one — and this repo's corpus
    already contains four-backtick fences. Pairing the outer opener with
    the INNER closer does not merely strip too little: it UN-FENCES the
    quoted instruction, so the gate fires on a step whose only crime is
    quoting the thing it forbids.
    """
    plan_dir = _purity_plan(
        tmp_path,
        step_text=(
            "Quote the rejected step into the skill:\n\n"
            "````markdown\n"
            "```yaml\n"
            "text: whatever\n"
            "```\n"
            "- Dispatch the cold-reader agent over the draft\n"
            "````"
        ),
    )
    assert _dispatch_issues(plan_dir) == []


def test_self_review_dispatch_gate_treats_an_unterminated_fence_as_open(tmp_path):
    """An unterminated fence strips to end of text — decided, not incidental.

    For a precision-first gate that is the safer reading of an ambiguous
    document: an author who opened a block meant everything after it to be
    content. The opposite reading (strip nothing) turns one missing
    backtick into a false error.
    """
    plan_dir = _purity_plan(
        tmp_path,
        step_text=(
            "Sketch the rejected step:\n\n```\n- Dispatch the cold-reader agent over the draft"
        ),
    )
    assert _dispatch_issues(plan_dir) == []


def test_plan_self_review_cli_exits_1_and_names_both_escapes(tmp_path, monkeypatch):
    """End-to-end #428 contract: the verdict an author actually reads.

    Four load-bearing tokens, because each carries one of the four things
    the author needs: what the executor lacks ("no Agent tool"), that the
    absence is structural on the other harness too ("task: deny"), the
    escape ("[manual] phase"), and where to read the rest ("#428").
    """
    from fr.cli import app
    from typer.testing import CliRunner

    plan_dir = _purity_plan(tmp_path, step_text="Dispatch `blog-craft:post-researcher` per post")
    repo = plan_dir.parents[3]
    # `_make_repo` scaffolds the pre-migration `archived-plans/`, which the
    # CLI's layout guard hard-stops on before any command runs.
    (repo / "docs" / "superpowers" / "archived-plans").rmdir()
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(app, ["plan", "self-review", str(plan_dir)])
    assert result.exit_code == 1, result.output
    # Rich wraps to the terminal width, so the tokens are asserted against
    # whitespace-normalized output: a line break landing between "no" and
    # "Agent tool" is a rendering detail, not a missing token.
    flat = " ".join(result.output.split())
    # BOTH escapes, as this test's name claims: the [manual] phase AND
    # "name the outcome". The second is the half d1 called the thing that
    # makes the lint actionable — a gate that errors without saying what to
    # write instead is half a fix — so it must not be droppable in silence.
    for token in (
        "no Agent tool",
        "task: deny",
        "[manual] phase",
        "Name the OUTCOME",
        "#428",
        # The escape must name the TRAILING manual phase. #496 (shipped in
        # 4.12.0) errors on a mid-plan manual phase with agentic work after
        # it, so "move it into a [manual] phase" — the message as first
        # written — hands the author a plan that fails the sibling gate.
        # Demonstrated: make the dispatch step's phase manual mid-plan and
        # self-review swaps #428's error for #496's.
        "TRAILING",
        "#496",
    ):
        assert token in flat, f"{token!r} missing from:\n{flat}"
    # The MATCHED TEXT, not the raw pattern — an author reading
    # `(?:dispatch|delegate to|...)` learns nothing about their own step.
    assert "Dispatch `blog-craft:post-researcher`" in flat


def test_create_rejects_phase_zero_before_writing(tmp_path):
    """Phase numbering starts at 1. create() must refuse a 0-numbered
    PhaseSpec BEFORE any file is written — failing only at the post-write
    re-parse would strand a half-built folder (the #133 failure mode)."""
    from fr.plan_ops import PhaseSpec, PlanEditError, create

    repo = _make_repo(tmp_path)
    spec_path = _make_spec(repo)
    with pytest.raises(PlanEditError, match="starts at 1"):
        create(
            repo_root=repo,
            slug="2026-06-04-zero-phase",
            spec=str(spec_path.relative_to(repo)),
            target_repo="derio-net/test",
            fr_version=">=3.0.0,<5.0.0",
            phases=[
                PhaseSpec(number=0, title="Prereqs", tag="manual"),
                PhaseSpec(number=1, title="Build", tag="agentic"),
            ],
            prose="# x\n",
        )
    folder = repo / "docs" / "superpowers" / "plans" / "2026-06-04-zero-phase"
    assert not folder.exists(), "phase-0 rejection must not strand a half-built folder"


def test_self_review_warns_on_overlong_plan_label(tmp_path):
    """#249: a slug whose NORMALIZED `plan:<slug>` form still exceeds GitHub's
    50-char label limit must surface a self-review warning (it's
    auto-truncated, but the operator should know to shorten the slug)."""
    from fr.plan_ops import PhaseSpec, create, self_review

    repo = _make_repo(tmp_path)
    spec_path = _make_spec(repo)
    # Normalizes to 53 chars -> 'plan:' + 53 = 58 > 50: still over-long.
    slug = "2026-05-23--obs--hop-blog-edge-monitoring-rework-1-extra-words"
    plan = create(
        repo_root=repo,
        slug=slug,
        spec=str(spec_path.relative_to(repo)),
        target_repo="derio-net/test",
        fr_version=">=3.0.0,<5.0.0",
        phases=[PhaseSpec(number=1, title="t", tasks=())],
        prose="# x\n",
    )
    issues = self_review(plan)
    assert any(
        i.severity == "warn" and "50" in i.message and "label" in i.message.lower() for i in issues
    ), [str(i) for i in issues]


def test_self_review_overlong_lint_checks_the_normalized_label(tmp_path):
    """A dated slug whose RAW `plan:<slug>` exceeds 50 chars but whose
    normalized form fits must NOT warn — the label that actually ships is
    the normalized one."""
    from fr.plan_ops import PhaseSpec, create, self_review

    repo = _make_repo(tmp_path)
    spec_path = _make_spec(repo)
    slug = "2026-05-23--obs--hop-blog-edge-monitoring-rework-1"  # raw label 55, normalized 43
    plan = create(
        repo_root=repo,
        slug=slug,
        spec=str(spec_path.relative_to(repo)),
        target_repo="derio-net/test",
        fr_version=">=3.0.0,<5.0.0",
        phases=[PhaseSpec(number=1, title="t", tasks=())],
        prose="# x\n",
    )
    issues = self_review(plan)
    assert not any("label" in i.message.lower() for i in issues), [str(i) for i in issues]


def test_self_review_warns_on_unresolvable_same_repo_spec(tmp_path):
    """#248: a spec in same-repo form (no owner/repo: prefix) that doesn't
    resolve locally is likely a malformed cross-repo ref."""
    from fr import parse
    from fr.plan_ops import PhaseSpec, create, self_review

    repo = _make_repo(tmp_path)
    spec_path = _make_spec(repo)
    create(
        repo_root=repo,
        slug="2026-05-10-specwarn",
        spec=str(spec_path.relative_to(repo)),
        target_repo="derio-net/test",
        fr_version=">=3.0.0,<5.0.0",
        phases=[PhaseSpec(number=1, title="t", tasks=())],
        prose="# x\n",
    )
    meta = repo / "docs" / "superpowers" / "plans" / "2026-05-10-specwarn" / "_meta.yaml"
    meta.write_text(
        meta.read_text().replace(
            f"spec: {spec_path.relative_to(repo)}",
            "spec: willikins/docs/superpowers/specs/nope.md",
        )
    )
    plan = parse(repo / "docs" / "superpowers" / "plans" / "2026-05-10-specwarn")
    issues = self_review(plan)
    assert any(i.severity == "warn" and "cross-repo" in i.message.lower() for i in issues), [
        str(i) for i in issues
    ]


def test_self_review_no_spec_warning_for_valid_cross_repo_form(tmp_path):
    """A correctly-formatted cross-repo spec (owner/repo:path) must NOT warn."""
    from fr import parse
    from fr.plan_ops import PhaseSpec, create, self_review

    repo = _make_repo(tmp_path)
    spec_path = _make_spec(repo)
    create(
        repo_root=repo,
        slug="2026-05-10-xrepo",
        spec=str(spec_path.relative_to(repo)),
        target_repo="derio-net/test",
        fr_version=">=3.0.0,<5.0.0",
        phases=[PhaseSpec(number=1, title="t", tasks=())],
        prose="# x\n",
    )
    meta = repo / "docs" / "superpowers" / "plans" / "2026-05-10-xrepo" / "_meta.yaml"
    meta.write_text(
        meta.read_text().replace(
            f"spec: {spec_path.relative_to(repo)}",
            "spec: derio-net/frank:docs/superpowers/specs/x-design.md",
        )
    )
    plan = parse(repo / "docs" / "superpowers" / "plans" / "2026-05-10-xrepo")
    issues = self_review(plan)
    assert not any("cross-repo" in i.message.lower() for i in issues), [str(i) for i in issues]


def test_is_cross_repo_spec_helper():
    from fr._urls import is_cross_repo_spec

    assert is_cross_repo_spec("derio-net/frank:docs/superpowers/specs/x.md") is True
    assert is_cross_repo_spec("docs/superpowers/specs/x.md") is False
    assert is_cross_repo_spec("willikins/docs/specs/x.md") is False  # no colon


# ---------------------------------------------------------------------------
# implemented/ layout (2026-06-05 dispatch-guards spec, Phase 3)


def _make_implemented_parent_plan(repo: Path, slug: str, spec_path: Path) -> Path:
    """Copy minimal fixture into implemented/plans/ as a 'completed parent'."""
    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    dest = repo / "docs" / "superpowers" / "implemented" / "plans" / slug
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(fixture, dest)
    import yaml as _yaml

    meta = _yaml.safe_load((dest / "_meta.yaml").read_text())
    meta["plan"] = slug
    meta["spec"] = str(spec_path.relative_to(repo))
    (dest / "_meta.yaml").write_text(_yaml.safe_dump(meta, sort_keys=False))
    return dest


def test_rework_create_accepts_parent_under_implemented_plans(tmp_path):
    from fr.plan_ops import rework_create

    repo = _make_repo(tmp_path)
    spec = _make_spec(repo)
    parent = _make_implemented_parent_plan(repo, "2026-05-08-parent", spec)

    rework = rework_create(parent)
    assert rework.meta.parent_plan is not None
    assert "2026-05-08-parent" in rework.meta.parent_plan


def test_rework_number_scans_implemented_plans(tmp_path):
    """A rework-1 already archived under implemented/plans/ must push the
    next rework number to 2, not collide or restart at 1."""
    from fr.plan_ops import rework_create

    repo = _make_repo(tmp_path)
    spec = _make_spec(repo)
    parent = _make_implemented_parent_plan(repo, "2026-05-08-parent", spec)
    (repo / "docs" / "superpowers" / "implemented" / "plans" / "2026-05-08-parent-rework-1").mkdir(
        parents=True
    )

    rework = rework_create(parent)
    assert rework.dir.name == "2026-05-08-parent-rework-2"


# ---------------------------------------------------------------------------
# vk.plan_ops.clear_tracking_issue (2026-06-05 dispatch-guards spec, Phase 6)


def test_clear_tracking_issue_nulls_field_and_returns_true(tmp_path):
    from fr.plan_ops import clear_tracking_issue, set_tracking_issue

    repo = _make_repo(tmp_path)
    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    plan_dir = repo / "docs" / "superpowers" / "plans" / "2026-05-09-fixture-minimal"
    shutil.copytree(fixture, plan_dir)

    url = "https://github.com/derio-net/test/issues/7"
    set_tracking_issue(plan_dir, 1, url)
    assert url in (plan_dir / "01.yaml").read_text()

    assert clear_tracking_issue(plan_dir, 1) is True
    text = (plan_dir / "01.yaml").read_text()
    assert url not in text
    assert "tracking_issue: null" in text


def test_clear_tracking_issue_noop_when_already_null(tmp_path):
    from fr.plan_ops import clear_tracking_issue

    repo = _make_repo(tmp_path)
    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    plan_dir = repo / "docs" / "superpowers" / "plans" / "2026-05-09-fixture-minimal"
    shutil.copytree(fixture, plan_dir)

    before = (plan_dir / "01.yaml").read_text()
    assert clear_tracking_issue(plan_dir, 1) is False
    assert (plan_dir / "01.yaml").read_text() == before


# ── 2026-06-06 spec-path-repair: canonical writers + spec fallback ──


def test_create_writes_bare_slug_file_cell(tmp_path):
    from fr.plan_ops import PhaseSpec, create

    repo = _make_repo(tmp_path)
    spec_path = _make_spec(repo)
    create(
        repo_root=repo,
        slug="2026-06-06-slugcell",
        spec=str(spec_path.relative_to(repo)),
        target_repo="derio-net/test",
        fr_version=">=1.0.0,<5.0.0",
        phases=[PhaseSpec(number=1, title="t", tasks=())],
        prose="# p\n",
    )
    table = spec_path.read_text()
    assert "| `2026-06-06-slugcell` |" in table or "| 2026-06-06-slugcell |" in table
    assert "docs/superpowers/plans/2026-06-06-slugcell" not in table


def test_rework_create_from_archived_spec_appends_row(tmp_path):
    """Parent's meta.spec records specs/X.md but the spec archived to
    implemented/specs/ — rework_create must resolve it and append the
    row (the old code silently skipped on a stale path)."""
    from fr.plan_ops import rework_create

    repo = _make_repo(tmp_path)
    spec = _make_spec(repo)
    parent = _make_archived_parent_plan(repo, "2026-06-06-parent", spec)
    moved = repo / "docs" / "superpowers" / "implemented" / "specs" / spec.name
    moved.parent.mkdir(parents=True, exist_ok=True)
    spec.rename(moved)

    rework = rework_create(parent)
    assert "2026-06-06-parent-rework-1" in moved.read_text()
    assert rework.meta.parent_plan == "2026-06-06-parent"


def test_rework_create_writes_canonical_refs(tmp_path):
    from fr.plan_ops import rework_create

    repo = _make_repo(tmp_path)
    spec = _make_spec(repo)
    parent = _make_archived_parent_plan(repo, "2026-06-06-canon", spec)

    rework = rework_create(parent)
    # parent_plan: bare slug, not a path
    assert rework.meta.parent_plan == "2026-06-06-canon"
    # spec: bare filename for same-repo refs
    assert rework.meta.spec == spec.name
    # spec-table File cell: bare rework slug
    table = spec.read_text()
    assert "2026-06-06-canon-rework-1" in table
    assert "docs/superpowers/plans/2026-06-06-canon-rework-1" not in table


def test_self_review_resolves_slug_form_spec(tmp_path):
    """#248 warn must not fire for a canonical slug-form spec ref that
    resolves via the lifecycle roots (2026-06-06 dogfood find)."""
    import shutil

    from fr.parser import parse
    from fr.plan_ops import self_review

    repo = _make_repo(tmp_path)
    spec = _make_spec(repo)
    plan_dir = repo / "docs" / "superpowers" / "plans" / "2026-06-06-slugspec"
    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    shutil.copytree(fixture, plan_dir)
    meta = (plan_dir / "_meta.yaml").read_text()
    meta = meta.replace(
        "spec: docs/superpowers/specs/fixture-spec-design.md",
        f"spec: {spec.name}",
    )
    (plan_dir / "_meta.yaml").write_text(meta)

    issues = self_review(parse(plan_dir))
    assert not any("does not resolve under the repo root" in i.message for i in issues), issues

    # ...and it still fires when the slug-form ref resolves nowhere.
    meta = meta.replace(f"spec: {spec.name}", "spec: 2026-06-06-gone-design.md")
    (plan_dir / "_meta.yaml").write_text(meta)
    issues = self_review(parse(plan_dir))
    assert any("does not resolve under the repo root" in i.message for i in issues)


# ---------------------------------------------------------------------------
# fr plan self-review — walking-skeleton gate (methodology restoration)


def _skeleton_plan(tmp_path, *, skeleton_on=()):
    """Scaffold a two-agentic-phase plan, marking `skeleton: True` on the
    phases in `skeleton_on`. Returns the plan dir."""
    from fr.plan_ops import PhaseSpec, create

    repo = _make_repo(tmp_path)
    spec_path = _make_spec(repo)
    slug = "2026-09-09-skeleton"
    create(
        repo_root=repo,
        slug=slug,
        spec=str(spec_path.relative_to(repo)),
        target_repo="derio-net/test",
        fr_version=">=3.0.0,<5.0.0",
        phases=[
            PhaseSpec(
                number=1,
                title="Build",
                tasks=(
                    {
                        "number": 1,
                        "title": "t",
                        "steps": [{"id": "P1.T1.S1", "text": "Run the test suite"}],
                    },
                ),
                skeleton=1 in skeleton_on,
            ),
            PhaseSpec(
                number=2,
                title="More",
                tasks=(
                    {
                        "number": 1,
                        "title": "t",
                        "steps": [{"id": "P2.T1.S1", "text": "Run the test suite"}],
                    },
                ),
                skeleton=2 in skeleton_on,
            ),
        ],
        prose="# x\n",
    )
    return repo / "docs" / "superpowers" / "plans" / slug


def _skeleton_issues(plan_dir):
    from fr.parser import parse
    from fr.plan_ops import self_review

    return [i for i in self_review(parse(plan_dir)) if "skeleton" in i.message]


def test_self_review_errors_when_first_agentic_phase_is_not_a_skeleton(tmp_path):
    issues = _skeleton_issues(_skeleton_plan(tmp_path))

    assert any(i.severity == "error" and "phase 1" in i.message for i in issues), issues


def test_self_review_passes_skeleton_gate_when_phase_1_marked(tmp_path):
    issues = _skeleton_issues(_skeleton_plan(tmp_path, skeleton_on=(1,)))

    assert all(i.severity != "error" for i in issues), issues
    # ...but the fr_version floor probe still warns: this plan admits a
    # pre-skeleton fr while marking a skeleton.
    assert any("floor it at" in i.message for i in issues), issues


def test_self_review_errors_when_skeleton_marks_a_later_phase(tmp_path):
    """The marker belongs on the FIRST agentic phase — later work builds on
    verified ground, so a skeleton anywhere else is a mis-scoped plan."""
    issues = _skeleton_issues(_skeleton_plan(tmp_path, skeleton_on=(2,)))

    assert any("phase 2" in i.message for i in issues), issues


def test_self_review_errors_when_first_phase_is_manual_only(tmp_path):
    """No agentic phase at all means nothing to build on — the gate stays
    silent (there is no implementation to verify early)."""
    from fr.plan_ops import PhaseSpec, create

    repo = _make_repo(tmp_path)
    spec_path = _make_spec(repo)
    create(
        repo_root=repo,
        slug="2026-09-09-manual-only",
        spec=str(spec_path.relative_to(repo)),
        target_repo="derio-net/test",
        fr_version=">=3.0.0,<5.0.0",
        phases=[
            PhaseSpec(
                number=1,
                title="Hands",
                tag="manual",
                tasks=(
                    {
                        "number": 1,
                        "title": "t",
                        "steps": [{"id": "P1.T1.S1", "text": "Rotate the secret"}],
                    },
                ),
            ),
        ],
        prose="# x\n",
    )
    plan_dir = repo / "docs" / "superpowers" / "plans" / "2026-09-09-manual-only"

    assert _skeleton_issues(plan_dir) == []


def test_skeleton_override_decision_in_spec_journal_silences_the_gate(tmp_path):
    """The only override is an explicit operator decision logged at spec
    scope: a `decision` entry ided `skeleton-override-<plan-slug>`."""
    from fr.journal.model import journal_path

    plan_dir = _skeleton_plan(tmp_path)
    repo = plan_dir.parents[3]
    journal = journal_path(repo, "spec", "2026-05-10-test-spec")
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(
        "# Journal: 2026-05-10-test-spec\n\n"
        "<!-- fr:journal kind=decision scope=spec "
        "id=skeleton-override-2026-09-09-skeleton created=2026-09-09T00:00:00 -->\n"
        "### skeleton-override-2026-09-09-skeleton · decision · Skeleton N/A here\n\n"
        "Pure docs change; no runtime to smoke.\n"
    )

    assert _skeleton_issues(plan_dir) == []


def test_skeleton_override_survives_spec_archival(tmp_path):
    """The override outlives the spec it was logged against: an archived
    spec-scope journal still silences the gate."""
    import shutil

    from fr.journal.model import archived_journal_path, journal_path

    plan_dir = _skeleton_plan(tmp_path)
    repo = plan_dir.parents[3]
    active = journal_path(repo, "spec", "2026-05-10-test-spec")
    active.parent.mkdir(parents=True, exist_ok=True)
    active.write_text(
        "# Journal: 2026-05-10-test-spec\n\n"
        "<!-- fr:journal kind=decision scope=spec "
        "id=skeleton-override-2026-09-09-skeleton created=2026-09-09T00:00:00 -->\n"
        "### skeleton-override-2026-09-09-skeleton · decision · Skeleton N/A here\n\n"
        "Pure docs change; no runtime to smoke.\n"
    )
    archived = archived_journal_path(repo, "spec", "2026-05-10-test-spec")
    archived.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(active), str(archived))

    assert _skeleton_issues(plan_dir) == []


def _sole_skeleton_plan(tmp_path, *, with_manual=False):
    """ONE agentic phase, marked `skeleton: true` — the shape of the #497 run's
    plan (2026-09-21 debug journal C2). `with_manual` appends a manual phase,
    which must not count as the "real work" after the smoke."""
    from fr.plan_ops import PhaseSpec, create

    repo = _make_repo(tmp_path)
    spec_path = _make_spec(repo)
    slug = "2026-09-09-skeleton"
    phases = [
        PhaseSpec(
            number=1,
            title="Everything",
            tasks=(
                {
                    "number": 1,
                    "title": "t",
                    "steps": [{"id": "P1.T1.S1", "text": "Run the test suite"}],
                },
            ),
            skeleton=True,
        )
    ]
    if with_manual:
        phases.append(
            PhaseSpec(
                number=2,
                title="Hands",
                tag="manual",
                depends_on=(1,),
                tasks=(
                    {
                        "number": 1,
                        "title": "t",
                        "steps": [{"id": "P2.T1.S1", "text": "Rotate the secret"}],
                    },
                ),
            )
        )
    create(
        repo_root=repo,
        slug=slug,
        spec=str(spec_path.relative_to(repo)),
        target_repo="derio-net/test",
        fr_version=">=4.2.0,<5.0.0",
        phases=phases,
        prose="# x\n",
    )
    return repo / "docs" / "superpowers" / "plans" / slug


@pytest.mark.parametrize("with_manual", [False, True])
def test_self_review_errors_when_the_skeleton_is_the_only_agentic_phase(tmp_path, with_manual):
    """2026-09-21 debug journal C2: the first fr-goal run after #508 shipped a
    one-phase plan whose single phase was marked the walking skeleton AND
    carried the whole change (tests, rewrite, mirrors, matrix, version bump).
    The gate only checked WHERE the marker sat, so it passed, and the per-phase
    implement → review loop ran exactly once. A skeleton is the smoke BEFORE the
    expensive part; with nothing after it, it is not a skeleton, it is the plan.
    Operator decision: an error, overridable like every other skeleton error."""
    issues = _skeleton_issues(_sole_skeleton_plan(tmp_path, with_manual=with_manual))

    assert any(i.severity == "error" and "only agentic phase" in i.message for i in issues), issues


def test_sole_skeleton_error_is_silenced_by_the_skeleton_override(tmp_path):
    """The same escape hatch as the unmarked-first-phase error: a genuinely
    tiny change records WHY on the spec journal instead of splitting itself
    into ceremony phases."""
    from fr.journal.model import journal_path

    plan_dir = _sole_skeleton_plan(tmp_path)
    repo = plan_dir.parents[3]
    journal = journal_path(repo, "spec", "2026-05-10-test-spec")
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(
        "# Journal: 2026-05-10-test-spec\n\n"
        "<!-- fr:journal kind=decision scope=spec "
        "id=skeleton-override-2026-09-09-skeleton created=2026-09-09T00:00:00 -->\n"
        "### skeleton-override-2026-09-09-skeleton · decision · One-line fix\n\n"
        "Single-line change; a separate smoke phase would test nothing new.\n"
    )

    assert _skeleton_issues(plan_dir) == []


def test_create_writes_skeleton_marker_only_when_set(tmp_path):
    """Byte-stability: plans that predate the marker carry no `skeleton:` key,
    so an old reader never meets a key it cannot parse."""
    from fr.parser import parse

    marked = parse(_skeleton_plan(tmp_path, skeleton_on=(1,)))
    assert marked.phases[0].phase.skeleton is True
    assert "skeleton: true" in (marked.dir / "01.yaml").read_text()
    # ...while the unmarked sibling phase of the SAME plan parses False and
    # carries no key at all.
    assert marked.phases[1].phase.skeleton is False
    assert "skeleton" not in (marked.dir / "02.yaml").read_text()


# ---------------------------------------------------------------------------
# the refactor-or-justify gate (methodology restoration; at resolve since 2026-09-25)


def _refactor_plan(tmp_path, *, step_texts=(), tag="agentic", ticked=False):
    """Scaffold a one-phase plan whose single task carries `step_texts`
    (default: a red+green pair with no refactor). Returns the plan dir."""
    from fr.plan_ops import PhaseSpec, create, tick

    repo = _make_repo(tmp_path)
    spec_path = _make_spec(repo)
    slug = "2026-09-09-refactor"
    texts = step_texts or ("RED: add the test", "GREEN: implement it")
    plan_dir = repo / "docs" / "superpowers" / "plans" / slug
    create(
        repo_root=repo,
        slug=slug,
        spec=str(spec_path.relative_to(repo)),
        target_repo="derio-net/test",
        fr_version=">=3.0.0,<5.0.0",
        phases=[
            PhaseSpec(
                number=1,
                title="Build",
                tag=tag,
                tasks=(
                    {
                        "number": 1,
                        "title": "t",
                        "steps": [
                            {"id": f"P1.T1.S{i + 1}", "text": text} for i, text in enumerate(texts)
                        ],
                    },
                ),
                skeleton=True,
            ),
        ],
        prose="# x\n",
    )
    if ticked:
        for i in range(len(texts)):
            tick(plan_dir, f"P1.T1.S{i + 1}", state="x")
    return plan_dir


def _refactor_issues(plan_dir):
    """The refactor gate's verdict for phase 1. It moved from `fr plan
    self-review` to `fr run resolve` (spec 2026-09-25 §5.C.2.2); the rules
    are `fr.record.gates.refactor_gaps`'s."""
    from fr.parser import parse
    from fr.record.gates import refactor_gaps

    return refactor_gaps(parse(plan_dir), 1)


def test_self_review_no_longer_gates_a_missing_refactor(tmp_path):
    from fr.parser import parse
    from fr.plan_ops import self_review

    issues = self_review(parse(_refactor_plan(tmp_path)))

    assert not [i for i in issues if "no-refactor-because" in i.message], issues


def test_the_gate_names_a_multi_step_task_without_refactor(tmp_path):
    assert _refactor_issues(_refactor_plan(tmp_path)) == ["P1.T1"]


def test_the_gate_passes_task_with_a_refactor_step(tmp_path):
    plan_dir = _refactor_plan(
        tmp_path,
        step_texts=("RED: add the test", "GREEN: implement it", "Refactor: extract it"),
    )

    assert _refactor_issues(plan_dir) == []


def test_the_gate_passes_single_step_task_without_refactor(tmp_path):
    """A one-step task is trivial — fr-plan omits the refactor step when
    there is nothing to clean, and so does this gate."""
    plan_dir = _refactor_plan(tmp_path, step_texts=("Run the test suite",))

    assert _refactor_issues(plan_dir) == []


def test_the_gate_still_asks_of_a_fully_ticked_task(tmp_path):
    """At resolve every task IS ticked — the exemption plan time needed for
    finished plans would make the gate vacuous where it now runs."""
    plan_dir = _refactor_plan(tmp_path, ticked=True)

    assert _refactor_issues(plan_dir) == ["P1.T1"]


def test_the_gate_exempts_manual_phases(tmp_path):
    plan_dir = _refactor_plan(tmp_path, tag="manual")

    assert _refactor_issues(plan_dir) == []


def test_journal_justification_silences_the_refactor_gate(tmp_path):
    """The recorded alternative to a refactor step: a plan-scope
    discovery/decision carrying `no-refactor-because` and the task id."""
    from fr.journal.model import journal_path

    plan_dir = _refactor_plan(tmp_path)
    repo = plan_dir.parents[3]
    journal = journal_path(repo, "plan", "2026-09-09-refactor")
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(
        "# Journal: 2026-09-09-refactor\n\n"
        "<!-- fr:journal kind=discovery scope=plan "
        "id=p1t1-norefactor created=2026-09-09T00:00:00 phase=1 -->\n"
        "### p1t1-norefactor · discovery · no-refactor-because P1.T1\n\n"
        "Two-line glue; nothing to extract.\n"
    )

    assert _refactor_issues(plan_dir) == []


# --- phase tier carried by `create()` (dispatch-holder-identity, finding f6) ---
#
# `PhaseHeader.tier` is the harness-neutral hint fr-goal §5 resolves to a model
# via `fr models resolve`, and fr-plan's own skill says it "tags each phase a
# tier". `PhaseSpec` carried no such field, so `fr plan create --phases-file`
# accepted a `tier:` in the phases file and silently dropped it — every plan it
# scaffolded was untiered, and every dispatch made from one could only record
# `model: null`.


def _tiered(tmp_path, tier=None):
    from fr.plan_ops import PhaseSpec, create

    kwargs = {"tier": tier} if tier is not None else {}
    return create(
        repo_root=tmp_path,
        slug="2026-09-20-tiered",
        spec=None,
        target_repo="derio-net/test",
        fr_version=">=4.2.0,<5.0.0",
        phases=[PhaseSpec(number=1, title="Build", tag="agentic", skeleton=True, **kwargs)],
        prose="# x\n",
    ).dir


def test_create_carries_a_phase_tier_into_the_phase_header(tmp_path):
    import yaml

    header = yaml.safe_load((_tiered(tmp_path, "hard") / "01.yaml").read_text())["phase"]

    assert header["tier"] == "hard"


def test_create_omits_tier_when_unset_so_untiered_plans_stay_byte_stable(tmp_path):
    """Same rule `acceptance` and `skeleton` already follow — an absent tier
    must not start emitting `tier: null` into every existing plan."""
    import yaml

    header = yaml.safe_load((_tiered(tmp_path) / "01.yaml").read_text())["phase"]

    assert "tier" not in header


def test_create_refuses_a_tier_outside_the_closed_vocabulary(tmp_path):
    """`PhaseHeader.tier` is a closed Literal, so an unknown tier would write a
    plan that `fr.parser.parse` cannot read back — a scaffold that succeeds and
    produces an unparseable artifact. Refused at create time, naming the valid
    tiers, which are derived from the Literal rather than re-listed."""
    from fr.plan_ops import PlanEditError
    from fr.types import phase_tiers

    with pytest.raises(PlanEditError) as e:
        _tiered(tmp_path, "turbo")

    assert "turbo" in str(e.value)
    for tier in phase_tiers():
        assert tier in str(e.value)


def test_a_tiered_plan_parses_back_with_its_tier(tmp_path):
    """The round-trip that matters: `fr pickup`/`fr run advance` read the tier
    through `fr.parser.parse`, not off the raw yaml."""
    from fr.parser import parse

    plan = parse(_tiered(tmp_path, "mechanical"))

    assert plan.phases[0].phase.tier == "mechanical"
