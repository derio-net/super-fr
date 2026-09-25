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
   writes land before them: a gate that refuses restores every byte this call
   touched, so a refusal still changes nothing on disk;
4. **commits once** through `fr.records_commit.commit_records`, and hands back
   the one line the caller prints.

`RecordRefusedError` carries a refusal's message; the caller prints it and exits 2.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from fr.artifacts.atomic import write_text_atomic
from fr.journal.model import (
    JournalEntry,
    JournalParseError,
    appended_journal_text,
    journal_path,
    parse_journal,
    resolution_record_id,
    spec_journal_slug,
)
from fr.record.model import StepRecord, allowed_sections, present_sections, records_dir
from fr.record.pr_body import PR_BODY_NAME, missing_sections, render_pr_body
from fr.workflow.artifacts import journal_scope

if TYPE_CHECKING:
    from fr.artifacts.commit import CommitOutcome

__all__ = [
    "ApplyOutcome",
    "RecordRefusedError",
    "RecordTarget",
    "apply_record",
]

MATRIX_REL = Path("docs/acceptance/matrix.yaml")


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
    before_write: Callable[[list[JournalEntry], list[JournalEntry]], None] | None = None
    """A verb's own last check over (existing, new) journal entries, run after
    validation and before any byte moves — `--answered-by operator`'s
    transcript verification."""


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
    emits_pr: bool = False


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
    owner_emits = tuple(step.emits) or (tuple(parent.emits) if parent is not None else ())
    scope = journal_scope(owner_emits)
    plan_rel = run_cmd._emitted_plan(state) or record.emitted.get("plan")
    plan_dir = repo_root / plan_rel if plan_rel else None
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
    phase = run_cmd._item_phase(record.item) if record.item else None
    emits_ticks = "plan:ticks" in owner_emits
    context = _Context(
        scope=scope,
        slug=slug,
        journal_file=None,
        plan_dir=plan_dir,
        phase=phase,
        completes_phase=emits_ticks and record.outcome == "done" and phase is not None,
        emits_ticks=emits_ticks,
        emits_pr="pr" in owner_emits,
    )
    return context, state


# --- journal ------------------------------------------------------------------


def _load_entries(text: str | None, where: Path) -> list[JournalEntry]:
    if text is None:
        return []
    try:
        return parse_journal(text)
    except JournalParseError as e:
        raise RecordRefusedError(f"{where}: journal does not parse: {e}") from e


def _stamp() -> str:
    import datetime as _dt

    return _dt.datetime.now().replace(microsecond=0).isoformat()


def _journal_writes(
    ctx: _Context, record: StepRecord, overlay: _Overlay, repo_root: Path, target: RecordTarget
) -> tuple[list[JournalEntry], dict[str, int]]:
    counts: dict[str, int] = {}
    refactor = dict(record.refactor)
    if not record.journal and not record.resolves and not refactor:
        return [], counts
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
    stamp = _stamp()

    def add(entry: JournalEntry) -> None:
        if entry.id in taken:
            raise RecordRefusedError(
                f"journal entry {entry.id!r} already exists; a finding changes by a "
                "`resolves` entry, never by re-adding it"
            )
        taken.add(entry.id)
        new.append(entry)

    def finding(fid: str) -> JournalEntry:
        hit = next((e for e in [*existing, *new] if e.id == fid), None)
        if hit is None:
            raise RecordRefusedError(f"no journal entry {fid!r} in {path.name} — nothing resolved")
        if hit.kind != "finding":
            raise RecordRefusedError(f"entry {fid!r} is a {hit.kind!r}, not a finding")
        return hit

    for item in record.journal:
        phase = item.phase if item.phase is not None else (None if item.is_global else ctx.phase)
        if item.is_global and scope != "plan":
            raise RecordRefusedError("`global` applies to plan-scope journals only")
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
            finding(item.resolves)
        try:
            entry = JournalEntry(
                kind=item.kind,
                scope=scope,  # type: ignore[arg-type]
                id=eid,
                created=stamp,
                phase=phase,
                title=item.title,
                body=item.body,
                state=state,
                resolves=item.resolves,
                review_scope=item.review_scope,
                answered_by=item.answered_by,
                tracked_by=item.tracked_by,
                out_of_scope=item.out_of_scope,
            )
        except ValueError as e:
            raise RecordRefusedError(f"invalid journal entry {eid!r}: {e}") from e
        add(entry)
        key: str = "open finding" if entry.kind == "finding" and state == "open" else entry.kind
        if entry.resolves is not None:
            key = "resolved"
        counts[key] = counts.get(key, 0) + 1

    for res in record.resolves:
        target_entry = finding(res.id)
        try:
            entry = JournalEntry(
                kind="finding",
                scope=scope,  # type: ignore[arg-type]
                id=resolution_record_id(res.id, taken),
                created=stamp,
                phase=res.phase if res.phase is not None else ctx.phase,
                title=f"resolves {res.id}: {target_entry.title}",
                body=res.body,
                state="open" if res.state in ("deferred", "out-of-scope") else res.state,  # type: ignore[arg-type]
                resolves=res.id,
                tracked_by=res.tracked_by,
                out_of_scope=res.state == "out-of-scope",
                answered_by=res.answered_by,
            )
        except ValueError as e:
            raise RecordRefusedError(f"invalid resolution of {res.id!r}: {e}") from e
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

    if target.before_write is not None:
        target.before_write(existing, new)
    text = overlay.read(path)
    for entry in new:
        text = appended_journal_text(text, slug, entry)
    overlay.put(path, text)
    return new, counts


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
    from fr.plan_ops import _yaml_dump

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

    def raw(n: int) -> dict[str, Any]:
        if n not in raws:
            text = overlay.read(ctx.plan_dir / f"{n:02d}.yaml")  # type: ignore[operator]
            raws[n] = yaml.safe_load(text or "") or {}
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
        completion["at"] = _now_iso()
        if note is not None:
            completion["note"] = note
        counts["completed"] = counts.get("completed", 0) + 1

    for n, data in raws.items():
        overlay.put(ctx.plan_dir / f"{n:02d}.yaml", _yaml_dump(data))
    _check_plan_parses(ctx.plan_dir, overlay)
    return counts


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


