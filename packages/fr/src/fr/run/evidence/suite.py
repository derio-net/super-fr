"""Suite logs as `tests` evidence: `deliver`'s fresh log, a phase's own log, a reuse of it,
and the `local` stamp it earns (spec 2026-11-27-run-verdict R7).

Moved from `fr.commands.run_cmd` in slice 5. The three verifiers return a `Verdict[str]`;
the checks every log meets (`read_suite_log`, `refuse_stale_suite_log`) raise
`RunRefusal`, which a verifier returns as its refusal with the warnings it gathered first.

Engine code: no `typer`, no `rich` but `rich.markup`, no `fr.commands`
(`tests/unit/test_run_writes_layering.py`).
"""

from __future__ import annotations

import datetime as _dt
import os
import re
from pathlib import Path
from typing import Literal

from rich.markup import escape

from fr.artifacts.paths import KIND_DIRS
from fr.git import GitUnavailableError
from fr.harness.detect import detect_harness
from fr.harness.model import HarnessError
from fr.run.evidence import refusal
from fr.run.model import RunState
from fr.run.unobserved import note_unobserved, why_tests_unobservable, why_unobservable
from fr.run.verdict import RunRefusal, Say, Verdict


def wrote_before(
    log: Path, opened: str | None, modified: _dt.datetime, slack: _dt.timedelta
) -> bool:
    """Did a command of the orchestrator's that wrote `log` start BEFORE the unit
    opened, end after it, and write the bytes on disk? Only chooses the
    refusal's wording (gh#765)."""
    from fr.run.telemetry import orchestrator_wrote_since, parse_timestamp

    opened_at = parse_timestamp(opened)
    earlier = orchestrator_wrote_since(os.environ, log, "1970-01-01T00:00:00+00:00")
    return opened_at is not None and any(
        e >= opened_at and s - slack <= modified <= e + slack for s, e in earlier or ()
    )


def verify_tests_log(key: str, log: str, repo_root: Path, *, opened: str | None) -> Verdict[str]:
    """`log` is a suite the ORCHESTRATOR ran during this unit — or a refusal.
    Returns the recorded witness, `<path>@<sha256[:12]>`.

    2026-09-21 debug journal C5: `deliver` resolved `done` 28 seconds after it
    opened with nothing but a PR url, and the PR said "verified locally" on the
    executor's word. Now the unit names the log of a suite run during delivery:
    it must exist and be non-empty, and — where the transcript is readable — a
    main-thread `Bash` call naming it must have run to completion since the unit
    opened. Unobservable: the file must at least be newer than the unit, and it
    says it could not verify who ran it.
    """
    from fr.run.telemetry import orchestrator_wrote_since, parse_timestamp

    warnings: list[Say] = []
    try:
        path, data = read_suite_log(key, log, repo_root)
    except RunRefusal as r:
        return Verdict(None, refusal=r.lines, exit_code=r.exit_code)
    modified = _dt.datetime.fromtimestamp(path.stat().st_mtime, tz=_dt.UTC)
    windows = orchestrator_wrote_since(os.environ, path, opened) if opened else None
    # One second of slack either side: the cursor stamps at second precision,
    # and a filesystem's mtime may round (review r1-1).
    slack = _dt.timedelta(seconds=1)
    if windows is not None and not any(s - slack <= modified <= e + slack for s, e in windows):
        if not windows and wrote_before(path, opened, modified, slack):
            # gh#765: the suite shared one call with the `fr run advance` that
            # opened this unit, so that call predates it. Still refused — the
            # suite must run during delivery — but "nobody wrote it" misled.
            return Verdict(
                None,
                refusal=refusal(
                    f"[red]{key}: --evidence tests={log}: the command of yours that wrote it "
                    f"was issued before this unit opened at {opened} (in the same call as "
                    "the `fr run advance` that opened it?). Run the suite again as its own "
                    "command, now that the unit is open, and name that log.[/red]"
                ),
                warnings=tuple(warnings),
            )
        why = (
            "no command of YOURS wrote it (a `>`, `>>` or `tee` naming it)"
            if not windows
            else "its bytes were not written by the command of yours that names it"
        )
        return Verdict(
            None,
            refusal=refusal(
                f"[red]{key}: --evidence tests={log}: {why} since this unit opened at "
                f"{opened}. A subagent's report is not verification — run the suite in this "
                "session, writing its output to the log you name. A backgrounded suite "
                "counts once its task-notification reports it completed (Claude Code), or "
                "once a later command of yours prints the log's exit=0 line (OpenCode's "
                "detached form, gh#719).[/red]"
            ),
            warnings=tuple(warnings),
        )
    if windows is None:
        opened_at = parse_timestamp(opened)
        if opened_at is not None and modified < opened_at:
            return Verdict(
                None,
                refusal=refusal(
                    f"[red]{key}: --evidence tests={log} predates this unit (opened {opened}) — "
                    "it is not a run of the code being delivered.[/red]"
                ),
                warnings=tuple(warnings),
            )
        note_unobserved("tests")
        warnings.append(
            Say(
                f"[yellow]{key}: could not verify who ran {log} — {why_tests_unobservable()}; "
                "recorded as a fresh log, unverified (evidence: unobserved=tests).[/yellow]",
                soft_wrap=True,
            )
        )
    try:
        refuse_stale_suite_log(key, log, path, repo_root)
    except RunRefusal as r:
        return Verdict(None, refusal=r.lines, exit_code=r.exit_code, warnings=tuple(warnings))
    return Verdict(log_witness(path, data, repo_root), warnings=tuple(warnings))


