"""Journal entry schema, scope→path resolution, and serialize/parse.

Design rules mirror ``fr/types.py``:
  - ``frozen=True``    -- entries are immutable values.
  - ``extra="forbid"`` -- closed-world schema; an unknown field fails loud.

Storage format (Phase 1, task 3): each entry is one Markdown block introduced
by an HTML-comment delimiter carrying the machine header, e.g.::

    <!-- fr:journal kind=finding scope=plan id=f1 created=2026-07-22T10:00:00 phase=2 state=open -->
    ### f1 · finding · title
    body...

The comment keeps the header out of the rendered Markdown while remaining
deterministically parseable; the body below is what a human reads.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, PrivateAttr, ValidationError, model_validator

JournalKind = Literal[
    "decision",
    "review",
    "discovery",
    "finding",
    "repro",
    "hypothesis",
    "ruled-out",
    "root-cause",
]
JournalScope = Literal["spec", "plan", "debug"]
FindingState = Literal["fixed", "refuted", "open"]

JOURNALS_REL = Path("docs/superpowers/journals")
IMPLEMENTED_JOURNALS_REL = Path("docs/superpowers/implemented/journals")

# Each scope gets its own subdirectory so a bare `ls journals/` tells you which
# journal is which at a glance (a debug-slug and a plan-slug can otherwise look
# identical). Mirrors the `specs/` + `plans/` split of the parent tree.
_SCOPE_DIR: dict[str, str] = {"spec": "specs", "plan": "plans", "debug": "debug"}

# Specs are written `<YYYY-MM-DD-slug>-design.md`, but the spec-scope journal is
# keyed by the bare feature slug (`journals/specs/<slug>.md`). Own the suffix in
# one place so the archive sweep and any journal reader agree (#417).
_SPEC_FILENAME_SUFFIX = "-design"


def spec_journal_slug(spec_stem: str) -> str:
    """The spec-scope journal slug for a spec file's stem.

    A spec `2026-07-24-x-design.md` (stem `2026-07-24-x-design`) owns the
    journal `journals/specs/2026-07-24-x.md`, so strip a trailing ``-design``.
    A stem without the suffix (an older or hand-named spec) maps to itself, so
    the helper is safe to apply to every spec.
    """
    if spec_stem.endswith(_SPEC_FILENAME_SUFFIX):
        return spec_stem[: -len(_SPEC_FILENAME_SUFFIX)]
    return spec_stem


class JournalParseError(Exception):
    """Raised when a journal file cannot be parsed into entries."""


class JournalEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: JournalKind
    scope: JournalScope
    id: str
    created: str  # ISO 8601; kept as a string for round-trip stability
    phase: int | None = None
    title: str
    body: str = ""
    # Present ONLY on `finding` entries (fixed | refuted | open).
    state: FindingState | None = None
    # Legacy headings may retain an old finding state. Read-only consumers may
    # use them, but a canonical full-file rewrite must refuse them.
    _rewrite_safe: bool = PrivateAttr(default=True)

    @model_validator(mode="after")
    def _finding_state_coupling(self) -> JournalEntry:
        if self.kind == "finding" and self.state is None:
            raise ValueError("a `finding` entry requires a `state` (fixed|refuted|open)")
        if self.kind != "finding" and self.state is not None:
            raise ValueError(f"`state` is only valid on `finding` entries, not `{self.kind}`")
        # The delimiter header is space-delimited `key=value` tokens, so an id
        # with whitespace would corrupt the round-trip (F3, review 2026-07-23).
        if not self.id or any(c.isspace() for c in self.id):
            raise ValueError(
                f"journal id must be a non-empty whitespace-free token, got {self.id!r}"
            )
        return self


def journal_path(repo_root: Path, scope: JournalScope, slug: str) -> Path:
    """Active journal path: ``docs/superpowers/journals/<scope-dir>/<slug>.md``.

    The scope names a subdirectory (``specs`` / ``plans`` / ``debug``) so the
    tree is glanceable and a debug-slug can never be mistaken for a plan-slug.
    """
    return repo_root / JOURNALS_REL / _SCOPE_DIR[scope] / f"{slug}.md"


def archived_journal_path(repo_root: Path, scope: JournalScope, slug: str) -> Path:
    """Archived journal path (mirrors ``implemented/plans`` / ``implemented/specs``)."""
    return repo_root / IMPLEMENTED_JOURNALS_REL / _SCOPE_DIR[scope] / f"{slug}.md"


def resolve_journal_read_path(repo_root: Path, scope: JournalScope, slug: str) -> Path:
    """Path to read a journal from: the active location if present, else the
    archived one.

    ``add`` always writes the active path, but a journal outlives its spec/plan:
    once archived it lives under ``implemented/journals/<scope>/``. Reads
    (``render`` / ``check``) resolve through here so they still find it. When
    neither exists the active path is returned (callers treat a missing file as
    an empty journal), keeping behaviour identical for never-written slugs.
    """
    active = journal_path(repo_root, scope, slug)
    if active.exists():
        return active
    archived = archived_journal_path(repo_root, scope, slug)
    if archived.exists():
        return archived
    return active


# --- serialization -------------------------------------------------------

_DELIM_PREFIX = "<!-- fr:journal "
_DELIM_SUFFIX = " -->"
# Header fields serialized into the delimiter comment, in a stable order.
_HEADER_FIELDS = ("kind", "scope", "id", "created", "phase", "state")


def serialize_entry(entry: JournalEntry) -> str:
    """Render one entry as a delimiter comment + a Markdown body block."""
    parts: list[str] = []
    for field in _HEADER_FIELDS:
        value = getattr(entry, field)
        if value is None:
            continue
        parts.append(f"{field}={value}")
    header = _DELIM_PREFIX + " ".join(parts) + _DELIM_SUFFIX
    phase_bit = f" (phase {entry.phase})" if entry.phase is not None else ""
    state_bit = f" [{entry.state}]" if entry.state is not None else ""
    heading = f"### {entry.id} · {entry.kind}{state_bit} · {entry.title}{phase_bit}"
    body = entry.body.rstrip("\n")
    return f"{header}\n{heading}\n\n{body}\n" if body else f"{header}\n{heading}\n"


def _parse_header(line: str) -> dict[str, str]:
    inner = line[len(_DELIM_PREFIX) : -len(_DELIM_SUFFIX)].strip()
    fields: dict[str, str] = {}
    for token in inner.split(" "):
        if not token:
            continue
        key, sep, value = token.partition("=")
        if not sep:
            raise JournalParseError(f"malformed journal header token: {token!r}")
        if key not in _HEADER_FIELDS:
            raise JournalParseError(f"unknown journal header field: {key!r}")
        if key in fields:
            raise JournalParseError(f"duplicate journal header field: {key!r}")
        fields[key] = value
    return fields


def _title_from_heading(block: list[str], fields: dict[str, str]) -> tuple[str, list[str], bool]:
    """Parse an entry heading and report whether canonical rewrite is safe."""
    while block and block[0].strip() == "":
        block.pop(0)
    if not block or not block[0].startswith("### "):
        raise JournalParseError("journal entry is missing its canonical heading")

    heading = block.pop(0)
    prefix = f"### {fields['id']} · {fields['kind']}"
    if not heading.startswith(prefix):
        raise JournalParseError(f"journal heading does not match its header: {heading!r}")
    remainder = heading[len(prefix) :]
    state = fields.get("state")
    rewrite_safe = True
    if state is None:
        if not remainder.startswith(" · "):
            raise JournalParseError(f"journal heading does not match its header: {heading!r}")
        title = remainder[3:]
    else:
        if not remainder.startswith(" [") or " · " not in remainder:
            raise JournalParseError(f"journal heading does not match its header: {heading!r}")
        heading_state, separator, title = remainder[2:].partition("] · ")
        if not separator or not title or heading_state not in {"fixed", "refuted", "open"}:
            raise JournalParseError(f"journal heading does not match its header: {heading!r}")
        rewrite_safe = heading_state == state
    if "phase" in fields:
        phase_suffix = f" (phase {fields['phase']})"
        if not title.endswith(phase_suffix):
            raise JournalParseError(f"journal heading does not match its header: {heading!r}")
        title = title[: -len(phase_suffix)]
    return title, block, rewrite_safe


def parse_journal(text: str) -> list[JournalEntry]:
    """Parse a journal file body into entries, in file order.

    Content before the first delimiter (a title/preamble) is ignored, so a
    journal can carry a human header. A delimiter with an unparseable header
    raises ``JournalParseError``.
    """
    entries: list[JournalEntry] = []
    entry_ids: set[str] = set()
    lines = text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.startswith(_DELIM_PREFIX):
            i += 1
            continue
        if not line.rstrip().endswith(_DELIM_SUFFIX):
            raise JournalParseError(f"unterminated journal delimiter: {line!r}")
        fields = _parse_header(line.rstrip())
        # Body = the lines up to the next delimiter (or EOF), minus the
        # auto-generated `### ...` heading and surrounding blank lines.
        j = i + 1
        block: list[str] = []
        while j < n and not lines[j].startswith(_DELIM_PREFIX):
            block.append(lines[j])
            j += 1
        try:
            title, block, rewrite_safe = _title_from_heading(block, fields)
        except KeyError as e:
            raise JournalParseError(f"journal entry missing required field: {e}") from e
        while block and block[0].strip() == "":
            block.pop(0)
        while block and block[-1].strip() == "":
            block.pop()
        try:
            entry = JournalEntry(
                kind=fields["kind"],  # type: ignore[arg-type]
                scope=fields["scope"],  # type: ignore[arg-type]
                id=fields["id"],
                created=fields["created"],
                phase=int(fields["phase"]) if "phase" in fields else None,
                title=title,
                body="\n".join(block),
                state=fields.get("state"),  # type: ignore[arg-type]
            )
        except KeyError as e:
            raise JournalParseError(f"journal entry missing required field: {e}") from e
        except ValidationError as e:
            raise JournalParseError(f"invalid journal entry: {e}") from e
        entry._rewrite_safe = rewrite_safe
        if entry.id in entry_ids:
            raise JournalParseError(f"duplicate journal entry id: {entry.id!r}")
        entry_ids.add(entry.id)
        entries.append(entry)
        i = j
    return entries


def _handoff_line(entry: JournalEntry) -> str:
    """One-line collapse of an entry: id, kind, state, title, phase."""
    state_bit = f" [{entry.state}]" if entry.state is not None else ""
    phase_bit = f" (phase {entry.phase})" if entry.phase is not None else " (unphased)"
    return f"- {entry.id} · {entry.kind}{state_bit} · {entry.title}{phase_bit}"


def compose_handoff(
    entries: list[JournalEntry],
    *,
    phase: int,
    scope: str,
    slug: str,
    depends_on: tuple[int, ...] = (),
) -> str:
    """Compose the curated executor handoff for `phase` from parsed `entries`.

    Dependency-scoped, not recency-scoped: an entry is *relevant* when it is
    open (actionable anywhere), untagged (global), or tagged to this phase or
    one it depends on. Relevant entries render in full; everything else
    collapses to one line each, so a phase-10 executor stops re-reading 39
    fixed findings in full. Empty sections are omitted; the raw-render
    pointer is always present, so the full file is one command away.

    Pure — no I/O. `fr journal handoff` resolves the journal and the plan's
    `depends_on`, then calls this.
    """
    relevant = {phase, *depends_on}
    open_findings: list[str] = []
    context: list[str] = []
    collapsed: list[str] = []
    for e in entries:
        if e.kind == "finding" and e.state == "open":
            open_findings.append(serialize_entry(e))
        elif e.phase is None or e.phase in relevant:
            context.append(serialize_entry(e))
        else:
            collapsed.append(_handoff_line(e))
    parts = [f"# Handoff (phase {phase})"]
    if open_findings:
        parts.append("## Open findings\n\n" + "\n".join(open_findings))
    if context:
        parts.append("## Relevant context\n\n" + "\n".join(context))
    if collapsed:
        parts.append("## Earlier history\n\n" + "\n".join(collapsed))
    parts.append(
        f"## Full journal\n\nRaw render: `fr journal render --scope {scope} --slug {slug}`"
    )
    return "\n\n".join(parts) + "\n"
