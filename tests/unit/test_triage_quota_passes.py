# ruff: noqa: F811 - pytest fixtures imported from the sibling test modules
"""Quiet, partial and essential-only passes in the drive (spec 2026-10-12-quota-pacing
§B, §C; R7, R9, R10, R13).

The looping drive runs for real over the `World` of `test_triage_batch_drive_cmd`: its
probes answer from a `FakeForge` probe table, its `/rate_limit` from a `Meter`, and its
collect is a fake that records what it was asked to read, writes the world's facts, and
calls the pacing write back as `collect_into` does.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd
from fr.triage import pacing_state
from fr.triage.model import FACTS_SCHEMA, Scope
from fr.triage.pacing_state import PacingState
from fr.triage.probe import QUOTA_HOLD, checks_probes, issues_probe, judgements_digest
from typer.testing import CliRunner

from tests.unit.test_triage_batch_drive_cmd import (  # noqa: F401 - fixtures
    NOW,
    REPO,
    DriveCheckout,
    World,
    _batch,
    _dispatch_event,
    _sandbox,
    _state,
    checkout_fixture,
    runner_fixture,
    world_fixture,
)
from tests.unit.test_triage_driver_pass import (  # noqa: F401 - fixtures
    Runners,
    _pass,
    _workspace,
    clock,
    remote,
    runners,
    visibility,
)
from tests.unit.test_triage_driver_pass import _world as _cloud_world
from tests.unit.test_triage_quota_loop import Meter
from tests.unit.triage_fixtures import FakeForge, rate_limit_answer

OTHER = "derio-net/other"
PROBES = (issues_probe(REPO), *checks_probes(REPO, "sha-101"))
SUMMARY = {"in_flight": 1, "merged": 0, "pending": 0, "closing": 0, "blocked": 0}
LOW = rate_limit_answer(graphql=500)  # 10%: below the default 20% floor


class Rig:
    """What one looping drive did: the collects it asked for, boards, naps, lease takes."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, world: World, meter: Meter) -> None:
        self.world = world
        self.collects: list[frozenset[str] | None] = []
        self.boards = 0
        self.leases = 0
        self.naps: list[float] = []
        self.stop_after = 1
        self.clock = [NOW]
        self.forge = FakeForge(issues={}, prs={})
        self.scope_args = ["--repo", REPO]
        self.reshape: Any = lambda facts: facts
        self.fail_after_write: list[str] = []  # each collect pops one: raised after the write
        monkeypatch.setattr(triage_batch_cmd, "_pace_forge", lambda: meter)
        monkeypatch.setattr(triage_batch_cmd, "_probe_forge", lambda: self.forge)
        monkeypatch.setattr(triage_batch_cmd, "_now", lambda: self.clock[0])
        monkeypatch.setattr(triage_batch_cmd, "recollect", self.recollect)
        monkeypatch.setattr(triage_batch_cmd, "_sleep", self.nap)
        monkeypatch.setattr(triage_batch_cmd._Driver, "_write_board", lambda d: self.board())
        real_take = triage_batch_cmd._Driver.take_lease

        def take(driver: Any) -> None:
            self.leases += 1
            real_take(driver)

        monkeypatch.setattr(triage_batch_cmd._Driver, "take_lease", take)

    def recollect(self, scope: Any, target: Path, **kw: Any) -> dict[str, Any]:
        only = kw.get("only")
        self.collects.append(only)
        facts = self.reshape(self.world.facts())
        (target / "facts.json").write_text(json.dumps(facts.to_json()), "utf-8")
        if kw.get("after_write") is not None:
            carried = frozenset(r for r in facts.repos if only is not None and r not in only)
            kw["after_write"](facts, carried)
        if self.fail_after_write:
            raise triage_batch_cmd.ForgeReadError(self.fail_after_write.pop(0), code=2)
        return {}

    def board(self) -> None:
        self.boards += 1

    def nap(self, seconds: float) -> None:
        self.naps.append(seconds)
        self.clock[0] += timedelta(seconds=seconds)
        if len(self.naps) >= self.stop_after:
            raise KeyboardInterrupt

    def drive(self, state: Path) -> tuple[int, str]:
        result = CliRunner().invoke(
            app, ["triage", "batch", "drive", "--yes", *self.scope_args, "--dir", str(state)]
        )
        return result.exit_code, result.output


def _pr_open(world: World, tmp_path: Path) -> None:
    world.issues[1] = "open"
    world.pr(101, "feat/batch-b1", [1])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")))


def _settled(tmp_path: Path, rig: Rig, *, digest: str | None = None) -> None:
    """pacing.json as a planned pass left it a minute ago, every probe's ETag current."""
    rig.forge.probe_etags = {p: f"E-{i}" for i, p in enumerate(PROBES)}
    pacing_state.save(
        tmp_path,
        PacingState(
            etags={REPO: dict(rig.forge.probe_etags)},
            full_at=NOW - timedelta(minutes=1),
            judgements_digest=digest or judgements_digest(tmp_path / "judgements.yaml"),
            summary=SUMMARY,
        ),
    )


