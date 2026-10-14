"""The collected close-out engine (spec 2026-10-14-exit-gates R15, R16, §E).

`fr triage batch closeout` closes out every landed, ungated batch in ONE session and
ONE housekeeping PR. Per batch, in order: verify-merge, the Test Plan outcomes of a
passed gate (`--ran`, the gate-pass comment as evidence), `fr archive --branch <b>
--no-issues`, and the issues a passed gate's rows cite closed (never a narrowed one),
`fr:awaiting-live` removed. A batch whose archive holds is reset, named and never
recorded. The engine is driven here through a fake worktree and a fake forge: no git,
no `fr` process, no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pytest
from fr.triage.batch_closeout import (
    Member,
    closeout_title,
    collected_branch,
    execute,
    member_steps,
    next_collected,
    plan_lines,
    step_ranges,
)

REPO = "derio-net/super-fr"
DAY = date(2026, 10, 14)
BRANCH = "chore/closeout-2026-10-14-1"
EVIDENCE = "https://github.com/derio-net/super-fr/pull/101#issuecomment-55"


@dataclass
class FakeTree:
    """The scratch worktree: each `fr` call answers from *codes* (by the verb), every
    call recorded; commits and resets are recorded too."""

    codes: dict[tuple[str, str], int] = field(default_factory=dict)  # (verb, branch) -> code
    calls: list[list[str]] = field(default_factory=list)
    sha: int = 0
    resets: list[str] = field(default_factory=list)
    squashed: list[tuple[str, str]] = field(default_factory=list)
    pushed: list[str] = field(default_factory=list)
    changed: bool = True

    def head(self) -> str:
        return f"sha{self.sha}"

    def run_fr(self, args: list[str]) -> tuple[int, str]:
        self.calls.append(list(args))
        verb = args[0] if args[0] != "isolation" else "verify-merge"
        if args[0] == "closeout":
            verb = "outcome"
        branch = args[args.index("--branch") + 1] if "--branch" in args else ""
        code = self.codes.get((verb, branch), 0)
        if code == 0:
            self.sha += 1
        return code, "" if code == 0 else f"{verb} held for {branch}\nlast line of why"

    def reset_hard(self, sha: str) -> None:
        self.resets.append(sha)

    def squash_all(self, base: str, message: str) -> str | None:
        self.squashed.append((base, message))
        return "squashed" if self.changed else None

    def push(self, branch: str, *, force: bool = False) -> None:
        self.pushed.append(branch)


@dataclass
class FakeForge:
    created: list[dict[str, Any]] = field(default_factory=list)
    closed: list[tuple[str, int]] = field(default_factory=list)
    unlabelled: list[tuple[str, int, frozenset[str]]] = field(default_factory=list)

    def pr_create(self, repo: str, *, head: str, base: str, title: str, body: str) -> int:
        self.created.append({"repo": repo, "head": head, "base": base, "title": title,
                             "body": body})  # fmt: skip
        return 900

    def close_issue(self, repo: str, number: int, comment: str) -> None:
        self.closed.append((repo, number))

    def edit_issue_labels(
        self, repo: str, number: int, *, add: frozenset[str], remove: frozenset[str]
    ) -> None:
        self.unlabelled.append((repo, number, remove))


def _run(members: list[Member], tree: FakeTree, forge: FakeForge) -> tuple[Any, list[Any]]:
    recorded: list[tuple[str, str]] = []
    result = execute(
        members, tree=tree, forge=forge, repo=REPO, default="main", branch=BRANCH,
        record=lambda bid, branch: recorded.append((bid, branch)), say=lambda _l: None,
    )  # fmt: skip
    return result, recorded


PLAIN = Member(batch="a", branch="feat/batch-a", run="r-a")
GATED = Member(
    batch="g", branch="feat/batch-g", run="r-g", passed=("tester",), evidence=EVIDENCE,
    missing=(1, 2, 3, 5), closes=(f"{REPO}#7", f"{REPO}#8"),
)  # fmt: skip
DEBUG = Member(batch="d", branch="fix/batch-d", run=None)


# ------------------------------------------------------------------ naming


def test_the_collected_branch_names_its_day_and_number() -> None:
    assert collected_branch(DAY, 1) == BRANCH
    assert next_collected(["chore/closeout-2026-10-14-1", "chore/closeout-2026-10-14-3",
                           "chore/closeout-2026-10-13-9", "chore/archive-x"], DAY) == 4  # fmt: skip
    assert next_collected([], DAY) == 1


def test_step_ranges_fold_consecutive_numbers() -> None:
    assert step_ranges([1, 2, 3, 5]) == ["1-3", "5"]
    assert step_ranges([4]) == ["4"]
    assert step_ranges([]) == []


# ------------------------------------------------------------------- the steps


def test_a_plain_batch_runs_verify_merge_then_the_archive_with_no_issues() -> None:
    argv = [s.argv for s in member_steps(PLAIN)]
    assert argv == [
        ("isolation", "verify-merge", "--repo", ".", "--branch", "feat/batch-a"),
        ("archive", "--branch", "feat/batch-a", "--no-issues"),
    ]


def test_a_passed_gated_batch_records_its_missing_outcomes_as_ran_with_the_comment() -> None:
    steps = member_steps(GATED)
    outcomes = [s.argv for s in steps if s.kind == "outcome"]
    assert outcomes == [
        ("closeout", "outcome", "--run", "r-g", "--step", "1-3", "--ran", "--evidence", EVIDENCE),
        ("closeout", "outcome", "--run", "r-g", "--step", "5", "--ran", "--evidence", EVIDENCE),
    ]
    assert [s.kind for s in steps] == ["verify-merge", "outcome", "outcome", "archive",
                                       "close", "close"]  # fmt: skip


def test_an_ungated_batch_records_no_outcome_even_with_steps_missing() -> None:
    held = Member(batch="h", branch="feat/batch-h", run="r-h", missing=(1,))
    assert "outcome" not in [s.kind for s in member_steps(held)]


def test_a_debug_batch_with_no_run_still_closes_out() -> None:
    assert [s.kind for s in member_steps(DEBUG)] == ["verify-merge", "archive"]


def test_without_yes_the_plan_lists_each_batchs_steps() -> None:
    lines = plan_lines([PLAIN, GATED], BRANCH)
    text = "\n".join(lines)
    assert BRANCH in lines[0]
    assert "a: fr isolation verify-merge" in text
    assert "a: fr archive --branch feat/batch-a --no-issues" in text
    assert "g: fr closeout outcome --run r-g --step 1-3 --ran --evidence" in text
    assert f"g: close {REPO}#7" in text


# --------------------------------------------------------------------- execute


def test_one_commit_one_branch_one_pr_and_every_event_names_that_branch() -> None:
    tree, forge = FakeTree(), FakeForge()
    result, recorded = _run([PLAIN, GATED, DEBUG], tree, forge)

    assert len(tree.squashed) == 1 and tree.squashed[0][0] == "sha0"
    assert tree.pushed == [BRANCH]
    assert [c["head"] for c in forge.created] == [BRANCH]
    assert forge.created[0]["base"] == "main"
    assert forge.created[0]["title"] == closeout_title(BRANCH, ["a", "g", "d"])
    assert recorded == [("a", BRANCH), ("g", BRANCH), ("d", BRANCH)]
    assert result.pr == 900 and result.done == ("a", "g", "d") and result.held == ()


def test_only_the_passed_gates_issues_close_and_lose_awaiting_live() -> None:
    tree, forge = FakeTree(), FakeForge()
    _run([PLAIN, GATED], tree, forge)

    assert forge.closed == [(REPO, 7), (REPO, 8)]
    assert [(r, n) for r, n, _ in forge.unlabelled] == [(REPO, 7), (REPO, 8)]
    assert all(rm == frozenset({"fr:awaiting-live"}) for _, _, rm in forge.unlabelled)


def test_a_batch_whose_archive_holds_moves_nothing_and_gets_no_event() -> None:
    held = Member(batch="h", branch="feat/batch-h", run="r-h", missing=(1,))
    tree = FakeTree(codes={("archive", "feat/batch-h"): 2})
    forge = FakeForge()
    result, recorded = _run([PLAIN, held], tree, forge)

    assert tree.resets == ["sha2"]  # back to where h started: after a's two steps
    assert [b for b, _ in result.held] == ["h"]
    assert "last line of why" in result.held[0][1]
    assert recorded == [("a", BRANCH)]
    assert forge.closed == []


def test_an_unverified_merge_holds_the_batch() -> None:
    tree = FakeTree(codes={("verify-merge", "feat/batch-a"): 1})
    result, recorded = _run([PLAIN], tree, FakeForge())

    assert [b for b, _ in result.held] == ["a"] and recorded == []
    assert tree.pushed == [] and tree.squashed == []  # nothing left: no commit, no PR


def test_an_unresolvable_merged_branch_does_not_hold_the_batch() -> None:
    """verify-merge exits 2 when the merged branch is gone everywhere (deleted at
    merge): that disproves nothing, so the close-out goes on."""
    tree = FakeTree(codes={("verify-merge", "feat/batch-a"): 2})
    result, recorded = _run([PLAIN], tree, FakeForge())
    assert result.done == ("a",) and recorded == [("a", BRANCH)]


def test_every_batch_holding_opens_no_pr() -> None:
    tree = FakeTree(codes={("archive", "feat/batch-a"): 2})
    forge = FakeForge()
    result, recorded = _run([PLAIN], tree, forge)
    assert forge.created == [] and recorded == [] and result.pr is None


@pytest.mark.parametrize("narrowed", [f"{REPO}#8", "Derio-Net/Super-FR#8"])
def test_a_narrowed_issue_is_never_closed(narrowed: str) -> None:
    from fr.triage.batch_closeout import issues_to_close

    assert issues_to_close((f"{REPO}#7", f"{REPO}#8"), narrowed=[narrowed]) == (f"{REPO}#7",)


# --------------------------------------------- the default branch's read (ledger)


def _closeout_repo(tmp_path: Any) -> Any:
    """`_ledger_repo`, plus a Test Plan with step 1 recorded and a spec-journal decision
    narrowing #8."""
    from fr.journal.model import JournalEntry, append_journal_entry, journal_path

    from tests.unit.test_triage_exit_gates_drive import _git, _ledger_repo

    checkout = _ledger_repo(tmp_path, walked=True)
    clone = checkout.path
    _git(clone, "checkout", "--quiet", "--", ".")
    spec = clone / "docs/superpowers/specs/s.md"
    spec.write_text(spec.read_text() + "\n## Test Plan\n\n1. One.\n2. Two.\n3. Three.\n")
    journal = journal_path(clone, "spec", "s")
    for entry in (
        JournalEntry(kind="discovery", scope="spec", id="test-plan-step-1",
                     created="2026-10-14T00:00:00+00:00", title="Test Plan step 1: ran"),
        JournalEntry(kind="decision", scope="spec", id="narrow", gate="owner",
                     created="2026-10-14T00:00:00+00:00", title="narrowed",
                     narrows=("#8",)),
    ):  # fmt: skip
        append_journal_entry(journal, "s", entry)
    _git(clone, "add", ".")
    _git(clone, "commit", "--quiet", "-m", "test plan")
    _git(clone, "push", "--quiet", "origin", "HEAD:main")
    _git(clone, "fetch", "--quiet", "origin")
    return checkout


def test_the_closeout_read_names_the_run_missing_steps_rows_and_narrowed_issues(
    tmp_path: Any,
) -> None:
    from fr.triage.ledger import closeout_read

    read = closeout_read(_closeout_repo(tmp_path), "origin/main", "feat/batch-b1", REPO)

    assert read.run == "r1"
    assert read.missing == (2, 3)
    assert [r.id for r in read.rows] == ["r-live"]
    assert read.narrowed == (f"{REPO}#8",)


def test_a_branch_no_run_names_reads_no_run(tmp_path: Any) -> None:
    from fr.triage.ledger import closeout_read

    assert closeout_read(_closeout_repo(tmp_path), "origin/main", "fix/x", REPO).run is None
