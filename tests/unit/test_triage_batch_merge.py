"""`fr triage batch merge` (spec 2026-11-19-wave-merge-queue R22, R23; the order and the method
choice of 2026-09-25-triage-batches §3.F).

There is no second merge path: `batch merge` opens the wave merge queue for its named or
approved batches and drives it in the foreground, as the driver does, until they landed or
the queue stopped. The retired merge loop's own tests (updates, version re-slotting, the
strict-checks exemption) are gone with it; the queue's equivalents are in
`tests/unit/test_wave_queue_planner.py` and `tests/integration/`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd
from fr.ghclient import BaseRules
from fr.triage.batch import merge_order
from fr.triage.model import PullRequest, TriageConfig, load_judgements
from typer.testing import CliRunner

from tests.unit.test_triage_batch_dispatch import FakeRunner
from tests.unit.test_triage_batch_drive_cmd import (  # noqa: F401 - fixtures
    NOW,
    REPO,
    DriveCheckout,
    RecordingQueue,
    World,
    _batch,
    _dispatch_event,
    _queued,
    _recording_queue,
    _sandbox,
    _state,
    runner_fixture,
    world_fixture,
)


def _pr(n: int, bid: str, head: str, files: list[str]) -> PullRequest:
    return PullRequest(
        author="operator", cross_repo=False, repo=REPO, number=n, title=bid, state="OPEN",
        is_draft=False, url=f"https://github.com/{REPO}/pull/{n}", head_ref=f"feat/batch-{bid}",
        head_oid=head, files=files,
    )  # fmt: skip


def _merge(tmp_path: Path, *args: str) -> tuple[int, str]:
    result = CliRunner().invoke(
        app, ["triage", "batch", "merge", *args, "--repo", REPO, "--dir", str(tmp_path)]
    )
    return result.exit_code, result.output


@pytest.fixture(name="clone")
def clone_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, world: World, runner: FakeRunner
) -> DriveCheckout:
    """The drive tests' fake clone and forge, with the queue's executor recording what it
    is asked to do; `queue.ci: push` is declared unless a test says it is not."""
    fake = DriveCheckout(tmp_path / "clone", world)
    fake.path.mkdir()
    monkeypatch.setattr(triage_batch_cmd, "make_checkout", lambda path: fake)
    _recording_queue(monkeypatch, world)
    return fake


def _ready(world: World, tmp_path: Path, *ids: int) -> None:
    for i in ids:
        world.issues[i] = "open"
        world.pr(100 + i, f"feat/batch-b{i}", [i])
    _state(tmp_path, world, *(_batch(f"b{i}", i, events=_dispatch_event(f"b{i}")) for i in ids))


def _land_on_the_second_nap(
    monkeypatch: pytest.MonkeyPatch, world: World, *numbers: int
) -> list[float]:
    """The queue lands the PRs while `batch merge` waits: the forge reads them MERGED."""
    naps: list[float] = []

    def _nap(seconds: float) -> None:
        naps.append(seconds)
        if len(naps) == 2:
            for n in numbers:
                world.prs[n].update(state="MERGED", merged_at=NOW.isoformat())
        assert len(naps) < 6, "batch merge did not end"

    monkeypatch.setattr(triage_batch_cmd, "_sleep", _nap)
    return naps


# ------------------------------------------------------------------ the foreground queue (R23)


def test_batch_merge_drives_the_queue_in_the_foreground_until_the_batches_landed(
    tmp_path: Path, world: World, clone: DriveCheckout, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ready(world, tmp_path, 1, 2)
    naps = _land_on_the_second_nap(monkeypatch, world, 101, 102)
    code, out = _merge(tmp_path, "b1", "b2", "--yes")
    assert code == 0, out
    assert "queue-open" in out and "merged 2 batches" in out
    assert len(naps) >= 2  # it waited while the combinations ran
    assert not [c for c in world.calls if c.startswith("pr_merge")] and world.merged == []
    batches = load_judgements(tmp_path / "judgements.yaml").batches
    assert not [e for b in batches for e in b.events if e.kind in ("update", "enqueue")]


def test_batch_merge_without_yes_prints_the_queues_plan_and_writes_nothing(
    tmp_path: Path, world: World, clone: DriveCheckout
) -> None:
    _ready(world, tmp_path, 1)
    code, out = _merge(tmp_path)
    assert code == 0, out
    assert "queue-open" in out and "nothing done" in out
    assert world.queue_plans == [] and load_judgements(tmp_path / "judgements.yaml").queues == []


def test_batch_merge_acts_on_the_queue_alone_it_dispatches_and_closes_nothing(
    tmp_path: Path, world: World, clone: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _ready(world, tmp_path, 1)
    world.issues[9] = "open"
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")), _batch("b9", 9))
    _land_on_the_second_nap(monkeypatch, world, 101)
    code, out = _merge(tmp_path, "b1", "--yes")
    assert code == 0, out
    assert runner.dispatched == [] and "dispatch b9" not in out


def test_a_named_batch_without_the_approval_label_is_refused(
    tmp_path: Path, world: World, clone: DriveCheckout
) -> None:
    _ready(world, tmp_path, 1)
    world.prs[101]["labels"] = []
    code, out = _merge(tmp_path, "b1", "--yes")
    assert code == 2 and "not approved: b1" in out and "approved-fr" in out
    assert world.queue_plans == []


def test_a_named_batch_that_is_not_pr_open_is_refused(
    tmp_path: Path, world: World, clone: DriveCheckout
) -> None:
    _ready(world, tmp_path, 1)
    world.issues[2] = "open"
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")), _batch("b2", 2))
    code, out = _merge(tmp_path, "b2", "--yes")
    assert code == 2 and "not a pr-open batch here: b2" in out


def test_a_repo_whose_queue_is_held_stops_batch_merge_with_the_reason(
    tmp_path: Path, world: World, clone: DriveCheckout, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R22: a base that requires a forge merge queue holds the queue; there is no other way
    to merge, so `batch merge` stops and says what to change."""
    world.rules = BaseRules(merge_queue=True)  # type: ignore[attr-defined]
    _ready(world, tmp_path, 1)
    code, out = _merge(tmp_path, "b1", "--yes")
    assert code == 1, out
    assert "requires a forge merge queue" in out
    assert world.queue_plans == [] and world.merged == []


