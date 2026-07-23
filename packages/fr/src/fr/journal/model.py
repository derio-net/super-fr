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

from pydantic import BaseModel, ConfigDict, model_validator

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
        fields[key] = value
    return fields


def parse_journal(text: str) -> list[JournalEntry]:
    """Parse a journal file body into entries, in file order.

    Content before the first delimiter (a title/preamble) is ignored, so a
    journal can carry a human header. A delimiter with an unparseable header
    raises ``JournalParseError``.
    """
    entries: list[JournalEntry] = []
    lines = text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if not (line.startswith(_DELIM_PREFIX) and line.rstrip().endswith(_DELIM_SUFFIX)):
            i += 1
            continue
        fields = _parse_header(line.rstrip())
        # Body = the lines up to the next delimiter (or EOF), minus the
        # auto-generated `### ...` heading and surrounding blank lines.
        j = i + 1
        block: list[str] = []
        while j < n and not lines[j].startswith(_DELIM_PREFIX):
            block.append(lines[j])
            j += 1
        # Drop the heading line (first non-blank) and blank padding.
        while block and block[0].strip() == "":
            block.pop(0)
        if block and block[0].startswith("### "):
            block.pop(0)
        while block and block[0].strip() == "":
            block.pop(0)
        while block and block[-1].strip() == "":
            block.pop()
        try:
            entries.append(
                JournalEntry(
                    kind=fields["kind"],  # type: ignore[arg-type]
                    scope=fields["scope"],  # type: ignore[arg-type]
                    id=fields["id"],
                    created=fields["created"],
                    phase=int(fields["phase"]) if "phase" in fields else None,
                    title=_title_from_heading(text, fields["id"]),
                    body="\n".join(block),
                    state=fields.get("state"),  # type: ignore[arg-type]
                )
            )
        except KeyError as e:
            raise JournalParseError(f"journal entry missing required field: {e}") from e
        i = j
    return entries


def _title_from_heading(text: str, entry_id: str) -> str:
    """Recover an entry's title from its ``### <id> · <kind>[ ...] · <title>`` heading."""
    for line in text.splitlines():
        if line.startswith(f"### {entry_id} · "):
            # title is the segment after the last ' · ', minus any trailing
            # ` (phase N)` suffix the serializer appended.
            title = line.split(" · ", 2)[-1]
            if title.endswith(")") and " (phase " in title:
                title = title[: title.rindex(" (phase ")]
            return title
    return ""
