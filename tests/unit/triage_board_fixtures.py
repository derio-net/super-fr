"""A realistic board fixture for the decision views (wave-driver §I; Test Plan 13).

Fictional owner and repo (`example-org/widgets`). `busy()` carries one of every
thing the board must surface; `healthy()` carries nothing that needs the
operator. Imported as a package module, never through a `sys.path` insert.
"""

from __future__ import annotations

from typing import Any

from fr.triage.model import Facts, Judgements, PullRequest

REPO = "example-org/widgets"
URL = f"https://github.com/{REPO}"
COLLECTED = "2026-10-02T12:00:00+00:00"


def pr(number: int, head_ref: str, **kw: Any) -> dict[str, Any]:
    return {
        "repo": REPO,
        "number": number,
        "title": f"pull {number}",
        "state": kw.pop("state", "OPEN"),
        "is_draft": kw.pop("is_draft", False),
        "url": f"{URL}/pull/{number}",
        "head_ref": head_ref,
        "head_oid": kw.pop("head_oid", f"sha-{number}"),
        "created_at": kw.pop("created_at", "2026-10-01T11:00:00Z"),
        "checks": kw.pop("checks", {"pass": 3, "fail": 0, "pending": 0}),
        "author": kw.pop("author", "operator"),
        "cross_repo": kw.pop("cross_repo", False),
        **kw,
    }


def issue(number: int, **kw: Any) -> dict[str, Any]:
    return {
        "repo": REPO,
        "number": number,
        "title": f"issue {number}",
        "state": kw.pop("state", "open"),
        "url": f"{URL}/issues/{number}",
        "created_at": "2026-09-20T09:00:00Z",
        # Intake admits a maintainer's issue; a test about the outside says so itself.
        "author_association": "OWNER",
        **kw,
    }


def dispatch(bid: str, skill: str = "goal") -> dict[str, Any]:
    prefix = "fix" if skill == "debug" else "feat"
    return {
        "kind": "dispatch",
        "at": "2026-10-01T10:00:00Z",
        "runner": "fake",
        "handle": "h",
        "branch": f"{prefix}/batch-{bid}",
    }


def batch(bid: str, ids: list[int], **kw: Any) -> dict[str, Any]:
    return {"id": bid, "title": f"batch {bid}", "ids": [f"widgets#{n}" for n in ids], **kw}


def facts(issues: list[dict[str, Any]], **kw: Any) -> Facts:
    return Facts.model_validate(
        {
            "schema": 4,
            "scope": "example-org--widgets",
            "kind": "repo",
            "collected_at": kw.pop("collected_at", COLLECTED),
            "repos": [REPO],
            "issues": issues,
            "viewer": kw.pop("viewer", "operator"),
            **kw,
        }
    )


def judgements(
    issues: dict[str, dict[str, Any]], batches: list[dict[str, Any]] | None = None, **kw: Any
) -> Judgements:
    return Judgements.model_validate(
        {
            "schema": 3,
            "ranked_at": "2026-10-01",
            "tiers": [{"n": 1, "title": "Now"}, {"n": 2, "title": "Later"}],
            "issues": issues,
            "batches": batches or [],
            **kw,
        }
    )


def j(tier: int = 1, **kw: Any) -> dict[str, Any]:
    return {"tier": tier, "theme": kw.pop("theme", "core"), "cx": kw.pop("cx", "S"), **kw}


