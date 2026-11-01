"""P2.T2/T3: `apply_plan` against `FakeGhClient` (spec 2026-11-01-gate-backfill §F, §G).
R6-R10 and R15. Names are fictional."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fr.gatebackfill import trackers as t
from fr.gatebackfill.apply import ApplyRefusedError, ApplyReport, apply_plan
from fr.gatebackfill.model import PlanEntry, PlanFile, PrHit
from fr.ghclient import UnsupportedForgeOperation

from tests.unit.fakes import FakeGhClient, FakeGhError
from tests.unit.gatebackfill_fixtures import REPO, STRANGER

KEY = "plan:2026-04-02-fleet#p3"
MUTATIONS = {
    "ensure_labels", "edit_pr_labels", "edit_issue_labels", "create_issue", "comment_issue",
    "edit_issue_body", "close_issue", "edit_issue_state", "comment_pr", "edit_issue",
}  # fmt: skip


def entry(
    key: str = KEY, *, gate: str | None = "devops", pr: int = 41, decision: str = "owed",
    walk_only: bool = False, issue: int | None = None,
) -> PlanEntry:  # fmt: skip
    return PlanEntry(
        key=key, title="fleet: phase 3", gate=gate, computed_gate=gate,
        pr=PrHit(number=pr, basis="commit"), decision=decision, default_decision="owed",
        walk_only=walk_only, issue=issue,
    )  # fmt: skip


def client(*prs: int) -> FakeGhClient:
    c = FakeGhClient()
    for n in prs or (41,):
        c.add_pr(REPO, n, state="MERGED", head_ref=f"feat/{n}")
    return c


def run(
    c: FakeGhClient, *entries: PlanEntry, fresh: list[PlanEntry] | None = None,
    tracking: str = "github", tmp: Path = Path("/nonexistent"),
) -> ApplyReport:  # fmt: skip
    plan = PlanFile(repo=REPO, entries=list(entries))
    return apply_plan(tmp, plan, fresh if fresh is not None else list(entries), c,
                      repo=REPO, tracking=tracking)  # fmt: skip


def names(c: FakeGhClient) -> list[str]:
    return [n for n, _ in c.calls if n in MUTATIONS]


def tracker(c: FakeGhClient, n: int, body: str, labels: set[str] | None = None) -> None:
    c.add_issue(REPO, n, labels=labels or {"fr:owed"}, body=body)


# --- T2.S1: the owed path -------------------------------------------------------------------


def test_owed_entry_labels_its_pr_and_files_one_tracker_with_labels_ensured_lazily() -> None:
    c = client()
    rep = run(c, entry())
    assert names(c) == ["ensure_labels", "edit_pr_labels", "ensure_labels", "create_issue"]
    ensured = [[x.name for x in kw["labels"]] for n, kw in c.calls if n == "ensure_labels"]
    assert ensured == [["gate:devops"], ["fr:owed"]]
    assert c.pr_labels[(REPO, 41)] == {"gate:devops"}
    body = c.issues[(REPO, 1)].body
    assert t.fr_gate_marker(body) == ("devops", 41) and rep.failed == 0


def test_a_pr_already_holding_the_gate_gets_no_label_write() -> None:
    c = client()
    c.prs[(REPO, 41)]["labels"] = ["gate:devops"]
    tracker(c, 5, t.tracker_body(KEY, "x", "devops", 41))
    run(c, entry())
    assert names(c) == []


def test_a_passed_gate_writes_nothing_and_reports_the_discharge_command() -> None:
    c = client()
    c.prs[(REPO, 41)]["labels"] = ["gate:devops-passed"]
    rep = run(c, entry())
    line = rep.lines()[0]
    assert names(c) == [] and "fr gate pass" not in line
    assert "nothing to tick" in line or "fr plan edit" in line


def test_a_walk_only_tracker_is_filed_with_awaiting_live() -> None:
    c = client()
    run(c, entry(gate="tester", walk_only=True))
    assert c.issues[(REPO, 1)].labels == {"fr:owed", "fr:awaiting-live"}


def test_a_reused_tracker_gains_awaiting_live_and_is_not_refiled() -> None:
    c = client()
    tracker(c, 5, t.tracker_body(KEY, "x", "tester", 41))
    run(c, entry(gate="tester", walk_only=True))
    assert c.issues[(REPO, 5)].labels == {"fr:owed", "fr:awaiting-live"}
    assert "create_issue" not in names(c)


def test_a_closed_issue_is_linked_once_and_never_reopened() -> None:
    c = client()
    c.add_issue(REPO, 9, state="CLOSED")
    e = entry("issue:example-org/widgets#9", issue=9)
    run(c, e)
    comments = [kw for n, kw in c.calls if n == "comment_issue"]
    assert len(comments) == 1 and comments[0]["number"] == 9
    assert comments[0]["body"].splitlines()[-1] == (
        "<!-- fr-gate-link:issue:example-org/widgets#9 tracker:example-org/widgets#1 -->"
    )
    assert "edit_issue_state" not in names(c)
    before = c.attempted_mutations
    run(c, e)
    assert c.attempted_mutations == before


def test_a_marker_less_owned_tracker_is_rewritten_and_another_prs_is_skipped() -> None:
    c = client(41, 42)
    tracker(c, 5, "old body\n\n<!-- fr-owed:plan:2026-04-02-fleet#p3 -->")
    run(c, entry())
    assert c.issues[(REPO, 5)].body == t.tracker_body(KEY, "fleet: phase 3", "devops", 41)
    fresh = client(41, 42)
    other = "plan:2026-05-01-other#p1"
    tracker(fresh, 6, t.tracker_body(other, "x", "devops", 42))
    rep = run(fresh, entry(other, pr=41))
    why = rep.results[0].skipped or ""
    assert "names gate:devops pr:42" in why and "not gate:devops pr:41" in why
    assert "fix the plan entry's gate or close the tracker, then re-run" in why
    assert fresh.attempted_mutations == 0


def test_tracking_none_writes_only_the_pr_label() -> None:
    c = client()
    run(c, entry(walk_only=True), tracking="none")
    assert names(c) == ["ensure_labels", "edit_pr_labels"]
    assert "list_issues" not in [n for n, _ in c.calls]


@pytest.mark.parametrize("decision", ["review", "tick", "na", "park"])
def test_other_decisions_write_nothing(decision: str) -> None:
    c = client()
    rep = run(c, entry(decision=decision))
    assert names(c) == [] and rep.results == []


def test_an_entry_without_a_gate_writes_nothing() -> None:
    c = client()
    rep = run(c, entry(gate=None))
    assert names(c) == [] and "no gate" in (rep.results[0].skipped or "")


def test_a_forge_error_is_recorded_and_the_rest_proceed() -> None:
    c = client(41, 42)
    c.fail_on_mutation = 0
    rep = run(c, entry(), entry("plan:2026-05-01-other#p1", pr=42))
    assert rep.failed == 1 and rep.results[1].error is None and rep.results[0].error
    assert (REPO, 1) in c.issues


def test_an_unsupported_operation_is_recorded_per_entry() -> None:
    class NoLabels(FakeGhClient):
        def edit_pr_labels(self, *a: Any, **k: Any) -> None:
            raise UnsupportedForgeOperation("edit_pr_labels", "gitea")

    c = NoLabels()
    c.add_pr(REPO, 41, state="MERGED")
    rep = run(c, entry())
    assert rep.failed == 1 and "not supported" in (rep.results[0].error or "")


def test_a_second_apply_makes_no_write() -> None:
    c = client(41, 42, 43)
    c.add_issue(REPO, 9, state="CLOSED")
    c.add_issue(REPO, 8, labels=set())
    c.issue_authors[(REPO, 8)] = STRANGER
    es = [
        entry(),
        entry("plan:2026-05-01-w#p1", gate="tester", pr=42, walk_only=True),
        entry("issue:example-org/widgets#9", pr=43, issue=9),
        entry("plan:2026-06-01-a#p2", pr=41, decision=f"adopt {REPO}#8"),
    ]
    run(c, *es)
    assert c.attempted_mutations > 0
    before = c.attempted_mutations
    rep = run(c, *es)
    assert c.attempted_mutations == before and rep.writes == 0


# --- T2.S2: R15 -----------------------------------------------------------------------------


def test_no_plan_file_refuses_before_any_write() -> None:
    c = client()
    with pytest.raises(ApplyRefusedError):
        apply_plan(Path("/x"), None, [entry()], c, repo=REPO, tracking="github")
    assert c.attempted_mutations == 0


def test_a_plan_for_another_repo_refuses() -> None:
    c = client()
    plan = PlanFile(repo="example-org/gadgets", entries=[entry()])
    with pytest.raises(ApplyRefusedError, match="gadgets"):
        apply_plan(Path("/x"), plan, [entry()], c, repo=REPO, tracking="github")
    assert c.attempted_mutations == 0


def test_an_entry_whose_pr_or_gate_re_resolves_differently_is_skipped() -> None:
    c = client(41, 42)
    rep = run(c, entry(), fresh=[entry(pr=42)])
    assert "re-resolves to #42" in (rep.results[0].skipped or "")
    rep = run(c, entry(), fresh=[entry(gate="tester")])
    assert "gate re-resolves" in (rep.results[0].skipped or "")
    assert c.attempted_mutations == 0


def test_an_operator_set_gate_applies_while_the_computed_one_still_matches() -> None:
    c = client()
    e = entry(gate="tester").model_copy(update={"computed_gate": "devops"})
    run(c, e, fresh=[entry(gate="devops")])
    assert c.pr_labels[(REPO, 41)] == {"gate:tester"}


def test_a_new_candidate_missing_from_the_plan_is_reported_not_applied() -> None:
    c = client()
    rep = run(c, entry(), fresh=[entry(), entry("plan:2026-07-01-new#p1")])
    assert any("plan:2026-07-01-new#p1" in ln and "not in the plan" in ln for ln in rep.lines())
    assert len([n for n in names(c) if n == "create_issue"]) == 1


def test_a_plan_entry_no_longer_a_candidate_is_skipped() -> None:
    c = client()
    rep = run(c, entry(), fresh=[])
    assert "no longer owed" in (rep.results[0].skipped or "") and c.attempted_mutations == 0


# --- T3.S1: adopt, foreign issues, duplicates -----------------------------------------------


def foreign(
    c: FakeGhClient, n: int, body: str = "please do it", labels: set[str] | None = None
) -> None:
    c.add_issue(REPO, n, body=body, labels=labels or set())
    c.issue_authors[(REPO, n)] = STRANGER


def kinds(c: FakeGhClient) -> list[str]:
    return [n for n, _ in c.calls if n in MUTATIONS]


def test_adopt_comments_and_labels_a_foreign_issue_and_never_edits_or_closes_it() -> None:
    c = client()
    foreign(c, 8)
    run(c, entry(decision=f"adopt {REPO}#8", walk_only=True))
    assert c.issues[(REPO, 8)].labels == {"fr:owed", "fr:awaiting-live"}
    assert c.issues[(REPO, 8)].body == "please do it"
    assert "edit_issue_body" not in kinds(c) and "close_issue" not in kinds(c)
    body = c.issue_comments[(REPO, 8)][0]["body"]
    assert t.fr_adopt_marker(body) == (KEY, "devops", 41)
    n = c.attempted_mutations
    run(c, entry(decision=f"adopt {REPO}#8", walk_only=True))
    assert c.attempted_mutations == n


def test_adopting_closes_the_fr_owned_duplicate() -> None:
    c = client()
    foreign(c, 8)
    tracker(c, 5, t.tracker_body(KEY, "x", "devops", 41))
    run(c, entry(decision=f"adopt {REPO}#8"))
    assert c.issues[(REPO, 5)].state == "CLOSED"
    closing = [kw for n, kw in c.calls if n == "close_issue"][0]
    assert closing["comment"] == f"Duplicate of {REPO}#8; tracking moved there."
    assert not [kw for n, kw in c.calls if n == "close_issue" and kw["number"] == 8]


@pytest.mark.parametrize(
    ("ref", "why"),
    [
        ("example-org/other#8", "not in example-org/widgets"),
        (f"{REPO}#99", "does not exist"),
        (f"{REPO}#7", "is closed"),
        (f"{REPO}#5", "fr-owned tracker"),
    ],
)
def test_an_unusable_adopt_target_is_skipped_with_its_reason(ref: str, why: str) -> None:
    c = client()
    c.add_issue(REPO, 7, state="CLOSED")
    tracker(c, 5, t.tracker_body("plan:2026-01-01-z#p1", "x", "devops", 41))
    rep = run(c, entry(decision=f"adopt {ref}"))
    assert why in (rep.results[0].skipped or "")
    assert c.attempted_mutations == 0


def test_an_issue_whose_marker_someone_else_wrote_is_never_reused() -> None:
    c = client()
    foreign(c, 8, body="text\n\n<!-- fr-owed:plan:2026-04-02-fleet#p3 -->", labels={"fr:owed"})
    run(c, entry())
    assert c.issues[(REPO, 8)].body.startswith("text") and (REPO, 1) in c.issues
    assert not [kw for n, kw in c.calls if n in ("edit_issue_body", "close_issue")]


# --- the review fixes (p2-r2 .. r8) --------------------------------------------------------


def test_p2_r2_a_bare_owed_on_an_open_issue_key_writes_nothing_and_says_how_to_adopt() -> None:
    c = client()
    foreign(c, 8)
    e = entry(f"issue:{REPO}#8", issue=8)
    rep = run(c, e)
    assert c.attempted_mutations == 0 and rep.writes == 0
    assert "adopt it (decision: adopt" in (rep.results[0].skipped or "")
    assert "give the manifest entry an issue:" in (rep.results[0].skipped or "")


def test_p2_r2_notes_are_not_writes() -> None:
    from fr.gatebackfill.apply import EntryResult

    rep = ApplyReport(results=[EntryResult("k", actions=["a"], notes=["n1", "n2"])])
    assert rep.writes == 1 and "n1" in rep.lines()[0]


def test_p2_r2_adopting_the_open_issue_key_is_the_idempotent_route() -> None:
    c = client()
    foreign(c, 8)
    e = entry(f"issue:{REPO}#8", issue=8, decision=f"adopt {REPO}#8")
    run(c, e)
    assert c.attempted_mutations > 0
    before = c.attempted_mutations
    assert run(c, e).writes == 0 and c.attempted_mutations == before


def test_p2_r4_only_a_not_found_reads_as_does_not_exist() -> None:
    class Flaky(FakeGhClient):
        def view_issue(self, repo: str, number: int) -> dict[str, Any]:
            raise FakeGhError("HTTP 500: server error")

    c = Flaky()
    c.add_pr(REPO, 41, state="MERGED")
    rep = run(c, entry(decision=f"adopt {REPO}#99"))
    assert rep.failed == 1 and "500" in (rep.results[0].error or "")
    assert rep.results[0].skipped is None


def test_p2_r5_every_fr_owned_duplicate_is_closed_in_one_run() -> None:
    c = client()
    foreign(c, 8)
    tracker(c, 5, t.tracker_body(KEY, "x", "devops", 41))
    tracker(c, 6, t.tracker_body(KEY, "x", "devops", 41))
    run(c, entry(decision=f"adopt {REPO}#8"))
    assert c.issues[(REPO, 5)].state == "CLOSED" and c.issues[(REPO, 6)].state == "CLOSED"
    before = c.attempted_mutations
    assert run(c, entry(decision=f"adopt {REPO}#8")).writes == 0
    assert c.attempted_mutations == before


def test_p2_r7_a_foreign_comment_with_a_valid_adopt_marker_is_not_trusted() -> None:
    c = client()
    foreign(c, 8)
    c.issue_comments[(REPO, 8)] = [{"body": t.adopt_comment(KEY, "devops", 41), "author": STRANGER}]
    run(c, entry(decision=f"adopt {REPO}#8"))
    mine = [kw for n, kw in c.calls if n == "comment_issue"]
    assert len(mine) == 1 and t.fr_adopt_marker(mine[0]["body"]) == (KEY, "devops", 41)


def test_p2_r7_the_same_holds_for_an_open_issue_key_adopted() -> None:
    c = client()
    foreign(c, 8)
    ikey = f"issue:{REPO}#8"
    c.issue_comments[(REPO, 8)] = [
        {"body": t.adopt_comment(ikey, "devops", 41), "author": STRANGER}
    ]
    run(c, entry(ikey, issue=8, decision=f"adopt {REPO}#8"))
    assert len([1 for n, _ in c.calls if n == "comment_issue"]) == 1


def test_p2_r8_the_cursors_are_read_once_per_apply(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import fr.run.cursors as cursors

    calls: list[Path] = []

    def counting(root: Path) -> list[Path]:
        calls.append(root)
        return []

    monkeypatch.setattr(cursors, "all_cursors", counting)
    c = client(41, 42, 43)
    run(
        c, entry(), entry("plan:2026-05-01-w#p1", pr=42), entry("plan:2026-06-01-a#p2", pr=43),
        tmp=tmp_path,
    )  # fmt: skip
    assert len(calls) == 1
