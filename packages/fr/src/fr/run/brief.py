"""The dispatch briefs, the dispatch record helpers and their refusal texts (spec
2026-11-27-run-verdict R6, R10).

What `fr run advance` hands a harness for a `kind: agent` step (`build_brief`) or one unit of a
fan-out (`build_member_brief`), the tier and binding helpers behind it, the helpers that open,
close and claim a unit's dispatch record, and the texts of the refusals around a dispatch.
Engine code: a refusal is a `RunRefusal`, a warning goes to the `warn` callable the command
passes, and nothing here prints (`tests/unit/test_run_writes_layering.py`). A function that
once resolved the repository root itself takes `repo_root`, which its caller already holds.
"""

from __future__ import annotations

import os
import re
import shlex
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from rich.markup import escape

import fr.bindings
from fr.artifacts.paths import emitted_path
from fr.bindings.health import BindingHealth, check_bindings
from fr.bindings.probe import default_probe_cache
from fr.bindings.wording import proposal_text
from fr.harness.detect import detect_harness
from fr.harness.long_commands import long_command_rule
from fr.harness.model import HarnessError
from fr.models import default_models_path, load_models, repo_models_path
from fr.run import units
from fr.run.evidence.lenses import lens_set_or_refuse
from fr.run.model import DispatchOutcome, RunState, RunStateError, StepRecord
from fr.run.steps import emitted_plan, item_phase, phase_tier, with_step
from fr.run.units import UnitAttempt
from fr.run.verdict import RunRefusal, Say, Warn
from fr.run.writes import now
from fr.types import PHASE_TIERS
from fr.workflow.artifacts import DERIVED_EVIDENCE, REPO_TRACKED_ARTIFACTS
from fr.workflow.model import Step

PHASE_EXECUTOR_AGENT = "super-fr:fr-phase-executor"

TEMPLATE_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.\-]+)\s*\}\}")


def template_context(state: RunState, repo_root: Path | None = None) -> dict[str, str]:
    """`{{ run.* }}` and `{{ artifacts.* }}` for a `kind: cli` step, which runs in the
    product checkout. Under quiet or stealth a repo-tracked artifact (`spec`, `plan`) is
    not there, so it is given as its absolute path below the artifact root; under `repo`
    the recorded relative path already names it from the checkout."""
    from fr.artifacts.paths import outside_repo

    placed = repo_root is not None and outside_repo(repo_root) is not None
    ctx = {"run.id": state.run, "run.branch": state.branch}
    for record in state.steps.values():
        if record.emitted:
            for name, value in record.emitted.items():
                if placed and repo_root is not None and name in REPO_TRACKED_ARTIFACTS:
                    value = str(emitted_path(repo_root, value))
                ctx[f"artifacts.{name}"] = value
    return ctx


def render_template(text: str, context: Mapping[str, str], *, quote: bool) -> str:
    """Substitute `{{ ... }}` from `context`.

    `quote=True` shell-quotes every substituted value and is mandatory for
    anything handed to a shell (review fix r2-f3). The manifest itself is
    operator-authored, but `{{ artifacts.* }}` values are not: they arrive via
    `fr run resolve --emitted name=path`, i.e. from whatever a dispatched
    agent reports. The shipped `plan-review` step is `fr plan self-review
    {{ artifacts.plan }}`, so an emitted path containing `;` or backticks was
    a command-injection seam straight through `shell=True`. Quoting at the
    substitution boundary keeps the manifest's own shell syntax (pipes,
    redirects, `&&`) working while making an interpolated value inert data.
    """

    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in context:
            raise RunStateError(f"unresolved template variable: {{{{ {key} }}}}")
        value = context[key]
        return shlex.quote(value) if quote else value

    return TEMPLATE_RE.sub(repl, text)


def build_brief(step: Step, state: RunState, *, repo_root: Path) -> dict[str, Any]:
    """The dispatch brief for a `kind: agent` step — everything the harness
    needs to actually run it, and nothing fr itself executes.

    Phase 11 wires `fr-goal` onto `fr run`; it must produce/consume this
    same shape, so its keys are deliberately exhaustive of `Step`'s
    agent-relevant fields rather than a subset convenient for today's tests
    — pinned by deriving the expected key set from `Step.model_fields` in
    `test_run_cli.py`, so a future `Step` field cannot be silently omitted.

    Exhaustive means every `Step` field except two: `id` (emitted as `step`)
    and `run` (the one cli-only field — `advance` executes it; it is never
    dispatched). `kind` is carried even though a brief is only ever printed
    for an `agent` step, so the brief stays self-describing and the
    exclusion list stays at exactly the two fields that have a reason.
    `for_each` and `gate` were missing until review fix r2-f4, which made
    the brief unable to express `implement`'s whole purpose (one executor
    per phase) or the fact that a step is gated at all. `steps` carries the
    member ids of a grouped `for_each` (empty for a flat step) so the
    harness can see the per-phase loop without re-reading the manifest.
    """
    return {
        "run": state.run,
        "workflow": state.workflow,
        "step": step.id,
        "kind": step.kind,
        "skill": brief_skill(step),
        "agent": step.agent,
        "needs": list(step.needs),
        "emits": list(step.emits),
        "gate": step.gate,
        "tier": step.tier,
        "evidence": caller_evidence(step),
        "for_each": step.for_each,
        "steps": [m.model_dump(exclude_none=True) for m in step.steps],
        # spec 2026-09-25 §5.C.3: the pre-filled step record — for a flat
        # step; a fan-out group's record is per member, in the member brief.
        "record": None if step.steps else record_brief(state, step, repo_root=repo_root),
        "commit_templates": commit_templates_brief(repo_root, state.issue),
        "unbound_tiers": unbound_tiers(repo_root),
        **gated_binding_keys(step, repo_root=repo_root),
        **lens_review_brief(step, state, repo_root=repo_root),
        **tests_brief(repo_root, step),
        **settle_brief(step),
    }


