"""A board fixture that populates every column and every card state (spec 2026-10-05 §D).

Fictional owner and repo (`example-org/widgets`). `world()` returns facts,
judgements, the session statuses a runner would report (by item id) and the
page notes; the page tests and the browser capture script both render it.
"""

from __future__ import annotations

from typing import Any

from fr.triage.model import Facts, Judgements

from tests.unit.triage_board_fixtures import (
    REPO,
    batch,
    dispatch,
    facts,
    issue,
    j,
    judgements,
    pr,
)

CLOSEOUT = {"kind": "closeout", "at": "2026-10-01T13:00:00Z", "runner": "fake", "handle": "c"}
HAND = {**CLOSEOUT, "runner": "hand"}
ARCHIVED = {**HAND, "archived": 77}
POST_MERGE = {"kind": "post_merge", "at": "2026-10-01T12:30:00Z"}
CANCEL = {"kind": "cancel", "at": "2026-10-01T12:00:00Z", "reason": "superseded"}
HOSTILE = '<script>alert(1)</script>"><img src=x onerror=alert(2)>'


def item(bid: str) -> str:
    return f"{REPO}/run/batch-{bid}"


def closeout_item(bid: str) -> str:
    return f"{REPO}/run/closeout-{bid}"


def world(
    *, title: str = "issue", hostile: bool = False
) -> tuple[Facts, Judgements, dict[str, str], list[str]]:
    """Every column populated: 2 proposed, 2 waiting (one blocked), 3 running (one blocked
    session, one with no session), 3 PR open, 3 closing out and 3 done."""
    merged = pr(10, "feat/batch-c-session", state="MERGED", merged_at="2026-10-01T09:00:00Z")
    merged2 = pr(11, "feat/batch-c-hand", state="MERGED", merged_at="2026-10-01T09:00:00Z")
    merged3 = pr(12, "feat/batch-c-none", state="MERGED", merged_at="2026-10-01T09:00:00Z")
    merged4 = pr(13, "feat/batch-d-done", state="MERGED", merged_at="2026-09-30T09:00:00Z")
    draft = pr(20, "feat/batch-o-draft", is_draft=True)
    red = pr(21, "feat/batch-o-red", checks={"pass": 1, "fail": 2, "pending": 0})
    ready = pr(22, "feat/batch-o-ready", mergeable="MERGEABLE", review="APPROVED")
    half = pr(14, "feat/batch-d-partial", state="MERGED", merged_at="2026-09-30T10:00:00Z")
    nums = iter(range(1, 100))
    issues: list[dict[str, Any]] = []
    batches: list[dict[str, Any]] = []

    def add(bid: str, prs: list[dict[str, Any]] | None = None, *, closed: bool = False,
            members: int = 1, **kw: Any) -> None:  # fmt: skip
        ids = []
        for k in range(members):
            n = next(nums)
            label = HOSTILE if hostile and bid == "r-run" else f"{title} {n}"
            issues.append(
                issue(n, title=label, state="closed" if closed else "open", prs=prs or [])
            )
            ids.append(n)
        batches.append(batch(bid, ids, **kw))

    add("p-queued", wave=1, rationale="small and free")
    add("p-later", wave=2)
    add("w-wait", wave=2, after=["p-queued"], rationale="needs the queue first")
    add("w-blocked", wave=2, after=["x-cancelled"])
    add("x-cancelled", wave=1, events=[dispatch("x-cancelled"), CANCEL])
    add(
        "r-run",
        wave=1,
        members=2,
        events=[dispatch("r-run")],
        rationale=HOSTILE if hostile else "the main work",
    )
    add("r-blocked", wave=1, events=[dispatch("r-blocked")])
    add("r-absent", wave=1, events=[dispatch("r-absent")])
    add("o-draft", [draft], wave=2, events=[dispatch("o-draft")])
    add("o-red", [red], wave=2, events=[dispatch("o-red")], skill="debug")
    add("o-ready", [ready], wave=2, members=3,
        events=[{**dispatch("o-ready"), "reserved_version": "5.6.0"}],
        launch={"harness": "claude", "model": "claude-opus-5-5"})  # fmt: skip
    add("c-session", [merged], closed=True, wave=3, members=2,
        events=[dispatch("c-session"), POST_MERGE, CLOSEOUT])  # fmt: skip
    add("c-hand", [merged2], closed=True, wave=3, events=[dispatch("c-hand"), HAND])
    add("c-none", [merged3], closed=True, wave=3, events=[dispatch("c-none")])
    add("d-done", [merged4], closed=True, wave=3, events=[dispatch("d-done"), ARCHIVED])
    add("d-partial", [half], wave=3, events=[dispatch("d-partial")])
    add("d-cancelled", wave=None, events=[dispatch("d-cancelled"), CANCEL])

    f = facts(
        issues,
        prs=[draft, red, ready],
        config={REPO: {"defaults": {"launch": {"harness": "codex", "model": "gpt-5"}}}},
    )
    judged = {k: j(1) for b in batches for k in b["ids"]}
    jd = judgements(judged, batches)
    statuses = {
        item("r-run"): "working",
        item("r-blocked"): "blocked",
        item("r-absent"): "absent",
        item("o-draft"): "idle",
        item("o-red"): "done",
        item("o-ready"): "unknown",
        item("c-session"): "done",
        closeout_item("c-session"): "idle",
        item("c-hand"): "done",
        item("d-cancelled"): "absent",
    }
    notes = ["runner `ghost` could not be loaded (no such runner); its sessions show unknown"]
    return f, jd, statuses, notes  # type: ignore[return-value]
