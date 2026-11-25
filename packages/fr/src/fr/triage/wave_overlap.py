"""Which open batches of one wave expect to change the same files (spec
2026-11-24-wave-queue-gaps R7-R10).

Pure over judgements and facts. A batch's expected change set is its PR's changed files
when it has one, else the paths its members' judgement details and trusted issue bodies
cite. Generated files and the version bump's files are left out: they conflict by
construction and the queue settles them itself. The surfaces (`batch suggest`, `create`,
`edit`, the dispatch brief) print what this module returns.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations

from fr.triage.batch import batch_pr, batch_repo, cited_paths, is_open, same_file
from fr.triage.intake import untrusted_issues
from fr.triage.model import Batch, Facts, Judgements
from fr.triage.regen import is_generated


@dataclass(frozen=True)
class Overlap:
    wave: int
    a: str  # batch ids, in id order
    b: str
    paths: tuple[str, ...]  # the shared files, sorted, each in its longer spelling


def expected_paths(batch: Batch, judgements: Judgements, facts: Facts) -> frozenset[str]:
    """The files *batch* is expected to change (R7)."""
    pr = batch_pr(batch, facts)
    if pr is not None and pr.files:
        found = set(pr.files)
    else:
        distrusted = {i.key for i, _ in untrusted_issues(facts)}
        bodies = {i.key: i.body for i in facts.issues}
        found = set()
        for key in batch.ids:
            if (j := judgements.issues.get(key)) is not None:
                found |= cited_paths(j.detail)
            if key not in distrusted:
                found |= cited_paths(bodies.get(key, ""))
    repo = batch_repo(batch, facts)
    config = facts.config_for(repo) if repo else None
    generated = config.generated if config else []
    versioned = config.version.files if config and config.version else []
    return frozenset(
        p
        for p in found
        if not is_generated(p, generated) and not any(same_file(p, v) for v in versioned)
    )


def _shared(a: frozenset[str], b: frozenset[str]) -> tuple[str, ...]:
    return tuple(sorted({max(p, q, key=len) for p in a for q in b if same_file(p, q)}))


def wave_overlaps(
    batches: Sequence[Batch],
    judgements: Judgements,
    facts: Facts,
    *,
    only: str | None = None,
) -> list[Overlap]:
    """Each unordered pair of open batches in one wave whose expected paths overlap (R8);
    with *only* (a batch id), just the pairs that batch forms."""
    live = sorted(
        (b for b in batches if b.wave is not None and is_open(b, facts)), key=lambda b: b.id
    )
    expected = {b.id: expected_paths(b, judgements, facts) for b in live}
    out: list[Overlap] = []
    for x, y in combinations(live, 2):
        if x.wave != y.wave or x.wave is None or x.repo_name != y.repo_name:
            continue  # the queue is per repo: batches of two repos never conflict
        if only is not None and only not in (x.id, y.id):
            continue
        if paths := _shared(expected[x.id], expected[y.id]):
            out.append(Overlap(x.wave, x.id, y.id, paths))
    return out


def overlap_line(o: Overlap, next_wave: int) -> str:
    """The R8 sentence: the pair, the shared paths and the two remedies."""
    return (
        f"overlap in wave {o.wave}: `{o.a}` and `{o.b}` both expect to change "
        f"{', '.join(o.paths)}; merge them into one batch, or move one to wave {next_wave} "
        "(`fr triage batch edit <batch> --wave N`)"
    )


def overlap_lines(
    batches: Sequence[Batch], judgements: Judgements, facts: Facts, *, only: str | None = None
) -> list[str]:
    """The lines a verb prints: one per overlapping pair, naming the next wave."""
    return [
        overlap_line(o, o.wave + 1) for o in wave_overlaps(batches, judgements, facts, only=only)
    ]


def overlap_brief_lines(
    batch: Batch, batches: Sequence[Batch], judgements: Judgements, facts: Facts
) -> list[str]:
    """R10: the dispatch brief's lines for a batch that overlaps another open one."""
    out: list[str] = []
    for o in wave_overlaps(batches, judgements, facts, only=batch.id):
        other = o.b if o.a == batch.id else o.a
        out.append(
            f"- Batch `{other}` of this wave also expects to change {', '.join(o.paths)}. "
            "Whichever of the two lands second gets the queue's conflict hand-back, naming "
            "the commit to merge, and must resolve it then."
        )
    return out
