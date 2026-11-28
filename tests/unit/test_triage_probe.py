"""Probes, pass kinds and ETag promotion (spec 2026-10-12-quota-pacing §B, R8, R9, R11, R15).

Pure over a `FakeForge` probe table: a probe sent with the ETag the forge holds answers
304, any other a 200 carrying the current one.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import fr.cli  # noqa: F401 - the command modules load in the CLI's order
from fr.triage.errors import ForgeError
from fr.triage.model import PullRequest, load_judgements
from fr.triage.pacing_state import PacingState
from fr.triage.probe import (
    FULL_EVERY,
    QUOTA_HOLD,
    checks_probes,
    issues_probe,
    judgements_digest,
    live_repos,
    pass_kind,
    plan_pass,
    probe_set,
    promote,
    run_probes,
)

from tests.unit.test_triage_batch_drive_cmd import (
    REPO,
    World,
    _batch,
    _dispatch_event,
    _state,
)
from tests.unit.triage_fixtures import FakeForge

OTHER = "derio-net/other"
NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
SUMMARY = {"in_flight": 1, "merged": 0, "pending": 0, "closing": 0}


def _archive_pr(number: int, repo: str = OTHER) -> PullRequest:
    return PullRequest(
        repo=repo,
        number=number,
        title="archive",
        state="OPEN",
        is_draft=False,
        url=f"https://github.com/{repo}/pull/{number}",
        head_ref="chore/archive-b9",
        head_oid=f"sha-{number}",
        author="operator",
        cross_repo=False,
    )


def _world(tmp_path: Path) -> tuple[object, object]:
    """REPO with a pr-open batch (PR #101 at sha-101); OTHER with an open archive PR."""
    world = World()
    world.issues[1] = "open"
    world.pr(101, "feat/batch-b1", [1])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")))
    facts = world.facts().model_copy(
        update={"repos": [REPO, OTHER, "derio-net/quiet"], "prs": [_archive_pr(300)]}
    )
    return facts, load_judgements(tmp_path / "judgements.yaml")


def test_the_probe_set_is_the_issues_probe_per_repo_plus_live_prs_checks(tmp_path: Path) -> None:
    facts, judgements = _world(tmp_path)
    probes = probe_set(facts.repos, facts, judgements)
    assert issues_probe(REPO) == (
        f"repos/{REPO}/issues?state=all&sort=updated&direction=desc&per_page=1"
    )
    assert checks_probes(REPO, "sha-101") == (
        f"repos/{REPO}/commits/sha-101/check-runs?per_page=100",
        f"repos/{REPO}/commits/sha-101/status",
    )
    assert probes == {
        REPO: (issues_probe(REPO), *checks_probes(REPO, "sha-101")),
        OTHER: (issues_probe(OTHER), *checks_probes(OTHER, "sha-300")),
        "derio-net/quiet": (issues_probe("derio-net/quiet"),),
    }
    assert live_repos(facts, judgements) == {REPO, OTHER}


def test_with_no_facts_the_probe_set_is_the_issues_probes() -> None:
    assert probe_set([REPO], None, None) == {REPO: (issues_probe(REPO),)}


def test_full_probes_are_unconditional_and_others_send_the_stored_etag() -> None:
    forge = FakeForge(issues={}, prs={})
    forge.probe_etags = {"a1": "E1", "b1": "F1"}
    state = PacingState(etags={"A": {"a1": "E1"}, "B": {"b1": "OLD"}})
    probes = {"A": ("a1",), "B": ("b1",)}

    changed, pending = run_probes(forge, probes, state, full=False)
    assert forge.probe_calls == [("a1", "E1"), ("b1", "OLD")]
    assert changed == {"B"}
    assert pending == {"A": {"a1": "E1"}, "B": {"b1": "F1"}}

    forge.probe_calls.clear()
    changed, _ = run_probes(forge, probes, state, full=True)
    assert forge.probe_calls == [("a1", None), ("b1", None)]
    assert changed == {"A", "B"}


def test_a_failed_probe_or_a_missing_etag_is_a_change() -> None:
    forge = FakeForge(issues={}, prs={})
    forge.probe_etags = {"a1": "E1", "a2": "E2"}
    forge.probe_failures = {"a2"}
    state = PacingState(etags={"A": {"a1": "E1", "a2": "E2"}, "B": {}})
    changed, pending = run_probes(forge, {"A": ("a1", "a2"), "B": ("b1",)}, state, full=False)
    assert changed == {"A", "B"}
    assert pending == {"A": {"a1": "E1"}}


def test_a_probe_raising_a_forge_error_is_a_change() -> None:
    class Raising(FakeForge):
        def probe(self, path: str, etag: str | None) -> tuple[bool, str | None]:
            raise ForgeError("unsupported")

    changed, pending = run_probes(
        Raising(issues={}, prs={}),
        {"A": ("a1",)},
        PacingState(etags={"A": {"a1": "E"}}),
        full=False,
    )
    assert changed == {"A"} and pending == {}


def test_promote_keeps_read_repos_drops_failed_and_leaves_the_rest() -> None:
    state = PacingState(etags={"A": {"a": "old"}, "B": {"b": "old"}, "C": {"c": "old"}})
    pending = {"A": {"a": "new"}, "B": {"b": "new"}, "C": {"c": "new"}}
    out = promote(state, pending, read_ok={"A"}, failed={"B"})
    assert out.etags == {"A": {"a": "new"}, "C": {"c": "old"}}


def test_an_interleaved_change_is_never_a_stale_304() -> None:
    """The probe's ETag is stored, never one read after the collect: a change landing
    between the probe and the collect answers 200 on the next pass (R11)."""
    forge = FakeForge(issues={}, prs={})
    forge.probe_etags = {"p": "E1"}
    probes = {"A": ("p",)}
    state = PacingState()
    _, pending = run_probes(forge, probes, state, full=True)
    assert pending == {"A": {"p": "E1"}}
    forge.probe_etags = {"p": "E2"}  # the repo changes before the collect reads it
    state = promote(state, pending, read_ok={"A"}, failed=set())
    changed, pending = run_probes(forge, probes, state, full=False)
    assert forge.probe_calls[-1] == ("p", "E1")
    assert changed == {"A"} and pending == {"A": {"p": "E2"}}


def test_pass_kinds() -> None:
    fresh = PacingState(full_at=NOW - timedelta(minutes=1), judgements_digest="d", summary=SUMMARY)
    assert pass_kind(PacingState(), NOW, set(), "d", below_floor=False) == "full"
    old = PacingState(full_at=NOW - FULL_EVERY, judgements_digest="d", summary=SUMMARY)
    assert pass_kind(old, NOW, set(), "d", below_floor=False) == "full"
    assert pass_kind(fresh, NOW, set(), "d", below_floor=False) == "quiet"
    assert pass_kind(fresh, NOW, set(), "edited", below_floor=False) == "partial"
    assert pass_kind(fresh, NOW, {"A"}, "d", below_floor=False) == "partial"
    assert pass_kind(fresh, NOW, {"A"}, "d", below_floor=True) == "essential"
    assert pass_kind(old, NOW, set(), "d", below_floor=True) == "essential"
    # Nothing to collect below the floor either: a quiet pass is cheaper still.
    assert pass_kind(fresh, NOW, set(), "d", below_floor=True) == "quiet"
    # A pass that never recorded its summary cannot be repeated quietly.
    unsummarised = PacingState(full_at=NOW, judgements_digest="d")
    assert pass_kind(unsummarised, NOW, set(), "d", below_floor=False) == "partial"
    # p2-r3: the last planned pass held its dispatches for the quota; above the floor
    # again, the held dispatches are owed a planned pass, whatever the probes say.
    held = replace(fresh, held_for_quota=True)
    assert pass_kind(held, NOW, set(), "d", below_floor=False) == "partial"
    assert pass_kind(held, NOW, set(), "d", below_floor=True) == "quiet"


def test_plan_pass_narrows_to_changed_and_below_the_floor_to_live_repos() -> None:
    repos = ["A", "B", "C"]
    fresh = PacingState(full_at=NOW, judgements_digest="d", summary=SUMMARY)
    old = PacingState(full_at=NOW - FULL_EVERY, judgements_digest="d", summary=SUMMARY)

    def plan(state: PacingState, changed: set[str], below: bool) -> tuple[object, ...]:
        p = plan_pass(state, NOW, repos=repos, changed=changed, digest="d",
                      below_floor=below, live={"A", "B"}, pending={}, probes=3)  # fmt: skip
        return p.kind, p.only, p.carried, p.dispatch_held

    assert plan(old, set(), False) == ("full", None, frozenset(), None)
    assert plan(fresh, {"B"}, False) == ("partial", frozenset({"B"}), frozenset({"A", "C"}), None)
    assert plan(fresh, set(), False) == ("quiet", frozenset(), frozenset(repos), None)
    assert plan(fresh, {"B", "C"}, True) == (
        "essential",
        frozenset({"B"}),
        frozenset({"A", "C"}),
        QUOTA_HOLD,
    )
    # A forced full pass below the floor reads only the live repos (R7, R11).
    assert plan(old, set(), True) == (
        "essential",
        frozenset({"A", "B"}),
        frozenset({"C"}),
        QUOTA_HOLD,
    )
    assert plan(fresh, {"A", "B", "C"}, False)[1] is None  # every repo: no narrowing


# ------------------------------------- close-outs read every pass (merge-truth R8)

_FRESH = PacingState(full_at=NOW, judgements_digest="d", summary=SUMMARY)


def _plan(
    changed: set[str], below: bool, closing: set[str], state: PacingState = _FRESH
) -> tuple[object, ...]:
    p = plan_pass(state, NOW, repos=["A", "B", "C"], changed=changed, digest="d",
                  below_floor=below, live={"A"}, pending={}, probes=3, closing=closing)  # fmt: skip
    return p.kind, p.only, p.carried


def test_plan_pass_adds_closing_to_a_partial_pass() -> None:
    assert _plan({"B"}, False, {"C"}) == ("partial", frozenset({"B", "C"}), frozenset({"A"}))


def test_plan_pass_adds_closing_to_an_essential_pass() -> None:
    kind, only, _ = _plan({"B"}, True, {"C"})
    assert (kind, only) == ("essential", frozenset({"C"}))
    old = replace(_FRESH, full_at=NOW - FULL_EVERY)
    kind, only, _ = _plan(set(), True, {"C"}, old)
    assert (kind, only) == ("essential", frozenset({"A", "C"}))


def test_a_quiet_pass_with_closing_repos_reads_only_them() -> None:
    assert _plan(set(), False, {"B"}) == ("partial", frozenset({"B"}), frozenset({"A", "C"}))
    assert _plan(set(), False, set()) == ("quiet", frozenset(), frozenset({"A", "B", "C"}))


def test_live_repos_includes_closing(tmp_path: Path) -> None:
    """A batch whose close-out started and is not archived keeps its repo live; once
    archived it does not."""
    from fr.triage.probe import closing_repos

    world = World()
    world.issues[1] = "closed"
    world.pr(101, "feat/batch-b1", [1], state="MERGED", merged_at=NOW.isoformat())
    closeout = (
        "      - {kind: closeout, at: 2026-10-02T11:59:00Z, runner: fake, handle: h, "
        "run: r1, archive: chore/archive-p1}\n"
    )
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + closeout))
    facts = world.facts()
    judgements = load_judgements(tmp_path / "judgements.yaml")
    assert closing_repos(facts, judgements) == {REPO}
    assert live_repos(facts, judgements) == {REPO}
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")
                                   + closeout.replace("}\n", ", archived: 7}\n")))  # fmt: skip
    judgements = load_judgements(tmp_path / "judgements.yaml")
    assert closing_repos(facts, judgements) == set()
    assert live_repos(facts, judgements) == set()