def settle_brief(step: Step) -> dict[str, str]:
    """`settle`, the settle loop's one instruction line, for a step that derives
    `settle` evidence (`deliver`; spec 2026-11-23-pr-readiness-wait R9, R10)."""
    from fr.settle.instructions import DELIVER_LINE

    return {"settle": DELIVER_LINE} if "settle" in step.evidence else {}


def commit_templates_brief(repo_root: Path, issue: int | None) -> dict[str, Any]:
    """The repo's commit subject templates and the run's issue (spec
    2026-11-04-repo-feature-settings R14): what an agent's commit subjects must
    match, `with_issue` when the run records an issue. `fr push` checks them."""
    from fr.settings import load_settings

    commit = load_settings(repo_root).settings.git.commit
    return {
        "use": "with_issue" if issue is not None else "without_issue",
        "with_issue": commit.with_issue,
        "without_issue": commit.without_issue,
        "issue": issue,
    }


def unbound_tiers(repo_root: Path) -> list[str] | None:
    """The phase tiers with no model bound for the harness `advance` runs
    under, in `PHASE_TIERS` order — `None` when no harness is detected (or
    `FR_HARNESS` is invalid, which the gate path reports itself): an empty
    list would read as "every tier is bound". A malformed models.yaml raises,
    as it already did from `orchestrator_model_notice` at the top of every
    `advance` — a broken config is reported, never read as "unbound".

    gh#538: fr-goal's model-per-tier question was gated on a `fr models
    resolve` the orchestrator had to REMEMBER to run, and on a real OpenCode
    run with nothing bound it never ran it. fr answers it in one lookup, so the
    brief states it and the question is triggered by data, not recall."""
    try:
        harness = detect_harness(os.environ)
    except HarnessError:
        return None
    if harness is None:
        return None
    return [t for t in PHASE_TIERS if resolved_model(repo_root, harness, t) is None]


def binding_health(
    repo_root: Path, tiers: list[str] | None = None
) -> tuple[str, list[BindingHealth]] | None:
    """`(harness, report)` for the detected harness's bindings — `None` when no
    harness is detected or it cannot be probed (spec 2026-10-06-model-binding-
    churn R10: only OpenCode can). The ONE place `fr run` reaches
    `check_bindings`: the start notice, the gated brief and the pre-dispatch
    guard all read it, with the 6 h probe cache allowed (R3)."""
    try:
        harness = detect_harness(os.environ)
    except HarnessError:
        return None
    if harness is None:
        return None
    prober = fr.bindings.prober_for(harness)
    if prober is None:
        return None
    report = check_bindings(
        harness,
        load_models(repo_models_path(repo_root)),
        load_models(default_models_path()),
        prober,
        tiers=tiers,
        cache=default_probe_cache(),
    )
    return harness, report


def gated_binding_keys(step: Step, *, repo_root: Path) -> dict[str, list[dict[str, Any]] | None]:
    """The brief's `dead_bindings` and `binding_offers` (R6): lists only for a
    `gate: operator` step on a probed harness — the one place an operator is
    there to answer them (R7) — and `null` everywhere else, so a dispatch
    brief never pays for a probe nobody will act on."""
    health = binding_health(repo_root) if step.gate == "operator" else None
    if health is None:
        return {"dead_bindings": None, "binding_offers": None}
    _, report = health
    dead = [
        {
            "tier": h.tier,
            "model": h.model,
            "verdict": h.verdict,
            "proposal": None
            if h.proposal is None
            else {
                "model": h.proposal.model,
                "rule": h.proposal.rule,
                "price_ratio": h.proposal.price_ratio,
            },
            "reason": h.detail,
        }
        for h in report
        if h.verdict == "dead"
    ]
    offers = [
        {"tier": o.tier, "model": o.model, "offer": o.offer} for h in report for o in h.offers
    ]
    return {"dead_bindings": dead, "binding_offers": offers}


def binding_notice_lines(harness: str, report: list[BindingHealth]) -> list[str]:
    """`fr run start`'s loud lines (R6): one per dead binding, one per offer."""
    lines: list[str] = []
    for h in report:
        if h.verdict == "dead":
            line = f"warning: {harness}/{h.tier} is bound to {h.model}, which is dead ({h.detail})"
            if h.proposal is not None:
                line += f" — proposed: {proposal_text(h.proposal)}"
            elif h.no_choice is not None:
                line += f" — no replacement ({h.no_choice.reason})"
            lines.append(line + "; review with `fr models check`")
        lines.extend(
            f"offer: {harness}/{o.tier} {o.model} → {o.offer} (newer, same family; never "
            f"applied unasked — `fr models set --harness {harness} --tier {o.tier} {o.offer}`)"
            for o in h.offers
        )
    return lines


def caller_evidence(step: Step) -> list[str]:
    """The evidence a brief lists: what the caller passes. A derived name is
    refused from the caller ("not yours to pass"), so listing it sent agents
    straight into that refusal (gh#653)."""
    return [n for n in step.evidence if n not in DERIVED_EVIDENCE]


def record_brief(
    state: RunState,
    step: Step,
    group: Step | None = None,
    item: str | None = None,
    *,
    repo_root: Path,
) -> dict[str, Any] | None:
    """The brief's `record` key — never the reason a brief fails to print."""
    from fr.record.template import record_brief as template_record_brief

    try:
        return template_record_brief(repo_root, state, step, group, item).as_dict()
    except Exception:  # noqa: BLE001 — a brief without a template still dispatches
        return None


