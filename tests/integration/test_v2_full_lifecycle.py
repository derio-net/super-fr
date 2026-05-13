"""End-to-end lifecycle: create plan → apply (dispatch) → tick → re-apply → complete."""

from __future__ import annotations

import pytest


@pytest.fixture()
def tmp_repo(tmp_path, monkeypatch):
    """Tmp repo with docs/superpowers/{specs,plans} + a stub spec."""
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "specs").mkdir()
    spec_path = tmp_path / "docs" / "superpowers" / "specs" / "2026-05-10-fixture.md"
    spec_path.write_text(
        "# Fixture spec\n\n"
        "## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n"
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_full_lifecycle_create_apply_tick_complete(tmp_repo, monkeypatch):
    """Walk through the v2 lifecycle: create → dispatch → tick → close."""
    from tests.unit.fakes import FakeGhClient
    from vk import parse
    from vk.apply import apply
    from vk.diff import IssueCreate, RepoLabelEnsure, diff
    from vk.observe import observe
    from vk.plan_ops import PhaseSpec, create, tick
    from vk.render import render

    # 1. CREATE the plan
    create(
        repo_root=tmp_repo,
        slug="2026-05-10-lifecycle",
        spec="docs/superpowers/specs/2026-05-10-fixture.md",
        target_repo="derio-net/superpowers-for-vk",
        vk_version=">=1.0.0,<3.0.0",
        phases=[
            PhaseSpec(
                number=1,
                title="Setup",
                tag="agentic",
                tasks=({"number": 1, "title": "t", "steps": [{"id": "P1.T1.S1", "text": "s"}]},),
            )
        ],
        prose="# Lifecycle test\n",
    )
    plan_dir = tmp_repo / "docs" / "superpowers" / "plans" / "2026-05-10-lifecycle"
    assert plan_dir.is_dir()
    plan = parse(plan_dir)

    # 2. APPLY (dispatch) — creates Issue via FakeGhClient
    gh = FakeGhClient()
    observed = observe(plan, gh)
    rendered = render(plan, observed)
    d = diff(rendered, observed, plan=plan)
    assert any(isinstance(m, IssueCreate) for m in d.mutations)
    result = apply(d, gh)
    assert result.failures == ()
    new_url = result.created_issues[1]
    assert new_url.startswith("https://github.com/")

    # 3. Inject the URL back, simulate plan-side commit
    from vk import plan_ops

    plan_ops.set_tracking_issue(plan_dir, 1, new_url)

    # 4. TICK the step
    tick(plan_dir, "P1.T1.S1")

    # 5. Simulate a merged PR for the phase
    issue_n = int(new_url.rsplit("/", 1)[-1])
    gh.issues[("derio-net/superpowers-for-vk", issue_n)].linked_prs.append(
        {
            "url": "https://github.com/derio-net/superpowers-for-vk/pull/999",
            "state": "CLOSED",
            "merged": True,
            "draft": False,
            "ci": "PASS",
        }
    )

    # 6. RE-APPLY: phase is now Complete; renderer says CLOSED; apply closes Issue
    plan2 = parse(plan_dir)
    observed2 = observe(plan2, gh)
    rendered2 = render(plan2, observed2)
    d2 = diff(rendered2, observed2, plan=plan2)
    apply(d2, gh)
    assert gh.issues[("derio-net/superpowers-for-vk", issue_n)].state == "CLOSED"

    # 7. Final cycle is a no-op (only RepoLabelEnsure remains)
    plan3 = parse(plan_dir)
    observed3 = observe(plan3, gh)
    rendered3 = render(plan3, observed3)
    d3 = diff(rendered3, observed3, plan=plan3)
    non_label = [m for m in d3.mutations if not isinstance(m, RepoLabelEnsure)]
    assert non_label == []


def test_full_lifecycle_manual_phase(tmp_repo):
    """Manual phase: completes via complete_phase(--note); apply closes Issue."""
    from tests.unit.fakes import FakeGhClient
    from vk import parse
    from vk.apply import apply
    from vk.diff import diff
    from vk.observe import observe
    from vk.plan_ops import PhaseSpec, complete_phase, create
    from vk.render import render

    create(
        repo_root=tmp_repo,
        slug="2026-05-10-manual",
        spec="docs/superpowers/specs/2026-05-10-fixture.md",
        target_repo="derio-net/superpowers-for-vk",
        vk_version=">=1.0.0,<3.0.0",
        phases=[PhaseSpec(number=1, title="Manual setup", tag="manual")],
        prose="# Manual\n",
    )
    plan_dir = tmp_repo / "docs" / "superpowers" / "plans" / "2026-05-10-manual"

    # Dispatch
    gh = FakeGhClient()
    plan = parse(plan_dir)
    apply(diff(render(plan, observe(plan, gh)), observe(plan, gh), plan=plan), gh)

    # Operator finishes runbook
    new_url = list(gh.issues.keys())[0]
    from vk import plan_ops

    url = f"https://github.com/{new_url[0]}/issues/{new_url[1]}"
    plan_ops.set_tracking_issue(plan_dir, 1, url)
    complete_phase(plan_dir, 1, note="ran the runbook")

    # Re-apply: Issue closes
    plan2 = parse(plan_dir)
    observed = observe(plan2, gh)
    rendered = render(plan2, observed)
    d = diff(rendered, observed, plan=plan2)
    apply(d, gh)
    assert gh.issues[new_url].state == "CLOSED"
