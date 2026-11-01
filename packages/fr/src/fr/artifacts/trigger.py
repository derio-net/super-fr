"""The obligatory trigger at CLI entry, context-aware (spec §3.C; contexts
re-decided by spec 2026-11-01-auto-migrate-own-commit §A, super-fr#1242).

`fr.cli`'s root callback calls `ensure_artifacts_current` before every command:

    fr <any command>
      └─ artifacts stale?
           ├─ ci           (a truthy CI marker)       → migrate in place, NEVER commit, continue
           ├─ opt-out      (FR_NON_INTERACTIVE)       → refuse, write nothing
           ├─ interactive  (a TTY on stdin + stdout)  → migrate, commit alone, continue
           ├─ workspace    (a valid fr-isolation one) → migrate, commit alone, continue
           └─ refuse       (a daemon, a base clone)   → refuse, write nothing

**The two committing contexts** (interactive, workspace) keep every git-state
guard: never on **the repository's default branch** (a commit made
automatically on `main`, before a command typed for another reason, is work
someone has to notice and undo), never on a detached HEAD, never from a
subdirectory, never while another fr holds the lock, and never over an
artifact with **uncommitted changes** (`git add -- <path>` stages the whole
file, so migrating it would commit a half-typed edit under a `chore(fr):
migrate ...` message). The migration is always its own commit. A workspace is
committed to because its branch survives and reaches a PR.

**CI** migrates the working tree so the command can run, and never commits: a
CI checkout is discarded. It warns on stderr that the files must not be
committed with other work.

**Refuse** is the bridge's row. The bridge works from a checkout it `reset
--hard`s to `origin/main` every tick (#286), so a commit there is discarded on
the next pass: auto-committing would be pointless *and* actively misleading.
Its refusal names the way to get the migration carried: `fr isolation up`.

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
from typing import Any, Final, Literal

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
    NoRepo,
    commit_migration,
    git_context,
    lock_path,
    uncommitted_veto,
)
from fr.artifacts.runner import (
    FailedAction,
    MigrationRegistry,
    MigrationReport,
    inspection_failures,
)
from fr.isolation.marker import valid_workspace

# --- what is exempt ------------------------------------------------------

EXEMPT_OPTIONS: Final[frozenset[str]] = frozenset({"--help", "--version"})
"""Asking what `fr` is must never rewrite the repo."""

READ_ONLY_COMMANDS: Final[tuple[str, ...]] = (
    "status",
    "skills",
    "isolation",
    "init",
    "validate",
    "harness",
    "triage",
    "usage",
    "services",
    "cloud",
    "debt",
    "gate",
    "release",
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
migrated at all. `fr harness` (2026-09-18 harness-parity-matrix, spec §3.F) is
the same shape as `validate`, and the precise claim matters since this list is
pinned so that additions are argued from here: the RENDER path reads nothing
but the `parity.yaml` shipped inside the wheel, and `--check` reads the
registration files but writes none — neither path mutates anything, so the
exemption cannot let an agent proceed *over* a stale artifact, which is the one
thing this gate exists to prevent. Render is explicitly designed to run on a pod
with no super-fr checkout at all, which is the case where blocking it behind
*this repo's own* stale plan/journal/run artifacts would be most visibly wrong:
the command's whole purpose is to work where there is no checkout to be
stale. `fr triage` (2026-09-21 fr-triage, spec §3.F′) meets the promise
strictly: it never reads or writes a registered artifact, and every file it
writes is under its own state directory (`<workspace>/.fr/triage-state/<scope>/`,
kept out of git by an `info/exclude` line, or `--dir`; 2026-10-07 cloud-triage R4),
plus its own state ref, the orphan branch `refs/heads/fr-triage/<scope-id>` (R5), which
shares no history with the code and holds no registered artifact. Its batch verbs
(2026-09-25 triage-batches, spec §5) also write the forge — labels, marker comments,
merges — behind `--yes`, and `batch merge`
commits and pushes from scratch worktrees under that same state directory. A
`git merge` there moves whatever artifacts the default branch carries, which
is ordinary git, not an fr rewrite of an artifact in the invoking checkout, so
the promise still holds. Gating it protects nothing, since triage cannot
proceed *over* a stale artifact; it would only refuse an agent's triage,
commonly an org triage run from inside some unrelated repo, over artifacts the
command never touches. `fr usage` (2026-09-25 lean-cost-aware-process, spec §5.A.5) is the
same shape as `triage`: it READS a run cursor (for its sessions and step
windows) and the harness's own transcripts, and writes only under its cache
directory (`$HOME/.cache/fr/usage/`, or `FR_USAGE_CACHE`) — never a registered
artifact, so it cannot proceed over a stale one. It must also run where the
cursor is stale: reporting what an old run cost is exactly the audit's job.
`fr services` (2026-09-28 fr-profiles-services, spec §3.F) only READS
`.devcontainer/fr-profiles.yaml` and the repo's CI files and writes nothing; it
must keep working on an unmigrated repo, whose version-1 file it reports as
`source: legacy`. `fr init` stays exempt: `fr init scaffold` touches
only the fr-profiles artifact, always at that kind's current version, and runs
the 1 -> 2 migration in process over an existing version-1 file first (refusing,
untouched, one it cannot migrate) — it never leaves, or proceeds over, a stale
one (spec 2026-09-28 fr-profiles-services §3.E.1). `fr init migrate` renames
vk-profiles.yaml to fr-profiles.yaml and so can leave a version-1 file, which the
next gated command migrates. `fr init agents` (2026-10-07 cloud-triage R19) writes the
`agents` artifact only at its current version, so it too never leaves a stale one.
`fr cloud` (same spec, R23) writes nothing: `doctor` reads the host's files and the
repo's `agents` artifact, `setup-script` prints a template; and it is what an operator
runs when the environment is not yet fit for fr, stale artifacts included.
`fr debt` (2026-10-11 debt-engine, R25) writes nothing; `issue` writes only to the forge and
`archive-pr` only through a nested `fr archive`, which this gate checks on its own.
`fr gate` (2026-10-14 exit-gates §D) writes only to the forge, with `--yes`: `pass` swaps a
PR's `gate:<g>` label for `gate:<g>-passed` and comments, because the merged PR's labels are
the gate ledger; it touches no registered artifact.
`fr release` (same spec, R21) reads tags and the forge and writes nothing: `status` lists the
merged PRs a post-merge gate still holds, and `release.py` runs it on the default branch."""

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


