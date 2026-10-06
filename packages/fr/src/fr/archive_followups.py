"""Open ends an archive leaves behind — listing and selecting them (spec
2026-10-06-archive-followups-design §C, R8–R9).

An *open end* is a finding whose folded state is `open` or `out-of-scope` in a
journal an archive moved. Its qualified id, `<scope>/<slug>/<id>`, is the one
token the issue marker, the closeout brief and `fr archive --issues` share:
finding ids are unique only within one journal, and one `--branch` archive
moves a spec journal and a plan journal.

Listing and selection are pure reads. `file_open_ends` is the one place that
talks to the forge (through the `GhClient` it is handed), and `write_back` the
one that appends to a journal."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from fr.journal.model import (
    IMPLEMENTED_JOURNALS_REL,
    SCOPE_DIRS,
    JournalEntry,
    JournalParseError,
    append_journal_entry,
    effective_finding_states,
    journal_now,
    parse_journal,
    resolution_entry,
    resolve_journal_read_path,
)

if TYPE_CHECKING:
    from fr.ghclient import GhClient

__all__ = [
    "FOLLOW_UP_LABEL",
    "Filed",
    "OpenEnd",
    "context_for",
    "file_open_ends",
    "journals_from_log",
    "marker",
    "open_ends",
    "select",
    "write_back",
]

FOLLOW_UP_LABEL = "follow-up"

_OPEN_STATES = ("open", "out-of-scope")
_DIR_TO_SCOPE = {d: s for s, d in SCOPE_DIRS.items()}


@dataclass(frozen=True)
class OpenEnd:
    scope: str
    slug: str
    id: str
    title: str
    body: str
    state: str
    path: Path

    @property
    def qid(self) -> str:
        return f"{self.scope}/{self.slug}/{self.id}"


def journals_from_log(moves: list[tuple[Path, Path]]) -> list[tuple[str, str]]:
    """The `(scope, slug)` of every journal an archive moved, in move order —
    read off destinations under `implemented/journals/<scope-dir>/`."""
    found: list[tuple[str, str]] = []
    for _src, dst in moves:
        try:
            rel = dst.relative_to(IMPLEMENTED_JOURNALS_REL)
        except ValueError:
            continue
        if len(rel.parts) != 2 or rel.suffix != ".md":
            continue
        scope = _DIR_TO_SCOPE.get(rel.parts[0])
        if scope is not None and (scope, rel.stem) not in found:
            found.append((scope, rel.stem))
    return found


def _entries(path: Path) -> list[JournalEntry]:
    if not path.is_file():
        return []
    try:
        return parse_journal(path.read_text())
    except (JournalParseError, OSError):
        return []


def _ends_in(repo_root: Path, scope: str, slug: str) -> list[OpenEnd]:
    path = resolve_journal_read_path(repo_root, scope, slug)  # type: ignore[arg-type]
    entries = _entries(path)
    states = effective_finding_states(entries)
    ends: list[OpenEnd] = []
    for e in entries:
        if e.kind != "finding" or e.resolves is not None:
            continue
        if states.get(e.id) in _OPEN_STATES and not any(x.id == e.id for x in ends):
            ends.append(OpenEnd(scope, slug, e.id, e.title, e.body, str(states[e.id]), path))
    return ends


def open_ends(repo_root: Path, journals: list[tuple[str, str]]) -> list[OpenEnd]:
    """Every open or out-of-scope finding of the named journals (R8)."""
    return [end for scope, slug in journals for end in _ends_in(repo_root, scope, slug)]


def select(listed: list[OpenEnd], spec: str, repo_root: Path) -> tuple[list[OpenEnd], list[str]]:
    """Resolve an `--issues` value to open ends (R9): `all`, or a comma list of
    qualified ids (read from their journal, live or archived) and bare ids
    (accepted only when exactly one LISTED end carries it).

    Returns `(chosen, refusals)`. Any refusal means the caller files nothing."""
    if spec.strip() == "all":
        return list(listed), []
    chosen: list[OpenEnd] = []
    refused: list[str] = []
    for token in (t.strip() for t in spec.split(",")):
        if not token:
            continue
        end, why = _resolve_token(token, listed, repo_root)
        if end is None:
            refused.append(f"{token}: {why}")
        elif end not in chosen:
            chosen.append(end)
    return chosen, refused


def _resolve_token(
    token: str, listed: list[OpenEnd], repo_root: Path
) -> tuple[OpenEnd | None, str]:
    parts = token.split("/")
    if len(parts) == 1:
        hits = [e for e in listed if e.id == token]
        if len(hits) == 1:
            return hits[0], ""
        if not hits:
            return None, "no open or out-of-scope finding with that id among those listed"
        return None, "ambiguous — name one of " + ", ".join(e.qid for e in hits)
    if len(parts) != 3 or parts[0] not in SCOPE_DIRS or not all(parts):
        return None, "not a qualified id (expected <scope>/<slug>/<id>)"
    scope, slug, fid = parts
    hit = next((e for e in _ends_in(repo_root, scope, slug) if e.id == fid), None)
    if hit is None:
        return None, "no open or out-of-scope finding with that id in that journal"
    return hit, ""


def marker(end: OpenEnd) -> str:
    """The body marker that identifies an end's issue (R11)."""
    return f"<!-- fr:journal {end.qid} -->"


