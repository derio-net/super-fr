"""The obligatory trigger at CLI entry, context-aware (spec §3.C).

`fr.cli`'s root callback calls `ensure_artifacts_current` before every command:

    fr <any command>
      └─ artifacts stale?
           ├─ interactive  → migrate, commit, continue
           └─ daemon / CI  → refuse loudly, exit non-zero

**Interactive** means a TTY with `CI` unset. Then the operator gets the "pause,
migrate, resume" they asked for, and the pause is invisible because the command
they typed still runs afterwards.

**Non-interactive** means refuse, exit non-zero, name the command to run — and
*never* migrate, never commit. The bridge works from a checkout it `reset
--hard`s to `origin/main` every tick (#286), so a commit there is discarded on
the next pass: auto-committing would be pointless *and* actively misleading.
That asymmetry is the whole reason this module has a context predicate at all,
and Phase 5's daemon refusal reuses `is_interactive` rather than growing a
second one.

Three properties this module is built around:

1. **It runs before every command, so it must be cheap.** Detection is
   `runner.is_stale`, which short-circuits on the first stale artifact; nothing
   here plans or walks the tree a second time when the answer is "no".
2. **The exemption list is narrow and closed.** An over-broad exemption
   disables the mechanism in the quietest possible way — everything keeps
   working and nothing ever migrates. `EXEMPTIONS` is pinned by a test.
3. **Nothing escapes as a traceback.** `is_stale` / `run_migrations` raise
   `MigrationChainError` when an artifact sits at a version no registered
   migration moves. That is a registry bug, and a registry bug must not crash
   an unrelated command: it becomes a loud refusal with exit 2.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

import typer

# The PACKAGE, not `fr.artifacts.runner`: importing `fr.artifacts` is what
# registers the built-in migrations (`fr_version`) into `MIGRATIONS`. Reaching
# straight for the runner would give a gate that walks an empty registry and
# cheerfully reports every tree as current.
from fr.artifacts import is_stale, run_migrations
from fr.artifacts.commit import commit_migration
from fr.artifacts.runner import MigrationRegistry, MigrationReport

# --- what is exempt ------------------------------------------------------

EXEMPT_OPTIONS: Final[frozenset[str]] = frozenset({"--help", "--version"})
"""Asking what `fr` is must never rewrite the repo."""

EXEMPT_COMMANDS: Final[frozenset[str]] = frozenset({"migrate"})
"""`fr migrate` cannot require itself — and `fr migrate artifacts` (dry-run by
default) has to stay a preview rather than becoming its own trigger."""

SKIP_ENV_VAR: Final[str] = "FR_SKIP_MIGRATION"
"""Recovery escape for when a migration is the thing that is broken."""

EXEMPTIONS: Final[tuple[str, ...]] = ("--help", "--version", "migrate", f"{SKIP_ENV_VAR}=1")
"""The complete list, flattened, so a test can assert it is *exactly* these."""

_SKIP_FALSY: Final[frozenset[str]] = frozenset({"", "0", "false", "no", "off"})
"""`FR_SKIP_MIGRATION=0` meaning "skip" would be a nasty surprise."""


def is_exempt(
    *,
    argv: Sequence[str] | None = None,
    invoked_subcommand: str | None = None,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Should the gate stay out of the way entirely?

    `invoked_subcommand` comes from click's group context, which is exact.
    `argv` (defaulting to the process argv) is only consulted for the two
    option tokens: click handles a top-level `--help` / `--version` eagerly and
    never reaches this callback, but `fr plan --help` *does* reach it, and by
    then the group context no longer carries the subcommand's own arguments
    (`ctx.args` is empty on click 8.3).
    """
    environ = os.environ if env is None else env
    skip = (environ.get(SKIP_ENV_VAR) or "").strip().lower()
    if skip not in _SKIP_FALSY:
        return True
    if invoked_subcommand is not None and invoked_subcommand in EXEMPT_COMMANDS:
        return True
    tokens = sys.argv[1:] if argv is None else argv
    return any(token in EXEMPT_OPTIONS for token in tokens)


# --- what context this is ------------------------------------------------


def _isatty(stream: Any) -> bool:
    """Prefer refusing: a stream that cannot answer is not a yes."""
    if stream is None:
        return False
    try:
        return bool(stream.isatty())
    except Exception:
        return False


def is_interactive(
    *,
    env: Mapping[str, str] | None = None,
    stdin: Any = None,
    stdout: Any = None,
) -> bool:
    """Is this an operator at a terminal, as opposed to a daemon or CI?

    Two independent signals, both of which must say yes:

    - `CI` unset (or empty). Every CI provider sets it, and it is the one
      signal that survives a runner that *does* allocate a pty.
    - stdin **and** stdout are both a TTY. Requiring both is deliberate: the
      cost of being wrongly non-interactive is a recoverable refusal that names
      the command to run, while the cost of being wrongly interactive is an
      unexpected commit in someone else's checkout.

    The bridge needs no special case — it has no TTY. Phase 5 calls this same
    predicate rather than inventing a second answer to the same question.
    """
    environ = os.environ if env is None else env
    if (environ.get("CI") or "").strip():
        return False
    return _isatty(sys.stdin if stdin is None else stdin) and _isatty(
        sys.stdout if stdout is None else stdout
    )


# --- the gate ------------------------------------------------------------


