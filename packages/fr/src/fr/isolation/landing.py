"""Landing analysis of the isolation lifecycle (#1517).

Whether a branch's changes reached the default branch: the archived-path
mapping, the commit-log and patch comparison, `branch_changes_present` and
`recorded_start`. Split out of `local.py`; it never imports `fr.isolation.local`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from fr.artifacts.paths import KIND_DIRS
from fr.isolation.branchrefs import _main_worktree_root
from fr.isolation.reap import MergeVerification
from fr.isolation.runner import Runner
from fr.isolation.types import IsolationError, load_state

# `fr archive` (fr/archive.py) `git mv`s a finished run's fr artifacts from
# docs/superpowers/<kind>/<rest> to docs/superpowers/implemented/<kind>/<rest>
# (plans/<dir>, specs/<file>, journals/<scope-dir>/<file>, runs/<id>.yaml,
# usage/<id>.yaml — every destination is the source path with `implemented/`
# spliced in after `docs/superpowers/`). Kept as a local constant, not imported
# from fr.archive: this module must not depend on the archive command.
_ARCHIVED_KINDS = tuple(
    sorted(
        name
        for rel in KIND_DIRS.values()
        if rel.startswith(f"{KIND_DIRS['superpowers']}/")
        and "/" not in (name := rel.removeprefix(f"{KIND_DIRS['superpowers']}/"))
        and f"{KIND_DIRS['archive']}/{name}" in KIND_DIRS.values()
    )
)  # the live kind dirs that have an `implemented/` twin: plans, specs, journals, runs, usage
_SUPERPOWERS = f"{KIND_DIRS['superpowers']}/"


def _archived_path(path: str) -> str | None:
    """Where `fr archive` moves `path` to, or None when it never moves it.

    Only the five archived kinds under docs/superpowers/ map; anything else
    (including a path already under `implemented/`) has no alternate.
    """
    for kind in _ARCHIVED_KINDS:
        if path.startswith(f"{_SUPERPOWERS}{kind}/"):
            return f"{KIND_DIRS['archive']}/{path[len(_SUPERPOWERS) :]}"
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