@dataclass(frozen=True)
class Filed:
    end: OpenEnd
    url: str | None = None
    reused: bool = False
    error: str | None = None


def _issue_body(end: OpenEnd, repo_root: Path, context: list[str]) -> str:
    try:
        journal = end.path.relative_to(repo_root).as_posix()
    except ValueError:
        journal = end.path.as_posix()
    lines = [end.body.strip() or end.title, "", f"Journal: `{journal}`"]
    lines.extend(f"Context: `{c}`" for c in context)
    lines += ["", marker(end)]
    return "\n".join(lines)


_MARKER_LINE = re.compile(r"^<!-- fr:journal (\S+) -->$")


def _existing_markers(gh: GhClient, repo: str) -> dict[str, str]:
    """`marker -> url` of the open issues THIS account filed that end in a
    marker line, exactly as `_issue_body` writes it. An issue anyone else wrote,
    or one that merely quotes a marker mid-body, is never reused — reuse hands
    its URL to `tracked_by`, so a third party could otherwise redirect it. Any
    error (no listing, no viewer) means no dedup, never a failure."""
    try:
        me = gh.viewer_login()
        issues = gh.list_issues(repo, "open", 200, fields="number,url,body,author")
    except Exception:  # noqa: BLE001 — dedup is best-effort by design (R11)
        return {}
    if not me:
        return {}
    found: dict[str, str] = {}
    for issue in issues:
        author = issue.get("author")
        login = author.get("login") if isinstance(author, dict) else author
        url, body = issue.get("url"), str(issue.get("body") or "").rstrip()
        if not url or login != me or not body:
            continue
        m = _MARKER_LINE.match(body.splitlines()[-1].strip())
        if m:
            found.setdefault(m.group(1), str(url))
    return found


def context_for(repo_root: Path, end: OpenEnd) -> list[str]:
    """The spec/plan the end belongs to, repo-relative, whichever location it
    is at now (archived or live) — independent of what this run moved."""
    root = Path("docs/superpowers")
    if end.scope == "plan":
        cands = [root / "implemented/plans" / end.slug, root / "plans" / end.slug]
        return [c.as_posix() for c in cands if (repo_root / c).is_dir()][:1]
    if end.scope == "spec":
        cands = [
            root / d / f"{end.slug}{suffix}"
            for d in ("implemented/specs", "specs")
            for suffix in ("-design.md", ".md")
        ]
        return [c.as_posix() for c in cands if (repo_root / c).is_file()][:1]
    return []


def file_open_ends(
    repo_root: Path,
    ends: list[OpenEnd],
    gh: GhClient,
    repo: str,
) -> list[Filed]:
    """One issue per end (R11): an open issue already carrying the end's
    marker is reused; a label that cannot be ensured is dropped; an error on
    one end is recorded on it and the rest proceed."""
    if not ends:
        return []
    known = _existing_markers(gh, repo)
    labels = frozenset({FOLLOW_UP_LABEL})
    try:
        gh.ensure_labels(repo, [FOLLOW_UP_LABEL])
    except Exception:  # noqa: BLE001 — file without the label rather than not at all
        labels = frozenset()
    out: list[Filed] = []
    for end in ends:
        hit = known.get(end.qid)
        if hit is not None:
            out.append(Filed(end, url=hit, reused=True))
            continue
        try:
            url = gh.create_issue(
                repo,
                title=end.title,
                body=_issue_body(end, repo_root, context_for(repo_root, end)),
                labels=labels,
            )
        except Exception as e:  # noqa: BLE001 — a forge error is per finding (R10)
            out.append(Filed(end, error=str(e)))
            continue
        known[end.qid] = url
        out.append(Filed(end, url=url))
    return out


def write_back(filed: Filed) -> Path:
    """Append the `deferred` record for a filed (or reused) end to its journal
    at its current location (R12), through the builder `fr journal resolve`
    uses. Returns the journal path; the caller stages it."""
    assert filed.url is not None
    path = filed.end.path
    entries = parse_journal(path.read_text())
    target = next(e for e in entries if e.id == filed.end.id and e.resolves is None)
    entry = resolution_entry(
        target=target,
        scope=filed.end.scope,  # type: ignore[arg-type]
        taken={e.id for e in entries},
        created=journal_now(),
        state="deferred",
        body=f"Filed at archive as {filed.url}.",
        tracked_by=filed.url,
    )
    append_journal_entry(path, filed.end.slug, entry)
    return path
