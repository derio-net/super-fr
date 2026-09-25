"""Batches: identity, derived stage, the open-batch rule, and the one writer
(spec 2026-09-25-triage-batches §3.A).

Pure over `fr.triage.model` — judgements and facts in, answers out — except
`save_batches`, the ONLY code that writes `judgements.yaml`. No forge call and
no runner lives here: the verbs that touch the forge take a `GhClient` in the
command layer (§3.J), and nothing in `fr.triage` imports `fr_dispatch`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
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
    Judgements,
    PullRequest,
    _check_schema,
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


def batch_pr(batch: Batch, facts: Facts) -> PullRequest | None:
    """The batch's PR: on its dispatch branch, in its repo; highest number wins.

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
    matches = [p for p in pool if p.repo == repo and p.head_ref == event.branch]
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

_TOP_KEY = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:")


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


def _replace_top_level(text: str, key: str, block: str, *, prepend: bool) -> str:
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    span = _top_level_span(lines, key)
    new = block.splitlines(keepends=True)
    if span is not None:
        lines[span[0] : span[1]] = new
    elif prepend:
        lines[:0] = new
    else:
        lines += new
    return "".join(lines)


def save_batches(path: Path, batches: Sequence[Batch]) -> Judgements:
    """Write *batches* as `path`'s `batches:` section and stamp schema 2.

    Only the `schema:` line and the `batches:` section change: the rest of the
    agent-owned file (its comments and layout included) is kept byte for byte.
    The new text is validated through the loader's own model BEFORE anything is
    written, so every load-time rule also holds on write; a refused write leaves
    the file untouched. Returns the judgements as they now load.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TriageError(f"{path}: cannot read judgements: {exc}") from exc
    text = _replace_top_level(text, "schema", f"schema: {JUDGEMENTS_SCHEMA}\n", prepend=True)
    text = _replace_top_level(text, "batches", _dump_batches(batches), prepend=False)
    try:
        data = _check_schema(path, yaml.safe_load(text), JUDGEMENTS_READS)
        judgements = Judgements.model_validate(data)
    except (yaml.YAMLError, ValidationError) as exc:
        raise TriageError(f"{path}: refusing to write invalid judgements: {exc}") from exc
    write_text_atomic(path, text)
    return judgements