MigrationContext = Literal["ci", "opt-out", "interactive", "workspace", "refuse"]
"""The five contexts of spec 2026-11-01-auto-migrate-own-commit §A, in precedence.

- **ci** — a truthy `CI_ENV_VARS` marker: migrate the working tree in place,
  never commit.
- **opt-out** — `FR_NON_INTERACTIVE` truthy: refuse, write nothing.
- **interactive** — a TTY on stdin and stdout: migrate and commit alone.
- **workspace** — a valid fr-isolation workspace: migrate and commit alone.
- **refuse** — anything else (a bridge/daemon checkout, an agent in a base
  clone): refuse, write nothing.
"""


def classify(
    env: Mapping[str, str] | None = None, stdin: Any = None, stdout: Any = None
) -> MigrationContext | None:
    """The context, from the environment and the streams alone.

    `None` means "workspace or refuse": that needs git, and is decided by the
    gate after `git_context`. CI comes first because a CI runner may allocate a
    pty and a CI checkout must never be committed to; `FR_NON_INTERACTIVE` comes
    before interactive because it is a TTY-bearing wrapper's explicit opt-out.
    `is_interactive` stays the one answer to "is this an operator's terminal?".
    """
    environ = os.environ if env is None else env
    if any(_truthy(environ, name) for name in CI_ENV_VARS):
        return "ci"
    if _truthy(environ, NON_INTERACTIVE_ENV_VAR):
        return "opt-out"
    if is_interactive(env=environ, stdin=stdin, stdout=stdout):
        return "interactive"
    return None


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
    context: MigrationContext | None = None,
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

    `registry`, `context`, `commit` and `err` are injection points for
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

    # Step 2 (spec 2026-11-01 §B): classify from the environment and the
    # streams alone. `None` is the workspace candidate, decided with git below.
    where = context if context is not None else classify(environ)
    if where == "opt-out":
        raise _refuse(
            emit,
            _will_not_act_here(
                root,
                registry,
                f'{NON_INTERACTIVE_ENV_VAR} is set — an explicit "do not write to git" — so '
                "fr will not migrate or commit here:",
                "the opt-out wins over a TTY and over an fr-isolation workspace alike.",
                carry=True,
            ),
        )
    if where == "ci":
        # §C: nothing is committed, so no git-state refusal applies. The lock
        # and the uncommitted-file veto still do.
        _migrate_in_place(root, registry, emit, environ)
        return
    if where == "refuse":
        raise _refuse(emit, _not_a_workspace(root, registry, "no TTY"))

    # Step 3. ONE place asks git anything (review r5-c1/c2/c3). Every branch
    # below reads the same snapshot, so the default-branch guard, the
    # detached-HEAD refusal, the workspace check and the uncommitted-file veto
    # cannot disagree about the tree — and a git that could not answer refuses
    # ONCE, loudly, instead of each predicate independently degrading to a
    # permissive default.
    state = git_context(root)
    if isinstance(state, GitRefusal):
        raise _refuse(
            emit,
            _will_not_act_here(
                root,
                registry,
                "fr could not establish this repository's git state, so it will not "
                "migrate or commit here:",
                f"{state.reason} Unknown git state is not a clean one.",
            ),
        )
    if isinstance(state, NoRepo) and where != "interactive":
        raise _refuse(emit, _not_a_workspace(root, registry, "not a git repository"))
    if isinstance(state, GitContext):
        # Step 4: the committing contexts' own git-state refusals, in today's
        # order — so a workspace mid-rebase hears "finish or abort it", never
        # "enter isolation".
        if _fell_back_to_cwd(root, state):
            raise _refuse(
                emit,
                _will_not_act_here(
                    root,
                    registry,
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
                    registry,
                    "HEAD is detached (a rebase, a bisect, or a checked-out commit), so fr "
                    "will not migrate or commit here:",
                    "a commit made now is folded into the operation in progress or "
                    "orphaned by the next checkout. Finish or abort it first.",
                ),
            )
        # Step 5: the workspace candidate must BE one (R2).
        if where != "interactive":
            verdict = valid_workspace(state.toplevel, state.branch)
            if not verdict.ok:
                raise _refuse(
                    emit, _not_a_workspace(root, registry, verdict.reason or "invalid marker")
                )
        # Step 6: never an automatic commit on the default branch (R6).
        if state.branch == state.default_branch:
            raise _refuse(
                emit,
                _will_not_act_here(
                    root,
                    registry,
                    f"HEAD is {state.branch!r}, this repository's default branch, so fr will "
                    "not migrate or commit here:",
                    "an automatic commit on a protected branch is work you have to notice "
                    "and undo. Do it on a branch, or run the migration yourself.",
                ),
            )

    # Step 7: lock, migrate, commit alone.
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
                    registry,
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