def _acceptance_writes(
    record: StepRecord, overlay: _Overlay, repo_root: Path
) -> tuple[dict[str, int], list[str]]:
    if not record.acceptance:
        return {}, []
    from typing import get_args

    from fr.acceptance.edit import append_row, merge_levels, replace_row
    from fr.acceptance.model import AcceptanceError, Row, Status, parse_matrix, split_ref
    from fr.acceptance.report import STALE_LEGACY_REPORTS, render_committed_set

    matrix_path = repo_root / MATRIX_REL
    text = overlay.read(matrix_path)
    if text is None:
        raise RecordRefusedError(f"no {MATRIX_REL} (run `fr acceptance init` to scaffold one)")
    counts: dict[str, int] = {}
    lines: list[str] = []
    valid = list(get_args(Status))
    for item in record.acceptance:
        if item.status not in valid:
            raise RecordRefusedError(
                f"acceptance {item.id}: unknown status {item.status!r} (valid: {' | '.join(valid)})"
            )
        try:
            matrix = parse_matrix(text)
        except AcceptanceError as e:
            raise RecordRefusedError(f"matrix does not parse: {e}") from e
        existing = next((r for r in matrix.rows if r.id == item.id), None)
        try:
            if existing is None:
                if item.capability is None or item.acceptance is None:
                    raise RecordRefusedError(
                        f"acceptance {item.id}: a new row needs `capability` and `acceptance`"
                    )
                row = Row(
                    id=item.id,
                    capability=item.capability,
                    acceptance=item.acceptance,
                    origin=item.origin,
                    levels=dict(item.levels),
                    status=item.status,  # type: ignore[arg-type]
                    notes=item.notes or "",
                )
            else:
                if not item.notes:
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
                        existing.levels, {k: list(v) for k, v in item.levels.items()}
                    ),
                    status=item.status,  # type: ignore[arg-type]
                    notes=item.notes,
                )
            for ref in row.refs():
                split_ref(ref)
        except AcceptanceError as e:
            raise RecordRefusedError(f"acceptance {item.id}: {e}") from e
        except ValueError as e:
            raise RecordRefusedError(f"acceptance {item.id}: {e}") from e
        if existing is None:
            text = append_row(text, row)
            lines.append(f"added row {row.id} ({row.status})")
            counts["row added"] = counts.get("row added", 0) + 1
        else:
            text = replace_row(text, item.id, row)
            lines.append(f"{row.id}: {existing.status} → {row.status}")
            counts["row moved"] = counts.get("row moved", 0) + 1
    try:
        final = parse_matrix(text)
    except AcceptanceError as e:
        raise RecordRefusedError(f"the rows would leave an invalid matrix: {e}") from e
    overlay.put(matrix_path, text)
    try:
        for rel, rendered in render_committed_set(final, repo_root).items():
            overlay.put(repo_root / rel, rendered)
        for rel in STALE_LEGACY_REPORTS:
            if (repo_root / rel).exists():
                overlay.put(repo_root / rel, None)
    except Exception as e:  # noqa: BLE001 — a render hiccup never fails a valid write
        lines.append(
            f"warning: matrix updated but the reports were not regenerated ({e}); run "
            "`fr acceptance report --deterministic` and commit them."
        )
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
        ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout.strip() or None if done.returncode == 0 else None