def busy() -> tuple[Facts, Judgements]:
    """Every kind of thing: a merged batch (post_merge owed), a green draft PR, a
    red batch PR, a blocked batch, a stale dispatch, a cancelled batch's open
    member, an unjudged issue, a parked issue, a feature member, and one batch the
    driver would dispatch next."""
    merged_pr = pr(10, "feat/batch-a-merged", state="MERGED", merged_at="2026-10-01T09:00:00Z")
    draft_pr = pr(11, "feat/batch-b-draft", is_draft=True)
    red_pr = pr(12, "feat/batch-c-red", checks={"pass": 1, "fail": 2, "pending": 0})
    issues = [
        issue(1, state="closed", prs=[merged_pr]),
        issue(2, state="closed", prs=[merged_pr]),
        issue(3, prs=[draft_pr]),
        issue(4, prs=[draft_pr]),
        issue(5, prs=[red_pr]),
        issue(6),
        issue(7),
        issue(8, labels=["fr:in-progress"], dispatch_marker_at="2026-09-20T09:00:00Z"),
        issue(9),
        issue(10),
        issue(11),
        issue(12),
        issue(13),
    ]
    f = facts(
        issues,
        prs=[draft_pr, red_pr],
        config={REPO: {"post_merge": ["make", "deploy"]}},
    )
    judged = {
        "widgets#1": j(1, cx="S", kind="defect"),
        "widgets#2": j(1, cx="XS", kind="defect"),
        "widgets#3": j(1, cx="M", kind="defect"),
        "widgets#4": j(1, cx="S", kind="defect"),
        "widgets#5": j(2, cx="L", kind="feature"),
        "widgets#6": j(1, cx="S", kind="defect"),
        "widgets#7": j(2, cx="S", kind="defect"),
        "widgets#8": j(2, cx="XS", kind="defect"),
        "widgets#10": j(2, kind="parked"),
        "widgets#11": j(2, cx="M", kind="feature"),
        "widgets#12": j(2, cx="S", kind="defect"),
        "widgets#13": j(1, cx="XS", kind="defect"),
    }
    batches = [
        batch("a-merged", [1, 2], wave=1, events=[dispatch("a-merged")], rationale="first"),
        batch("b-draft", [3, 4], wave=2, events=[dispatch("b-draft")], rationale="drafted"),
        batch("c-red", [5], wave=2, events=[dispatch("c-red")], skill="debug"),
        batch("d-blocked", [6], wave=3, after=["z-cancelled"], rationale="needs z"),
        batch(
            "z-cancelled",
            [7],
            wave=3,
            events=[
                dispatch("z-cancelled"),
                {"kind": "cancel", "at": "2026-10-01T12:00:00Z", "reason": "dropped"},
            ],
        ),
        batch("e-next", [13], wave=3, rationale="small and free", bump="patch"),
    ]
    features = [
        {"rank": 2, "title": "Second feature", "ids": ["widgets#12"], "why": "later", "start": "x"},
        {
            "rank": 1,
            "title": "First feature",
            "ids": ["widgets#11"],
            "why": "most value",
            "start": "/fr-goal first",
        },
    ]
    return f, judgements(judged, batches, features=features)


def healthy() -> tuple[Facts, Judgements]:
    """One merged batch, one dispatchable batch behind nothing, everything placed."""
    merged_pr = pr(10, "feat/batch-a-merged", state="MERGED", merged_at="2026-10-02T11:59:00Z")
    f = facts(
        [issue(1, state="closed", prs=[merged_pr]), issue(2)],
    )
    judged = {"widgets#1": j(1, kind="defect"), "widgets#2": j(1, kind="defect")}
    batches = [
        batch("a-merged", [1], wave=1, events=[dispatch("a-merged")]),
        batch("b-next", [2], wave=2),
    ]
    return f, judgements(judged, batches)


def make_pr(**kw: Any) -> PullRequest:
    return PullRequest.model_validate(pr(**kw))


def element_by_id(page: str, sid: str) -> str:
    """The whole element (`section`, `details` or `div`) whose id is *sid*, nested elements of
    the same tag counted: a section is a fold now, and a fold holds more folds."""
    import re

    m = re.search(rf'<(section|details|div)[^>]*\bid="{re.escape(sid)}"', page)
    assert m, f"no element with id {sid}"
    tag = m.group(1)
    depth, pos = 0, m.start()
    for t in re.finditer(rf"<(/?){tag}\b", page[m.start() :]):
        depth += -1 if t.group(1) else 1
        if depth == 0:
            return page[m.start() : m.start() + t.end() + len(">")]
        pos = t.end()
    raise AssertionError(f"element {sid} never closes ({pos})")


def id_ancestors(page: str) -> dict[str, tuple[tuple[str, str | None], ...]]:
    """Every id on *page* with the chain of elements around it, outermost first, each as
    `(tag, id or None)`: what a hash link's script walks (`details` to open, a `tabpanel` to
    select). Void elements open nothing."""
    from html.parser import HTMLParser

    void = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "wbr"}

    class P(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.stack: list[tuple[str, str | None]] = []
            self.found: dict[str, tuple[tuple[str, str | None], ...]] = {}

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            ident = dict(attrs).get("id")
            if ident:
                self.found[ident] = tuple(self.stack)
            if tag not in void:
                self.stack.append((tag, ident))

        def handle_endtag(self, tag: str) -> None:
            while self.stack and self.stack.pop()[0] != tag:
                pass

    p = P()
    p.feed(page)
    return p.found