def test_the_judgements_digest_is_of_the_bytes(tmp_path: Path) -> None:
    path = tmp_path / "judgements.yaml"
    assert judgements_digest(path) == judgements_digest(tmp_path / "missing.yaml")
    path.write_text("a: 1\n")
    first = judgements_digest(path)
    path.write_text("a: 1 \n")
    assert judgements_digest(path) != first


# ------------------------- close-out deadlines wake a quiet pass (2026-11-27-queue-followups R7)


def _landed(
    tmp_path: Path, *, merged_at: str | None, queued: bool = False
) -> tuple[object, object]:
    """REPO with batch b1 merged at *merged_at* and no close-out event; *queued*: a
    `queue_land` of REPO names it."""
    import yaml
    from fr.triage.model import Scope
    from fr.triage.scope_config import scope_id

    tmp_path.mkdir(parents=True, exist_ok=True)
    world = World()
    world.issues[1] = "closed"
    kw = {"merged_at": merged_at} if merged_at is not None else {}
    world.pr(101, "feat/batch-b1", [1], state="MERGED", **kw)
    path = (
        _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1"))) / "judgements.yaml"
    )
    if queued:
        text = path.read_text("utf-8").replace("schema: 3\n", "schema: 14\n")
        land = {"kind": "queue_land", "at": NOW.isoformat(), "main": "m" * 40,
                "entries": [{"batch": "b1"}]}  # fmt: skip
        queue = {"repo": REPO, "wave": None, "base": "m" * 40, "events": [land],
                 "scope": scope_id(Scope(kind="repo", target=REPO))}  # fmt: skip
        path.write_text(text + yaml.safe_dump({"queues": [queue]}), "utf-8")
    return world.facts(), load_judgements(path)


