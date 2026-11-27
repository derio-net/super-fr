"""Plan file overlap between unmerged batches (spec 2026-11-25-wave-plan-file-overlap).

Batches of one wave conflict only when the second PR to touch a file lands. Every plan
phase already declares the paths it will touch (`phase.files` of each `NN.yaml`), and a
batch's plan sits on its branch long before its PR is ready. This module reads those
paths at each unmerged batch's `origin/<branch>`, through the local clone alone (no
fetch, no write, no forge), and reports the pairs whose plans name the same files.

The check is advisory: nothing here changes a dispatch, a merge, an approval or a state
file. Reads are over raw mappings, never the plan parser, because a plan at a branch head
may come from an older or newer `fr`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Protocol

import yaml

from fr.artifacts.paths import KIND_DIRS
from fr.triage import gitseam
from fr.triage.batch import batch_repo, derive_batch_stage, last_dispatch
from fr.triage.errors import TriageError
from fr.triage.gitseam import Checkout, GitError
from fr.triage.model import Facts, Judgements

RUNS_DIR = KIND_DIRS["run"]
_PHASE_FILE = re.compile(r"^\d+\.yaml$")
_READ_STAGES = frozenset({"dispatched", "pr-open"})


class PlanSource(Protocol):
    """What the reader needs of a clone; `gitseam.Checkout` satisfies it."""

    def exists_at(self, ref: str, path: str) -> bool: ...

    def list_dir(self, ref: str, directory: str) -> list[str]: ...

    def show(self, ref: str, file: str) -> str | None: ...


@dataclass(frozen=True)
class PlanPaths:
    paths: tuple[str, ...]
    plan: str


@dataclass(frozen=True)
class Unread:
    reason: str


@dataclass(frozen=True)
class Entry:
    """One compared batch: *before* is its whole `after` closure (every batch it must
    follow, through any number of batches, merged or not)."""

    batch: str
    repo: str
    wave: int | None
    before: frozenset[str]
    paths: tuple[str, ...]


@dataclass(frozen=True)
class Overlap:
    a: str
    b: str
    repo: str
    wave_a: int | None
    wave_b: int | None
    paths: tuple[str, ...]


@dataclass(frozen=True)
class OverlapReport:
    overlaps: tuple[Overlap, ...]
    unread: tuple[tuple[str, str], ...]  # (batch id, reason)


# ------------------------------------------------------------------ reading a plan


def _names_branch(doc: object, branch: str) -> bool:
    return isinstance(doc, Mapping) and doc.get("branch") == branch


def _cursor_plan(doc: object) -> str | None:
    """The first `plan` value among the steps' `emitted` mappings of cursor *doc*."""
    steps = doc.get("steps") if isinstance(doc, Mapping) else None
    for record in steps.values() if isinstance(steps, Mapping) else ():
        emitted = record.get("emitted") if isinstance(record, Mapping) else None
        plan = emitted.get("plan") if isinstance(emitted, Mapping) else None
        if isinstance(plan, str) and plan:
            return plan
    return None


def _phase_files(doc: object) -> list[str]:
    phase = doc.get("phase") if isinstance(doc, Mapping) else None
    files = phase.get("files") if isinstance(phase, Mapping) else None
    return [f for f in files if isinstance(f, str)] if isinstance(files, list) else []


def _load(source: PlanSource, ref: str, path: str) -> object | Unread:
    """The YAML document at *path*, None when absent; an `Unread` when it cannot be read."""
    try:
        text = source.show(ref, path)
        return None if text is None else yaml.safe_load(text)
    # A branch's file is untrusted: PyYAML raises a plain ValueError for a date-shaped scalar
    # that is no real date (`2020-13-45`), and RecursionError on deep nesting.
    except (TriageError, yaml.YAMLError, ValueError, RecursionError) as exc:
        return Unread(f"unreadable {path}: {' '.join(str(exc).split()) or type(exc).__name__}")


