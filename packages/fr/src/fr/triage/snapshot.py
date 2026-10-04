"""Render snapshots: what the board showed, kept so the next one can say what changed
(wave-driver R17, design I).

Every `fr triage render` stores `<state dir>/snapshots/<UTC timestamp>.json`, keeps the
latest `KEEP`, and diffs the previous readable snapshot against the new one. The
snapshot records batch id -> stage, issue key -> state and tier, PR -> state and checks,
acceptance counts when the repo has a matrix, and the figures the page shows.

Pure but for the files it writes: the clock is an argument (`store_snapshot(now=)`), so
`render.py`, which must read none, never touches this module's time. A snapshot that
cannot be read — not JSON, wrong schema, wrong shape — is treated as ABSENT, never as
an error and never as zeros: the diff then runs against the next older readable one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from fr.triage.batch import derive_batch_stage
from fr.triage.check import classify
from fr.triage.stage import IN_FLIGHT

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping

    from fr.triage.model import Facts, Judgements, PullRequest

KEEP = 30
ACCEPTANCE_UNTRACKED = "acceptance rows: not tracked for this scope"
SNAPSHOT_DIR = "snapshots"
_STAMP = "%Y%m%dT%H%M%S%fZ"


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IssueState(_M):
    state: str
    tier: int | None = None


class PrState(_M):
    state: str
    draft: bool = False
    checks: dict[str, int] = {}


class Acceptance(_M):
    counts: dict[str, int]
    rows: dict[str, str]


class Snapshot(_M):
    schema_version: Literal[1] = 1
    batches: dict[str, str]
    issues: dict[str, IssueState]
    prs: dict[str, PrState]
    acceptance: Acceptance | None = None
    figures: dict[str, int]


@dataclass(frozen=True)
class SnapshotDiff:
    merged_or_closed: list[str]
    filed: list[str]
    stage_changes: list[str]
    acceptance_moved: list[str]
    figures_changed: list[tuple[str, int, int]]
    acceptance_note: str | None = None  # set when the new board tracks no acceptance rows

    @property
    def empty(self) -> bool:
        return not (
            self.merged_or_closed
            or self.filed
            or self.stage_changes
            or self.acceptance_moved
            or self.figures_changed
        )


# --------------------------------------------------------------------- taking


def figures(facts: Facts, judgements: Judgements) -> dict[str, int]:
    """The measured figures the page's masthead shows, plus the unplaced count."""
    result = classify(facts, judgements)
    return {
        "open": sum(1 for i in facts.issues if i.state == "open"),
        "unranked": len(result.unranked),
        "in flight": sum(1 for i in facts.issues if i.stage in IN_FLIGHT),
        "settled": len(result.settled) + len(result.settled_prs),
        "repos": len(facts.collected),
        "unplaced": len(result.unplaced),
        "batches": len(judgements.batches),
    }


def _all_prs(facts: Facts) -> Iterable[PullRequest]:
    seen: set[tuple[str, int]] = set()
    pools = [facts.prs, facts.batch_prs, *(i.prs for i in facts.issues)]
    for pool in pools:
        for pr in pool:
            if (pr.repo, pr.number) not in seen:
                seen.add((pr.repo, pr.number))
                yield pr


def pr_key(pr: PullRequest) -> str:
    return f"{pr.repo}#{pr.number}"


def take_snapshot(
    facts: Facts, judgements: Judgements, *, acceptance: Mapping[str, str] | None
) -> Snapshot:
    """What the board shows now. *acceptance* maps matrix row id -> status, or None
    when the repo has no matrix."""
    acc: Acceptance | None = None
    if acceptance is not None:
        counts: dict[str, int] = {}
        for status in acceptance.values():
            counts[status] = counts.get(status, 0) + 1
        acc = Acceptance(counts=counts, rows=dict(acceptance))
    return Snapshot(
        batches={b.id: derive_batch_stage(b, facts) for b in judgements.batches},
        issues={
            i.key: IssueState(
                state=i.state, tier=j.tier if (j := judgements.issues.get(i.key)) else None
            )
            for i in facts.issues
        },
        prs={
            pr_key(pr): PrState(state=pr.state, draft=pr.is_draft, checks=dict(pr.checks))
            for pr in _all_prs(facts)
        },
        acceptance=acc,
        figures=figures(facts, judgements),
    )


def acceptance_rows(matrix: Path | None) -> dict[str, str] | None:
    """Matrix row id -> status for *matrix*; None when there is none or it will not load."""
    if matrix is None or not matrix.is_file():
        return None
    from fr.acceptance.model import load_matrix

    try:
        return {r.id: str(r.status) for r in load_matrix(matrix).rows}
    except Exception:  # an unreadable matrix is "no matrix": the board never fails on it
        return None


# --------------------------------------------------------------------- storing