def test_deadline_repos_reads_a_repo_whose_closeout_fallback_passed(tmp_path: Path) -> None:
    from fr.triage.probe import deadline_repos

    merged = (NOW - timedelta(minutes=10, seconds=30)).isoformat()
    facts, judgements = _landed(tmp_path, merged_at=merged)
    assert deadline_repos(facts, judgements, NOW - timedelta(minutes=1), NOW) == {REPO}
    assert deadline_repos(facts, judgements, NOW - timedelta(seconds=20), NOW) == set()
    assert deadline_repos(facts, judgements, None, NOW) == {REPO}  # unknown: fail open


def test_deadline_repos_fails_open_on_no_merged_at_and_skips_queue_landed(tmp_path: Path) -> None:
    from fr.triage.probe import deadline_repos

    facts, judgements = _landed(tmp_path / "a", merged_at=None)
    assert deadline_repos(facts, judgements, NOW - timedelta(seconds=20), NOW) == {REPO}
    merged = (NOW - timedelta(minutes=10, seconds=30)).isoformat()
    facts, judgements = _landed(tmp_path / "b", merged_at=merged, queued=True)
    assert deadline_repos(facts, judgements, NOW - timedelta(minutes=1), NOW) == set()
    assert deadline_repos(facts, judgements, None, NOW) == set()


def test_a_quiet_pass_with_a_deadline_repo_reads_only_it() -> None:
    p = plan_pass(_FRESH, NOW, repos=["A", "B", "C"], changed=set(), digest="d",
                  below_floor=False, live={"A"}, pending={}, probes=3, deadline={"B"})  # fmt: skip
    assert (p.kind, p.only) == ("partial", frozenset({"B"}))
