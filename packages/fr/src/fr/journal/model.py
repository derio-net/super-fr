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
    # A RESOLUTION RECORD names the finding it speaks about (spec §3.G.1). The
    # journal is an audit log: `fr journal resolve` appends one of these rather
    # than rewriting the finding, because a finding mutated in place erases
    # that it was ever open. `effective_finding_states` folds them.
    resolves: str | None = None

    @model_validator(mode="after")
    def _finding_state_coupling(self) -> JournalEntry:
        if self.kind == "finding" and self.state is None:
            raise ValueError("a `finding` entry requires a `state` (fixed|refuted|open)")
        if self.kind != "finding" and self.state is not None:
            raise ValueError(f"`state` is only valid on `finding` entries, not `{self.kind}`")
        if self.resolves is not None:
            if self.kind != "finding":
                raise ValueError(
                    f"`resolves` is only valid on `finding` entries, not `{self.kind}` "
                    "— a resolution record carries the state it resolves the finding to"
                )
            if any(c.isspace() for c in self.resolves) or not self.resolves:
                raise ValueError(
                    f"`resolves` must be a non-empty whitespace-free journal id, "
                    f"got {self.resolves!r}"
                )
            if self.resolves == self.id:
                raise ValueError(
                    f"entry `{self.id}` cannot resolve itself — a resolution record is a "
                    "SEPARATE entry naming the finding it closes"
                )
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
# `resolves` is appended LAST so every journal written before phase 7 keeps
# the byte-for-byte header it already has; an fr that predates the field reads
# the token and ignores it (`parse_journal` names the fields it wants), so an
# older reader sees a resolution record as an ordinary fixed/refuted finding.
_HEADER_FIELDS = ("kind", "scope", "id", "created", "phase", "state", "resolves")


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
    entry_ids: set[str] = set()
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
        # NAMED KEYS, NEVER `JournalEntry(**fields)` — this projection is
        # load-bearing, not style. `JournalEntry` is `extra="forbid"` (like
        # `RunState`), so splatting would make every future optional header
        # token a BREAKING change: an older fr would raise on a journal it used
        # to read. Because the fields are named here, an unknown token stays in
        # `fields` and never reaches the model, which is why a real fr 4.4.0
        # renders a journal full of `resolves=` records at exit 0 while the same
        # test against the run kind fails loudly. `test_journal_model.py::
        # test_a_header_token_this_fr_does_not_know_is_ignored_not_fatal` is the
        # guard; a refactor to `**fields` fails it immediately.
        try:
            entry = JournalEntry(
                kind=fields["kind"],  # type: ignore[arg-type]
                scope=fields["scope"],  # type: ignore[arg-type]
                id=fields["id"],
                created=fields["created"],
                phase=int(fields["phase"]) if "phase" in fields else None,
                title=_title_from_heading(text, fields["id"]),
                body="\n".join(block),
                state=fields.get("state"),  # type: ignore[arg-type]
                resolves=fields.get("resolves"),
            )
            if entry.id in entry_ids:
                raise JournalParseError(f"duplicate journal entry id: {entry.id!r}")
            entry_ids.add(entry.id)
            entries.append(entry)
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


# --- effective finding state (the fold) ----------------------------------


def effective_finding_states(entries: list[JournalEntry]) -> dict[str, FindingState]:
    """Each finding id → the state its LAST record gives it (spec §3.G.1).

    A *record* for a finding is either the finding entry itself or a later
    resolution record naming it through `resolves`. Entries arrive in file
    order, which for an append-only journal is chronological, so the fold is a
    left-to-right overwrite: resolved, then re-opened by a later record, reads
    open again.

    A record carrying `resolves` speaks about the finding it names and NOT
    about itself — otherwise resolving one finding would open a new one — so it
    never contributes its own id to the map. A record naming an id that has no
    entry still folds (a hand-spliced journal must not crash the gate);
    `fr journal resolve` refuses to write one.

    A journal with no resolution records — every journal written before this
    existed — folds to exactly each finding's own `state`.
    """
    states: dict[str, FindingState] = {}
    for e in entries:
        if e.resolves is not None:
            if e.state is not None:
                states[e.resolves] = e.state
        elif e.kind == "finding" and e.state is not None:
            states[e.id] = e.state
    return states


def open_finding_ids(entries: list[JournalEntry]) -> list[str]:
    """Findings whose EFFECTIVE state is open, in first-appearance order.

    First-appearance, not resolution order, so the gate's message stays stable
    as records accumulate.
    """
    states = effective_finding_states(entries)
    ordered: list[str] = []
    seen: set[str] = set()
    for e in entries:
        if e.kind != "finding":
            continue
        fid = e.resolves if e.resolves is not None else e.id
        if fid in seen:
            continue
        seen.add(fid)
        if states.get(fid) == "open":
            ordered.append(fid)
    return ordered


