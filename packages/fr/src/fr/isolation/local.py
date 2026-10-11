"""LocalWorktreeDevcontainerTarget — worktree + devcontainer over a Runner seam.

Every external call (git, devcontainer, docker, gh) goes through `runner` so
the lifecycle is unit-testable without Docker. The devcontainer CLI labels
containers with `devcontainer.local_folder=<workspace>`, which is how status
and down re-find the container.
"""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any, ClassVar, cast

from fr._hosts import detect_backend
from fr.ghclient import CommandRunner
from fr.hostclient import FORGE_ERRORS, client_for
from fr.isolation import preserve as _preserve
from fr.isolation.preserve import TeardownReport
from fr.isolation.types import (
    IsolationError,
    IsolationState,
    _git_common_dir,
    carried_state,
    delete_state,
    harden_secret_file,
    list_states,
    load_state,
    recorded_mode,
    repo_cache_name,
    resolve_profile,
    save_state,
)
from fr.plan_validator_wrapper import REPAIR_COMMAND

Runner = Callable[..., "subprocess.CompletedProcess[str]"]

_BASE32 = "0123456789abcdefghijklmnopqrstuv"


def devcontainer_id(local_folder: str, config_file: str) -> str:
    """The devcontainer CLI's `${devcontainerId}` for a container's id labels:
    sha256 of the sorted label JSON, as a base-32 number padded to 52 chars.

    Features key per-workspace named volumes on it (docker-in-docker:
    `dind-var-lib-docker-<id>`), so it is how teardown tells a volume this
    workspace owns from one it merely shares."""
    labels = {
        "devcontainer.config_file": config_file,
        "devcontainer.local_folder": local_folder,
    }
    raw = json.dumps(labels, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    n = int.from_bytes(hashlib.sha256(raw.encode("utf-8")).digest(), "big")
    digits = ""
    while n:
        n, r = divmod(n, 32)
        digits = _BASE32[r] + digits
    return digits.rjust(52, "0")


def _missing_binary(err: FileNotFoundError, context: str) -> str:
    """One line naming the binary the runner could not find — from the error
    itself, never an assumed name."""
    missing = err.filename or (err.args[0] if err.args else "a required binary")
    return f"{missing} not found on PATH — {context}."


def subprocess_runner(
    argv: list[str],
    cwd: Path | None = None,
    check: bool = False,
    capture: bool = True,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """capture=False inherits stdio — exec passthrough must stream the
    container's output live (long builds/test runs), not swallow it.

    `timeout` makes the call bounded AND non-interactive: stdin is /dev/null,
    and an expiry returns exit 124 with a `timed out` stderr instead of
    raising, so a caller reads it as a failure (for a probe: `unknown`)."""
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            check=check,
            capture_output=capture,
            text=True,
            env=env,
            timeout=timeout,
            stdin=subprocess.DEVNULL if timeout is not None else None,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            argv, 124, stdout="", stderr=f"{argv[0]}: timed out after {timeout:g}s\n"
        )


def _home() -> Path:
    return Path(os.environ.get("HOME", str(Path.home())))


# --- opportunistic gc spawn seam (#354 Task B) ---
#
# `up`/`down` fire a detached `fr isolation gc` after their own work — the
# primary auto-trigger that bounds the steady-state leak to <=1 workspace with
# no daemon. Routed through an INJECTABLE seam (not the Runner: a fire-and-forget
# Popen is a different shape than subprocess.run) so the non-blocking /
# non-raising contract is testable. The library default is a NO-OP — production
# opts into the real spawn at the CLI boundary, so a Target built directly (every
# unit test, and gc's own sibling teardown Targets) never spawns.
#
# The second argument is the spawning target's MODE (gh#569, review p2-f2): a
# required part of the contract, so no wrapper or test double can silently drop
# it and hand the child sweep the caller's env instead.
GcSpawner = Callable[[Path, str], None]


def _detached_gc_spawn(repo_root: Path, mode: str) -> None:
    """Fire-and-forget `fr isolation gc`: detached (own session), non-blocking,
    output to a rotating-ish log. Any spawn error is swallowed — a caller must
    never fail because a background reap could not start.

    `mode` is always pinned as the child's `FR_ISOLATION_TARGET` (gh#569):
    the sweep's discovery and docker steps run in the SPAWNING target's mode,
    not whatever the caller's env says. A `down` of a host-worktree workspace
    run without the env would otherwise start a devcontainer sweep, which dies
    on `docker ps` (FileNotFoundError) on a docker-less pod.

    Named with `--repo` and run there rather than inheriting the caller's cwd
    (#423): a `down` fired from inside the worktree it just removed would
    otherwise hand the child a deleted cwd — `Path.cwd()` then raises and the
    sweep dies before classifying anything. It also keeps the child's
    state-record discovery source pointed at the repo the caller was working in.
    """
    try:
        log_path = _home() / ".cache" / "fr" / "isolation-gc.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = open(log_path, "a")  # noqa: SIM115 — handed to the child; not ours to close
        subprocess.Popen(
            [sys.executable, "-m", "fr", "isolation", "gc", "--repo", str(repo_root)],
            cwd=str(repo_root) if repo_root.is_dir() else None,
            env={**os.environ, "FR_ISOLATION_TARGET": mode},
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
        )
    except Exception:
        pass


def _noop_gc_spawn(repo_root: Path, mode: str) -> None:
    """The safe default — no background sweep (see GcSpawner)."""


@dataclass
class MergeVerification:
    """Whether a branch's changes are present on a base ref (#320 close-out)."""

    changed: list[str]  # files the branch changed since its merge-base
    missing: list[str]  # changed files NOT yet present on the base ref
    changes_present: bool


@dataclass
class GcWorkspace:
    """A workspace discovered by the host-wide gc sweep (#354 Task B).

    `state` is None for a true orphan (worktree gone, container found only by
    docker label) or an ambiguous label-less directory with no fr state.
    """

    worktree: Path
    container_id: str | None
    state: IsolationState | None


def _forge_refused(exc: Exception) -> IsolationError:
    """The forge adapter's host refusal (spec 2026-10-06-forge-remainder §4.E:
    a declared GitHub host gh is not logged into) as this lifecycle's own
    error. Callers that guard work (`down`, `verify-merge`, the reap hazard)
    refuse on it like any other `IsolationError`; the read-only, many-workspace
    ones (`status`, the gc sweep) degrade per workspace instead (review p2-r1)."""
    return IsolationError(f"cannot ask the forge: {exc}")


@dataclass
class GcAction:
    """One workspace's gc verdict + what gc did about it (#354 Task B)."""

    worktree: str
    branch: str | None
    # merged | merged-by-content | open | no-pr | orphan | no-state | dangling-image
    # | empty-repo-dir | stale-session (cache/index hygiene, spec 2026-09-04 §5)
    # | unverifiable (a refused forge lookup, spec 2026-10-06-forge-remainder)
    verdict: str
    # reaped | skipped | warned | reap-failed | would-reap | would-skip | removed
    # | would-remove
    action: str
    detail: str = ""


@dataclass(frozen=True)
class ReapHazard:
    """Work that a reap would destroy, and how to keep it (spec 2026-09-20
    isolation-reap-data-loss-guards §3.1)."""

    kind: str  # "drifted-checkout" | "dirty-worktree" | "unlanded-content" | "unverifiable"
    detail: str  # names the branch and what would be lost — see _hazard_detail


class ReapRefused(IsolationError):  # noqa: N818 — a refusal is a decision, not
    # an "Error" (spec §3.5: gc classifies it as a skip, never a failure); the
    # name is the spec's own vocabulary (§3.1), kept verbatim.
    """Raised INSTEAD of tearing down, by `_down_worktree_tail`'s hazard check.
    Carries the hazard so gc can classify a refusal as a deliberate skip rather
    than a failure (spec §3.5, phase 3)."""

    def __init__(self, hazard: ReapHazard) -> None:
        self.hazard = hazard
        super().__init__(hazard.detail)


def _merged_before(pr: dict[str, Any], created_at: str) -> bool:
    """True when `pr` provably merged before the workspace was created (gh#844).

    `_pr_from` finds a PR by branch NAME, which a later workspace can re-use.
    Only a merge time we can read AND compare proves the PR is an earlier one:
    a missing or unparseable time keeps the old by-name verdict rather than
    inventing a new one."""
    try:
        merged = datetime.fromisoformat(str(pr.get("mergedAt") or "").replace("Z", "+00:00"))
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if merged.tzinfo is None or created.tzinfo is None:
        return False
    return merged < created


def _hazard_detail(branch: str, headline: str, paths: list[str], remedy: str) -> str:
    """One shared voice for every reap-hazard message (spec §3.8) — phases 2
    and 3 add two more callers (unlanded-content, unverifiable-fetch), and all
    three must read as the same product, not three ad hoc f-strings.

    `remedy` is per-hazard and NOT optional: the three hazards do not have the
    same way out, and a single hardcoded clause was wrong for two of them
    (phase-1 review f1). "Commit or stash them" has no referent when the
    hazard is that `git status` itself failed, and the way out of unlanded
    content is to push, not to stash.

    The `--force` sentence deliberately says what --force *does* rather than
    "destroys the work", because that is not uniformly true (phase-1 review
    f2, verified against real git): `git worktree remove --force` removes the
    working tree and fr's state record, and does NOT delete the branch or its
    commits. So a forced reap of a DIRTY tree is unrecoverable (uncommitted
    edits were never objects), while a forced reap of an unlanded COMMIT
    leaves the branch ref intact and recoverable. Overstating it is not a
    harmless exaggeration — an operator who believes --force deletes their
    commits will not use it, which is a false refusal by other means.

    Caps the listed paths so a hazard on a 200-file branch doesn't produce a
    wall of text: the first few, then `+N more`.
    """
    lines = [f"isolation: {branch} {headline} — refusing to reap (nothing was deleted)."]
    if paths:
        shown = paths[:5]
        rest = len(paths) - len(shown)
        listed = ", ".join(shown) + (f", +{rest} more" if rest > 0 else "")
        lines.append(f"  {listed}")
    lines.append(remedy)
    lines.append(
        f"Or reap it anyway with `fr isolation down --branch {branch} --force`, "
        "which removes the worktree and fr's record of it (the branch and any "
        "commits on it remain in the repo; uncommitted changes do not survive, except "
        "fr's own records under `docs/superpowers/`, which are preserved and restored "
        "by the next `up`)."
    )
    return "\n".join(lines)


# `fr archive` (fr/archive.py) `git mv`s a finished run's fr artifacts from
# docs/superpowers/<kind>/<rest> to docs/superpowers/implemented/<kind>/<rest>
# (plans/<dir>, specs/<file>, journals/<scope-dir>/<file>, runs/<id>.yaml,
# usage/<id>.yaml — every destination is the source path with `implemented/`
# spliced in after `docs/superpowers/`). Kept as a local constant, not imported
# from fr.archive: this module must not depend on the archive command.
_ARCHIVED_KINDS = ("plans", "specs", "journals", "runs", "usage")
_SUPERPOWERS = "docs/superpowers/"

# Files only fr's own tooling writes into a workspace, appended to the shared
# `info/exclude` on `up` so they never make a worktree dirty — which would make
# `down`'s reap-hazard check refuse at close-out. `devcontainer-lock.json` is
# what the devcontainer CLI writes beside each profile's config (gh#824);
# anchored, so a lock file the repo keeps elsewhere stays the repo's business.
_FR_OWNED_EXCLUDES = (".fr-isolation", "/.devcontainer/*/devcontainer-lock.json")


def _archived_path(path: str) -> str | None:
    """Where `fr archive` moves `path` to, or None when it never moves it.

    Only the five archived kinds under docs/superpowers/ map; anything else
    (including a path already under `implemented/`) has no alternate.
    """
    for kind in _ARCHIVED_KINDS:
        if path.startswith(f"{_SUPERPOWERS}{kind}/"):
            return f"{_SUPERPOWERS}implemented/{path[len(_SUPERPOWERS) :]}"
    return None


def _branch_added_lines(
    run: Runner, repo_root: Path, merge_base: str, branch: str, path: str
) -> list[str]:
    """The non-blank lines the branch ADDED to `path` since `merge_base`."""
    return _branch_patch_lines(run, repo_root, merge_base, branch, path)[0]


def _branch_patch_lines(
    run: Runner, repo_root: Path, merge_base: str, branch: str, path: str
) -> tuple[list[str], list[str]]:
    """The non-blank lines the branch (added, removed) in `path` since `merge_base`.

    Parsed from the branch's own diff (`+`/`-` lines, minus the `+++`/`---`
    headers). Blank / whitespace-only lines are dropped — they carry no
    identity and would trivially "match" almost any base content, weakening
    containment.
    """
    diff = run(["git", "diff", merge_base, branch, "--", path], cwd=repo_root)
    added: list[str] = []
    removed: list[str] = []
    for ln in diff.stdout.splitlines():
        if ln.startswith(("+++", "---")):
            continue
        if ln[:1] in ("+", "-") and ln[1:].strip():
            (added if ln[0] == "+" else removed).append(ln[1:])
    return added, removed


@dataclass
class _LogCommit:
    """One commit of `_branch_blob_was_on_base`'s log: its raw diff lines for
    the path, and the non-blank lines its patch added and removed there."""

    raw: list[list[str]] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)


_COMMIT_MARK = "\x01"


def _parse_log(stdout: str) -> list[_LogCommit]:
    """Split `git log --format=%x01 --raw -p -U0` output into commits.

    A hunk line is `+`/`-` only between an `@@` header and the next
    `diff --git`, so a removed line whose text starts `-- ` (shown as `--- …`)
    is still content, not a file header.
    """
    commits: list[_LogCommit] = []
    in_hunk = False
    for line in stdout.splitlines():
        if line == _COMMIT_MARK:
            commits.append(_LogCommit())
            in_hunk = False
        elif not commits:
            continue
        elif line.startswith("diff --git "):
            in_hunk = False
        elif line.startswith("@@"):
            in_hunk = True
        elif in_hunk and line[:1] in ("+", "-"):
            if line[1:].strip():
                (commits[-1].added if line[0] == "+" else commits[-1].removed).append(line[1:])
        elif not in_hunk and line.startswith(":"):
            meta, _, _rest = line[1:].partition("\t")
            commits[-1].raw.append(meta.split())
    return commits


def _is_inverse_patch(
    commit: _LogCommit, branch_added: list[str], branch_removed: list[str]
) -> bool:
    """Does `commit`'s patch undo the branch's: it removes every non-blank line
    the branch added, and adds nothing but lines the branch removed? That is a
    revert however the surrounding lines moved in between (#739). A rewrite of
    the branch's lines adds new ones, so it is not one.

    A branch that only REMOVED lines has nothing to take away, so there the
    revert is the commit that puts every one of them back (#753 review f1);
    without that, any later removal-only commit would vacuously qualify. A
    branch with no non-blank line either way (blank-only, binary) has no patch
    to invert."""
    if not branch_added and not branch_removed:
        return False
    restores = not branch_added and not (Counter(branch_removed) - Counter(commit.added))
    return (
        (bool(branch_added) or restores)
        and not (Counter(branch_added) - Counter(commit.removed))
        and not (Counter(commit.added) - Counter(branch_removed))
    )


def _carries_patch(commit: _LogCommit, branch_added: list[str]) -> bool:
    """Does `commit`'s patch add every non-blank line the branch added? That
    is the branch landing even when the commit's blob is not the branch's: a
    squash over a CONCURRENT base edit to the same file writes a blob that
    combines both, but its own patch against its first parent is still the
    branch's (#715). A branch that added no non-blank line has no patch to
    recognise, so only its blob can land it."""
    return bool(branch_added) and not (Counter(branch_added) - Counter(commit.added))


