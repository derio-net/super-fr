"""Amendments: how a feature changes a row another feature merged (spec 2026-11-04
R16, R17).

- **Which fragment.** An amendment is written to the fragment of the feature making
  it: `--feature`, else the spec of the run this branch carries, else refused
  (`resolve_feature`).
- **Merged rows are immutable.** A row as it stands in a fragment on the default ref
  changes only by amendment; `merged_row_edits` names every working-tree edit that
  breaks that.
- **Stale base.** Before merge, `check` and `deliver` fetch the default ref and
  refuse a branch amendment whose `base` is not its row's revision
  (`branch_refusals`, over `Effective.stale_pending`); `fr acceptance amend
  --rebase` re-bases them.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from fr.acceptance.fold import Effective, default_ref_fold, effective
from fr.acceptance.fragment import Fragment, fragment_slug_for_spec, parse_fragment
from fr.acceptance.model import AcceptanceError

IMMUTABLE = "rows merged on {ref} change only by amendment"
"""The refusal's wording, one place (the check and its tests read it)."""


def _branch_run_specs(repo_root: Path, branch: str) -> set[str]:
    """The spec (repo-relative) of every run cursor recorded for *branch*."""
    from fr.artifacts.paths import artifact_root
    from fr.requirements import run_spec
    from fr.run.model import RUNS_REL, RunStateError, parse_run_state

    runs = artifact_root(repo_root) / RUNS_REL
    if not runs.is_dir():
        return set()
    specs: set[str] = set()
    for path in sorted(runs.glob("*.yaml")):
        try:
            state = parse_run_state(path.read_text())
        except (RunStateError, OSError, UnicodeDecodeError):
            continue
        if state.branch == branch and (spec := run_spec(state)) is not None:
            specs.add(spec)
    return specs


def resolve_feature(repo_root: Path, given: str | None) -> str | None:
    """The feature an amendment is written to: *given*, else the spec slug of the
    one run this branch carries, else None (the caller refuses, naming --feature)."""
    if given:
        return given
    from fr.run.adopt import current_branch

    branch = current_branch(repo_root)
    if branch is None:
        return None
    slugs = {fragment_slug_for_spec(s) for s in _branch_run_specs(repo_root, branch)}
    return slugs.pop() if len(slugs) == 1 else None


NO_FEATURE = (
    "an amendment is written to the fragment of the feature making it, and none is "
    "known: pass --feature <spec-slug> (or run on the branch of a run with a spec)"
)


FEATURE_PLACEHOLDER = "<spec-slug>"


def _origin_feature(repo_root: Path, origins: tuple[str, ...]) -> str | None:
    """The fragment slug of the one spec *origins* name, or None (none, or several)."""
    from fr.acceptance.logical import is_logical, origin_spec_path, parse_logical

    slugs: set[str] = set()
    for origin in origins:
        if is_logical(origin):
            try:
                ref = parse_logical(origin)
            except AcceptanceError:
                continue
            if ref.kind == "spec":
                slugs.add(fragment_slug_for_spec(ref.slug))
            continue
        path = origin_spec_path(origin, repo_root)
        if path is not None:
            slugs.add(fragment_slug_for_spec(path))
    return slugs.pop() if len(slugs) == 1 else None


def feature_flag(repo_root: Path, row_id: str | None = None, *, spec: str | None = None) -> str:
    """The `--feature <slug>` every command fr PRINTS for a post-merge `set-status` or
    `amend` carries (R16: an amendment goes to the fragment of the feature making it,
    and a post-merge walk or link belongs to the feature whose gate or delivery it
    closes): *spec*'s slug when the printer knows the run's spec, else the one spec
    *row_id*'s origin names, else a placeholder the operator fills. Never the row
    owner's fragment by default: that is the shared file R16 exists to avoid."""
    import shlex

    feature = fragment_slug_for_spec(spec) if spec else None
    if feature is None and row_id is not None:
        from fr.acceptance.fold import effective

        try:
            row = next((r for r in effective(repo_root).matrix.rows if r.id == row_id), None)
        except AcceptanceError:
            row = None
        if row is not None:
            feature = _origin_feature(repo_root, tuple(row.origin))
    return f"--feature {shlex.quote(feature) if feature else FEATURE_PLACEHOLDER}"


def default_ref_name(repo_root: Path) -> str | None:
    """`origin/main`-style name of the default ref, or None."""
    from fr.git import GitRefusal, GitUnavailableError, remote_default_ref

    try:
        named = remote_default_ref(repo_root)
    except GitUnavailableError:
        return None
    return None if named is None or isinstance(named, GitRefusal) else named