def brief_skill(step: Step) -> str | list[str] | None:
    """`skill` as the brief carries it: exactly what the manifest wrote. One
    skill is a string — byte-identical to every brief before the list form —
    and several are a JSON list in the manifest's order, which IS the order to
    load them in."""
    return step.skill if step.skill is None or isinstance(step.skill, str) else list(step.skill)


def effective_tier(step: Step, group: Step | None = None) -> str | None:
    """The tier a unit actually dispatches under: its own `tier:` when set,
    else its group's — `None` when neither has one. `build_member_brief`
    and `open_dispatch`'s `_advance_group` call site both read this ONE
    helper (P2.T1.S3) rather than each re-deriving the fallback, which is
    how the two came to duplicate it in the first place. `group=None` for a
    flat step, which has none to fall back to."""
    if step.tier is not None:
        return step.tier
    return group.tier if group is not None else None


PHASE_TIER_SENTINEL = "from_phase"
"""`Step.tier`'s one non-tier value — the shipped `fr-goal` shape's marker for
"this unit's tier is whatever the plan's phase header says".

`Step.tier` is a free `str`, not `PhaseHeader.tier`'s closed
mechanical/standard/hard Literal, precisely so a shape can say this. The
*brief* passes the sentinel through verbatim, because there it is an
instruction to the harness: look the phase up. A dispatch RECORD cannot do
that — it stores what was actually sent — so `_advance_group` resolves it
first (finding f4). Handing the sentinel straight to `fr models resolve` can
only ever miss, which is how every real fr-goal dispatch came to record
`model: null`."""


def dispatch_tier(repo_root: Path, state: RunState, tier: str | None, phase_n: int) -> str | None:
    """`tier` with `PHASE_TIER_SENTINEL` replaced by phase `phase_n`'s own
    tier — what a dispatch RECORD needs, as opposed to what the brief says.

    An unresolvable sentinel becomes `None`, which `resolved_model` then
    records as an absent model: the spec §4.A rule that nothing is ever
    guessed applies to the sentinel exactly as it does to an unbound tier.

    Resolution itself is `phase_tier`'s, gh#506's function for the same
    job — that PR landed the sentinel fix for the dispatch BRIEF while this
    one landed it for the dispatch RECORD, and one reader of the plan's
    phase header is enough for both."""
    if tier != PHASE_TIER_SENTINEL:
        return tier
    return phase_tier(repo_root, state, phase_n)


def resolved_model(repo_root: Path, harness: str | None, tier: str | None) -> str | None:
    """The model bound to `tier` for `harness`, via `fr.models.resolve` —
    repo config overriding user config, the same rule `fr models resolve`
    itself uses. `None` when there is no tier, no harness, or no binding for
    the pair: an unresolved tier leaves `model` absent rather than guessed
    (spec §4.A / P2.T1.S2).

    `harness` is PASSED IN rather than detected here (finding f8). A tier
    resolves to a model only *for a harness*, so the two belong to the same
    record — detecting it privately meant `open_dispatch` could store a
    model without naming the harness that chose it, which an orchestrator-run
    step (never claimed) would never get filled in afterwards.

    `PHASE_TIER_SENTINEL` is refused here as well as resolved upstream in
    `dispatch_tier`. Callers with no phase in hand — a flat `kind: agent`
    step — have nothing to resolve it against, and without this guard a
    models.yaml that happened to carry a `from_phase:` key would bind it,
    turning a sentinel into a model name by coincidence."""
    if tier is None or tier == PHASE_TIER_SENTINEL or harness is None:
        return None
    from fr.models import default_models_path, load_models, repo_models_path
    from fr.models import resolve as resolve_model

    repo_cfg = load_models(repo_models_path(repo_root))
    user_cfg = load_models(default_models_path())
    return resolve_model(harness, tier, repo_cfg=repo_cfg, user_cfg=user_cfg)


ORCHESTRATOR_ROLE = "orchestrator"
"""The models.yaml key binding the ORCHESTRATOR's model, beside the phase tiers
(`claude-code: {orchestrator: claude-opus-5, standard: …}`). A role, not a
tier: nothing dispatches to it, so it is only ever compared, never resolved
into a dispatch (2026-09-21 debug journal C3)."""


def orchestrator_model_notice(repo_root: Path) -> str | None:
    """A loud line when the orchestrator runs on a model other than the one
    bound to `orchestrator` for this harness — else `None`.

    Record + warn, NEVER block (operator decision, debug journal C3): the
    session model is the operator's `/model` choice and outranks the binding.
    Silent with no binding (no contract was asked for) and silent when the
    running model cannot be observed — an unobservable model is not a mismatch,
    and saying so on every harness without a transcript reader would be noise.
    """
    from fr.run.telemetry import orchestrator_model

    try:
        harness = detect_harness(os.environ)
    except HarnessError:
        # A bad FR_HARNESS is `advance`'s gate path's error to raise (exit 2,
        # naming the variable); a notice must never pre-empt it.
        return None
    bound = resolved_model(repo_root, harness, ORCHESTRATOR_ROLE)
    if bound is None:
        return None
    running = orchestrator_model(os.environ)
    if running is None or running == bound:
        return None
    return (
        f"warning: this run's orchestrator is running on {running}, but models.yaml "
        f"binds the {harness} orchestrator to {bound}. Every non-dispatched step "
        f"(brainstorm, reviews, deliver) runs on the orchestrator's model. Switch "
        f"with `/model` if that was not intended; fr records the model it observes."
    )