def _branch_blob_was_on_base(
    run: Runner,
    repo_root: Path,
    merge_base: str,
    branch: str,
    base_ref: str,
    path: str,
    base_path: str | None = None,
) -> bool:
    """Did the branch's exact content of `path` ever appear on the base?

    True when `<branch>:<path>` resolves to the same blob as `<c>:<path>` for
    some commit `c` in `merge_base..base_ref` that touched `path`. A later merge
    that rewrote the branch's lines leaves the branch's blob in the base's own
    history; an orphan (content that never landed) matches nothing. Every
    failure — the branch lacks the file (a deletion has no blob), an
    unresolvable rev, a failed git call — reads as no match, never as a pass.

    `base_path` is where to look on the base side (default: `path` itself) — the
    `implemented/` path `fr archive` moved it to.

    ONE git call answers the whole range question (C1 perf review, #665/#598):
    `git log --raw` over `merge_base..base_ref` for `bpath` lists every
    touching commit's raw diff line in a single process, and the blob is read
    straight out of the "new blob" column — no per-commit `git rev-parse`. A
    generated report/matrix file is touched by nearly every later PR, so the
    old one-`rev-parse`-per-commit scan multiplied badly across every
    workspace in a gc sweep.

    A merge later REVERTED does not count (#716). The landing commit stays in
    history, so "the blob was written" alone would still pass; the same log,
    read oldest-first, also shows the revert — after the landing, the path is
    written back to a blob it held BEFORE the landing (at the merge-base, an
    intermediate PR's state, or a rebase merge's earlier commit). That holds
    even when later commits edit the path again, which the base's current blob
    alone would miss. Writing the branch's blob again (the revert reverted)
    re-lands it. Absence is not a "held" state: a file the branch added that
    later disappears is the consumed `.changes` fragment, and a later deletion
    counts as landed — so a revert of a branch that ONLY added files stays
    indistinguishable by content, as it always was.

    A revert applied after ANOTHER change to the path (a three-way revert)
    writes a blob the path never held, so the held-state test alone misses it
    (#739). The same call therefore also reads each commit's patch (`-p -U0`):
    a later commit that removes every non-blank line the branch added, and adds
    nothing but lines the branch removed, is the branch's patch inverted — a
    revert, whatever else moved around it (`_is_inverse_patch`). A rewrite adds
    lines of its own, so it is not one (#665 stays landed); a deletion is never
    one (absence again — the consumed fragment); and a later PR that only
    removes exactly the branch's lines reads as a revert: a safe refusal. A
    three-way re-land (a revert of such a revert) is not recognised by its
    patch, so it stays missing — the safe direction.

    The landing itself is recognised by its patch as well as its blob (#715):
    when the base edited the same file concurrently, the squash's blob combines
    both edits and is never the branch's, so a later rewrite of the branch's
    lines would hide the landing from both checks. A first-parent commit whose
    patch adds every non-blank line the branch added is that landing
    (`_carries_patch`); a line pushed to the branch after the merge is in no
    such patch, so the #320 orphan stays missing. The revert checks above then
    run from it unchanged.
    Only the base's first-parent line is read, so content that reached the
    base solely through a side branch's own commits reads as missing (safe).
    """
    bpath = base_path or path
    want = run(["git", "rev-parse", "--verify", "--quiet", f"{branch}:{path}"], cwd=repo_root)
    if want.returncode != 0 or not want.stdout.strip():
        return False
    blob = want.stdout.strip()
    log = run(
        [
            "git",
            # A user's `log.follow` would chase the path across a rename (a
            # match under another name); colour would hide every `:` line.
            "-c",
            "log.follow=false",
            "log",
            "--no-color",
            "--no-abbrev",
            "--raw",
            # The patch rides the same call (#739): zero context, and never a
            # user's external diff driver or textconv filter, whose output
            # would not be the committed lines.
            "-p",
            "--unified=0",
            "--no-ext-diff",
            "--no-textconv",
            # `-m`: a merge commit prints no raw lines without it, so a blob that
            # exists on the base only as a merge result (a conflict resolution)
            # would read as never landed (Opus fix review f2).
            "-m",
            # The base's own line, oldest first: the revert check below needs
            # "before the landing" and "after it" to mean something. Without
            # `--first-parent`, a side branch merged LATER (a merge-commit PR
            # forked before the landing) lists its commits after the landing,
            # and one writing an old blob would un-land it (#716 review f1).
            # With it, `-m` diffs each merge against its first parent only.
            "--first-parent",
            "--topo-order",
            "--reverse",
            "--format=%x01",  # prints _COMMIT_MARK, one line per commit
            f"{merge_base}..{base_ref}",
            "--",
            bpath,
        ],
        cwd=repo_root,
    )
    if log.returncode != 0:
        return False
    held: set[str] = set()  # every blob the path held before (and at) the landing
    landed = False
    branch_patch: tuple[list[str], list[str]] | None = None  # read once, only if needed
    for commit in _parse_log(log.stdout):
        # `:oldmode newmode oldsha newsha status[score]` — the new blob is
        # field 3, present on every raw line (add/modify/delete/rename alike).
        for fields in commit.raw:
            if len(fields) < 4:
                continue
            old, new = fields[2], fields[3]
            if not landed and new != blob and new.strip("0"):
                if branch_patch is None:
                    branch_patch = _branch_patch_lines(run, repo_root, merge_base, branch, path)
                carries = _carries_patch(commit, branch_patch[0])
            else:
                carries = False
            if new == blob or carries:
                landed = True
                seen: tuple[str, ...] = (old,)
            elif landed:
                if new in held:
                    landed = False  # reverted: the path went back to a pre-landing state
                elif new.strip("0"):
                    if branch_patch is None:
                        branch_patch = _branch_patch_lines(run, repo_root, merge_base, branch, path)
                    if _is_inverse_patch(commit, *branch_patch):
                        landed = False  # reverted three-way: the branch's patch undone
                continue
            else:
                seen = (old, new)
            # Absence (the all-zero id of an add's old side or a delete's new side,
            # 40 or 64 digits) is not a held state — see the docstring.
            held.update(b for b in seen if b.strip("0"))
    return landed


def _landed_at(
    run: Runner,
    repo_root: Path,
    merge_base: str,
    branch: str,
    base_ref: str,
    path: str,
    base_path: str,
) -> bool:
    """The branch's contribution to `path` (per-line containment, then blob
    equality) against `base_ref:base_path`."""
    added = _branch_added_lines(run, repo_root, merge_base, branch, path)
    if added:
        show = run(["git", "show", f"{base_ref}:{base_path}"], cwd=repo_root)
        if show.returncode == 0:
            base_lines = set(show.stdout.splitlines())
            if all(line in base_lines for line in added):
                return True
    return _branch_blob_was_on_base(run, repo_root, merge_base, branch, base_ref, path, base_path)


def _branch_change_present_in_file(
    run: Runner, repo_root: Path, merge_base: str, branch: str, base_ref: str, path: str
) -> bool:
    """Is the branch's contribution to `path` reflected on `base_ref`?

    Per-line containment (#387): every non-blank line the branch added to `path`
    must appear verbatim in `base_ref:path`. This is robust to a CONCURRENT
    merge that later touches the same file elsewhere — such an edit shifts line
    numbers and diverges whole-file content, but leaves the branch's own added
    lines intact, so whole-file equality false-negatives while containment does
    not.

    When containment fails (including a file with no added line, or one absent
    from `base_ref`), fall back to blob equality (`_branch_blob_was_on_base`): a
    LATER merge that rewrote the branch's lines does not un-land them if the
    branch's exact file content was on the base after the merge.

    An fr artifact that `fr archive` later moved to `implemented/` is judged the
    same way at its archived path (`_archived_path`): the branch's added lines
    contained in `<base_ref>:<implemented path>`, or the branch's blob on that
    path in the base's history. Same soundness as the same-path check, and no
    looser than it: a missing archived file, or unrelated content, stays missing.
    Containment (not only exact blob equality) because the archive commit can carry
    the closeout's appended lines (usage capture, cursor advance) on top of the
    branch's content.

    Conservative in the missing direction: a file whose branch-side change added
    no identifiable line and whose blob never appeared on the base (a pure
    deletion that did NOT land byte-identically) reports *not present*, i.e. a
    safe "STOP and check", never a false "verified".
    """
    if _landed_at(run, repo_root, merge_base, branch, base_ref, path, path):
        return True
    archived = _archived_path(path)
    return archived is not None and _landed_at(
        run, repo_root, merge_base, branch, base_ref, path, archived
    )


def _diff_names(run: Runner, repo_root: Path, args: list[str]) -> list[str]:
    """`git diff --name-only -z <args>` as real paths, raising on failure.

    A failed diff has empty stdout, which `branch_changes_present` would read
    as "nothing changed" / "nothing differs" — i.e. ALL CHANGES PRESENT (#705).
    `-z` because the default output C-quotes non-ASCII and special paths, and a
    quoted name, fed back as a pathspec, matches nothing — so an unmerged file
    also read as present (#717)."""
    res = run(["git", "diff", "--name-only", "-z", *args], cwd=repo_root)
    if res.returncode != 0:
        raise IsolationError(
            f"git diff --name-only {' '.join(args[:2])} failed "
            f"(exit {res.returncode}): {(res.stderr or '').strip()}"
        )
    return [p for p in res.stdout.split("\0") if p]


def _fork_point(
    run: Runner,
    repo_root: Path,
    merge_base: str,
    branch: str,
    base_ref: str,
    start: str | None = None,
) -> str:
    """Where the branch's own changes start, for `merge_base..branch`.

    `git merge-base` answers that directly — except when the branch is an
    ANCESTOR of the base, which is what a --no-ff merge-commit landing leaves
    behind (#741): the merge-base is then the branch tip itself, the branch's
    diff is empty, and every change reads as present before a single path is
    judged, so a `git revert -m 1` of the landing still reads landed.

    For an ancestor branch the fork point is the merge-base of the branch with
    the landing merge's FIRST parent — the base as it was just before the
    landing. The landing merge is the oldest commit on the base's first-parent
    line that descends from the tip. A fast-forward (or a branch with no commits
    of its own) puts the tip itself on that line, so the landing's first parent
    IS the tip and the answer stays the tip: nothing changes for those.

    A branch landed MORE than once (merged, then extended and merged again)
    repeats the step from each fork it finds, against the base as it was before
    that landing, until a landing's first parent already holds the fork: the
    answer is where the branch left the base before its FIRST landing, so a file
    only the earlier, since-reverted landing touched is still judged (#753
    review f2). `upper` moves to a strict ancestor every step, so it ends.

    A fast-forward landing leaves no merge to mark where the branch began, so
    content alone cannot tell it from an empty branch, and a later revert of it
    would still read landed (#757). `start` is that missing evidence: the
    commit fr cut the branch from at `up` (`IsolationState.base_sha`). When the
    walk ends at the tip and `start` is a strict ancestor of it, `start` is the
    fork. A `start` that is not an ancestor (a branch name reused after a
    reset) is no evidence about this branch and is ignored.

    A failed git call raises rather than returning `merge_base`, which here
    would read as ALL CHANGES PRESENT (the #705 shape).
    """
    tip = run(["git", "rev-parse", "--verify", "--quiet", f"{branch}^{{commit}}"], cwd=repo_root)
    if tip.returncode != 0 or tip.stdout.strip() != merge_base:
        return merge_base
    fork = _landing_fork(run, repo_root, merge_base, branch, base_ref)
    if fork != merge_base or not start or start == merge_base:
        return fork
    ancestor = run(["git", "merge-base", "--is-ancestor", start, merge_base], cwd=repo_root)
    if ancestor.returncode == 0:
        return start
    if ancestor.returncode == 1:
        return fork
    raise IsolationError(
        f"git merge-base --is-ancestor {start[:12]} {merge_base[:12]} failed "
        f"(exit {ancestor.returncode}): {(ancestor.stderr or '').strip()}"
    )


def _landing_fork(run: Runner, repo_root: Path, merge_base: str, branch: str, base_ref: str) -> str:
    """`_fork_point`'s walk for an ancestor branch: back through each landing
    merge to where the branch left the base before its first landing."""
    fork, upper = merge_base, base_ref
    while True:
        line = run(
            [
                "git",
                "rev-list",
                "--first-parent",
                "--ancestry-path",
                "--reverse",
                f"{fork}..{upper}",
            ],
            cwd=repo_root,
        )
        if line.returncode != 0:
            raise IsolationError(
                f"git rev-list {fork[:12]}..{upper} failed (exit {line.returncode}): "
                f"{(line.stderr or '').strip()}"
            )
        landing = next(iter(line.stdout.split()), None)
        if landing is None:  # nothing on the base's line descends from `fork`
            return fork
        res = run(["git", "merge-base", f"{landing}^1", branch], cwd=repo_root)
        if res.returncode != 0 or not res.stdout.strip():
            raise IsolationError(
                f"git merge-base {landing[:12]}^1 {branch} failed (exit {res.returncode}): "
                f"{(res.stderr or '').strip()}"
            )
        earlier = res.stdout.strip()
        if earlier == fork:  # fast-forward: the line already held the fork
            return fork
        fork, upper = earlier, f"{landing}^1"


def _branch_fork_and_changes(
    run: Runner, repo_root: Path, branch: str, base_ref: str, start: str | None = None
) -> tuple[str, list[str]]:
    """(fork point, changed names) — the one merge-base/fork computation path
    shared by `branch_changed_paths` and `branch_changes_present`, so the two
    can never drift (#696/#727/#716 all hardened this diff)."""
    mb = run(["git", "merge-base", base_ref, branch], cwd=repo_root)
    if mb.returncode != 0:
        raise IsolationError(
            f"no merge-base for {base_ref} and {branch} — unrelated histories? "
            f"If {base_ref!r} is the wrong base, pass --default-branch <branch>."
        )
    merge_base = _fork_point(run, repo_root, mb.stdout.strip(), branch, base_ref, start)
    changed = _diff_names(run, repo_root, [merge_base, branch])
    return merge_base, changed


def branch_changed_paths(
    run: Runner, repo_root: Path, branch: str, base_ref: str, start: str | None = None
) -> list[str]:
    """The paths `branch` added, modified or deleted since its fork from
    `base_ref` — the same `changed` list `branch_changes_present` diffs
    (§A, 2026-09-28-closeout-always spec). The first half of that function,
    lifted out for close-out's "what did the branch touch"."""
    return _branch_fork_and_changes(run, repo_root, branch, base_ref, start)[1]


def branch_changes_present(
    run: Runner, repo_root: Path, branch: str, base_ref: str, start: str | None = None
) -> MergeVerification:
    """Are the branch's changes present on `base_ref` (e.g. origin/main)?

    Compares CONTENT, not commit identity / ancestry — so it is correct across
    squash, merge-commit, and rebase merges alike (an ancestry/patch-id check
    would false-negative on squash). Two-stage:

    1. Fast path — a file whose `base_ref` content is byte-identical to the
       branch's is present, full stop (covers the clean squash/rebase/merge
       cases with no further work).
    2. For each file that DIFFERS on `base_ref`, fall back to per-line
       containment (`_branch_change_present_in_file`): the branch's own added
       lines must all be on `base_ref`. This is what distinguishes a genuinely
       un-merged change (the #320 orphan — a commit pushed to the branch after
       the merge shows up as a path whose added lines are absent → missing) from
       a CONCURRENT merge that later edits the same file elsewhere (#387 — the
       branch's added lines are still there, so it is NOT missing even though
       whole-file content diverged). If containment fails, the branch's exact
       blob having appeared on the base after the merge also counts as landed
       (a later merge rewrote those lines).

    `start` is the commit the branch was cut from, when fr recorded one
    (`IsolationState.base_sha`) — the only evidence of where a fast-forwarded
    branch began (`_fork_point`, #757).

    Conservative: anything it cannot positively confirm reads as missing (a safe
    "STOP and check", never a false "verified").
    """
    merge_base, changed = _branch_fork_and_changes(run, repo_root, branch, base_ref, start)
    if not changed:
        return MergeVerification(changed=[], missing=[], changes_present=True)
    differing = _diff_names(run, repo_root, [branch, base_ref, "--", *changed])
    missing = [
        path
        for path in differing
        if not _branch_change_present_in_file(run, repo_root, merge_base, branch, base_ref, path)
    ]
    return MergeVerification(changed=changed, missing=missing, changes_present=not missing)


