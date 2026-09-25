"""Batches: identity, derived stage, the open-batch rule, and the one writer
(spec 2026-09-25-triage-batches §3.A).

Pure over `fr.triage.model` — judgements and facts in, answers out — except
`save_batches`, the ONLY code that writes `judgements.yaml`. No forge call and
no runner lives here: the verbs that touch the forge take a `GhClient` in the
command layer (§3.J), and nothing in `fr.triage` imports `fr_dispatch`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from itertools import permutations
from pathlib import Path
from typing import Literal

import yaml
from pydantic import ValidationError

from fr.artifacts.atomic import write_text_atomic
from fr.triage.errors import TriageError
from fr.triage.model import (
    JUDGEMENTS_READS,
    JUDGEMENTS_SCHEMA,
    Batch,
    DispatchEvent,
    Facts,
    Issue,
    Judgement,
    Judgements,
    Launch,
    PullRequest,
    TriageConfig,
    _check_schema,
    batch_marker,
    withdrawn_marker,
)

BatchStage = Literal[
    "proposed", "cancelled", "dispatched", "pr-open", "merged", "partial", "abandoned"
]
BATCH_STAGES: tuple[BatchStage, ...] = (
    "proposed",
    "cancelled",
    "dispatched",
    "pr-open",
    "merged",
    "partial",
    "abandoned",
)
# A batch at one of these no longer holds its members (spec §3.A): `partial` and
# `abandoned` are terminal and release their still-open members, like a cancel.
CLOSED_OUT: frozenset[BatchStage] = frozenset({"cancelled", "merged", "partial", "abandoned"})

BRANCH_PREFIX = "feat/batch-"


class BatchConflictError(TriageError):
    """One issue key in two open batches (the open-batch rule, spec §3.A)."""


# ---------------------------------------------------------------- identity


def batch_branch(batch_id: str) -> str:
    """The branch a batch's run works on: `feat/batch-<id>`."""
    return f"{BRANCH_PREFIX}{batch_id}"


def batch_item_id(repo: str, batch_id: str) -> str:
    """The run item id `<owner>/<repo>/run/batch-<id>` (spec §3.C Identity).

    Spelled here rather than imported: `fr.triage` never imports `fr_dispatch`.
    It equals `fr_dispatch.work_item.run_item_id(repo, "batch-<id>")`, which a
    test pins.
    """
    return f"{repo}/run/batch-{batch_id}"


def batch_repo(batch: Batch, facts: Facts) -> str | None:
    """The `OWNER/REPO` the batch's members live in, among the scope's repos."""
    return next(
        (r for r in facts.repos if r.split("/", 1)[1].lower() == batch.repo_name),
        None,
    )


def last_dispatch(batch: Batch) -> DispatchEvent | None:
    """The batch's most recent dispatch event, if any."""
    for event in reversed(batch.events):
        if isinstance(event, DispatchEvent):
            return event
    return None


# ------------------------------------------------------------------- stage


def _members(batch: Batch, facts: Facts) -> list[Issue]:
    found = {i.key: i for i in facts.issues}
    return [found[k] for k in batch.ids if k in found]


def _parse_time(stamp: str | None) -> datetime | None:
    """An aware datetime from a forge timestamp; None when absent or unreadable."""
    if not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def of_dispatch(pr: PullRequest, event: DispatchEvent) -> bool:
    """Whether *pr* can belong to the dispatch *event* (review r2p-f1).

    A PR opened before the dispatch belongs to an earlier one — an abandoned
    PR must not make a redispatch read `abandoned`. A PR whose creation time
    is unknown (facts collected before `createdAt` was read) is kept: it cannot
    be shown to predate the dispatch.
    """
    created = _parse_time(pr.created_at)
    return created is None or created >= event.at