def open_dispatch(
    state: RunState,
    step_id: str,
    key: str,
    *,
    agent_type: str | None,
    tier: str | None,
    repo_root: Path,
    at: str | None = None,
) -> RunState:
    """Append a new attempt opening `key`'s hold under `step_id`.

    `at` is the attempt's `dispatched`, taken by the grouped caller BEFORE
    the brief is built. Absent, it is stamped here — right for the flat
    `kind: agent` branch, which saves before it prints the brief.

    Spec §4.B.1: called exactly when `advance` moves a unit to `running` —
    from BOTH `_advance_group`'s write-claim and the flat `kind: agent`
    branch, and only on the actual transition (both call sites already guard
    on that). Never called from `_gate_pending`: a gated step is marked
    `blocked`, not `running`, so nothing was dispatched and there is nothing
    to hold.
    """
    from fr.run.telemetry import SESSION_ID_ENVS, orchestrator_model, run_session

    record = state.steps[step_id]
    # Detected ONCE and both recorded and used (finding f8): the harness is
    # what turns a tier into a model, so a record that carries the model
    # without naming it is not self-describing — and an orchestrator-run
    # step, which nothing ever claims, would never have it filled in later.
    harness = detect_harness(os.environ)
    new_record = units.with_attempt_appended(
        record,
        key,
        UnitAttempt(
            dispatched=at or now(),
            agent_type=agent_type,
            harness=harness,
            # A tier is resolved only for work fr DISPATCHED to a tier. A tier
            # binding answers "which model does a dispatched agent of this tier
            # get"; an attempt with no `agent_type` is the orchestrator running
            # the unit in its own session. Such a member still inherits its
            # group's tier, so resolving it here wrote a model for work that
            # tier never touched — seven false `claude-opus-5` reviews in this
            # repo's own archive. That lesson stands. What changed (2026-09-21
            # debug journal C3) is that the orchestrator's model is no longer
            # invisible: its own transcript names it, so fr records what it
            # OBSERVES there — never a resolution — and `None` when it cannot.
            #
            # For a SUBAGENT attempt the binding is a prediction, so it goes
            # into `bound` beside its `tier` (spec 2026-10-06-cost-evidence
            # §D, R7) and `model` is left for what ran: a `--model` claim, or
            # `observed_model` at resolve. Before run version 9 the binding
            # sat in `model`, which is why "ran" is shown only beside `bound`.
            model=(None if agent_type is not None else orchestrator_model(os.environ)),
            tier=(tier if agent_type is not None else None),
            bound=(resolved_model(repo_root, harness, tier) if agent_type is not None else None),
            # Derived from fr's OWN environment, exactly like `harness` — the
            # agent never reports it (§4.D.1). It is what lets a later session
            # read the RIGHT transcript directory, and what stops a window
            # from being borrowed across sessions. `None` for a harness with
            # no session concept, which reads as "not observable from here"
            # and never as zero. No hostname beside it: a missing session
            # directory already says "elsewhere".
            #
            # `current_session` reads only the key the detected harness OWNS
            # (gh#537): an OpenCode started from a Claude Code shell inherits
            # Claude Code's key, which names a session that never held this
            # unit; OpenCode's own arrives through the super-fr plugin's
            # `shell.env` export (spec 2026-10-02-opencode-observe-2 §B).
            # `run_session` walks a child's id up to the run's. An UNDETECTED
            # harness owns no key (review p1-r1): there `current_session`
            # falls back to Claude Code's, which in gh#537's mixed shell is
            # the inherited, stale one — record nothing, as main did.
            session=(run_session(os.environ) if harness in SESSION_ID_ENVS else None),
        ),
    )
    return with_step(state, step_id, new_record)


def dispatch_needs_open(record: StepRecord, key: str) -> bool:
    """Should `advance` append a fresh `Attempt` for `key`?

    True when nothing has been recorded for it yet, or its last attempt is
    CLOSED (`returned` is not `None`) — an abandoned (`fr run claim
    --abandoned`) or failed-and-retried unit is not currently held, so
    re-dispatching it opens a NEW hold rather than silently leaving the old,
    closed one as the only record. False while the last attempt is still
    OPEN — the unit is currently HELD, which `advance` refuses to dispatch
    over (`_hold_on`, spec §4.C / gh-499) unless `--redispatch` says so.

    This is the ONE notion of "is the last record open?" in the module:
    `held_record` is its read half, and `advance`'s refusal (`_hold_on`),
    `--redispatch`'s abandon and `resolve`'s close all go through the pair
    rather than each re-deriving it.
    """
    return held_record(record, key) is None


def held_record(record: StepRecord, key: str) -> UnitAttempt | None:
    """`key`'s OPEN attempt, or `None` when the unit is free.

    The read half of `dispatch_needs_open` — same predicate, but handing
    back the holder so a caller can name it. Delegates to
    `fr.run.units.open_attempt`, which is where "open = the last attempt,
    unreturned" is decided; this module keeps the name because every comment
    and refusal in it is written in terms of the pair."""
    return units.open_attempt(record, key)


def close_dispatch(record: StepRecord, key: str, outcome: DispatchOutcome) -> StepRecord:
    """Close `key`'s open dispatch: `returned` = now, `outcome` = `outcome`.

    `Attempt` enforces that the two are one fact, so they are written
    in one `model_copy` and never separately. Callers must have established
    that the unit IS held (`held_record` / `_open_dispatch_record`); this
    helper does not re-derive it, so there is still exactly one place that
    decides what "open" means."""
    return units.with_last_attempt_replaced(
        record,
        key,
        units.attempts(record, key)[-1].model_copy(update={"returned": now(), "outcome": outcome}),
    )


