"""`git.push: ask` / `git.pr: ask` (spec 2026-11-04-repo-feature-settings R11).

Each push or PR creation fr performs proceeds only on a verified operator answer
given after its request was printed:

1. The first attempt prints a `RemoteWriteRequest` and refuses. The request (its
   id, the head it was made at, the time it was printed) is kept in the git dir,
   never committed: a committed request would move HEAD and so its own id.
2. The approval is a spec-journal decision with the request's id and
   `answered_by: operator` (`decided_by=operator`), created after the request.
3. fr reads the session transcript (`operator_answered_since`) for an operator
   answer since the request. Not observable is a refusal naming the harness; there
   is no `--no-questions` bypass.

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

from fr.run.telemetry import operator_answered_since

RequestKind = Literal["push", "pr"]

JOURNALS_PREFIX = "docs/superpowers/journals/"
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
    spec_slug: str

    def journal_command(self) -> str:
        what = "push" if self.kind == "push" else "PR creation"
        return (
            f"fr journal add --scope spec --slug {self.spec_slug} --kind decision "
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
                f"  Ask the operator, with your harness's question tool, whether fr may {what}.",
                "  When the operator approves, record it, then run this command again:",
                f"    {self.journal_command()}",
            ]
        )


def _quote(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


def _safe(branch: str) -> str:
    return _UNSAFE.sub("-", branch).strip("-") or "branch"


def request_id(kind: RequestKind, branch: str, head: str) -> str:
    """`push-<branch>-<head sha[:12]>` / `pr-<branch>`: a journal id, so one token."""
    return f"push-{_safe(branch)}-{head[:12]}" if kind == "push" else f"pr-{_safe(branch)}"


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

    path = resolve_journal_read_path(repo_root, "spec", request.spec_slug)
    try:
        entries = parse_journal(path.read_text())
    except FileNotFoundError:
        return False
    except (OSError, JournalParseError) as e:
        raise AskRefusedError(f"cannot read the spec journal {path}: {e}") from e
    since = journal_stamp_as_utc(request.at)
    return any(
        e.kind == "decision"
        and e.id == request.id
        and e.decided_by == "operator"
        and journal_stamp_as_utc(e.created) >= since
        for e in entries
    )


def require_approval(
    repo_root: Path,
    *,
    kind: RequestKind,
    branch: str,
    head: str,
    spec_slug: str | None,
    git_dir: Path,
    still_current: bool,
    env: Mapping[str, str] | None = None,
) -> RemoteWriteRequest:
    """The approved request, or `AskRefusedError` (after printing a new request when
    there was none, or it went stale). *still_current* says whether a stored push
    request still covers HEAD (the caller checked the commits after it)."""
    from fr.journal.model import journal_now, journal_stamp_as_utc

    env = os.environ if env is None else env
    if spec_slug is None:
        raise AskRefusedError(
            f"{kind}: ask needs the run's spec journal to record the operator's approval, "
            "and this run has no spec yet"
        )
    path = _store(git_dir, kind, branch)
    request = _load(path)
    if request is None or not still_current or request.spec_slug != spec_slug:
        request = RemoteWriteRequest(
            kind=kind,
            id=request_id(kind, branch, head),
            branch=branch,
            head=head,
            at=journal_now(),
            spec_slug=spec_slug,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(request)))
        raise AskRefusedError(request.text())
    if not _approved(repo_root, request):
        raise AskRefusedError(request.text())
    observed = operator_answered_since(env, journal_stamp_as_utc(request.at))
    if observed is True:
        return request
    if observed is False:
        raise AskRefusedError(
            f"request {request.id}: no answered question in this session's transcript since "
            f"{request.at}. The decision says the operator approved; fr can read the "
            "transcript here and it does not show it. Ask the operator, then run this again."
        )
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
