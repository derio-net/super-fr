"""`Pacer`'s bookkeeping around a pass (spec 2026-10-12-quota-pacing R9, R11): what
`after_collect` stores once facts.json is written, and what `record_summary` stores
once the pass has planned."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fr.triage import pacing_state
from fr.triage.model import Facts, Unviewed
from fr.triage.pacing import Pacer
from fr.triage.pacing_state import PacingState
from fr.triage.probe import PassPlan

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
A, B = "example-org/alpha", "example-org/beta"
SUMMARY = {"in_flight": 1, "merged": 0, "pending": 0, "closing": 0}


def _pacer(tmp_path: Path, state: PacingState) -> Pacer:
    pacing_state.save(tmp_path, state)
    return Pacer(
        tmp_path,
        floor=0.2,
        interval_s=120,
        api="graphql",
        forge=lambda: None,  # type: ignore[arg-type,return-value]
        now=lambda: NOW,
        warn=lambda _: None,
    )


def _facts(**kw: object) -> Facts:
    return Facts(
        schema=3,
        scope="example-org",
        kind="org",
        collected_at=NOW.isoformat(),
        repos=[A, B],
        issues=[],
        **kw,  # type: ignore[arg-type]
    )


def _plan(**kw: object) -> PassPlan:
    defaults: dict[str, object] = {
        "kind": "partial",
        "only": frozenset({A, B}),
        "carried": frozenset(),
        "digest": "d-now",
        "pending": {A: {"pa": "A2"}, B: {"pb": "B2"}},
    }
    return PassPlan(**{**defaults, **kw})  # type: ignore[arg-type]


def test_a_rate_limited_unviewed_key_fails_its_repo(tmp_path: Path) -> None:
    """p2-r2: the repo of a key the rate limit left unviewed keeps no ETag, so the next
    pass reads it again instead of trusting a 304 over facts it never finished."""
    pacer = _pacer(tmp_path, PacingState(etags={A: {"pa": "A1"}, B: {"pb": "B1"}}))
    facts = _facts(unviewed=[Unviewed(key="beta#99", reason="API rate limit exceeded")])
    pacer.after_collect(_plan(), facts, frozenset())
    etags = pacing_state.load(tmp_path)[0].etags
    assert etags == {A: {"pa": "A2"}}


def test_an_unviewed_key_for_another_reason_keeps_its_repo_s_etags(tmp_path: Path) -> None:
    pacer = _pacer(tmp_path, PacingState())
    facts = _facts(unviewed=[Unviewed(key="beta#99", reason="HTTP 404: Not Found")])
    pacer.after_collect(_plan(), facts, frozenset())
    assert pacing_state.load(tmp_path)[0].etags == {A: {"pa": "A2"}, B: {"pb": "B2"}}


def test_the_collect_s_own_carried_set_decides_which_etags_move(tmp_path: Path) -> None:
    """p2-r5: the repos the collect actually carried keep their ETags, whatever the plan
    expected to carry."""
    pacer = _pacer(tmp_path, PacingState(etags={B: {"pb": "B1"}}))
    pacer.after_collect(_plan(only=frozenset({A}), carried=frozenset({B})), _facts(), frozenset())
    assert pacing_state.load(tmp_path)[0].etags == {A: {"pa": "A2"}, B: {"pb": "B2"}}


def test_a_written_facts_json_is_no_planned_pass(tmp_path: Path) -> None:
    """p2-r1: once facts.json is written the last planned pass's summary no longer
    describes the forge, and the pass may still fail before it plans: the record is
    dropped, so the next pass cannot be quiet on the strength of it."""
    pacer = _pacer(
        tmp_path,
        PacingState(full_at=NOW - timedelta(minutes=1), judgements_digest="d", summary=SUMMARY),
    )
    pacer.after_collect(_plan(digest="d"), _facts(), frozenset())
    state = pacing_state.load(tmp_path)[0]
    assert state.summary is None and state.judgements_digest is None


def test_the_planned_pass_records_its_summary_digest_and_quota_hold(tmp_path: Path) -> None:
    pacer = _pacer(tmp_path, PacingState())
    pacer.record_summary(SUMMARY, digest="d-now", held=True)
    state = pacing_state.load(tmp_path)[0]
    assert (state.summary, state.judgements_digest, state.held_for_quota) == (
        SUMMARY,
        "d-now",
        True,
    )
    pacer.record_summary(SUMMARY, digest="d-now", held=False)
    assert pacing_state.load(tmp_path)[0].held_for_quota is False