def batch_pr(batch: Batch, facts: Facts) -> PullRequest | None:
    """The batch's PR: on its dispatch branch, in its repo, opened at or after
    its LAST dispatch; highest number wins.

    Candidates are the members' linked PRs, the unlinked open PRs and the
    head-branch lookups (`Facts.batch_prs`) — the last is how a merged PR whose
    body lost every Closes line is still found (spec §3.A).
    """
    event = last_dispatch(batch)
    repo = batch_repo(batch, facts)
    if event is None or repo is None:
        return None
    pool = [p for issue in _members(batch, facts) for p in issue.prs]
    pool += [*facts.prs, *facts.batch_prs]
    matches = [
        p for p in pool if p.repo == repo and p.head_ref == event.branch and of_dispatch(p, event)
    ]
    return max(matches, key=lambda p: p.number, default=None)


def derive_batch_stage(batch: Batch, facts: Facts) -> BatchStage:
    """The spec §3.A stage table, from the last event and the facts. Never stored."""
    if not batch.events:
        return "proposed"
    if batch.events[-1].kind == "cancel":
        return "cancelled"
    pr = batch_pr(batch, facts)
    if pr is None:
        return "dispatched"
    if pr.state == "OPEN":
        return "pr-open"
    if pr.state == "CLOSED":
        return "abandoned"
    found = {i.key: i for i in facts.issues}
    # A member missing from the facts is not known to be closed.
    all_closed = all(k in found and found[k].state == "closed" for k in batch.ids)
    return "merged" if all_closed else "partial"


def is_open(batch: Batch, facts: Facts) -> bool:
    """Open unless cancelled, merged, partial or abandoned (spec §3.A)."""
    return derive_batch_stage(batch, facts) not in CLOSED_OUT


def check_open_membership(batches: Sequence[Batch], facts: Facts) -> None:
    """Refuse when any issue key belongs to two open batches."""
    holders: dict[str, list[str]] = {}
    for batch in batches:
        if is_open(batch, facts):
            for key in batch.ids:
                holders.setdefault(key, []).append(batch.id)
    clashes = {k: ids for k, ids in holders.items() if len(ids) > 1}
    if clashes:
        detail = "; ".join(f"{k} is in {', '.join(ids)}" for k, ids in sorted(clashes.items()))
        raise BatchConflictError(f"an issue may be in only one open batch: {detail}")


# ------------------------------------------------------------------ writer

# A top-level key, plain or quoted (`batches:`, `"batches":`, `'batches':`) —
# all three are the same YAML key, so all three are replaced (review r2p-f6).
_TOP_KEY = re.compile(r"^(?P<q>[\"']?)(?P<key>[A-Za-z_][A-Za-z0-9_]*)(?P=q)\s*:")
_DOC_START = re.compile(r"^---(\s|$)")
_DOC_END = re.compile(r"^\.\.\.(\s|$)")


def _dump_batches(batches: Iterable[Batch]) -> str:
    """The `batches:` block, in field order, storing only what was set.

    `exclude_defaults` is what keeps a launch value that was never given out of
    the file, so dispatch can still resolve it from the repo defaults (§3.B).
    """
    docs = [b.model_dump(mode="json", by_alias=True, exclude_defaults=True) for b in batches]
    return yaml.safe_dump({"batches": docs}, sort_keys=False, allow_unicode=True, width=100)


def _top_level_span(lines: list[str], key: str) -> tuple[int, int] | None:
    """[start, end) of the top-level *key*'s block, trailing blank lines excluded."""
    start = next(
        (i for i, ln in enumerate(lines) if (m := _TOP_KEY.match(ln)) and m["key"] == key),
        None,
    )
    if start is None:
        return None
    end = start + 1
    while end < len(lines):
        ln = lines[end]
        if ln.strip() and not ln[0].isspace() and not ln.startswith("-"):
            break
        end += 1
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return start, end