def merge_claim(
    open_record: UnitAttempt,
    key: str,
    *,
    agent: str | None,
    harness: str | None,
    model: str | None,
    agent_type: str | None,
    warn: Warn,
) -> UnitAttempt:
    """`open_record` after a claim of `harness`/`model`/`agent_type` (#1110).

    The ONE rule for what a claim does to an open attempt, shared by
    `fr run claim`, `--open-unit` and `fr run resolve`'s late identity. An
    UNCLAIMED attempt (no `agent`) takes the claim's values as given — that is
    how a first claim refines what `advance` pre-filled. A CLAIMED one keeps
    what its first claim recorded: an empty field is filled, an equal value
    (or, for `model`, one in the same `model_family`) is a silent no-op, and
    anything else is kept with a warning, exit 0."""
    from fr.models import model_family

    claimed_by = agent if agent is not None else open_record.agent
    if open_record.agent is None:
        update: dict[str, Any] = {}
        if agent is not None:
            update["agent"] = agent
        for field, value in (("harness", harness), ("model", model), ("agent_type", agent_type)):
            if value is not None:
                update[field] = value
        return open_record.model_copy(update=update)
    update = {}
    for field, value in (("harness", harness), ("model", model), ("agent_type", agent_type)):
        if value is None:
            continue
        recorded = getattr(open_record, field)
        if recorded is None:
            update[field] = value
        elif recorded == value or (
            field == "model" and model_family(recorded) == model_family(value)
        ):
            continue
        else:
            warn(
                Say(
                    f"warning: {key}: {claimed_by} is recorded with {field}={recorded}; keeping "
                    f"it (this claim said {value}). The first claim's identity stands; resolve "
                    "records the model the transcript observed. If the executor was really "
                    "replaced, close it with `fr run claim ... --abandoned` and re-dispatch.",
                    markup=False,
                    soft_wrap=True,
                )
            )
    return open_record.model_copy(update=update) if update else open_record


def claimed_identity(
    open_record: UnitAttempt,
    key: str,
    *,
    agent: str,
    harness: str | None,
    model: str | None,
    agent_type: str | None = None,
    warn: Warn,
) -> UnitAttempt:
    """`open_record` carrying the orchestrator's reported identity, or refuse.

    Shared by `fr run claim` (the eager report) and `fr run resolve`'s late
    fallback (decision d2), so a *second* agent id can never be attached to a
    dispatch by taking the other route. Re-reporting the SAME id is
    idempotent: it fills empty `harness`/`model`/`agent_type` fields only and
    otherwise keeps the first claim's values, warning on a different one
    (`merge_claim`); a DIFFERENT id is refused
    naming both, because two ids on one hold is the two-writers hazard this
    whole feature exists to make visible."""
    if open_record.agent is not None and open_record.agent != agent:
        raise RunRefusal(
            (
                Say(
                    f"[red]{key}: already claimed by {open_record.agent!r} — refusing to "
                    f"attribute it to {agent!r} as well. The worktree has exactly one "
                    "writer; close the first claim (`fr run resolve ... --state "
                    "done|failed`, or `fr run claim ... --abandoned`) before naming a "
                    "second.[/red]",
                    soft_wrap=True,
                ),
            )
        )
    return merge_claim(
        open_record,
        key,
        agent=agent,
        harness=harness,
        model=model,
        agent_type=agent_type,
        warn=warn,
    )


def close_on_resolve(
    state: RunState,
    owner_id: str,
    key: str,
    outcome: DispatchOutcome,
    *,
    agent: str | None,
    harness: str | None,
    model: str | None,
    warn: Warn,
) -> RunState:
    """`resolve`'s half of the dispatch pair: close `key`'s open record with
    `outcome`, optionally attaching a late identity first (spec §4.C).

    **Silent when there is nothing open** — and that is the requirement, not
    a shortcut. A run `fr run adopt`ed from a plan on disk has no dispatch
    history at all, and a `gate: operator` step is marked `blocked` without
    ever being dispatched; neither may start failing to resolve because this
    feature landed. Nothing is invented for them either: an absent record
    stays absent rather than being back-filled with a dispatch fr never made.

    A record that is already CLOSED (`claim --abandoned`) is likewise left
    exactly as it is — `abandoned` is what happened to that attempt, and
    overwriting it with this resolve's outcome would erase the one fact the
    operator recorded by hand.
    """
    record = state.steps[owner_id]
    open_record = held_record(record, key)
    if open_record is None:
        return state
    if agent is not None:
        open_record = claimed_identity(
            open_record, key, agent=agent, harness=harness, model=model, warn=warn
        )
    elif harness is not None or model is not None:
        open_record = merge_claim(
            open_record,
            key,
            agent=None,
            harness=harness,
            model=model,
            agent_type=None,
            warn=warn,
        )
    open_record = observed_model(open_record, key, warn)
    record = units.with_last_attempt_replaced(record, key, open_record)
    return with_step(state, owner_id, close_dispatch(record, key, outcome))


def observed_model(attempt: UnitAttempt, key: str, warn: Warn) -> UnitAttempt:
    """`attempt` carrying the model its subagent's transcript says RAN (gh#637).

    `advance` wrote the tier binding for a dispatched attempt — what SHOULD
    run. Resolve is the first point that knows the agent id, so the transcript
    can now say what DID: a dispatch sent without a model argument runs on
    the orchestrator's model, and the binding then named a model that never
    ran (run 2026-09-26-fix-624: haiku/sonnet recorded, opus throughout).
    Observed beats bound and beats reported, as `orchestrator_model` already
    does for the orchestrator's own units; a difference is said aloud, never
    blocked. Unobservable leaves the attempt as it was — an absence is not
    a mismatch.

    The comparison is against `bound` (spec 2026-10-06-cost-evidence §D),
    falling back to `model` for an attempt opened before run version 9, whose
    `model` held the binding. `tier` and `bound` are never touched."""
    from fr.models import model_family
    from fr.run.telemetry import subagent_model

    if attempt.agent is None or attempt.agent_type is None:
        return attempt
    observed = subagent_model(os.environ, attempt.session, attempt.agent)
    if observed is None:
        return attempt
    # Compared even when a claim already wrote the observed model (review
    # p2-r2: OpenCode always claims `--model`), against the binding.
    expected = attempt.bound if attempt.bound is not None else attempt.model
    if expected is not None and model_family(observed) != model_family(expected):
        warn(
            Say(
                f"[yellow]{key}: agent {attempt.agent} ran on {observed}, but the cursor "
                f"recorded {expected}. fr records what ran. If the tier's binding was "
                "meant, pass that model in the dispatch.[/yellow]",
                soft_wrap=True,
            )
        )
    return attempt.model_copy(update={"model": observed})


