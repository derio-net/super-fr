"""`fr triage board --watch` shares the drive's pacing (spec 2026-10-12-quota-pacing §E, R17).

Fake clock, forge and sleep; nothing here reaches a forge or the wall clock.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import fr.cli  # noqa: F401 - the command modules load in the CLI's order
import pytest
from fr.commands import triage_kanban_cmd
from fr.triage import pacing_state
from fr.triage.model import load_facts
from fr.triage.pacing_state import PacingState
from fr.triage.probe import judgements_digest

from tests.unit.test_triage_batch_drive_cmd import REPO
from tests.unit.test_triage_kanban_cmd import _board, _setup, _Watch

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
OTHER = "derio-net/other"
SUMMARY = {"in_flight": 1, "merged": 0, "pending": 0, "closing": 0}


def _raw(remaining: int, reset: datetime) -> dict[str, Any]:
    one = {"limit": 5000, "used": 5000 - remaining, "remaining": remaining}
    one["reset"] = int(reset.timestamp())
    return {"resources": {"graphql": dict(one), "core": dict(one)}}


class _Quota:
    def __init__(self, *readings: dict[str, Any]) -> None:
        self.readings = list(readings)

    def rate_limit(self) -> dict[str, Any]:
        return self.readings.pop(0) if len(self.readings) > 1 else self.readings[0]


class _Probes:
    def __init__(self, moved: set[str] | None = None) -> None:
        self.moved, self.asked = moved, []

    def probe(self, path: str, etag: str | None) -> tuple[bool, str | None]:
        self.asked.append(path)
        if self.moved is None:
            return False, etag
        return any(f"/{r}/" in f"/{path}" for r in self.moved), "e"


class _Paced(_Watch):
    def __init__(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, quota: _Quota, probes: Any = None
    ) -> None:
        super().__init__(tmp_path, monkeypatch, stop=1)
        self.collects: list[dict[str, Any]] = []

        def collect(scope: Any, target: Any, **kw: Any) -> None:
            self.calls.append("collect")
            self.collects.append(kw)

        monkeypatch.setattr(triage_kanban_cmd, "recollect", collect)
        monkeypatch.setattr(triage_kanban_cmd, "_now", lambda: NOW)
        monkeypatch.setattr(triage_kanban_cmd, "_pace_forge", lambda: quota)
        monkeypatch.setattr(triage_kanban_cmd, "_probe_forge", lambda: probes or _Probes({REPO}))


def _quiet_state(tmp_path: Path) -> None:
    """A state a quiet pass can stand on: a recent full pass, a recorded digest."""
    state = PacingState(
        full_at=NOW,
        judgements_digest=judgements_digest(tmp_path / "judgements.yaml"),
        summary=None,
    )
    pacing_state.save(tmp_path, state)


def test_an_exhausted_budget_sleeps_until_the_reset_plus_thirty_seconds_and_collects_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path)
    w = _Paced(tmp_path, monkeypatch, _Quota(_raw(0, NOW + timedelta(minutes=10))))
    code, out = _board(tmp_path, "--watch")
    assert code == 0, out
    assert w.sleeps == [630.0] and w.calls == []
    assert "quota:" in out and "waiting" in out


def test_below_the_floor_the_watch_collects_what_changed_and_waits_four_intervals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path)
    w = _Paced(tmp_path, monkeypatch, _Quota(_raw(500, NOW + timedelta(hours=1))))
    code, out = _board(tmp_path, "--watch", "--interval", "60")
    assert code == 0, out
    assert w.sleeps == [240.0]  # 4x the interval
    assert "below floor" in out


def test_quota_floor_is_accepted_and_a_bad_one_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path)
    w = _Paced(tmp_path, monkeypatch, _Quota(_raw(2500, NOW + timedelta(hours=1))))
    assert _board(tmp_path, "--watch", "--quota-floor", "0.6")[0] == 0
    assert w.sleeps == [240.0]  # 50% is under a 60% floor
    code, out = _board(tmp_path, "--watch", "--quota-floor", "3")
    assert code == 2 and "quota" in out.lower()


def test_when_every_probe_is_a_304_nothing_is_collected_or_rendered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path)
    (tmp_path / "board.html").write_text("kept")
    _quiet_state(tmp_path)
    w = _Paced(tmp_path, monkeypatch, _Quota(_raw(5000, NOW + timedelta(hours=1))), _Probes(None))
    code, out = _board(tmp_path, "--watch")
    assert code == 0, out
    assert w.calls == [] and w.sleeps == [60]
    assert (tmp_path / "board.html").read_text() == "kept"


def test_a_changed_repo_is_collected_alone_and_the_board_rendered_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path)
    facts = json.loads((tmp_path / "facts.json").read_text())
    facts["repos"] = [REPO, OTHER]
    (tmp_path / "facts.json").write_text(json.dumps(facts))
    _quiet_state(tmp_path)
    w = _Paced(tmp_path, monkeypatch, _Quota(_raw(5000, NOW + timedelta(hours=1))), _Probes({REPO}))
    code, out = _board(tmp_path, "--watch")
    assert code == 0, out
    assert w.calls == ["collect", "write"]
    assert w.collects[0]["only"] == frozenset({REPO})


def test_a_rate_limited_collect_waits_for_the_reset_instead_of_retrying(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path)
    reset = NOW + timedelta(minutes=20)
    w = _Paced(tmp_path, monkeypatch, _Quota(_raw(5000, reset), _raw(0, reset)))

    def boom(scope: Any, target: Any, **kw: Any) -> None:
        w.calls.append("collect")
        raise RuntimeError("API rate limit exceeded")

    monkeypatch.setattr(triage_kanban_cmd, "recollect", boom)
    code, out = _board(tmp_path, "--watch")
    assert code == 0, out
    assert w.sleeps == [1230.0] and w.calls == ["collect"]
    state, _ = pacing_state.load(tmp_path)
    assert state.wait_until == reset + timedelta(seconds=30)


def test_the_watch_records_the_digest_it_collected_on_and_no_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A drive that follows must plan, not stand quiet on the watch's collect (R17)."""
    _setup(tmp_path)
    _Paced(tmp_path, monkeypatch, _Quota(_raw(5000, NOW + timedelta(hours=1))))

    def collect(scope: Any, target: Any, **kw: Any) -> None:
        facts = load_facts(tmp_path / "facts.json")
        kw["after_write"](facts, frozenset())

    monkeypatch.setattr(triage_kanban_cmd, "recollect", collect)
    assert _board(tmp_path, "--watch")[0] == 0
    state, _ = pacing_state.load(tmp_path)
    assert state.summary is None
    assert state.judgements_digest == judgements_digest(tmp_path / "judgements.yaml")
