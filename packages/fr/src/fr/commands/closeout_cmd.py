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
from pathlib import Path

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
) -> None:
    """Record one outcome for each Test Plan step in --step (R18).

    Exactly one of `--ran --evidence <text>`, `--owed --why <text>` or
    `--na --reason <text>`. A step that already has an outcome is refused, and
    nothing is written for any step of the range.
    """
    from fr.archive import outcome_id, recorded_outcomes, spec_slug_of
    from fr.journal.model import owed_body, resolve_journal_read_path
    from fr.record import apply as engine
    from fr.record.model import JournalItem, StepRecord
    from fr.spec import test_plan_steps

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
    spec_path = _spec_of_run(root, run) if run is not None else _spec_arg(root, spec or "")
    steps = test_plan_steps(spec_path.read_text())
    if not steps:
        raise _refuse(f"{spec_path.name} has no `## Test Plan` section — nothing to record")
    numbers = _parse_range(step, len(steps))
    slug = spec_slug_of(spec_path)
    journal = resolve_journal_read_path(root, "spec", slug)
    done = recorded_outcomes(journal)
    already = [outcome_id(n) for n in numbers if outcome_id(n) in done]
    if already:
        raise _refuse(f"already recorded: {', '.join(already)}")

    items = []
    for n in numbers:
        what = steps[n - 1].text
        sid = outcome_id(n)
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
    try:
        applied = engine.apply_record(
            root,
            None,
            StepRecord(journal=tuple(items)),
            target=engine.RecordTarget(
                journal_scope="spec",
                journal_slug=slug,
                journal_file=journal,
                message=f"chore(fr): closeout {slug} — Test Plan step(s) {step} {kind}",
            ),
        )
    except engine.RecordRefusedError as e:
        raise _refuse(str(e)) from e
    for n in numbers:
        typer.echo(f"{outcome_id(n)}: {'n/a' if kind == 'na' else kind}")
    if not applied.committed:
        # Review p3-r3(b): the outcome is written but git does not hold it, and
        # `fr archive` refuses to move a spec journal with uncommitted outcomes.
        rel = journal.relative_to(root).as_posix() if journal.is_relative_to(root) else journal
        typer.echo(
            f"warning: {rel} is uncommitted — fr archive will hold the plan until it is "
            "committed (commit it on a branch, not the default branch)"
        )