def build_member_brief(
    member: Step,
    group: Step,
    item: str,
    state: RunState,
    resolved_tier: str | None,
    harness: str | None = None,
    *,
    repo_root: Path,
) -> dict[str, Any]:
    """The dispatch brief for one `(phase, member)` unit of a grouped step.

    Same keys as the step brief (so a harness parses one shape) plus `group`
    (the fan-out step's id), `item` (the `phase/<n>` unit) and
    `resolved_tier`. `tier` and `for_each` fall back to the group's when the
    member leaves them unset — the common case, where the group declares the
    dispatch policy once.

    `resolved_tier` is member-only (D5): `tier` keeps the manifest's literal
    meaning — for the shipped `fr-goal` shape, the sentinel `"from_phase"` —
    so `resolved_tier` carries what that sentinel actually resolves to for
    THIS item: the tier declared on the named phase's header, or `None` when
    the phase declares none (the dispatch-time observable form of phase 2's
    untiered-plan warning). It has no analogue on the group/flat brief
    (`build_brief`, left untouched): a group spans every phase, so there is
    no single tier to resolve there, and a confidently-wrong value would be
    worse than an absent one.

    `long_commands` (gh#582) is the long-command rule for `harness`, the
    one `fr.harness.long_commands` resolves. It rides every member brief
    because the executor reads its task prompt when it acts, and the same
    rule in its agent file alone did not stop OpenCode killing a full suite
    at 120 s. fr-goal §5 relays it verbatim.
    """
    return {
        "run": state.run,
        "workflow": state.workflow,
        "step": member.id,
        "group": group.id,
        "long_commands": long_command_rule(harness),
        "item": item,
        "kind": member.kind,
        "skill": brief_skill(member),
        "agent": member.agent,
        "needs": list(member.needs),
        "emits": list(member.emits),
        "gate": member.gate,
        "tier": effective_tier(member, group),
        # The member's OWN, never the group's: an obligation is a property of
        # the step that carries it, and inheriting it would make every member
        # of the loop owe the review member's evidence.
        "evidence": caller_evidence(member),
        "resolved_tier": resolved_tier,
        "for_each": group.for_each,
        "steps": [],
        "record": record_brief(state, member, group, item, repo_root=repo_root),
        "commit_templates": commit_templates_brief(repo_root, state.issue),
        # R6: every agent-step brief carries them; a member is never
        # `gate: operator`, so there is nobody here to answer them.
        "dead_bindings": None,
        "binding_offers": None,
        **review_findings_brief(member, item),
        **tests_brief(repo_root, member),
    }


def tests_brief(repo_root: Path, step: Step) -> dict[str, Any]:
    """`tests: {mode: ci[, fast_tier: ...]}` for `deliver` (a step that declares
    `tests` evidence) and for a phase executor's unit, when the repo's
    `.fr/ci.yaml` at HEAD declares `tests: ci` (spec 2026-11-19-local-suite-cost
    R8, §3.F) — else nothing, so every other brief is unchanged. `fast_tier` is
    the repo's own command (`.fr/ci.yaml`'s `fast_tier`, `{base}` made the run's
    default ref), present only when the repo names one: fr ships none. A value
    fr refuses refuses the brief (exit 2), never read as "not declared", and so
    does a `fast_tier` whose default ref git cannot name: never a blank base. Under quiet
    and stealth both keys come from the configuration branch only when the forge protects
    it (`ci_evidence._at_tip`, review p3-r1): unprotected, this brief carries neither."""
    from fr.git import GitRefusal, remote_default_ref
    from fr.run.ci_evidence import CiEvidenceRefused, declared_fast_tier, declared_tests_mode

    if "tests" not in step.evidence and step.agent != PHASE_EXECUTOR_AGENT:
        return {}
    try:
        mode = declared_tests_mode(repo_root)
        template = declared_fast_tier(repo_root) if mode is not None else None
    except CiEvidenceRefused as e:
        raise RunRefusal(
            (Say(f"[red]{step.id}: refused — {escape(str(e))}[/red]", soft_wrap=True),)
        ) from e
    if mode is None:
        return {}
    tests: dict[str, Any] = {"mode": mode}
    if template is not None:
        base = remote_default_ref(repo_root)
        if not isinstance(base, str) or not base:
            # Never a blank `{base}` (l-errors-r1): the executor would run the
            # tier against nothing and read its silence as green.
            why = base.reason if isinstance(base, GitRefusal) else "no remote default ref"
            raise RunRefusal(
                (
                    Say(
                        f"[red]{step.id}: refused — .fr/ci.yaml's fast_tier needs {{base}}, the "
                        f"run's default ref, and git cannot name it: {escape(why)}. Fix: "
                        "`git remote set-head <remote> --auto` (a remote with no HEAD), or "
                        "`git config checkout.defaultRemote <remote>` (several remotes).[/red]",
                        soft_wrap=True,
                    ),
                )
            )
        command = template.format(base=base)
        tests["fast_tier"] = " ".join(command.split())
    return {"tests": tests}


def review_findings_brief(member: Step, item: str) -> dict[str, str]:
    """`review_findings` for a phase review unit whose reviewer's return fr
    checks at resolve (spec 2026-10-02-opencode-observe-2 §E, R7) — every
    `review-phase` of the shipped shapes — else nothing. fr-goal §6 puts its
    text into the reviewer's prompt verbatim."""
    from fr.run.review_return import review_findings_rule

    if not {"findings", "reviewer"} <= set(member.evidence):
        return {}
    phase = item_phase(item)
    return {} if phase is None else {"review_findings": review_findings_rule(phase)}