def test_a_repo_without_queue_ci_is_refused_with_what_to_add(
    tmp_path: Path, world: World, runner: FakeRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = DriveCheckout(tmp_path / "clone", world)
    fake.path.mkdir()
    monkeypatch.setattr(triage_batch_cmd, "make_checkout", lambda path: fake)
    RecordingQueue.world, RecordingQueue.script = world, {}
    monkeypatch.setattr(triage_batch_cmd, "QueueExecutor", RecordingQueue)
    _ready(world, tmp_path, 1)
    code, out = _merge(tmp_path, "b1", "--yes")
    assert code == 1, out
    assert "queue.ci" in out and "ci: push" in out
    assert world.queue_plans == []


def test_batch_merge_uses_the_method_it_is_given_or_the_repos_default(
    tmp_path: Path, world: World, clone: DriveCheckout
) -> None:
    _ready(world, tmp_path, 1)
    code, out = _merge(tmp_path, "b1", "--yes", "--method", "rebase")
    assert code == 2
    assert "rebase" in out and "squash" in out  # the repo allows squash only
    assert world.queue_plans == []


# ---------------------------------------- triage-claims: merge keeps hands off (R6, R7)


def _hold(tmp_path: Path, *issue_indexes: int) -> None:
    from fr.triage.model import load_facts

    from tests.unit.triage_claim_fixtures import FAR, OTHER, held, marker

    path = tmp_path / "facts.json"
    facts = load_facts(path)
    issues = [
        i.model_copy(update=held(marker(OTHER, "theirs", expires=FAR))) if n in issue_indexes else i
        for n, i in enumerate(facts.issues)
    ]
    path.write_text(json.dumps(facts.model_copy(update={"issues": issues}).to_json()), "utf-8")


def _ready_held(world: World, tmp_path: Path, *ids: int) -> None:
    _ready(world, tmp_path, *ids)
    (tmp_path / "facts.json").write_text(json.dumps(world.facts().to_json()), "utf-8")


def test_merge_refuses_a_batch_held_elsewhere(
    tmp_path: Path, world: World, clone: DriveCheckout
) -> None:
    from tests.unit.triage_claim_fixtures import OTHER

    _ready_held(world, tmp_path, 1)
    _hold(tmp_path, 0)
    code, out = _merge(tmp_path, "b1", "--yes")  # naming it: still a refusal (R7)
    assert code == 2 and "cannot be merged" in out and OTHER in out
    assert world.queue_plans == []


def test_merge_with_no_ids_skips_a_held_batch_and_queues_the_rest(
    tmp_path: Path, world: World, clone: DriveCheckout, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.triage_claim_fixtures import OTHER

    _ready_held(world, tmp_path, 1, 2)
    _hold(tmp_path, 0)
    _land_on_the_second_nap(monkeypatch, world, 102)
    code, out = _merge(tmp_path, "--yes")
    assert code == 0, out
    assert f"skipped b1: held by {OTHER}" in out
    assert _queued(world) == [] or "b1" not in _queued(world)


def test_merge_with_no_ids_says_nothing_to_merge_when_every_batch_is_held(
    tmp_path: Path, world: World, clone: DriveCheckout
) -> None:
    _ready_held(world, tmp_path, 1, 2)
    _hold(tmp_path, 0, 1)
    code, out = _merge(tmp_path, "--yes")
    assert code == 0, out
    assert "skipped b1: held by" in out and "skipped b2: held by" in out
    assert "nothing to merge" in out and world.queue_plans == []


# ------------------------------------------------------------------ one verdict rule


@pytest.mark.parametrize(
    ("required", "every", "ci_none"),
    [
        ([{"name": "test", "bucket": "pass"}], None, False),
        ([{"name": "test", "bucket": "fail"}], None, False),
        ([{"name": "test", "bucket": "pending"}], None, False),
        ([], [{"name": "lint", "bucket": "fail"}, {"name": "x", "bucket": "pass"}], False),
        ([], [], False),
        ([{"name": "test", "bucket": "fail"}], None, True),
    ],
)
def test_pr_checks_verdict_matches_live_checks(
    tmp_path: Path, required: list[dict[str, Any]], every: Any, ci_none: bool
) -> None:
    """`pr_checks_verdict` holds the rule `live_checks` judges by: the driver reads a PR the
    facts do not hold through it, with no MergeContext to hand."""
    from fr.triage.batch_merge import MergeContext, live_checks, pr_checks_verdict

    class Forge:
        def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
            return required

        def pr_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
            return every or []

    ctx = MergeContext(
        client=Forge(),  # type: ignore[arg-type]
        checkout=None,  # type: ignore[arg-type]
        repo="derio-net/super-fr", version=None, method="squash",
        say=lambda line: None, ci_none=ci_none,
    )  # fmt: skip
    direct = pr_checks_verdict(Forge(), "derio-net/super-fr", 7, ci_none=ci_none)  # type: ignore[arg-type]
    assert direct == live_checks(ctx, 7)


# ------------------------------------------------------------------ order (§3.F)


def _entry(bid: str, files: list[str], *, order: int | None = None, tier: int = 2) -> Any:
    from fr.triage.batch import QueueEntry
    from fr.triage.model import Batch

    batch = Batch.model_validate({"id": bid, "title": bid, "ids": ["super-fr#1"], "order": order})
    return QueueEntry(batch=batch, pr=_pr(1, bid, "h", files), tier=tier)


def test_explicit_order_is_a_hard_constraint() -> None:
    entries = [
        _entry("zeta", ["a.py"], order=1),
        _entry("alpha", ["b.py"]),
        _entry("mid", ["a.py", "c.py"], order=2),
    ]
    assert [e.batch.id for e in merge_order(entries)] == ["zeta", "mid", "alpha"]


def test_overlapping_batches_are_not_adjacent_when_avoidable() -> None:
    entries = [_entry("a", ["x.py"]), _entry("b", ["x.py"]), _entry("c", ["y.py"])]
    order = [e.batch.id for e in merge_order(entries)]
    assert order == ["a", "c", "b"]


def test_ties_break_on_fewest_overlaps_then_lowest_tier_then_id() -> None:
    entries = [
        _entry("d", ["p.py"], tier=2),
        _entry("c", ["q.py"], tier=1),
        _entry("b", ["r.py"], tier=2),
        _entry("a", ["p.py"], tier=1),
    ]
    # a and d share p.py (1 overlap each) -> they go after b, c, which have none;
    # c before b on tier; a before d on tier; a and d are kept apart where possible.
    assert [e.batch.id for e in merge_order(entries)] == ["c", "a", "b", "d"]


def test_the_order_is_deterministic() -> None:
    entries = [_entry(x, ["f.py"]) for x in "edcba"]
    once = [e.batch.id for e in merge_order(entries)]
    assert once == [e.batch.id for e in merge_order(list(reversed(entries)))]


def test_the_config_takes_an_optional_merge_method() -> None:
    assert TriageConfig().merge_method is None
    assert TriageConfig.model_validate({"merge_method": "rebase"}).merge_method == "rebase"
    with pytest.raises(ValueError, match="merge_method"):
        TriageConfig.model_validate({"merge_method": "fast-forward"})


@pytest.mark.parametrize(
    ("methods", "configured", "want"),
    [
        ({"default": None, "allowed": ["merge", "squash"]}, "squash", "squash"),
        ({"default": None, "allowed": ["merge", "rebase", "squash"]}, "rebase", "rebase"),
        # The forge's own default still wins where it names one.
        ({"default": "merge", "allowed": ["merge", "squash"]}, "squash", "merge"),
        # One allowed method needs no setting.
        ({"default": None, "allowed": ["squash"]}, None, "squash"),
    ],
)
def test_choose_method_uses_the_configured_method_when_the_forge_names_none(
    methods: dict[str, Any], configured: str | None, want: str
) -> None:
    from fr.triage.batch_merge import choose_method

    assert choose_method(None, methods, configured=configured) == want


def test_choose_method_refuses_a_configured_method_the_repo_disallows() -> None:
    from fr.triage.batch_merge import choose_method
    from fr.triage.errors import TriageError

    with pytest.raises(TriageError, match=r"merge_method: rebase.*\.fr/triage\.yaml"):
        choose_method(None, {"default": None, "allowed": ["merge", "squash"]}, configured="rebase")


def test_several_allowed_and_no_default_names_the_config_key_and_the_flag() -> None:
    from fr.triage.batch_merge import choose_method
    from fr.triage.errors import TriageError

    with pytest.raises(TriageError) as exc:
        choose_method(None, {"default": None, "allowed": ["merge", "squash"]})
    assert "--method" in str(exc.value)
    assert "merge_method" in str(exc.value) and ".fr/triage.yaml" in str(exc.value)