def recorded_start(repo_root: Path, branch: str) -> str | None:
    """The commit fr cut `branch` from at `up` (`IsolationState.base_sha`), or
    None: no record (gc reaped it, or `up` did not create the branch) or an
    unreadable one. `branch_changes_present`'s `start` for callers that hold a
    branch name rather than a state — absence only drops the #757 evidence."""
    try:
        state = load_state(_main_worktree_root(repo_root), branch)
    except Exception:
        return None
    return state.base_sha if state else None


def _realpath(p: Path) -> Path:
    """Symlink-resolved identity for gc's discovery keys. The three sources
    spell the same workspace differently (a docker label is whatever string was
    recorded at `up`; the cache scan builds from `$HOME`; a state record carries
    its own copy), and on macOS `/tmp` is a symlink — so raw path equality would
    classify one workspace twice. Never raises: a path that cannot be resolved
    keys as itself."""
    try:
        return p.resolve()
    except OSError:
        return p


def _main_worktree_root(repo_root: Path) -> Path:
    """The MAIN checkout's toplevel, even when launched from a linked worktree.

    The common dir is <main>/.git; its parent is the main toplevel. Keying
    isolation off the durable main checkout (not the possibly-ephemeral launch
    worktree, e.g. an Agent(isolation:"worktree")) means the persisted state and
    the spawned worktree survive that launch worktree being reaped. No-op for a
    main checkout. #292

    `--separate-git-dir` / non-".git"-named git dirs are out of scope: the
    guard falls back to repo_root (the bind-mount still resolves correctly via
    _git_common_dir; only this normalization is skipped).
    """
    common = _git_common_dir(repo_root)
    return common.parent if common.name == ".git" else repo_root


# ----- `up --branch <B>` classification (#438, spec 2026-09-23 §3.E) -----


@dataclass(frozen=True)
class RemoteView:
    """What fr knows about `origin/<B>`.

    `state` is one of:
    - `exists` — probed and fetched (or, under `--no-fetch`, a local ref);
    - `unfetched` — ls-remote says it exists but the explicit fetch failed;
    - `absent` — ls-remote exit 2, or no origin remote at all;
    - `unknown` — any other probe failure (never read as absence, #354);
    - `unchecked` — `--no-fetch` with no local `origin/<B>` ref.

    `sha` is the local `origin/<B>` ref's commit when one exists: freshly
    fetched for `exists`, the last-fetched value otherwise.
    """

    state: str
    sha: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class BranchDecision:
    """`local` checks `<B>` out as-is; `remote` creates `<B>` from `ref`
    (`origin/<B>`); `cold` hands off to the cold-start base resolution.
    `lines` go to stderr before the worktree is added."""

    action: str
    ref: str | None
    lines: tuple[str, ...]


# A git call that talks to origin is bounded and never prompts (#438 review).
_NETWORK_TIMEOUT_S = 60.0
_BATCH_SSH = "ssh -o BatchMode=yes -o ConnectTimeout=15"


def network_env(run: Runner, repo_root: Path) -> dict[str, str]:
    """The environment for a git call that talks to origin: never prompt
    (no terminal credential prompt; ssh in BatchMode with a connect
    timeout) — unless the operator already chose an ssh command, which a
    GIT_SSH_COMMAND of ours would silently override."""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    if not env.get("GIT_SSH_COMMAND") and not env.get("GIT_SSH"):
        configured = run(["git", "config", "--get", "core.sshCommand"], cwd=repo_root)
        if configured.returncode != 0 or not (configured.stdout or "").strip():
            env["GIT_SSH_COMMAND"] = _BATCH_SSH
    return env


