"""`git.push: ask` / `git.pr: ask` (spec 2026-11-04-repo-feature-settings R11).

Each push or PR creation fr performs proceeds only on a verified operator answer
given after its request was printed:

1. The first attempt prints a `RemoteWriteRequest` and refuses. The request (its
   id, the head it was made at, the time it was printed) is kept in the git dir,
   never committed: a committed request would move HEAD and so its own id.
2. The approval is a decision in the run's OWN journal (`ApprovalJournal`): the
   spec journal of a spec-driven run, the debug journal of an fr-debugging session
   (which has no spec, review p4-r5), with the request's id and
   `answered_by: operator` (`decided_by=operator`), created after the request.
3. fr reads the session transcript (`answered_rounds_since`) for an ANSWERED
   question since the request whose text names the request id, and the answer to
   THAT question, read structurally as a (question, answer) pair, must be exactly
   `Approve <request-id>` (`approval_label`) after trimming whitespace (review
   p4-r3: any answer, to any question, was accepted before). Answers to other
   questions are ignored. Where the pairs cannot be read, or the transcript cannot
   be read at all, the request is refused naming the harness. There is no
   `--no-questions` bypass.

A push request goes stale when a commit other than journal bookkeeping lands
after it: the operator approved pushing what was there, not what came later.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from fr.artifacts.paths import KIND_DIRS
from fr.run.telemetry import Round, answered_rounds_since

RequestKind = Literal["push", "pr"]
ApprovalScope = Literal["spec", "debug"]


@dataclass(frozen=True)
class ApprovalJournal:
    """Where a request's approval is recorded and read: the run's own journal."""

    scope: ApprovalScope
    slug: str


JOURNALS_PREFIX = f"{KIND_DIRS['journal']}/"
"""Commits after a push request that touch only this tree (the approval itself) keep it."""

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


class AskRefusedError(Exception):
    """The remote write is not (yet) approved; the message says what to do."""


@dataclass(frozen=True)
class RemoteWriteRequest:
    """One push or PR request, shared by `fr push` and `fr pr create`."""

    kind: RequestKind
    id: str
    branch: str
    head: str
    at: str
    """`journal_now()` stamp of when the request was printed."""
    scope: ApprovalScope
    slug: str
    """The journal the approval goes in (`ApprovalJournal`)."""

    def journal_command(self) -> str:
        what = "push" if self.kind == "push" else "PR creation"
        return (
            f"fr journal add --scope {self.scope} --slug {self.slug} --kind decision "
            f"--id {self.id} --title {_quote(f'operator approved the {what}')} "
            "--answered-by operator"
        )

    def text(self) -> str:
        what = (
            f"push {self.branch} at {self.head[:12]}"
            if self.kind == "push"
            else f"open a draft PR for {self.branch}"
        )
        setting = "git.push" if self.kind == "push" else "git.pr"
        return "\n".join(
            [
                f"fr asks before it writes to the remote ({setting}: ask): request {self.id}.",
                f"  Ask the operator, with your harness's question tool, whether fr may {what}:",
                f"  put the request id {self.id} in the question text, and offer exactly the",
                f"  option {approval_label(self.id)!r} plus a decline option. Only that exact",
                "  answer to that question approves.",
                "  When the operator approves, record it, then run this command again:",
                f"    {self.journal_command()}",
            ]
        )


def _quote(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


def _safe(branch: str) -> str:
    return _UNSAFE.sub("-", branch).strip("-") or "branch"


def request_id(kind: RequestKind, branch: str, head: str) -> str:
    """`<kind>-<branch>-<head sha[:12]>`: a journal id, so one token. The head makes
    each request's id new (journal ids are create-only, so a `pr-<branch>` id could
    only ever be approved once, review p4-r4)."""
    return f"{kind}-{_safe(branch)}-{head[:12]}"


def _store(git_dir: Path, kind: RequestKind, branch: str) -> Path:
    return git_dir / "fr" / "requests" / f"{kind}-{_safe(branch)}.json"


def _load(path: Path) -> RemoteWriteRequest | None:
    try:
        return RemoteWriteRequest(**json.loads(path.read_text()))
    except (OSError, ValueError, TypeError):
        return None


def consume(git_dir: Path, kind: RequestKind, branch: str) -> None:
    """Forget the request once the write it approved was made."""
    _store(git_dir, kind, branch).unlink(missing_ok=True)


def _approved(repo_root: Path, request: RemoteWriteRequest) -> bool:
    from fr.journal.model import (
        JournalParseError,
        journal_stamp_as_utc,
        parse_journal,
        resolve_journal_read_path,
    )

    path = resolve_journal_read_path(repo_root, request.scope, request.slug)
    try:
        entries = parse_journal(path.read_text())
    except FileNotFoundError:
        return False
    except (OSError, JournalParseError) as e:
        raise AskRefusedError(f"cannot read the {request.scope} journal {path}: {e}") from e
    since = journal_stamp_as_utc(request.at)
    return any(
        e.kind == "decision"
        and e.id == request.id
        and e.decided_by == "operator"
        and journal_stamp_as_utc(e.created) >= since
        for e in entries
    )


def approval_label(request_id: str) -> str:
    """The one answer that approves a request: fr names it, the agent offers it."""
    return f"Approve {request_id}"


def answers_to(round_: Round, request_id: str) -> list[str] | None:
    """The operator's answers to the question(s) of *round_* whose text names
    *request_id*, read from the round's structural (question, answer) pairs.
    Answers to other questions are ignored. `None` when the pairs are not readable."""
    if round_.answer_pairs is None:
        return None
    return [a for q, a in round_.answer_pairs if request_id in q]


def approves(question_answers: list[str], request_id: str) -> bool:
    """Exactly the label, after trimming whitespace: nothing else approves."""
    label = approval_label(request_id)
    return bool(question_answers) and all(a.strip() == label for a in question_answers)


def require_approval(
    repo_root: Path,
    *,
    kind: RequestKind,
    branch: str,
    head: str,
    journal: ApprovalJournal | str,
    git_dir: Path,
    still_current: bool,
    env: Mapping[str, str] | None = None,
) -> RemoteWriteRequest:
    """The approved request, or `AskRefusedError` (after printing a new request when
    there was none, or it went stale). *still_current* says whether a stored push
    request still covers HEAD (the caller checked the commits after it). *journal* is
    where the approval goes, or why the branch has none (a refusal)."""
    from fr.journal.model import journal_now, journal_stamp_as_utc

    env = os.environ if env is None else env
    if isinstance(journal, str):
        raise AskRefusedError(
            f"{kind}: ask records the operator's approval in the run's own journal (the "
            f"spec journal, or a debugging session's debug journal): {journal}"
        )
    path = _store(git_dir, kind, branch)
    request = _load(path)
    if (
        request is None
        or not still_current
        or (request.scope, request.slug) != (journal.scope, journal.slug)
    ):
        request = RemoteWriteRequest(
            kind=kind,
            id=request_id(kind, branch, head),
            branch=branch,
            head=head,
            at=journal_now(),
            scope=journal.scope,
            slug=journal.slug,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(request)))
        raise AskRefusedError(request.text())
    if not _approved(repo_root, request):
        raise AskRefusedError(request.text())
    rounds = answered_rounds_since(env, journal_stamp_as_utc(request.at))
    if rounds is not None:
        asked = [r for r in rounds if any(request.id in q for q in r.question_texts)]
        if not asked:
            raise AskRefusedError(
                f"request {request.id}: no answered question naming {request.id} in this "
                f"session's transcript since {request.at}. The decision says the operator "
                "approved; fr can read the transcript here and it does not show it. Ask the "
                "operator, with the request id in the question, then run this again."
            )
        paired = [answers_to(r, request.id) for r in asked]
        if all(p is not None for p in paired):
            said = [a for p in paired if p is not None for a in p]
            if approves(said, request.id):
                return request
            saw = next((a for a in said if a.strip() != approval_label(request.id)), None)
            raise AskRefusedError(
                f"request {request.id}: the operator's answer to the question naming it was "
                + (f"{saw!r}" if saw is not None else "not found")
                + f", not {approval_label(request.id)!r}. Only that exact option approves; "
                f"fr will not {request.kind} on it."
            )
        # The answers cannot be paired with their questions here: treated as an
        # unreadable transcript, below. Never the id match alone.
    from fr.harness.detect import detect_harness
    from fr.harness.model import HarnessError

    try:
        harness = detect_harness(env) or "an unrecognised harness"
    except HarnessError as e:
        harness = str(e)
    raise AskRefusedError(
        f"request {request.id}: fr cannot read the operator's answer on {harness}, so "
        f"`git.{kind}: ask` refuses here (an unverified approval is no approval; there is "
        "no --no-questions bypass). Run it from a session whose transcript fr can read, "
        f"or make the {kind} yourself."
    )


def stored(git_dir: Path, kind: RequestKind, branch: str) -> RemoteWriteRequest | None:
    return _load(_store(git_dir, kind, branch))
