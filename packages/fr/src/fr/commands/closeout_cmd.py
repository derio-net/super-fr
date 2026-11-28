"""`fr closeout outcome` — one recorded outcome per Test Plan step (spec
2026-10-11-debt-engine §E, R17, R18).

A close-out that skips a Test Plan step must say so: every step gets exactly
one outcome — ran (with its evidence), owed (with why), or n/a (with the
reason) — written to the spec journal as `test-plan-step-<n>`. Ran and n/a are
`discovery` entries, so they never read as operator decisions; owed is an
`owed` entry, which `fr archive` files as an `fr:owed` issue. `fr archive`
holds a plan whose spec has a step with no outcome (R19).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.markup import escape

from fr.commands.common import resolve_repo_root

err_console = Console(stderr=True, highlight=False)

closeout_app = typer.Typer(
    help="Close-out records: one outcome per spec Test Plan step.",
    no_args_is_help=True,
)

_RANGE_RE = re.compile(r"^(\d+)(?:-(\d+))?$")
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")


def _refuse(message: str) -> typer.Exit:
    err_console.print(f"[red]{escape(message)}[/red] — nothing written", soft_wrap=True)
    return typer.Exit(2)


def _spec_of_run(root: Path, run_id: str) -> Path:
    from fr.archive import run_spec_path

    if not _RUN_ID_RE.match(run_id):
        raise _refuse(f"--run {run_id!r} is not a run id")
    spec = run_spec_path(root, run_id)
    if spec is None:
        raise _refuse(f"run {run_id!r}: no run cursor names a spec this repo holds")
    return spec


def _spec_arg(root: Path, value: str) -> Path:
    from fr.archive import resolve_local_spec

    spec = resolve_local_spec(root, value)
    if spec is None:
        raise _refuse(f"--spec {value!r} does not resolve to a spec in this repo")
    return spec


def _parse_range(value: str, count: int) -> list[int]:
    m = _RANGE_RE.match(value.strip())
    if m is None:
        raise _refuse(f"--step {value!r} is not N or N-M")
    lo = int(m.group(1))
    hi = int(m.group(2)) if m.group(2) else lo
    if lo < 1 or hi < lo or hi > count:
        raise _refuse(f"--step {value} is out of range — the Test Plan has steps 1-{count}")
    return list(range(lo, hi + 1))


@closeout_app.command("outcome")
def outcome(
    run: str | None = typer.Option(None, "--run", help="The run whose spec's Test Plan this is."),
    spec: str | None = typer.Option(
        None, "--spec", help="The spec instead of a run (a plan with no run cursor)."
    ),
    step: str = typer.Option(..., "--step", help="The step number, or a range N-M."),
    ran: bool = typer.Option(False, "--ran", help="The step ran; --evidence says what it showed."),
    owed: bool = typer.Option(False, "--owed", help="The step is owed; --why says why."),
    na: bool = typer.Option(False, "--na", help="The step does not apply; --reason says why."),
    evidence: str | None = typer.Option(None, "--evidence", help="--ran: what it showed."),
    why: str | None = typer.Option(None, "--why", help="--owed: why it is not done now."),
    reason: str | None = typer.Option(None, "--reason", help="--na: why it does not apply."),
    supersede: bool = typer.Option(
        False,
        "--supersede",
        help="Record over a step's existing outcome, owed included: a new entry the fold "
        "reads as latest (an owed one may already be filed as an fr:owed issue, so it is "
        "never overwritten silently).",
    ),
    harness: str = typer.Option(
        "operator", "--harness", help="--ran: the harness a named row's walk ran on."
    ),
    model: str = typer.Option("human", "--model", help="--ran: the model that walked it."),
) -> None:
    """Record one outcome for each Test Plan step in --step (R18).

    Exactly one of `--ran --evidence <text>`, `--owed --why <text>` or
    `--na --reason <text>`. A step that already has an outcome is refused, and
    nothing is written for any step of the range, unless `--supersede` is given; then a
    new entry is appended and the old one stays, as a journal is a log.

    `--ran` on a step whose `(rows: …)` pointer names acceptance rows also records a
    passing walk on each, in the same commit (spec 2026-11-27-ops-gate-truth R9):
    harness `--harness` (default `operator`), model `--model` (default `human`).
    """
    from fr.archive import display_path, outcome_id, recorded_outcomes, spec_slug_of
    from fr.journal.model import owed_body, resolve_journal_read_path
    from fr.record import apply as engine
    from fr.record.model import JournalItem, StepRecord
    from fr.spec import TestPlanHeadingError, test_plan_steps

    chosen = [name for name, on in (("ran", ran), ("owed", owed), ("na", na)) if on]
    if len(chosen) != 1:
        raise _refuse("give exactly one of --ran, --owed or --na")
    texts = {"ran": evidence, "owed": why, "na": reason}
    flags = {"ran": "--evidence", "owed": "--why", "na": "--reason"}
    kind = chosen[0]
    for other, text in texts.items():
        if other != kind and text is not None:
            raise _refuse(f"{flags[other]} goes with --{other}, not --{kind}")
    text = (texts[kind] or "").strip()
    if not text:
        raise _refuse(f"--{kind} needs {flags[kind]} <text>")
    if (run is None) == (spec is None):
        raise _refuse("give exactly one of --run or --spec")

    root = resolve_repo_root()
    if run is not None:
        from fr.run.closeout import RunElsewhereError, run_checkout

        try:
            root = run_checkout(root, run)  # a quiet feature's run, from the base clone
        except RunElsewhereError as e:
            raise _refuse(str(e)) from e
    spec_path = _spec_of_run(root, run) if run is not None else _spec_arg(root, spec or "")
    try:
        steps = test_plan_steps(spec_path.read_text(), source=display_path(root, spec_path))
    except TestPlanHeadingError as e:
        raise _refuse(str(e)) from e
    if not steps:
        raise _refuse(f"{spec_path.name} has no `## Test Plan` section — nothing to record")
    numbers = _parse_range(step, len(steps))
    slug = spec_slug_of(spec_path)
    journal = resolve_journal_read_path(root, "spec", slug)
    done = recorded_outcomes(journal)
    effective = _effective_outcomes(journal)
    already = [outcome_id(n) for n in numbers if effective.get(n) is not None and not supersede]
    if already:
        raise _refuse(f"already recorded: {', '.join(already)} (--supersede records over it)")
    ids: dict[int, str] = {}
    for n in numbers:
        sid, k = outcome_id(n), 1
        while sid in done:  # an owed, or superseded, outcome keeps its entry
            k += 1
            sid = f"{outcome_id(n)}-{k}"
        ids[n] = sid

    items = []
    for n in numbers:
        what = steps[n - 1].text
        sid = ids[n]
        if kind == "owed":
            how = (
                f"fr journal resolve --scope spec --slug {slug} --id {sid} --state fixed "
                '--note "<evidence>"'
            )
            body = owed_body(what=what, why=text, how=how, key=f"spec:{slug}#step{n}")
            items.append(
                JournalItem.model_validate(
                    {"kind": "owed", "id": sid, "title": f"Test Plan step {n} owed", "body": body}
                )
            )
        else:
            label = "ran" if kind == "ran" else "n/a"
            field = "Evidence" if kind == "ran" else "Reason"
            items.append(
                JournalItem.model_validate(
                    {
                        "kind": "discovery",
                        "id": sid,
                        "title": f"Test Plan step {n}: {label}",
                        "body": f"Step: {what}\n\n{field}: {text}",
                    }
                )
            )
    walks = (
        _row_walks(root, run, spec_path, steps, numbers, text, harness, model)
        if kind == "ran"
        else None
    )
    try:
        applied = engine.apply_record(
            root,
            None,
            StepRecord(journal=tuple(items), acceptance=walks.items if walks else ()),
            target=engine.RecordTarget(
                journal_scope="spec",
                journal_slug=slug,
                journal_file=journal,
                message=f"chore(fr): closeout {slug} — Test Plan step(s) {step} {kind}",
                feature=walks.feature if walks else None,
            ),
        )
    except engine.RecordRefusedError as e:
        raise _refuse(str(e)) from e
    for n in numbers:
        typer.echo(f"{ids[n]}: {'n/a' if kind == 'na' else kind}")
    if walks:
        from fr.acceptance.walks import close_commands

        for line in walks.lines:
            typer.echo(line)
        for before in walks.before:
            for line in close_commands(root, before):
                typer.echo(line)
    if not applied.committed:
        # Review p3-r3(b): the outcome is written but git does not hold it, and
        # `fr archive` refuses to move a spec journal with uncommitted outcomes.
        rel = journal.relative_to(root).as_posix() if journal.is_relative_to(root) else journal
        typer.echo(
            f"warning: {rel} is uncommitted — fr archive will hold the plan until it is "
            "committed (commit it on a branch, not the default branch)"
        )


@dataclass(frozen=True)
class _RowWalks:
    """What `--ran` adds for the rows its steps name (R9): one acceptance item per row,
    the fragment its amendments go to, the rows as they stood, and one line per row."""

    items: tuple[Any, ...]
    feature: str
    before: tuple[Any, ...]
    lines: tuple[str, ...]


def _row_walks(
    root: Path,
    run: str | None,
    spec_path: Path,
    steps: list[Any],
    numbers: list[int],
    evidence: str,
    harness: str,
    model: str,
) -> _RowWalks | None:
    """A passing walk on each row the steps in *numbers* name (R9), or `None` when they
    name none or acceptance is off (R8). Refuses, before anything is written, a named id
    that is not a row citing the spec, and a row whose effective strategy is `none`."""
    import datetime as _dt

    from fr.acceptance.fragment import fragment_slug_for_spec
    from fr.acceptance.model import AcceptanceError, Walk
    from fr.acceptance.walks import walk_verified
    from fr.archive import display_path
    from fr.record.model import AcceptanceItem
    from fr.requirements import load_spec_matrix, rows_citing
    from fr.settings import SettingsError, disabled
    from fr.verification.model import RESERVED
    from fr.verification.rows import spec_verification
    from fr.verification.spec_section import SectionError

    named = {rid: n for n in reversed(numbers) for rid in steps[n - 1].rows}
    if not named:
        return None
    try:
        if disabled(root, "acceptance"):
            return None
    except SettingsError as e:
        raise _refuse(str(e)) from e
    spec_rel = display_path(root, spec_path)
    try:
        matrix, spec_ref = load_spec_matrix(root, spec_rel)
        verification = spec_verification(root, spec_rel, _shape_default(root, run))
    except (AcceptanceError, SectionError) as e:
        raise _refuse(str(e)) from e
    citing = {r.id: r for r in rows_citing(matrix, spec_ref)}
    at = _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    items, before, lines = [], [], []
    for rid, n in sorted(named.items(), key=lambda kv: (kv[1], kv[0])):
        row = citing.get(rid)
        if row is None:
            raise _refuse(f"step {n} names row {rid!r}, which is not a row citing {spec_rel}")
        strategy = verification.strategy(row)
        if strategy is None or strategy == RESERVED:
            raise _refuse(f"row {rid!r} has strategy none: there is no walk to record")
        walk = Walk(strategy=strategy, harness=harness, model=model, outcome="pass", at=at,
                    evidence=f"Test Plan step {n}: {evidence}")  # fmt: skip
        after = row.model_copy(update={"walks": (*row.walks, walk)})
        passing = {w.harness for w in after.walks if w.outcome == "pass"}
        owed = [h for h in row.harnesses if h not in passing]
        if walk_verified(after):
            status, notes = "walked", f"walked by Test Plan step {n}: {evidence}"
            lines.append(f"{rid}: walked")
        else:
            status = row.status
            notes = "; ".join(x for x in (row.notes, f"walked on {harness}") if x)
            lines.append(f"{rid}: walk recorded on {harness}; still owed: {', '.join(owed)}")
        items.append(AcceptanceItem(id=rid, status=status, notes=notes, walk=walk))
        before.append(row)
    return _RowWalks(tuple(items), fragment_slug_for_spec(spec_rel), tuple(before), tuple(lines))


def _shape_default(root: Path, run: str | None) -> str | None:
    """The run's shape default strategy, or `None` without a run (or a cursor fr cannot
    read: the section's own `strategy:` line still applies)."""
    if run is None:
        return None
    from fr.run.model import RunStateError, parse_run_state, run_path
    from fr.verification.rows import shape_default

    try:
        return shape_default(root, parse_run_state(run_path(root, run).read_text()))
    except RunStateError, OSError:
        return None


def _effective_outcomes(journal: Path) -> dict[int, str]:
    """Step number -> its effective outcome kind (`fr.ops.holds.fold_step_outcomes`)."""
    from fr.journal.model import JournalParseError, parse_journal
    from fr.ops.holds import fold_step_outcomes

    if not journal.is_file():
        return {}
    try:
        return fold_step_outcomes(parse_journal(journal.read_text()))
    except JournalParseError, OSError:
        return {}
