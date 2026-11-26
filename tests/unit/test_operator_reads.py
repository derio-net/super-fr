"""`fr.triage.operator_entries.operator_reads` over a fake driver and forge (spec
2026-11-24-wave-queue-gaps R12, R13, R15, §C, §F 8, 9).

The read is the command layer's: it decides what the pure planner is handed
(`queue_operator`, `queue_pending`, `queue_removed`) and every forge write R13 makes. The
queue's `approval` events are written for real, through `queue_writer`, into tmp_path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from fr.commands.triage_cmd import _scope
from fr.triage.model import (
    ApprovalEvent,
    Facts,
    Issue,
    Judgements,
    PullRequest,
    QueueApprovalEvent,
    load_judgements,
)
from fr.triage.operator_entries import PREAPPROVAL_MARKER, operator_reads
from fr.triage.scope_config import scope_id

REPO = "derio-net/super-fr"
H1, H2 = "1" * 40, "2" * 40
MAIN = "m" * 40
AT = "2026-11-24T10:00:00Z"


def _pr(number: int, head_ref: str, *, author: str = "operator", cross: bool = False,
        head: str = H1) -> PullRequest:  # fmt: skip
    return PullRequest(
        repo=REPO, number=number, title=f"pr {number}", state="OPEN", is_draft=False,
        url=f"https://github.com/{REPO}/pull/{number}", head_ref=head_ref, head_oid=head,
        author=author, cross_repo=cross, created_at="2026-11-24T09:30:00Z",
    )  # fmt: skip


class Forge:
    def __init__(self) -> None:
        self.views: dict[int, dict[str, Any]] = {}
        self.required: dict[int, list[dict[str, Any]]] = {}
        self.checks: dict[int, list[dict[str, Any]]] = {}
        self.writes: list[tuple[str, Any]] = []

    def view(self, n: int, *, head: str = H1, labels: tuple[str, ...] = (), **over: Any) -> None:
        self.views[n] = {"state": "OPEN", "head_oid": head, "head_ref": f"fix/{n}",
                         "base_ref": "main", "labels": list(labels), "draft": False,
                         "mergeable": "MERGEABLE", **over}  # fmt: skip
        self.checks.setdefault(n, [{"name": "ci", "bucket": "pass"}])

    def pr_view(self, repo: str, n: int) -> dict[str, Any]:
        return dict(self.views[n])

    def pr_required_checks(self, repo: str, n: int) -> list[dict[str, Any]]:
        return self.required.get(n, [])

    def pr_checks(self, repo: str, n: int) -> list[dict[str, Any]]:
        return self.checks.get(n, [])

    def edit_issue_labels(self, repo: str, n: int, *, add: frozenset[str],
                          remove: frozenset[str]) -> None:  # fmt: skip
        self.writes.append(("labels", (n, sorted(add), sorted(remove))))
        labels = [x for x in self.views[n]["labels"] if x not in remove] + sorted(add)
        self.views[n]["labels"] = labels

    def comment_pr(self, repo: str, n: int, body: str) -> None:
        self.writes.append(("comment", (n, body)))

    def label_exists(self, repo: str, name: str) -> bool:
        return True

    def read_file(self, repo: str, path: str) -> str:
        raise RuntimeError("Not Found (HTTP 404)")  # no .fr/settings.yaml: labels allowed


class Clone:
    def default_branch(self) -> str:
        return "main"

    def rev_parse(self, ref: str) -> str:
        return MAIN


class Driver:
    def __init__(self, target: Path, forge: Forge, *, yes: bool = True) -> None:
        self.target, self.forge, self.yes = target, forge, yes
        self.scope = _scope(REPO, None)
        self.scope_args = ("--repo", REPO)
        self.patch_ids: dict[tuple[int, str], str | None] = {}
        self.warned: list[str] = []

    def client(self, facts: Any, repo: str) -> Forge:
        return self.forge

    def _ci_none(self, repo: str) -> bool:
        return False

    def _patch_id_of(self, facts: Any, repo: str) -> Any:
        def of(pr: int, head: str, *, fresh: bool = False) -> str | None:
            return self.patch_ids.get((pr, head), f"pid-{head[:4]}")

        return of

    def _fetched_reader(self, repo: str) -> Clone:
        return Clone()

    def _report_once(self, key: str, message: str) -> bool:
        self.warned.append(message)
        return True


def _facts(*prs: PullRequest) -> Facts:
    return Facts(
        viewer="operator", schema=3, scope="derio-net--super-fr", kind="repo",
        collected_at="2026-11-24T09:00:00+00:00", repos=[REPO],
        issues=[Issue(repo=REPO, number=1, title="issue 1", state="open",
                      url=f"https://github.com/{REPO}/issues/1", author_association="OWNER")],
        prs=list(prs), config={},
    )  # fmt: skip


def _request(n: int, *, kind: str = "queue_add", by: str = "operator", at: str = AT,
             preapproved: bool = False) -> dict[str, Any]:  # fmt: skip
    doc: dict[str, Any] = {"kind": kind, "at": at, "repo": REPO,
                           "scope": scope_id(_scope(REPO, None)), "pr": n, "by": by}  # fmt: skip
    if kind == "queue_add":
        doc["preapproved"] = preapproved
    return doc


def _state(tmp_path: Path, *requests: dict[str, Any], queues: list[Any] | None = None,
           batch_pr: bool = False) -> Judgements:  # fmt: skip
    events: list[dict[str, Any]] = [{"kind": "dispatch", "at": "2026-11-24T09:00:00Z",
                                     "runner": "fake", "handle": "h",
                                     "branch": "feat/batch-a"}]  # fmt: skip
    doc: dict[str, Any] = {
        "schema": 14, "tiers": [{"n": 1, "title": "Now"}], "issues": {"super-fr#1": {"tier": 1}},
        "batches": [{"id": "a", "title": "A", "ids": ["super-fr#1"], "wave": 1,
                     "events": events}] if batch_pr else [],
        "queue_requests": list(requests),
    }  # fmt: skip
    if queues:
        doc["queues"] = queues
    (tmp_path / "judgements.yaml").write_text(yaml.safe_dump(doc, sort_keys=False), "utf-8")
    return load_judgements(tmp_path / "judgements.yaml")


def _read(driver: Driver, facts: Facts, judgements: Judgements) -> dict[str, Any]:
    return operator_reads(driver, facts, judgements, {"a": REPO}, ())


def _batch_approvals(tmp_path: Path) -> list[ApprovalEvent]:
    return [e for b in load_judgements(tmp_path / "judgements.yaml").batches for e in b.events
            if isinstance(e, ApprovalEvent)]  # fmt: skip


def _approvals(tmp_path: Path) -> list[QueueApprovalEvent]:
    return [e for q in load_judgements(tmp_path / "judgements.yaml").queues for e in q.events
            if isinstance(e, QueueApprovalEvent)]  # fmt: skip


# ------------------------------------------------------------------ admission (R12)


def test_an_added_pr_with_a_valid_label_is_admitted_as_an_operator_entry(tmp_path: Path) -> None:
    forge = Forge()
    forge.view(10, labels=("approved-fr",))
    judgements = _state(tmp_path, _request(10))

    out = _read(Driver(tmp_path, forge), _facts(_pr(10, "fix/10")), judgements)

    ((live, at),) = out["queue_operator"][REPO]
    assert live.number == 10 and live.head == H1 and live.checks == "green" and live.trusted
    assert at is not None
    (event,) = _approvals(tmp_path)
    assert event.entry.kind == "operator" and event.entry.pr == 10 and event.head == H1
    assert event.patch_id == "pid-1111"
    assert out["queue_pending"] == {REPO: {"operator#10": datetime(2026, 11, 24, 10, tzinfo=UTC)}}


def test_an_unlabelled_added_pr_is_pending_but_not_admitted(tmp_path: Path) -> None:
    forge = Forge()
    forge.view(10)
    judgements = _state(tmp_path, _request(10))

    out = _read(Driver(tmp_path, forge), _facts(_pr(10, "fix/10")), judgements)

    assert REPO not in out["queue_operator"]
    assert "operator#10" in out["queue_pending"][REPO]
    assert forge.writes == []


def test_red_own_checks_admit_it_as_failing(tmp_path: Path) -> None:
    forge = Forge()
    forge.view(10, labels=("approved-fr",))
    forge.checks[10] = [{"name": "ci", "bucket": "fail"}]
    judgements = _state(tmp_path, _request(10))

    out = _read(Driver(tmp_path, forge), _facts(_pr(10, "fix/10")), judgements)

    ((live, _),) = out["queue_operator"][REPO]
    assert live.checks == "failing"


def test_a_push_that_changes_the_diff_voids_the_approval(tmp_path: Path) -> None:
    forge = Forge()
    forge.view(10, labels=("approved-fr",))
    judgements = _state(tmp_path, _request(10))
    driver = Driver(tmp_path, forge)
    _read(driver, _facts(_pr(10, "fix/10")), judgements)

    forge.view(10, head=H2, labels=("approved-fr",))
    out = _read(driver, _facts(_pr(10, "fix/10")), load_judgements(tmp_path / "judgements.yaml"))

    assert REPO not in out["queue_operator"]
    assert ("labels", (10, [], ["approved-fr"])) in forge.writes
    assert _approvals(tmp_path)[-1].voided_at == H2


def test_a_fork_or_a_stranger_is_never_admitted_nor_labelled(tmp_path: Path) -> None:
    forge = Forge()
    forge.view(11, labels=("approved-fr",))
    forge.view(12)
    judgements = _state(tmp_path, _request(11), _request(12, preapproved=True))
    facts = _facts(_pr(11, "fix/11", cross=True), _pr(12, "fix/12", author="mallory"))

    out = _read(Driver(tmp_path, forge), facts, judgements)

    assert REPO not in out["queue_operator"] and forge.writes == []
    assert set(out["queue_pending"][REPO]) == {"operator#11", "operator#12"}


def test_a_batch_pr_is_never_an_operator_entry_nor_pending(tmp_path: Path) -> None:
    forge = Forge()
    forge.view(17, labels=("approved-fr",))
    judgements = _state(tmp_path, _request(17), batch_pr=True)

    out = _read(Driver(tmp_path, forge), _facts(_pr(17, "feat/batch-a")), judgements)

    assert REPO not in out["queue_operator"] and REPO not in out["queue_pending"]


def test_a_closed_or_landed_pr_is_not_pending(tmp_path: Path) -> None:
    forge = Forge()
    forge.view(10, state="MERGED")
    forge.view(13)
    land = {"kind": "queue_land", "at": AT, "entries": [{"pr": 13, "kind": "operator"}],
            "main": MAIN}  # fmt: skip
    queues = [{"repo": REPO, "wave": None, "scope": scope_id(_scope(REPO, None)), "base": MAIN,
               "events": [{"kind": "queue_open", "at": AT}, land]}]  # fmt: skip
    judgements = _state(tmp_path, _request(10), _request(13), queues=queues)

    out = _read(Driver(tmp_path, forge), _facts(_pr(10, "fix/10"), _pr(13, "fix/13")), judgements)

    assert out["queue_pending"] == {}


def test_a_removed_pr_is_named_for_the_eject_and_no_longer_read(tmp_path: Path) -> None:
    forge = Forge()
    judgements = _state(tmp_path, _request(10),
                        _request(10, kind="queue_remove", at="2026-11-24T11:00:00Z"))  # fmt: skip

    out = _read(Driver(tmp_path, forge), _facts(_pr(10, "fix/10")), judgements)

    assert out["queue_removed"] == {REPO: frozenset({"operator#10"})}
    assert out["queue_operator"] == {} and out["queue_pending"] == {}


# ------------------------------------------------------------------ preapproval (R13)


def test_preapproval_labels_and_comments_with_head_and_patch_id(tmp_path: Path) -> None:
    forge = Forge()
    forge.view(10)
    judgements = _state(tmp_path, _request(10, preapproved=True))

    out = _read(Driver(tmp_path, forge), _facts(_pr(10, "fix/10")), judgements)

    assert ("labels", (10, ["approved-fr"], [])) in forge.writes
    ((_, (n, body)),) = [w for w in forge.writes if w[0] == "comment"]
    assert n == 10 and body.startswith(PREAPPROVAL_MARKER)
    assert H1 in body and "pid-1111" in body and "fr triage queue remove --pr 10" in body
    (event,) = _approvals(tmp_path)  # settled in the same pass, at that head and patch-id
    assert event.head == H1 and event.patch_id == "pid-1111"
    assert out["queue_operator"][REPO][0][0].number == 10


def test_preapproval_needs_an_allowed_adder_at_use_time(tmp_path: Path) -> None:
    forge = Forge()
    forge.view(10)
    judgements = _state(tmp_path, _request(10, by="mallory", preapproved=True))
    driver = Driver(tmp_path, forge)

    out = _read(driver, _facts(_pr(10, "fix/10")), judgements)

    assert forge.writes == [] and REPO not in out["queue_operator"]
    assert any("mallory" in w and "not an allowed author" in w for w in driver.warned)


def test_preapproval_waits_for_green_own_checks(tmp_path: Path) -> None:
    forge = Forge()
    forge.view(10)
    forge.checks[10] = [{"name": "ci", "bucket": "pending"}]
    judgements = _state(tmp_path, _request(10, preapproved=True))

    _read(Driver(tmp_path, forge), _facts(_pr(10, "fix/10")), judgements)

    assert forge.writes == []


def test_preapproval_skips_a_pr_the_forge_reads_as_conflicting(tmp_path: Path) -> None:
    forge = Forge()
    forge.view(10, mergeable="CONFLICTING")
    judgements = _state(tmp_path, _request(10, preapproved=True))

    _read(Driver(tmp_path, forge), _facts(_pr(10, "fix/10")), judgements)

    assert forge.writes == []


def test_preapproval_skips_a_head_with_a_recorded_queue_conflict(tmp_path: Path) -> None:
    forge = Forge()
    forge.view(10)
    eject = {"kind": "queue_eject", "at": AT, "entry": {"pr": 10, "kind": "operator"},
             "reason": "conflict", "head": H1}  # fmt: skip
    queues = [{"repo": REPO, "wave": None, "scope": scope_id(_scope(REPO, None)), "base": MAIN,
               "events": [{"kind": "queue_open", "at": AT}, eject]}]  # fmt: skip
    judgements = _state(tmp_path, _request(10, preapproved=True), queues=queues)

    _read(Driver(tmp_path, forge), _facts(_pr(10, "fix/10")), judgements)

    assert forge.writes == []


def test_an_unreadable_patch_id_holds_the_preapproval_for_the_pass(tmp_path: Path) -> None:
    forge = Forge()
    forge.view(10)
    judgements = _state(tmp_path, _request(10, preapproved=True))
    driver = Driver(tmp_path, forge)
    driver.patch_ids[(10, H1)] = None

    _read(driver, _facts(_pr(10, "fix/10")), judgements)

    assert forge.writes == [] and _approvals(tmp_path) == []
    assert any("held for this pass" in w for w in driver.warned)


def test_preapproval_renews_at_the_next_green_head_after_a_void(tmp_path: Path) -> None:
    forge = Forge()
    forge.view(10)
    judgements = _state(tmp_path, _request(10, preapproved=True))
    driver = Driver(tmp_path, forge)
    _read(driver, _facts(_pr(10, "fix/10")), judgements)

    forge.views[10]["head_oid"] = H2  # a push that changes the diff: the label stays on
    out = _read(driver, _facts(_pr(10, "fix/10")), load_judgements(tmp_path / "judgements.yaml"))
    assert REPO not in out["queue_operator"]  # voided this pass, label off
    out = _read(driver, _facts(_pr(10, "fix/10")), load_judgements(tmp_path / "judgements.yaml"))

    comments = [w[1][1] for w in forge.writes if w[0] == "comment"]
    assert len(comments) == 2 and H1 in comments[0] and H2 in comments[1]
    assert "pid-2222" in comments[1]
    assert _approvals(tmp_path)[-1].head == H2 and _approvals(tmp_path)[-1].voided_at is None
    assert out["queue_operator"][REPO][0][0].head == H2


class _CommentsOffForge(Forge):
    def read_file(self, repo: str, path: str) -> str:
        return "forge:\n  comments: off\n"


def test_preapproval_does_nothing_while_forge_comments_are_off(tmp_path: Path) -> None:
    forge = _CommentsOffForge()
    forge.view(10)
    judgements = _state(tmp_path, _request(10, preapproved=True))
    driver = Driver(tmp_path, forge)

    _read(driver, _facts(_pr(10, "fix/10")), judgements)

    assert forge.writes == [] and _approvals(tmp_path) == []  # no comment, label or record
    (said,) = driver.warned
    assert "not preapproved" in said and "comments" in said


def test_preapproval_writes_nothing_in_a_dry_run(tmp_path: Path) -> None:
    forge = Forge()
    forge.view(10)
    judgements = _state(tmp_path, _request(10, preapproved=True))

    _read(Driver(tmp_path, forge, yes=False), _facts(_pr(10, "fix/10")), judgements)

    assert forge.writes == [] and _approvals(tmp_path) == []


def test_a_preapproved_batch_pr_records_the_batch_approval_at_the_vetted_head(
    tmp_path: Path,
) -> None:
    forge = Forge()
    forge.view(17)
    judgements = _state(tmp_path, _request(17, preapproved=True), batch_pr=True)

    out = _read(Driver(tmp_path, forge), _facts(_pr(17, "feat/batch-a")), judgements)

    assert ("labels", (17, ["approved-fr"], [])) in forge.writes
    assert _approvals(tmp_path) == []  # no queue event: the batch holds its approval
    (event,) = _batch_approvals(tmp_path)  # p2-r1: in the same pass, at the vetted head
    assert event.pr == 17 and event.head == H1 and event.patch_id == "pid-1111"
    assert REPO not in out["queue_operator"]


def test_a_push_between_the_preapproval_and_the_next_settle_voids_a_batch_approval(
    tmp_path: Path,
) -> None:
    """p2-r1: the batch's settle runs at the start of the NEXT pass. A session push to H2
    between the label and that settle must void, never be recorded approved at H2."""
    from fr.commands.triage_batch_cmd import event_writer
    from fr.triage.approval import Unlabelled, settle_approvals

    forge = Forge()
    forge.view(17)
    facts = _facts(_pr(17, "feat/batch-a"))
    _read(Driver(tmp_path, forge), facts, _state(tmp_path, _request(17, preapproved=True),
                                                 batch_pr=True))  # fmt: skip
    comment = next(w[1][1] for w in forge.writes if w[0] == "comment")
    assert H1 in comment

    forge.views[17]["head_oid"] = H2  # the session pushes; the label stays on
    batch = load_judgements(tmp_path / "judgements.yaml").batches[0]
    verdicts = settle_approvals(
        forge, event_writer(tmp_path, facts), REPO, [(batch, 17)], lambda _: None,
        now=datetime(2026, 11, 24, 12, tzinfo=UTC),
        patch_id_of=Driver(tmp_path, forge)._patch_id_of(facts, REPO),
    )  # fmt: skip

    assert verdicts == {"a": Unlabelled()}
    assert ("labels", (17, [], ["approved-fr"])) in forge.writes
    approvals = _batch_approvals(tmp_path)
    assert approvals[-1].head == H1 and approvals[-1].voided_at == H2
    assert all(e.head != H2 or e.voided_at for e in approvals)


def test_a_failed_audit_comment_leaves_no_label_and_no_approval(tmp_path: Path) -> None:
    """p2-r1: the audit comment goes first. A comment the forge refuses leaves no label, so
    the next pass cannot read the label as a first approval at an unvetted head."""
    import pytest
    from fr.gh import GhError

    forge = Forge()
    forge.view(10)

    def refuse(repo: str, n: int, body: str) -> None:
        raise GhError("HTTP 502")

    forge.comment_pr = refuse  # type: ignore[method-assign]
    judgements = _state(tmp_path, _request(10, preapproved=True))

    with pytest.raises(GhError):
        _read(Driver(tmp_path, forge), _facts(_pr(10, "fix/10")), judgements)

    assert forge.writes == [] and forge.views[10]["labels"] == []
    assert _approvals(tmp_path) == []
    forge.views[10]["head_oid"] = H2  # a push before the next pass
    del forge.comment_pr
    out = _read(Driver(tmp_path, forge), _facts(_pr(10, "fix/10", head=H2)),
                load_judgements(tmp_path / "judgements.yaml"))  # fmt: skip
    ((_, (_, body)),) = [w for w in forge.writes if w[0] == "comment"]
    assert H2 in body  # the head it approves is the head the audit comment names
    assert _approvals(tmp_path)[-1].head == H2
    assert out["queue_operator"][REPO][0][0].head == H2


def test_a_preapproved_operator_pr_is_recorded_before_it_is_labelled(tmp_path: Path) -> None:
    """p2-r1: the approval event is written in the preapproval itself, before the label: a
    label fr adds never stands without the approval naming the head the comment names."""
    forge = Forge()
    forge.view(10)
    seen: list[int] = []
    edit = forge.edit_issue_labels

    def edit_after_record(repo: str, n: int, *, add: frozenset[str],
                          remove: frozenset[str]) -> None:  # fmt: skip
        seen.append(len(_approvals(tmp_path)))
        edit(repo, n, add=add, remove=remove)

    forge.edit_issue_labels = edit_after_record  # type: ignore[method-assign]
    judgements = _state(tmp_path, _request(10, preapproved=True))

    _read(Driver(tmp_path, forge), _facts(_pr(10, "fix/10")), judgements)

    assert seen == [1]
    assert [w[0] for w in forge.writes] == ["comment", "labels"]
    (event,) = _approvals(tmp_path)
    assert event.head == H1 and event.patch_id == "pid-1111"


def test_a_batch_pr_with_a_conflict_event_at_its_head_is_not_preapproved(tmp_path: Path) -> None:
    forge = Forge()
    forge.view(17)
    judgements = _state(tmp_path, _request(17, preapproved=True), batch_pr=True)
    batch = judgements.batches[0]
    conflict = {"kind": "conflict", "at": "2026-11-24T09:10:00Z", "head": H1, "paths": ["a.py"],
                "delivered": "session"}  # fmt: skip
    doc = yaml.safe_load((tmp_path / "judgements.yaml").read_text())
    doc["batches"][0]["events"].append(conflict)
    (tmp_path / "judgements.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))
    assert batch.id == "a"

    _read(Driver(tmp_path, forge), _facts(_pr(17, "feat/batch-a")),
          load_judgements(tmp_path / "judgements.yaml"))  # fmt: skip

    assert forge.writes == []


# ------------------------------------------------------------------ lens review


def test_preapproval_skips_a_pr_whose_merge_state_is_dirty(tmp_path: Path) -> None:
    forge = Forge()
    forge.view(10, merge_state="DIRTY")
    judgements = _state(tmp_path, _request(10, preapproved=True))
    driver = Driver(tmp_path, forge)

    _read(driver, _facts(_pr(10, "fix/10")), judgements)

    assert forge.writes == [] and _approvals(tmp_path) == []
    assert any("conflicting" in w for w in driver.warned)


def test_preapproval_refuses_a_pr_whose_base_moved_off_the_default_branch(tmp_path: Path) -> None:
    """Hardening (lens security): the base is re-checked at use time, not only at `add`."""
    forge = Forge()
    forge.view(10, base_ref="release")
    judgements = _state(tmp_path, _request(10, preapproved=True))
    driver = Driver(tmp_path, forge)

    _read(driver, _facts(_pr(10, "fix/10")), judgements)
    _read(driver, _facts(_pr(10, "fix/10")), judgements)

    assert forge.writes == [] and _approvals(tmp_path) == []
    (said,) = {w for w in driver.warned if "base" in w}
    assert "'release'" in said and "'main'" in said


def test_a_skipped_repos_added_prs_stay_pending_from_the_state_alone(tmp_path: Path) -> None:
    """l-errors-r1: a repo the pass skipped (unread, carried) still holds its added PRs as
    pending, read from the judgements with no forge read: a drive cannot read done over one."""
    forge = Forge()  # no views: a pr_view would raise
    land = {"kind": "queue_land", "at": AT, "entries": [{"pr": 13, "kind": "operator"}],
            "main": MAIN}  # fmt: skip
    queues = [{"repo": REPO, "wave": None, "scope": scope_id(_scope(REPO, None)), "base": MAIN,
               "events": [{"kind": "queue_open", "at": AT}, land]}]  # fmt: skip
    judgements = _state(tmp_path, _request(10), _request(13), _request(17), _request(18),
                        _request(18, kind="queue_remove", at="2026-11-24T11:00:00Z"),
                        queues=queues, batch_pr=True)  # fmt: skip
    facts = _facts(_pr(10, "fix/10"), _pr(13, "fix/13"), _pr(17, "feat/batch-a"))

    out = operator_reads(Driver(tmp_path, forge), facts, judgements, {"a": REPO}, (REPO,))

    assert out["queue_pending"] == {REPO: {"operator#10": datetime(2026, 11, 24, 10, tzinfo=UTC)}}
    assert out["queue_operator"] == {} and forge.writes == []


def test_a_trust_refused_added_pr_is_named_as_refused(tmp_path: Path) -> None:
    """l-errors-r2: the planner gives a refused entry its Need at once."""
    forge = Forge()
    forge.view(11)
    forge.view(12)
    judgements = _state(tmp_path, _request(11), _request(12))
    facts = _facts(_pr(11, "fix/11", cross=True), _pr(12, "fix/12", author="mallory"))

    out = _read(Driver(tmp_path, forge), facts, judgements)

    refused = out["queue_refused"][REPO]
    assert set(refused) == {"operator#11", "operator#12"}
    assert all(refused.values())
