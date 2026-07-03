"""_status_counts — the shared per-plan status arithmetic used by both the
local and the cross-repo branches of compute_status (#339)."""

from __future__ import annotations

from fr.types import PhaseDoc


def _phase(number: int, steps: dict[str, str], completion_at: str | None = None) -> PhaseDoc:
    return PhaseDoc.model_validate(
        {
            "schema_version": 2,
            "phase": {
                "number": number,
                "title": f"phase {number}",
                "tag": "agentic",
                "depends_on": [],
                "tracking_issue": None,
            },
            "tasks": [
                {
                    "number": 1,
                    "title": "task",
                    "steps": [{"id": sid, "text": "x"} for sid in steps],
                }
            ],
            "state": {
                "steps": {
                    sid: {"state": st, "ticked_at": None, "note": None} for sid, st in steps.items()
                },
                "completion": {"at": completion_at, "note": None, "observed_prs": []},
            },
        }
    )


def test_all_complete() -> None:
    from fr.spec import _status_counts

    phases = [
        _phase(1, {"P1.T1.S1": "x"}, completion_at="2026-07-03T00:00:00Z"),
        _phase(2, {"P2.T1.S1": "x", "P2.T1.S2": "x"}, completion_at="2026-07-03T00:00:00Z"),
    ]
    state, pc, pt, ticked, total = _status_counts(phases)
    assert (state, pc, pt, ticked, total) == ("Complete", 2, 2, 3, 3)


def test_in_progress() -> None:
    from fr.spec import _status_counts

    phases = [
        _phase(1, {"P1.T1.S1": "x"}, completion_at="2026-07-03T00:00:00Z"),
        _phase(2, {"P2.T1.S1": " ", "P2.T1.S2": " "}),
    ]
    state, pc, pt, ticked, total = _status_counts(phases)
    assert (state, pc, pt, ticked, total) == ("In Progress", 1, 2, 1, 3)


def test_not_started_zero_steps() -> None:
    from fr.spec import _status_counts

    phases = [_phase(1, {})]
    state, pc, pt, ticked, total = _status_counts(phases)
    assert (state, pc, pt, ticked, total) == ("Not Started", 0, 1, 0, 0)


def test_not_started_untouched() -> None:
    from fr.spec import _status_counts

    phases = [_phase(1, {"P1.T1.S1": " "})]
    state, pc, pt, ticked, total = _status_counts(phases)
    assert (state, pc, pt, ticked, total) == ("Not Started", 0, 1, 0, 1)
