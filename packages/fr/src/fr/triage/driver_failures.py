"""`fr triage drive failures --file --yes`: one tracking issue per driver-failure cause
(spec 2026-11-19-batch-train-truth R10).

The ledger (`fr.triage.driver_record`) counts every refusal, transient failure and crash by
cause. Filing turns each recurring cause into tracked improvement work, in the scope's state
repo when it has one, else in the scope's repo:

- a cause with no issue gets one (or adopts an open one carrying its marker, so two hosts
  never file the same cause twice);
- a cause whose open issue was filed at a lower count gets one comment with the new count;
- a cause whose issue was closed and that recurred gets a new issue naming the closed one
  (or adopts the open one another host already filed for it); one that did not recur since
  its filing is left closed.

A forge error mid-filing stops the filing: what was filed before it is in the returned
ledger, and the error is the result's last line (`Filing.error`), never a traceback.

An issue carries the label `fr:driver-failure`, a hidden marker `fr-driver-failure:<cause>`,
the cause, kind, counts, dates, fr version and exception class, and never the failure's
message: messages carry heads, paths and hosts. Every forge call goes through the target's
`GhClient`; with `write=False` nothing is written and the plan is returned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

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
    error: str | None = None  # the forge error that stopped the filing, if one did


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
    except Exception as exc:  # noqa: BLE001 - every backend's error: nothing was written
        return Filing([f"nothing filed in {repo}: its open issues could not be read: {exc}"],
                      error=str(exc))  # fmt: skip
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

    def adopt(cause: str, entry: Cause, found: int) -> None:  # filed from another host
        if write:
            entry.issue = f"{repo}#{found}"
            out.changed = True
        out.lines.append(f"{cause}: {verb}adopt {repo}#{found}")
        if comments_ok and write and entry.count > entry.filed_count:
            comment(cause, entry, found)

    def one(cause: str, entry: Cause) -> None:
        number = _number(entry.issue) if entry.issue else None
        if entry.issue and entry.issue.startswith(f"{repo}#") and number is not None:
            state = _view_state(client, repo, number)
            if state == "CLOSED":
                closed = entry.issue
                if entry.count <= entry.filed_count:  # nothing since its filing (p1a-r3)
                    out.lines.append(f"{cause}: {closed} closed, no recurrence")
                    return
                if cause in by_marker:  # another host re-filed it already (p1a-r4)
                    adopt(cause, entry, by_marker[cause])
                    return
                create(cause, entry, closed)
                out.lines.append(f"{cause}: {verb}file a new issue (it recurred after {closed} "
                                 "was closed)")  # fmt: skip
                return
            if entry.count > entry.filed_count:
                if not comments_ok:
                    out.lines.append(f"{cause}: {entry.issue} not commented: "
                                     f"{policy.block('comments')}")  # fmt: skip
                    return
                comment(cause, entry, number)
                out.lines.append(f"{cause}: {verb}comment the count {entry.count} on {entry.issue}")
                return
            out.lines.append(f"{cause}: {entry.issue} is up to date ({entry.count})")
            return
        if cause in by_marker:  # filed from another host: adopt it
            adopt(cause, entry, by_marker[cause])
            return
        create(cause, entry, None)
        shown = f" as {entry.issue}" if write and entry.issue else ""
        out.lines.append(f"{cause}: {verb}file an issue in {repo}{shown}")

    for cause, entry in ledger.by_count():
        try:
            one(cause, entry)
        except Exception as exc:  # noqa: BLE001 - every backend's error: keep what was done
            out.lines.append(f"{cause}: the forge failed, filing stopped: {exc}")
            out.error = str(exc)
            break
    return out


def _view_state(client: GhClient, repo: str, number: int) -> str:
    return str(client.view_issue(repo, number).get("state", "")).upper()