def lens_review_brief(step: Step, state: RunState, *, repo_root: Path) -> dict[str, Any]:
    """`lens_review` for the lens review (spec 2026-11-12-review-lenses R8, §3.C):
    the feature's lens set, each lens with its text, why it is there and its
    return rule — else nothing, so every other brief is unchanged. A set fr cannot
    compute refuses the brief (exit 2) before anything is written: an empty set
    read off an error would dispatch no reviewer for a lens a rule requires."""
    from fr.lenses.review import LENS_EVIDENCE
    from fr.lenses.review import lens_review_brief as lens_set_brief
    from fr.shape import shape_path

    if LENS_EVIDENCE not in step.evidence:
        return {}
    lenses = lens_set_or_refuse(step.id, repo_root, state)
    return {"lens_review": lens_set_brief(repo_root, lenses, shape_path(repo_root, state.run))}


def resolve_hint(run_id: str, member_id: str, item: str | None, state: str = "done") -> str:
    """The exact `fr run resolve` command that records one grouped unit's
    outcome — the two-flag form `--step <member> --item <head>` that
    `_split_member_id` teaches when someone reaches for the composite.

    One builder because two surfaces print it for the same act: `advance`
    pre-empts the #501 error beside every dispatch brief, and (Phase 2) the
    ALREADY RUNNING refusal names the command that clears it. Spelled
    separately they would drift, and an operator who was shown two different
    commands for one outcome has no way to tell which is current.

    **`--state` is a CONCRETE value, never the alternation `done|failed`**
    (review `r1-f1`). This string is printed under "resolve with:" and is
    meant to be pasted. In every POSIX shell `|` is a pipe, so pasting
    `--state done|failed` RUNS the resolve with `--state done` and then fails
    with `command not found: failed` — exit 127 over a run whose state has
    already changed. A line that reports failure while having done the thing
    is the precise defect class this whole PR exists to remove, and the
    existing operator-gate hint (`--state done`) already set the precedent.
    A caller that needs to mention the other outcome says so in prose beside
    the command, outside the pasteable span.

    `item` is None for a TOP-LEVEL step, which has no `--item` to address —
    the flag is simply omitted. One builder rather than two spellings for the
    same act: the ALREADY RUNNING refusal (§3.A) prints this for both shapes,
    and a second inline `f"fr run resolve ..."` is exactly how the two would
    drift apart.
    """
    scope = f" --item {item}" if item is not None else ""
    return f"fr run resolve {run_id} --step {member_id}{scope} --state {state}"


def dispatched_from_another_session(attempt: UnitAttempt | None) -> bool:
    """Was `attempt` opened by a session that is NOT this one? (spec §4.D.1)

    A PROOF, never a default. An attempt with no recorded `session` — every
    one written before the field existed, and every harness with no session
    concept — is not claimed to be elsewhere, because not knowing where it
    came from is not the same as knowing it came from somewhere else.
    """
    from fr.run.telemetry import dispatched_from_this_session

    if attempt is None or attempt.session is None:
        return False
    return not dispatched_from_this_session(os.environ, attempt.session)


def already_running_refusal(
    step_id: str,
    subject: str,
    at: str | None,
    run_id: str,
    member_id: str,
    item: str | None,
    held: UnitAttempt | None = None,
) -> str:
    """The #499 refusal, in one renderer for both call sites (spec §3.A).

    `advance_cmd`'s top-level `agent` branch and `_advance_group`'s grouped
    member differ only in whether the outstanding unit has an `--item`, so
    they differ only in this function's last argument. Spelled separately,
    the operator would eventually be shown two different texts for one
    situation and have no way to tell which was current.

    Both ways forward are named because both are legitimate: waiting is
    almost always right, and `--redispatch` is the deliberate escape for a
    genuinely lost agent. Neither pasteable command carries a shell
    metacharacter (review `r1-f1`) — the `--state failed` alternative is
    prose OUTSIDE the command, not an alternation inside it.
    """
    # A top-level step IS its own outstanding unit, so naming it twice
    # ("plan: plan is ALREADY RUNNING") reads as a bug in the message. The
    # group prefix exists to say WHICH group the unit belongs to; when there
    # is no group there is nothing to prefix.
    named = subject if subject == step_id else f"{step_id}: {subject}"
    # HELD names the agent; RUNNING only names the clock. gh#503 and gh#519
    # each built this refusal, one from the dispatch record and one from the
    # `items` map, and the record is strictly the better witness: it knows WHO
    # is holding the unit, not merely that something is. It is still optional,
    # because a cursor adopted from disk, or written before the record existed,
    # has no holder to name — and "ALREADY RUNNING (dispatched <ts>)" is the
    # honest sentence in that case rather than a fabricated identity.
    if held is not None:
        who = dispatch_holder_label(held)
        suffix = dispatch_descriptor_suffix(held, with_agent_type=True)
        head = f"[red]{named} is ALREADY HELD by {who}{suffix} "
        head += f"(dispatched {held.dispatched}) — not yet returned.[/red]\n"
    else:
        head = f"[red]{named} is ALREADY RUNNING (dispatched {at}).[/red]\n"
    # §4.D.1: every other refusal fr prints means "someone is working". This
    # one may mean "that agent died with its host" — the cursor travelled with
    # the branch and nothing else did — and without saying so the operator
    # waits forever on a holder nothing here can observe. The escape is named
    # below already; this only says why to reach for it.
    if dispatched_from_another_session(held):
        head += (
            "  Dispatched from ANOTHER session: this one cannot see whether that agent is "
            "alive, and its cost is not observable from here. If it died with its host "
            "(a run picked up on another machine), close it with the `lost agent` line "
            "below.\n"
        )
    return (
        head
        + "  Waiting on that agent — do NOT dispatch again.\n"
        + f"  resolve it:      {resolve_hint(run_id, member_id, item)}"
        "   (or --state failed)\n"
        f"  lost agent:      fr run claim {run_id} --step {member_id}"
        + (f" --item {item}" if item else "")
        + " --abandoned\n"
        + f"  re-brief anyway: fr run advance {run_id} --redispatch"
    )