def _ci_veto(root: Path) -> Callable[[Path], str | None]:
    """`uncommitted_veto`, except that a veto which cannot read git state holds
    nothing back: a CI checkout with no repo has no edits to protect (§C)."""
    try:
        return uncommitted_veto(root)
    except Exception:
        return lambda path: None


def _migrate_in_place(
    root: Path,
    registry: MigrationRegistry | None,
    emit: Callable[[str], None],
    environ: Mapping[str, str],
) -> None:
    """The ci row (spec 2026-11-01 §C, R5): migrate the working tree, never commit.

    A CI checkout is discarded, so a commit there is pointless; migrating lets
    the command run over a tree it can read. Everything is said on STDERR — the
    `::warning::` annotation included — so a `--json` command's stdout, or a
    `>> $GITHUB_STEP_SUMMARY` redirect, is never contaminated. No adoption
    offer: it offers to write run files, which makes no sense here.
    """
    with migration_lock(lock_path(root)) as acquired:
        if not acquired:
            if not _still_stale(root, registry):
                emit("  another fr process migrated this tree; continuing.")
                return
            raise _refuse(
                emit,
                _will_not_act_here(
                    root,
                    registry,
                    "another fr process is migrating this repository right now, so fr "
                    "will not migrate here:",
                    "two migrations of one tree race each other. Re-run this command "
                    "once it finishes.",
                ),
            )
        try:
            report = run_migrations(root, dry_run=False, registry=registry, veto=_ci_veto(root))
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
    if report.failed:
        for failure in report.failed:
            emit(f"  FAILED: {_rel(failure.path, root)} · {failure.error}")
            for companion in failure.also_wrote:
                emit(f"    it had already written {_rel(companion, root)} (uncommitted)")
        raise _refuse(
            emit,
            [
                f"fr: {len(report.applied)} artifact(s) migrated in place (not committed); "
                f"{len(report.failed)} left unmodified.",
                "  Refusing to run over a half-migrated tree. Fix them by hand, or set "
                f"{SKIP_ENV_VAR}=1 to bypass this check.",
            ],
        )

    n = len(report.changed_paths)
    emit(
        f"fr: {n} artifact(s) in {root} were written for an older fr; migrated in place "
        "for this run (NOT committed)."
    )
    emit(
        "  Do not commit these files with other work. Carry the migration on a branch: "
        "the next fr command in an fr-isolation workspace commits it alone."
    )
    if _truthy(environ, "GITHUB_ACTIONS"):
        emit(
            f"::warning title=fr artifacts stale::{n} artifact(s) migrated in place for "
            "this run; carry the migration on a branch."
        )


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
            notice = _commit_notice(outcome)
            if notice:
                emit(notice)

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
            for companion in failure.also_wrote:
                emit(f"    it had already written {_rel(companion, root)} (uncommitted)")
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