def append_journal_entry(path: Path, slug: str, entry: JournalEntry) -> None:
    """The ONE writer — `fr journal add`, `fr journal resolve`, and any test
    fixture built through `fr.test_support.build_plan_journal` all land here,
    so none of them can disagree about separators, the file header, or the
    serialized shape. A test fixture built by calling this (rather than
    formatting Markdown by hand) is a CAPTURE of the real serializer's
    output, not a guess that can drift from it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    block = serialize_entry(entry)
    if path.exists():
        prior = path.read_text()
        sep = "" if prior.endswith("\n\n") else ("\n" if prior.endswith("\n") else "\n\n")
        path.write_text(prior + sep + block)
    else:
        path.write_text(f"# Journal: {slug}\n\n{block}")


def _handoff_line(entry: JournalEntry, effective_state: str | None = None) -> str:
    """One-line collapse of an entry: id, kind, state, title, phase.

    `effective_state` overrides the entry's OWN state for display. A journal is
    an append-only log, so each record correctly states what was true when it
    was written and `serialize_entry` must keep printing that — but a handoff
    reports CURRENT state, and a finding written `open` that a later record
    closed is not open now. Showing the entry's own field there tells a phase-6
    executor to chase ten bugs that no longer exist, which is the cost this
    whole bound exists to remove (super-fr#464). Defaults to the entry's own
    state so non-finding callers are unaffected.
    """
    state = entry.state if effective_state is None else effective_state
    state_bit = f" [{state}]" if state is not None else ""
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

    **State first, then dependency** — a three-way decision, in this order:

    1. a finding whose EFFECTIVE state is open renders in full, wherever it is
       tagged: it is actionable anywhere;
    2. any other finding — effectively `fixed` or `refuted` — collapses to one
       line, *regardless of phase*: no phase relationship makes a closed bug
       actionable again. A resolution record collapses with it, with ONE
       exception: a record that RE-OPENS its target renders in full, because
       there the "it is history" rationale is simply false and collapsing it
       drops the only text saying why the finding is live again;
    3. every non-finding kind (decisions, discoveries, reviews, and the
       debug-scope kinds) keeps the dependency rule: it renders in full when
       untagged or tagged to this phase or one it depends on, and collapses
       otherwise.

    Rule 2 running *ahead of* the dependency test is the bound. Before it, state
    only routed a finding into `## Open findings`; past that, `{phase,
    *depends_on}` decided, so a `fixed` finding on a dependency phase rendered
    in full — and real plans depend on their predecessors, so the old
    docstring's "a phase-10 executor stops re-reading 39 fixed findings in full"
    held only for the non-dependency ones. Measured on a real SEVEN-phase
    journal (the category breakdown is spec §5.A3; §2 has the size-by-phase
    table), that left 38,020 chars across 30 closed findings inside phase 6's
    83,132-char handoff, describing bugs that no longer existed — the measured
    saving is 34,022. Now a closed entry costs O(1) characters however long its
    body is.

    The collapsed line reports the entry's EFFECTIVE state, not the state its
    own record carries. The journal is an append-only log, so a record rightly
    says what was true when it was written; a handoff reports what is true now.

    Decisions and discoveries stay dependency-scoped deliberately: a decision is
    never "closed" — it still constrains the phase that depends on it — and a
    discovery is a trap paid for once. Only findings have a lifecycle that makes
    them historical, so only findings collapse on state.

    Handoff size still GROWS with phase number, and that is not a bug to fix
    later (spec §5.A3): what remains is decisions and discoveries a later phase
    genuinely needs, and dropping them is the one failure the handoff contract
    ("missing anything → STOP, do not guess") exists to prevent.

    Empty sections are omitted; the raw-render pointer is always present, so the
    full file is one command away.

    Pure — no I/O. `fr journal handoff` resolves the journal and the plan's
    `depends_on`, then calls this.
    """
    relevant = {phase, *depends_on}
    # EFFECTIVE state, not each entry's own: a finding resolved by a later
    # record has stopped being actionable, and re-showing it in full is the
    # noise the fold exists to remove. This is the same fold `fr journal check`
    # gates on (`open_finding_ids`) — deliberately reused rather than
    # reimplemented, so the handoff and the gate can never disagree about what
    # is still open. The collapsed line keeps id, title, state and phase, so the
    # handoff still says both what was found and what became of it.
    still_open = set(open_finding_ids(entries))
    # The FULL fold, not just its open subset: the collapsed line reports
    # effective state, and `refuted` must survive as `refuted`. Reading
    # `e.state` instead printed the record's own label, so a finding written
    # `refuted` and later closed by a `fixed` resolution record still read
    # `[refuted]` — the same defect the phase-2 review fixed in the
    # open->fixed direction, which only looked fixed because the fallback
    # happened to say `fixed`.
    effective = effective_finding_states(entries)
    open_findings: list[str] = []
    context: list[str] = []
    collapsed: list[str] = []
    for e in entries:
        section: list[str]
        if e.kind == "finding":
            # STATE first — this is the bound. An open finding is actionable
            # anywhere; any other finding (fixed, refuted, or a resolution
            # record) is history, and no phase relationship makes a closed bug
            # actionable again. `relevant` is never consulted for a finding.
            # A resolution record is history — UNLESS it re-opens. Re-opening
            # is a first-class CLI path (`fr journal add --resolves <id>
            # --state open`), and collapsing one drops the only text saying
            # why the finding is actionable again, while the original report
            # still renders in full labelled with its old state. So ask the
            # fold about the finding this entry SPEAKS FOR: its target when it
            # resolves one, itself otherwise. Still one fold, and still O(1)
            # for closed entries, because a re-opened finding is by definition
            # open.
            speaks_for = e.resolves if e.resolves is not None else e.id
            renders_full = speaks_for in still_open
            section = open_findings
        else:
            # Dependency rule, deliberately unchanged: decisions and
            # discoveries are never "closed" and carry forward value.
            renders_full = e.phase is None or e.phase in relevant
            section = context
        if renders_full:
            section.append(serialize_entry(e))
        elif e.kind == "finding":
            # Display the EFFECTIVE state: this entry reached the collapse
            # branch, so the fold says it is closed whatever its own field
            # reads. Ask the fold, never the record.
            collapsed.append(_handoff_line(e, effective.get(e.id) or e.state))
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