def _echo_err(line: str) -> None:
    # Plain echo, not rich: rich soft-wraps and splits copy-pasteable commands
    # and long paths across lines. Everything the gate says goes to STDERR, so
    # it can never contaminate the stdout of the command the operator typed.
    typer.echo(line, err=True)


def _refuse(emit: Callable[[str], None], lines: Sequence[str]) -> typer.Exit:
    for line in lines:
        emit(line)
    return typer.Exit(2)


def ensure_artifacts_current(
    *,
    argv: Sequence[str] | None = None,
    invoked_subcommand: str | None = None,
    env: Mapping[str, str] | None = None,
    repo_root: Path | None = None,
    registry: MigrationRegistry | None = None,
    interactive: bool | None = None,
    commit: Callable[[Path, MigrationReport], Any] | None = None,
    err: Callable[[str], None] | None = None,
) -> None:
    """Migrate stale artifacts, or refuse — before the invoked command runs.

    Returns normally in the two cases where the command should proceed: nothing
    was stale, or everything stale was migrated. Every other outcome raises
    `typer.Exit(2)`.

    `registry`, `interactive`, `commit` and `err` are injection points for
    tests, mirroring the runner's own `registry=`; production passes none of
    them.
    """
    environ = os.environ if env is None else env
    if is_exempt(argv=argv, invoked_subcommand=invoked_subcommand, env=environ):
        return

    emit = err if err is not None else _echo_err

    if repo_root is not None:
        root = repo_root
    else:
        # Imported here, not at module scope: `fr.artifacts` is a lower layer
        # than `fr.commands`, and the gate is the one place the two meet.
        from fr.commands.common import resolve_repo_root

        root = resolve_repo_root()

    try:
        stale = is_stale(root, registry=registry)
    except Exception as e:
        raise _refuse(
            emit,
            [
                f"fr: cannot tell whether the artifacts in {root} are current.",
                f"  {type(e).__name__}: {e}",
                "  Refusing rather than running over a tree of unknown state.",
                f"  Inspect with `fr migrate artifacts` (dry-run), or set "
                f"{SKIP_ENV_VAR}=1 to bypass this check.",
            ],
        ) from e

    if not stale:
        return

    live = interactive if interactive is not None else is_interactive(env=environ)
    if not live:
        raise _refuse(
            emit,
            [
                f"fr: artifacts in {root} were written for a different fr and must be "
                "migrated before this command can run.",
                "  This context is non-interactive (CI is set, or there is no TTY), so fr "
                "will not migrate or commit here:",
                "  a daemon checkout is hard-reset every tick, so a commit made in it "
                "would be silently discarded.",
                "  preview:  fr migrate artifacts",
                "  apply:    fr migrate artifacts --yes",
                f"  bypass (recovery only):  {SKIP_ENV_VAR}=1 fr <command>",
            ],
        )

    emit(f"fr: artifacts in {root} are out of date — migrating before running the command.")
    try:
        report = run_migrations(root, dry_run=False, registry=registry)
    except Exception as e:
        raise _refuse(
            emit,
            [
                f"fr: artifact migration failed: {type(e).__name__}: {e}",
                f"  Nothing was committed. Run `fr migrate artifacts` to inspect, or set "
                f"{SKIP_ENV_VAR}=1 to bypass this check.",
            ],
        ) from e

    for action in report.applied:
        emit(f"  migrated: {_rel(action.path, root)} · {action.summary}")
    for skipped in report.skipped:
        emit(f"  skipped (another writer got there first): {_rel(skipped.path, root)}")

    if report.applied:
        do_commit = commit if commit is not None else commit_migration
        try:
            outcome = do_commit(root, report)
        except Exception as e:
            # The files ARE migrated; only the commit failed. Say so and let
            # the command run — refusing here would strand the operator with a
            # migrated tree and a command that never works.
            emit(f"  warning: could not commit the migration ({type(e).__name__}: {e});")
            emit("  the migrated files are in your working tree, uncommitted.")
        else:
            reason = getattr(outcome, "reason", None)
            if reason:
                emit(f"  {reason}")

    # Spec §3.E: the migration REPORTS in-flight plans that have no run cursor.
    # It stops at reporting here on purpose. This runs before an unrelated
    # command — an operator who typed `fr status` must not come back to new
    # git-tracked run files they never asked for. `fr migrate artifacts
    # --adopt` and `fr run adopt` are the two places that actually write one.
    for line in _adoption_offer(root):
        emit(line)

    if report.failed:
        for failure in report.failed:
            emit(f"  FAILED: {_rel(failure.path, root)} · {failure.error}")
        raise _refuse(
            emit,
            [
                f"fr: {len(report.failed)} artifact(s) could not be migrated and were left "
                "unmodified.",
                "  Refusing to run over a half-migrated tree. Fix them by hand, or set "
                f"{SKIP_ENV_VAR}=1 to bypass this check.",
            ],
        )


def _adoption_offer(repo_root: Path) -> tuple[str, ...]:
    """Imported lazily: `fr.run.adopt` reaches `fr.parser`/`fr.render`, and the
    gate runs before EVERY command — it must stay cheap when nothing is stale
    (the common case returns above without ever calling this)."""
    from fr.run.adopt import adoption_offer_lines

    return adoption_offer_lines(repo_root)


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:  # pragma: no cover — every artifact is under the root
        return str(path)