def _body_bounds(lines: list[str]) -> tuple[int, int]:
    """[start, end) of the document body: after a leading `---` (and any
    directives or comments before it), before a trailing `...`. Inserting
    outside these bounds would make the file two documents (review r2p-f6)."""
    start = next((i + 1 for i, ln in enumerate(lines) if _DOC_START.match(ln)), 0)
    if any(
        ln.strip() and not ln.lstrip().startswith(("#", "%")) for ln in lines[: max(start - 1, 0)]
    ):
        start = 0  # content before the `---`: that marker is not the document start
    end = len(lines)
    while end > start and not lines[end - 1].strip():
        end -= 1
    if end > start and _DOC_END.match(lines[end - 1]):
        return start, end - 1
    return start, len(lines)


def _replace_top_level(text: str, key: str, block: str, *, prepend: bool) -> str:
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    span = _top_level_span(lines, key)
    new = block.splitlines(keepends=True)
    start, end = _body_bounds(lines)
    if span is not None:
        lines[span[0] : span[1]] = new
    elif prepend:
        lines[start:start] = new
    else:
        lines[end:end] = new
    return "".join(lines)


def save_batches(path: Path, batches: Sequence[Batch], *, read: Sequence[Batch]) -> Judgements:
    """Write *batches* as `path`'s `batches:` section and stamp schema 2.

    Only the `schema:` line and the `batches:` section change: the rest of the
    agent-owned file (its comments and layout included) is kept byte for byte.
    The new text is validated through the loader's own model BEFORE anything is
    written, so every load-time rule also holds on write; a refused write leaves
    the file untouched. Returns the judgements as they now load.

    *read* is the batches the caller loaded and based *batches* on. The file's
    CURRENT batches are compared with it first (review r2p-f7): if another
    writer changed them in between, the write is refused rather than silently
    dropping their change.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TriageError(f"{path}: cannot read judgements: {exc}") from exc
    try:
        current = Judgements.model_validate(
            _check_schema(path, yaml.safe_load(text), JUDGEMENTS_READS)
        ).batches
    except (yaml.YAMLError, ValidationError) as exc:
        raise TriageError(f"{path}: cannot read judgements: {exc}") from exc
    if list(current) != list(read):
        raise TriageError(f"{path}: judgements.yaml changed since it was read; re-run")
    text = _replace_top_level(text, "schema", f"schema: {JUDGEMENTS_SCHEMA}\n", prepend=True)
    text = _replace_top_level(text, "batches", _dump_batches(batches), prepend=False)
    try:
        data = _check_schema(path, yaml.safe_load(text), JUDGEMENTS_READS)
        judgements = Judgements.model_validate(data)
    except (yaml.YAMLError, ValidationError) as exc:
        raise TriageError(f"{path}: refusing to write invalid judgements: {exc}") from exc
    write_text_atomic(path, text)
    return judgements


# ------------------------------------------------------------------ launch


def resolve_launch(batch: Batch, config: TriageConfig) -> Launch:
    """The batch's launch, each unset field taken from `defaults.launch` (§3.B).

    Resolved at dispatch, never at create: fr never picks a runner, harness or
    model itself, so a field set in neither place is refused.
    """
    defaults = config.defaults.launch
    resolved = Launch(
        runner=batch.launch.runner or defaults.runner,
        harness=batch.launch.harness or defaults.harness,
        model=batch.launch.model or defaults.model,
    )
    missing = [f for f in ("runner", "harness", "model") if getattr(resolved, f) is None]
    if missing:
        raise TriageError(
            f"batch {batch.id!r} has no {', '.join(missing)} to launch with: give "
            f"{' '.join('--' + f for f in missing)} on the batch, or set defaults.launch "
            "in the repo's .fr/triage.yaml"
        )
    return resolved


# ----------------------------------------------------------------- markers


def latest_marker(
    comments: Iterable[dict[str, object]], item_id: str
) -> Literal["dispatch", "withdrawn"] | None:
    """The kind of the newest fr-batch marker for *item_id* (comments oldest first).

    The two prefixes never match each other (decision p2-withdrawn-marker), so
    a withdrawal after a dispatch reads `withdrawn`, and a redispatch after it
    reads `dispatch` again.
    """
    latest: Literal["dispatch", "withdrawn"] | None = None
    for c in comments:
        body = str(c.get("body") or "").lstrip()
        if body.startswith(withdrawn_marker(item_id)):
            latest = "withdrawn"
        elif body.startswith(batch_marker(item_id)):
            latest = "dispatch"
    return latest


def withdrawn_already(comments: Iterable[dict[str, object]], item_id: str) -> bool:
    """True when the latest fr-batch marker for *item_id* is a withdrawal.

    Makes `batch cancel` idempotent: a re-run after a partial forge failure
    posts a withdrawal only where none is current.
    """
    return latest_marker(comments, item_id) == "withdrawn"


def withdrawal_body(batch: Batch, item_id: str, reason: str) -> str:
    """The cancel comment: marker first, then plain words. No handle, no host."""
    text = f"{withdrawn_marker(item_id)}\nbatch `{batch.id}` withdrawn."
    return f"{text} Reason: {reason}" if reason else text


# ----------------------------------------------------------------- suggest

_URL = re.compile(r"https?://\S+")
_PATH = re.compile(r"[\w.-]+(?:/[\w.-]+)+|[\w-]+\.(?:py|md|ts|js|sh|yaml|yml|json|toml|lock|txt)\b")


@dataclass(frozen=True)
class Suggestion:
    signal: Literal["file", "theme", "pattern"]
    label: str
    keys: list[str]


def cited_paths(text: str) -> set[str]:
    """File paths a judgement's `detail` cites: tokens with a `/` or a file extension."""
    return {m.strip(".,;:") for m in _PATH.findall(_URL.sub(" ", text))}


