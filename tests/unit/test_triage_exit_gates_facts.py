"""Exit-gates facts (spec 2026-10-14-exit-gates §D "Facts", R13, R18).

`collect` reads the labels of each unfinished batch's merged PR (the gate ledger) and,
through a reader the command layer builds on `gitseam`, the run cursor's position at an
open batch PR's head. Together with `TriageConfig.exit` this moves `FACTS_SCHEMA`.
The forge is faked; the cursor reader runs against a throwaway git repo.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fr.triage.collect import collect_facts
from fr.triage.cursor import cursor_position, read_cursor
from fr.triage.gitseam import Checkout
from fr.triage.model import (
    FACTS_READS,
    FACTS_SCHEMA,
    CursorPosition,
    PullRequest,
    Scope,
    load_facts,
)

from tests.unit.triage_fixtures import NOW, FakeForge

REPO = "example-org/alpha"
SCOPE = Scope(kind="repo", target=REPO)
AT = datetime(2026, 9, 25, 0, 0, tzinfo=UTC)
AFTER = "2026-09-25T06:00:00Z"
BRANCH = "feat/batch-x"


def _pr(number: int, *, state: str = "MERGED", head: str = BRANCH) -> dict[str, Any]:
    return {
        "number": number,
        "title": f"PR {number}",
        "state": state,
        "isDraft": False,
        "createdAt": AFTER,
        "mergedAt": "2026-09-26T00:00:00Z" if state == "MERGED" else None,
        "url": f"https://github.com/{REPO}/pull/{number}",
        "headRefName": head,
        "headRefOid": f"oid{number}",
        "closingIssuesReferences": [],
        "author": {"login": "operator"},
        "isCrossRepository": False,
    }


def _forge(prs: list[dict[str, Any]], **kw: Any) -> FakeForge:
    return FakeForge(issues={REPO: []}, prs={REPO: []}, head_prs={(REPO, BRANCH): prs}, **kw)


# ------------------------------------------------------------------ the stamp


def test_facts_schema_is_mains_plus_one_and_older_schemas_still_load(tmp_path: Path) -> None:
    assert FACTS_SCHEMA == 12
    assert FACTS_READS == (3, 4, 5, 6, 7, 8, 9, 10, 11, 12)
    merged = {"repo": REPO, "number": 4, "title": "t", "state": "MERGED", "is_draft": False,
              "url": "u"}  # fmt: skip
    old = {"schema": 11, "scope": REPO, "kind": "repo", "collected_at": AFTER, "repos": [REPO],
           "issues": [], "batch_prs": [merged]}  # fmt: skip
    (tmp_path / "facts.json").write_text(json.dumps(old))
    facts = load_facts(tmp_path / "facts.json")
    assert facts.schema_ == 11
    assert facts.batch_prs[0].labels is None and facts.batch_prs[0].cursor is None


def test_the_stamp_comment_cites_the_labels_the_cursor_and_the_exit_block() -> None:
    import fr.triage.model as model

    source = Path(model.__file__).read_text(encoding="utf-8")
    comment = source[source.index("# 12 adds") : source.index("FACTS_SCHEMA: Literal")]
    for needle in ("labels", "cursor", "TriageConfig.exit"):
        assert needle in comment


def test_collected_facts_are_stamped_twelve() -> None:
    assert collect_facts(_forge([]), SCOPE, now=NOW).to_json()["schema"] == 12


# ---------------------------------------------------------- merged-PR labels


def test_an_unfinished_batchs_merged_pr_carries_its_labels() -> None:
    forge = _forge([_pr(40)], pr_labels={(REPO, 40): ["gate:tester", "verification:live"]})

    facts = collect_facts(
        forge, SCOPE, now=NOW, batch_branches=[("alpha", BRANCH, AT)],
        ledger_branches=[("alpha", BRANCH, AT)],
    )  # fmt: skip

    (pr,) = facts.batch_prs
    assert pr.labels == ["gate:tester", "verification:live"]
    assert forge.called("pr_labels") == [{"repo": REPO, "number": 40}]


def test_a_finished_batchs_merged_pr_costs_no_label_read() -> None:
    forge = _forge([_pr(40)], pr_labels={(REPO, 40): ["gate:tester"]})

    facts = collect_facts(forge, SCOPE, now=NOW, batch_branches=[("alpha", BRANCH, AT)])

    assert facts.batch_prs[0].labels is None
    assert forge.called("pr_labels") == []


def test_an_open_batch_pr_is_never_label_read_again() -> None:
    """An open PR's labels come from the open-PR list already (merge-train §A)."""
    forge = _forge([_pr(41, state="OPEN")])

    collect_facts(
        forge, SCOPE, now=NOW, batch_branches=[("alpha", BRANCH, AT)],
        ledger_branches=[("alpha", BRANCH, AT)],
    )  # fmt: skip

    assert forge.called("pr_labels") == []


# ------------------------------------------------------------ cursor position


def _cursor(**steps: dict[str, Any]) -> dict[str, Any]:
    return {"run": "r1", "branch": BRANCH, "cursor": next(reversed(steps)), "steps": steps}


