"""The pure half of `batch dispatch` (spec 2026-09-25-triage-batches §3.C, §3.D, §3.E, §3.I).

The brief, the marker comment, the idempotency read of the marker, the
config-freshness rule and the live reservations: judgements and facts in,
text or answers out. The runner, the adapter and the checkout are the command
layer's (`fr.commands.triage_batch_cmd`); nothing here imports `fr_dispatch`,
runs a process or calls a forge.
"""

from __future__ import annotations

import shlex
from collections.abc import Iterable, Sequence

import yaml
from pydantic import ValidationError

from fr.triage.batch import (
    batch_branch,
    batch_repo,
    derive_batch_stage,
    last_dispatch,
    latest_marker,
    recorded_branch,
)
from fr.triage.errors import TriageError
from fr.triage.model import (
    Batch,
    Facts,
    Judgements,
    TriageConfig,
    batch_marker,
    parse_triage_config,
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
) -> str:
    """The launch brief (§3.C step 3): engine-owned, deterministic text.

    The same judgements and facts always give the same bytes. *closing_refs*
    come from the adapter (`GhClient.closing_ref`), one per member in member
    order, so the brief never hardcodes one forge's closing syntax.
    """
    debug = batch.skill == "debug"
    slash = "/fr-debugging" if debug else "/fr-goal"
    titles = {i.key: i.title for i in facts.issues}
    lines = [
        f"{slash} {batch.title}",
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
    committed = "the failing test is committed" if debug else "the spec is committed"
    lines += [
        "",
        "## Delivery rules",
        f"- Work on branch `{batch_branch(batch)}`.",
        f"- Open a draft PR as soon as {committed}. Its body contains these "
        "lines, one per member, so every member closes when it merges:",
        *(f"  {ref}" for ref in closing_refs),
    ]
    if reserved_version is not None:
        lines.append(
            # Provisional (super-fr#646): `live_reservations` sees only this
            # triage scope's batches, so another scope may hold the same number;
            # merge reconcile (`batch_merge`) renumbers, so nothing bad ships.
            f"- Bump the version to `{reserved_version}` (provisional: reserved within "
            "this triage only, and the merge renumbers it if another batch lands "
            "that number first)."
        )
    lines += [
        "- Do not name any member issue as a phase `tracking_issue` in the plan: the "
        "bridge would then own that issue's `fr:` labels.",
    ]
    if debug:
        lines += [
            "",
            "## Debugging rules",
            "- If investigation cannot form a confident single hypothesis, stop and ask; "
            "don't guess.",
            "- After three failed fixes, stop and ask before a fourth attempt.",
            "- These members were batched as ONE root cause; if investigation finds more "
            "than one, stop and ask before fixing any.",
        ]
    return "\n".join(lines) + "\n"


def conflict_brief(
    batch: Batch,
    *,
    pr: int | None,
    head: str,
    paths: Sequence[str],
    branch: str,
    base: str,
    mirrors: Sequence[Sequence[str]],
) -> str:
    """The conflict hand-back brief (spec 2026-10-06-verification-strategies §G, R20):
    the batch, its PR, the head and the paths merge refused, then the six steps. The
    repo's `.fr/triage.yaml` `mirrors:` commands, when declared, are step 4's."""
    where = f"PR #{pr}" if pr is not None else "its PR"
    regenerate = "4. Regenerate generated mirrors instead of hand-resolving them"
    if mirrors:
        commands = "; ".join(f"`{shlex.join(argv)}`" for argv in mirrors)
        regenerate += f": run {commands}, then stage what they wrote."
    else:
        regenerate += " (rerun whatever generates them), then stage what they wrote."
    return "\n".join(
        [
            f"Merge conflict on batch {batch.id} ({batch.title}): {where} on {branch}, at "
            f"head {head}, conflicts with {base} in a change the wave driver will not "
            f"resolve: {', '.join(paths)}.",
            f"Resolve it on {branch} itself, in these six steps:",
            f"1. Enter the batch's workspace first: `fr isolation up --branch {branch}`. "
            f"{branch} is checked out there, not in the clone you may have started in; "
            "on an existing workspace the command resumes it, and a session already in "
            "that workspace has nothing to do. Every later step runs in the workspace.",
            f"2. `git fetch origin && git merge {base}` into {branch}. Do not rebase and "
            "do not force-push: the PR's history stays as it is.",
            f"3. Resolve the conflicted paths: {', '.join(paths)}.",
            regenerate,
            "5. Run the test suite, and fix what the merge broke.",
            f"6. Commit the merge and `git push origin {branch}`. The driver merges the PR "
            "once its checks are green.",
        ]
    )


def dispatch_comment(batch: Batch, item_id: str, key: str) -> str:
    """Member *key*'s comment (§3.E): marker first, then plain words naming the
    other members. No handle, no host, no local detail."""
    others = [k for k in batch.ids if k != key]
    company = f", with {', '.join(others)}" if others else ""
    return (
        f"{batch_marker(item_id)}\n"
        f"Dispatched as batch `{batch.id}` ({batch.title}){company}. "
        f"Branch `{recorded_branch(batch)}`."
    )


def dispatched_already(comments: Iterable[dict[str, object]], item_id: str) -> bool:
    """True when a dispatch marker for *item_id* is newer than its latest
    withdrawal (comments oldest first).

    Makes the §3.E comment idempotent under `--repair`, while a redispatch after
    a cancel still posts a NEW marker: the old one predates the withdrawal
    (decision p2-withdrawn-marker).
    """
    return latest_marker(comments, item_id) == "dispatch"


def check_config_fresh(
    collected: TriageConfig | None, on_origin: str | None, *, lenient: bool = False
) -> None:
    """Refuse a collected `.fr/triage.yaml` that is not the one on
    `origin/<default>` now (§3.I).

    Identity, not time (review r3-f13): the file's text at the default branch
    is parsed and compared with what `collect` recorded. Committer dates are
    set by whoever commits (a rebase, a skewed clock, a cherry-pick) and say
    nothing about which content was read; the content itself does. *collected*
    is None when collect found no file, *on_origin* when there is none now.
    *lenient* is the wave driver's (gh#998): a top-level key this `fr` does not
    know is dropped from both sides of the comparison, as its collect dropped it.
    """
    try:
        current = (
            parse_triage_config(yaml.safe_load(on_origin) or {}, lenient=lenient)[0]
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
