"""Open ends an archive leaves behind — listing and selecting them (spec
2026-10-06-archive-followups-design §C, R8–R9).

An *open end* is a finding whose folded state is `open` or `out-of-scope` in a
journal an archive moved. Its qualified id, `<scope>/<slug>/<id>`, is the one
token the issue marker, the closeout brief and `fr archive --issues` share:
finding ids are unique only within one journal, and one `--branch` archive
moves a spec journal and a plan journal.

Pure reads — nothing here touches the forge or writes a journal."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fr.journal.model import (
    IMPLEMENTED_JOURNALS_REL,
    SCOPE_DIRS,
    JournalEntry,
    JournalParseError,
    effective_finding_states,
    parse_journal,
    resolve_journal_read_path,
)

__all__ = ["OpenEnd", "journals_from_log", "open_ends", "select"]

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