def nothing_running_refusal(subject: str, detail: str, run_id: str) -> str:
    """`--redispatch` with nothing outstanding (spec §3.A).

    It exits 2 rather than quietly degrading into an ordinary `advance`: the
    operator reaching for the flag believes an agent is running, and if none
    is, the mental model is wrong and saying so is the whole point of §3.A.
    `fr-goal`'s loop never passes the flag, so this strictness costs the
    normal path nothing.

    Two call sites, one renderer, for the same reason as
    `already_running_refusal`: `advance_cmd` catches the step that is not
    running at all (including every `cli` step, which fr executes inline and
    so is never `running`), `_advance_group` catches the group that is
    running with every unit already resolved. `detail` is the only part that
    differs.
    """
    return (
        f"[red]{subject}: --redispatch, but nothing is running{detail}.[/red]\n"
        "  --redispatch re-briefs a unit already dispatched; it never starts one.\n"
        f"  advance normally: fr run advance {run_id}"
    )


def manual_placement_errors(repo_root: Path, state: RunState) -> tuple[str | None, list[str]]:
    """`(plan_rel, messages)` — every way this run's plan mis-places a manual
    phase (spec §3.D.2). Empty when the plan is fine, missing or unparseable.

    The VERDICT half of `manual_placement_preflight`, split out so the idle
    reading (`fr run check --idle`, spec 2026-09-20-unit-record-unification
    §4.G) can ask "would `advance` refuse this group?" without a second
    definition of the rule — and without printing or exiting.

    It calls `fr.plan_review._manual_placement_issues` — the authoring gate
    ITSELF, not a re-implementation of it — so the two points share one
    definition of "trailing" (`_trailing_manual_block`), one definition of
    "outstanding", and one message. Spelled twice they would drift, and an
    operator shown two different texts for one situation has no way to tell
    which is current.
    """
    from fr.parser import PlanSchemaError, parse
    from fr.plan_review import _manual_placement_issues

    plan_rel = emitted_plan(state)
    if plan_rel is None:  # pragma: no cover — `group_phases` refused first
        return None, []
    try:
        plan = parse(emitted_path(repo_root, plan_rel))
    except PlanSchemaError:  # pragma: no cover — `group_phases` refused first
        return plan_rel, []
    return plan_rel, [i.message for i in _manual_placement_issues(plan) if i.severity == "error"]


def manual_placement_preflight(repo_root: Path, state: RunState, step_id: str) -> None:
    """Refuse a whole group whose plan mis-places a manual phase (spec §3.D.2).

    The rule is one invariant — *no manual phase may be outstanding when an
    agentic phase after it runs* — and `fr plan self-review` is its primary
    gate, running as fr-goal's `plan-review` `kind: cli` step, where a `cli`
    step's exit code is its verdict. This is the second enforcement point,
    for the paths that never pass through the first: a run reached by
    `fr run adopt`, or driven by a repo-authored shape with no plan-review
    step, arrives at the fan-out with the plan unchecked.

    Silent when the plan is missing or unparseable: `group_phases` has
    already refused the advance for both, naming the cause, and a second
    refusal here would only mask its message.
    """
    plan_rel, messages = manual_placement_errors(repo_root, state)
    if not messages:
        return
    detail = "\n".join(f"  {message}" for message in messages)
    raise RunRefusal(
        (
            Say(
                f"[red]{step_id}: this plan mis-places a manual phase — refusing to "
                f"dispatch ANY of it.[/red]\n{detail}\n"
                f"  re-check it with: fr plan self-review {plan_rel}",
                # soft_wrap: the last line is a command meant to be pasted, and rich
                # folds at width 80 whenever stderr is not a tty (`p1-f1`, `r1-f2`).
                soft_wrap=True,
            ),
        )
    )


def dispatch_holder_label(attempt: UnitAttempt) -> str:
    """Who to name for `attempt` — the priority spec §4.B.1/§4.C both rely on.

    `agent_type is None` means an orchestrator-run `kind: agent` step (the
    manifest's own `agent: null`): that is not a missing value, it is the
    orchestrator doing the work itself, and it never reports an `agent` id
    for itself. Only once a unit IS dispatched to an actual agent type does
    an absent `agent` read as `an unclaimed agent` — the same distinction
    the gh-499 refusal (`already_running_refusal`) draws, by calling this.
    """
    if attempt.agent_type is None:
        return "the orchestrator"
    if attempt.agent is not None:
        return f"agent {attempt.agent}"
    return "an unclaimed agent"


def dispatch_descriptor_suffix(attempt: UnitAttempt, *, with_agent_type: bool = False) -> str:
    """` (harness, model)` — and, for the gh-499 refusal, the agent TYPE first.

    `fr run status` prints one line per attempt and already says which unit it
    is under, so the type would be noise there. The refusal is read by someone
    deciding whether to wait, and "what kind of agent has this" is one of the
    four facts that decision needs (who, what kind, which harness, since when).
    """
    agent_type = attempt.agent_type if with_agent_type else None
    descriptors = [d for d in (agent_type, attempt.harness, attempt.model) if d]
    return f" ({', '.join(descriptors)})" if descriptors else ""
