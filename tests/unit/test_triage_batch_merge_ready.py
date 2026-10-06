"""`merge_ready`: `merge_one` without the wait (wave-driver spec §B, R4).

Built on the fakes of `test_triage_batch_merge` (an in-memory forge and clone).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from fr.triage.batch import pr_open_queue
from fr.triage.batch_merge import (
    HeadMovedError,
    MergeAttempt,
    MergeContext,
    MergeStopError,
    merge_one,
    merge_ready,
    plan_queue,
    routine_commit,
)
from fr.triage.batch_version import only_versions_bumped
from fr.triage.model import load_facts, load_judgements

from tests.unit.test_triage_batch_merge import REPO, FakeCheckout, MergeForge, _setup


def _ctx(tmp_path: Path, forge: MergeForge, checkout: FakeCheckout) -> tuple[MergeContext, list]:
    facts = load_facts(tmp_path / "facts.json")
    judgements = load_judgements(tmp_path / "judgements.yaml")
    ctx = MergeContext(
        client=forge,  # type: ignore[arg-type]
        checkout=checkout,  # type: ignore[arg-type]
        repo=REPO,
        version=facts.config_for(REPO).version,
        scratch_root=tmp_path / "merge",
        method="squash",
        say=lambda line: None,
    )
    queue = pr_open_queue(judgements.batches, facts, judgements.issues)
    slots, _ = plan_queue(ctx, queue)
    return ctx, slots


def _solo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[MergeForge, FakeCheckout]:
    return _setup(tmp_path, monkeypatch, [("solo", 1, None, "minor", "4.22.0", ["a.py"])])


def test_a_ready_pr_merges_without_waiting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    assert merge_ready(ctx, slot, None) == MergeAttempt("merged", head="head-solo")
    assert forge.merged == [(1001, "head-solo", "squash")]
    assert forge.waits == []


def test_a_draft_is_reported_and_never_merged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    forge.prs[1001]["draft"] = True
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    assert merge_ready(ctx, slot, None).outcome == "draft"
    assert forge.merged == []


def test_pending_checks_are_reported_without_waiting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    forge.checks[1001] = [{"name": "test", "bucket": "pending"}]
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    got = merge_ready(ctx, slot, None)
    assert (got.outcome, got.checks) == ("pending", ("test",))
    assert forge.merged == [] and forge.waits == []


def test_failing_checks_are_named(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    forge.checks[1001] = [{"name": "lint", "bucket": "fail"}, {"name": "test", "bucket": "pass"}]
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    got = merge_ready(ctx, slot, None)
    assert (got.outcome, got.checks) == ("failing", ("lint",))
    assert forge.merged == []


def test_an_already_merged_pr_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    forge.prs[1001]["state"] = "MERGED"
    assert merge_ready(ctx, slot, None).outcome == "already-merged"


def test_a_moved_head_stops(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    forge.prs[1001]["head_oid"] = "elsewhere"
    with pytest.raises(MergeStopError, match="head moved"):
        merge_ready(ctx, slot, None)


def test_a_moved_head_is_told_from_a_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The driver stops a train on a moved head and steps over a refusal (R3, R4)."""
    forge, checkout = _solo(tmp_path, monkeypatch)
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    forge.prs[1001]["head_oid"] = "elsewhere"
    with pytest.raises(HeadMovedError):
        merge_ready(ctx, slot, None)
    assert issubclass(HeadMovedError, MergeStopError)


def test_a_pr_behind_its_base_is_updated_and_left_for_a_later_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    checkout.up_to_date.discard("head-solo")
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    got = merge_ready(ctx, slot, None)
    assert got.outcome == "updated"
    assert forge.merged == [] and forge.waits == []


def test_a_merge_emits_exactly_one_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    lines: list[str] = []
    ctx = dataclasses.replace(ctx, say=lines.append)
    assert merge_ready(ctx, slot, None).outcome == "merged"
    assert len(lines) == 1 and lines[0].startswith("merged PR #")


# ------------------------------------------- routine commits on main (gh#927)
#
# Every driver merge moves main twice — the merge, then its `release:` commit —
# and close-out/archive merges move it again. A PR behind ONLY by such commits
# merges as it is: updating it would buy a CI run that proves nothing new.
# Classified by the files a commit changes, never by its subject line.

RELEASE = ("rel", (("M", "pyproject.toml"), ("M", "uv.lock"), ("D", ".changes/feat-x.yaml")))
ARCHIVE = (
    "arc",
    (
        ("D", "docs/superpowers/plans/2026-10-03-x/_meta.yaml"),
        ("A", "docs/superpowers/implemented/plans/2026-10-03-x/_meta.yaml"),
    ),
)
CODE = ("code", (("M", "packages/fr/src/fr/cli.py"),))


