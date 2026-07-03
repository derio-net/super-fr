"""_resolve_remote_plan_phases — probe path variants, gate on _meta.yaml,
parse NN.yaml, memoize (the cross-repo resolver behind #339)."""

from __future__ import annotations

import yaml
from fr.types import PhaseDoc

from tests.unit.fakes import FakeGhClient


def _phase_yaml(number: int, steps: dict[str, str], completion_at: str | None = None) -> str:
    doc = {
        "schema_version": 2,
        "phase": {
            "number": number,
            "title": f"phase {number}",
            "tag": "agentic",
            "depends_on": [],
            "tracking_issue": None,
        },
        "tasks": [
            {"number": 1, "title": "task", "steps": [{"id": sid, "text": "x"} for sid in steps]}
        ],
        "state": {
            "steps": {
                sid: {"state": st, "ticked_at": None, "note": None} for sid, st in steps.items()
            },
            "completion": {"at": completion_at, "note": None, "observed_prs": []},
        },
    }
    return yaml.safe_dump(doc, sort_keys=False)


def _put_plan(gh: FakeGhClient, repo: str, root: str, slug: str, phases: dict[str, str]) -> None:
    base = f"docs/superpowers/{root}/{slug}"
    gh.remote_tree[(repo, f"{base}/_meta.yaml")] = "schema_version: 2\n"
    for name, body in phases.items():
        gh.remote_tree[(repo, f"{base}/{name}")] = body


def test_resolves_active_plan() -> None:
    from fr.spec import _resolve_remote_plan_phases

    gh = FakeGhClient()
    _put_plan(
        gh,
        "owner/repo",
        "plans",
        "myplan",
        {"01.yaml": _phase_yaml(1, {"P1.T1.S1": "x"}, "2026-07-03T00:00:00Z")},
    )
    phases = _resolve_remote_plan_phases(gh, "owner/repo", "myplan", {})
    assert phases is not None
    assert [p.phase.number for p in phases] == [1]
    assert isinstance(phases[0], PhaseDoc)


def test_active_wins_over_implemented() -> None:
    from fr.spec import _resolve_remote_plan_phases

    gh = FakeGhClient()
    # active has two phases, implemented (archived) has one — active must win.
    _put_plan(
        gh,
        "owner/repo",
        "plans",
        "myplan",
        {
            "01.yaml": _phase_yaml(1, {"P1.T1.S1": "x"}),
            "02.yaml": _phase_yaml(2, {"P2.T1.S1": " "}),
        },
    )
    _put_plan(
        gh,
        "owner/repo",
        "implemented/plans",
        "myplan",
        {"01.yaml": _phase_yaml(1, {"P1.T1.S1": "x"})},
    )
    phases = _resolve_remote_plan_phases(gh, "owner/repo", "myplan", {})
    assert phases is not None
    assert [p.phase.number for p in phases] == [1, 2]


def test_missing_meta_is_none() -> None:
    from fr.spec import _resolve_remote_plan_phases

    gh = FakeGhClient()
    # NN.yaml present but no _meta.yaml → not a v2 plan folder.
    gh.remote_tree[("owner/repo", "docs/superpowers/plans/myplan/01.yaml")] = _phase_yaml(
        1, {"P1.T1.S1": "x"}
    )
    assert _resolve_remote_plan_phases(gh, "owner/repo", "myplan", {}) is None


def test_non_owner_repo_no_call() -> None:
    from fr.spec import _resolve_remote_plan_phases

    gh = FakeGhClient()
    assert _resolve_remote_plan_phases(gh, "—", "myplan", {}) is None
    assert gh.calls == []


def test_not_found_is_none() -> None:
    from fr.spec import _resolve_remote_plan_phases

    gh = FakeGhClient()
    assert _resolve_remote_plan_phases(gh, "owner/repo", "ghost", {}) is None


def test_memo_suppresses_second_lookup() -> None:
    from fr.spec import _resolve_remote_plan_phases

    gh = FakeGhClient()
    _put_plan(gh, "owner/repo", "plans", "myplan", {"01.yaml": _phase_yaml(1, {"P1.T1.S1": "x"})})
    cache: dict[tuple[str, str], list[PhaseDoc] | None] = {}
    _resolve_remote_plan_phases(gh, "owner/repo", "myplan", cache)
    n_after_first = len(gh.calls)
    _resolve_remote_plan_phases(gh, "owner/repo", "myplan", cache)
    assert len(gh.calls) == n_after_first  # cache hit — no new gh calls