def read_plan_paths(source: PlanSource, branch: str) -> PlanPaths | Unread:
    """The union of the `files:` of every phase of the plan that the run cursor naming
    *branch* records, read at `refs/remotes/origin/<branch>`; or why it cannot be read."""
    ref = f"refs/remotes/origin/{branch}"
    try:
        if not source.exists_at(ref, ""):
            # The read never fetches, so the usual cause is a branch this clone never fetched.
            return Unread(f"no ref origin/{branch} (not fetched in this clone? git fetch origin)")
        names = [n for n in source.list_dir(ref, RUNS_DIR) if n.endswith(".yaml")]
    except TriageError as exc:
        return Unread(f"unreadable {RUNS_DIR}: {' '.join(str(exc).split())}")
    plan: str | None = None
    found = False
    broken: Unread | None = None  # an unreadable cursor matters only if none names the branch
    for name in names:
        doc = _load(source, ref, f"{RUNS_DIR}/{name}")
        if isinstance(doc, Unread):
            broken = broken or doc
            continue
        if _names_branch(doc, branch):
            found = True
            plan = _cursor_plan(doc)
            break
    if not found:
        return broken or Unread("no run cursor")
    if plan is None:
        return Unread("no recorded plan")
    try:
        if not source.exists_at(ref, plan):
            return Unread(f"unreadable {plan}: not found at origin/{branch}")
        phases = sorted(n for n in source.list_dir(ref, plan) if _PHASE_FILE.match(n))
    except TriageError as exc:
        return Unread(f"unreadable {plan}: {' '.join(str(exc).split())}")
    paths: list[str] = []
    for name in phases:
        doc = _load(source, ref, f"{plan}/{name}")
        if isinstance(doc, Unread):
            return doc
        paths.extend(p for p in _phase_files(doc) if p not in paths)
    if not paths:
        # Compared with no paths, the batch would read as "no overlap": say it was not read.
        return Unread(f"plan names no files ({plan})")
    return PlanPaths(tuple(paths), plan)


# ------------------------------------------------------------------ the rule


def _is_glob(path: str) -> bool:
    # `[` alone is no glob: real paths carry it (route segments such as `app/[id]/page.tsx`).
    return any(c in path for c in "*?")


def _matches(path: str, globs: Sequence[str]) -> bool:
    """`fnmatchcase`, where `*` spans `/`, except that a `**/` segment also matches no
    directory at all (`tests/**/*.py` matches `tests/x.py`), as plan authors mean it."""
    return any(
        fnmatchcase(path, g) or ("**/" in g and fnmatchcase(path, g.replace("**/", "")))
        for g in globs
    )


def _shared(a: Entry, b: Entry, ignore: Sequence[str]) -> tuple[str, ...]:
    """Literal paths both name, plus each side's literals matched by the other's globs.
    Two globs never share a path."""
    lit_a = {p for p in a.paths if not _is_glob(p)}
    lit_b = {p for p in b.paths if not _is_glob(p)}
    glob_a = [p for p in a.paths if _is_glob(p)]
    glob_b = [p for p in b.paths if _is_glob(p)]
    common = (lit_a & lit_b) | {p for p in lit_b if _matches(p, glob_a)}
    common |= {p for p in lit_a if _matches(p, glob_b)}
    return tuple(sorted(p for p in common if not _matches(p, ignore)))


def overlaps(entries: Sequence[Entry], *, ignore: Sequence[str]) -> list[Overlap]:
    """The overlapping pairs among *entries*: same repo, no `after` link either way, at
    least one shared path outside *ignore*. Repo names compare case-insensitively (R8 of
    spec 2026-11-27-queue-followups)."""
    found: list[Overlap] = []
    for i, a in enumerate(entries):
        for b in entries[i + 1 :]:
            if a.repo.lower() != b.repo.lower() or b.batch in a.before or a.batch in b.before:
                continue
            if paths := _shared(a, b, ignore):
                found.append(Overlap(a.batch, b.batch, a.repo, a.wave, b.wave, paths))
    return found


def _before(batch_id: str, after: Mapping[str, Sequence[str]]) -> frozenset[str]:
    """Every batch *batch_id* must follow, directly or through others."""
    seen: set[str] = set()
    todo = list(after.get(batch_id, ()))
    while todo:
        dep = todo.pop()
        if dep not in seen:
            seen.add(dep)
            todo.extend(after.get(dep, ()))
    return frozenset(seen)


# ------------------------------------------------------------------ the report


def _ignore_globs(facts: Facts, repo: str) -> list[str]:
    config = facts.config_for(repo)
    return [*config.generated, *(config.version.files if config.version else ())]