def merged_row_edits(repo_root: Path, merged: Effective | None, ref: str | None) -> list[str]:
    """Every row (and amendment) of a fragment on the default ref that this branch
    changed or removed (R16: a merged row changes only by amendment). Compared by
    value; an entry the branch never had (it merged after the branch forked) is the
    branch being behind, not an edit, so it is judged against the merge base."""
    if merged is None or ref is None:
        return []
    from fr.acceptance.fold import _tip_fragments, git_runner

    run = git_runner(repo_root)
    sha = run(["rev-parse", "--verify", "--quiet", f"refs/remotes/{ref}^{{commit}}"], None)
    if sha.returncode != 0:
        return []
    tip_sha = sha.stdout.decode().strip()
    tip = _tip_fragments(run, tip_sha)
    fork = run(["merge-base", "HEAD", tip_sha], None)
    forked = _tip_fragments(run, fork.stdout.decode().strip()) if fork.returncode == 0 else {}
    errors: list[str] = []
    rule = IMMUTABLE.format(ref=ref)
    for rel, frag in sorted(tip.items()):
        path = repo_root / rel
        try:
            now = parse_fragment(path.read_text(), source=rel) if path.is_file() else None
        except AcceptanceError as e:
            errors.append(str(e))
            continue
        errors += _fragment_edits(rel, frag, now, forked.get(rel), rule)
    return errors


def _fragment_edits(
    rel: str, frag: Fragment, now: Fragment | None, then: Fragment | None, rule: str
) -> list[str]:
    """The R16 edits of one merged fragment *frag*: its rows as the branch has them
    (*now*) against the merged ones, and its merged amendments (*then*: as the branch
    forked from them) leading the working list unchanged, in order."""
    errors: list[str] = []
    rows = {r.id: r for r in now.rows} if now is not None else {}
    at_fork = {r.id: r for r in then.rows} if then is not None else {}
    for row in frag.rows:
        current = rows.get(row.id)
        if current == row or current == at_fork.get(row.id):
            continue  # unchanged, or untouched by this branch
        what = "removed" if current is None else "edited in place"
        errors.append(
            f"{rel}: row {row.id} {what}; {rule} (`fr acceptance amend --id {row.id}`, "
            f"or `fr acceptance set-status`, which writes one)"
        )
    # The fold orders a fragment's amendments by position, so the merged ones (as
    # this branch forked from them: an amendment merged since is the branch being
    # behind) must lead the working list unchanged, in order. A multiset compare
    # let a swap, or an insert above them, pass and change the post-merge fold.
    merged_list = then.amendments if then is not None else ()
    working = now.amendments if now is not None else ()
    for k, a in enumerate(merged_list):
        if k < len(working) and working[k] == a:
            continue
        errors.append(
            f"{rel}: merged amendment {k} ({a.op} of row {a.row}, base {a.base}) removed, "
            "changed, reordered or preceded by a new one; a merged amendment is never "
            "edited, and a new one is appended after every merged one"
        )
        break
    return errors


def outside_merged_row_edits(repo_root: Path) -> list[str]:
    """`merged_row_edits` under quiet and stealth (review p5-r5): this branch's own
    feature, once merged, keeps its fragments as they were frozen at the merge
    (`fr.acceptance.fold.own_merged_fragments`); a row or amendment it changed since is
    refused like an in-place edit on the default ref."""
    from fr.acceptance.fold import own_merged_fragments

    found = own_merged_fragments(Path(repo_root))
    if found is None:
        return []
    frozen, live, ref = found
    rule = IMMUTABLE.format(ref=ref)
    errors: list[str] = []
    for rel, text in sorted(frozen.items()):
        try:
            frag = parse_fragment(text, source=rel)
            now = parse_fragment(live[rel], source=rel) if rel in live else None
        except AcceptanceError as e:
            errors.append(str(e))
            continue
        errors += _fragment_edits(rel, frag, now, frag, rule)
    return errors


def stale_lines(effective: Effective) -> list[str]:
    """R17's stale-base refusal, one line per pending amendment, with the fix."""
    return [
        f"{s.path}: amendment {s.op} of row {s.row} is based on revision {s.base}, but the "
        f"row is at revision {s.revision} on the default ref (another feature amended it "
        f"first): review the row, then re-base with `fr acceptance amend --rebase`"
        for s in effective.stale_pending
    ]


@dataclass
class BranchCheck:
    """What `check` and `deliver` refuse before merge (R16, R17)."""

    errors: list[str] = field(default_factory=list)
    """Merged rows edited in place: a malformed branch."""
    stale: list[str] = field(default_factory=list)
    """Stale-base amendments: refused, exit 2."""
    warnings: list[str] = field(default_factory=list)
    source: str | None = None
    """Which default ref the checks read: fetched, or the checkout's local ref."""


