"""compute_status(gh=...) resolves cross-repo rows via the contents API and
degrades to Unreachable on absence / failure / --no-gh (#339)."""

from __future__ import annotations

from pathlib import Path

import yaml
from fr.spec import compute_status, parse_spec

from tests.unit.fakes import FakeGhClient, FakeGhError


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


def _spec_with_crossrepo_row(tmp_path: Path) -> Path:
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    spec_path = specs / "s.md"
    spec_path.write_text(
        "# S\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n"
        "| Remote plan | `owner/repo` | `docs/superpowers/plans/myplan/` | — |\n"
    )
    return spec_path


def _put_plan(gh: FakeGhClient, root: str, phases: dict[str, str]) -> None:
    base = f"docs/superpowers/{root}/myplan"
    gh.remote_tree[("owner/repo", f"{base}/_meta.yaml")] = "schema_version: 2\n"
    for name, body in phases.items():
        gh.remote_tree[("owner/repo", f"{base}/{name}")] = body


def test_archived_remote_counts_complete(tmp_path: Path) -> None:
    spec = _spec_with_crossrepo_row(tmp_path)
    gh = FakeGhClient()
    _put_plan(
        gh,
        "implemented/plans",
        {
            "01.yaml": _phase_yaml(1, {"P1.T1.S1": "x"}, "2026-07-03T00:00:00Z"),
            "02.yaml": _phase_yaml(2, {"P2.T1.S1": "x"}, "2026-07-03T00:00:00Z"),
        },
    )
    st = compute_status(parse_spec(spec), tmp_path, gh=gh)
    row = st.plans[0]
    assert row.state == "Complete"
    assert row.phases_complete == 2 and row.phases_total == 2
    assert st.aggregate.plans_complete == 1
    assert st.aggregate.steps_total == 2  # remote steps in the aggregate


def test_active_remote_in_progress(tmp_path: Path) -> None:
    spec = _spec_with_crossrepo_row(tmp_path)
    gh = FakeGhClient()
    _put_plan(
        gh,
        "plans",
        {
            "01.yaml": _phase_yaml(1, {"P1.T1.S1": "x"}, "2026-07-03T00:00:00Z"),
            "02.yaml": _phase_yaml(2, {"P2.T1.S1": " ", "P2.T1.S2": " "}),
        },
    )
    st = compute_status(parse_spec(spec), tmp_path, gh=gh)
    row = st.plans[0]
    assert row.state == "In Progress"
    assert (row.phases_complete, row.phases_total) == (1, 2)
    assert (row.steps_ticked, row.steps_total) == (1, 3)


def test_no_gh_stays_unreachable(tmp_path: Path) -> None:
    spec = _spec_with_crossrepo_row(tmp_path)
    st = compute_status(parse_spec(spec), tmp_path, gh=None)
    row = st.plans[0]
    assert row.state == "Unreachable"
    assert st.aggregate.plans_complete == 0
    assert st.warnings  # still warns, degrades gracefully


def test_read_failure_degrades(tmp_path: Path) -> None:
    spec = _spec_with_crossrepo_row(tmp_path)
    gh = FakeGhClient()
    _put_plan(gh, "plans", {"01.yaml": _phase_yaml(1, {"P1.T1.S1": "x"})})

    def boom(repo: str, path: str) -> str:
        raise FakeGhError("network down")

    gh.read_file = boom  # type: ignore[method-assign]
    st = compute_status(parse_spec(spec), tmp_path, gh=gh)
    assert st.plans[0].state == "Unreachable"


def test_not_found_degrades(tmp_path: Path) -> None:
    spec = _spec_with_crossrepo_row(tmp_path)
    gh = FakeGhClient()  # empty remote_tree
    st = compute_status(parse_spec(spec), tmp_path, gh=gh)
    row = st.plans[0]
    assert row.state == "Unreachable"
    assert row.note is not None