def refuse_stale_suite_log(key: str, log: str, path: Path, repo_root: Path) -> None:
    """`RunRefusal` when a code path changed after the suite log was written
    (`fr.run.code_tree.newest_code_mtime`, the phase log's freshness rule).

    gh#1454: `deliver` checked who wrote its fresh log and when, never the code it
    ran on, so code edited and committed after the suite read as covered by it
    (and a `local` stamp recorded HEAD's tree for a run that never saw it). A
    commit moves no mtime, but the edit before it does, and so does a checkout."""
    from fr.run.code_tree import default_merge_base, newest_code_mtime

    try:
        newest = newest_code_mtime(repo_root, default_merge_base(repo_root), ignore=[path])
    except GitUnavailableError as e:
        raise RunRefusal(
            refusal(
                f"[red]{key}: --evidence tests={log}: cannot tell which code it covers — "
                f"{escape(str(e))}[/red]"
            )
        ) from e
    if newest is not None and newest[0] > path.stat().st_mtime:
        raise RunRefusal(
            refusal(
                f"[red]{key}: --evidence tests={log} is stale — {newest[1]} changed after "
                "the log was written, so the suite did not run the code being delivered. "
                "Run the full suite again and name the new log.[/red]"
            )
        )


def read_suite_log(key: str, log: str, repo_root: Path) -> tuple[Path, bytes]:
    """`(resolved path, bytes)` of a named suite log — or `RunRefusal` when it sits
    in a run's records dir or is missing or empty. The checks every `tests=`
    log meets, whoever wrote it (`deliver`'s and a phase unit's alike)."""
    from fr.record.model import RECORDS_SUFFIX

    path = (Path(log) if Path(log).is_absolute() else repo_root / log).resolve()
    try:
        rel_parts = path.relative_to(repo_root.resolve()).parts
    except ValueError:
        rel_parts = ()
    if rel_parts[:3] == Path(KIND_DIRS["run"]).parts and (
        len(rel_parts) > 4 and rel_parts[3].endswith(RECORDS_SUFFIX)
    ):
        # gh#638: `<run>.records/` holds step records and fr's pr-body render,
        # and fr empties it; a log written there got committed and reached
        # `main` with nothing to remove it.
        raise RunRefusal(
            refusal(
                f"[red]{key}: --evidence tests={log} is inside a run's records dir, which "
                "holds step records only and is emptied by fr. Write the suite log outside "
                "the repo (e.g. $TMPDIR/full-suite.log) and name that path.[/red]"
            )
        )
    try:
        data = path.read_bytes()
    except OSError:
        data = b""
    if not data:
        raise RunRefusal(
            refusal(
                f"[red]{key}: --evidence tests={log} is missing or empty — run the full suite "
                "yourself, write its output to a file, and name that file.[/red]"
            )
        )
    from fr.run.ci_evidence import ADVISORY_LINE, is_advisory_log

    if is_advisory_log(data):
        # Spec 2026-11-19-local-suite-cost R7: a narrowed pytest session (the fast
        # tier, `-m`/`-k`, explicit paths, --lf/--sw) marks itself advisory. It is
        # not the whole suite, so it is no `tests` evidence, and a phase log refused
        # here is never a witness `tests: reuse` could carry into `deliver`.
        raise RunRefusal(
            refusal(
                f"[red]{key}: --evidence tests={log} holds the line `{ADVISORY_LINE}`: it is "
                "not the whole suite. A session prints it when it ran with --fr-scope, a "
                "non-empty -m or -k (the default local run's -m 'not scenario' included), "
                "explicit paths or from a subdirectory, --lf, --sw, --ignore/--ignore-glob/"
                "--deselect, -x/--maxfail, -o testpaths= or --collect-only; the line before "
                "it in the log, `fr-scope: advisory because ...`, names which. Run the full "
                'suite with `pytest -m ""` into a log and name that file, or offer '
                "`tests: ci`.[/red]"
            )
        )
    return path, data


