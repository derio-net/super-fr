"""`deliver`'s pre-merge walk: what is owed, and whether the named log covers it (spec
2026-11-27-run-verdict R7).

Moved from `fr.commands.run_cmd` in slice 5. `walk_obligation` raises `RunRefusal` when fr
cannot tell what is owed; `verify_walk` returns a `Verdict[str]`, its warnings the
unobserved-provenance note.

Engine code: no `typer`, no `rich` but `rich.markup`, no `fr.commands`
(`tests/unit/test_run_writes_layering.py`).
"""

from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path
from typing import TYPE_CHECKING

from rich.markup import escape

from fr.git import GitUnavailableError
from fr.run.evidence import refusal
from fr.run.evidence.suite import log_witness
from fr.run.model import RunState
from fr.run.unobserved import note_unobserved, why_unobservable
from fr.run.verdict import RunRefusal, Say, Verdict, Warn

if TYPE_CHECKING:
    from fr.verification.walk import WalkOwed


def walk_obligation(key: str, repo_root: Path, state: RunState) -> WalkOwed:
    """What walk `deliver` owes for this run (§C), or `RunRefusal`.

    Fail-closed: a section, matrix or strategy fr cannot read means fr cannot
    tell whether a walk is owed, and a gate that cannot decide does not pass.
    R10: an owed row that names no scenario is refused BY ID, before anything is
    asked of the log.
    """
    from fr.acceptance.model import AcceptanceError
    from fr.requirements import load_spec_matrix
    from fr.verification.model import StrategyError
    from fr.verification.rows import run_verification
    from fr.verification.spec_section import SectionError
    from fr.verification.walk import WalkOwed, walk_owed

    try:
        spec_rel, verification = run_verification(repo_root, state)
        if spec_rel is None:
            return WalkOwed()
        matrix, spec_ref = load_spec_matrix(repo_root, spec_rel)
        owed = walk_owed(matrix, spec_ref, verification, repo_root)
    except (AcceptanceError, SectionError, StrategyError, OSError) as e:
        raise RunRefusal(
            refusal(
                f"[red]{key}: cannot tell whether a pre-merge walk is owed — {escape(str(e))}[/red]"
            )
        ) from e
    unscripted = [r.id for r in owed.rows if not r.scenario]
    if unscripted:
        first = Say(
            f"[red]{key}: refused — row {unscripted[0]!r} has an agent-driven pre-merge "
            "strategy and names no `scenario` (set it with `fr acceptance set-status "
            "--scenario`).[/red]",
            soft_wrap=True,
        )
        others = (Say(f"  also unscripted: {other}", markup=False) for other in unscripted[1:])
        raise RunRefusal((first, *others))
    return owed