def test_a_quiet_pass_reads_nothing_plans_nothing_and_renews_the_lease(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: Any, monkeypatch: Any
) -> None:
    _pr_open(world, tmp_path)
    rig = Rig(monkeypatch, world, Meter())
    _settled(tmp_path, rig)

    code, out = rig.drive(tmp_path)

    assert rig.collects == [], "no collect: no list_issues, list_prs or anything else"
    assert "pr_view 101" not in world.calls and world.merged == []
    assert rig.boards == 0
    assert rig.leases == 1, "the lease is still taken every pass"
    assert "quiet: 3 probes unchanged" in out, out
    assert all(etag is not None for _, etag in rig.forge.probe_calls), "conditional probes"
    assert code != 3 and rig.naps == [120]


def test_an_edited_judgements_file_is_never_quiet_and_a_carried_repo_reads_nothing_live(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: Any, monkeypatch: Any
) -> None:
    """R9: the edit forces a planned pass; R10: the unchanged repo is carried, so its
    pr-open batch gets no live read and no merge, and is never reported unread."""
    _pr_open(world, tmp_path)
    rig = Rig(monkeypatch, world, Meter())
    _settled(tmp_path, rig, digest="the judgements of another pass")

    code, out = rig.drive(tmp_path)

    assert "quiet:" not in out
    assert rig.collects == [frozenset()], "nothing changed on the forge: nothing read"
    assert "pr_view 101" not in world.calls and world.merged == []
    assert not [line for line in out.splitlines() if line.startswith("merge ")]
    assert "was not read this pass" not in out
    assert rig.boards == 1
    assert pacing_state.load(tmp_path)[0].judgements_digest == judgements_digest(
        tmp_path / "judgements.yaml"
    )


def test_a_changed_repo_is_collected_and_acted_on(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: Any, monkeypatch: Any
) -> None:
    _pr_open(world, tmp_path)
    rig = Rig(monkeypatch, world, Meter())
    _settled(tmp_path, rig)
    rig.forge.probe_etags[issues_probe(REPO)] = "E-new"  # someone commented

    code, out = rig.drive(tmp_path)

    assert rig.collects == [None], "the scope's one repo changed: it is read"
    assert world.merged == [(101, "sha-101", "squash")], out
    stored = pacing_state.load(tmp_path)[0]
    assert stored.etags[REPO][issues_probe(REPO)] == "E-new", "promoted after the facts"


def _proposed(world: World, tmp_path: Path) -> None:
    world.issues[2] = "open"
    _state(tmp_path, world, _batch("b2", 2))


def test_below_the_floor_nothing_is_dispatched_and_the_drive_keeps_going(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: Any, monkeypatch: Any
) -> None:
    """R7, §C: an essential-only pass holds each dispatch as pending (never stalled, so no
    exit 3), skips the board, logs the quota line and waits four intervals."""
    _proposed(world, tmp_path)
    rig = Rig(monkeypatch, world, Meter(LOW))

    code, out = rig.drive(tmp_path)
    flat = " ".join(out.split())

    assert runner.dispatched == []
    assert f"held b2: {QUOTA_HOLD}" in out, out
    assert "pending 1" in flat
    assert "below floor 20%: essential-only pass, dispatch held, next pass in 8m" in flat
    assert code != 3, "a below-floor pass never ends the drive as stalled"
    assert rig.naps == [4 * 120]
    assert rig.boards == 0
    assert "re-run with --yes" not in out, "an essential pass with --yes acted (p2-r4)"
    assert pacing_state.load(tmp_path)[0].next_pass_at == NOW + timedelta(seconds=480)


def test_dispatch_resumes_once_the_budget_is_back_above_the_floor(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: Any, monkeypatch: Any
) -> None:
    """p2-r3: a recent full pass on record and nothing changed since the held pass: the
    pass back above the floor is still planned (never quiet), so the held dispatch goes."""
    _proposed(world, tmp_path)
    rig = Rig(monkeypatch, world, Meter(LOW, rate_limit_answer()))
    rig.stop_after = 2
    rig.forge.probe_etags = {issues_probe(REPO): "E-0"}
    pacing_state.save(
        tmp_path,
        PacingState(
            etags={REPO: {issues_probe(REPO): "E-0"}},
            full_at=NOW - timedelta(minutes=1),
            judgements_digest="the judgements of another pass",  # the held pass plans
            summary=SUMMARY,
        ),
    )

    code, out = rig.drive(tmp_path)

    assert f"held b2: {QUOTA_HOLD}" in out, out
    assert "quiet:" not in out, out
    assert len(runner.dispatched) == 1 and "b2" in runner.dispatched[0].id
    assert rig.naps[0] == 480
    assert pacing_state.load(tmp_path)[0].held_for_quota is False