def _is_tracked(repo_root: Path, path: Path) -> bool:
    done = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--error-unmatch", "--", str(path)],
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
        )

    overlay = _Overlay()
    counts: dict[str, int] = {}
    entries, journal_counts = _journal_writes(ctx, record, overlay, repo_root, target)
    counts.update(journal_counts)
    counts.update(_plan_writes(ctx, record, overlay))
    row_counts, row_lines = _acceptance_writes(record, overlay, repo_root)
    counts.update(row_counts)
    if run_id is not None and ctx.emits_pr and record.outcome == "done":
        body_path = records_dir(repo_root, run_id) / PR_BODY_NAME
        _check_live_pr(repo_root, state, record, body_path)
        overlay.put(body_path, None)  # the render goes with the record once delivered
    delete_record = record_file is not None and record_file.is_file()
    if delete_record:
        assert record_file is not None
        overlay.put(record_file, None)

    commit_paths = [p for p, text in overlay.writes.items() if text is not None]
    if delete_record and record_file is not None and _is_tracked(repo_root, record_file):
        commit_paths.append(record_file)
    commit_paths += [
        p
        for p, text in overlay.writes.items()
        if text is None and p != record_file and _is_tracked(repo_root, p)
    ]

    before = overlay.snapshot()
    overlay.write()
    if run_id is None:
        outcome = _commit(repo_root, commit_paths, target.message or "chore(fr): record")
        return ApplyOutcome(
            line="",
            counts=counts,
            sha=_short_head(repo_root) if outcome.committed else None,
            committed=outcome.committed,
            written=tuple(commit_paths),
            entries=tuple(entries),
            notices=tuple(row_lines),
        )

    from fr.commands import run_cmd

    assert record.step is not None and record.outcome is not None
    state_value = "done" if record.outcome == "done" else "failed"
    try:
        result = run_cmd.resolve_in_process(
            repo_root,
            run_id,
            step_id=record.step,
            item=record.item,
            state_value=state_value,
            evidence=dict(record.evidence),
            emitted=dict(record.emitted),
            also_commit=commit_paths,
        )
    except BaseException:
        _restore(before)
        raise
    word = record.outcome if record.outcome != "blocked" else "blocked (resolved failed)"
    subject = " ".join(x for x in (record.step, record.item, word) if x)
    sha = _short_head(repo_root) if result.committed else None
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
        notices=tuple(row_lines) + tuple(result.notices),
    )


def _check_live_pr(repo_root: Path, state: Any, record: StepRecord, body_path: Path) -> None:
    """Render the PR body fr owns, then refuse `deliver` until the LIVE PR
    carries every required section (spec §5.C.4). The render is the one file
    a refusal leaves behind: it is what the agent opens the PR with."""
    from fr import gh

    body_path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(body_path, render_pr_body(repo_root, state))
    rel = body_path.relative_to(repo_root).as_posix()
    ref = record.emitted.get("pr") or state.branch
    try:
        live = gh.view_pr_body(ref, cwd=repo_root)
    except gh.GhError as e:
        raise RecordRefusedError(
            f"cannot read the PR {ref!r} ({e}). fr rendered its body to {rel}: open the PR "
            f"with `gh pr create --body-file {rel}`, put its url in the record's "
            "`emitted: {pr: <url>}`, and resolve again"
        ) from e
    missing = missing_sections(live)
    if missing:
        raise RecordRefusedError(
            f"the PR body lacks required section(s): {', '.join(missing)}. Update it "
            f"from fr's render — `gh pr edit {ref} --body-file {rel}` — and resolve again"
        )


def _commit(repo_root: Path, paths: list[Path], message: str) -> CommitOutcome:
    from fr.artifacts.commit import CommitOutcome
    from fr.records_commit import commit_records

    if not paths:
        return CommitOutcome(committed=False, reason="nothing written", unchanged=True)
    return commit_records(repo_root, paths, message)
