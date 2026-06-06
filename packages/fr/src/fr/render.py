"""Pure projection: (Plan, GhState) -> RenderedState.

The renderer never performs I/O. Same inputs always produce the same
output. Drift detection is `actual == rendered`-comparison-free for
consumers because everything is hashable+frozen.

Projection rules implemented here come straight from the spec:
  docs/superpowers/specs/2026-05-06-vk-rebuild-state-machine-design.md
  §"Rendering"
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from fr._urls import is_cross_repo_spec
from fr._urls import issue_number as _issue_number_from_url
from fr.labels import (
    FR_BLOCKED,
    FR_IN_PROGRESS,
    FR_PR_READY,
    FR_READY,
    FR_SYNCED,
    MANUAL,
    LabelDef,
    is_queued,
    phase_label,
    plan_label,
    runner_label,
    spec_label,
)
from fr.parser import Plan
from fr.states import (
    GhState,
    PhaseObservation,
    RenderedIssue,
    RenderedState,
    Warning,
)
from fr.types import PhaseDoc


def _spec_slug(spec_path: str | None) -> str | None:
    """Strip the `.md` suffix from the spec path; return None if unset.

    Date-prefix stripping happens inside `labels.spec_label` (via
    `normalize_label_slug`) — stripping it here too used to leave a
    leading dash on `YYYY-MM-DD--<layer>--…` slugs (`spec:-auto--…`)
    because the local regex consumed exactly one trailing dash.
    """
    if not spec_path:
        return None
    return Path(spec_path).stem


def _deps_satisfied(phase: PhaseDoc, plan: Plan, observed: GhState) -> bool:
    """True iff every phase in `phase.depends_on` is complete."""
    phase_by_number = {p.phase.number: p for p in plan.phases}
    for dep_n in phase.phase.depends_on:
        dep_phase = phase_by_number.get(dep_n)
        if dep_phase is None:
            return False
        dep_obs = observed.phases.get(dep_n)
        if not _phase_complete(dep_phase, dep_obs):
            return False
    return True


def _lifecycle_label(
    phase: PhaseDoc,
    obs: PhaseObservation | None,
    plan: Plan,
    observed: GhState,
) -> LabelDef | None:
    """Compute the single lifecycle LabelDef for a phase.

    Returns None when the Issue should be closed (phase complete).
    """
    if _phase_complete(phase, obs):
        return None  # closed; no lifecycle label
    if phase.phase.tag == "manual":
        return MANUAL
    if not _deps_satisfied(phase, plan, observed):
        return FR_BLOCKED
    if obs is None:
        return FR_READY
    has_open_pr_nondraft = any(
        pr.state == "OPEN" and not pr.draft and not pr.merged for pr in obs.linked_prs
    )
    if has_open_pr_nondraft:
        return FR_PR_READY
    has_assignee_or_draft_pr = bool(obs.issue_assignees) or any(
        pr.state == "OPEN" and pr.draft for pr in obs.linked_prs
    )
    if has_assignee_or_draft_pr:
        return FR_IN_PROGRESS
    return FR_READY


def _phase_complete(phase: PhaseDoc, obs: PhaseObservation | None) -> bool:
    """Per spec rules.

    - Manual phase: requires `completion.at` AND `completion.note`. Steps optional.
    - Agentic phase: requires `completion.at` AND a merged PR observed AND no
      open linked PR remains. BOTH signals required:
        - `completion.at` is the agent's "I'm done" signal
        - merged PR is the operator's "I accepted the work" signal
      Either alone is insufficient. Setting `completion.at` without a merged
      PR keeps the Issue OPEN (renderer projects pr-ready when a PR exists,
      vk-ready otherwise) so the work surfaces correctly until merge.

      Exception (#246): once the Issue is already CLOSED and `completion.at`
      is set with no open linked PR, treat the phase as complete even without
      a GitHub-linked merged PR. Inline-executed plans (direct commits) and
      PRs that didn't use a closing keyword never produce an observable merged
      PR, so the merged-PR signal would be permanently unsatisfiable and apply
      would reopen the operator's deliberately-closed Issue on every run. This
      cannot resurrect an OPEN issue — it only honours a close that already
      happened, so it does not reintroduce the premature-close bug below.

    Pre-2026-05-18 behavior was `completion.at OR (all_steps_ticked + merged PR)`
    — the OR shortcut closed Issues prematurely when an agent set
    `completion.at` before opening its PR. See 2026-05-18 incident
    (multiple VK-spawned agents skipped `fr apply --yes` to avoid the
    premature close).
    """
    completion = phase.state.completion

    if phase.phase.tag == "manual":
        return completion.at is not None and completion.note is not None

    if completion.at is None:
        return False
    if obs is None:
        return False
    has_merged_pr = any(pr.merged for pr in obs.linked_prs)
    has_open_pr = any(pr.state == "OPEN" and not pr.merged for pr in obs.linked_prs)
    if has_merged_pr and not has_open_pr:
        return True
    # Respect a deliberate operator close for terminal work (#246).
    return obs.issue_state == "CLOSED" and not has_open_pr


def plan_locally_complete(phase: PhaseDoc) -> bool:
    """LOCAL-only completion signal: completion.at set, OR steps non-empty
    and all ticked ('x' or '-'). No gh observation involved.

    Deliberately weaker than `_phase_complete`, which encodes "operator
    accepted the work" via merged-PR evidence and must keep requiring it
    (2026-05-18 premature-close incident). This predicate answers a
    different question — "does the plan ITSELF claim this phase is done?" —
    and exists for surfaces that run before any Issue exists: the dispatch
    guard in `vk.diff.diff` (2026-06-05 stale-plan dispatch postmortem),
    the `_drift_warnings` never-dispatched warning, the `fr spec status`
    roll-up, and the `fr archive` gate.

    Tag-agnostic by design: unlike `_phase_complete`, a manual phase with
    `completion.at` but no `completion.note` still counts — for a dispatch
    guard, any completion claim is reason enough to refuse creating new
    work.
    """
    if phase.state.completion.at is not None:
        return True
    steps = phase.state.steps
    return bool(steps) and all(s.state in ("x", "-") for s in steps.values())


def archive_gate(plan: Plan, observed: GhState) -> tuple[str, ...]:
    """Per-phase blockers for `fr archive`; empty tuple = plan may archive.

    A phase clears the gate when it is `_phase_complete` (gh agrees the
    work landed) OR it was never dispatched and `plan_locally_complete`
    (the bookmarks shape: ticked but no Issue ever existed — dispatch
    refuses it, so archive is its terminal state). Broader than
    `RenderedState.archive_decision` (strict all-`_phase_complete`), which
    this gate consumes for the dispatched arm.

    Shared by `fr archive` (the actual gate), and `fr apply` / `fr status`
    (the "plan complete — run fr archive" nudge) so the three surfaces
    can't disagree.
    """
    blockers: list[str] = []
    for phase in plan.phases:
        n = phase.phase.number
        obs = observed.phases.get(n)
        if _phase_complete(phase, obs):
            continue
        if phase.phase.tracking_issue is None and plan_locally_complete(phase):
            continue
        steps = phase.state.steps
        ticked = sum(1 for s in steps.values() if s.state in ("x", "-"))
        state = "undispatched" if phase.phase.tracking_issue is None else "dispatched"
        blockers.append(f"Phase {n}: {ticked}/{len(steps)} steps ticked, {state} — not complete")
    return tuple(blockers)


def spec_url(plan: Plan) -> str | None:
    """GitHub blob URL for `plan.meta.spec`; None when unset.

    Same-repo specs resolve against `target_repo`; cross-repo
    `owner/repo:path` notation (see `vk._urls.is_cross_repo_spec`)
    resolves against the named repo. `main` is the deliberate branch
    choice — it matches the bridge's hardcoded pull convention and the
    dispatch reachability gate ("plan and spec must be on origin/HEAD").
    """
    spec = plan.meta.spec
    if not spec:
        return None
    if is_cross_repo_spec(spec):
        repo, path = spec.split(":", 1)
    else:
        # plan.spec_path is the parse-time lifecycle resolution
        # (2026-06-06 spec-path-repair): the link follows the spec to
        # implemented/specs/, and slug-form refs become real paths.
        repo, path = plan.meta.target_repo, plan.spec_path or spec
    return f"https://github.com/{repo}/blob/main/{path}"


_BACKTICK_RUN_RE = re.compile(r"`+")

# Enrichment budget. GitHub caps Issue bodies at 65,536 chars; the static
# body template is well under 5k, so capping the enrichment block at 55k
# keeps the assembled body comfortably below 60k. Truncation inside the
# budget is deterministic (same inputs → same output) so re-renders
# converge and the body diff never churns.
_ENRICHMENT_BUDGET = 55_000


def _fence_for(content: str) -> str:
    """Code fence guaranteed to wrap `content`: longest backtick run + 1, min 3.

    Phase yaml legitimately contains triple-backtick fences inside step
    text — a fixed ``` fence would terminate early on GitHub.
    """
    longest = max((len(m.group()) for m in _BACKTICK_RUN_RE.finditer(content)), default=0)
    return "`" * max(3, longest + 1)


def _truncated(text: str, limit: int, pointer: str) -> str:
    """Clamp `text` to AT MOST `limit` chars, deterministically.

    Appends a pointer marker when there's room for one; hard-cuts when
    `limit` is too tight for the marker itself (the result is never
    longer than `limit`).
    """
    if len(text) <= limit:
        return text
    marker = f"\n… (truncated — see {pointer} in the repo)"
    if limit <= len(marker):
        return text[:limit]
    return text[: limit - len(marker)] + marker


def _prose_section(prose: str) -> str:
    return f"## Plan prose\n\n<details>\n<summary>📜 _prose.md</summary>\n\n{prose}\n\n</details>\n"


def _phase_section(raw: str, fname: str) -> str:
    fence = _fence_for(raw)
    return (
        f"## Phase document\n\n<details>\n<summary>🧾 {fname}</summary>\n\n"
        f"{fence}yaml\n{raw}\n{fence}\n\n</details>\n"
    )


def enrichment_block(plan: Plan, phase: PhaseDoc) -> str:
    """Spec/prose/phase-yaml context block shared by Issue bodies + VK cards.

    Embeds the plan's `_prose.md` and the phase's raw `NN.yaml` (both
    carried on `Plan` by `parse()`) in collapsed `<details>` blocks.
    Missing inputs degrade gracefully: absent prose or phase text just
    omits that section; both absent returns "". Oversized content is
    truncated deterministically — yaml first (it has a canonical in-repo
    home), then prose — so the RETURNED block never exceeds
    `_ENRICHMENT_BUDGET`. Content is rstripped once at entry so the
    truncation arithmetic is exact (each `_truncated` char removed is a
    block char removed); the budget check runs on the assembled block,
    join separator and section overhead included.
    """
    prose = (plan.prose or "").rstrip() or None
    raw = (plan.phase_texts.get(phase.phase.number) or "").rstrip() or None
    fname = f"{phase.phase.number:02d}.yaml"

    def _assemble(p: str | None, y: str | None) -> str:
        sections = []
        if p:
            sections.append(_prose_section(p))
        if y:
            sections.append(_phase_section(y, fname))
        return "\n".join(sections)

    block = _assemble(prose, raw)
    if len(block) > _ENRICHMENT_BUDGET and raw:
        yaml_limit = max(0, len(raw) - (len(block) - _ENRICHMENT_BUDGET))
        raw = _truncated(raw, yaml_limit, f"{plan.repo_relative_dir}/{fname}") or None
        block = _assemble(prose, raw)
    if len(block) > _ENRICHMENT_BUDGET and prose:
        prose_limit = max(0, len(prose) - (len(block) - _ENRICHMENT_BUDGET))
        prose = _truncated(prose, prose_limit, f"{plan.repo_relative_dir}/_prose.md") or None
        block = _assemble(prose, raw)
    return block


def render_body(
    phase: PhaseDoc,
    plan: Plan,
    *,
    phase_to_issue: dict[int, int] | None = None,
    phase_to_repo: dict[int, str] | None = None,
) -> str:
    """Body template: tracking header, instruction, deps, enrichment block.

    NOT static through close (the pre-enrichment doctrine): the body
    embeds the phase's yaml document — including its `state:` block — so
    it re-renders as steps tick and `apply()` syncs it via
    `IssueBodyChange`. Deliberate: the projection keeps the GitHub view
    of progress honest with zero new sync machinery.

    Uses `plan.repo_relative_dir` (NOT `plan.dir`) for the `📋 Plan:`
    line so the body doesn't leak the dispatcher's absolute filesystem
    path — the body is consumed by humans + tooling in every clone of
    the repo, including pod-side agents on different filesystems.

    `phase_to_issue` maps phase numbers to the predecessor's tracking
    Issue number (int). When set, `- Blocked by #N` uses the Issue
    number, not the phase number — which is what the bridge actually
    parses. `phase_to_repo` is forward-compat for cross-repo deps; v2
    doesn't dispatch cross-repo today, but the bridge already accepts
    `owner/repo#N`, so making the renderer symmetric now avoids a
    second rework.

    Both default to None (treated as empty dict) — callers that
    haven't been updated still get the phase-number form, which is
    obviously broken at a glance, so the operator notices and
    re-dispatches.

    Deliberately does NOT carry a "include `Closes #N` to auto-close"
    hint. v2 handles auto-close via the renderer projection
    (`apply()` closes Issues when the phase becomes Complete) so the
    hint that v1's body needed is structurally unnecessary now.
    """
    total = len(plan.phases)
    repo = plan.meta.target_repo
    url = spec_url(plan)
    spec = f"[{plan.meta.spec}]({url})" if url else (plan.meta.spec or "—")
    plan_path = plan.repo_relative_dir
    tracking = (
        f"📦 Repo:   {repo}\n"
        f"📋 Plan:   {plan_path}\n"
        f"📐 Spec:   {spec}\n"
        f"🎯 Phase:  {phase.phase.number}/{total} — {phase.phase.title} [{phase.phase.tag}]\n"
        f"🔗 Issue:  {phase.phase.tracking_issue or '(assigned on create)'}\n"
    )

    def _dep_ref(n: int) -> str:
        issue_n = (phase_to_issue or {}).get(n)
        if issue_n is None:
            # Predecessor hasn't been dispatched yet AND isn't in this
            # apply's created_issues. Fall back to the phase-number form —
            # the operator will see the broken ref and re-dispatch.
            return f"#{n}"
        dep_repo = (phase_to_repo or {}).get(n)
        if dep_repo and dep_repo != plan.meta.target_repo:
            return f"{dep_repo}#{issue_n}"
        return f"#{issue_n}"

    if phase.phase.depends_on:
        deps_block = "\n".join(f"- Blocked by {_dep_ref(n)}" for n in phase.phase.depends_on)
    else:
        deps_block = "None — no blocking phases."
    enrichment = enrichment_block(plan, phase)
    return (
        f"{tracking}"
        f"\n---\n\n"
        f"## Instruction\n\n"
        f"Use super-fr:fr-execute to implement Phase "
        f"{phase.phase.number} of this plan.\n\n"
        f"## Workspace\n\n"
        f"Repos: {repo}\n\n"
        f"## Dependencies\n\n"
        f"{deps_block}\n" + (f"\n{enrichment}" if enrichment else "")
    )


def _phase_labels(phase: PhaseDoc, plan: Plan) -> frozenset[LabelDef]:
    """Taxonomy LabelDef set for a phase (factory-resolved, registry-colored)."""
    labels: set[LabelDef] = {
        plan_label(plan.meta.plan),
        phase_label(phase.phase.number),
    }
    spec_slug = _spec_slug(plan.meta.spec)
    if spec_slug:
        labels.add(spec_label(spec_slug))
    return frozenset(labels)


def _drift_warnings(plan: Plan, observed: GhState) -> tuple[Warning, ...]:
    """Surface non-blocking drift signals for operator review.

    Severity levels:
      - "info":  benign — agent forgot a checkbox tick
      - "warn":  ambiguous — operator action may be needed
      - "error": something is wrong — Issue closed without plan agreement
    """
    warnings: list[Warning] = []
    for phase in plan.phases:
        n = phase.phase.number
        obs = observed.phases.get(n)
        steps = phase.state.steps
        all_ticked = bool(steps) and all(s.state in ("x", "-") for s in steps.values())
        if obs is None:
            # Undispatched phase. Pre-2026-06-05 this `continue` also
            # swallowed the locally-complete case, so a fully-ticked,
            # never-dispatched plan produced ZERO warnings while apply
            # created spurious Issues (bookmarks incident). The PR-based
            # checks below still need an observation — only this signal
            # is observable without one.
            if plan_locally_complete(phase):
                ticked = sum(1 for s in steps.values() if s.state in ("x", "-"))
                warnings.append(
                    Warning(
                        severity="warn",
                        message=(
                            f"Phase {n}: {ticked}/{len(steps)} steps ticked but never "
                            f"dispatched — dispatch would be refused "
                            f"(fr archive if this plan is done)."
                        ),
                    )
                )
            continue
        has_merged_pr = any(pr.merged for pr in obs.linked_prs)
        # Steps all ticked but no merged PR (operator may have ticked prematurely)
        if all_ticked and not has_merged_pr and obs.linked_prs:
            warnings.append(
                Warning(
                    severity="warn",
                    message=(
                        f"Phase {n}: all steps ticked but no merged PR observed — "
                        f"operator may have ticked prematurely."
                    ),
                )
            )
        # Merged PR but some steps still unticked (agent forgot to tick)
        if has_merged_pr and not all_ticked:
            warnings.append(
                Warning(
                    severity="info",
                    message=(
                        f"Phase {n}: PR merged but steps unticked — "
                        f"agent may have forgotten to tick them."
                    ),
                )
            )
        # Issue closed but plan says incomplete (someone closed it manually)
        if obs.issue_state == "CLOSED" and not _phase_complete(phase, obs):
            warnings.append(
                Warning(
                    severity="error",
                    message=(
                        f"Phase {n}: Issue closed but plan is incomplete — reconciliation needed."
                    ),
                )
            )
    return tuple(warnings)


def build_phase_to_issue(
    plan: Plan, created_issues: dict[int, str] | None = None
) -> dict[int, int]:
    """Map phase number → tracking-issue number.

    Pulls from each phase's persisted `tracking_issue`. If `created_issues`
    is supplied (the in-flight `phase_number → issue_url` dict returned by
    `apply()`), its entries take precedence — that's how `apply()` can
    re-render a dependent phase's body after its predecessor's
    `IssueCreate` lands in the same run.
    """
    result: dict[int, int] = {}
    for ph in plan.phases:
        n = _issue_number_from_url(ph.phase.tracking_issue)
        if n is not None:
            result[ph.phase.number] = n
    if created_issues:
        for phase_n, url in created_issues.items():
            n = _issue_number_from_url(url)
            if n is not None:
                result[phase_n] = n
    return result


def render(
    plan: Plan,
    observed: GhState,
    *,
    created_issues: dict[int, str] | None = None,
    queue_runner: str | None = None,
) -> RenderedState:
    """Project (plan, observed) → RenderedState. Pure function.

    `created_issues` is the in-flight `phase_number → issue_url` map from
    a running `apply()`. When set, dependent phases' bodies render with
    the now-known Issue numbers instead of the phase-number fallback.

    `queue_runner` is the v3 dispatch intent (`fr apply --to <runner>`):
    when set, every phase is projected with the queue lifecycle and a
    `runner:<name>` attribute. When None (the tracking-only default),
    queue lifecycle is projected ONLY for phases whose OBSERVED labels
    say they already entered a queue (`labels.is_queued`) — the runner
    choice is recorded on the Issue, never in the plan (super-fr split
    design, "derive, don't store").
    """
    phase_to_issue = build_phase_to_issue(plan, created_issues)
    # phase_to_repo is forward-compat for cross-repo deps. v2 is
    # single-target_repo today, so the map is always empty in practice.
    phase_to_repo: dict[int, str] = {}
    issues: dict[int, RenderedIssue] = {}
    for phase in plan.phases:
        n = phase.phase.number
        obs = observed.phases.get(n)
        labels: set[LabelDef] = set(_phase_labels(phase, plan))
        observed_names = obs.issue_labels if obs is not None else frozenset()
        phase_queued = queue_runner is not None or is_queued(observed_names)
        if phase_queued:
            lifecycle = _lifecycle_label(phase, obs, plan, observed)
            if lifecycle is not None:
                labels.add(lifecycle)
            # Preserve the runner attribution: the explicit --to choice, or
            # whatever runner:<name> the Issue already carries.
            if queue_runner is not None:
                labels.add(runner_label(queue_runner))
            else:
                for name in observed_names:
                    if name.startswith("runner:"):
                        labels.add(runner_label(name.removeprefix("runner:")))
        elif phase.phase.tag == "manual" and not _phase_complete(phase, obs):
            # `manual` is a routing attribute, not queue lifecycle — it
            # stays on tracking-only issues so humans can filter their work.
            labels.add(MANUAL)
        # `fr:synced` is protocol-owned (set after the runner accepts): the
        # renderer doesn't initiate it, but must carry it forward so
        # diff() sees no drift.
        if FR_SYNCED.name in observed_names:
            labels.add(FR_SYNCED)
        state: Literal["OPEN", "CLOSED"] = "CLOSED" if _phase_complete(phase, obs) else "OPEN"
        issues[n] = RenderedIssue(
            body=render_body(
                phase, plan, phase_to_issue=phase_to_issue, phase_to_repo=phase_to_repo
            ),
            labels=frozenset(labels),
            state=state,
        )
    archive = all(_phase_complete(p, observed.phases.get(p.phase.number)) for p in plan.phases)
    return RenderedState(
        issue_per_phase=issues,
        archive_decision=archive,
        warnings=_drift_warnings(plan, observed),
    )
