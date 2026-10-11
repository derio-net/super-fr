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
    TRACKED_BY_RE,
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
    "FiledOwed",
    "OwedEnd",
    "file_owed_ends",
    "owed_ends",
    "owed_marker",
    "write_manual_owed",
    "write_owed_back",
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


# --- owed actions (spec 2026-10-11-debt-engine §E, R21, R22) -----------------
#
# Filed OUTSIDE the `--issues`/`--no-issues` selection: an owed action is the
# operator's, never this change's to drop, so archive always files it — unless
# the repo declares `tracking: none`, when the journal holds it.

_SAFE_REPO = re.compile(r"^[\w.][\w.-]*(/[\w.-]+)+$")
_TRAILING_NUMBER = re.compile(r"/(\d+)/?$")


@dataclass(frozen=True)
class OwedEnd:
    scope: str
    slug: str
    id: str
    title: str
    key: str
    what: str
    how: str
    path: Path


def owed_marker(key: str) -> str:
    """The body marker that identifies an owed action's issue (R21)."""
    return f"<!-- fr-owed:{key} -->"


def owed_ends(repo_root: Path, journals: list[tuple[str, str]]) -> list[OwedEnd]:
    """Every open `owed` entry of the named journals not yet filed, each once."""
    from fr.journal.model import open_owed_ids, owed_fields, owed_filed_as, owed_key

    out: list[OwedEnd] = []
    for scope, slug in journals:
        path = resolve_journal_read_path(repo_root, scope, slug)  # type: ignore[arg-type]
        entries = _entries(path)
        filed = owed_filed_as(entries)
        still = set(open_owed_ids(entries))
        for e in entries:
            key = owed_key(e) if e.kind == "owed" else None
            if key is None or e.id not in still or e.id in filed:
                continue
            if any(o.key == key for o in out):
                continue
            fields = owed_fields(e)
            out.append(
                OwedEnd(
                    scope,
                    slug,
                    e.id,
                    e.title,
                    key,
                    fields.get("what", ""),
                    fields.get("how", ""),
                    path,
                )
            )
    return out


@dataclass(frozen=True)
class FiledOwed:
    end: OwedEnd
    ref: str | None = None
    reused: bool = False
    error: str | None = None


def _issue_ref(repo: str, number: object, url: object) -> str | None:
    """`owner/repo#n` when that is a valid reference, else the URL; `None`
    when neither is."""
    if not isinstance(number, int) and isinstance(url, str):
        m = _TRAILING_NUMBER.search(url)
        number = int(m.group(1)) if m else None
    if isinstance(number, int):
        ref = f"{repo}#{number}"
        if TRACKED_BY_RE.match(ref):
            return ref
    return url if isinstance(url, str) and TRACKED_BY_RE.match(url) else None


_OWED_MARKER_LINE = re.compile(r"^<!-- fr-owed:(\S+) -->$")


def _existing_owed(gh: GhClient, repo: str) -> dict[str, str]:
    """`owed key -> ref` of the open issues THIS account filed whose last line
    is an owed marker — the same trust rule as `_existing_markers`."""
    try:
        me = gh.viewer_login()
        issues = gh.list_issues(repo, "open", 200, fields="number,url,body,author")
    except Exception:  # noqa: BLE001 — dedup is best-effort, as for open ends
        return {}
    if not me:
        return {}
    found: dict[str, str] = {}
    for issue in issues:
        author = issue.get("author")
        login = author.get("login") if isinstance(author, dict) else author
        body = str(issue.get("body") or "").rstrip()
        if login != me or not body:
            continue
        m = _OWED_MARKER_LINE.match(body.splitlines()[-1].strip())
        ref = _issue_ref(repo, issue.get("number"), issue.get("url")) if m else None
        if m and ref:
            found.setdefault(m.group(1), ref)
    return found


def _owed_body(end: OwedEnd, repo_root: Path) -> str:
    try:
        journal = end.path.relative_to(repo_root).as_posix()
    except ValueError:
        journal = end.path.as_posix()
    lines = [
        f"Owed: {end.what or end.title}",
        "",
        f"Complete it, then discharge it: `{end.how}`" if end.how else "Complete it.",
        "",
        f"Journal: `{journal}` (entry `{end.id}`)",
        "",
        owed_marker(end.key),
    ]
    return "\n".join(lines)