def run_network(
    run: Runner,
    repo_root: Path,
    argv: list[str],
    cwd: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """A bounded, non-interactive git call against origin. A timeout comes
    back as a non-zero, non-2 exit — `unknown`, never `absent`. `extra_env`
    is a forge adapter's host overlay, set on top of the network env
    (gh#1015)."""
    env = {**network_env(run, repo_root), **(extra_env or {})}
    return run(argv, cwd=cwd or repo_root, env=env, timeout=_NETWORK_TIMEOUT_S)


def _forge_runner(run: Runner) -> CommandRunner:
    """This lifecycle's runner as a forge adapter's `CommandRunner`: the
    adapter's host overlay (`GH_HOST` / `GITLAB_HOST`) is applied on top of
    this process's environment, never dropped (gh#1015). With no host the
    call is exactly what it was before the overlay existed."""

    def call(
        argv: list[str], *, cwd: Path, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        if not env:
            return run(argv, cwd=cwd)
        return run(argv, cwd=cwd, env={**os.environ, **env})

    return call


def resolve_branch_refs(
    run: Runner, repo_root: Path, branch: str, remote: str
) -> tuple[list[str], bool]:
    """Fetch `<branch>` from `<remote>`, and report whether that fetch is
    trustworthy as `branch_fetched`.

    The fetch uses an EXPLICIT refspec (`+refs/heads/<b>:refs/remotes/
    <remote>/<b>`, like `_remote_view`), not a bare `git fetch <remote>
    <branch>` (C2 review, #665/#598): in a `--single-branch` clone the
    configured fetch refspec only covers the default branch, so a bare
    fetch of another branch updates FETCH_HEAD only, never the
    remote-tracking ref — leaving `<remote>/<branch>` stale or entirely
    absent and hiding a commit pushed to the real remote branch (from a
    different clone) after the merge.

    A failed fetch is not automatically a fallback: GitHub deletes a
    merged branch by default, and THAT case — `git ls-remote --heads`
    confirms exit 2 for the EXACT `refs/heads/<b>` (a bare name
    pattern-matches `foo/<b>` too) — is the one situation where the
    refs this clone still has (typically the local branch) are still
    trustworthy. Any other outcome (`ls-remote` finds the branch, or
    `ls-remote` itself fails) means the branch's true remote state is
    unknown, so `branch_fetched` is False and the caller must not verify
    off a possibly-stale ref alone.

    Module-level (not bound to a workspace's ops object) so a caller with no
    state file — `fr archive --branch` (2026-09-28-closeout-always §B.2) —
    resolves refs exactly as verify-merge does. Returns every ref among
    `<remote>/<branch>` and the local `<branch>` that resolves; an empty list
    means neither does, and the caller decides how to refuse.
    """
    tracking = f"refs/remotes/{remote}/{branch}"
    fetch = run_network(
        run, repo_root, ["git", "fetch", remote, f"+refs/heads/{branch}:{tracking}"]
    )
    branch_fetched = fetch.returncode == 0
    if not branch_fetched:
        ls = run_network(
            run, repo_root, ["git", "ls-remote", "--exit-code", remote, f"refs/heads/{branch}"]
        )
        branch_fetched = ls.returncode == 2
    refs = [
        cand
        for cand in (f"{remote}/{branch}", branch)
        if run(
            ["git", "rev-parse", "--verify", "--quiet", f"{cand}^{{commit}}"],
            cwd=repo_root,
        ).returncode
        == 0
    ]
    return refs, branch_fetched


def _why(what: str, result: subprocess.CompletedProcess[str]) -> str:
    """`<what> exited <rc>`, plus the last stderr line git printed."""
    lines = [ln for ln in (result.stderr or "").splitlines() if ln.strip()]
    head = f"{what} exited {result.returncode}"
    return f"{head}: {lines[-1].strip()}" if lines else head


def _short(sha: str | None) -> str:
    return (sha or "")[:12]


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _local_row(
    branch: str,
    local_sha: str,
    remote: RemoteView,
    relation: tuple[int, int] | None,
    worktree: Path,
) -> BranchDecision:
    """The `local <B> exists` rows. #322 corner 1: always reuse as-is."""
    remote_ref = f"origin/{branch}"
    line = f"isolation: reusing local branch {branch} at {_short(local_sha)}"
    if remote.state in ("unknown", "unfetched", "unchecked"):
        return BranchDecision("local", branch, (f"{line} (origin not checked: {remote.reason})",))
    if remote.state != "exists" or remote.sha is None or remote.sha == local_sha:
        return BranchDecision("local", branch, (line,))
    if relation is None:
        return BranchDecision(
            "local",
            branch,
            (f"{line} (differs from {remote_ref} at {_short(remote.sha)}; relation unknown)",),
        )
    ahead, behind = relation
    if behind == 0:
        return BranchDecision(
            "local", branch, (f"{line} ({_plural(ahead, 'commit')} ahead of {remote_ref})",)
        )
    if ahead == 0:
        relation_text, catch_up = "is behind", f"merge --ff-only {remote_ref}"
    else:
        relation_text, catch_up = "has diverged from", f"merge {remote_ref}"
    return BranchDecision(
        "local",
        branch,
        (
            f"WARNING: local {branch} ({_short(local_sha)}) {relation_text} {remote_ref} "
            f"({_short(remote.sha)}, +{ahead}/−{behind}) — using local; "
            f"`git -C {worktree} {catch_up}` to catch up",
        ),
    )


def classify_branch(
    branch: str,
    *,
    local_sha: str | None,
    remote: RemoteView,
    relation: tuple[int, int] | None,
    base: str | None,
    worktree: Path,
) -> BranchDecision:
    """The §3.E table as a pure function — no git, no I/O.

    `relation` is (ahead, behind) of local `<B>` against `origin/<B>`, or None
    when it could not be counted; it is only read when both exist and differ.
    Raises IsolationError for the refused rows: `--base` beside a known
    `origin/<B>` (it would fork a second history under one name), and an
    `origin/<B>` that exists but could neither be fetched nor found locally
    (a cold start there is #438 itself).
    """
    if local_sha is not None:
        return _local_row(branch, local_sha, remote, relation, worktree)

    remote_ref = f"origin/{branch}"
    fetch_hint = f"`git fetch origin +refs/heads/{branch}:refs/remotes/origin/{branch}`"
    if remote.state == "unfetched" and remote.sha is None:
        raise IsolationError(
            f"{remote_ref} exists but could not be fetched ({remote.reason}) — retry, "
            f"or {fetch_hint}"
        )
    known = remote.state == "exists" or (
        remote.state in ("unknown", "unfetched") and remote.sha is not None
    )
    if known and base is not None:
        seen = {
            "exists": "exists",
            "unfetched": "exists (fetch failed)",
            "unknown": "was last fetched (origin unreachable)",
        }[remote.state]
        raise IsolationError(
            f"{remote_ref} {seen} — --base would fork a second history under the same "
            "name; drop --base to reuse it, or choose another branch name"
        )
    if remote.state == "exists":
        return BranchDecision(
            "remote",
            remote_ref,
            (f"isolation: reusing remote branch {branch} at {remote_ref} ({_short(remote.sha)})",),
        )
    if remote.sha is not None:  # unknown / unfetched with a last-fetched ref
        why = (
            f"fetch of {remote_ref} failed" if remote.state == "unfetched" else "origin unreachable"
        )
        return BranchDecision(
            "remote",
            remote_ref,
            (
                f"WARNING: {why} — reusing the last-fetched {remote_ref} "
                f"({_short(remote.sha)}); it may be stale",
            ),
        )
    if remote.state == "unknown":
        return BranchDecision(
            "cold",
            None,
            (
                f"WARNING: origin could not be checked for {branch} ({remote.reason}) — "
                "cold-starting it; if it exists on origin this forks a second history",
            ),
        )
    if remote.state == "unchecked":
        return BranchDecision(
            "cold",
            None,
            (
                f"isolation: {remote_ref} not checked (--no-fetch, no local ref) — "
                "starting a new branch",
            ),
        )
    return BranchDecision("cold", None, ())


class LocalWorktreeDevcontainerTarget:
    # The mode this class implements — pinned on the background gc it spawns
    # (gh#569). HostWorktreeTarget overrides it.
    _MODE: ClassVar[str] = "devcontainer"

    def __init__(
        self,
        repo_root: Path,
        runner: Runner = subprocess_runner,
        gc_spawner: GcSpawner = _noop_gc_spawn,
    ):
        # resolve() — the mount target must match the realpath git bakes
        # into the worktree's gitdir pointer (symlinked /tmp on macOS etc.).
        # Then normalize to the main toplevel so a worktree-launched run keys
        # off the durable main checkout (#292).
        self.repo_root = _main_worktree_root(Path(repo_root).resolve())
        self.run = runner
        self._gc_spawner = gc_spawner

    # ---------- lifecycle ----------

    def _worktree_up_core(self, branch: str, path: Path | None) -> Path:
        """Shared worktree prelude for the linked-worktree modes: the git-repo
        guard + the default worktree-path computation + parent mkdir. Extracted
        so `HostWorktreeTarget.up` reuses it verbatim instead of duplicating ~15
        lines (isolation host modes). Callers append their own mode-specific
        steps (profile/devcontainer for the local target; none for host)."""
        if not (self.repo_root / ".git").exists():
            raise IsolationError(
                f"{self.repo_root} is not a git repo — fr isolation only runs inside one."
            )
        # Keyed on the MAIN checkout's basename (spec 2026-09-04 §5.C): an `up`
        # from inside a linked worktree files under the repo, never `agent-…`.
        worktree = path or (
            _home()
            / ".cache"
            / "fr"
            / "worktrees"
            / repo_cache_name(self.repo_root)
            / branch.replace("/", "__")
        )
        worktree.parent.mkdir(parents=True, exist_ok=True)
        return worktree

    def up(
        self,
        profile: str | None,
        branch: str,
        path: Path | None = None,
        base: str | None = None,
        no_fetch: bool = False,
    ) -> IsolationState:
        worktree = self._worktree_up_core(branch, path)
        name = resolve_profile(self.repo_root, profile)
        base_sha = self._git_worktree_add(worktree, branch, base=base, no_fetch=no_fetch)

        config = worktree / ".devcontainer" / name / "devcontainer.json"
        # super-fr#299 part 2: the worktree is cut from the committed tree. If
        # the profile exists only as an UNCOMMITTED file in the base repo, the
        # worktree won't have it — explain the fix instead of letting
        # `devcontainer up` fail with a cryptic "config not found". Gate on the
        # base copy being GENUINELY uncommitted (porcelain non-empty): a profile
        # that is committed but merely absent on an older target branch is a
        # different situation, so we must not misreport it as "not committed".
        if not config.exists():
            rel = f".devcontainer/{name}/devcontainer.json"
            base_status = self.run(
                ["git", "-C", str(self.repo_root), "status", "--porcelain", "--", rel]
            )
            if base_status.stdout.strip():
                raise IsolationError(
                    f"profile {name!r} is written in the base repo but not committed, so the "
                    f"worktree can't see it — run `fr init scaffold --profile {name} --force` "
                    "(which commits; add `--tracking none` if the repo has no recognised "
                    "remote) or commit .devcontainer/ yourself, then retry `fr isolation up`."
                )
        # Record BEFORE the side effect that can fail (gh#578): a failing
        # postCreate used to leave a worktree and a container that neither
        # `status` nor `down` could address. With the record saved first, a
        # failed `up` is a listed workspace — retry `up`, or `down` it.
        state = carried_state(
            self.repo_root, branch, worktree, name, "devcontainer", base_sha=base_sha
        )
        save_state(state)
        self._write_isolation_marker(worktree, branch, created_at=state.created_at)
        try:
            self._devcontainer_up(worktree, name)
        except IsolationError as err:
            raise IsolationError(
                f"{err}\nThe workspace for {branch} is recorded: fix the cause and re-run "
                f"`fr isolation up --branch {branch}`, or remove it with "
                f"`fr isolation down --branch {branch}`."
            ) from err
        self._spawn_gc()
        return state

    @staticmethod
    def _config_path(worktree: Path, profile: str) -> Path:
        """The BRANCH's own profile config — `<worktree>/.devcontainer/<profile>/
        devcontainer.json`, never the base clone's."""
        return worktree / ".devcontainer" / profile / "devcontainer.json"

    def _devcontainer_argv(self, worktree: Path, profile: str, *sub: str) -> list[str]:
        """`devcontainer <sub…> --workspace-folder=<wt> --config=<cfg>`: the
        addressing every devcontainer call shares (up, exec, the ssh probe)."""
        return [
            "devcontainer",
            *sub,
            f"--workspace-folder={worktree}",
            f"--config={self._config_path(worktree, profile)}",
        ]

    def _devcontainer_up(
        self,
        worktree: Path,
        profile: str,
        *,
        remove_existing: bool = False,
        no_cache: bool = False,
    ) -> None:
        """The one `devcontainer up` — shared by `up`, `rebuild` and exec's
        resume, so the mount and config rules cannot drift between them."""
        self._ensure_mounted_env_file(self._config_path(worktree, profile))
        # Resolve the shared common dir, not <repo_root>/.git: correct even if
        # repo_root is a worktree (a gitfile), independent of normalization (#292).
        git_dir = _git_common_dir(self.repo_root)
        argv = [
            *self._devcontainer_argv(worktree, profile, "up"),
            f"--mount=type=bind,source={git_dir},target={git_dir}",
        ]
        if remove_existing:
            argv.append("--remove-existing-container")
        if no_cache:
            argv.append("--build-no-cache")
        try:
            result = self.run(argv, cwd=worktree)
        except FileNotFoundError as err:
            raise IsolationError(_missing_binary(err, "cannot run `devcontainer up`")) from err
        if result.returncode != 0:
            raise IsolationError(f"devcontainer up failed: {result.stderr or result.stdout}")
        probe = self.run(
            [*self._devcontainer_argv(worktree, profile, "exec"), "fr", "--version"],
            cwd=worktree,
        )
        if probe.returncode != 0:
            detail = (probe.stderr or probe.stdout or "fr is not executable").strip()
            raise IsolationError(
                "devcontainer is missing the required `fr` runtime: "
                f"`fr --version` failed: {detail}\n"
                f"Update {self._config_path(worktree, profile)} so postCreateCommand installs "
                "fr without suppressing failures, then run `fr isolation rebuild`."
            )

    def exec(self, state: IsolationState, argv: list[str]) -> int:
        """Run `argv` in the workspace's container, resuming a stopped one first
        (`_ensure_running`, spec §3.B). A missing binary is an IsolationError,
        never a traceback."""
        if not state.worktree.is_dir():
            raise IsolationError(
                f"worktree {state.worktree} for {state.branch} is gone — "
                f"run `fr isolation up --branch {state.branch}`."
            )
        self._ensure_running(state)
        try:
            result = self.run(
                [*self._devcontainer_argv(state.worktree, state.profile, "exec"), *argv],
                cwd=state.worktree,
                capture=False,
            )
        except FileNotFoundError as err:
            raise IsolationError(_missing_binary(err, f"cannot run in {state.branch}")) from err
        return result.returncode

    # Docker states `exec` runs in directly, and the ones it resumes with
    # `devcontainer up` (which re-runs postStartCommand; a bare `docker start`
    # would skip it).
    _RUNNING: ClassVar[frozenset[str]] = frozenset({"running", "restarting"})
    _RESUMABLE: ClassVar[frozenset[str]] = frozenset({"exited", "created"})

    def _ensure_running(self, state: IsolationState) -> None:
        """Bring the workspace's container to a state `devcontainer exec` can
        use, or raise (spec §3.B). A failed `docker ps` raises `docker is
        unreachable` via `_ps_pairs_strict` — never read as absence (#354).
        Absent or dead is never recreated silently: that is a build, not a
        resume, so the error names `rebuild`."""
        branch = state.branch
        rebuild = f"`fr isolation rebuild --branch {branch}` recreates it (worktree kept)."
        pairs = self._ps_pairs_strict(state)
        if any(current in self._RUNNING for _, current in pairs):
            return
        # Several containers can share the label: the first usable one wins,
        # a resumable one before a paused one; only none usable raises.
        resumable = next((cid for cid, cur in pairs if cur in self._RESUMABLE), None)
        paused = next((cid for cid, cur in pairs if cur == "paused"), None)
        if resumable is not None:
            print(
                f"isolation: container for {branch} was stopped — resuming (devcontainer up)",
                file=sys.stderr,
            )
            try:
                self._devcontainer_up(state.worktree, state.profile)
            except IsolationError as err:
                # The hint leads: devcontainer's output is multi-line (p2-f6).
                raise IsolationError(
                    f"could not resume the container for {branch} — {rebuild}\n{err}"
                ) from err
            return
        if paused is not None:
            result = self.run(["docker", "unpause", paused])
            if result.returncode != 0:
                raise IsolationError(
                    f"could not unpause the container for {branch} ({paused}) — {rebuild}\n"
                    f"{(result.stderr or result.stdout or '').strip()}"
                )
            return
        if not pairs:
            raise IsolationError(f"no usable container for {branch} — {rebuild}")
        container, current = pairs[0]
        raise IsolationError(
            f"no usable container for {branch} ({container}, docker state {current}) — {rebuild}"
        )

    def rebuild(self, state: IsolationState, no_cache: bool = False) -> str:
        """Recreate the container against the existing worktree and the
        branch's own profile config (#577, spec §3.A). The state record,
        worktree, marker, bindings and run cursor are never touched.

        On success the old image is reclaimed if the rebuild changed it: the
        rebuild retags the same `vsc-…` name, so the old image becomes `<none>`
        and gc's `vsc-`-prefix sweep would never reach it. On failure nothing
        is reclaimed — `--remove-existing-container` may already have removed
        the old container, and the retry needs its image."""
        branch = state.branch
        if not state.worktree.is_dir():
            raise IsolationError(
                f"worktree {state.worktree} for {branch} is gone — there is nothing to "
                f"rebuild against; run `fr isolation up --branch {branch}`."
            )
        config = self._config_path(state.worktree, state.profile)
        before = self._ps_pairs_strict(state)
        old = before[0][0] if before else None
        old_image = self._image_for(old) if old else None
        try:
            self._devcontainer_up(
                state.worktree, state.profile, remove_existing=True, no_cache=no_cache
            )
        except IsolationError as err:
            raise IsolationError(
                f"rebuild of {branch} failed: {err}\n"
                f"The old container ({old or 'none'}) may already have been removed; the "
                "worktree and run are intact. Fix the profile and retry with "
                f"`fr isolation rebuild --branch {branch}`."
            ) from err
        # The container WAS recreated: a failed re-query must not report the
        # rebuild as failed (p2-f1). Without the new id, skip the reclaim.
        new: str | None = None
        try:
            after = self._ps_pairs_strict(state)
        except IsolationError as err:
            print(
                f"warning: {branch} was rebuilt, but the new container could not be "
                f"queried ({err}); the old image was not reclaimed.",
                file=sys.stderr,
            )
        else:
            known = {cid for cid, _ in before}
            new = next((cid for cid, _ in after if cid not in known), None)
            if new is None and after:
                new = after[0][0]
        new_image = self._image_for(new) if new else None
        if old_image and new_image and new_image != old_image:
            self._reclaim_image(old_image)
        return (
            f"{branch} recreated ({old or 'none'} → {new or 'unknown'}) from {config}; "
            "worktree untouched"
        )

    def restart(self, state: IsolationState, force: bool = False) -> str:
        """Bounce the devcontainer without dropping the worktree (#341 Task 3).

        `docker restart` cycles only the process tree — the container filesystem
        and the bind-mounted worktree survive, so node_modules / local DB stacks
        / in-container installs are kept (unlike down+up). `force` uses
        `--time=0` (immediate SIGKILL then start) for a container too wedged to
        stop gracefully. Returns the restarted container id.
        """
        container, _ = self._require_container(state, "nothing to restart")
        argv = ["docker", "restart", *(["--time=0"] if force else []), container]
        result = self.run(argv)
        if result.returncode != 0:
            raise IsolationError(
                f"docker restart failed: {result.stderr or result.stdout}. If the container "
                "is too wedged to stop gracefully, retry with --force."
            )
        return container

    # Docker states in which the container's process tree is not running —
    # `stop` has nothing to do for these (#471).
    _NOT_RUNNING: ClassVar[frozenset[str]] = frozenset({"exited", "created", "dead"})

    def stop(self, state: IsolationState) -> str:
        """Halt the devcontainer, keeping the worktree, state, marker and
        bindings (#471, spec §3.B). `up`, `restart` or the next `exec` resumes it.

        The stop is verified by re-querying `docker ps --all`, never inferred
        from `docker stop`'s exit code; a query that FAILS is an error, never
        read as 'no container' (the #354 rule). An already-stopped container is
        a no-op success whose message says so."""
        container, current = self._require_container(state, "nothing to stop")
        if current == "dead":
            # Not resumable: `up`/`restart`/`exec` cannot bring a dead container
            # back, so do not promise they will (phase-1 review f4).
            return (
                f"{state.branch}'s container {container} is dead — "
                f"`fr isolation rebuild --branch {state.branch}` recreates it (worktree kept)."
            )
        if current in self._NOT_RUNNING:
            return f"{state.branch} already stopped ({container}, docker state {current})."
        result = self.run(["docker", "stop", container])
        if result.returncode != 0:
            raise IsolationError(
                f"docker stop failed for {state.branch} ({container}): "
                f"{(result.stderr or result.stdout or '').strip()}"
            )
        # Verify THIS container by id, not whatever line comes first: the label
        # filter can list several containers for one worktree (phase-1 review
        # f1). Absent from the re-query means it was removed (`--rm`) — stopped.
        after = dict(self._ps_pairs_strict(state)).get(container)
        if after is not None and after not in self._NOT_RUNNING:
            raise IsolationError(
                f"container {container} for {state.branch} is still running "
                f"(docker state {after}) after `docker stop`."
            )
        return (
            f"{state.branch} stopped ({container}) — worktree, state and bindings kept; "
            "`fr isolation up`, `restart` or the next `exec` resumes it."
        )

    def _ps_parts_strict(self, state: IsolationState) -> list[str]:
        """`[id, state]` of the first container from `docker ps --all`, `[]`
        when there is none. Raises like `_ps_pairs_strict`."""
        pairs = self._ps_pairs_strict(state)
        return list(pairs[0]) if pairs else []

    def _ps_pairs_strict(self, state: IsolationState) -> list[tuple[str, str]]:
        """Every `(id, state)` from `docker ps --all` for this worktree. Unlike
        `_docker_ps_line`, a failed query — or a missing docker binary — raises
        instead of reading as absence (#354)."""
        try:
            result = self._docker_ps(state)
        except FileNotFoundError as err:
            raise IsolationError(
                f"docker is unreachable — cannot query the container for {state.branch}."
            ) from err
        if result.returncode != 0:
            raise IsolationError(
                f"docker is unreachable — `docker ps` failed for {state.branch}: "
                f"{(result.stderr or result.stdout or '').strip()}"
            )
        pairs = []
        for line in (result.stdout or "").splitlines():
            parts = line.split()
            if len(parts) >= 2:
                pairs.append((parts[0], parts[1]))
        return pairs

    def _require_container(self, state: IsolationState, nothing: str) -> tuple[str, str]:
        """The workspace's `(container id, docker state)`; raise with the `up`
        hint when there is none. Shared by `restart` and `stop`."""
        parts = self._ps_parts_strict(state)
        if not parts:
            raise IsolationError(
                f"no container for {state.branch} — {nothing} (run `fr isolation up` first)."
            )
        return parts[0], parts[1]

    def stats(self, state: IsolationState) -> dict[str, str] | None:
        """Host-side `docker stats --no-stream` for a RUNNING container (#341
        Task 3B), so an agent can detect a thrashing container instead of
        inferring it from hung execs. Returns None (never raises) for a missing,
        non-running, or unreadable container — the caller renders `n/a`."""
        # One `docker ps` for both id and state (id state, space-joined).
        parts = self._docker_ps_line(state).split()
        if len(parts) < 2 or parts[1] != "running":
            return None
        container = parts[0]
        # Pipe-delimited: MemUsage ("1.2GiB / 4GiB") itself contains spaces.
        result = self.run(
            [
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}",
                container,
            ]
        )
        line = (result.stdout or "").strip()
        if result.returncode != 0 or line.count("|") != 2:
            return None
        cpu, mem, mem_perc = line.split("|")
        return {"cpu": cpu, "mem": mem, "mem_perc": mem_perc}

    def status(self, state: IsolationState) -> dict[str, Any]:
        return {
            "repo": str(state.repo_root),
            "branch": state.branch,
            "profile": state.profile,
            "worktree": str(state.worktree),
            "worktree_exists": state.worktree.is_dir(),
            "container": self._shown_container_state(state),
            "pr": self._status_pr(state),
        }

    def _status_pr(self, state: IsolationState) -> dict[str, Any] | None:
        """`status`'s PR column: a refused forge lookup is reported on stderr and
        shown as no PR, never a traceback over every row (review p2-r1)."""
        try:
            return self._pr(state)
        except IsolationError as exc:
            print(f"warning: {state.branch}: {exc}", file=sys.stderr)
            return None

    # Backend CLI name + PR/MR label for push_check's guidance line —
    # shares the gh/glab/tea vocabulary `fr._hosts.TAG_FOR_BACKEND` already
    # uses elsewhere, kept local (not imported) since that map's values are
    # the short vk-card tags ("gh"/"gl"/"gt"), not the CLI binary names.
    _CLI_FOR_BACKEND: ClassVar[dict[str, str]] = {
        "github": "gh",
        "gitlab": "glab",
        "gitea": "tea",
    }
    _PR_LABEL: ClassVar[dict[str, str]] = {
        "github": "PR",
        "gitlab": "MR",
        "gitea": "PR",
    }

    def push_check(self, state: IsolationState) -> dict[str, Any]:
        """Read-only preflight diagnostic for #377: worktree remotes,
        whether an SSH agent socket is visible IN-CONTAINER (informational
        only — expected to be ABSENT, that is not a failure), and a
        backend-aware pointer at the correct host-side push workflow. Never
        prints key material, tokens, or ssh-agent socket contents/paths —
        presence/absence only (see `_ssh_agent_probe`)."""
        remote = self.run(["git", "-C", str(state.worktree), "remote", "-v"])
        remotes = [ln for ln in (remote.stdout or "").splitlines() if ln.strip()]
        backend = detect_backend(self.repo_root)
        cli = self._CLI_FOR_BACKEND.get(backend, "gh")
        pr_label = self._PR_LABEL.get(backend, "PR")
        guidance = (
            f"push and {cli} {pr_label} creation must run on the HOST from the worktree "
            f"(cd {state.worktree} && git push ...) — the container has no SSH agent "
            "or git-host credentials by design; see fr-isolation SKILL.md's "
            "Exec-bridge discipline."
        )
        return {
            "branch": state.branch,
            "remotes": remotes,
            "backend": backend,
            "ssh_agent_in_container": self._ssh_agent_probe(state),
            "guidance": guidance,
        }

    def _ssh_agent_probe(self, state: IsolationState) -> dict[str, Any]:
        """In-container SSH_AUTH_SOCK presence check ONLY — reports whether
        the env var is set and, if set, whether the socket path exists, never
        the path itself or any key material (no `ssh-add -l`, no reading the
        socket)."""
        probe_script = (
            'if [ -n "$SSH_AUTH_SOCK" ]; then '
            'if [ -S "$SSH_AUTH_SOCK" ]; then echo set:socket-exists; '
            "else echo set:socket-missing; fi; "
            "else echo unset; fi"
        )
        result = self.run(
            [
                *self._devcontainer_argv(state.worktree, state.profile, "exec"),
                "sh",
                "-c",
                probe_script,
            ],
            cwd=state.worktree,
        )
        detail = (result.stdout or "").strip() or "unknown"
        return {"present": detail.startswith("set:"), "detail": detail}

    def verify_merge(
        self,
        state: IsolationState,
        default_branch: str,
        remote: str = "origin",
    ) -> dict[str, Any]:
        """Confirm the branch's changes reached `<remote>/<default_branch>`.

        Squash/rebase/merge-safe (content-based, not ancestry). `verified`
        requires ALL FOUR positive confirmations — content present AND the PR
        is `MERGED` AND the `<remote>/<default_branch>` ref is fresh (fetch
        succeeded) AND the branch's own remote state is known
        (`branch_fetched`: fetched, or confirmed deleted by `ls-remote`). Every
        ref of the branch that resolves — the fetched `<remote>/<branch>` and
        the local branch — must have its changes on the base. The content check
        alone can be fooled by genuinely convergent content (the same fix
        landing twice), so the MERGED PR is the load-bearing tiebreak; an
        unknown PR state or a failed fetch is
        conservatively NOT verified, never a silent pass. The close-out (#320)
        STOPs (and the caller inspects which signal is missing) when not
        verified.

        The branch is checked at EVERY ref that resolves — `<remote>/<branch>`
        after a fresh fetch of it, and the local branch — so a stale local ref
        cannot decide alone and an unpushed local commit still refuses. Raises
        IsolationError naming the branch when neither resolves.
        """
        refs, branch_fetched = self._branch_refs(state.branch, remote)
        return self._verdict(
            state.worktree,
            state.branch,
            default_branch,
            remote,
            pr=self._pr(state),
            refs=refs,
            branch_fetched=branch_fetched,
            start=state.base_sha,
        )

    def verify_merge_reaped(
        self,
        branch: str,
        default_branch: str,
        remote: str = "origin",
    ) -> dict[str, Any]:
        """`verify_merge` for a branch whose workspace gc already reaped.

        No state file and no worktree, so the same fetch + content check +
        PR-state verdict runs from the repo root, against EVERY ref of the
        branch that still resolves — `<remote>/<branch>` after a fresh fetch of
        it, and the local branch gc keeps. Each must have its changes on the
        base: a post-merge push from another clone lives only on the remote
        ref, an unpushed commit only on the local one, and either is work that
        did not land (adversarial review M1). Raises IsolationError naming the
        ref when neither resolves. `verified` still needs all four signals."""
        refs, branch_fetched = self._branch_refs(branch, remote)
        pr = self._pr_from(self.repo_root, branch)
        res = self._verdict(
            self.repo_root,
            branch,
            default_branch,
            remote,
            pr=pr,
            refs=refs,
            branch_fetched=branch_fetched,
            start=recorded_start(self.repo_root, branch),
        )
        res["reaped"] = True
        return res

    def _branch_refs(self, branch: str, remote: str) -> tuple[list[str], bool]:
        """`resolve_branch_refs`, raising IsolationError when neither ref
        resolves (verify-merge has nothing to check)."""
        refs, branch_fetched = resolve_branch_refs(self.run, self.repo_root, branch, remote)
        if not refs:
            raise IsolationError(
                f"cannot resolve branch ref {branch!r} (neither local nor {remote}/{branch})."
            )
        return refs, branch_fetched

    def _verdict(
        self,
        cwd: Path,
        branch: str,
        default_branch: str,
        remote: str,
        pr: dict[str, Any] | None,
        refs: list[str] | None = None,
        *,
        branch_fetched: bool,
        start: str | None = None,
    ) -> dict[str, Any]:
        base_ref = f"{remote}/{default_branch}"
        fetch = self._run_network(["git", "fetch", remote, default_branch], cwd=cwd)
        fetched = fetch.returncode == 0
        results = [
            branch_changes_present(self.run, cwd, r, base_ref, start) for r in refs or [branch]
        ]
        missing = sorted({m for r in results for m in r.missing})
        changes_present = all(r.changes_present for r in results)
        pr_state = pr.get("state") if pr else None
        # `branch_fetched` (C2 review, #665/#598): a failed branch fetch whose
        # remote state is unknown (not confirmed gone via ls-remote) must not
        # let a possibly-stale ref decide `verified`.
        verified = changes_present and pr_state == "MERGED" and fetched and branch_fetched
        return {
            "branch": branch,
            "verified": verified,
            "changes_present": changes_present,
            "missing": missing,
            "pr_state": pr_state,
            "fetched": fetched,
            "branch_fetched": branch_fetched,
        }

    def _reap_hazard(self, state: IsolationState) -> ReapHazard | None:
        """PURE QUERY — runs no destructive command — so `gc --dry-run` (phase 3)
        can ask exactly the question the live reap path enforces, instead of
        predicting a different answer. `git fetch` is the one exception to
        "no command that writes": it only advances remote-tracking refs, never
        a workspace, branch, or working tree (spec §3.4).

        The exits are ordered LOCAL-FIRST, NETWORK-SECOND, and the ordering is
        load-bearing, not incidental: the free local check must short-circuit
        before any candidate pays for a fetch.

        1. Worktree directory already gone (removed out-of-band) → None, not a
           hazard — the `_down_worktree_tail` post-condition check further down
           treats that as already-torn-down. Nothing left to query, nothing
           left to lose.
        2. DIRTY WORKTREE (#435, phase 1): `git status --porcelain` in
           `state.worktree`. Non-empty output is a hazard — tracked AND
           untracked alike (decision d1: #435's own lost work was a newly
           authored, therefore untracked, file). A NON-ZERO return code is
           also a hazard (`kind="unverifiable"`) rather than being read as
           clean — the #354 invariant ("a failed query is not evidence of
           absence") applied to the working tree. Ignored paths (`.venv/`,
           `.fr-isolation`, `__pycache__/`) never appear in `--porcelain`, so
           routine workspace clutter cannot wedge the guard.
        3. UNLANDED CONTENT (#467, phase 2): the worktree is clean, but the
           branch may hold content that never reached `origin/<default>` — a
           local-only commit, or one pushed to the branch after its PR merged
           (the #320 orphan, caught for free). Fetches `origin/<default>`
           first (a stale local ref would misread a genuinely-merged workspace
           as unlanded), then compares content with `branch_changes_present`.
           A failed fetch is `kind="unverifiable"`, the same #354 invariant
           applied to the network call: offline defers a reap, never permits a
           wrong one.
        """
        if not state.worktree.is_dir():
            return None
        # DRIFTED CHECKOUT (gh#553): every later check speaks for
        # `state.branch`, but the worktree may have another branch checked
        # out (a `git checkout -b` inside the workspace). That branch's
        # commits are checked by nothing below, so refuse rather than reap
        # on the registered branch's verdict. A detached HEAD (mid-rebase,
        # bisect) is not a different branch and falls through.
        head = self.run(["git", "symbolic-ref", "--quiet", "--short", "HEAD"], cwd=state.worktree)
        checked_out = (head.stdout or "").strip() if head.returncode == 0 else ""
        if checked_out and checked_out != state.branch:
            return ReapHazard(
                kind="drifted-checkout",
                detail=_hazard_detail(
                    state.branch,
                    f"has {checked_out} checked out, not the branch fr registered",
                    [],
                    f"Switch back with `git switch {state.branch}`; to keep working on "
                    f"{checked_out}, then give it its own workspace with "
                    f"`fr isolation up --branch {checked_out}`.",
                ),
            )
        status = self.run(["git", "status", "--porcelain"], cwd=state.worktree)
        if status.returncode != 0:
            return ReapHazard(
                kind="unverifiable",
                detail=_hazard_detail(
                    state.branch,
                    "could not be checked for uncommitted changes (git status failed)",
                    [],
                    "Fix the worktree so `git status` runs there, then re-run `fr isolation down`.",
                ),
            )
        paths = [line[3:] for line in (status.stdout or "").splitlines() if line.strip()]
        if paths:
            return ReapHazard(
                kind="dirty-worktree",
                detail=_hazard_detail(
                    state.branch,
                    f"has {len(paths)} uncommitted change(s)",
                    paths,
                    "Commit or stash them.",
                ),
            )

        # Phase 2 (#467): the worktree is clean, but the BRANCH may still hold
        # content that never reached origin/<default> — a local-only commit,
        # or one pushed to the branch after its PR merged (the #320 orphan).
        # Fetch first, using the RESOLVED default branch (never the literal
        # "main" `verify_merge` defaults to — that default is a latent bug for
        # a repo on master) — a stale local origin/<default> would read every
        # genuinely-merged workspace as unlanded (spec §3.4). A failed fetch is
        # itself a hazard, not a pass: the #354 invariant ("a failed query is
        # not evidence of absence") applied to the network call — offline
        # defers a reap, it never permits a wrong one.
        # A repo with NO `origin` remote at all is a different thing from a
        # fetch that failed, and conflating them made `down` unusable there
        # (phase-2 review f3). There is no remote for the branch to be behind,
        # so the content question is unanswerable AND meaningless; and nothing
        # unrecoverable is at stake, because `git worktree remove` leaves the
        # branch and its commits in the repo (phase-1 review f2) while guard 2
        # above still covers the uncommitted work that genuinely has no object.
        # Refusing here would mean a local-only repo could only ever be reaped
        # with --force — the one lever an agent may not reach for on its own
        # (decision d3). Local check, no network.
        if self.run(["git", "remote", "get-url", "origin"], cwd=state.worktree).returncode != 0:
            return None
        default = self._resolve_default_branch()
        fetch = self._run_network(["git", "fetch", "origin", default], cwd=state.worktree)
        if fetch.returncode != 0:
            return ReapHazard(
                kind="unverifiable",
                detail=_hazard_detail(
                    state.branch,
                    f"could not be checked against origin/{default} (git fetch failed)",
                    [],
                    "Check connectivity to origin (or that the remote still exists), "
                    "then re-run `fr isolation down`.",
                ),
            )
        # Deliberately NOT `self.verify_merge(state)` — the tempting reuse and
        # the wrong one (spec §3.3). verify_merge is fetch + branch_changes_present
        # + `self._pr(state)`, and that third call shells out to gh/glab/tea; gc
        # has already made exactly that call one line earlier (`_gc_one`) to
        # classify the workspace, so reusing verify_merge would buy a SECOND
        # host-CLI round trip per reap candidate on a host-wide sweep, only to
        # recompute a PR state the caller is already holding — and then discard
        # `verified`, which the PR-less merged-by-content path can never
        # satisfy anyway. Do the two steps this guard actually needs directly.
        # TOTAL, never raising (phase-2 review f4): `branch_changes_present`
        # raises IsolationError when `git merge-base` fails (unrelated
        # histories, a base ref that vanished between the fetch and here).
        # A guard that raises is worse than one that refuses — `_gc_one`'s
        # `if dry_run:` arms sit OUTSIDE their `try`, so an exception escaping
        # here aborts the whole host-wide sweep, breaking gc's documented
        # "one failed workspace never aborts the sweep" invariant. Unknown
        # state is not "safe to reap"; it is `unverifiable`, which phase 3
        # classifies as a skip. Mirrors `_merged_by_content`'s own
        # `except Exception: return False`.
        try:
            result = branch_changes_present(
                self.run, state.worktree, state.branch, f"origin/{default}", state.base_sha
            )
        except Exception as e:
            return ReapHazard(
                kind="unverifiable",
                detail=_hazard_detail(
                    state.branch,
                    f"could not be compared with origin/{default} ({e})",
                    [],
                    "Check that the branch and origin/"
                    f"{default} share history, then re-run `fr isolation down`.",
                ),
            )
        if result.missing:
            return ReapHazard(
                kind="unlanded-content",
                detail=_hazard_detail(
                    state.branch,
                    f"has {len(result.missing)} changed file(s) that are not on origin/{default}",
                    result.missing,
                    "Push the branch.",
                ),
            )
        return None

    def down(
        self, state: IsolationState, force: bool = False, preserve: bool = True
    ) -> TeardownReport:
        """Tear down the workspace, verifying each destructive step's
        POST-CONDITION before deleting the bookkeeping (#354 Task A).

        Historically `down` ran `docker stop`/`rm` and `git worktree remove`
        with their return codes ignored, then `delete_state()` unconditionally —
        so a transient docker hiccup left a running container that `fr isolation
        status` could no longer see (state gone). Now: re-query the container /
        worktree AFTER the teardown call and, if it survived, raise
        `IsolationError` while LEAVING the state file + `.fr-isolation` marker in
        place, so the workspace stays visible and a retry (or `--force`, for a
        refused-guard case) can finish the job.

        Re-query — not the return code — is authoritative: `docker rm` on an
        already-gone container returns non-zero while the post-condition (gone)
        holds, and a `rm` can return 0 yet leave a wedged container. `--force`
        bypasses all three refusal guards — the open-PR check AND the
        reap-hazard guard (#467 phase 3: dirty worktree, unlanded content,
        unverifiable) — but it never skips THIS verification (that would
        re-introduce the invisible-leak bug).

        Before destroying anything it preserves fr's own records under
        `docs/superpowers/` (#575, spec §3.D) — `preserve=False` discards them,
        and is accepted only together with `force`. Returns what it ended.
        """
        report = self._down_worktree_tail(state, force, preserve=preserve)
        self._spawn_gc()
        return report

    def _open_pr_refusal(self, state: IsolationState) -> str | None:
        """The open-PR guard's refusal text, or None when no PR is open."""
        pr = self._pr(state)
        if pr and pr.get("state") == "OPEN":
            return (
                f"PR for {state.branch} is still open ({pr.get('url', '?')}) — "
                "the operator may push to it. Re-run with --force to tear down anyway."
            )
        return None

    def down_refusal(self, state: IsolationState) -> str | None:
        """PURE QUERY (#533): the reason a non-forced `down` would refuse this
        workspace, or None if it would proceed. Asks the SAME two guards, in
        the same order, that `_down_worktree_tail` enforces — so `down --all`'s
        blast-radius listing predicts rather than guesses — including the
        `isolation: <b> holds active run <id> …` prefix (#575, spec §3.D.1)."""
        runs = _preserve.branch_runs(state.worktree, state.branch)
        open_pr = self._open_pr_refusal(state)
        if open_pr is not None:
            return _preserve.name_runs(runs, open_pr, state.branch)
        hazard = self._reap_hazard(state)
        return (
            _preserve.name_runs(runs, hazard.detail, state.branch) if hazard is not None else None
        )

    def held_runs(self, state: IsolationState) -> str:
        """PURE QUERY: the `holds run <id> at step <cursor>` line(s) for the
        branch's active runs ('' when none) — `down --all` shows it for every
        workspace, even under `--force`, where no refusal carries it."""
        return _preserve.runs_line(_preserve.branch_runs(state.worktree, state.branch))

    def _down_worktree_tail(
        self, state: IsolationState, force: bool, preserve: bool = True
    ) -> TeardownReport:
        """PR guard → reap-hazard guard → STAGE fr's records → environment
        teardown → verified worktree removal → COMMIT the tombstone → marker +
        state retirement. Shared with `HostWorktreeTarget` (#... isolation host
        modes): the ONLY per-mode difference is `_teardown_container`, which the
        host-worktree mode overrides to a no-op (no docker), so both guards, the
        post-condition verification, and the marker/state cleanup stay identical
        across modes.

        #575 (spec §3.D): the branch's runs are computed ONCE and name every
        refusal. Preservation is two-phase — staged after the guards (a copy
        failure raises here, with the workspace intact), committed only after
        the removal is verified — and keyed on `state.repo_root`, so gc's
        host-wide sweep files each record under the workspace's own repo."""
        if not preserve and not force:
            raise IsolationError(
                "--no-preserve is only valid with --force — it discards fr's records "
                "under docs/superpowers/, an explicit per-call decision."
            )
        runs = _preserve.branch_runs(state.worktree, state.branch)
        open_pr = self._open_pr_refusal(state)
        if open_pr is not None and not force:
            raise IsolationError(_preserve.name_runs(runs, open_pr, state.branch))
        if not force:
            hazard = self._reap_hazard(state)
            if hazard is not None:
                raise ReapRefused(
                    ReapHazard(hazard.kind, _preserve.name_runs(runs, hazard.detail, state.branch))
                )
        record = _preserve.stage(state, self.run, runs=runs) if preserve else None
        self._teardown_container(state)
        if record is not None:
            # From here staging/ may be the only copy: protect it (p4-f2).
            _preserve.mark_removal_attempted(record)
        wt = self.run(
            ["git", "worktree", "remove", "--force", str(state.worktree)],
            cwd=self.repo_root,
        )
        if wt.returncode != 0 and state.worktree.exists():
            raise IsolationError(
                f"git worktree remove failed for {state.worktree}: "
                f"{wt.stderr or wt.stdout} — state left intact; retry `fr isolation down`."
            )
        # Marker removal is LAST: a raise above leaves the marker inside the
        # still-present worktree, so the workspace stays a valid isolation
        # workspace. When the worktree is gone the marker went with it — the
        # unlink is then an idempotent no-op.
        preserved: Path | None = None
        reason: str | None = None if preserve else _preserve.NO_PRESERVE
        if record is not None:
            try:
                preserved = _preserve.commit(record, forced=force, run=self.run)
            except Exception as e:
                # The worktree is already gone: failing now would strand the
                # state record of a workspace that no longer exists. The
                # staged copies are protected (removal_attempted) and the next
                # down merges them; the report says where they are (p4-f4).
                reason = (
                    f"could not record the teardown ({e}); the staged copies are at "
                    f"{record.staging}"
                )
        self._remove_isolation_marker(state.worktree)
        delete_state(state.repo_root, state.branch)
        # A retry's record carries the first attempt's runs too (p4-f2).
        ended = record.runs if record is not None else runs
        return TeardownReport(
            branch=state.branch,
            preserved_dir=preserved,
            ended_runs=[(r.id, r.cursor) for r in ended if r.active],
            reason=reason,
            preserved_files=len(record.files) if record is not None and preserved else 0,
            skipped=list(record.skipped) if record is not None else [],
            unpreserved_runs=record.unpreserved_runs() if record is not None else [],
        )

    def _teardown_container(self, state: IsolationState) -> None:
        """Stop + rm the devcontainer and reclaim its image, verifying the
        post-condition. Overridden to a no-op by docker-less modes."""
        # A FAILED `docker ps` (daemon unreachable) must NOT be read as "no
        # container" — that path would `delete_state()` while a container may
        # still be running once the daemon recovers, the exact #354 leak. So the
        # probe raises on query failure, only a successful-but-empty result means
        # "genuinely absent".
        probe = self._docker_ps(state)
        if probe.returncode != 0:
            raise IsolationError(
                f"docker ps failed while tearing down {state.branch} "
                f"({(probe.stderr or probe.stdout or '').strip()}) — cannot verify teardown; "
                "state left intact, retry `fr isolation down` once docker recovers."
            )
        line = (probe.stdout or "").strip()
        container = line.split()[0] if line else None
        # Capture the image id BEFORE `docker rm` (the container must still exist
        # to inspect it); reclaim it AFTER the container is confirmed gone.
        image = self._image_for(container) if container else None
        volumes = self._workspace_volumes(container) if container else []
        if container:
            self.run(["docker", "stop", container])
            self.run(["docker", "rm", container])
            verify = self._docker_ps(state)
            if verify.returncode != 0 or (verify.stdout or "").strip():
                raise IsolationError(
                    f"container for {state.branch} still present (or unverifiable) after "
                    "docker stop/rm — workspace left intact (still visible to `fr isolation "
                    "status`); retry `fr isolation down` once docker recovers."
                )
            self._reclaim_image(image)
            self._reclaim_volumes(volumes)

    def _spawn_gc(self) -> None:
        """Fire the opportunistic background sweep — best-effort, never raises
        into up()/down().

        Every spawner is handed this target's mode (gh#569), so the background
        sweep runs in the mode of the workspace that fired it."""
        try:
            self._gc_spawner(self.repo_root, self._MODE)
        except Exception:
            pass

    # ---------- gc: host-wide reconciliation (#354 Task B) ----------

    def gc(self, dry_run: bool = False) -> list[GcAction]:
        """Reconcile every isolation workspace on the host: tear down the ones
        whose PR merged, leave open-PR and no-PR work alone, and reap orphaned
        containers. Host-wide (an `up` in repo A reaps completed work in B…F),
        so end-to-end workflows no longer depend on a human remembering to run
        `down` in the originating session.

        Classification is authoritative BEFORE any action — a blind `down()`
        would reap in-progress no-PR work (its guard only blocks OPEN PRs). Each
        workspace is handled in isolation: one failed teardown is recorded and
        the sweep continues.

        A host-wide flock serializes concurrent sweeps (two near-simultaneous
        up/down each fork a gc): the second gets `EWOULDBLOCK` and short-circuits
        to an empty report. The sweep is idempotent, so a skipped overlap is
        harmless — the next up/down re-runs it.
        """
        try:
            lock = self._acquire_gc_lock()
        except BlockingIOError:
            return []
        try:
            actions = [self._gc_one_guarded(rec, dry_run) for rec in self._discover_workspaces()]
            actions.extend(self._sweep_dangling_images(dry_run))
            actions.extend(self._sweep_empty_repo_dirs(dry_run))
            actions.extend(self._sweep_stale_sessions(dry_run))
            return actions
        finally:
            lock.close()

    def _acquire_gc_lock(self) -> IO[str]:
        """flock(LOCK_EX | LOCK_NB) on the host-wide gc lock; BlockingIOError if
        another sweep holds it. Idiom mirrored from fr_vk.bridge_cli (reimplemented
        locally — `fr` must not depend on `fr_vk`, which is being dropped)."""
        lock_path = _home() / ".cache" / "fr" / "isolation-gc.lock"
        try:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            lock_path = Path("/tmp/fr-isolation-gc.lock")  # noqa: S108 — unprivileged fallback
        fh = open(lock_path, "w")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            fh.close()
            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                raise BlockingIOError("gc sweep already in progress") from e
            raise
        return fh

    def _gc_one_guarded(self, rec: GcWorkspace, dry_run: bool) -> GcAction:
        """`_gc_one`, but an `IsolationError` that escapes it (a refused forge
        lookup, review p2-r1) skips THAT workspace instead of aborting the
        host-wide sweep. Skipped is the safe verdict: nothing is reaped."""
        try:
            return self._gc_one(rec, dry_run)
        except IsolationError as exc:
            branch = rec.state.branch if rec.state is not None else None
            return GcAction(str(rec.worktree), branch, "unverifiable", "skipped", str(exc))

    def _gc_one(self, rec: GcWorkspace, dry_run: bool) -> GcAction:
        wt = str(rec.worktree)
        if not rec.worktree.is_dir():
            # Orphan: worktree gone. If a container lingers (found by label),
            # reap it directly — no PR check needed (worktree gone ⇒ done).
            if not rec.container_id:
                return self._gc_stale_state(rec, dry_run)
            if dry_run:
                return GcAction(wt, None, "orphan", "would-reap")
            try:
                self._label_reap(rec.container_id)
                if rec.state is not None:  # dangling state file, if any
                    delete_state(rec.state.repo_root, rec.state.branch)
                return GcAction(wt, None, "orphan", "reaped", rec.container_id)
            except Exception as e:  # reap is best-effort; never abort the sweep
                return GcAction(wt, None, "orphan", "reap-failed", str(e))
        state = rec.state
        if state is None:
            return GcAction(wt, None, "no-state", "warned", "worktree present, no fr state")
        pr = self._pr_from(state.worktree, state.branch)
        pr_state = pr.get("state") if pr else None
        if pr is not None and pr_state == "MERGED" and _merged_before(pr, state.created_at):
            # gh#844: the lookup is by branch NAME, so a re-used name answers
            # with an earlier PR that merged before this workspace existed —
            # not this workspace's work. Fall through to the content check,
            # which judges the branch itself.
            pr_state = None
        if pr_state == "MERGED":
            return self._reap_or_classify(wt, state, "merged", dry_run)
        if pr_state == "OPEN":
            return GcAction(wt, state.branch, "open", "skipped")
        # No MERGED/OPEN PR. Before warning forever, check whether the branch's
        # CHANGES already landed on origin/<default> — a PR-less merge (work
        # squash-merged, rebased, or re-authored under another PR) is invisible
        # to gc's PR-only view, so the workspace would warn forever. Reap only
        # when provably safe (see _merged_by_content).
        if self._merged_by_content(state):
            return self._reap_or_classify(wt, state, "merged-by-content", dry_run)
        return GcAction(
            wt, state.branch, "no-pr", "warned", "no PR — `fr isolation down` when done"
        )

    def _reap_or_classify(
        self, wt: str, state: IsolationState, verdict: str, dry_run: bool
    ) -> GcAction:
        """Shared tail for both reap-eligible verdicts (MERGED-by-PR and
        merged-by-content, phase 3, #467 spec §3.5): the classification that
        gets here differs (PR state vs. content comparison), but what to DO
        once classified — preview or reap, and how a refusal reads — is
        identical, so it lives once.

        `_down_worktree_tail`'s hazard guard (force=False, unconditional) can
        still refuse a workspace gc has already classified as reap-eligible —
        e.g. a MERGED PR with an uncommitted change in the worktree. That
        refusal is a DECISION, not a teardown failure: caught here as
        `ReapRefused`, BEFORE the broad `except Exception`, and reported as
        "skipped" with the hazard's own detail — never "reap-failed", which
        reads as breakage and trains the operator to ignore the row. The
        broad handler still catches genuine teardown errors (IsolationError,
        a missing binary, an OSError from delete_state) so one workspace's
        failure never aborts the host-wide sweep.

        dry-run asks `_reap_hazard` the SAME question the live reap enforces
        before promising "would-reap" — a preview that predicts an action the
        live run would refuse is not a preview.

        Both the preview probe and the live teardown go through a sibling built
        from the WORKSPACE's recorded mode (gh#569), not `type(self)`. gc is
        host-wide and `self` is whatever mode the triggering command ran in: a
        host-worktree sweep reaping a devcontainer workspace through
        `type(self)` ran the docker-less `_teardown_container` no-op and leaked
        the container — the #354 leak by another route. Function-local import:
        `routing` imports `hostworktree`, which imports this module.
        """
        from fr.isolation.external import GC_EXTERNAL_DETAIL
        from fr.isolation.routing import target_for_state

        if recorded_mode(state) == "external":
            # An adopted checkout is the preparer's to clean up — classified,
            # never reaped, by a worktree sweep (same verdict ExternalTarget.gc
            # reports).
            return GcAction(wt, state.branch, "external", "skipped", GC_EXTERNAL_DETAIL)
        # Rooted at the WORKSPACE's repo (see the dry-run note below) and built
        # with the NO-OP spawner so a reap never re-triggers a sweep. The cast
        # is sound: with external excluded above, routing only ever returns
        # this class or HostWorktreeTarget.
        sibling = cast(
            "LocalWorktreeDevcontainerTarget",
            target_for_state(state, runner=self.run, gc_spawner=_noop_gc_spawn),
        )
        if dry_run:
            # Ask through a sibling rooted at the WORKSPACE's repo, exactly as
            # the live path below does — `_reap_hazard` calls
            # `_resolve_default_branch()`, which reads `self.repo_root`, and gc
            # is host-wide: `self` here is whichever repo happened to trigger
            # the sweep, not this workspace's. Asking `self` would resolve
            # repo A's default branch while comparing repo B's worktree, so a
            # `master` repo swept from a `main` one would preview "would-skip"
            # for a workspace the live run then reaps — the preview/live
            # divergence this dry-run change exists to remove (phase-3 review
            # f5). Same sibling idiom as `_merged_by_content`.
            hazard = sibling._reap_hazard(state)
            if hazard is not None:
                return GcAction(wt, state.branch, verdict, "would-skip", hazard.detail)
            return GcAction(wt, state.branch, verdict, "would-reap")
        try:
            # Tear down through a Target rooted at the workspace's OWN repo
            # (down() keys git/gh off its repo_root) — substrate-neutral: gc
            # orchestrates Targets, it doesn't reach past them.
            report = sibling.down(state, force=False)
            ended = "; ".join(f"ended run {i} at step {c}" for i, c in report.ended_runs)
            if ended and report.preserved_dir is not None:
                ended += f" — record preserved at {report.preserved_dir}"
            return GcAction(wt, state.branch, verdict, "reaped", ended)
        except ReapRefused as e:
            return GcAction(wt, state.branch, verdict, "skipped", e.hazard.detail)
        except Exception as e:
            # Broad by design (matches the orphan branch): one workspace's
            # teardown — IsolationError, a missing binary, an OSError from
            # delete_state — must NEVER abort the host-wide sweep.
            return GcAction(wt, state.branch, verdict, "reap-failed", str(e))

    def _gc_stale_state(self, rec: GcWorkspace, dry_run: bool) -> GcAction:
        """Worktree gone, no container: retire the dangling fr state RECORD.

        A worktree removed out of band (`rm -rf`, a runner reaping its own
        workspace, a `git worktree remove` outside fr) leaves the state JSON at
        `<git-common-dir>/fr/isolation/<branch>.json` behind. Nothing discovered
        it before this (#423) — discovery was directory/container-driven — so
        `fr isolation status` reported a workspace that no longer exists, forever.

        Only bookkeeping is retired: the branch, its commits, and git's own
        worktree registration are left exactly as they are. Reaping is gated on
        `_stale_state_reapable()` so #354's invariant holds — a FAILED docker
        query must never be read as "no container".
        """
        wt = str(rec.worktree)
        state = rec.state
        if state is None:
            return GcAction(wt, None, "orphan", "skipped", "no container")
        from fr.isolation.external import GC_EXTERNAL_DETAIL
        from fr.isolation.routing import target_for_state

        if recorded_mode(state) == "external":
            return GcAction(wt, state.branch, "external", "skipped", GC_EXTERNAL_DETAIL)
        # Ask the WORKSPACE's mode, not the sweeper's (review p2-f1): a
        # host-worktree sweeper's own answer is an unconditional True, so a
        # devcontainer record whose worktree is gone would be dropped without
        # asking docker whether its container still runs — the #354 leak.
        try:
            owner = cast(
                "LocalWorktreeDevcontainerTarget",
                target_for_state(state, runner=self.run, gc_spawner=_noop_gc_spawn),
            )
        except Exception as e:  # unknown owner ⇒ never reap; never abort the sweep
            return GcAction(wt, state.branch, "orphan", "skipped", f"cannot route: {e}")
        if not owner._stale_state_reapable():
            return GcAction(
                wt, state.branch, "orphan", "skipped", "docker unavailable — reap deferred"
            )
        if dry_run:
            return GcAction(wt, state.branch, "orphan", "would-reap", "stale state record")
        try:
            delete_state(state.repo_root, state.branch)
            return GcAction(wt, state.branch, "orphan", "reaped", "stale state record")
        except Exception as e:  # per-workspace; never abort the host-wide sweep
            return GcAction(wt, state.branch, "orphan", "reap-failed", str(e))

    def _stale_state_reapable(self) -> bool:
        """May a state record whose worktree is gone be retired right now?

        Only when the container view is TRUSTWORTHY: a healthy `docker ps`
        (returncode 0) means `_labelled_containers()` genuinely saw every
        container, so a record with none really is stale. A broken or absent
        daemon defers the reap to a later sweep rather than dropping the state
        file that is the only pointer to a container that may still be running
        (#354). Docker-less modes override this to an unconditional True — they
        have no containers by construction.
        """
        try:
            return self.run(["docker", "ps", "-q"]).returncode == 0
        except Exception:
            return False

    def _merged_by_content(self, state: IsolationState) -> bool:
        """True when a PR-less workspace's changes are ALL already present on
        origin/<default> — a merge gc's PR-only classifier can't see — and
        reaping is provably safe.

        CONTENT-based, not ancestry-based, so it recognizes SQUASH merges — the
        dominant org pattern. A squash lands the branch's net content as a new
        commit, leaving the branch NOT an ancestor of the default branch; an
        `is-ancestor` check would false-negative exactly there. Comparing final
        file content (`branch_changes_present` — squash/rebase/merge-commit safe)
        still sees the work as landed.

        ALL must hold (conservative on every unknown ⇒ False ⇒ warn, never reap):
        - `origin/<default>` resolves and exists;
        - the branch actually CHANGED files since its merge-base — a pristine or
          idle branch that merely fell behind main changed nothing, so it is not
          a merge and is never reaped (this protects the fresh workspace `up`
          creates at, or just behind, the tip);
        - every changed file's final content is already on `origin/<default>`;
        - the worktree is CLEAN (no uncommitted work to lose).

        A stale local `origin/<default>` ref only DEFERS a reap to a later sweep,
        never causes a wrong one. Documented residual (clean-worktree-guarded):
        genuinely convergent content — the identical change landing independently
        on main — reads as merged.
        """
        try:
            wt = state.worktree
            sibling = type(self)(state.repo_root, runner=self.run, gc_spawner=_noop_gc_spawn)
            base = f"origin/{sibling._resolve_default_branch()}"
            if self.run(["git", "rev-parse", "--verify", "--quiet", base], cwd=wt).returncode != 0:
                return False
            status = self.run(["git", "status", "--porcelain"], cwd=wt)
            if status.returncode != 0 or (status.stdout or "").strip():
                return False
            result = branch_changes_present(self.run, wt, state.branch, base, state.base_sha)
            return bool(result.changed) and result.changes_present
        except Exception:
            return False

    def _discover_workspaces(self) -> list[GcWorkspace]:
        """Union THREE ownership-proving sources, then resolve each to its fr
        state. Every source is evidence that fr owns the workspace; nothing here
        enumerates `git worktree list`, so a plain `git worktree add` made by
        other automation is never seen and never reaped (#423 non-goal).

        1. docker-label containers (`devcontainer.local_folder`) — devcontainer
           mode only; docker-less modes override it to an empty list;
        2. directories under the fr worktree cache `~/.cache/fr/worktrees`;
        3. the invoking repo's own fr state records (#423) — the ONLY source
           that finds a workspace created at a custom `--path` (the shape
           runners use) or a record whose worktree has since vanished.

        Sources 1–2 are host-wide; source 3 is necessarily per-repo (state is
        per-repo, there is no host registry), which is why the cache scan stays.
        """
        by_path: dict[Path, GcWorkspace] = {}
        for cid, path in self._labelled_containers():
            by_path[path] = GcWorkspace(worktree=path, container_id=cid, state=None)
        for path in self._worktree_dirs():
            by_path.setdefault(path, GcWorkspace(worktree=path, container_id=None, state=None))
        recorded: dict[Path, IsolationState] = {}
        seen = {_realpath(p) for p in by_path}
        for st in self._repo_states():
            recorded[st.worktree] = st
            key = _realpath(st.worktree)
            if key in seen:
                continue  # already discovered by label/cache — don't double-classify
            seen.add(key)
            by_path[st.worktree] = GcWorkspace(worktree=st.worktree, container_id=None, state=None)
        for path, rec in by_path.items():
            if path.is_dir():
                try:
                    rec.state = self._resolve_state(path)
                except Exception:
                    # A single corrupt/unreadable state JSON must not abort the
                    # host-wide sweep — treat as no-state (the workspace is then
                    # warned, never blindly reaped).
                    rec.state = None
            else:
                # Worktree gone. Carry the state record through so the sweep can
                # retire the dangling bookkeeping (`_gc_stale_state`) instead of
                # leaving `fr isolation status` reporting a phantom workspace.
                rec.state = recorded.get(path)
        return list(by_path.values())

    def _repo_states(self) -> list[IsolationState]:
        """The invoking repo's fr state records — discovery source 3.

        Best-effort: a missing/corrupt state dir yields nothing rather than
        aborting the host-wide sweep (the other two sources still report)."""
        try:
            return list_states(self.repo_root)
        except Exception:
            return []

    def _labelled_containers(self) -> list[tuple[str, Path]]:
        result = self.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "label=devcontainer.local_folder",
                "--format",
                '{{.ID}}\t{{.Label "devcontainer.local_folder"}}',
            ]
        )
        out: list[tuple[str, Path]] = []
        for line in (result.stdout or "").splitlines():
            parts = line.split("\t")
            if len(parts) == 2 and parts[0] and parts[1]:
                out.append((parts[0], Path(parts[1])))
        return out

    def _worktree_dirs(self) -> list[Path]:
        root = _home() / ".cache" / "fr" / "worktrees"
        if not root.is_dir():
            return []
        return [
            child
            for repo in root.iterdir()
            if repo.is_dir()
            for child in repo.iterdir()
            if child.is_dir()
        ]

    def _resolve_state(self, worktree: Path) -> IsolationState | None:
        common = _git_common_dir(worktree)
        repo_root = common.parent if common.name == ".git" else common
        for st in list_states(repo_root):
            if st.worktree == worktree or st.worktree.resolve() == worktree.resolve():
                return st
        return None

    def _label_reap(self, container_id: str) -> None:
        """Reap a container found only by docker label (worktree already gone):
        stop + rm + best-effort image rmi."""
        image = self._image_for(container_id)
        volumes = self._workspace_volumes(container_id)
        self.run(["docker", "stop", container_id])
        self.run(["docker", "rm", container_id])
        self._reclaim_image(image)
        self._reclaim_volumes(volumes)

    def _sweep_dangling_images(self, dry_run: bool) -> list[GcAction]:
        """rmi `vsc-*` devcontainer images no live container references — the
        ~1 GB layers that accumulate as workspaces come and go (#354). Each rmi
        is best-effort: a still-referenced image failing is recorded, never
        raised."""
        referenced = self._referenced_images()
        out: list[GcAction] = []
        for image_id, repo, tag in self._vsc_images():
            ref = f"{repo}:{tag}"
            if image_id in referenced or repo in referenced or ref in referenced:
                continue
            if dry_run:
                out.append(GcAction(repo, None, "dangling-image", "would-reap", image_id))
                continue
            # Reap by the TAGGED ref, not the image id: a dangling image carrying
            # more than one tag makes `docker rmi <id>` fail ("referenced in
            # multiple repositories"). Removing each `repo:tag` untags cleanly and
            # frees the layers on the last tag — no --force, no multi-tag conflict.
            r = self.run(["docker", "rmi", ref])
            out.append(
                GcAction(
                    repo,
                    None,
                    "dangling-image",
                    "reaped" if r.returncode == 0 else "reap-failed",
                    image_id,
                )
            )
        return out

    def _vsc_images(self) -> list[tuple[str, str, str]]:
        result = self.run(["docker", "images", "--format", "{{.ID}}\t{{.Repository}}\t{{.Tag}}"])
        out: list[tuple[str, str, str]] = []
        for line in (result.stdout or "").splitlines():
            parts = line.split("\t")
            if len(parts) == 3 and parts[1].startswith("vsc-"):
                out.append((parts[0], parts[1], parts[2]))
        return out

    def _referenced_images(self) -> set[str]:
        result = self.run(["docker", "ps", "-a", "--format", "{{.Image}}"])
        return {ln.strip() for ln in (result.stdout or "").splitlines() if ln.strip()}

    # ---------- gc: cache + session-index hygiene (spec 2026-09-04 §5.A/§5.C) ----------
    #
    # Substrate-neutral (no docker, no git), so every worktree mode inherits
    # them verbatim; ExternalTarget has its own read-only gc and is untouched.

    def _empty_repo_dirs(self) -> list[Path]:
        """Children of `~/.cache/fr/worktrees` with NO subdirectories — the
        `agent-…` / branch-slug folders an `up` from inside a linked worktree
        used to create before the cache was keyed on the main checkout, plus any
        repo folder whose last workspace was torn down. Stray files (`.DS_Store`)
        do not make a folder live: a workspace is always a subdirectory."""
        root = _home() / ".cache" / "fr" / "worktrees"
        if not root.is_dir():
            return []
        return [
            d
            for d in sorted(root.iterdir())
            if d.is_dir() and not any(c.is_dir() for c in d.iterdir())
        ]

    def _sweep_empty_repo_dirs(self, dry_run: bool) -> list[GcAction]:
        out: list[GcAction] = []
        for d in self._empty_repo_dirs():
            if dry_run:
                out.append(GcAction(str(d), None, "empty-repo-dir", "would-remove"))
                continue
            try:
                shutil.rmtree(d)
                out.append(GcAction(str(d), None, "empty-repo-dir", "removed"))
            except OSError as e:  # per-dir; never abort the host-wide sweep
                out.append(GcAction(str(d), None, "empty-repo-dir", "reap-failed", str(e)))
        return out

    def _sweep_stale_sessions(self, dry_run: bool) -> list[GcAction]:
        """Unlink per-session index files whose worktree is gone or whose
        workspace state no longer lists the session (state wins — the index is
        derived). Classification lives in `sessions.stale_session_indexes`, which
        is pure; only the unlink happens here. `detail` carries the index path."""
        from .sessions import stale_session_indexes

        out: list[GcAction] = []
        for p, data in stale_session_indexes():
            wt, br = data.get("worktree", "?"), data.get("branch")
            if dry_run:
                out.append(GcAction(wt, br, "stale-session", "would-remove", str(p)))
                continue
            p.unlink(missing_ok=True)
            out.append(GcAction(wt, br, "stale-session", "removed", str(p)))
        return out

    # ---------- helpers ----------

    def _ensure_validator_wrapper_in_ref(self, ref: str) -> None:
        """Plan repos need the wrapper in the ref used for worktree add.

        `fr isolation up` creates/reuses a linked worktree from git state, not
        the base checkout's uncommitted files. A filesystem-only wrapper check
        would let an untracked wrapper pass, then the isolated worktree would
        still lack the validator entry point.
        """
        plans = self.run(
            ["git", "ls-tree", ref, "--", "docs/superpowers/plans"],
            cwd=self.repo_root,
        )
        if plans.returncode != 0 or not plans.stdout.strip():
            return
        result = self.run(
            ["git", "ls-tree", ref, "--", "scripts/validate-plans.sh"],
            cwd=self.repo_root,
        )
        line = result.stdout.strip()
        if result.returncode != 0 or not line:
            raise IsolationError(
                f"plan repo has docs/superpowers/plans in {ref} but no "
                f"scripts/validate-plans.sh there; run `{REPAIR_COMMAND}` from the repo "
                "root, commit it to the isolation start ref, then retry `fr isolation up`."
            )
        mode = line.split(maxsplit=1)[0]
        if mode != "100755":
            raise IsolationError(
                f"plan repo has scripts/validate-plans.sh in {ref} but it is not executable; "
                "run `chmod +x scripts/validate-plans.sh`, commit it to the isolation "
                "start ref, then retry `fr isolation up`."
            )

    def _ensure_validator_wrapper_in_worktree(self, worktree: Path) -> None:
        plans = worktree / "docs" / "superpowers" / "plans"
        if not plans.is_dir():
            return
        wrapper = worktree / "scripts" / "validate-plans.sh"
        if not wrapper.is_file() or not (wrapper.stat().st_mode & 0o111):
            raise IsolationError(
                f"existing isolation worktree {worktree} is missing executable "
                f"scripts/validate-plans.sh; run `{REPAIR_COMMAND}`, commit it on the worktree "
                "branch, then retry `fr isolation up`."
            )

    def _git_worktree_add(
        self, worktree: Path, branch: str, base: str | None = None, no_fetch: bool = False
    ) -> str | None:
        """Provision `worktree` on `branch`; the commit a NEW branch was cut
        from, or None when the branch or worktree already existed (gh#768)."""
        if worktree.exists():
            self._ensure_validator_wrapper_in_worktree(worktree)
            return None  # already provisioned — up() is idempotent on the worktree
        # Classify <B> against origin/<B> (#438, spec §3.E). The probe runs
        # for the local rows too, best-effort: an unknown origin never blocks
        # a reuse, and a local branch is never fetched into or rebased (#322
        # corner 1) — only the remote-tracking ref moves.
        local_sha = self._rev(f"refs/heads/{branch}")
        remote = self._remote_view(branch, no_fetch)
        decision = classify_branch(
            branch,
            local_sha=local_sha,
            remote=remote,
            relation=self._relation(local_sha, remote.sha),
            base=base,
            worktree=worktree,
        )
        # stderr, always: `--print-path` and `fr run start` own stdout (§3.C).
        for line in decision.lines:
            print(line, file=sys.stderr)
        track = False
        start_sha: str | None = None
        if decision.action == "local":
            checkout = branch
            argv = ["git", "worktree", "add", str(worktree), branch]
        elif decision.action == "remote":
            checkout = f"origin/{branch}"
            # --no-track + explicit upstream config: git's --track refuses a
            # remote-tracking ref no fetch refspec maps (a --single-branch or
            # narrow-refspec clone — exactly where pods and CI live).
            argv = ["git", "worktree", "add", "--no-track", "-b", branch, str(worktree), checkout]
            track = True
        else:
            # Genuine cold-start: a brand-new branch. Default to freshly-fetched
            # origin/<default> instead of the base repo's current HEAD (#322).
            # An unknown probe already failed to reach origin: no second fetch.
            start_point, log_line = self._cold_start_base(
                branch, base, no_fetch, origin_reachable=remote.state != "unknown"
            )
            checkout = start_point or "HEAD"
            sha = start_sha = self._rev(checkout)
            print(f"{log_line} ({_short(sha)})" if sha else log_line, file=sys.stderr)
            argv = ["git", "worktree", "add", str(worktree), "-b", branch]
            if start_point is not None:
                argv.append(start_point)
        self._ensure_validator_wrapper_in_ref(checkout)
        result = self.run(argv, cwd=self.repo_root)
        if result.returncode != 0:
            raise IsolationError(f"git worktree add failed: {result.stderr}")
        if track:
            self._set_upstream(branch)
        # #575 (spec §3.D.4): only a worktree this call CREATED gets the
        # branch's preserved records back — a reuse returned above. A restore
        # problem never fails the `up`: the worktree is already correct.
        # A cold start is a NEW branch that merely reuses the name: its restore
        # only points at the old records, never applies them (p4-f5).
        try:
            _preserve.restore(
                self.repo_root,
                branch,
                worktree,
                self.run,
                new_branch=decision.action not in ("local", "remote"),
            )
        except Exception as e:
            print(
                f"WARNING: could not restore {branch}'s preserved records ({e}) — they stay "
                f"at {_preserve.preserved_dir(self.repo_root, branch)}",
                file=sys.stderr,
            )
        return start_sha

    def _set_upstream(self, branch: str) -> None:
        """branch.<B>.{remote,merge} — what --track would have written. A
        failure is reported, never fatal: the worktree is already correct."""
        for key, value in (("remote", "origin"), ("merge", f"refs/heads/{branch}")):
            res = self.run(["git", "config", f"branch.{branch}.{key}", value], cwd=self.repo_root)
            if res.returncode != 0:
                print(
                    f"WARNING: could not set {branch}'s upstream to origin/{branch} "
                    f"({_why('git config', res)}) — set branch.{branch}.remote=origin and "
                    f"branch.{branch}.merge=refs/heads/{branch} yourself",
                    file=sys.stderr,
                )
                return

    def _rev(self, ref: str) -> str | None:
        """The commit `ref` names, or None when it names none."""
        result = self.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd=self.repo_root
        )
        sha = (result.stdout or "").strip()
        return sha if result.returncode == 0 and sha else None

    def _network_env(self) -> dict[str, str]:
        return network_env(self.run, self.repo_root)

    def _run_network(
        self, argv: list[str], cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        """A bounded, non-interactive git call against origin. A timeout comes
        back as a non-zero, non-2 exit — `unknown`, never `absent`."""
        return run_network(self.run, self.repo_root, argv, cwd=cwd)

    def _remote_view(self, branch: str, no_fetch: bool) -> RemoteView:
        """Probe `origin/<B>`: `ls-remote --exit-code` (0 exists, 2 absent,
        anything else unknown — never absence, #354), then an explicit-refspec
        fetch so `origin/<B>` updates even in a --single-branch clone."""
        tracking = f"refs/remotes/origin/{branch}"
        if not self._has_origin_remote():
            return RemoteView("absent", None, "no origin remote")
        if no_fetch:
            sha = self._rev(tracking)
            return RemoteView("exists", sha) if sha else RemoteView("unchecked", None, "--no-fetch")
        probe = self._run_network(
            ["git", "ls-remote", "--exit-code", "origin", f"refs/heads/{branch}"]
        )
        if probe.returncode == 2:
            return RemoteView("absent")
        if probe.returncode != 0:
            return RemoteView("unknown", self._rev(tracking), _why("git ls-remote", probe))
        fetch = self._run_network(["git", "fetch", "origin", f"+refs/heads/{branch}:{tracking}"])
        sha = self._rev(tracking)
        if fetch.returncode != 0:
            return RemoteView("unfetched", sha, _why("git fetch", fetch))
        if sha is None:
            return RemoteView("unfetched", None, f"no origin/{branch} after the fetch")
        return RemoteView("exists", sha)

    def _relation(self, local_sha: str | None, remote_sha: str | None) -> tuple[int, int] | None:
        """(ahead, behind) of local `<B>` against `origin/<B>`; None when
        either is missing, they agree, or git cannot count."""
        if local_sha is None or remote_sha is None or local_sha == remote_sha:
            return None
        result = self.run(
            ["git", "rev-list", "--left-right", "--count", f"{local_sha}...{remote_sha}"],
            cwd=self.repo_root,
        )
        parts = (result.stdout or "").split()
        if result.returncode != 0 or len(parts) != 2 or not all(p.isdigit() for p in parts):
            return None
        return int(parts[0]), int(parts[1])

    # ----- .fr-isolation marker lifecycle (#328 Task 3) -----

    def _write_isolation_marker(
        self,
        worktree: Path,
        branch: str,
        mode: str = "worktree",
        created_at: str | None = None,
        target: str = "devcontainer",
    ) -> None:
        """Write the `.fr-isolation` identity marker and git-exclude it.

        `target` (`devcontainer | worktree`) records which isolation `up`
        chose, beside the unchanged `mode` the edit gate reads: both targets
        write `mode: worktree`, and only `target` tells `fr run`'s host-side
        check a devcontainer from a host-worktree pod (spec
        2026-09-25-lean-cost-aware-process §5.B.6, p2-r20).

        The marker is what the `fr-isolation-required` PreToolUse hook reads to
        decide whether an edit is inside a real isolation workspace (#328 Task
        3). Identity = the resolved worktree toplevel + branch + mode; the hook
        blocks when the recorded toplevel does not match the file's actual
        toplevel (a stale / copied marker) or when the toplevel is not a linked
        worktree. `up` also appends it to the shared `info/exclude`, so the
        marker can never be staged into a PR — backed by a committed
        `.gitignore` entry and a CI tripwire.
        """
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / ".fr-isolation").write_text(
            json.dumps(
                {
                    "toplevel": str(worktree.resolve()),
                    "branch": branch,
                    "mode": mode,
                    "target": target,
                    # the state record's own created_at, so an `up` that
                    # carries the record forward does not restamp the marker
                    "created_at": created_at or datetime.now(UTC).isoformat(),
                },
                indent=2,
            )
            + "\n"
        )
        exclude = _git_common_dir(self.repo_root) / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        text = exclude.read_text() if exclude.is_file() else ""
        missing = [p for p in _FR_OWNED_EXCLUDES if p not in text.splitlines()]
        if missing:
            with exclude.open("a") as fh:
                # The file is shared and may be hand-edited: a last line with no
                # trailing newline would otherwise absorb our first pattern
                # (`*.log` + `.fr-isolation` → `*.log.fr-isolation`, gh#843).
                if text and not text.endswith("\n"):
                    fh.write("\n")
                fh.writelines(f"{p}\n" for p in missing)

    def _remove_isolation_marker(self, worktree: Path) -> None:
        """Retire the marker on `down` (idempotent — absent is fine)."""
        (worktree / ".fr-isolation").unlink(missing_ok=True)

    # ----- cold-start base resolution (#322) -----

    def _cold_start_base(
        self, branch: str, base: str | None, no_fetch: bool, origin_reachable: bool = True
    ) -> tuple[str | None, str]:
        """Resolve the start-point for a NEW branch per the spec matrix.

        Returns (start_point, log_line). start_point is the ref to append after
        `-b <branch>`, or None meaning "append nothing" — git then defaults to
        the current HEAD (byte-identical to the legacy behaviour). The log_line
        is printed by the caller, to stderr (every line `up` prints does).
        """
        # Operator named an explicit start-point — use it verbatim, no fetch, no
        # default-branch resolution. `--base HEAD` is the documented opt-in to the
        # old "fork from current checkout" behaviour (stacking / current-branch).
        if base is not None:
            if base == "HEAD":
                return None, f"isolation: basing new branch {branch} on HEAD (--base)"
            return base, f"isolation: basing new branch {branch} on {base} (--base)"

        if no_fetch:
            default = self._resolve_default_branch()
            ref = f"origin/{default}"
            if self._ref_exists(ref):
                return ref, f"isolation: basing new branch {branch} on {ref} (local, --no-fetch)"
            return None, (
                f"WARNING: --no-fetch but no local {ref} tracking ref — "
                f"basing {branch} on local HEAD"
            )

        if not self._has_origin_remote():
            return None, f"WARNING: no origin remote — basing {branch} on local HEAD"

        if not origin_reachable:
            # The <B> probe just failed to reach origin; a second, full fetch
            # would only repeat that wait (#438 review).
            return None, f"WARNING: origin unreachable — basing {branch} on local HEAD"

        if not self._fetch_origin():
            return None, f"WARNING: git fetch origin failed — basing {branch} on local HEAD"

        default = self._resolve_default_branch()
        ref = f"origin/{default}"
        if self._ref_exists(ref):
            return ref, f"isolation: basing new branch {branch} on {ref} (fetched)"
        return None, f"WARNING: {ref} not found after fetch — basing {branch} on local HEAD"

    def _has_origin_remote(self) -> bool:
        result = self.run(["git", "remote"], cwd=self.repo_root)
        return "origin" in (result.stdout or "").split()

    def _fetch_origin(self) -> bool:
        """git fetch origin; return success. Never raises — a fetch problem
        degrades to the local-HEAD fallback, it does not abort the run."""
        result = self._run_network(["git", "fetch", "origin"])
        if result.returncode != 0:
            return False
        # Refresh origin/HEAD so _resolve_default_branch's symbolic-ref hits.
        # Best-effort: a failure here just falls through to the gh/main chain.
        self._run_network(["git", "remote", "set-head", "origin", "--auto"])
        return True

    def _resolve_default_branch(self) -> str:
        """symbolic-ref refs/remotes/origin/HEAD → the forge's own answer → main.

        The forge step is the adapter's `default_branch` (`fr.hostclient.
        client_for`), which picks gh / glab / tea for this checkout's backend;
        a failed lookup reads as `None`, hence "main".
        """
        sym = self.run(
            ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=self.repo_root
        )
        name = (sym.stdout or "").strip()
        if sym.returncode == 0 and name:
            # --short yields "origin/main"; strip to the bare branch name.
            return name.removeprefix("origin/")

        # The forge step runs on this lifecycle's own runner, with the
        # non-interactive network env and timeout (spec
        # 2026-10-06-forge-remainder §4.B), plus the adapter's host (gh#1015).
        try:
            branch = client_for(self.repo_root).default_branch(
                cwd=self.repo_root,
                run=lambda argv, *, cwd, env=None: run_network(
                    self.run, self.repo_root, argv, cwd, extra_env=env
                ),
            )
        except FORGE_ERRORS as exc:  # the lookup soft-fails all else: the host refusal
            raise _forge_refused(exc) from exc
        return branch or "main"

    def _ref_exists(self, ref: str) -> bool:
        return self._rev(ref) is not None

    def _ensure_mounted_env_file(self, config: Path) -> None:
        """Ensure the env-file the profile's devcontainer.json mounts exists.

        Mount-following (#272): the committed config is the source of truth —
        the fr file is created so docker can read it. An unmigrated repo that
        still mounts the legacy vk secrets path hard-errors, pointing at
        `fr init migrate`; no --env-file in runArgs → nothing to ensure.
        """
        try:
            run_args = json.loads(config.read_text()).get("runArgs", [])
        except (OSError, json.JSONDecodeError):
            return
        for flag, value in zip(run_args, run_args[1:]):
            if flag != "--env-file":
                continue
            env_file = Path(value.replace("${localEnv:HOME}", str(_home())))
            if "/.config/vk/secrets/" in str(env_file):
                raise IsolationError(
                    f"{config} still mounts the legacy vk secrets path ({env_file}) — "
                    "run `fr init migrate` to rewrite the --env-file mount to "
                    "~/.config/fr/secrets."
                )
            if not env_file.is_file():
                env_file.parent.mkdir(parents=True, exist_ok=True)
                env_file.write_text(f"# fr isolation secrets — {self.repo_root.name}\n")
            harden_secret_file(env_file)  # 0600 file / 0700 dirs — self-heals loose perms

    def _docker_ps(self, state: IsolationState) -> subprocess.CompletedProcess[str]:
        return self.run(
            [
                "docker",
                "ps",
                "--all",
                f"--filter=label=devcontainer.local_folder={state.worktree}",
                "--format={{.ID}} {{.State}}",
            ]
        )

    def _docker_ps_line(self, state: IsolationState) -> str:
        """Tolerant read for status/stats — empty on absent OR query failure.
        `down()` uses the raw `_docker_ps` so it can tell those two apart: a
        FAILED query must never be read as 'container gone' (that would re-open
        the #354 leak under a down daemon), only a successful-but-empty one."""
        return (self._docker_ps(state).stdout or "").strip()

    def _image_for(self, container: str) -> str | None:
        """The image id backing a container (for post-teardown reclamation)."""
        result = self.run(["docker", "inspect", "--format", "{{.Image}}", container])
        img = (result.stdout or "").strip()
        return img if result.returncode == 0 and img else None

    def _reclaim_image(self, image: str | None) -> None:
        """Best-effort `docker rmi` — #354. A devcontainer's `vsc-*` image is
        ~1 GB and leaks today (down never removed it). Reclamation is OFF the
        verification path: a shared / in-use image failing `rmi` is logged, never
        fatal — image cleanup must not block a teardown whose container is
        already gone."""
        if not image:
            return
        result = self.run(["docker", "rmi", image])
        detail = (result.stderr or result.stdout or "").strip()
        # Already gone is reclaimed, not a failure: a features profile's rebuild
        # can leave the old image id removed before fr gets to it (live walk,
        # phase-6 p6-f1). Only an image that is still there earns the warning.
        if result.returncode != 0 and "No such image" not in detail:
            print(
                f"warning: could not remove image {image} (shared or in use?): {detail}",
                file=sys.stderr,
            )

    def _workspace_volumes(self, container: str) -> list[str]:
        """Named volumes this container's workspace owns, read BEFORE `docker rm`.

        `docker rm` never removes a named volume, and docker-in-docker keeps the
        inner dockerd's whole /var/lib/docker in `dind-var-lib-docker-<id>` — a
        leak of many GB per torn-down workspace. Ownership is the
        `${devcontainerId}` in the volume name: a shared volume (a cache mounted
        by every workspace) carries no id and is never touched."""
        result = self.run(
            [
                "docker",
                "inspect",
                "--format",
                '{{index .Config.Labels "devcontainer.local_folder"}}\t'
                '{{index .Config.Labels "devcontainer.config_file"}}\n'
                '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}} {{end}}{{end}}',
                container,
            ]
        )
        lines = (result.stdout or "").splitlines()
        if result.returncode != 0 or len(lines) < 2:
            return []
        folder, _, config = lines[0].partition("\t")
        if not folder or not config:
            return []
        dc_id = devcontainer_id(folder, config)
        return [v for v in lines[1].split() if dc_id in v]

    def _reclaim_volumes(self, volumes: list[str]) -> None:
        """Best-effort `docker volume rm`, after the container is gone (a mounted
        volume cannot be removed). Like image reclaim, never fatal."""
        for volume in volumes:
            result = self.run(["docker", "volume", "rm", volume])
            detail = (result.stderr or result.stdout or "").strip()
            if result.returncode != 0 and "no such volume" not in detail.lower():
                print(f"warning: could not remove volume {volume}: {detail}", file=sys.stderr)

    def _shown_container_state(self, state: IsolationState) -> str:
        """`status`'s rendering of the docker state: `exited` reads as `stopped`
        (the state `fr isolation stop` leaves, #471); every other state passes
        through; no container is `not running`. A FAILED query is not absence
        (#354, phase-1 review f7): it reads `unknown (docker unreachable)`."""
        try:
            pairs = self._ps_pairs_strict(state)
        except IsolationError:
            return "unknown (docker unreachable)"
        current = pairs[0][1] if pairs else None
        if current is None:
            return "not running"
        return "stopped" if current == "exited" else current

    def _pr(self, state: IsolationState) -> dict[str, Any] | None:
        return self._pr_from(self.repo_root, state.branch)

    def _pr_from(self, cwd: Path, branch: str) -> dict[str, Any] | None:
        """PR/MR-for-branch lookup from an arbitrary repo cwd — gc reconciles
        workspaces across repos, so it can't assume `self.repo_root`. Uses
        host auth (gh/glab) or the CLI's own login (tea).

        The adapter's `pr_for_branch` (`fr.hostclient.client_for(cwd)`) runs
        it on this lifecycle's runner and returns the one shape callers
        depend on: `{"state": "OPEN"|"MERGED"|"CLOSED", "url": str,
        "mergedAt": str|None}` (the merge time where the forge reports one —
        gc's #844 check), or None.
        """
        try:
            return client_for(cwd).pr_for_branch(branch, cwd=cwd, run=_forge_runner(self.run))
        except FORGE_ERRORS as exc:  # the lookup soft-fails all else: the host refusal
            raise _forge_refused(exc) from exc