def log_witness(path: Path, data: bytes, repo_root: Path) -> str:
    """`<shown>@<sha256[:12]>`. Review r1-8: the witness lands in a git-tracked
    cursor, so it names the log repo-relative, or by basename when it lives
    outside the repo — never an absolute path carrying someone's home
    directory."""
    import hashlib

    try:
        shown = str(path.relative_to(repo_root.resolve()))
    except ValueError:
        shown = path.name
    return f"{shown}@{hashlib.sha256(data).hexdigest()[:12]}"


def phase_log_windows(
    path: Path, opened: str | None, holder: str | None
) -> list[tuple[_dt.datetime, _dt.datetime]] | str | Literal[False] | None:
    """The run windows of the holder's commands that wrote `path` — read
    through `fr.run.observed` from the holder's own session: the claimed
    agent's child (a Claude Code subagent transcript, an OpenCode child
    session), or the run session itself when the unit ran inline (no holder).

    `False` when this session dispatched no agent `holder` (a bogus or foreign
    id: refused, never unobserved); a `str` reason when nothing can be read —
    including Hermes, which has no session reader (spec
    2026-09-29-fr-goal-light-path §D, §E; 2026-10-02-opencode-observe-2 §A)."""
    from fr.run.observed import observed_session
    from fr.run.telemetry import parse_timestamp

    try:
        harness = detect_harness(os.environ)
    except HarnessError:
        harness = None
    if harness == "hermes":
        return f"fr has no child-session reader for {harness}, so a phase log is not witnessed"
    view = observed_session(os.environ)
    start = parse_timestamp(opened)
    if view is None or start is None:
        return why_unobservable("commands") if view is None else "the unit has no opening stamp"
    found = view.child(holder) if holder is not None else view
    if found is None:
        return f"the session {view.session} could not be read"
    if found is False:
        return False
    windows = found.wrote_windows(path, start)
    if windows is None:
        return f"the holder's session {found.session} could not be read"
    return windows


TESTS_REUSE = "reuse"
"""`deliver`'s `tests: reuse` — the most recent phase suite log stands in for a
fresh run while the code tree it covered is unchanged (spec
2026-09-29-fr-goal-light-path §D, R6)."""
TREE_SEP = ";tree="
REUSED_PREFIX = "reused:"
TESTS_CI = "ci"
"""`tests: ci` — the forge's CI on the pushed head stands in for a local suite
log (spec 2026-10-07-cloud-triage R22, §I; `fr.run.ci_evidence`)."""