def verify_walk(
    key: str, value: str, repo_root: Path, state: RunState, owed: WalkOwed, *, opened: str | None
) -> Verdict[str]:
    """`value` is `none` (accepted only when no walk is owed) or a log
    `fr verification walk` wrote on HEAD's code tree, every step passing and
    every owed row covered — or a refusal naming the cause. Returns the witness,
    `<log>@<sha256[:12]>`.

    Attributed as `tests=` is (review p3-r1): the header is the log's own
    claim, so it must also sit in this run's walk dir and — where the
    transcript is readable — have been written inside the run window of a
    command of YOURS that ran `fr verification walk --run <run>` since this
    unit opened. Unobservable: recorded `unobserved=walk`, never silent.
    """
    from fr.run.code_tree import code_tree, dirty_code_paths
    from fr.verification.model import StrategyError
    from fr.verification.resolve import strategy_identity
    from fr.verification.walk import WalkError, check_walk_log, parse_walk_log, walk_log_dir

    warnings: list[Say] = []
    if value == "none":
        if owed.owed:
            wanted = [r.id for r in owed.rows] or [owed.run_strategy or "?"]
            return Verdict(
                None,
                refusal=refusal(
                    f"[red]{key}: --evidence walk=none — a pre-merge walk is owed "
                    f"({', '.join(wanted)}); run `fr verification walk` and name its log.[/red]"
                ),
                warnings=tuple(warnings),
            )
        return Verdict("none")
    given = Path(value).expanduser()
    named = given if given.is_absolute() else repo_root / given
    # The REAL path, symlinks followed, must sit in this run's walk dir, and
    # the name itself must be a regular file — a link placed there is not a
    # log the walk wrote (security review of p3-r1).
    path = Path(os.path.realpath(named))
    # `$HOME` may itself sit behind a link (macOS `/var`); the run's own dir
    # may not — it is compared unresolved under the resolved walks root.
    directory = Path(os.path.realpath(walk_log_dir(state.run).parent)) / state.run
    if named.is_symlink():
        return Verdict(
            None,
            refusal=refusal(
                f"[red]{key}: --evidence walk={value} is a symlink — name the log "
                f"`fr verification walk --run {state.run}` wrote.[/red]"
            ),
            warnings=tuple(warnings),
        )
    if not path.is_relative_to(directory) or not path.is_file():
        return Verdict(
            None,
            refusal=refusal(
                f"[red]{key}: --evidence walk={value} is not a regular file in {directory} — "
                f"name the log `fr verification walk --run {state.run}` wrote.[/red]"
            ),
            warnings=tuple(warnings),
        )
    try:
        data = path.read_bytes()
        log = parse_walk_log(data.decode())
        problems = check_walk_log(
            log,
            owed,
            code_tree(repo_root),
            run=state.run,
            manifest=strategy_identity(log.strategy, repo_root),
        )
        dirty = dirty_code_paths(repo_root)
        modified = _dt.datetime.fromtimestamp(path.stat().st_mtime, tz=_dt.UTC)
    except (OSError, UnicodeDecodeError, WalkError, GitUnavailableError, StrategyError) as e:
        return Verdict(
            None,
            refusal=refusal(f"[red]{key}: --evidence walk={value}: {escape(str(e))}[/red]"),
            warnings=tuple(warnings),
        )
    if dirty:
        problems.append(f"uncommitted code since the walk ({dirty[0]}...)")
    problems += walk_provenance(key, state.run, modified, opened=opened, warn=warnings.append)
    if problems:
        head = Say(f"[red]{key}: --evidence walk={value} is refused:[/red]", soft_wrap=True)
        listed = (Say(f"  - {problem}", markup=False, soft_wrap=True) for problem in problems)
        return Verdict(None, refusal=(head, *listed), warnings=tuple(warnings))
    return Verdict(log_witness(path, data, repo_root), warnings=tuple(warnings))


def walk_provenance(
    key: str, run: str, modified: _dt.datetime, *, opened: str | None, warn: Warn
) -> list[str]:
    """Why the walk log, modified at `modified`, is not one a command of
    yours wrote during this unit (empty when it is) — only a command that is
    exactly the walk counts (`walks_run`). Unobservable:
    `unobserved=walk`, warned — and a log older than the unit is still
    refused."""
    from fr.run.observed import walks_run
    from fr.run.telemetry import orchestrator_ran_since, parse_timestamp

    windows = (
        orchestrator_ran_since(os.environ, lambda command: walks_run(command, run), opened)
        if opened
        else None
    )
    # One second of slack either side, as `tests=` (review r1-1).
    slack = _dt.timedelta(seconds=1)
    if windows is not None:
        if any(s - slack <= modified <= e + slack for s, e in windows):
            return []
        why = (
            "no command of yours ran it"
            if not windows
            else "its bytes were not written by the command of yours that ran it"
        )
        return [
            f"{why} — `fr verification walk --run {run}` must run in this session since "
            f"this unit opened at {opened}, and write the log you name"
        ]
    opened_at = parse_timestamp(opened)
    if opened_at is not None and modified < opened_at - slack:
        return [f"the log predates this unit (opened {opened}) — walk again"]
    note_unobserved("walk")
    warn(
        Say(
            f"[yellow]{key}: could not verify who ran the walk — "
            f"{why_unobservable('commands')}; recorded unverified "
            "(evidence: unobserved=walk).[/yellow]",
            soft_wrap=True,
        )
    )
    return []
