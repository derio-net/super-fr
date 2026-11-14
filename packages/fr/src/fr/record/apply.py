"""The step-record apply engine (spec `2026-09-25-lean-cost-aware-process-design.md`
§5.C.2, §5.C.6).

ONE code path for every bookkeeping write fr makes on an agent's behalf:
`fr run resolve --record` hands it a whole step's record, and the verbs (`fr
journal add/resolve`, `fr plan edit --tick/--complete-phase`, `fr acceptance
add/set-status`) hand it a one-entry record. Either way it:

1. **validates** the record — against the step's `emits:` when a run is named
   (`allowed_sections`), and every entry against what is on disk: an unknown
   tick id, an unknown finding id, a duplicate id or a malformed entry refuses
   the WHOLE record;
2. **builds every write in memory** — journal appends, plan ticks and phase
   completion, matrix rows and the three reports regenerated once, the record
   file's deletion;
3. **writes them atomically** (`write_text_atomic`) only once all of that
   succeeded, then runs the step's existing gates through `fr run resolve`'s
   own code (review witness, operator guard, `deliver`'s `tests=` log, the
   refactor gate). Those gates READ the journal and the plan, which is why the
   writes land before them: a gate that refuses — or a crash before any commit
   landed — restores every byte this call touched, the cursor and usage
   capture included, so a refusal still changes nothing on disk (p3-r3);
4. **commits once** through `fr.records_commit.commit_records`, and hands back
   the one line the caller prints. The record file is removed only once every
   write is on disk and every gate passed, and re-applying a record whose
   entries already landed is a no-op for them — a retry heals, never wedges.

`RecordRefusedError` carries a refusal's message; the caller prints it and exits 2.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.paths import emitted_path
from fr.git import git_argv
from fr.journal.model import (
    JournalEntry,
    JournalParseError,
    appended_journal_text,
    journal_path,
    journal_stamp_as_utc,
    owed_key,
    parse_journal,
    resolution_entry,
    spec_journal_slug,
)
from fr.record.model import AmendmentItem, StepRecord, allowed_sections, present_sections
from fr.workflow.artifacts import journal_scope

_SESSION_START = "1970-01-01T00:00:00+00:00"
"""The window a decision's operator claim opens on an empty journal: any answer
in this session counts (spec 2026-10-14 R12)."""

if TYPE_CHECKING:
    from fr.artifacts.commit import CommitOutcome

__all__ = [
    "ApplyOutcome",
    "RecordRefusedError",
    "RecordTarget",
    "apply_record",
]


class RecordRefusedError(Exception):
    """The record was refused; nothing on disk changed."""


@dataclass(frozen=True)
class RecordTarget:
    """Where a run-less (verb) record's entries land. A run record derives all
    of this from the run and its step."""

    journal_scope: str | None = None
    journal_slug: str | None = None
    journal_file: Path | None = None
    """Override for the journal path (`fr journal resolve` writes through the
    read path, so an archived journal is resolved where it lives)."""
    plan_dir: Path | None = None
    phase: int | None = None
    message: str | None = None
    """The commit subject a verb record commits under."""
    discharges_owed: bool = False
    """`fr journal resolve`'s target: a `fixed` resolution may name an `owed`
    entry (review p3-r6). Every other caller is refused one."""
    acceptance_drops: Mapping[str, Mapping[str, tuple[str, ...]]] = field(default_factory=dict)
    """Refs to remove from existing rows before the record's `levels` are
    merged in: row id → level → refs (gh#624). Verb-only — fed by
    `fr acceptance set-status --drop-level`. The `record` kind's shape is
    deliberately unchanged (spec d-carrier): an `AcceptanceItem` cannot drop
    refs, so a step that needs a removal runs the verb."""
    acceptance_features: Mapping[str, str] = field(default_factory=dict)
    """Row id → the fragment (feature slug) a NEW row is written to, when its
    origins name no single spec (`fr acceptance add --feature`; spec 2026-11-04
    R16). Verb-only, like `acceptance_drops`."""
    acceptance_origins: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    """Row id → the corrected `origin` of a row still PENDING on this branch (`fr
    acceptance amend --op reword --origin`): rewritten in place, never as an amendment,
    since a merged row's origins are its history and no amendment op carries them.
    Verb-only, like `acceptance_drops`: the `record` kind's shape is unchanged."""
    acceptance_repo: str | None = None
    """`<org>/<repo>` for the first fragment of a repo whose fragments name none and
    whose origin remote does not say (`fr acceptance add --repo`)."""
    feature: str | None = None
    """The feature (spec slug) whose fragment a verb record's amendments are written
    to (`fr acceptance amend|set-status --feature`, else the branch's run; spec
    2026-11-04 R16). A run record uses the run's spec."""


@dataclass
class ApplyOutcome:
    line: str
    counts: dict[str, int] = field(default_factory=dict)
    next_step: str | None = None
    sha: str | None = None
    committed: bool = False
    written: tuple[Path, ...] = ()
    entries: tuple[JournalEntry, ...] = ()
    notices: tuple[str, ...] = ()


# --- the in-memory overlay ---------------------------------------------------


class _Overlay:
    """Every write this record makes, as `{path: new text | None (delete)}`,
    read through so a second edit of one file builds on the first."""

    def __init__(self) -> None:
        self.writes: dict[Path, str | None] = {}

    def read(self, path: Path) -> str | None:
        if path in self.writes:
            return self.writes[path]
        return path.read_text() if path.is_file() else None

    def put(self, path: Path, text: str | None) -> None:
        self.writes[path] = text

    def snapshot(self) -> dict[Path, bytes | None]:
        return {p: (p.read_bytes() if p.is_file() else None) for p in self.writes}

    def write(self) -> None:
        for path, text in self.writes.items():
            if text is None:
                if path.is_file():
                    path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            write_text_atomic(path, text)


def _restore(before: dict[Path, bytes | None]) -> None:
    for path, data in before.items():
        if data is None:
            if path.is_file():
                path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.fr-restore")
        tmp.write_bytes(data)
        tmp.replace(path)


# --- the run side: what a record for this step may carry, and where ---------


@dataclass
class _Context:
    scope: str | None
    slug: str | None
    journal_file: Path | None
    plan_dir: Path | None
    phase: int | None
    completes_phase: bool
    emits_ticks: bool
    discharges_owed: bool = False
    """Only `fr journal resolve` discharges an owed entry: it closes the issue
    the entry was filed as, which a step record's `resolves:` never does."""
    gate_answer: Any = None
    """When this record clears an operator gate (the brainstorm record): who the
    gate's DERIVED provenance says answered it (`run_cmd.derive_gate_answer`,
    the same derivation `_gate_provenance` records), with the answered rounds
    it read. Its decisions are stamped `decided_by=operator` from it (spec
    2026-10-14 R12; reviews p3-r2, p3-r3) — see `_stamped_decider`."""
    identity: tuple[str, str] | None = None
    """The repo's `(org, repo)` — the Closes guard's — that a bare `#n` in a
    narrowing or a round names; `None` when it cannot be resolved, and then no
    narrowing is stamped."""
    feature: str | None = None
    """The run's spec as a fragment slug: the feature a new acceptance row of this
    record belongs to when its origins name no single spec (spec 2026-11-04 R16)."""


def _run_context(repo_root: Path, run_id: str, record: StepRecord) -> tuple[_Context, Any]:
    from fr.commands import run_cmd
    from fr.run.adopt import AdoptError
    from fr.run.model import RunStateError, load_run_state
    from fr.workflow.model import WorkflowError

    if record.step is None:
        raise RecordRefusedError("record names no `step`")
    if record.outcome is None:
        raise RecordRefusedError(f"{record.step}: record has no `outcome` (done|failed|blocked)")
    try:
        state = load_run_state(repo_root, run_id)
        manifest = run_cmd._resolve_manifest_for_state(repo_root, state)
        step, parent = run_cmd._find_step(manifest, record.step)
    except (RunStateError, WorkflowError, AdoptError) as e:
        raise RecordRefusedError(str(e)) from e
    allowed = allowed_sections(step, parent)
    extra = sorted(present_sections(record) - allowed)
    if extra:
        emits = list(step.emits) or (list(parent.emits) if parent is not None else [])
        raise RecordRefusedError(
            f"{record.step}: section(s) {', '.join(extra)} not allowed — the step emits "
            f"{emits}, which allows {sorted(allowed)} (spec §5.C.2.1)"
        )
    if record.shape is not None:
        # §A (R1): refused before any write, by the same rules resolve applies.
        try:
            run_cmd._rebind_shape(state, manifest, record.step, record.shape, repo_root)
        except RunStateError as e:
            raise RecordRefusedError(str(e)) from e
    owner_emits = tuple(step.emits) or (tuple(parent.emits) if parent is not None else ())
    scope = journal_scope(owner_emits)
    plan_rel = run_cmd._emitted_plan(state) or record.emitted.get("plan")
    plan_dir = emitted_path(repo_root, plan_rel) if plan_rel else None
    slug: str | None = None
    if scope == "plan" and plan_dir is not None:
        slug = plan_dir.name
    elif scope == "spec":
        spec_rel = record.emitted.get("spec") or next(
            (r.emitted["spec"] for r in state.steps.values() if r.emitted and "spec" in r.emitted),
            None,
        )
        if spec_rel is not None:
            slug = spec_journal_slug(Path(spec_rel).stem)
    run_spec_rel = record.emitted.get("spec") or next(
        (r.emitted["spec"] for r in state.steps.values() if r.emitted and "spec" in r.emitted),
        None,
    )
    phase = run_cmd._item_phase(record.item) if record.item else None
    emits_ticks = "plan:ticks" in owner_emits
    current = state.steps.get(record.step)
    gate_answer = (
        run_cmd.derive_gate_answer(
            current, no_questions=record.no_questions, claimed=record.evidence.get("answered_by")
        )
        if current is not None
        and run_cmd._clears_gate(step, current, "done" if record.outcome == "done" else "failed")
        else None
    )
    context = _Context(
        scope=scope,
        slug=slug,
        journal_file=None,
        plan_dir=plan_dir,
        phase=phase,
        completes_phase=emits_ticks and record.outcome == "done" and phase is not None,
        emits_ticks=emits_ticks,
        gate_answer=gate_answer,
        identity=_repo_identity(repo_root) if gate_answer is not None else None,
        feature=_feature_of_spec(run_spec_rel),
    )
    return context, state


def _feature_of_spec(spec_rel: str | None) -> str | None:
    if not spec_rel:
        return None
    from fr.acceptance.fragment import fragment_slug_for_spec

    return fragment_slug_for_spec(spec_rel)


def _repo_identity(repo_root: Path) -> tuple[str, str] | None:
    """The `(org, repo)` the Closes guard resolves (`resolve_identity` over the
    matrix, else the origin remote), or `None` when it cannot be resolved."""
    from fr.acceptance.check import resolve_identity
    from fr.acceptance.fold import load_effective
    from fr.acceptance.model import AcceptanceError

    try:
        return resolve_identity(load_effective(repo_root), repo_root)
    except (AcceptanceError, OSError):
        return None


_UNVERIFIED_NOTE = (
    "_`decided_by=operator` recorded unverified: the gate could not read who answered it._"
)


def _round_names_every_ref(
    texts: list[str], narrows: tuple[str, ...], identity: tuple[str, str] | None
) -> bool:
    """Do the answered rounds name EVERY narrowed issue? Both sides are reduced
    to `owner/repo#n` by the Closes guard's own normalizer, and the rounds' refs
    are extracted with the PR-body parser's regex — never a substring test — so
    `#1` never matches `#12`, and another repo's `#n` only that repo (review
    p3-r2, its security addendum). An unknown identity, or a narrowed ref that
    does not normalize, matches nothing."""
    from fr.record.pr_body import issue_refs, normalize_issue_ref

    if identity is None:
        return False
    named: set[str] = set()
    for text in texts:
        named |= issue_refs(text, identity)
    wanted = [normalize_issue_ref(ref, identity) for ref in narrows]
    return all(ref is not None and ref in named for ref in wanted)


def _stamped_decider(ctx: _Context, narrows: tuple[str, ...]) -> tuple[str | None, str | None]:
    """`(decided_by, note)` for a decision the gate record did not attribute
    itself (spec 2026-10-14 R12). From the gate's DERIVED answer, never the claim
    alone (p3-r3):

    - observed, operator: an ordinary decision is the operator's; a NARROWING one
      only when every narrowed ref appears in an answered round's question or
      answer text (p3-r2) — otherwise it stays the agent's, and `fr journal add …
      --answered-by operator` (verified) is the later route;
    - unobserved, claimed operator: never a narrowing; an ordinary decision is
      stamped with a recorded unverified note;
    - anything else (agent, a refused gate, no gate): nobody's stamp."""
    answer = ctx.gate_answer
    if answer is None or answer.who != "operator":
        return None, None
    if not answer.observed:
        return (None, None) if narrows else ("operator", _UNVERIFIED_NOTE)
    texts = [t for r in answer.rounds for t in (*r.question_texts, *r.answer_texts)]
    if not narrows or _round_names_every_ref(texts, narrows, ctx.identity):
        return "operator", None
    return None, None


# --- journal ------------------------------------------------------------------


def _load_entries(text: str | None, where: Path) -> list[JournalEntry]:
    if text is None:
        return []
    try:
        return parse_journal(text)
    except JournalParseError as e:
        raise RecordRefusedError(f"{where}: journal does not parse: {e}") from e


def _stamp() -> str:
    from fr.journal.model import journal_now

    return journal_now()


def _same_entry(a: JournalEntry, b: JournalEntry, *, ignore: frozenset[str]) -> bool:
    """Equal in everything but `ignore` — a retry's entry differs from the one
    a crashed apply already wrote only in its `created` stamp."""
    return a.model_dump(exclude=set(ignore)) == b.model_dump(exclude=set(ignore))


_STAMP = frozenset({"created"})
_STAMP_AND_ID = frozenset({"created", "id"})


def _journal_writes(
    ctx: _Context, record: StepRecord, overlay: _Overlay, repo_root: Path
) -> tuple[list[JournalEntry], dict[str, int], list[str]]:
    """Journal appends, in memory. Returns (entries appended, counts, advisory
    lines). Re-applying a record whose entries are already in the journal —
    a retry after an apply that died between its writes and its commit —
    is a no-op for those entries (p3-r3): the retry heals the tree instead of
    wedging on "already exists". A same-id entry with different content still
    refuses."""
    counts: dict[str, int] = {}
    notices: list[str] = []
    refactor = dict(record.refactor)
    if not record.journal and not record.resolves and not refactor:
        return [], counts, notices
    scope = ctx.scope or ("plan" if refactor else None)
    slug = ctx.slug or (ctx.plan_dir.name if refactor and ctx.plan_dir is not None else None)
    if scope is None or slug is None:
        raise RecordRefusedError(
            "record has journal entries but fr cannot tell which journal they belong in "
            "(the step emits no `journal:<scope>`, or its spec/plan is not recorded yet)"
        )
    path = ctx.journal_file or journal_path(repo_root, scope, slug)  # type: ignore[arg-type]
    existing = _load_entries(overlay.read(path), path)
    taken = {e.id for e in existing}
    new: list[JournalEntry] = []
    stamped: set[str] = set()  # decisions the gate attributed, verified by the gate
    stamp = _stamp()

    def add(entry: JournalEntry) -> None:
        if entry.id in taken:
            there = next((e for e in existing if e.id == entry.id), None)
            if there is not None and _same_entry(there, entry, ignore=_STAMP):
                return  # already applied by an earlier, interrupted apply
            raise RecordRefusedError(
                f"journal entry {entry.id!r} already exists; a finding changes by a "
                "`resolves` entry, never by re-adding it"
            )
        _verify(entry)
        taken.add(entry.id)
        new.append(entry)

    def _verify(entry: JournalEntry) -> None:
        # p3-r1: every path that writes an operator claim checks it here, the
        # verbs and a whole step's record alike.
        if entry.answered_by != "operator" and entry.decided_by != "operator":
            return
        if entry.resolves is None and (entry.kind != "decision" or entry.id in stamped):
            return  # the brainstorm gate attributed it from its own rounds (R12)
        from fr.journal.operator import (
            OperatorClaimRefusedError,
            verify_operator_answer,
            verify_operator_claim,
        )

        try:
            if entry.resolves is not None:
                advisory = verify_operator_claim([*existing, *new], entry.resolves)
            else:
                # A decision answers what was asked since the journal last moved ON
                # DISK; an empty journal opens the window at the session's start. Never
                # at an entry this record adds: every one carries the apply time, after
                # any answer the operator gave (the operator brief ahead of a brainstorm
                # record's decisions refused every one of them, 7.0.0rc3 live walk).
                # Deliberately, so one window serves every decision of the record: a
                # question round answers several decisions in one exchange, as the gate's
                # own attribution of a round's decisions does. What is checked is that
                # the operator answered in the window, never which decision an answer
                # was about; with no answer there, every claimed decision is refused.
                since = existing[-1].created if existing else None
                since_utc = journal_stamp_as_utc(since) if since else _SESSION_START
                advisory = verify_operator_answer(
                    f"decision {entry.id}", since or "the session's start", since_utc
                )
        except OperatorClaimRefusedError as e:
            raise RecordRefusedError(str(e)) from e
        if advisory is not None:
            notices.append(advisory)

    def finding(fid: str, *, discharge: bool = False, files: bool = False) -> JournalEntry:
        hit = next((e for e in [*existing, *new] if e.id == fid), None)
        if hit is None:
            raise RecordRefusedError(f"no journal entry {fid!r} in {path.name} — nothing resolved")
        if hit.kind == "owed" and discharge and ctx.discharges_owed:
            return hit  # discharging an owed action (spec 2026-10-11 §E, R24)
        if hit.kind == "owed" and files:
            return hit  # `fr journal file` records where it went (2026-10-14 R10)
        if hit.kind == "owed":
            raise RecordRefusedError(
                f"entry {fid!r} is an owed action — discharge it with `fr journal resolve "
                f"--scope <s> --slug <slug> --id {fid} --state fixed --note <evidence>`, "
                "which also closes the issue it was filed as; a step record's `resolves:` "
                "cannot"
            )
        if hit.kind != "finding":
            raise RecordRefusedError(f"entry {fid!r} is a {hit.kind!r}, not a finding")
        return hit

    for item in record.journal:
        phase = item.phase if item.phase is not None else (None if item.is_global else ctx.phase)
        if item.is_global and scope != "plan":
            raise RecordRefusedError("`global` applies to plan-scope journals only")
        if item.kind == "lens":
            entry = _lens_entry(
                item, scope, phase, record.step, stamp, [*existing, *new], repo_root
            )
            if entry is not None:
                add(entry)
            counts["lens"] = counts.get("lens", 0) + 1
            continue
        if scope == "plan" and phase is None and not item.is_global:
            raise RecordRefusedError(
                f"journal entry {item.title!r}: a plan-scope entry needs `phase` or "
                "`global: true` — an untagged entry renders in every handoff"
            )
        eid = (
            item.id
            or hashlib.sha1(
                f"{item.kind}|{scope}|{slug}|{item.title}|{item.body}".encode()
            ).hexdigest()[:12]
        )
        state = (
            item.state if item.state is not None else ("open" if item.kind == "finding" else None)
        )
        if item.resolves is not None:
            finding(item.resolves, files=item.filed_as is not None)
        # A decision's provenance and remainder ride decision-only tokens no
        # released fr knows (review p3-r1); the record keeps its field names.
        decision = item.kind == "decision"
        decided_by: str | None = item.answered_by if decision else None
        note: str | None = None
        if decision and decided_by is None:
            decided_by, note = _stamped_decider(ctx, item.narrows)
            if decided_by is not None:
                stamped.add(eid)
        body = f"{item.body.rstrip()}\n\n{note}".lstrip() if note else item.body
        try:
            entry = JournalEntry(
                kind=item.kind,
                scope=scope,  # type: ignore[arg-type]
                id=eid,
                created=stamp,
                phase=phase,
                title=item.title,
                body=body,
                state=state,
                resolves=item.resolves,
                review_scope=item.review_scope,
                answered_by=None if decision else item.answered_by,
                tracked_by=None if decision else item.tracked_by,
                out_of_scope=item.out_of_scope,
                input=item.input,
                filed_as=item.filed_as,
                gate=item.gate,
                narrows=item.narrows,
                decided_by=decided_by,  # type: ignore[arg-type]
                remainder_tracked_by=item.tracked_by if decision else None,
            )
        except ValueError as e:
            raise RecordRefusedError(f"invalid journal entry {eid!r}: {e}") from e
        if entry.kind == "owed" and owed_key(entry) is None:
            raise RecordRefusedError(
                f"owed entry {eid!r} needs an `owed_key: <key>` body line "
                "(spec:<slug>#step<n>, plan:<name>#p<n>, row:<id>) — every owed item has one key"
            )
        add(entry)
        key: str = "open finding" if entry.kind == "finding" and state == "open" else entry.kind
        if entry.resolves is not None:
            key = "resolved"
        counts[key] = counts.get(key, 0) + 1

    for res in record.resolves:
        target_entry = finding(res.id, discharge=res.state == "fixed")
        try:
            entry = resolution_entry(
                target=target_entry,
                scope=scope,  # type: ignore[arg-type]
                taken=taken,
                created=stamp,
                state=res.state,
                body=res.body,
                phase=res.phase if res.phase is not None else ctx.phase,
                tracked_by=res.tracked_by,
                answered_by=res.answered_by,
            )
        except ValueError as e:
            raise RecordRefusedError(f"invalid resolution of {res.id!r}: {e}") from e
        last = next((e for e in reversed([*existing, *new]) if e.resolves == res.id), None)
        if last is None or last in new or not _same_entry(last, entry, ignore=_STAMP_AND_ID):
            add(entry)
        counts["resolved"] = counts.get("resolved", 0) + 1

    if refactor:
        justified = _justified_tasks([*existing, *new])
        for task, reason in refactor.items():
            if ctx.phase is not None and not task.startswith(f"P{ctx.phase}."):
                raise RecordRefusedError(f"refactor: {task} is not a task of phase {ctx.phase}")
            if task in justified:
                continue
            add(
                JournalEntry(
                    kind="discovery",
                    scope="plan",
                    id=_unique_id(f"no-refactor-{task.lower().replace('.', '-')}", taken),
                    created=stamp,
                    phase=ctx.phase,
                    title=f"no-refactor-because {task}",
                    body=reason,
                )
            )
            counts["refactor"] = counts.get("refactor", 0) + 1

    # Put even when nothing is new: a retry that found every entry already
    # written still commits the journal an interrupted apply left dirty.
    text = overlay.read(path)
    for entry in new:
        text = appended_journal_text(text, slug, entry)
    if text is not None:
        overlay.put(path, text)
    return new, counts, notices


def _lens_entry(
    item: Any,
    scope: str,
    phase: int | None,
    step: str | None,
    created: str,
    prior: list[JournalEntry],
    repo_root: Path,
) -> JournalEntry | None:
    """A `lens` item as its journal entry (spec 2026-11-12-review-lenses §3.B): the
    lens must be effective; fr assigns the id (`lens-<id>-<n>`, counting this
    journal's entries for that lens) and stamps `step` from the record. In a plan
    journal a lens added outside a phase unit is global. `None` when the same
    addition is already in the journal (a retry of an interrupted apply)."""
    from fr.lenses.model import LensError
    from fr.lenses.resolve import effective_lenses

    try:
        effective = effective_lenses(repo_root)
    except LensError as e:
        raise RecordRefusedError(f"lens {item.lens!r}: the lens config is unreadable: {e}") from e
    if item.lens not in effective:
        raise RecordRefusedError(
            f"lens {item.lens!r} is not an effective lens of this repo; effective: "
            + (", ".join(sorted(effective)) or "none")
        )
    same = [e for e in prior if e.kind == "lens" and e.lens == item.lens]
    eid = next_lens_id(item.lens, prior)
    try:
        entry = JournalEntry(
            kind="lens",
            scope=scope,  # type: ignore[arg-type]
            id=eid,
            created=created,
            phase=phase if scope == "plan" else None,
            title=item.title,
            body=item.body,
            lens=item.lens,
            step=step,
            # Carried so the entry model refuses what a lens cannot take.
            state=item.state,
            resolves=item.resolves,
            review_scope=item.review_scope,
            answered_by=item.answered_by,
            tracked_by=item.tracked_by,
            out_of_scope=item.out_of_scope,
            input=item.input,
            gate=item.gate,
            narrows=item.narrows,
            filed_as=item.filed_as,
        )
    except ValueError as e:
        raise RecordRefusedError(f"invalid lens entry for {item.lens!r}: {e}") from e
    if any(_same_entry(e, entry, ignore=_STAMP_AND_ID) for e in same):
        return None
    return entry


def next_lens_id(lens: str, prior: list[JournalEntry]) -> str:
    """The id the next `lens` entry for `lens` takes in a journal holding `prior`:
    `lens-<id>-<n>`, n counting that lens's entries and skipping any id in use."""
    n = sum(1 for e in prior if e.kind == "lens" and e.lens == lens) + 1
    taken = {e.id for e in prior}
    while f"lens-{lens}-{n}" in taken:
        n += 1
    return f"lens-{lens}-{n}"


def _unique_id(base: str, taken: set[str]) -> str:
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def _justified_tasks(entries: Iterable[JournalEntry]) -> set[str]:
    import re

    found: set[str] = set()
    for e in entries:
        if e.kind not in ("discovery", "decision"):
            continue
        hay = f"{e.title}\n{e.body}".casefold()
        if "no-refactor-because" in hay:
            found.update(m.group(0).upper() for m in re.finditer(r"p\d+\.t\d+", hay))
    return found


# --- plan ---------------------------------------------------------------------


def _plan_writes(ctx: _Context, record: StepRecord, overlay: _Overlay) -> dict[str, int]:
    ticks = record.tick_items()
    complete = record.complete
    if not ticks and complete is None and not ctx.completes_phase:
        return {}
    if ctx.plan_dir is None:
        raise RecordRefusedError("record ticks plan steps but no plan is recorded for this run")
    from fr.parser import PlanSchemaError, parse
    from fr.plan_ops import rewrite_phase_text

    try:
        plan = parse(ctx.plan_dir)
    except PlanSchemaError as e:
        raise RecordRefusedError(f"plan does not parse: {e}") from e
    owner: dict[str, int] = {}
    for ph in plan.phases:
        for task in ph.tasks:
            for step in task.steps:
                owner[step.id] = ph.phase.number
    raws: dict[int, dict[str, Any]] = {}
    texts: dict[int, str] = {}

    def raw(n: int) -> dict[str, Any]:
        if n not in raws:
            texts[n] = overlay.read(ctx.plan_dir / f"{n:02d}.yaml") or ""  # type: ignore[operator]
            raws[n] = yaml.safe_load(texts[n]) or {}
        return raws[n]

    counts: dict[str, int] = {}
    from fr.plan_ops import _now_iso

    for tick in ticks:
        n = owner.get(tick.id)
        if n is None:
            raise RecordRefusedError(f"unknown tick id {tick.id!r} — no such step in the plan")
        if ctx.phase is not None and n != ctx.phase:
            raise RecordRefusedError(
                f"tick {tick.id} is in phase {n}, not this record's phase {ctx.phase}"
            )
        current = raw(n)["state"]["steps"][tick.id]
        if current.get("state") == tick.state and (
            tick.note is None or current.get("note") == tick.note
        ):
            continue
        raw(n)["state"]["steps"][tick.id] = {
            "state": tick.state,
            "ticked_at": _now_iso(),
            "note": tick.note,
        }
        counts["ticked"] = counts.get("ticked", 0) + 1

    to_complete: list[tuple[int, str | None]] = []
    if complete is not None:
        to_complete.append((complete.phase, complete.note))
    elif ctx.completes_phase and ctx.phase is not None:
        to_complete.append((ctx.phase, None))
    for n, note in to_complete:
        matched = next((p for p in plan.phases if p.phase.number == n), None)
        if matched is None:
            raise RecordRefusedError(f"phase {n} not found in plan")
        if matched.phase.tag == "manual" and not note:
            raise RecordRefusedError(f"phase {n} is manual; completing it needs a note")
        steps = raw(n)["state"]["steps"]
        if matched.phase.tag == "agentic":
            unticked = sorted(sid for sid, s in steps.items() if (s or {}).get("state") == " ")
            if unticked:
                raise RecordRefusedError(
                    f"phase {n} (agentic) has unticked steps: {unticked} — tick them in the "
                    "record, or report the phase failed/blocked"
                )
        completion = raw(n)["state"]["completion"]
        if completion.get("at") and complete is None:
            continue  # already complete: a resolve does not re-stamp it
        _refactor_check(plan, n, overlay)
        completion["at"] = _now_iso()
        if note is not None:
            completion["note"] = note
        counts["completed"] = counts.get("completed", 0) + 1

    for n, data in raws.items():
        # Ticks and completion live under `state:`; nothing else is rewritten (gh#502).
        overlay.put(ctx.plan_dir / f"{n:02d}.yaml", rewrite_phase_text(texts[n], data, "state"))
    _check_plan_parses(ctx.plan_dir, overlay)
    return counts


def _refactor_check(plan: Any, phase_n: int, overlay: _Overlay) -> None:
    """The refactor-or-justify gate on EVERY phase completion (p3-r8) — a
    record's or `fr plan edit --complete-phase`'s alike. The justifications
    are read from the journal on disk plus this record's own entries, which
    are still in memory."""
    from fr.record.gates import refactor_gaps

    extra: set[str] = set()
    if plan.repo_root is not None:
        path = journal_path(plan.repo_root, "plan", plan.meta.plan)
        if path in overlay.writes:
            extra = _justified_tasks(_load_entries(overlay.read(path), path))
    gaps = refactor_gaps(plan, phase_n, extra)
    if gaps:
        raise RecordRefusedError(
            f"phase {phase_n}: task(s) {', '.join(gaps)} have no refactor step and no "
            f"refactor reason — add `refactor: {{{gaps[0]}: <why there was nothing to "
            "clean>}` to the step record, or journal a `no-refactor-because "
            f"{gaps[0]}` discovery for phase {phase_n} before completing it"
        )


def _check_plan_parses(plan_dir: Path, overlay: _Overlay) -> None:
    """Parse the plan as it WILL be, in a scratch copy — the post-write
    re-parse `plan_ops.tick` does, moved before any byte lands."""
    from fr.parser import PlanSchemaError, parse

    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / plan_dir.name
        shutil.copytree(plan_dir, copy)
        for path, text in overlay.writes.items():
            if path.parent == plan_dir and text is not None:
                (copy / path.name).write_text(text)
        try:
            parse(copy, enforce_fr_version=False)
        except PlanSchemaError as e:
            raise RecordRefusedError(f"the ticks would leave the plan unparseable: {e}") from e


# --- acceptance ---------------------------------------------------------------


def _check_drops(
    record: StepRecord, drops: Mapping[str, Mapping[str, tuple[str, ...]]], run_id: str | None
) -> None:
    """Refuse every misalignment that would make a drop a silent no-op
    (spec 2026-09-26 §2.C) — before anything is built or written."""
    if not drops:
        return
    if run_id is not None:
        raise RecordRefusedError(
            "acceptance drops are verb-only (`set-status --drop-level`); "
            f"a run record never reads them (run {run_id!r})"
        )
    for row_id, levels in drops.items():
        named = [
            item
            for item in record.acceptance
            if not isinstance(item, AmendmentItem) and item.id == row_id
        ]
        if not named:
            raise RecordRefusedError(
                f"acceptance {row_id}: a drop names a row the record does not move"
            )
        if len(named) > 1:
            # Judged by position, a create-then-move would pass the create
            # refusal below and drop from the row it had just created.
            raise RecordRefusedError(
                f"acceptance {row_id}: the record names this row more than once, so "
                "which entry the drop belongs to is ambiguous"
            )
        if not any(levels.values()):
            raise RecordRefusedError(
                f"acceptance {row_id}: a drop entry that names no ref would remove nothing"
            )
        item = named[0]
        if item.capability is not None or item.acceptance is not None:
            raise RecordRefusedError(
                f"acceptance {row_id}: a drop on a row the record creates — a new row "
                "has nothing to drop"
            )
        # gh#655: the CLI refuses this before it builds the record; the engine
        # is reachable without the CLI, so it refuses it too. Dropped then
        # re-added nets to the row's prior state while reading as two edits.
        both = sorted(
            f"{lv}={ref}"
            for lv, refs in levels.items()
            for ref in refs
            if ref in item.levels.get(lv, ())
        )
        if both:
            raise RecordRefusedError(
                f"acceptance {row_id}: {', '.join(both)} named in both the drops and the "
                "additions — a contradiction, so nothing changed"
            )


def _no_ci_reason(repo_root: Path) -> str | None:
    """Why this repo cannot hold a `ci` row, or None when it has CI."""
    from fr.acceptance.ci import ci_reason

    return ci_reason(repo_root)


def _union(old: tuple[str, ...], new: tuple[str, ...]) -> tuple[str, ...]:
    """`old` then whatever of `new` it lacks, in order — an add, never a reorder."""
    return old + tuple(x for x in dict.fromkeys(new) if x not in old)


def strategy_error(name: str, repo_root: Path) -> str | None:
    """Why `verify: name` cannot be written, or None: it must resolve to a
    strategy or be `none` (spec 2026-10-06-verification-strategies §B)."""
    from fr.verification.model import RESERVED, StrategyError
    from fr.verification.resolve import resolve_strategy

    if name == RESERVED:
        return None
    try:
        resolve_strategy(name, repo_root)
    except StrategyError as e:
        return f"verify {name!r}: {e}"
    return None


class _Amending:
    """Amendments for one record (spec 2026-11-04 R16, R17): which rows are merged on
    the default ref, each row's revision (the base an amendment names when the
    record gives none), and the row each amendment leaves, so a second amendment of
    one row in the same record builds on the first."""

    def __init__(self, repo_root: Path, feature: str | None) -> None:
        self.repo_root = repo_root
        self._feature = feature
        self._merged: frozenset[str] | None = None
        self._current: Any = None
        self.rows: dict[str, Any] = {}
        from collections import Counter

        self.taken: Counter[str] = Counter()

    def _fold(self) -> Any:
        if self._current is None:
            from fr.acceptance.fold import effective
            from fr.acceptance.model import AcceptanceError

            try:
                self._current = effective(self.repo_root)
            except AcceptanceError as e:
                raise RecordRefusedError(f"the acceptance fragments do not fold: {e}") from e
            self.rows = {r.id: r for r in self._current.matrix.rows}
        return self._current

    def is_merged(self, row_id: str) -> bool:
        """Whether the default ref's fragments define *row_id* (none without one)."""
        if self._merged is None:
            from fr.acceptance.fold import default_ref_fold
            from fr.acceptance.model import AcceptanceError

            try:
                merged = default_ref_fold(self.repo_root)
            except AcceptanceError as e:
                raise RecordRefusedError(f"the default ref's fragments do not fold: {e}") from e
            self._merged = frozenset(merged.owners) if merged is not None else frozenset()
        return row_id in self._merged

    def identity(self) -> str | None:
        """`<org>/<repo>` as the fold's fragments name it, or None when none does."""
        matrix = self._fold().matrix
        return f"{matrix.org}/{matrix.repo}" if matrix.org and matrix.repo else None

    def merged_outside(self, own_rows: frozenset[str]) -> None:
        """Quiet and stealth: the rows the fold knows that this branch's own fragments do
        not define are merged (the fold includes no unmerged feature but this one), and
        so is every row this branch's own feature defined when it merged: its fragments
        frozen at the merge (PR #1437 review F2: a merged row of the branch's own feature
        was read as pending, so `set-status` and `amend --origin` rewrote it in place)."""
        from fr.acceptance.fold import own_merged_fragments
        from fr.acceptance.fragment import parse_fragment
        from fr.acceptance.model import AcceptanceError

        merged = frozenset(self._fold().owners) - own_rows
        try:
            frozen = own_merged_fragments(self.repo_root)
            if frozen is not None:
                merged |= {
                    r.id for rel, t in frozen[0].items() for r in parse_fragment(t, source=rel).rows
                }
        except AcceptanceError as e:
            raise RecordRefusedError(f"the merged fragments do not fold: {e}") from e
        self._merged = merged

    def feature(self) -> str:
        if self._feature is None:
            from fr.acceptance.amend import NO_FEATURE

            raise RecordRefusedError(NO_FEATURE)
        return self._feature

    def row(self, row_id: str, *, contested_retired: bool = False) -> Any:
        """The row an amendment applies to. With *contested_retired*, a retired row the
        fold marks contested is returned too: R17's next correctly based amendment is
        the only way to clear it, so `amend` must be able to write one (decision
        fold-retired-rows-keep-the-base-rule). A retired row that is not contested
        has nothing to clear and stays refused."""
        current = self._fold()
        if row_id not in self.rows:
            if contested_retired and row_id in current.contested:
                hit = next((r for r in current.retired if r.id == row_id), None)
                if hit is not None:
                    return hit
            retired = any(r.id == row_id for r in current.retired)
            raise RecordRefusedError(
                f"acceptance {row_id}: "
                + ("the row is retired" if retired else "no such row")
                + " — an amendment names a row of the effective matrix"
            )
        return self.rows[row_id]

    def base(self, row_id: str) -> int:
        return int(self._fold().revisions.get(row_id, 0)) + self.taken[row_id]

    def amend(self, item: AmendmentItem, write: Any, no_ci: str | None) -> str:
        from fr.acceptance.anchors import line_anchor_error
        from fr.acceptance.fold import apply_amendment
        from fr.acceptance.logical import is_logical, parse_logical
        from fr.acceptance.model import AcceptanceError, pipeline_ref_error, split_ref, walked_error

        was_retired = item.row not in self.rows
        old = self.row(item.row, contested_retired=True)
        base = item.base if item.base is not None else self.base(item.row)
        try:
            amendment = item.to_amendment(base)
        except ValueError as e:
            raise RecordRefusedError(str(e)) from e
        where = f"acceptance {item.row}"
        if amendment.op == "add-level":
            try:
                parse_logical(amendment.ref) if is_logical(amendment.ref) else split_ref(
                    amendment.ref
                )
            except AcceptanceError as e:
                raise RecordRefusedError(f"{where}: {e}") from e
            for why in (pipeline_ref_error(amendment.ref), line_anchor_error(amendment.ref)):
                if why is not None:
                    raise RecordRefusedError(f"{where}: {why}")
        if amendment.op == "drop-level" and amendment.ref not in old.levels.get(
            amendment.level, ()
        ):
            raise RecordRefusedError(
                f"{where}: cannot drop {amendment.ref!r} from level {amendment.level!r}: the "
                f"row does not carry it (current refs: {list(old.levels.get(amendment.level, ()))})"
            )
        new = apply_amendment(old, amendment)
        if amendment.op == "set-status":
            if amendment.verify is not None and (
                why := strategy_error(amendment.verify, self.repo_root)
            ):
                raise RecordRefusedError(f"{where}: {why}")
            if (why := walked_error(new)) is not None:
                raise RecordRefusedError(f"{where}: {why}")
            if new.status == "local":
                from fr.acceptance.local import local_error

                own = (self.identity() or "").rpartition("/")[2] or None
                if (why := local_error(new, self.repo_root, own=own)) is not None:
                    raise RecordRefusedError(f"{where}: {why}")
            if no_ci is not None and new.status == "ci" and old.status != "ci":
                raise RecordRefusedError(
                    f"{where}: status `ci` needs a CI run as its evidence, but {no_ci}. "
                    "Record it as `unwired` (a test exists, not in CI) instead."
                )
        write(amendment)
        if was_retired:
            pass  # a retired row stays retired: R16 has no op that brings one back
        elif amendment.op == "retire":
            self.rows.pop(item.row)
        else:
            self.rows[item.row] = new
        return f"{item.row}: {amendment.op} amendment (base {base}) in {self.feature()}"

    def move(
        self,
        item: Any,
        drops: Mapping[str, tuple[str, ...]],
        write: Any,
        no_ci: str | None,
    ) -> str:
        """An `AcceptanceItem` move of a merged row, as the amendments it amounts to:
        a `set-status` for its status, note, walk, issues, verify and scenario, then
        one `add-level` per ref it adds and one `drop-level` per ref it drops."""
        from fr.acceptance.edit import describe_move

        old = self.row(item.id)
        if any(h not in old.harnesses for h in item.harnesses):
            raise RecordRefusedError(
                f"acceptance {item.id}: the row is merged, and no amendment op carries "
                "`harnesses`; a merged row changes only by amendment"
            )
        if not item.notes and item.status != old.status:
            raise RecordRefusedError(
                f"acceptance {item.id}: moving a row's status needs `notes` — "
                "a status that moved for no recorded reason is a silent change"
            )
        issues = tuple(i for i in dict.fromkeys(item.issues) if i not in old.issues)
        notes = item.notes or old.notes
        verify = item.verify if item.verify is not None and item.verify != old.verify else None
        scenario = (
            item.scenario if item.scenario is not None and item.scenario != old.scenario else None
        )
        why = notes or f"set-status {item.status}"
        planned: list[AmendmentItem] = []
        if (
            item.status != old.status
            or notes != old.notes
            or item.walk is not None
            or issues
            or verify is not None
            or scenario is not None
        ):
            planned.append(
                AmendmentItem(
                    row=item.id,
                    op="set-status",
                    status=item.status,
                    notes=notes,
                    walk=item.walk,
                    issues=issues,
                    verify=verify,
                    scenario=scenario,
                    why=why,
                )  # fmt: skip
            )
        for lv, refs in item.levels.items():
            for ref in refs:
                if ref not in old.levels.get(lv, ()):
                    planned.append(
                        AmendmentItem(row=item.id, op="add-level", level=lv, ref=ref, why=why)
                    )
        for lv, refs in drops.items():
            for ref in dict.fromkeys(refs):
                planned.append(
                    AmendmentItem(row=item.id, op="drop-level", level=lv, ref=ref, why=why)
                )
        for amendment in planned:
            self.amend(amendment, write, no_ci)
        new = self.rows[item.id]
        return (
            f"{item.id}: {describe_move(old, new)} "
            f"({len(planned)} amendment{'s' if len(planned) != 1 else ''} in {self.feature()}"
            if planned
            else f"{item.id}: unchanged (no amendment"
        ) + ")"


def _reword_pending(
    item: AmendmentItem,
    origins: Mapping[str, tuple[str, ...]] | None,
    frags: Mapping[Path, Any],
    texts: dict[Path, str],
    amending: Any,
    rel: Any,
    deleted: set[Path],
) -> str:
    """A `reword` that corrects a row's `origin` (debug journal
    2026-11-13-placement-plan-paths): only a row still pending on this branch, in the
    fragment that holds it, rewritten in place with its new origins (written in their
    logical form, R18) and any new acceptance or capability. A merged row is refused:
    its origins are history, and no amendment op carries them."""
    from fr.acceptance.edit import replace_row
    from fr.acceptance.logical import canonical, is_logical, parse_logical, spec_slug, to_logical
    from fr.acceptance.model import AcceptanceError, split_ref

    where = f"acceptance {item.row}"
    if item.op != "reword":
        raise RecordRefusedError(f"{where}: `--origin` corrects a row only with `--op reword`")
    if amending.is_merged(item.row):
        raise RecordRefusedError(
            f"{where}: the row is merged, so its origins are history and no amendment op "
            "carries them; `--origin` corrects only a row still pending on this branch"
        )
    owner = next((p for p, f in frags.items() if any(r.id == item.row for r in f.rows)), None)
    if owner is None:
        raise RecordRefusedError(f"{where}: no such row pending on this branch")
    existing = next(r for r in frags[owner].rows if r.id == item.row)
    own = (amending.identity() or "").partition("/")[2]
    new_origins = tuple(
        canonical(o) if is_logical(o) else to_logical(o, own_repo=own)
        for o in (origins or {})[item.row]
    )
    try:
        for ref in new_origins:
            parse_logical(ref) if is_logical(ref) else split_ref(ref)
    except AcceptanceError as e:
        raise RecordRefusedError(f"{where}: {e}") from e
    from fr.acceptance.anchors import line_anchor_error

    for ref in new_origins:  # review F4: what `add` refuses in an origin, so does this
        if (why := line_anchor_error(ref)) is not None:
            raise RecordRefusedError(f"{where}: {why}")
    row = existing.model_copy(
        update={
            "origin": new_origins,
            "acceptance": item.acceptance or existing.acceptance,
            "capability": item.capability or existing.capability,
        }
    )
    moved = f"{item.row}: origin {', '.join(existing.origin) or '—'} -> {', '.join(new_origins)}"

    def spec_slugs(refs: tuple[str, ...]) -> set[str]:
        return {spec_slug(parse_logical(o).slug) for o in refs if o.startswith("spec:")}

    # Review F6: only a changed set of origin specs re-files the row; a correction within
    # the same spec keeps it where it is (`--feature` may have put it there).
    slugs = spec_slugs(new_origins)
    moves = len(slugs) == 1 and slugs != spec_slugs(existing.origin)
    target = owner.parent / f"{next(iter(slugs))}.yaml" if moves else owner
    if target == owner:
        texts[owner] = replace_row(texts[owner], item.row, row)
        return moved
    # The row is owned by the feature of its one origin spec (R16): a corrected origin
    # naming another spec moves it to that spec's fragment, still pending here.
    from fr.acceptance.edit import insert_row, remove_row, render_fragment

    if target in frags and any(r.id == item.row for r in frags[target].rows):
        raise RecordRefusedError(f"{where}: {rel(target)} already holds a row {item.row}")
    if any(r.id != item.row for r in frags[owner].rows) or frags[owner].amendments:
        # Other rows, or this feature's amendments of merged rows, stay where they are.
        texts[owner] = remove_row(texts[owner], item.row)
    else:
        del texts[owner]  # nothing else in it: the file goes (flushed by the caller)
        deleted.add(owner)
    if target not in texts:
        texts[target] = (
            target.read_text()
            if target.is_file()
            else render_fragment(target.stem, amending.identity() or "", ())
        )
    texts[target] = insert_row(texts[target], row)
    return f"{moved} (moved to {rel(target)})"


def _acceptance_writes(
    record: StepRecord,
    overlay: _Overlay,
    repo_root: Path,
    drops: Mapping[str, Mapping[str, tuple[str, ...]]],
    *,
    features: Mapping[str, str] | None = None,
    repo: str | None = None,
    default_feature: str | None = None,
    origins: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[dict[str, int], list[str]]:
    """The record's `acceptance:` entries as fragment writes (spec 2026-11-04 R16):
    a new row into the fragment of its one origin spec (or `features[id]`); a row
    still pending on this branch rewritten in place in the fragment that holds it;
    a row merged on the default ref, and every amendment item, appended as
    amendments to the feature's fragment (*default_feature*). No report is written:
    reports are derived (R20)."""
    if not record.acceptance:
        return {}, []
    from fr.settings import disabled, disabled_because

    if disabled(repo_root, "acceptance"):
        raise RecordRefusedError(disabled_because("acceptance", "a record's `acceptance:` section"))
    from typing import get_args

    from fr.acceptance.anchors import line_anchor_error
    from fr.acceptance.edit import (
        append_amendment,
        describe_move,
        drop_levels,
        insert_row,
        merge_levels,
        render_fragment,
        replace_row,
    )
    from fr.acceptance.fold import fold_outside_with, fold_texts, has_fragments
    from fr.acceptance.fragment import FRAGMENTS_DIR, Fragment, parse_fragment
    from fr.acceptance.logical import canonical, is_logical, parse_logical, spec_slug, to_logical
    from fr.acceptance.model import (
        AcceptanceError,
        Row,
        Status,
        pipeline_ref_error,
        split_ref,
        walked_error,
    )
    from fr.artifacts.paths import artifact_root, outside_repo

    folder = artifact_root(repo_root) / FRAGMENTS_DIR
    outside = outside_repo(repo_root) is not None
    if not folder.is_dir() and not (outside and has_fragments(repo_root)):
        # Under quiet and stealth a feature's own fragment folder is made by its first
        # write: the repo keeps acceptance when any feature root does.
        raise RecordRefusedError(
            f"no {FRAGMENTS_DIR}/ (run `fr acceptance init` to scaffold acceptance)"
        )
    paths = {p for p in folder.glob("*.yaml") if p.is_file()} if folder.is_dir() else set()
    paths |= {p for p in overlay.writes if p.parent == folder and p.suffix == ".yaml"}
    texts: dict[Path, str] = {}
    for p in sorted(paths):
        t = overlay.read(p)
        if t is not None:
            texts[p] = t
    before = dict(texts)
    deleted: set[Path] = set()  # fragments a moved row emptied

    froot = artifact_root(repo_root)

    def rel(p: Path) -> str:
        return p.relative_to(froot).as_posix()

    def parsed() -> dict[Path, Fragment]:
        try:
            return {p: parse_fragment(t, source=rel(p)) for p, t in texts.items()}
        except AcceptanceError as e:
            raise RecordRefusedError(f"a fragment does not parse: {e}") from e

    def identity() -> str:
        known = {f.repo for f in parsed().values()}
        if known:
            return sorted(known)[0]
        if outside:  # another feature's fragments already name the repo
            seen = amending.identity()
            if seen:
                return seen
        if repo:
            return repo
        from fr.acceptance.check import resolve_identity
        from fr.acceptance.model import Matrix

        try:
            org, name = resolve_identity(Matrix(), repo_root)
        except AcceptanceError as e:
            raise RecordRefusedError(
                "the first fragment needs `repo: <org>/<repo>` and no origin remote names "
                "it: pass --repo <org>/<repo>"
            ) from e
        return f"{org}/{name}"

    counts: dict[str, int] = {}
    lines: list[str] = []
    valid = list(get_args(Status))
    no_ci: str | None = (
        _no_ci_reason(repo_root)
        if any(getattr(item, "status", None) == "ci" for item in record.acceptance)
        else None
    )
    amending = _Amending(repo_root, default_feature)
    if outside:
        # Under quiet and stealth "merged on the default ref" is a row another feature's
        # merged fragments define (R17's clause): it changes only by amendment (R16).
        amending.merged_outside(frozenset(r.id for f in parsed().values() for r in f.rows))

    def write_amendment(amendment: Any) -> None:
        feature = amending.feature()
        path = folder / f"{feature}.yaml"
        text = texts.get(path) or render_fragment(feature, identity(), ())
        texts[path] = append_amendment(text, amendment)
        amending.taken[amendment.row] += 1
        counts["amendment"] = counts.get("amendment", 0) + 1

    for item in record.acceptance:
        if isinstance(item, AmendmentItem) and (origins or {}).get(item.row):
            lines.append(_reword_pending(item, origins, parsed(), texts, amending, rel, deleted))
            counts["row moved"] = counts.get("row moved", 0) + 1
            continue
        if isinstance(item, AmendmentItem):
            lines.append(amending.amend(item, write_amendment, no_ci))
            continue
        if item.status not in valid:
            raise RecordRefusedError(
                f"acceptance {item.id}: unknown status {item.status!r} (valid: {' | '.join(valid)})"
            )
        frags = parsed()
        owner = next((p for p, f in frags.items() if any(r.id == item.id for r in f.rows)), None)
        existing = (
            next(r for r in frags[owner].rows if r.id == item.id) if owner is not None else None
        )
        # p3-r5: the entry's shape says which verb it is, as the verbs do —
        # `capability`/`acceptance` present is `fr acceptance add` (create-only),
        # absent is `set-status` (move-only). Existence alone never decides.
        creates = item.capability is not None or item.acceptance is not None
        if creates and (item.capability is None or item.acceptance is None):
            raise RecordRefusedError(
                f"acceptance {item.id}: a new row needs both `capability` and `acceptance`"
            )
        if not creates and amending.is_merged(item.id):
            # R16: a row merged on the default ref changes only by amendment.
            lines.append(amending.move(item, drops.get(item.id, {}), write_amendment, no_ci))
            continue
        if not creates and existing is None:
            raise RecordRefusedError(
                f"acceptance {item.id}: no such row — moving a status needs an existing id; "
                "give `capability` and `acceptance` to create it"
            )
        own = identity().partition("/")[2] if creates else ""

        def logical(refs: tuple[str, ...] | list[str]) -> tuple[str, ...]:
            # R18: a spec or plan path is written in its logical form.
            # A logical spec ref is stored in its one spelling (`spec_slug`).
            # `to_logical`'s output already is in that spelling (and a
            # `-design-design.md` spec must keep one `-design`).
            return tuple(
                canonical(r) if is_logical(r) else to_logical(r, own_repo=own) for r in refs
            )

        try:
            if creates:
                assert item.capability is not None and item.acceptance is not None
                row = Row(
                    id=item.id,
                    capability=item.capability,
                    acceptance=item.acceptance,
                    origin=logical(item.origin),
                    levels={lv: logical(refs) for lv, refs in item.levels.items()},
                    status=item.status,  # type: ignore[arg-type]
                    notes=item.notes or "",
                    verify=item.verify,
                    visual=item.visual,
                    scenario=item.scenario,
                    issues=item.issues,
                    harnesses=item.harnesses,
                    walks=(item.walk,) if item.walk is not None else (),
                )
            else:
                assert existing is not None  # refused above when absent
                if not item.notes and item.status != existing.status:
                    raise RecordRefusedError(
                        f"acceptance {item.id}: moving a row's status needs `notes` — "
                        "a status that moved for no recorded reason is a silent change"
                    )
                row = Row(
                    id=existing.id,
                    capability=existing.capability,
                    acceptance=existing.acceptance,
                    origin=existing.origin,
                    levels=merge_levels(
                        drop_levels(existing.levels, drops.get(item.id, {})),
                        {k: list(v) for k, v in item.levels.items()},
                    ),
                    status=item.status,  # type: ignore[arg-type]
                    # Only a status move owes a note (refused above), so an item that moves
                    # nothing and names none keeps the row's own.
                    notes=item.notes or existing.notes,
                    # A status move keeps the row's `verify` unless it names one.
                    verify=item.verify if item.verify is not None else existing.verify,
                    # `visual` is create-only — set-status never touches it (spec
                    # 2026-09-28 §A), so a move always keeps the existing value.
                    visual=existing.visual,
                    # Matrix kind 4 (spec 2026-10-06 §B): `scenario` is kept
                    # unless named; `issues`/`harnesses` are ADDED to; a `walk`
                    # is APPENDED — the row's walks are its history.
                    scenario=item.scenario if item.scenario is not None else existing.scenario,
                    issues=_union(existing.issues, item.issues),
                    harnesses=_union(existing.harnesses, item.harnesses),
                    walks=existing.walks + ((item.walk,) if item.walk is not None else ()),
                )
            if item.verify is not None and (why := strategy_error(item.verify, repo_root)):
                raise RecordRefusedError(f"acceptance {item.id}: {why}")
            for ref in row.refs():
                if is_logical(ref):
                    parse_logical(ref)
                else:
                    split_ref(ref)
            # Only the refs this write adds: refused where written, not where
            # loaded, so a row that already carries one still moves (gh#775).
            added = [ref for refs in item.levels.values() for ref in refs]
            for ref in added:
                if (why := pipeline_ref_error(ref)) is not None:
                    raise RecordRefusedError(f"acceptance {item.id}: {why}")
            # gh#531: likewise only what this write adds — a row still carrying a
            # line anchor moves; `check` and the matrix repair handle the rest.
            for ref in [*added, *(item.origin if creates else ())]:
                if (why := line_anchor_error(ref)) is not None:
                    raise RecordRefusedError(f"acceptance {item.id}: {why}")
        except AcceptanceError as e:
            raise RecordRefusedError(f"acceptance {item.id}: {e}") from e
        except ValueError as e:
            raise RecordRefusedError(f"acceptance {item.id}: {e}") from e
        # p1-r2: `walked` means proven by a passing walk, on the row or in this entry.
        if (why := walked_error(row)) is not None:
            raise RecordRefusedError(f"acceptance {item.id}: {why}")
        # Spec 2026-11-14-acceptance-local-status R2, R3: `local` names resolving tests in
        # this repo, and only a repo with no CI holds it. Checked on every entry that sets
        # it, since setting `local` again clears the row's stamp.
        if row.status == "local":
            from fr.acceptance.local import local_error

            if (why := local_error(row, repo_root, own=identity().rpartition("/")[2])) is not None:
                raise RecordRefusedError(f"acceptance {item.id}: {why}")
        # gh#775: `ci` means a CI run is the evidence, so a row moves there only
        # in a repo with CI. A row already `ci` is left alone — refusing it
        # would block every unrelated edit to it.
        if (
            no_ci is not None
            and row.status == "ci"
            and (existing is None or existing.status != "ci")
        ):
            raise RecordRefusedError(
                f"acceptance {item.id}: status `ci` needs a CI run as its evidence, but "
                f"{no_ci}. Record it as `unwired` (a test exists, not in CI) instead."
            )
        if creates and existing is not None:
            if existing == row:
                continue  # already created by an earlier, interrupted apply (p3-r3)
            raise RecordRefusedError(
                f"acceptance {item.id}: row already exists — `capability`/`acceptance` "
                "create a row; drop them to move its status"
            )
        if existing is None:
            feature = (features or {}).get(item.id)
            if feature is None:
                slugs = {
                    spec_slug(parse_logical(o).slug) for o in row.origin if o.startswith("spec:")
                }
                if len(slugs) != 1 and default_feature is not None:
                    slugs = {default_feature}  # a run's row belongs to the run's spec
                if len(slugs) != 1:
                    raise RecordRefusedError(
                        f"acceptance {item.id}: a row is owned by the feature of its one "
                        f"origin spec, and its origins name {len(slugs) or 'no'} "
                        f"spec{'s' if len(slugs) > 1 else ''} — pass --feature <slug> to "
                        "name the fragment (`legacy` for a row with no feature)"
                    )
                feature = next(iter(slugs))
            path = folder / f"{feature}.yaml"
            text = texts.get(path) or render_fragment(feature, identity(), ())
            texts[path] = insert_row(text, row)
            lines.append(f"added row {row.id} ({row.status}) to {rel(path)}")
            counts["row added"] = counts.get("row added", 0) + 1
        else:
            assert owner is not None
            # A row still pending on this branch (no default ref defines it) moves in
            # place in the fragment that holds it; a merged one took the branch above.
            texts[owner] = replace_row(texts[owner], item.id, row)
            lines.append(f"{row.id}: {describe_move(existing, row)}")
            counts["row moved"] = counts.get("row moved", 0) + 1
    try:
        written = {rel(p): t for p, t in texts.items()}
        fold_outside_with(repo_root, written) if outside else fold_texts(written)
    except AcceptanceError as e:
        raise RecordRefusedError(f"the rows would leave invalid fragments: {e}") from e
    for p, t in texts.items():
        if before.get(p) != t:
            overlay.put(p, t)
    for p in deleted:
        overlay.put(p, None)
    return counts, lines


# --- the one line -------------------------------------------------------------

_COUNT_ORDER = (
    "ticked",
    "completed",
    "decision",
    "discovery",
    "review",
    "open finding",
    "finding",
    "resolved",
    "refactor",
    "row added",
    "row moved",
    "amendment",
)


def _plural(n: int, noun: str) -> str:
    if n == 1 or noun in ("ticked", "completed", "resolved"):
        return f"{n} {noun}"
    if noun == "discovery":
        return f"{n} discoveries"
    if noun.startswith("row "):
        return f"{n} rows {noun[4:]}"
    return f"{n} {noun}s"


def summary_counts(counts: dict[str, int]) -> list[str]:
    ordered = [k for k in _COUNT_ORDER if k in counts] + sorted(
        k for k in counts if k not in _COUNT_ORDER
    )
    return [_plural(counts[k], k) for k in ordered if counts[k]]


def _short_head(repo_root: Path) -> str | None:
    done = subprocess.run(
        git_argv(repo_root, "-C", str(repo_root), "rev-parse", "--short", "HEAD"),
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout.strip() or None if done.returncode == 0 else None


def _is_tracked(repo_root: Path, path: Path) -> bool:
    done = subprocess.run(
        git_argv(repo_root, "-C", str(repo_root), "ls-files", "--error-unmatch", "--", str(path)),
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode == 0


# --- the engine ---------------------------------------------------------------


def apply_record(
    repo_root: Path,
    run_id: str | None,
    record: StepRecord,
    *,
    target: RecordTarget | None = None,
    record_file: Path | None = None,
) -> ApplyOutcome:
    """Validate, build in memory, write atomically, gate, commit once.

    `run_id` names the run whose step `record` resolves; `None` is a verb's
    one-entry record, whose destination `target` names. `record_file`, when
    given, is deleted in the same commit. Raises `RecordRefusedError` (nothing on
    disk changed) or `typer.Exit` from one of `fr run resolve`'s own gates
    (every byte restored first).
    """
    target = target or RecordTarget()
    state: Any = None
    _check_drops(record, target.acceptance_drops, run_id)
    if run_id is not None:
        if record.run is not None and record.run != run_id:
            raise RecordRefusedError(f"record is for run {record.run!r}, not {run_id!r}")
        ctx, state = _run_context(repo_root, run_id, record)
    else:
        ctx = _Context(
            scope=target.journal_scope,
            slug=target.journal_slug,
            journal_file=target.journal_file,
            plan_dir=target.plan_dir,
            phase=target.phase,
            completes_phase=False,
            emits_ticks=target.plan_dir is not None,
            discharges_owed=target.discharges_owed,
            feature=target.feature,
        )

    overlay = _Overlay()
    counts: dict[str, int] = {}
    entries, journal_counts, journal_notices = _journal_writes(ctx, record, overlay, repo_root)
    counts.update(journal_counts)
    counts.update(_plan_writes(ctx, record, overlay))
    row_counts, row_lines = _acceptance_writes(
        record,
        overlay,
        repo_root,
        target.acceptance_drops,
        features=target.acceptance_features,
        repo=target.acceptance_repo,
        default_feature=ctx.feature,
        origins=target.acceptance_origins,
    )
    counts.update(row_counts)
    notices = (*journal_notices, *row_lines)

    commit_paths = [p for p, text in overlay.writes.items() if text is not None]
    commit_paths += [
        p for p, text in overlay.writes.items() if text is None and _is_tracked(repo_root, p)
    ]

    before = overlay.snapshot()
    if run_id is None:
        overlay.write()
        outcome = _commit(repo_root, commit_paths, target.message or "chore(fr): record")
        return ApplyOutcome(
            line="",
            counts=counts,
            sha=_short_head(repo_root) if outcome.committed else None,
            committed=outcome.committed,
            written=tuple(commit_paths),
            entries=tuple(entries),
            notices=notices,
        )

    from fr.commands import run_cmd

    assert record.step is not None and record.outcome is not None
    state_value = "done" if record.outcome == "done" else "failed"
    # p3-r3: the record survives until every write — the cursor included — is
    # on disk. A tracked record is removed the instant before the commit that
    # records its deletion (git commits a path as the working tree has it); an
    # untracked one only after that commit landed. Everything this call writes,
    # the cursor and the usage capture included, is remembered before it moves,
    # and restored on ANY exit unless a commit already landed — a restore after
    # a commit would leave a tree that disagrees with HEAD.
    guard = run_cmd.ResolveGuard()
    record_bytes: bytes | None = None
    tracked_record = False
    if record_file is not None and record_file.is_file():
        record_bytes = record_file.read_bytes()
        tracked_record = _is_tracked(repo_root, record_file)

    def drop_tracked_record() -> list[Path]:
        if not tracked_record or record_file is None or not record_file.is_file():
            return []
        guard.originals.setdefault(record_file, record_bytes)
        record_file.unlink()
        return [record_file]

    guard.before_commit = drop_tracked_record
    try:
        overlay.write()
        result = run_cmd.resolve_in_process(
            repo_root,
            run_id,
            step_id=record.step,
            item=record.item,
            state_value=state_value,
            evidence=dict(record.evidence),
            emitted=dict(record.emitted),
            no_questions=record.no_questions,
            reason=record.reason,
            questions=record.questions,
            also_commit=commit_paths,
            guard=guard,
            visual=record.visual,
            shape=record.shape,
        )
    except BaseException:
        if not guard.landed:
            _restore({**guard.originals, **before})
        raise
    if record_bytes is not None and not tracked_record and record_file is not None:
        record_file.unlink(missing_ok=True)  # every write landed and every gate passed
    word = record.outcome if record.outcome != "blocked" else "blocked (resolved failed)"
    subject = " ".join(x for x in (record.step, record.item, word) if x)
    # The commit landed where the run's artifacts live (the `fr` worktree or tracking
    # clone under quiet or stealth), so that repository's HEAD names it.
    from fr.artifacts.paths import artifact_root

    sha = _short_head(artifact_root(repo_root)) if result.committed else None
    parts = [subject, *summary_counts(counts), f"next: {result.next_step or 'none'}"]
    parts.append(sha if sha else "NOT committed")
    return ApplyOutcome(
        line=" · ".join(parts),
        counts=counts,
        next_step=result.next_step,
        sha=sha,
        committed=result.committed,
        written=tuple(commit_paths),
        entries=tuple(entries),
        notices=notices + tuple(result.notices),
    )


def _commit(repo_root: Path, paths: list[Path], message: str) -> CommitOutcome:
    from fr.artifacts.commit import CommitOutcome
    from fr.records_commit import commit_records

    if not paths:
        return CommitOutcome(committed=False, reason="nothing written", unchanged=True)
    return commit_records(repo_root, paths, message)