def latest_tests_witness(state: RunState) -> tuple[str, str] | None:
    """`(unit key, witness)` of the most recently resolved `done` unit whose
    `tests` evidence carries a code tree (a phase unit's,
    `verify_phase_tests_log`), or `None`. "Most recently" is the unit's last
    attempt's `returned`; a unit with none sorts first, and a tie goes to the
    later unit in cursor order."""
    best: tuple[str, int, str, str] | None = None
    seq = 0
    for record in state.steps.values():
        for key, unit in (record.units or {}).items():
            seq += 1
            witness = (unit.evidence or {}).get("tests", "")
            if TREE_SEP not in witness or witness.startswith(REUSED_PREFIX):
                continue
            # Review r2-3: only a unit that is `done` NOW vouches for its tree
            # — a failed one, or one re-dispatched since, does not.
            if (unit.state or record.state) != "done":
                continue
            returned = unit.attempts[-1].returned if unit.attempts else None
            candidate = (returned or "", seq, key, witness)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
    return (best[2], best[3]) if best is not None else None


def reuse_tests_witness(key: str, repo_root: Path, state: RunState) -> Verdict[str]:
    """`reused:<unit>:<witness>` when HEAD's code tree equals the tree of the
    most recently resolved unit carrying a suite log and no code path is
    uncommitted — or a refusal with the fresh-run instruction."""
    from fr.run.code_tree import code_paths_since_tree, code_tree, dirty_code_paths
    from fr.run.telemetry import UNOBSERVED

    latest = latest_tests_witness(state)
    if latest is None:
        return Verdict(
            None,
            refusal=refusal(
                f"[red]{key}: tests: reuse — no phase unit recorded a suite log "
                "(`evidence: {tests: <log>}` on an implement-phase or review-phase record); "
                "run the full suite yourself into a log and name it.[/red]"
            ),
        )
    unit, witness = latest
    recorded = witness.rpartition(TREE_SEP)[2]
    own_log = own_log_path(repo_root, witness.rpartition(TREE_SEP)[0])
    try:
        dirty = [p for p in dirty_code_paths(repo_root) if p != own_log]
        same = code_tree(repo_root) == recorded and not dirty
        changed = None if same else code_paths_since_tree(repo_root, recorded)
        if changed is not None:
            changed = [p for p in changed if p != own_log]
    except GitUnavailableError as e:
        return Verdict(
            None,
            refusal=refusal(
                f"[red]{key}: tests: reuse — cannot compute the code tree: {escape(str(e))}[/red]"
            ),
        )
    if not same:
        if changed:
            n = len(changed)
            what = f"{n} path{'' if n == 1 else 's'}, e.g. {changed[0]}"
        else:
            what = "its commit is not in HEAD's recent history"
        return Verdict(
            None,
            refusal=refusal(
                f"[red]{key}: tests: reuse — the code tree changed since {unit} ({what}); "
                "run the full suite yourself into a log and name it.[/red]"
            ),
        )
    reused = f"{REUSED_PREFIX}{unit}:{witness}"
    if "tests" not in unit_evidence(state, unit).get(UNOBSERVED, "").split(","):
        return Verdict(reused)
    # Review r2-4: a reuse is no better verified than the log it reuses.
    note_unobserved("tests")
    warning = Say(
        f"[yellow]{key}: {unit}'s suite log was recorded unverified "
        "(evidence: unobserved=tests), so this reuse is unverified too.[/yellow]",
        soft_wrap=True,
    )
    return Verdict(reused, warnings=(warning,))


FRESH_LOG_WITNESS = re.compile(r"^[^;]+@[0-9a-f]{12}$")
"""A fresh `tests=<log>` witness, `<shown>@<sha256[:12]>` (`log_witness`)."""


