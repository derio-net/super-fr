"""Close-out, archive and export PRs get a verdict from the readiness family (spec
2026-11-24-batch-merge-readiness R8, §C).

The queue admits one by its trust rule; `drive_pass` keeps the candidates a rule refused with
their reason (`QueueSnapshot.refused`), and `other_readiness(key, qs)` reads both: its trust
fact is "admitted" or the reason, and its `admits` is `_other_ready`'s.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
from fr.triage.batch_drive import LivePr, drive_pass, queue_snapshot
from fr.triage.readiness import Refused, other_readiness
from fr.triage.wave_queue import OtherEntry, QueueSnapshot, _other_ready

from tests.unit.test_triage_batch_drive import REPO, RUNS, _archive, _closed, _snap
from tests.unit.test_triage_readiness import NOW, B, _qs

KINDS = ("closeout", "archive", "export")


def _other_qs(kind: str, pr: LivePr, *, admitted: bool = True, reason: str = "") -> QueueSnapshot:
    key = f"{kind}#{pr.number}"
    entry = OtherEntry(key, kind, pr.number, None, NOW, "b1")  # type: ignore[arg-type]
    base = _qs(B)
    return dataclasses.replace(
        base,
        live={**base.live, key: pr},
        others=(entry,) if admitted else (),
        refused={} if admitted else {key: reason},
        refused_entries=() if admitted else (entry,),
    )


def _pr(**kw: Any) -> LivePr:
    base: dict[str, Any] = {"number": 7, "state": "OPEN", "draft": False, "head": "h7",
                            "checks": "green", "head_ref": "chore/x", "base": "main",
                            "url": "https://github.com/derio-net/super-fr/pull/7"}  # fmt: skip
    return LivePr(**{**base, **kw})


CASES = [
    ("open, green, on the default branch", _pr(), True),
    ("checks running", _pr(checks="pending"), False),
    ("checks red", _pr(checks="failing", failing=("lint",)), False),
    ("based on another branch", _pr(base="release"), False),
    ("closed", _pr(state="CLOSED"), False),
]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(("case", "pr", "admits"), CASES, ids=[c[0] for c in CASES])
def test_admits_is_exactly_the_queues_other_ready(
    kind: str, case: str, pr: LivePr, admits: bool
) -> None:
    qs = _other_qs(kind, pr)
    r = other_readiness(f"{kind}#7", qs)
    assert r.admits == _other_ready(qs.others[0], qs) == admits
    assert r.facts.delivered == ("admitted" if pr.state == "OPEN" else "unknown")


@pytest.mark.parametrize("kind", KINDS)
def test_a_refused_candidate_reads_its_refusal_and_is_never_admitted(kind: str) -> None:
    why = "is not trusted (not from this repo by an allowed author)"
    qs = _other_qs(kind, _pr(), admitted=False, reason=why)
    r = other_readiness(f"{kind}#7", qs)
    assert not r.admits
    assert r.facts.delivered == why
    assert r.verdict == f"Not ready: {why}"
    assert r.facts.whose_move == "the operator"


def test_the_verdict_names_what_an_admitted_entry_waits_on() -> None:
    assert other_readiness("archive#7", _other_qs("archive", _pr(checks="pending"))).verdict == (
        "Not ready: CI running"
    )
    red = other_readiness("archive#7", _other_qs("archive", _pr(checks="failing", failing=("a",))))
    assert red.verdict == "Not ready: CI red: a"
    assert red.facts.ci == "red: a at h7"
    ok = other_readiness("archive#7", _other_qs("archive", _pr()))
    assert ok.verdict == "Admitted, merges next"
    assert ok.facts.link.endswith("/pull/7")


def test_an_unknown_key_is_not_an_entry() -> None:
    r = other_readiness("archive#99", _qs(B))
    assert not r.admits and r.kind == "not-open"


def test_drive_pass_keeps_the_candidate_a_trust_rule_refused() -> None:
    """R8: an archive PR on the wrong base is refused with the driver's own reason."""
    b = _closed("x", 1, archive="chore/archive-p", run="r-x")
    pr = _archive(7, "chore/archive-p", files=(f"{RUNS}/r-x.yaml",), base="release")
    snap = _snap([b], {"x": "merged"}, archives={REPO: (pr,)})
    got = drive_pass(snap)
    assert got.admitted == {}
    qs = queue_snapshot(
        snap, REPO, refused=[Refused("archive", REPO, pr, "is based on release", "x")]
    )
    assert qs.refused == {"archive#7": "is based on release"}
    assert qs.live["archive#7"] is pr and qs.others == ()
    (plan,) = got.queues
    r = plan.readiness["archive#7"]
    assert not r.admits
    assert r.verdict.startswith("Not ready: ") and "release" in r.verdict
    assert "release" in r.facts.delivered


def test_an_admitted_archive_pr_reads_admitted_in_the_plan() -> None:
    b = _closed("x", 1, archive="chore/archive-p", run="r-x")
    pr = _archive(7, "chore/archive-p", files=(f"{RUNS}/r-x.yaml",))
    (plan,) = drive_pass(_snap([b], {"x": "merged"}, archives={REPO: (pr,)})).queues
    r = plan.readiness["archive#7"]
    assert r.admits and r.facts.delivered == "admitted"
    assert r.kind == "merges-next" and r.verdict == "Admitted, merges next"
