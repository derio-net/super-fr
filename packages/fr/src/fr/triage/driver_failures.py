"""`fr triage drive failures --file --yes`: one tracking issue per driver-failure cause
(spec 2026-11-19-batch-train-truth R10).

The ledger (`fr.triage.driver_record`) counts every refusal, transient failure and crash by
cause. Filing turns each recurring cause into tracked improvement work, in the scope's state
repo when it has one, else in the scope's repo:

- a cause with no issue gets one (or adopts an open one carrying its marker, so two hosts
  never file the same cause twice);
- a cause whose open issue was filed at a lower count gets one comment with the new count;
- a cause whose issue was closed and that recurred gets a new issue naming the closed one.

An issue carries the label `fr:driver-failure`, a hidden marker `fr-driver-failure:<cause>`,
the cause, kind, counts, dates, fr version and exception class, and never the failure's
message: messages carry heads, paths and hosts. Every forge call goes through the target's
`GhClient`; with `write=False` nothing is written and the plan is returned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from fr.ghclient import GhClient, ListingCapped
from fr.labels import LabelDef
from fr.settings.remote import RepoPolicy
from fr.triage.driver_record import Cause, Ledger

DRIVER_FAILURE = LabelDef(
    "fr:driver-failure", "B60205", "A wave-driver failure cause, filed from its ledger"
)
MARKER = "<!-- fr-driver-failure:{cause} -->"
SEARCH_LIMIT = 200


def marker(cause: str) -> str:
    return MARKER.format(cause=cause)


def _date(cause: Cause) -> tuple[str, str]:
    return cause.first.date().isoformat(), cause.last.date().isoformat()


def title(cause: str, entry: Cause) -> str:
    return f"wave driver: {entry.kind} `{cause}`"


def body(cause: str, entry: Cause, *, closed: str | None = None) -> str:
    """The issue's body: everything the ledger knows but the message."""
    first, last = _date(entry)
    lines = [
        marker(cause),
        "The wave driver (`fr triage batch drive`) recorded this failure cause in its ledger "
        "(`driver-failures.yaml`, in the scope's state directory on the driving host).",
        "",
        f"- cause: `{cause}`",
        f"- kind: {entry.kind}",
        f"- count: {entry.count}",
        f"- first seen: {first}",
        f"- last seen: {last}",
        f"- fr version: {entry.fr_version}",
        f"- exception: `{entry.exception or 'unknown'}`",
        "",
        "The failure's message is not included: it carries heads, paths and hosts. Read it in "
        "the ledger, `fr triage drive failures`.",
    ]
    if closed is not None:
        lines += ["", f"The cause recurred after {closed} was closed."]
    return "\n".join(lines) + "\n"


def _number(url_or_ref: str) -> int | None:
    match = re.search(r"(?:#|/issues/)(\d+)\s*$", url_or_ref)
    return int(match.group(1)) if match else None


@dataclass
class Filing:
    """What filing did (or, without `write`, would do), one line per cause."""

    lines: list[str]
    changed: bool = False


def file_failures(
    ledger: Ledger, client: GhClient, repo: str, policy: RepoPolicy, *, write: bool
) -> Filing:
    """File, comment or re-file every cause of *ledger* in *repo* (R10), updating the
    ledger's `issue` and `filed_count` when *write*. *policy* is the target's: `forge.issues`
    or `tracking: none` off files nothing, and says so."""
    blocked = policy.block("issues")
    if blocked is not None:
        return Filing([f"nothing filed in {repo}: {blocked}"])
    labels_ok = policy.allows("labels")
    comments_ok = policy.allows("comments")
    out = Filing([])
    labelled = False
    try:
        open_issues = client.list_open_issues_with_body(
            repo, search=("fr-driver-failure:",), limit=SEARCH_LIMIT
        )
    except ListingCapped as capped:  # a partial answer adopts what it found, files the rest
        open_issues = capped.issues
    by_marker: dict[str, int] = {}
    for issue in open_issues:
        for found in re.findall(r"<!-- fr-driver-failure:(\S+) -->", str(issue.get("body", ""))):
            by_marker.setdefault(found, int(issue["number"]))
    verb = "" if write else "would "

    def create(cause: str, entry: Cause, closed: str | None) -> None:
        nonlocal labelled
        if not write:
            return
        if labels_ok and not labelled:
            client.ensure_labels(repo, [DRIVER_FAILURE])
            labelled = True
        url = client.create_issue(
            repo,
            title=title(cause, entry),
            body=body(cause, entry, closed=closed),
            labels=frozenset({DRIVER_FAILURE.name}) if labels_ok else frozenset(),
        )
        number = _number(url)
        entry.issue = f"{repo}#{number}" if number is not None else url
        entry.filed_count = entry.count
        out.changed = True

    def comment(cause: str, entry: Cause, number: int) -> None:
        if not write:
            return
        _, last = _date(entry)
        client.comment_issue(
            repo, number,
            f"{marker(cause)}\nThe count of `{cause}` is now {entry.count} "
            f"(it was {entry.filed_count} when last filed); last seen {last}, "
            f"fr {entry.fr_version}.",
        )  # fmt: skip
        entry.filed_count = entry.count
        out.changed = True

    for cause, entry in ledger.by_count():
        number = _number(entry.issue) if entry.issue else None
        if entry.issue and entry.issue.startswith(f"{repo}#") and number is not None:
            state = str(_view_state(client, repo, number))
            if state == "CLOSED":
                closed = entry.issue
                create(cause, entry, closed)
                out.lines.append(f"{cause}: {verb}file a new issue (it recurred after {closed} "
                                 "was closed)")  # fmt: skip
                continue
            if entry.count > entry.filed_count:
                if not comments_ok:
                    out.lines.append(f"{cause}: {entry.issue} not commented: "
                                     f"{policy.block('comments')}")  # fmt: skip
                    continue
                comment(cause, entry, number)
                out.lines.append(f"{cause}: {verb}comment the count {entry.count} on {entry.issue}")
                continue
            out.lines.append(f"{cause}: {entry.issue} is up to date ({entry.count})")
            continue
        if cause in by_marker:  # filed from another host: adopt it
            found = by_marker[cause]
            if write:
                entry.issue = f"{repo}#{found}"
                out.changed = True
            out.lines.append(f"{cause}: {verb}adopt {repo}#{found}")
            if comments_ok and write and entry.count > entry.filed_count:
                comment(cause, entry, found)
            continue
        create(cause, entry, None)
        shown = f" as {entry.issue}" if write and entry.issue else ""
        out.lines.append(f"{cause}: {verb}file an issue in {repo}{shown}")
    return out


def _view_state(client: GhClient, repo: str, number: int) -> Any:
    return str(client.view_issue(repo, number).get("state", "")).upper()