def local_stamp_witness(repo_root: Path, tests: str | None) -> tuple[str, str] | str:
    """`(log, tree)` a `local` stamp records for `deliver`'s verified `tests` witness, or
    why that witness cannot earn one (spec 2026-11-14-acceptance-local-status R4).

    A `reused:` witness (`reuse_tests_witness`) carries the tree its phase log covered.
    A fresh log (`verify_tests_log`, observed or `unobserved=tests`) covers HEAD's code
    tree only when no code path is uncommitted. Anything else (`tests: ci`, no witness)
    is no local run of the suite."""
    from fr.run.code_tree import code_tree, dirty_code_paths

    if tests is not None and tests.startswith(REUSED_PREFIX):
        log, sep, tree = tests.rpartition(TREE_SEP)
        if not sep or not tree:
            return f"tests: {tests} names no code tree"
        return log, tree
    if tests is None or not FRESH_LOG_WITNESS.match(tests):
        shown = "none" if tests is None else tests
        return (
            f"tests: {shown} is not a local suite log — a `local` row is earned by a "
            "fresh suite log or a `tests: reuse` of a phase's"
        )
    try:
        own = own_log_path(repo_root, tests)
        dirty = [p for p in dirty_code_paths(repo_root) if p != own]
        tree = code_tree(repo_root)
    except GitUnavailableError as e:
        return f"cannot compute the code tree: {e}"
    if dirty:
        n = len(dirty)
        return (
            f"{n} code path{'' if n == 1 else 's'} uncommitted (e.g. {dirty[0]}), so the "
            "suite log does not cover HEAD — commit, run the suite again and name the new log"
        )
    return tests, tree


def unit_evidence(state: RunState, key: str) -> dict[str, str]:
    """`key`'s evidence, from whichever step holds that unit (`{}` if none)."""
    for record in state.steps.values():
        unit = (record.units or {}).get(key)
        if unit is not None:
            return dict(unit.evidence or {})
    return {}


def own_log_path(repo_root: Path, witness: str) -> str | None:
    """The repo-relative path of the log `witness` (`<shown>@<sha[:12]>`)
    names, when that file is in the worktree with exactly those bytes — so an
    untracked suite log does not read as uncommitted code (review r2-5). A
    same-named file with other bytes is not the log, and stays dirty."""
    import hashlib

    shown, _, digest = witness.rpartition("@")
    if not shown or not digest:
        return None
    path = repo_root / shown
    try:
        data = path.read_bytes() if path.is_file() else None
    except OSError:
        return None
    if data is None or hashlib.sha256(data).hexdigest()[:12] != digest:
        return None
    return Path(shown).as_posix()