def _local_sha(repo_root: Path, ref: str) -> str | None:
    """The commit `refs/remotes/<ref>` names at the checkout, or None."""
    from fr.git import GitUnavailableError, git_answer

    try:
        done = git_answer(
            repo_root, "rev-parse", "--verify", "--quiet", f"refs/remotes/{ref}^{{commit}}"
        )
    except GitUnavailableError:
        return None
    return done.stdout.strip() or None if done.returncode == 0 else None


def _ci() -> bool:
    from fr.artifacts.trigger import in_ci

    return in_ci()


def _has_remote(repo_root: Path) -> bool:
    """Whether *repo_root* is a git repo naming any remote (two remotes with no
    default count: the default ref is then unresolvable, not absent)."""
    from fr.git import GitUnavailableError, git_answer

    try:
        listed = git_answer(repo_root, "remote")
    except GitUnavailableError:
        return False
    return listed.returncode == 0 and bool(listed.stdout.split())


def fetch_default(repo_root: Path, ref: str) -> str | None:
    """`git fetch <remote> <branch>` for the default ref *ref*; None on success,
    else why it failed."""
    from fr.git import git_argv

    remote, _, branch = ref.partition("/")
    try:
        done = subprocess.run(
            git_argv(
                repo_root, "fetch", "--quiet", remote, f"+refs/heads/{branch}:refs/remotes/{ref}"
            ),
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return str(e)
    return None if done.returncode == 0 else (done.stderr.strip() or f"exit {done.returncode}")


def branch_refusals(repo_root: Path, *, fetch: bool = True) -> BranchCheck:
    """Fetch the default ref (unless *fetch* is False), then the immutability and
    stale-base checks. A failed fetch is a warning when the checkout already holds the
    default ref (a CI checkout with `fetch-depth: 0`, an offline laptop): the checks
    read that local ref and `source` names it. A failed fetch with no local ref, or a
    remote with no resolvable default ref, is a refusal in CI and a warning elsewhere.
    A repo with no remote is judged against HEAD, as before."""
    from fr.acceptance.fold import clear_fold_cache, has_fragments

    out = BranchCheck()
    root = Path(repo_root)
    if not has_fragments(root):
        return out
    ref = default_ref_name(root)
    if ref is None and _has_remote(root):
        # With no default ref the fold falls back to HEAD, so the immutability and
        # stale-base checks would pass vacuously (review p3-r3): CI refuses, as a
        # failed fetch does; a laptop is warned. A repo with no remote has nothing
        # merged to judge against, and keeps no refusal.
        line = (
            "the repo has a remote but no default ref (no `<remote>/HEAD`, no "
            "`<remote>/{main,master,trunk,develop}`), so merged rows and stale bases "
            "cannot be judged: fetch the default branch (`git fetch <remote> <branch>`, "
            "`git remote set-head <remote> --auto`), or check out with `fetch-depth: 0` in CI"
        )
        if _ci():
            out.errors.append(f"{line}; refused")
            return out
        out.warnings.append(line)
    if fetch and ref is not None:
        why = fetch_default(root, ref)
        if why is None:
            clear_fold_cache()
            local = _local_sha(root, ref)
            out.source = f"{ref} at {local[:12]} (fetched)" if local else f"{ref} (fetched)"
        else:
            # A CI checkout that already holds the default branch (`fetch-depth: 0`
            # with `persist-credentials: false`, whose own fetch of a private repo
            # fails) is judged against that ref, and says so (review pr1408-r3). With
            # no local ref at all there is nothing to judge against: CI refuses.
            line = f"cannot fetch the default ref {ref}: {why}"
            local = _local_sha(root, ref)
            if local is None:
                if _ci():
                    out.errors.append(f"{line}; a stale base cannot be judged, so this is refused")
                    return out
                out.warnings.append(f"{line}; no local {ref} to check against")
            else:
                out.source = f"the local ref {ref} at {local[:12]} (fetch failed)"
                out.warnings.append(f"{line}; checking against {out.source}")
    elif ref is not None:
        local = _local_sha(root, ref)
        out.source = (
            f"the local ref {ref}" + (f" at {local[:12]}" if local else "") + " (not fetched)"
        )
    try:
        merged = default_ref_fold(root)
        out.errors += merged_row_edits(root, merged, ref)
        out.errors += outside_merged_row_edits(root)
        out.stale += stale_lines(effective(root))
    except AcceptanceError as e:
        out.errors.append(str(e))
    return out
