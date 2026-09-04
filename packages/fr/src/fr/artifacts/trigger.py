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
*never* migrate, never commit. So does **HEAD being the repository's default
branch**: a commit made automatically on `main`, before a command the operator
typed for some other reason, is work they have to notice and undo. So does an
artifact the operator has **uncommitted changes in**: `git add -- <path>`
stages the whole file, so migrating it would commit their half-typed edit under
a `chore(fr): migrate ...` message. The bridge works from a checkout it `reset
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
   `MigrationChainError` when an artifact sits at a *declared* version no
   registered migration moves. That is a registry bug, and a registry bug must
   not crash an unrelated command: it becomes a loud refusal with exit 2.
4. **Every refusal has the same shape.** Say what is wrong, say why fr will not
   act here, then give the preview command, the apply command and the bypass.
   Three of the four refusals below are the same six lines with one clause
   changed, and that is deliberate: an operator who has read one has read them
   all.
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
from fr.artifacts.atomic import migration_lock
from fr.artifacts.commit import (
    GitContext,
    GitRefusal,
    commit_migration,
    git_context,
    lock_path,
    uncommitted_veto,
)
from fr.artifacts.runner import MigrationRegistry, MigrationReport

# --- what is exempt ------------------------------------------------------

EXEMPT_OPTIONS: Final[frozenset[str]] = frozenset({"--help", "--version"})
"""Asking what `fr` is must never rewrite the repo."""

READ_ONLY_COMMANDS: Final[tuple[str, ...]] = (
    "status",
    "skills",
    "isolation",
    "init",
    "validate",
)
"""Commands that promise not to mutate the repo's artifacts — so the gate must
not mutate them on their behalf.

`fr status` is registered as "Read-only plan report (allowlist-safe; never
mutates)"; before this exemption it could rewrite every stale artifact and
create a commit. `fr validate artifacts` is worse than surprising: interactive,
the gate migrated and committed *before* the validator ran, so a human could
never see it report a stale artifact — only CI, which is non-interactive, ever
could. That guts the diagnostic. `fr isolation` and `fr init` are the two
commands an operator reaches for when the workspace is not yet in a state to be
migrated at all."""

EXEMPT_COMMANDS: Final[frozenset[str]] = frozenset({"migrate", *READ_ONLY_COMMANDS})
"""`fr migrate` cannot require itself — and `fr migrate artifacts` (dry-run by
default) has to stay a preview rather than becoming its own trigger. The rest
are `READ_ONLY_COMMANDS`."""

SKIP_ENV_VAR: Final[str] = "FR_SKIP_MIGRATION"
"""Recovery escape for when a migration is the thing that is broken."""

EXEMPTIONS: Final[tuple[str, ...]] = (
    "--help",
    "--version",
    "migrate",
    *READ_ONLY_COMMANDS,
    f"{SKIP_ENV_VAR}=1",
)
"""The complete list, flattened, so a test can assert it is *exactly* these."""

_SKIP_FALSY: Final[frozenset[str]] = frozenset({"", "0", "false", "no", "off"})
"""`FR_SKIP_MIGRATION=0` meaning "skip" would be a nasty surprise."""

CI_ENV_VARS: Final[tuple[str, ...]] = (
    "CI",
    "GITHUB_ACTIONS",
    "GITLAB_CI",
    "BUILDKITE",
    "JENKINS_URL",
    "TF_BUILD",
    "TEAMCITY_VERSION",
    "CIRCLECI",
)
"""Environment markers that mean "this is automation, not an operator".

`CI` alone was the whole test (review r5-e8). Every provider here sets `CI`
*as well*, so this is belt-and-braces rather than a fix for a known escape —
but the cost of a wrongly-interactive verdict is an unexpected commit in a
runner's checkout, and the cost of the list is one dict lookup per name. Each
is read with the same truthiness rule as `CI`: a marker set to `false`/`0` is
someone explicitly saying "not CI", and is honoured.

Pinned literally by `tests/unit/test_migration_trigger.py` so adding one means
arguing for it in a diff.
"""

NON_INTERACTIVE_ENV_VAR: Final[str] = "FR_NON_INTERACTIVE"
"""Explicit opt-out for an operator (or wrapper) that HAS a TTY but does not
want fr writing to git — a `script`/`expect` harness, a tmux-driven agent, a
pairing session. Truthy means non-interactive; falsy means "no opinion", not
"force interactive": a real CI marker still wins."""

_FALSY: Final[frozenset[str]] = frozenset({"", "0", "false", "no", "off"})


def _truthy(environ: Mapping[str, str], name: str) -> bool:
    return (environ.get(name) or "").strip().lower() not in _FALSY


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

    **A `--help` that is an option VALUE is not a request for help** (review
    r5-c5). The test was `any(token in EXEMPT_OPTIONS for token in tokens)`,
    which matched anywhere — so `fr journal add --text --help` exempted a
    command that writes to the repo, on the strength of somebody's entry text.
    `_asks_for_help` instead refuses the match when the preceding token is an
    option that could be consuming it.
    """
    environ = os.environ if env is None else env
    skip = (environ.get(SKIP_ENV_VAR) or "").strip().lower()
    if skip not in _SKIP_FALSY:
        return True
    if invoked_subcommand is not None and invoked_subcommand in EXEMPT_COMMANDS:
        return True
    tokens = sys.argv[1:] if argv is None else argv
    return _asks_for_help(tokens)


def _asks_for_help(tokens: Sequence[str]) -> bool:
    """Is one of `EXEMPT_OPTIONS` here as an OPTION rather than as a value?

    Without click's parameter table the arity of an option is unknowable, so
    the rule is positional and deliberately conservative: `--help` counts
    unless the token immediately before it is a bare option token, in which
    case it may be that option's value.

    - `fr --help`, `fr plan --help`, `fr plan create --help` → yes; the
      preceding token is a command word or nothing.
    - `fr apply --format json --help` → yes; `json` is a value, not an option.
    - `fr journal add --text --help` → **no**; `--text` takes a value and this
      is it. This is the case the fix exists for.
    - `fr apply --yes --help` → no, conservatively. `--yes` is a flag, so this
      IS a help request, and the cost of the false negative is that the gate
      runs before help prints — a refusal at worst, never a silent write. The
      opposite error disables the gate, so the asymmetry is deliberate.

    `--opt=value` is self-contained and cannot consume the next token.
    Everything after a bare `--` is a positional argument by definition.
    """
    previous: str | None = None
    for token in tokens:
        if token == "--":
            return False
        if token in EXEMPT_OPTIONS:
            consumed_by_previous = (
                previous is not None
                and previous.startswith("-")
                and previous != "-"
                and "=" not in previous
            )
            if not consumed_by_previous:
                return True
        previous = token
    return False


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

    Three independent signals, all of which must say yes:

    - **No CI marker is truthy** (`CI_ENV_VARS`). These survive a runner that
      *does* allocate a pty. Truthiness matters: `CI=false` is a person saying
      "not CI", and reading it as "CI is set" was a real trap — the previous
      test was `(environ.get("CI") or "").strip()`, so `CI=0` and `CI=false`
      both made an operator's terminal non-interactive (review r5-e8).
    - **`FR_NON_INTERACTIVE` is not truthy** — the explicit opt-out for a
      TTY-bearing wrapper that still does not want fr writing to git.
    - stdin **and** stdout are both a TTY. Requiring both is deliberate: the
      cost of being wrongly non-interactive is a recoverable refusal that names
      the command to run, while the cost of being wrongly interactive is an
      unexpected commit in someone else's checkout.

    The bridge needs no special case — it has no TTY. Phase 5 calls this same
    predicate rather than inventing a second answer to the same question.
    """
    environ = os.environ if env is None else env
    if any(_truthy(environ, name) for name in CI_ENV_VARS):
        return False
    if _truthy(environ, NON_INTERACTIVE_ENV_VAR):
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

    Four outcomes, not three (review r5-c5):

    1. **Nothing was stale** — returns immediately, no git call.
    2. **Everything stale was migrated** — returns; the command runs.
    3. **fr will not act here** — non-interactive, the default branch, a
       detached HEAD, unestablished git state, another fr holding the lock, or
       an artifact the operator is editing. Nothing is written; `typer.Exit(2)`.
    4. **PARTIAL success** — some artifacts migrated (and possibly committed)
       and others did not. Still `typer.Exit(2)`, because a half-migrated tree
       is not one to run a command over, but the message says how many landed:
       an operator told only "N could not be migrated" re-runs and is surprised
       by a commit that already exists.

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
            _will_not_act_here(
                root,
                "This context is non-interactive (CI is set, or there is no TTY), so fr "
                "will not migrate or commit here:",
                "a daemon checkout is hard-reset every tick, so a commit made in it "
                "would be silently discarded.",
            ),
        )

    # ONE place asks git anything (review r5-c1/c2/c3). Every branch below
    # reads the same snapshot, so the default-branch guard, the detached-HEAD
    # refusal and the uncommitted-file veto cannot disagree about the tree —
    # and a git that could not answer refuses ONCE, loudly, instead of each
    # predicate independently degrading to a permissive default.
    state = git_context(root)
    if isinstance(state, GitRefusal):
        raise _refuse(
            emit,
            _will_not_act_here(
                root,
                "fr could not establish this repository's git state, so it will not "
                "migrate or commit here:",
                f"{state.reason} Unknown git state is not a clean one.",
            ),
        )
    if isinstance(state, GitContext):
        if _fell_back_to_cwd(root, state):
            raise _refuse(
                emit,
                _will_not_act_here(
                    root,
                    f"{root} is not this repository's root (git says {state.toplevel}), so "
                    "fr will not migrate or commit here:",
                    "the migration would run over a subtree while the commit named paths "
                    "outside it. Run fr from the repository root.",
                ),
            )
        if state.branch is None:
            raise _refuse(
                emit,
                _will_not_act_here(
                    root,
                    "HEAD is detached (a rebase, a bisect, or a checked-out commit), so fr "
                    "will not migrate or commit here:",
                    "a commit made now is folded into the operation in progress or "
                    "orphaned by the next checkout. Finish or abort it first.",
                ),
            )
        if state.branch == state.default_branch:
            raise _refuse(
                emit,
                _will_not_act_here(
                    root,
                    f"HEAD is {state.branch!r}, this repository's default branch, so fr will "
                    "not migrate or commit here:",
                    "an automatic commit on a protected branch is work you have to notice "
                    "and undo. Do it on a branch, or run the migration yourself.",
                ),
            )

    emit(f"fr: artifacts in {root} are out of date — migrating before running the command.")
    # One migration at a time, per repository (review r5-e7). Two agents — or
    # an agent and the operator — running `fr` in the same second would both
    # plan the same work, both apply it, and both try to commit; the second
    # produces a duplicate or an empty commit. The lock lives in the git COMMON
    # directory, so linked worktrees of one repo share it.
    with migration_lock(lock_path(root)) as acquired:
        if not acquired:
            if not _still_stale(root, registry):
                emit("  another fr process migrated this tree; continuing.")
                return
            raise _refuse(
                emit,
                _will_not_act_here(
                    root,
                    "another fr process is migrating this repository right now, so fr "
                    "will not migrate or commit here:",
                    "two migrations of one tree race each other into two commits. "
                    "Re-run this command once it finishes.",
                ),
            )
        _migrate_and_commit(root, registry, commit, emit)


def _still_stale(root: Path, registry: MigrationRegistry | None) -> bool:
    """Re-check after losing the lock. The winner has very likely just done
    exactly this work, in which case there is nothing left to do and the
    command the operator typed should simply proceed."""
    try:
        return is_stale(root, registry=registry)
    except Exception:
        return True


def _migrate_and_commit(
    root: Path,
    registry: MigrationRegistry | None,
    commit: Callable[[Path, MigrationReport], Any] | None,
    emit: Callable[[str], None],
) -> None:
    try:
        report = run_migrations(root, dry_run=False, registry=registry, veto=uncommitted_veto(root))
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
        # PARTIAL SUCCESS is its own outcome and the message says so (review
        # r5-c5). One plan migrated and committed while another failed on a
        # `~=` ceiling is the ordinary shape of a consumer repo mid-upgrade;
        # "N artifact(s) could not be migrated" alone reads as though nothing
        # happened, and an operator who then re-runs is surprised by a commit
        # that is already there.
        raise _refuse(
            emit,
            [
                f"fr: {len(report.applied)} artifact(s) migrated"
                + (" and committed" if report.applied else "")
                + f"; {len(report.failed)} left unmodified.",
                "  Refusing to run over a half-migrated tree. Fix them by hand, or set "
                f"{SKIP_ENV_VAR}=1 to bypass this check.",
            ],
        )


def _fell_back_to_cwd(root: Path, state: GitContext) -> bool:
    """Did `resolve_repo_root` hand us a cwd instead of the repository root?

    `resolve_repo_root` swallows a failing `git rev-parse --show-toplevel` and
    returns the cwd (`fr.commands.common`). Combined with the old fail-OPEN
    git layer that produced the one outcome this module promises never to
    reach: from a subdirectory of a repo git could not answer for, the gate
    proceeded over a stale tree it had never established the state of (review
    r5-c2). Now git answers separately, so the two can be compared — and a
    disagreement is a refusal, not a shrug.

    Not a refusal when `$VK_REPO_ROOT` deliberately points somewhere else and
    that somewhere else IS a repo root; that is the documented test/override
    seam, and it agrees with git by definition when it is a real root.
    """
    return root.resolve() != state.toplevel


def _will_not_act_here(root: Path, because: str, detail: str) -> tuple[str, ...]:
    """The refusal shape shared by every "stale, but fr will not touch it here".

    One sentence of fact, one clause naming the context, one explaining why it
    is the wrong place to write, then the three commands. Kept in one function
    so a new refusal cannot quietly ship a different vocabulary.
    """
    return (
        f"fr: artifacts in {root} were written for a different fr and must be "
        "migrated before this command can run.",
        f"  {because}",
        f"  {detail}",
        "  preview:  fr migrate artifacts",
        "  apply:    fr migrate artifacts --yes",
        f"  bypass (recovery only):  {SKIP_ENV_VAR}=1 fr <command>",
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