def _unversioned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[MergeForge, FakeCheckout]:
    """A repo like this one: no `version:` block, releases cut on main."""
    forge, checkout = _setup(
        tmp_path, monkeypatch, [("solo", 1, None, "minor", "4.22.0", ["a.py"])], config=None
    )
    checkout.up_to_date.discard("head-solo")
    checkout.files.update(
        {
            ("rel^", "pyproject.toml"): '[project]\nname = "x"\nversion = "5.2.4"\n',
            ("rel", "pyproject.toml"): '[project]\nname = "x"\nversion = "5.2.5"\n',
            ("rel^", "uv.lock"): '[[package]]\nname = "x"\nversion = "5.2.4"\nsource = 1\n',
            ("rel", "uv.lock"): '[[package]]\nname = "x"\nversion = "5.2.5"\nsource = 1\n',
        }
    )
    return forge, checkout


def test_a_pr_behind_only_by_a_release_commit_merges_in_the_same_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _unversioned(tmp_path, monkeypatch)
    checkout.base_commits["head-solo"] = (RELEASE,)
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    assert merge_ready(ctx, slot, None) == MergeAttempt("merged", head="head-solo")
    assert forge.merged == [(1001, "head-solo", "squash")]
    assert checkout.worktrees == []  # no update was even started


def test_a_pr_behind_only_by_an_archive_merge_merges_in_the_same_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _unversioned(tmp_path, monkeypatch)
    checkout.base_commits["head-solo"] = (ARCHIVE, RELEASE)
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    assert merge_ready(ctx, slot, None).outcome == "merged"


@pytest.mark.parametrize("routine", [RELEASE, ARCHIVE], ids=["release", "archive"])
def test_a_routine_commit_plus_any_other_commit_still_updates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, routine: tuple
) -> None:
    forge, checkout = _unversioned(tmp_path, monkeypatch)
    checkout.base_commits["head-solo"] = (routine, CODE)
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    assert merge_ready(ctx, slot, None).outcome == "updated"
    assert forge.merged == []


def test_a_release_shaped_commit_that_changes_more_than_versions_still_updates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Subject lines are not trusted: a `release:` commit that also adds a
    dependency is a real change to what the PR's CI ran against."""
    forge, checkout = _unversioned(tmp_path, monkeypatch)
    checkout.files[("rel", "pyproject.toml")] = (
        '[project]\nname = "x"\nversion = "5.2.5"\ndependencies = ["y"]\n'
    )
    checkout.base_commits["head-solo"] = (RELEASE,)
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    assert merge_ready(ctx, slot, None).outcome == "updated"