@pytest.mark.parametrize(
    ("doc", "kind", "step", "unit"),
    [
        (_cursor(brainstorm={"state": "blocked"}), "gate", "brainstorm", None),
        (_cursor(implement={"state": "running"}, deliver={"state": "done"}),
         "deliver-done", "deliver", None),
        (_cursor(implement={"state": "running", "units": {
            "phase/1/implement-phase": {"state": "done"}, "phase/2": {"state": "manual"}}}),
         "manual", "implement", "phase/2"),
        (_cursor(implement={"state": "running", "units": {
            "phase/1/implement-phase": {"state": "running"}, "phase/2": {"state": "manual"}}}),
         "none", "implement", None),
        (_cursor(implement={"state": "running"}), "none", "implement", None),
    ],
)  # fmt: skip
def test_the_cursor_position_names_a_gate_a_done_deliver_or_a_manual_unit(
    doc: dict[str, Any], kind: str, step: str, unit: str | None
) -> None:
    assert cursor_position(doc, BRANCH) == CursorPosition(run="r1", step=step, kind=kind, unit=unit)


def test_a_cursor_for_another_branch_or_unreadable_is_no_position() -> None:
    assert cursor_position(_cursor(deliver={"state": "done"}), "feat/other") is None
    assert cursor_position({"branch": BRANCH}, BRANCH) is None
    assert cursor_position(["not", "a", "mapping"], BRANCH) is None


def test_collect_puts_the_cursor_position_on_an_open_batch_pr() -> None:
    forge = _forge([_pr(41, state="OPEN")])
    seen: list[tuple[str, str]] = []

    def at(pr: PullRequest) -> CursorPosition | None:
        seen.append((pr.head_ref, pr.head_oid))
        return CursorPosition(run="r1", step="deliver", kind="deliver-done")

    facts = collect_facts(
        forge, SCOPE, now=NOW, batch_branches=[("alpha", BRANCH, AT)],
        ledger_branches=[("alpha", BRANCH, AT)], cursor_at=at,
    )  # fmt: skip

    assert facts.batch_prs[0].cursor == CursorPosition(
        run="r1", step="deliver", kind="deliver-done"
    )
    assert seen == [(BRANCH, "oid41")]


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def test_read_cursor_reads_the_cursor_at_the_pr_head_through_gitseam(tmp_path: Path) -> None:
    repo = tmp_path / "clone"
    _git(tmp_path, "init", "--quiet", "--initial-branch=main", str(repo))
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(repo, "config", k, v)
    runs = repo / "docs/superpowers/runs"
    runs.mkdir(parents=True)
    (runs / "other.yaml").write_text("run: other\nbranch: feat/other\ncursor: x\nsteps: {}\n")
    (runs / "r1.yaml").write_text(
        f"run: r1\nbranch: {BRANCH}\ncursor: brainstorm\nsteps:\n  brainstorm:\n"
        "    state: blocked\n"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "--quiet", "-m", "cursor")
    head = _git(repo, "rev-parse", "HEAD")
    # The working tree moves on: the read is at the PR head, never the checkout.
    (runs / "r1.yaml").write_text(f"run: r1\nbranch: {BRANCH}\ncursor: x\nsteps: {{}}\n")
    pr = PullRequest(repo=REPO, number=41, title="t", state="OPEN", is_draft=False, url="u",
                     head_ref=BRANCH, head_oid=head)  # fmt: skip

    assert read_cursor(Checkout(repo), pr) == CursorPosition(
        run="r1", step="brainstorm", kind="gate"
    )
    unknown = pr.model_copy(update={"head_oid": "0" * 40})
    assert read_cursor(Checkout(repo), unknown) is None  # a head the clone cannot reach


def test_p4_r7_a_merged_pr_known_ungated_or_passed_is_not_read_again() -> None:
    forge = _forge([_pr(40), _pr(42, head="feat/batch-y")], pr_labels={(REPO, 40): ["x"]})
    forge.head_prs[(REPO, "feat/batch-y")] = [_pr(42, head="feat/batch-y")]
    branches = [("alpha", BRANCH, AT), ("alpha", "feat/batch-y", AT)]

    facts = collect_facts(
        forge, SCOPE, now=NOW, batch_branches=branches, ledger_branches=branches,
        known_labels={(REPO, 40): ["gate:tester", "gate:tester-passed"],
                      (REPO, 42): ["gate:tester"]},
    )  # fmt: skip

    assert {p.number: p.labels for p in facts.batch_prs} == {
        40: ["gate:tester", "gate:tester-passed"],
        42: [],
    }
    assert forge.called("pr_labels") == [{"repo": REPO, "number": 42}]  # held: read again


def test_p4_r7_only_a_batch_with_no_closeout_event_is_a_ledger_branch() -> None:
    from fr.commands.triage_cmd import ledger_branches
    from fr.triage.model import Batch

    def batch(bid: str, *extra: dict[str, Any]) -> Batch:
        dispatch = {"kind": "dispatch", "at": "2026-10-01T10:00:00Z", "runner": "fake",
                    "handle": "h", "branch": f"feat/batch-{bid}"}  # fmt: skip
        return Batch.model_validate(
            {"id": bid, "title": bid, "ids": [f"alpha#{bid[-1]}"], "events": [dispatch, *extra]}
        )

    started = {"kind": "closeout", "at": "2026-10-02T10:00:00Z", "runner": "fake", "handle": "c"}
    got = ledger_branches([batch("b1"), batch("b2", started)])

    assert [b for _, b, _ in got] == ["feat/batch-b1"]