def file_owed_ends(
    repo_root: Path, ends: list[OwedEnd], gh: GhClient, repo: str
) -> list[FiledOwed]:
    """One `fr:owed` issue per owed action (R21), idempotent by its owed key:
    an open issue already carrying the key's marker is reused. `repo` must be
    an `owner/repo` path — it reaches the forge CLI's argv."""
    from fr.labels import FR_OWED

    if not ends:
        return []
    if not _SAFE_REPO.match(repo):
        return [FiledOwed(e, error=f"repo {repo!r} is not owner/repo") for e in ends]
    known = _existing_owed(gh, repo)
    labels = frozenset({FR_OWED.name})
    try:
        gh.ensure_labels(repo, [FR_OWED])
    except Exception:  # noqa: BLE001 — file without the label rather than not at all
        labels = frozenset()
    out: list[FiledOwed] = []
    for end in ends:
        hit = known.get(end.key)
        if hit is not None:
            out.append(FiledOwed(end, ref=hit, reused=True))
            continue
        try:
            url = gh.create_issue(
                repo,
                title=f"Owed: {end.title}",
                body=_owed_body(end, repo_root),
                labels=labels,
            )
        except Exception as e:  # noqa: BLE001 — a forge error is per action
            out.append(FiledOwed(end, error=str(e)))
            continue
        ref = _issue_ref(repo, None, url)
        if ref is None:
            out.append(FiledOwed(end, error=f"the forge returned no issue reference ({url!r})"))
            continue
        known[end.key] = ref
        out.append(FiledOwed(end, ref=ref))
    return out


def write_owed_back(filed: FiledOwed) -> Path:
    """Append the `open` record carrying `filed_as=<ref>` (still owed) to the
    owed entry's journal. Returns the journal path; the caller stages it."""
    assert filed.ref is not None
    path = filed.end.path
    entries = parse_journal(path.read_text())
    target = next(e for e in entries if e.id == filed.end.id and e.resolves is None)
    entry = resolution_entry(
        target=target,
        scope=filed.end.scope,  # type: ignore[arg-type]
        taken={e.id for e in entries},
        created=journal_now(),
        state="open",
        body=f"Filed at archive as {filed.ref}; still owed until discharged.",
        phase=target.phase,
        filed_as=filed.ref,
    )
    append_journal_entry(path, filed.end.slug, entry)
    return path


def write_manual_owed(repo_root: Path, plan_name: str, phases: list[int]) -> Path | None:
    """One `owed` entry `manual-phase-<n>` (key `plan:<name>#p<n>`) per unticked
    manual phase holding the plan, into its plan journal (R22). Idempotent: a
    phase that already has its entry is skipped. Returns the journal path when
    anything was written; the caller stages it."""
    from fr.journal.model import OWED_KEY_RE, journal_path, owed_body

    path = journal_path(repo_root, "plan", plan_name)
    if path.exists():
        entries = parse_journal(path.read_text())
    else:
        entries = []
    taken = {e.id for e in entries}
    wrote = False
    for n in phases:
        eid = f"manual-phase-{n}"
        key = f"plan:{plan_name}#p{n}"
        if eid in taken or not OWED_KEY_RE.match(key):
            continue
        entry = JournalEntry(
            kind="owed",
            scope="plan",
            id=eid,
            created=journal_now(),
            phase=n,
            title=f"{plan_name}: manual phase {n} is not ticked",
            body=owed_body(
                what=f"do manual phase {n} of {plan_name} and tick its steps",
                why="fr archive holds the plan until its manual phases are ticked",
                how=f"tick phase {n} (fr plan edit --tick), then fr archive "
                f"docs/superpowers/plans/{plan_name}",
                key=key,
            ),
        )
        append_journal_entry(path, plan_name, entry)
        taken.add(eid)
        wrote = True
    return path if wrote else None