def test_below_the_floor_a_forced_full_pass_reads_only_the_live_batch_repos(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: Any, monkeypatch: Any
) -> None:
    """R7, R11: no full pass for 15 minutes, but below the floor only the repos with a live
    batch are read; the rest are carried and their probes still go unconditionally."""
    _pr_open(world, tmp_path)
    group = Scope.group([REPO, OTHER])

    def grouped(facts: Any) -> Any:
        return facts.model_copy(
            update={"schema_": FACTS_SCHEMA, "scope": group.name, "kind": "group",
                    "repos": [OTHER, REPO]}
        )  # fmt: skip

    (tmp_path / "facts.json").write_text(json.dumps(grouped(world.facts()).to_json()), "utf-8")
    rig = Rig(monkeypatch, world, Meter(LOW))
    rig.scope_args = ["--repo", f"{REPO},{OTHER}", "--checkout", f"{REPO}={checkout.path}",
                      "--checkout", f"{OTHER}={checkout.path}"]  # fmt: skip
    rig.reshape = grouped

    code, out = rig.drive(tmp_path)

    assert rig.collects == [frozenset({REPO})], out
    assert "below floor 20%: essential-only pass" in " ".join(out.split())
    assert (issues_probe(OTHER), None) in rig.forge.probe_calls, "a full pass's probes"
    assert not [c for c in world.calls if OTHER in c], "no live read for the carried repo"


def test_the_cloud_pass_below_the_floor_is_the_same_essential_only_pass(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    remote: Path,
    visibility: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§E: the cloud pass runs the host's `run_pass`: the live batch merges, the proposed
    ones are held, and the next wake is stretched to four intervals."""
    _, state = _workspace(tmp_path, "a")
    _cloud_world(world, state)
    (state / "scope-durable.yaml").write_text(f"state_repo: {REPO}\n")
    monkeypatch.setattr(triage_batch_cmd, "_pace_forge", lambda: Meter(LOW))

    result = _pass(state, tmp_path / "outbox.json")
    flat = " ".join(result.output.split())

    assert world.merged and world.merged[0][0] == 103, result.output
    assert f"held b1: {QUOTA_HOLD}" in result.output and f"held b2: {QUOTA_HOLD}" in result.output
    assert "essential-only pass, dispatch held" in flat
    assert pacing_state.load(state)[0].next_pass_at is not None


def test_a_pass_that_fails_after_writing_its_facts_is_never_followed_by_a_quiet_one(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: Any, monkeypatch: Any
) -> None:
    """p2-r1: the collect wrote facts.json (and moved the ETags) and then the pass hit a
    rate limit before it planned; the next pass sees 304s and the same judgements, but
    the failed pass's plan is still owed, so it plans rather than going quiet."""
    _pr_open(world, tmp_path)
    rig = Rig(monkeypatch, world, Meter())
    _settled(tmp_path, rig)
    rig.forge.probe_etags[issues_probe(REPO)] = "E-new"  # pass 1 has something to read
    rig.fail_after_write = ["API rate limit exceeded for user ID 1"]
    rig.stop_after = 2

    code, out = rig.drive(tmp_path)

    assert "quiet:" not in out, out
    assert len(rig.collects) == 2, "the pass after the failed one collects and plans"
    assert rig.collects[1] is None, "and carries nothing: its merges are not deferred"
    assert "merge b1: merged PR #101" in out, "and plans the merge the failed pass owed"


def test_a_paced_drive_with_no_previous_facts_below_the_floor_reads_and_merges(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: Any, monkeypatch: Any
) -> None:
    """p2-r5: no facts.json to carry from: the essential pass reads every repo, so a
    ready batch still merges and the repo's ETags are stored."""
    _pr_open(world, tmp_path)
    (tmp_path / "facts.json").unlink()
    rig = Rig(monkeypatch, world, Meter(LOW))
    rig.forge.probe_etags = {issues_probe(REPO): "E-0"}

    code, out = rig.drive(tmp_path)

    assert rig.collects == [None], out
    assert world.merged == [(101, "sha-101", "squash")], out
    assert pacing_state.load(tmp_path)[0].etags[REPO] == {issues_probe(REPO): "E-0"}


def test_a_carried_repo_s_batch_claims_its_members_before_it_dispatches(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: Any, monkeypatch: Any
) -> None:
    """p2-r6: a carried repo's issues and claim comments are current (its probes said
    unchanged), so the claims its dispatch owes are planned from the carried facts."""
    _proposed(world, tmp_path)
    rig = Rig(monkeypatch, world, Meter())
    rig.forge.probe_etags = {issues_probe(REPO): "E-0"}
    pacing_state.save(
        tmp_path,
        PacingState(
            etags={REPO: {issues_probe(REPO): "E-0"}},
            full_at=NOW - timedelta(minutes=1),
            judgements_digest="the judgements of another pass",
            summary=SUMMARY,
        ),
    )

    code, out = rig.drive(tmp_path)

    assert rig.collects == [frozenset()], "the repo is carried"
    assert len(runner.dispatched) == 1, out
    assert "claim super-fr#2 (b2): posted" in out, out
    assert out.index("claim super-fr#2") < out.index("dispatch b2")