def _same_file(a: str, b: str) -> bool:
    """Two citations name one file when one is a path suffix of the other."""
    return a == b or a.endswith("/" + b) or b.endswith("/" + a)


def suggest(judgements: Judgements, facts: Facts) -> list[Suggestion]:
    """Candidate groupings of open judged issues in no open batch (§3.B).

    Signals in order: a cited file path, then a theme, then a pattern. Each
    group has two or more members. Pure and model-free: the agent accepts one
    with `create` or ignores it.
    """
    held = {k for b in judgements.batches if is_open(b, facts) for k in b.ids}
    open_keys = {i.key for i in facts.issues if i.state == "open"}
    free = [k for k in judgements.issues if k in open_keys and k not in held]
    out: list[Suggestion] = []

    cites = {k: cited_paths(judgements.issues[k].detail) for k in free}
    groups: dict[frozenset[str], str] = {}
    for path in sorted({p for ps in cites.values() for p in ps}):
        members = frozenset(k for k in free if any(_same_file(path, q) for q in cites[k]))
        if len(members) > 1 and len(path) > len(groups.get(members, "")):
            groups[members] = path
    out += [
        Suggestion("file", label, [k for k in free if k in members])
        for members, label in sorted(groups.items(), key=lambda kv: kv[1])
    ]

    themes: dict[str, list[str]] = {}
    for k in free:
        if theme := judgements.issues[k].theme:
            themes.setdefault(theme, []).append(k)
    out += [Suggestion("theme", t, ks) for t, ks in sorted(themes.items()) if len(ks) > 1]

    for p in judgements.patterns:
        ks = [k for k in p.ids if k in free]
        if len(ks) > 1:
            out.append(Suggestion("pattern", p.title, ks))
    return out


# ------------------------------------------------------------- merge order

# Exhaustive search over the unordered batches up to this many; a greedy pass
# beyond it (a queue that long is already a planning problem of its own).
_EXACT_ORDER_LIMIT = 8
_NO_TIER = 10**6


