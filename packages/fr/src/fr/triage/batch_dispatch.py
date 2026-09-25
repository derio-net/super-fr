"""The pure half of `batch dispatch` (spec 2026-09-25-triage-batches §3.C, §3.D, §3.E, §3.I).

The brief, the marker comment, the idempotency read of the marker, the
config-freshness rule and the live reservations: judgements and facts in,
text or answers out. The runner, the adapter and the checkout are the command
layer's (`fr.commands.triage_batch_cmd`); nothing here imports `fr_dispatch`,
runs a process or calls a forge.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import yaml
from pydantic import ValidationError

from fr.triage.batch import (
    batch_branch,
    batch_repo,
    derive_batch_stage,
    last_dispatch,
    latest_marker,
)
from fr.triage.errors import TriageError
from fr.triage.model import (
    Batch,
    Facts,
    Judgements,
    TriageConfig,
    batch_marker,
)

# Stages whose reservation still stands: the run was briefed with it and has
# not merged or been given up (§3.D "every live reservation").
LIVE_STAGES = frozenset({"dispatched", "pr-open"})
# `dispatch --yes` may start a batch only from these (§3.C step 6.1).
DISPATCHABLE = frozenset({"proposed", "cancelled", "abandoned"})

TRIAGE_CONFIG_PATH = ".fr/triage.yaml"


def render_brief(
    batch: Batch,
    judgements: Judgements,
    facts: Facts,
    *,
    repo: str,
    closing_refs: Sequence[str],
    reserved_version: str | None,
    model: str,
) -> str:
    """The launch brief (§3.C step 3): engine-owned, deterministic text.

    The same judgements and facts always give the same bytes. *closing_refs*
    come from the adapter (`GhClient.closing_ref`), one per member in member
    order, so the brief never hardcodes one forge's closing syntax.
    """
    titles = {i.key: i.title for i in facts.issues}
    lines = [
        f"/fr-goal {batch.title}",
        "",
        f"Batch `{batch.id}` of {repo}: {len(batch.ids)} issues, delivered as ONE pull request.",
    ]
    for key in batch.ids:
        j = judgements.issues.get(key)
        lines += ["", f"## {key}: {titles.get(key, '(title not collected)')}"]
        if j is not None and j.detail:
            lines.append(j.detail)
        if j is not None and j.note:
            lines.append(f"Note: {j.note}")
    if batch.rationale:
        lines += ["", "## Why these belong together", batch.rationale]
    lines += [
        "",
        "## Delivery rules",
        f"- Work on branch `{batch_branch(batch.id)}`.",
        "- Open a draft PR as soon as the spec is committed. Its body contains these "
        "lines, one per member, so every member closes when it merges:",
        *(f"  {ref}" for ref in closing_refs),
    ]
    if reserved_version is not None:
        lines.append(
            f"- Bump the version to `{reserved_version}` (reserved for this batch; "
            "do not pick another number)."
        )
    lines += [
        f"- Use `{model}` for every subagent and every model tier.",
        "- Do not name any member issue as a phase `tracking_issue` in the plan: the "
        "bridge would then own that issue's `fr:` labels.",
    ]
    return "\n".join(lines) + "\n"


def dispatch_comment(batch: Batch, item_id: str, key: str) -> str:
    """Member *key*'s comment (§3.E): marker first, then plain words naming the
    other members. No handle, no host, no local detail."""
    others = [k for k in batch.ids if k != key]
    company = f", with {', '.join(others)}" if others else ""
    return (
        f"{batch_marker(item_id)}\n"
        f"Dispatched as batch `{batch.id}` ({batch.title}){company}. "
        f"Branch `{batch_branch(batch.id)}`."
    )


def dispatched_already(comments: Iterable[dict[str, object]], item_id: str) -> bool:
    """True when a dispatch marker for *item_id* is newer than its latest
    withdrawal (comments oldest first).

    Makes the §3.E comment idempotent under `--repair`, while a redispatch after
    a cancel still posts a NEW marker: the old one predates the withdrawal
    (decision p2-withdrawn-marker).
    """
    return latest_marker(comments, item_id) == "dispatch"


def check_config_fresh(collected: TriageConfig | None, on_origin: str | None) -> None:
    """Refuse a collected `.fr/triage.yaml` that is not the one on
    `origin/<default>` now (§3.I).

    Identity, not time (review r3-f13): the file's text at the default branch
    is parsed and compared with what `collect` recorded. Committer dates are
    set by whoever commits (a rebase, a skewed clock, a cherry-pick) and say
    nothing about which content was read; the content itself does. *collected*
    is None when collect found no file, *on_origin* when there is none now.
    """
    try:
        current = (
            TriageConfig.model_validate(yaml.safe_load(on_origin) or {})
            if on_origin is not None
            else None
        )
    except (yaml.YAMLError, ValidationError) as exc:
        raise TriageError(
            f"{TRIAGE_CONFIG_PATH} on the default branch is not valid triage config: {exc}"
        ) from exc

    def _shape(c: TriageConfig | None) -> object:  # values, not pydantic's fields-set
        return c.model_dump(by_alias=True) if c is not None else None

    if _shape(current) != _shape(collected):
        raise TriageError(
            f"the collected {TRIAGE_CONFIG_PATH} is not the one on the default branch now; "
            "re-collect with `fr triage collect` first"
        )


def live_reservations(batches: Sequence[Batch], facts: Facts, repo: str, *, skip: str) -> list[str]:
    """Reserved versions of the repo's other batches still at dispatched / pr-open."""
    out: list[str] = []
    for b in batches:
        if b.id == skip or batch_repo(b, facts) != repo:
            continue
        event = last_dispatch(b)
        if event and event.reserved_version and derive_batch_stage(b, facts) in LIVE_STAGES:
            out.append(event.reserved_version)
    return out
