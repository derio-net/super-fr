"""`fr usage collect|report` — what a session or run cost, and on what (spec §5.A.5).

`collect` normalizes harness sessions (`fr.usage.readers`) into JSON under
`$HOME/.cache/fr/usage/` (`FR_USAGE_CACHE` overrides): `<harness>/<session>.json`,
plus `runs/<run>.json` naming a run's sessions. `report` renders a rollup as a
table or one self-contained HTML page.

Read-only with respect to registered artifacts: a run cursor is READ (for its
sessions and step windows), never written, and nothing lands in the repo — which
is why `usage` is in `fr.artifacts.trigger.READ_ONLY_COMMANDS`.

Exit codes: 0 success (an unreadable session is recorded as `unavailable` and
reported, not failed); 2 usage error (no session or run named, an unknown run,
an unknown harness).
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

from fr.run.model import archived_run_path, run_path
from fr.usage.model import UsageRecord
from fr.usage.readers import READERS
from fr.usage.render import render_html, render_table
from fr.usage.rollup import Window, rollup, windows_from_cursor
from fr.usage.sources import read_session, sessions_of

CACHE_ENV = "FR_USAGE_CACHE"

usage_app = typer.Typer(
    help="What harness sessions and runs cost, split by activity and step (read-only).",
    no_args_is_help=True,
)


def cache_root(env: Mapping[str, str]) -> Path:
    override = env.get(CACHE_ENV)
    return Path(override) if override else Path.home() / ".cache" / "fr" / "usage"


def _fail(message: str) -> typer.Exit:
    typer.echo(f"fr usage: {message}", err=True)
    return typer.Exit(2)


def _cursor(repo: Path, run: str) -> dict[str, Any]:
    for path in (run_path(repo, run), archived_run_path(repo, run)):
        if path.is_file():
            data = yaml.safe_load(path.read_text())
            if isinstance(data, dict):
                return data
    raise _fail(f"no run cursor for {run!r} under {repo}")


def _run_sessions(repo: Path, run: str) -> list[tuple[str, str]]:
    return list(dict.fromkeys(sessions_of(_cursor(repo, run))))


def _check_harness(harness: str) -> None:
    if harness not in READERS:
        raise _fail(f"unknown harness {harness!r} (one of: {', '.join(sorted(READERS))})")


def _repo(repo: Path | None) -> Path:
    return (repo or Path.cwd()).resolve()


RunOpt = Annotated[list[str] | None, typer.Option("--run", help="A run id (repeatable).")]
SessionOpt = Annotated[
    list[str] | None, typer.Option("--session", help="A harness session id (repeatable).")
]
HarnessOpt = Annotated[
    str,
    typer.Option("--harness", help="Harness of the --session ids: claude-code|opencode|hermes."),
]
RepoOpt = Annotated[
    Path | None, typer.Option("--repo", help="Repo holding the run cursors (default: cwd).")
]


@usage_app.command("collect")
def collect(
    run: RunOpt = None,
    session: SessionOpt = None,
    harness: HarnessOpt = "claude-code",
    repo: RepoOpt = None,
) -> None:
    """Normalize sessions into the usage cache (`$HOME/.cache/fr/usage/`)."""
    _check_harness(harness)
    if not run and not session:
        raise _fail("name at least one --run or --session")
    env = os.environ
    root = cache_root(env)
    wanted: list[tuple[str, str]] = [(harness, s) for s in session or ()]
    for run_id in run or ():
        pairs = _run_sessions(_repo(repo), run_id)
        index = root / "runs" / f"{run_id}.json"
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text(json.dumps({"run": run_id, "sessions": pairs}, indent=1) + "\n")
        wanted += pairs
    missing = 0
    for harness_key, session_id in dict.fromkeys(wanted):
        record = read_session(harness_key, session_id, env)
        missing += record.unavailable is not None
        out = root / harness_key / f"{session_id}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(record.model_dump_json(indent=1) + "\n")
    count = len(dict.fromkeys(wanted))
    typer.echo(f"fr usage: collected {count} session(s), {missing} unavailable -> {root}")


def _load(harness: str, session: str, env: Mapping[str, str]) -> UsageRecord:
    cached = cache_root(env) / harness / f"{session}.json"
    if cached.is_file():
        try:
            return UsageRecord.model_validate_json(cached.read_text())
        except ValueError:
            pass
    return read_session(harness, session, env)


@usage_app.command("report")
def report(
    run: RunOpt = None,
    session: SessionOpt = None,
    harness: HarnessOpt = "claude-code",
    repo: RepoOpt = None,
    fmt: Annotated[str, typer.Option("--format", help="table | html")] = "table",
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write here instead of stdout.")
    ] = None,
) -> None:
    """Render collected usage (reading live for any session not yet collected)."""
    _check_harness(harness)
    if fmt not in ("table", "html"):
        raise _fail(f"unknown --format {fmt!r} (table | html)")
    if not run and not session:
        raise _fail("name at least one --run or --session")
    env = os.environ
    pairs: list[tuple[str, str]] = [(harness, s) for s in session or ()]
    windows: list[Window] = []
    runs = list(run or ())
    for run_id in runs:
        cursor = _cursor(_repo(repo), run_id) if _has_cursor(_repo(repo), run_id) else None
        index = cache_root(env) / "runs" / f"{run_id}.json"
        if not index.is_file() and cursor is None:
            raise _fail(f"run {run_id!r}: no cursor under {_repo(repo)} and never collected")
        # the union: the cached index keeps sessions of a cursor that has since
        # gone, the live cursor adds sessions attached after the last collect
        if index.is_file():
            pairs += [(str(h), str(s)) for h, s in json.loads(index.read_text())["sessions"]]
        if cursor is not None:
            pairs += list(dict.fromkeys(sessions_of(cursor)))
        for window in windows_from_cursor(cursor) if cursor is not None else ():
            step = window.step if len(runs) == 1 else f"{run_id}:{window.step}"
            windows.append(Window(step=step, start=window.start, end=window.end))
    records = [_load(h, s, env) for h, s in dict.fromkeys(pairs)]
    result = rollup(records, windows=windows)
    text = render_table(result) if fmt == "table" else render_html(result)
    if output is None:
        typer.echo(text, nl=False)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text)
    typer.echo(f"fr usage: wrote {fmt} report for {len(records)} session(s) -> {output}")


def _has_cursor(repo: Path, run: str) -> bool:
    return run_path(repo, run).is_file() or archived_run_path(repo, run).is_file()