def verify_phase_tests_log(
    key: str,
    log: str,
    repo_root: Path,
    *,
    opened: str | None,
    holder: str | None,
    record_tree: bool = True,
) -> Verdict[str]:
    """A phase unit's own suite log (spec 2026-09-29-fr-goal-light-path §D,
    R6) — or a refusal. Returns `<shown>@<sha256[:12]>;tree=<code-tree>`.

    1. **Writer** — `verify_tests_log`'s rules, read from the HOLDER's
       transcript (`phase_log_windows`); unreadable records `unobserved=tests`.
    2. **Freshness** — the log is no older than any tracked code path, any
       directory holding one, or the directory a code path was deleted or
       renamed out of since the merge-base (`fr.run.code_tree.newest_code_mtime`).
    3. **Witness** — the code tree of HEAD. Computed here, before the record's
       own commit, and equal to the tree after it: that commit writes only fr's
       artifact trees, which the code tree excludes by definition. HEAD's tree
       is what the suite ran only when nothing is uncommitted, so a dirty code
       path (the log itself aside) is refused (review r2-1).

    `record_tree=False` (a resolve that is not `done`, review r2-3) checks the
    writer only and returns `<shown>@<sha256[:12]>` — a failed phase vouches
    for no tree, so there is no tree to record and nothing to keep fresh.
    """
    from fr.run.code_tree import (
        code_tree,
        default_merge_base,
        dirty_code_paths,
        newest_code_mtime,
    )
    from fr.run.telemetry import parse_timestamp

    warnings: list[Say] = []
    try:
        path, data = read_suite_log(key, log, repo_root)
    except RunRefusal as r:
        return Verdict(None, refusal=r.lines, exit_code=r.exit_code)
    modified = _dt.datetime.fromtimestamp(path.stat().st_mtime, tz=_dt.UTC)
    windows = phase_log_windows(path, opened, holder)
    if windows is False:
        return Verdict(
            None,
            refusal=refusal(
                f"[red]{key}: --evidence tests={log}: this session dispatched no agent "
                f"{holder!r}, so the unit's holder cannot be the one who ran the suite. "
                "Name the agent id the executor's dispatch returned.[/red]"
            ),
            warnings=tuple(warnings),
        )
    slack = _dt.timedelta(seconds=1)
    if isinstance(windows, list):
        if not any(s - slack <= modified <= e + slack for s, e in windows):
            why = (
                "no command of the unit's holder wrote it (a `>`, `>>` or `tee` naming it)"
                if not windows
                else "its bytes were not written by the holder's command that names it"
            )
            return Verdict(
                None,
                refusal=refusal(
                    f"[red]{key}: --evidence tests={log}: {why} since this unit opened at "
                    f"{opened}. Name the log the phase's own full-suite run wrote, or leave "
                    "`tests` out of the record.[/red]"
                ),
                warnings=tuple(warnings),
            )
    else:
        opened_at = parse_timestamp(opened)
        if opened_at is not None and modified < opened_at:
            return Verdict(
                None,
                refusal=refusal(
                    f"[red]{key}: --evidence tests={log} predates this unit (opened {opened}) — "
                    "it is not a run of this phase's code.[/red]"
                ),
                warnings=tuple(warnings),
            )
        note_unobserved("tests")
        warnings.append(
            Say(
                f"[yellow]{key}: could not verify who ran {log} — {windows}; recorded "
                "unverified (evidence: unobserved=tests).[/yellow]",
                soft_wrap=True,
            )
        )
    if not record_tree:
        return Verdict(log_witness(path, data, repo_root), warnings=tuple(warnings))
    try:
        own = own_log_path(repo_root, log_witness(path, data, repo_root))
        dirty = [p for p in dirty_code_paths(repo_root) if p != own]
        newest = newest_code_mtime(repo_root, default_merge_base(repo_root), ignore=[path])
        tree = code_tree(repo_root)
    except GitUnavailableError as e:
        return Verdict(
            None,
            refusal=refusal(
                f"[red]{key}: --evidence tests={log}: cannot compute the code tree it "
                f"covers — {escape(str(e))}[/red]"
            ),
            warnings=tuple(warnings),
        )
    if dirty:
        n = len(dirty)
        return Verdict(
            None,
            refusal=refusal(
                f"[red]{key}: --evidence tests={log}: {n} code path{'' if n == 1 else 's'} "
                f"uncommitted (e.g. {dirty[0]}) — the witness is HEAD's tree, which is not "
                "what the suite ran. Commit your code before recording the suite log, then "
                "run the full suite again and name the new log.[/red]"
            ),
            warnings=tuple(warnings),
        )
    if newest is not None and newest[0] > path.stat().st_mtime:
        return Verdict(
            None,
            refusal=refusal(
                f"[red]{key}: --evidence tests={log} is stale — {newest[1]} changed after "
                "the log was written, so the suite did not run the code being recorded. "
                "Run the full suite again and name the new log.[/red]"
            ),
            warnings=tuple(warnings),
        )
    return Verdict(
        f"{log_witness(path, data, repo_root)}{TREE_SEP}{tree}", warnings=tuple(warnings)
    )