def plan_overlap_report(
    judgements: Judgements,
    facts: Facts,
    source_for: Callable[[str], PlanSource | str],
) -> OverlapReport:
    """Read every dispatched or open-PR batch's plan paths and find the overlaps.
    *source_for(repo)* is a clone to read through, or the reason there is none."""
    after = {b.id: list(b.after) for b in judgements.batches}
    entries: list[Entry] = []
    unread: list[tuple[str, str]] = []
    for batch in judgements.batches:
        event = last_dispatch(batch)
        if (
            derive_batch_stage(batch, facts) not in _READ_STAGES
            or event is None
            or not event.branch
        ):
            continue
        repo = batch_repo(batch, facts)
        if repo is None:
            unread.append((batch.id, "repo of batch unknown"))
            continue
        source = source_for(repo)
        if isinstance(source, str):
            unread.append((batch.id, source))
            continue
        read = read_plan_paths(source, event.branch)
        if isinstance(read, Unread):
            unread.append((batch.id, read.reason))
            continue
        entries.append(Entry(batch.id, repo, batch.wave, _before(batch.id, after), read.paths))
    found: list[Overlap] = []
    for repo in sorted({e.repo for e in entries}):
        mine = [e for e in entries if e.repo == repo]
        found.extend(overlaps(mine, ignore=_ignore_globs(facts, repo)))
    return OverlapReport(tuple(found), tuple(unread))


ALL_BATCHES = "(all batches)"


def checked_report(
    judgements: Judgements,
    facts: Facts,
    source_for: Callable[[str], PlanSource | str],
) -> OverlapReport:
    """`plan_overlap_report`, for a caller that must never fail on it (`fr triage check`
    always exits 0, R6): an unexpected exception is one not-compared line, never raised."""
    try:
        return plan_overlap_report(judgements, facts, source_for)
    except Exception as exc:  # noqa: BLE001 - advisory read inside an always-exit-0 command
        cause = " ".join(str(exc).split()) or type(exc).__name__
        return OverlapReport((), ((ALL_BATCHES, f"plan overlap not checked: {cause}"),))


def source_for_clones(
    cwd: Path, checkouts: Mapping[str, Path | None] | None
) -> Callable[[str], PlanSource | str]:
    """The clone to read *repo* through (R9): the driver's own clone from *checkouts*, else
    the clone *cwd* sits in when its `origin` is *repo*. Never raises: a reason string
    says why there is none."""

    def source_for(repo: str) -> PlanSource | str:
        try:
            if checkouts is not None:
                path = checkouts.get(repo.lower())
                return Checkout.at(path) if path is not None else f"no clone of {repo} here"
            top = gitseam.toplevel(cwd)
            if top is None:
                return f"no clone here: {cwd} is not inside a git clone"
            clone = Checkout(top)
            origin = clone.origin_repo()
        except (GitError, OSError) as exc:  # keep the cause: a stale --checkout path, no origin
            return f"no clone here: {' '.join(str(exc).split()) or type(exc).__name__}"
        if origin is None or origin.lower() != repo.lower():
            return f"no clone of {repo} here"
        return clone

    return source_for


# ------------------------------------------------------------------ wording and output


def fix_text(a: str, b: str) -> str:
    """The one wording of the fix, for `fr triage check` and the Batches page."""
    return (
        f"merge {a} and {b} into one batch, or order one after the other "
        f"(`fr triage batch edit {b} --after {a}`), or give one a later `--wave`"
    )


def card_lines(report: OverlapReport) -> dict[str, tuple[str, ...]]:
    """Batch id -> one sentence per overlap it is in: the other batch, the shared paths and
    the fix."""
    lines: dict[str, list[str]] = {}
    for o in report.overlaps:
        shared = ", ".join(o.paths)
        for mine, other in ((o.a, o.b), (o.b, o.a)):
            lines.setdefault(mine, []).append(
                f"Plans overlap with {other} on {shared}: {fix_text(o.a, o.b)}."
            )
    return {k: tuple(v) for k, v in lines.items()}


def report_json(report: OverlapReport) -> dict[str, Any]:
    return {
        "overlaps": [
            {
                "a": o.a,
                "b": o.b,
                "repo": o.repo,
                "waves": [o.wave_a, o.wave_b],
                "paths": list(o.paths),
                "fix": fix_text(o.a, o.b),
            }
            for o in report.overlaps
        ],
        "unread": [{"batch": b, "reason": r} for b, r in report.unread],
    }