COMMIT_NOTICE_PREFIX: Final = "fr: migrated and committed"
"""The one line the session hooks relay (spec §D, R11) — keep it a prefix match."""

CARRY_LINE: Final = (
    "  carry it:  fr isolation up --branch <branch>   "
    "(the next fr command there migrates and commits it alone)"
)


def _commit_notice(outcome: Any) -> str | None:
    """`fr: migrated and committed <n> artifact(s): <subject> (<sha>)`, or None."""
    if not getattr(outcome, "committed", False):
        return None
    message = getattr(outcome, "message", None) or ""
    subject = message.splitlines()[0] if message else "chore(fr): migrate"
    n = len(getattr(outcome, "paths", ()) or ())
    sha = getattr(outcome, "sha", None)
    return f"{COMMIT_NOTICE_PREFIX} {n} artifact(s): {subject}" + (f" ({sha})" if sha else "")


def _not_a_workspace(
    root: Path, registry: MigrationRegistry | None, reason: str
) -> tuple[str, ...]:
    """The refuse row (R3): non-interactive, not CI, not a valid workspace."""
    return _will_not_act_here(
        root,
        registry,
        f"this context is non-interactive and not an fr-isolation workspace ({reason}), "
        "so fr will not migrate or commit here:",
        "a daemon checkout is hard-reset every tick, so a commit made in it "
        "would be silently discarded.",
        carry=True,
    )


def _will_not_act_here(
    root: Path,
    registry: MigrationRegistry | None,
    because: str,
    detail: str,
    *,
    carry: bool = False,
) -> tuple[str, ...]:
    """The refusal shape shared by every "stale, but fr will not touch it here".

    One sentence of fact, one clause naming the context, one explaining why it
    is the wrong place to write, then the three commands. Kept in one function
    so a new refusal cannot quietly ship a different vocabulary.

    Unless the tree is not stale but UNREADABLE: then "written for a different
    fr and must be migrated" is false, and the migration it recommends cannot
    help — the refusal names each file and its error instead (#812).
    """
    failures = inspection_failures(root, registry=registry)
    if failures:
        return _cannot_read(root, failures)
    return (
        f"fr: artifacts in {root} were written for a different fr and must be "
        "migrated before this command can run.",
        f"  {because}",
        f"  {detail}",
        *((CARRY_LINE,) if carry else ()),
        "  preview:  fr migrate artifacts",
        "  apply:    fr migrate artifacts --yes",
        f"  bypass (recovery only):  {SKIP_ENV_VAR}=1 fr <command>",
    )


RECORDS_DIR_SUFFIX: Final = ".records"
"""The record kind's directory suffix, as its locator in `registry` spells it
(`fr.record` sits above this layer, so its constant is not imported here)."""


def _cannot_read(root: Path, failures: Sequence[FailedAction]) -> tuple[str, ...]:
    lines = [
        f"fr: {len(failures)} artifact(s) in {root} cannot be read, so fr cannot tell "
        "whether they are current — no migration can fix this:",
        *(f"  {_rel(f.path, root)}: {f.error}" for f in failures),
    ]
    if any(f.path.parent.name.endswith(RECORDS_DIR_SUFFIX) for f in failures):
        lines.append(
            f"  Every file under docs/superpowers/runs/<run>{RECORDS_DIR_SUFFIX}/ is read "
            "as one step's record. Scratch inputs (for `fr plan create`, say) belong "
            "outside the repository — in $TMPDIR."
        )
    lines += [
        "  Fix or move each file, then re-run the command.",
        f"  bypass (recovery only):  {SKIP_ENV_VAR}=1 fr <command>",
    ]
    return tuple(lines)


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