@dataclass(frozen=True)
class QueueEntry:
    """A `pr-open` batch with its PR and its lowest member tier (§3.F Order)."""

    batch: Batch
    pr: PullRequest
    tier: int = _NO_TIER


def _shares(a: QueueEntry, b: QueueEntry) -> bool:
    return bool(set(a.pr.files) & set(b.pr.files))


def merge_order(entries: Sequence[QueueEntry]) -> list[QueueEntry]:
    """The spec §3.F merge order.

    Explicit `order` values are hard constraints and go first, in order (then
    id). The rest are arranged so that batches sharing files are not adjacent
    where avoidable, then by fewest overlaps, then by lowest member tier, then
    by batch id: among the arrangements with the fewest adjacent overlaps, the
    one whose per-position keys `(overlaps, tier, id)` sort first. Pure and
    deterministic: input order never matters.
    """
    fixed = sorted(
        (e for e in entries if e.batch.order is not None),
        key=lambda e: (e.batch.order, e.batch.id),
    )
    free = sorted((e for e in entries if e.batch.order is None), key=lambda e: e.batch.id)
    overlaps = {e.batch.id: sum(_shares(e, o) for o in entries if o is not e) for e in entries}

    def key(e: QueueEntry) -> tuple[int, int, str]:
        return (overlaps[e.batch.id], e.tier, e.batch.id)

    def adjacent(seq: Sequence[QueueEntry]) -> int:
        return sum(_shares(x, y) for x, y in zip(seq, seq[1:], strict=False))

    if len(free) <= _EXACT_ORDER_LIMIT:
        best = min(
            (list(p) for p in permutations(free)),
            key=lambda p: (adjacent([*fixed[-1:], *p]), [key(e) for e in p]),
        )
        return [*fixed, *best]
    out = list(fixed)
    left = sorted(free, key=key)
    while left:
        pick = next((e for e in left if not (out and _shares(out[-1], e))), left[0])
        out.append(pick)
        left.remove(pick)
    return out


def lowest_tier(batch: Batch, issues: Mapping[str, Judgement]) -> int:
    """The most urgent (lowest) tier among the batch's judged members."""
    return min((issues[k].tier for k in batch.ids if k in issues), default=_NO_TIER)


def pr_open_queue(
    batches: Sequence[Batch], facts: Facts, issues: Mapping[str, Judgement]
) -> list[QueueEntry]:
    """Every `pr-open` batch with its PR, in batch-file order."""
    return [
        QueueEntry(batch=b, pr=pr, tier=lowest_tier(b, issues))
        for b in batches
        if derive_batch_stage(b, facts) == "pr-open" and (pr := batch_pr(b, facts)) is not None
    ]


@dataclass(frozen=True)
class MergeStep:
    batch: Batch
    pr: PullRequest
    reserved_version: str | None
    shared: list[str]  # files this PR shares with a LATER step: the conflict forecast


def with_forecast(ordered: Sequence[QueueEntry]) -> list[MergeStep]:
    """Each step with its reservation and the files it shares with later steps."""
    steps: list[MergeStep] = []
    for i, e in enumerate(ordered):
        later = {f for o in ordered[i + 1 :] for f in o.pr.files}
        event = last_dispatch(e.batch)
        steps.append(
            MergeStep(
                batch=e.batch,
                pr=e.pr,
                reserved_version=event.reserved_version if event else None,
                shared=sorted(set(e.pr.files) & later),
            )
        )
    return steps


def planned_merge_order(
    batches: Sequence[Batch], facts: Facts, issues: Mapping[str, Judgement] | None = None
) -> list[MergeStep]:
    """The `pr-open` batches in the spec §3.F order, with the conflict forecast.

    The board (§3.G) and `batch merge` share this order; merge re-reads each PR
    from the forge before acting on it.
    """
    return with_forecast(merge_order(pr_open_queue(batches, facts, issues or {})))