def store_snapshot(
    state_dir: Path, snap: Snapshot, now: datetime, *, warn: Callable[[str], None] | None = None
) -> Path:
    """Write *snap* under `<state_dir>/snapshots/` named for *now* (UTC), then drop all
    but the latest `KEEP`. Retention counts file names, readable or not. Pruning is
    best-effort: a file that cannot be removed is reported through *warn*, never raised."""
    target = state_dir / SNAPSHOT_DIR
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{now.astimezone(UTC).strftime(_STAMP)}.json"
    path.write_text(snap.model_dump_json(indent=2) + "\n", encoding="utf-8")
    for old in sorted(target.glob("*.json"))[:-KEEP]:
        try:
            old.unlink()
        except OSError as exc:
            if warn is not None:
                warn(f"cannot prune old snapshot {old}: {exc}")
    return path


def _readable(state_dir: Path) -> Iterator[Snapshot]:
    target = state_dir / SNAPSHOT_DIR
    if not target.is_dir():
        return
    for path in sorted(target.glob("*.json"), reverse=True):
        try:
            yield Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValidationError, OSError, UnicodeDecodeError):
            continue


def stored_snapshots(state_dir: Path) -> list[tuple[datetime, Snapshot]]:
    """Every READABLE stored snapshot with the time its file name records (UTC), oldest
    first. A corrupt file, or one whose name is not a stamp, is skipped as absent."""
    target = state_dir / SNAPSHOT_DIR
    out: list[tuple[datetime, Snapshot]] = []
    if not target.is_dir():
        return out
    for path in sorted(target.glob("*.json")):
        try:
            when = datetime.strptime(path.stem, _STAMP).replace(tzinfo=UTC)
            out.append((when, Snapshot.model_validate_json(path.read_text(encoding="utf-8"))))
        except (ValueError, ValidationError, OSError, UnicodeDecodeError):
            continue
    return out


def latest_snapshot(state_dir: Path) -> Snapshot | None:
    """The newest READABLE snapshot, or None. A corrupt one is skipped as absent."""
    return next(_readable(state_dir), None)


def previous_snapshot(state_dir: Path, new: Snapshot) -> Snapshot | None:
    """What *new* is diffed against: the newest readable snapshot that DIFFERS from it,
    so a re-render with nothing new keeps showing the last real change. When every
    readable one is identical, the latest (an empty diff); None when there is none."""
    latest: Snapshot | None = None
    for snap in _readable(state_dir):
        if snap != new:
            return snap
        latest = latest or snap
    return latest


def matrix_for_scope(scope_repo: str | None, cwd: Path) -> Path | None:
    """The acceptance matrix to read for a scope: the checkout containing *cwd*'s
    `docs/acceptance/matrix.yaml`, but only when the scope is the single repo
    *scope_repo* (OWNER/REPO) and that checkout's `origin` names it. A matrix is one
    repo's; reading it for any other scope would record unrelated rows."""
    if scope_repo is None:
        return None
    from fr.triage.gitseam import GitError, git, repo_of_url

    try:
        top = Path(git(["rev-parse", "--show-toplevel"], cwd).strip())
        origin = repo_of_url(git(["remote", "get-url", "origin"], top).strip())
    except GitError:
        return None
    if origin is None or origin.lower() != scope_repo.lower():
        return None
    matrix = top / "docs" / "acceptance" / "matrix.yaml"
    return matrix if matrix.is_file() else None


# ---------------------------------------------------------------------- diffing


def diff_snapshots(previous: Snapshot | None, new: Snapshot) -> SnapshotDiff | None:
    """What changed from *previous* to *new*; None when there is no previous."""
    if previous is None:
        return None
    done: list[str] = []
    for key, now in sorted(new.issues.items()):
        before = previous.issues.get(key)
        if before is not None and before.state == "open" and now.state == "closed":
            done.append(f"{key} closed")
    for key, now_pr in sorted(new.prs.items()):
        before_pr = previous.prs.get(key)
        if (
            before_pr is not None
            and before_pr.state == "OPEN"
            and now_pr.state in {"MERGED", "CLOSED"}
        ):
            done.append(f"PR {key} {now_pr.state.lower()}")
    filed = [
        key for key, now in sorted(new.issues.items()) if key not in previous.issues
        and now.state == "open"
    ]  # fmt: skip
    stages = [
        f"{bid}: {previous.batches.get(bid, 'new')} -> {stage}"
        for bid, stage in sorted(new.batches.items())
        if previous.batches.get(bid) != stage
    ]
    moved: list[str] = []
    if previous.acceptance is not None and new.acceptance is not None:
        for row, status in sorted(new.acceptance.rows.items()):
            old = previous.acceptance.rows.get(row)
            if old is None:
                moved.append(f"{row}: added as {status}")
            elif old != status:
                moved.append(f"{row}: {old} -> {status}")
    changed = [
        (name, previous.figures.get(name, 0), value)
        for name, value in new.figures.items()
        if previous.figures.get(name, 0) != value
    ]
    note = ACCEPTANCE_UNTRACKED if new.acceptance is None else None
    return SnapshotDiff(done, filed, stages, moved, changed, note)