def test_a_routine_commit_touching_a_file_the_pr_changed_still_updates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The PR's own change to that file never ran against main's version of it,
    and merging blind could conflict at the forge."""
    forge, checkout = _unversioned(tmp_path, monkeypatch)
    checkout.base_commits["head-solo"] = (ARCHIVE,)
    checkout.pr_paths["head-solo"] = frozenset({"docs/superpowers/plans/2026-10-03-x/_meta.yaml"})
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    assert merge_ready(ctx, slot, None).outcome == "updated"


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ((("M", "docs/superpowers/journals/debug/x.md"),), True),
        ((("D", ".changes/fix-x.yaml"), ("M", "pyproject.toml")), True),
        # Review: a version-shaped edit that consumes no fragment is not a release —
        # a pinned tool in a workflow, a constant in source.
        ((("M", ".github/workflows/ci.yml"),), False),
        ((("M", "pyproject.toml"),), False),
        ((("D", ".changes/fix-x.yaml"),), False),  # deletes a fragment, bumps nothing
        ((("D", ".changes/fix-x.yaml"), ("M", "run.sh")), False),  # a mode-only change
        ((("A", ".changes/fix-x.yaml"), ("M", "pyproject.toml")), False),  # adds one
        ((("M", "docs/acceptance/matrix.yaml"),), False),
        ((), False),  # nothing knowable is not routine
    ],
)
def test_routine_commit_classifies_by_files(changes: tuple, expected: bool) -> None:
    files = {
        ("rel^", "pyproject.toml"): 'version = "1.0.0"\n',
        ("rel", "pyproject.toml"): 'version = "1.0.1"\n',
        ("rel^", ".github/workflows/ci.yml"): 'uv: "0.5.1"\n',
        ("rel", ".github/workflows/ci.yml"): 'uv: "0.5.2"\n',
        ("rel^", "run.sh"): "echo\n",
        ("rel", "run.sh"): "echo\n",
    }
    assert routine_commit(changes, lambda ref, path: files.get((ref, path)), "rel") is expected


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        ('version = "5.2.4"\n', 'version = "5.2.5"\n', True),
        ('{\n  "version": "5.2.4"\n}\n', '{\n  "version": "5.2.5"\n}\n', True),
        ('version = "5.2.4"\n', 'version = "5.2.4"\n', False),  # no change at all
        ('version = "5.2.5"\n', 'version = "5.2.4"\n', False),  # a downgrade
        ('version = "5.2.4"\n', 'version = "5.2.5"\nnew = 1\n', False),
        ('dep = "a>=5.2.4"\n', 'dep = "a>=5.2.5"\n', False),  # a pin, not a version
        ('a = "1.0.0"\nb = "2.0.0"\n', 'a = "1.0.1"\nb = "2.0.1"\n', False),  # two bumps
    ],
)
def test_only_versions_bumped(before: str, after: str, expected: bool) -> None:
    assert only_versions_bumped([(before, after)]) is expected


# ------------------------------------------- R4 in merge_ready itself (gh#880)
#
# The required checks when the branch has any, else every check; nothing
# reported is pending, and only a `ci none` repo merges without a check. The
# rule is `batch_drive.checks_verdict`'s, applied by every caller of merge_ready,
# not only by the driver pass in front of it.


def _no_required(forge: MergeForge, every: list[dict[str, str]]) -> None:
    forge.checks[1001] = []
    forge.all_checks[1001] = every


@pytest.mark.parametrize(
    ("every", "outcome", "named"),
    [
        ([{"name": "lint", "bucket": "fail"}], "failing", ("1 failing check(s)",)),
        ([{"name": "lint", "bucket": "pending"}], "pending", ("1 pending check(s)",)),
        ([], "pending", ("no check reported yet",)),
    ],
    ids=["failing", "pending", "nothing-reported"],
)
def test_with_no_required_checks_every_check_gates_the_merge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    every: list[dict[str, str]],
    outcome: str,
    named: tuple[str, ...],
) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    _no_required(forge, every)
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    got = merge_ready(ctx, slot, None)
    assert (got.outcome, got.checks) == (outcome, named)
    assert forge.merged == []


def test_with_no_required_checks_green_checks_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    _no_required(forge, [{"name": "lint", "bucket": "pass"}])
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    assert merge_ready(ctx, slot, None).outcome == "merged"


def test_a_ci_none_repo_merges_with_no_check_at_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    _no_required(forge, [])
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    ctx = dataclasses.replace(ctx, ci_none=True)
    assert merge_ready(ctx, slot, None).outcome == "merged"


# ------------------------------- batch merge's wait after an update push (gh#947)


def _after_push(forge: MergeForge, answers: list[list[dict[str, str]]]) -> None:
    """Pass before the push; after it (the head is `new-1`), each read of every
    check takes the next answer, the last one repeating. No check is required."""
    left = list(answers)

    def every(repo: str, number: int) -> list[dict[str, str]]:
        if forge.prs[number]["head_oid"] != "new-1":
            return [{"name": "test", "bucket": "pass"}]
        return list(left.pop(0) if len(left) > 1 else left[0])

    forge.pr_required_checks = lambda repo, number: []  # type: ignore[method-assign]
    forge.pr_checks = every  # type: ignore[method-assign]


def test_after_an_update_push_no_check_yet_is_waited_for_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    checkout.up_to_date.discard("head-solo")
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    _after_push(forge, [[], [], [{"name": "test", "bucket": "pass"}]])
    slept: list[float] = []
    ctx = dataclasses.replace(ctx, interval=5.0, timeout=60.0, sleep=slept.append)

    merge_one(ctx, slot, None)

    assert forge.merged == [(1001, "new-1", "squash")]
    assert slept == [5.0, 5.0]


def test_a_head_whose_checks_never_appear_is_not_merged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing reported is pending, however long it lasts: only `ci none` merges a
    head with no check (R4), never a grace period running out."""
    forge, checkout = _solo(tmp_path, monkeypatch)
    checkout.up_to_date.discard("head-solo")
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    _after_push(forge, [[]])
    slept: list[float] = []
    ctx = dataclasses.replace(ctx, interval=10.0, timeout=25.0, sleep=slept.append)

    with pytest.raises(MergeStopError, match="pending: no check reported yet"):
        merge_one(ctx, slot, None)
    assert forge.merged == []
    assert slept == [10.0, 10.0]
