# Journal: 2026-10-06-model-binding-churn

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-06T17:34:32+00:00 input=true -->
### operator-brief · discovery · Operator brief: batch model-bindings / super-fr#591

Batch `model-bindings` of derio-net/super-fr (one PR, branch feat/batch-model-bindings): super-fr#591 — Model bindings rot as providers churn: probe live, fall back by family then tier, ask when interactive, decide and record when not (high priority). Operator note: Design first: live probe, then family, then tier fallback; ask when interactive, decide and record when not.

Issue text:

# Model bindings rot as providers churn: probe live, fall back by family then tier, ask when interactive, decide and record when not (high priority)

> **Priority: high.** Model availability now churns faster than anyone re-runs
> `fr models set`. On 2026-09-23 an entire provider generation vanished within
> about a day of its successor shipping, and a machine was left with a tier agent
> bound to a dead model and no signal from anything.

## What happened

Copilot released `gpt-6-*` and `claude-opus-5.5` on 2026-09-22. By the next day
**every** `gpt-5.6-*` model had been retired. A live probe of each:

| model | live probe |
|---|---|
| `github-copilot/gpt-5.6-terra` | `Error: The requested model is not supported.` |
| `github-copilot/gpt-5.6-luna` | `Error: The requested model is not supported.` |
| `github-copilot/gpt-5.6-sol` | `Error: The requested model is not supported.` |
| `github-copilot/gpt-6-sol` / `gpt-6-luna` / `claude-opus-5.5` / `claude-haiku-4.5` | `OK` |

Meanwhile:

- **The operator's installed `fr-phase-executor-standard` was bound to
  `gpt-5.6-luna`.** Any OpenCode `/fr-goal` that dispatched a `standard` phase
  would have failed at dispatch. Nothing warned: `fr models set` accepted the
  string, the materialiser wrote it, `fr harness parity` was green.
- **The catalogue does not know either.** `opencode models --refresh` still
  lists all three, and `--verbose` marks each **`"status": "active"`** — the
  same as the live models. The catalogue's `status` is not an availability
  signal.
- The Claude side needed a manual bump too (`claude-opus-5-5`), because
  bindings are concrete model ids.

## The requirement (operator's words)

> the models are churning very quickly, there must be fallback processes and
> dynamic in-place updates. Asking the user if possible, autonomously deciding
> (based on the 3-tiered concept) when not

## What the data already supports

The catalogue is untrustworthy about *availability* but reliable about
**lineage**. From `opencode models --verbose`:

| retired | `family` | released | same-family successor |
|---|---|---|---|
| `gpt-5.6-luna` | `gpt-luna` | 2026-07-09 | `gpt-6-luna` (2026-09-22) |
| `gpt-5.6-sol` | `gpt-sol` | 2026-07-09 | `gpt-6-sol` (2026-09-22) |
| `gpt-5.6-terra` | `gpt-terra` | 2026-07-09 | **none** — gpt-6 has no terra |
| *(still live)* `claude-opus-5` | `claude-opus` | 2026-07-24 | `claude-opus-5.5` (2026-09-22) |

So there are two different cases, and they deserve different rules.

## Proposed behaviour

### Detection — live, and as early as possible

- **Probe at bind time.** `fr models set` issues a minimal call and **refuses**
  a model the provider will not serve, naming the error. Fail at authoring, not
  at dispatch.
- **Probe at run start.** `fr run start` (and `advance` before dispatching)
  probes the orchestrator binding and every tier the plan uses, once per run,
  cached. Cost is a few tokens per model.
- **Recognise retirement at dispatch** as a distinct error class, so a dispatch
  failure caused by a dead model triggers fallback rather than failing the
  phase.
- **Never trust catalogue `status`** — pinned by a test using the evidence above.

### Choosing a replacement — the 3-tier concept

1. **Same-family successor** (`family` equal, newer `release_date`, live) — the
   provider's own lineage. Covers luna, sol and opus above. Safe to take
   autonomously.
2. **No family successor** (terra's case) — choose by **tier**, keeping the
   tier's relative position among the other bindings: `mechanical` ≤ `standard`
   ≤ `hard` by cost, tool-calling capable, live, and distinct from the
   `orchestrator` binding (the constraint #560 established — a tier bound to the
   session model cannot be told from an untiered dispatch).
3. **Nothing satisfies the tier** — refuse, loudly. Never silently collapse two
   tiers onto one model.

### Asking vs deciding

- **Interactive** (TTY, or an operator gate available) → **ask**, proposing the
  choice above as the recommended option, with the alternatives. In fr-goal this
  belongs in the batched question gate — the model-per-tier question
  (SKILL.md:47) already lives there. But note #538: that question relies on the
  model remembering a check, and on OpenCode it did not fire. The trigger has to
  be a **CLI refusal or warning**, not prose.
- **Non-interactive** (pods, CI, the bridge, an unattended run) → **decide
  autonomously** by the rules above, and never escalate cost beyond a bound —
  e.g. no more than N× the retired model's price without a human.
- **Either way, record it.** Every substitution is written with old model, new
  model, reason (`retired`), decider (`operator` | `autonomous`) and rule used.
  An autonomous substitution must be as loud as a refusal. Silent success is the
  defect class this repo keeps producing.

This deliberately differs from the artifact-migration gate, which **refuses** in
non-interactive contexts rather than mutating. The difference is justified: a
stale artifact can wait for a human, whereas a dead model makes an unattended run
fail outright. It should be stated as a decision, not left implicit.

### In-place update

Rewrite `models.yaml` and re-materialise the installed OpenCode agents through
the #504 materialiser — which is also where #505's misleading "no agent files
found" message lives, so fix it here or first. On OpenCode the tier lives in the
agent's **name** and its model is fixed in the agent file (SKILL.md:92), so a
fallback must rewrite the file **before** dispatch. On Claude Code the model is
passed per call, so fallback can be per-dispatch.

### Upgrades are different: ask only, never autonomous

A new model in a still-live family (`claude-opus-5` → `claude-opus-5.5`) is an
**offer**, not a fallback. The bound model still works, so nothing justifies
changing behaviour or cost without consent. Surface it — `fr models` status, or
the run-start banner — and let the operator accept.

## Acceptance — live, per the #486 precedent

- [ ] `fr models set` refuses a retired model, showing the provider's error.
- [ ] With a tier bound to a retired model, an interactive `fr run start` asks
      and proposes the same-family successor; the answer is materialised and
      the dispatched agent runs on it (verified in `opencode.db`).
- [ ] Non-interactive, the same situation substitutes autonomously, records old
      → new, reason and decider, and says so loudly.
- [ ] A tier with no family successor gets a tier-ranked replacement that is
      distinct from the orchestrator and keeps tier ordering — or a loud refusal.
- [ ] A new model in a live family is offered, never applied unasked.
- [ ] A test pins that catalogue `status: active` is not treated as live.

## Related

#538 (tier question never fires on OpenCode — same trigger problem), #505
(materialiser message), #536 C3 (served model recorded, and the `orchestrator`
binding that warns on mismatch — the natural anchor for the distinctness rule).

Suggested handoff: `/fr-goal` on this issue.

<!-- fr:journal kind=decision scope=spec id=probe-scope-opencode-only created=2026-10-06T17:34:32+00:00 -->
### probe-scope-opencode-only · decision · Live probing covers OpenCode only

Operator answer (Q1): OpenCode only. Claude Code and Hermes bindings are reported `unprobed`; nothing substitutes them (spec R10).

<!-- fr:journal kind=decision scope=spec id=ask-at-gates-else-decide created=2026-10-06T17:34:32+00:00 -->
### ask-at-gates-else-decide · decision · Ask at TTY/operator gate, decide autonomously elsewhere

Operator answer (Q2): ask on a terminal (`fr models set/check`) and in fr-goal's brainstorm question round; decide + record at `fr run advance` before a dispatch, so a run never stalls mid-wave (spec R5-R8).

<!-- fr:journal kind=decision scope=spec id=autonomous-cost-bound-2x created=2026-10-06T17:34:32+00:00 -->
### autonomous-cost-bound-2x · decision · Autonomous picks cost at most 2x the dead model

Operator answer (Q3): catalogue input+output price of an autonomous replacement <= 2x the dead model's; else no autonomous pick (spec R4).

<!-- fr:journal kind=decision scope=spec id=record-in-run-journal-only created=2026-10-06T17:34:32+00:00 -->
### record-in-run-journal-only · decision · Substitutions are recorded in the run journal only

Operator answer (Q4): run journal only. Outside a run, the loud stderr line is the only record (spec R11).

<!-- fr:journal kind=decision scope=spec id=offers-asked-in-round created=2026-10-06T17:34:32+00:00 -->
### offers-asked-in-round · decision · Upgrade offers are also asked in fr-goal's round

Operator answer (Q5): the gated brief carries `binding_offers`; fr-goal asks one question per offer (recommended: keep), never applied unasked (spec R6, R7, R12).

<!-- fr:journal kind=decision scope=spec id=verification-candidate-plus-live created=2026-10-06T17:34:32+00:00 -->
### verification-candidate-plus-live · decision · Verified by candidate scenarios plus one live row

Operator answer (Q6): `candidate` walk with stub-opencode scenarios; one post-merge `live` row for a real OpenCode retirement verified in opencode.db (spec ## Verification, Test Plan).

<!-- fr:journal kind=decision scope=spec id=repo-layer-never-rewritten created=2026-10-06T17:34:32+00:00 -->
### repo-layer-never-rewritten · decision · A dead repo-layer binding is refused, never rewritten

Author decision, stated in the spec (R9): docs/superpowers/models.yaml is a tracked contract; advance refuses (exit 2) rather than edit it.

<!-- fr:journal kind=decision scope=spec id=triage-launch-out-of-scope created=2026-10-06T17:34:32+00:00 -->
### triage-launch-out-of-scope · decision · Triage batch launch is out of scope

Author decision (spec non-goals): herdr only supports Claude Code, which is unprobed per Q1.

<!-- fr:journal kind=review scope=spec id=spec-review-r1 created=2026-10-06T17:41:10+00:00 -->
### spec-review-r1 · review · independent spec review: 12 findings

Reviewed docs/superpowers/specs/2026-10-06-model-binding-churn-design.md against the spec journal's eight decision entries, against the codebase it names, and against itself (including matrix coverage and the `## Verification` grammar).
Findings raised: sr1-f1..sr1-f12, all review_scope: in. Codebase: f1, f2, f3, f12. Decisions: f6, f11. Consistency/completeness: f4, f5, f7, f8, f9, f10.
Verified: models.py:105 set_binding; models.py:70 resolved_config (spec cites :67); models_cmd.py:94-112 set → set_binding → materialize_agents → _report_changes; models_cmd.py:69 _report_changes; opencode_agents.py:145 materialize_agents; run_cmd.py:3347 _unbound_tiers (key emitted at :3343); run_cmd.py:3473 _orchestrator_model_notice called at :4450 (start) and :5047 (advance); run_cmd.py:4071 _advance_group (_open_dispatch at :4194, unit marked running at :4174); run_cmd.py:4012 _print_member_dispatch; run_cmd.py:4281 start_cmd; run_cmd.py:163/:191 _RunWrites + note(repo_root, path); run_cmd.py:723 _phase_tier → str|None; run_cmd.py:5174 gated agent step prints _build_brief; trigger.py:280 is_interactive (TTY on stdin+stdout, no CI marker; also honours FR_NON_INTERACTIVE); journal/model.py:576 append_journal_entry(path, slug, entry), JournalEntry at :89 (frozen, extra=forbid, title required); parity.yaml rows are kind hook|interaction; harness/check.py:134 checks hook rows only, so an interaction row passes --check; fr_herdr/runner.py:97-99 HARNESSES = only `claude`; fr-goal.yaml:61-64 brainstorm is the gate: operator step; fr-goal SKILL.md:57 the model-per-tier / unbound_tiers sentence exists; verification/spec_section.py:30-115 the section parses (one strategy line, two row lines with reasons; prose ignored); matrix.yaml:7077-7145 five model-binding-* rows cite R1, R2, R4–R12 but not R3.

<!-- fr:journal kind=finding scope=spec id=sr1-f1 created=2026-10-06T17:41:10+00:00 state=open review_scope=in -->
### sr1-f1 · finding [open] (reviewer: in scope) · `_flat_brief` does not exist; the brief builder is `_build_brief`, and it serves every agent step

check: codebase. Evidence: spec §C "Brief keys"; run_cmd.py:3305 (`_build_brief`), :3343 (`unbound_tiers`), :5174 (gated brief). The function returning the brief dict carrying `unbound_tiers` is `_build_brief(step, state)` at run_cmd.py:3305; it is not "flat" — it is called for grouped steps too (:5179 → `_advance_group`) and for the gated brief at :5174. Fix: rename to `_build_brief` and state the new keys are added only when `step.gate == "operator"`; its docstring and `test_run_cli.py` pin the key set to `Step.model_fields`, so say whether that test learns two conditional keys or the keys are always present as `null`.

<!-- fr:journal kind=finding scope=spec id=sr1-f2 created=2026-10-06T17:41:10+00:00 state=open review_scope=in -->
### sr1-f2 · finding [open] (reviewer: in scope) · Several cited line numbers have drifted, and the description of `is_interactive` omits one condition

check: codebase. Evidence: spec §2; models.py:70; models_cmd.py:94-95; trigger.py:295. `resolved_config` is at models.py:70, not :67; `fr models set` is at models_cmd.py:94-95, not :96. `is_interactive` also returns false when `FR_NON_INTERACTIVE` is truthy (trigger.py:295); R5's "off a terminal" inherits that, so state it.

<!-- fr:journal kind=finding scope=spec id=sr1-f3 created=2026-10-06T17:41:10+00:00 state=open review_scope=in -->
### sr1-f3 · finding [open] (reviewer: in scope) · R8 checks only grouped phase dispatch, misses tiered flat agent steps, and names the wrong tier source

check: consistency. Evidence: R8; spec §C; flat dispatch run_cmd.py:5201-5223 (`_open_dispatch(..., tier=step.tier)`); fr-goal.yaml:85-86 (`spec-review`: `agent: super-fr:fr-spec-reviewer`, `tier: hard`); grouped tier run_cmd.py:4199 (`_dispatch_tier(repo_root, state, _effective_tier(member, step), phase_n)`); run_cmd.py:723-744 (`_phase_tier` returns None when the phase declares no tier). On OpenCode fr-spec-reviewer is materialised per tier like the phase executor; the flat path dispatches it with `tier: hard` and no binding check, so a dead `hard` binding still fails at dispatch. The grouped member's tier comes from `_dispatch_tier(… _effective_tier(member, step) …)`, not `_phase_tier`, which is fail-soft (None for an untiered phase). Fix: check the same tier `_open_dispatch` receives, on both paths (or state flat tiered steps are a non-goal), and say what happens when the tier is None.

<!-- fr:journal kind=finding scope=spec id=sr1-f4 created=2026-10-06T17:41:10+00:00 state=open review_scope=in -->
### sr1-f4 · finding [open] (reviewer: in scope) · R4 is undefined for the spec's own motivating case: a dead model with no catalogue entry and no snapshot

check: consistency. Evidence: spec §2 (orchestrator `gpt-6-sol` has left the catalogue); R3; R4; R1; R5; §A `choose_replacement(tier, dead, bindings, entries, probe)`. Snapshots only start being recorded with this change, so every binding already dead and gone (gpt-6-sol) has neither entry nor snapshot. R4 says only "no autonomous pick, asking is the only path", but the family rule needs `family`/`release_date` and the tier rule ranks by price nearest the dead model's — so R1, R5 and R7 have nothing defined to propose. Same gap when an entry exists but `price` is None. The 2× bound is only for autonomous picks, yet `choose_replacement` has no autonomous/proposal flag. Fix: define the proposal for no-entry/no-snapshot and unknown-price (e.g. the provider's "Did you mean" hint, the tier rule without price nearness, or explicitly none), and make the 2× bound a parameter or a `Choice` field the caller checks.

<!-- fr:journal kind=finding scope=spec id=sr1-f5 created=2026-10-06T17:41:10+00:00 state=open review_scope=in -->
### sr1-f5 · finding [open] (reviewer: in scope) · The tier rule's ordering is undefined for the `orchestrator` binding, which R5 and R6 propose replacements for

check: consistency. Evidence: R4 (tier rule ordering, distinct from `orchestrator`); R5/R6 cover `orchestrator`; models_cmd.py:100-102 (orchestrator is never dispatched to). Fix: state what the tier rule means for `orchestrator` — family rule only, or distinct from every phase tier with no ordering, or no tier-rule proposal.

<!-- fr:journal kind=finding scope=spec id=sr1-f6 created=2026-10-06T17:41:10+00:00 state=open review_scope=in -->
### sr1-f6 · finding [open] (reviewer: in scope) · "Run journal" is not a journal scope; the spec records in two different journals, and the operator-decided entry lacks R11's fields

check: decisions. Evidence: decision `record-in-run-journal-only`; R7 (brainstorm decision → spec journal); R8 (plan journal); R11 ("the run journal records it"); journal scopes are spec|plan|debug. An autonomous substitution goes to the plan journal, an operator choice to the spec journal; R7 does not require old, new, reason, decider, rule. Fix: define "run journal" (e.g. spec journal before plan, plan journal after) and require R7's decision body to carry the same five fields with `decider: operator`.

<!-- fr:journal kind=finding scope=spec id=sr1-f7 created=2026-10-06T17:41:10+00:00 state=open review_scope=in -->
### sr1-f7 · finding [open] (reviewer: in scope) · R3 (probe cache, 6 h TTL, catalogue snapshots) is cited by no acceptance row

check: consistency. Evidence: matrix.yaml:7077-7145 rows cite R1, R2, R4–R12, never R3. R3 states behaviour the run-integration and replacement rows depend on (TTL, set/check fresh, the snapshot that keeps lineage). Fix: add R3 to `model-binding-replacement`'s origin or add a row for it.

<!-- fr:journal kind=finding scope=spec id=sr1-f8 created=2026-10-06T17:41:10+00:00 state=open review_scope=in -->
### sr1-f8 · finding [open] (reviewer: in scope) · Neither the Test Plan nor `## Verification` names the three candidate rows or their scenarios

check: consistency. Evidence: spec `## Test Plan` and `## Verification` (only -live-opencode and -run-integration listed); matrix rows model-binding-set-probe/-replacement/-check-report are `verify: candidate` with scenarios tests/scenarios/model-binding-{set-probe,replacement,check}.sh (matrix.yaml:7089-7117). The section is grammatically valid but never names the rows the walk runs or the scenario files to build; the issue's "a test pins catalogue `status: active` is not treated as live" has no stated location. Fix: list the three candidate rows in `## Verification`, name their scenario scripts and stub states, and say where the status:active test is pinned.

<!-- fr:journal kind=finding scope=spec id=sr1-f9 created=2026-10-06T17:41:10+00:00 state=open review_scope=in -->
### sr1-f9 · finding [open] (reviewer: in scope) · parity row `opencode: enforced` overclaims for a surface proven only against a stub

check: consistency. Evidence: spec §D; parity.yaml:242-251 and :272-282 (OpenCode interaction rows stay `partial` until their post-merge live row runs); Test Plan row `model-binding-live-opencode`. Fix: `opencode: partial` with a scope_note citing `model-binding-live-opencode` until it runs live.

<!-- fr:journal kind=finding scope=spec id=sr1-f10 created=2026-10-06T17:41:10+00:00 state=open review_scope=in -->
### sr1-f10 · finding [open] (reviewer: in scope) · Unproven assumption that a mid-session agent-file rewrite reaches the next OpenCode dispatch

check: consistency. Evidence: R8; §C (`materialize_agents` then the brief); issue ("a fallback must rewrite the file before dispatch"). R8 rewrites `fr-phase-executor-<tier>.md` while the orchestrating OpenCode session runs and assumes the next task dispatch reads the new `model:`; nothing cites evidence OpenCode reloads agent files mid-session. If not, the substitution is recorded and announced while the old model still runs. Fix: cite a measurement, or add a Risk plus a scenario/live-row step that confirms the served model after a mid-session rewrite, and name that as the property the live row proves.

<!-- fr:journal kind=finding scope=spec id=sr1-f11 created=2026-10-06T17:41:10+00:00 state=open review_scope=in -->
### sr1-f11 · finding [open] (reviewer: in scope) · The decision lists `fr models set` as a place to ask; R1 refuses instead

check: decisions. Evidence: decision `ask-at-gates-else-decide` ("ask on a terminal (`fr models set/check`)"); R1 (dead → exit 2 printing the proposal). Fix: on `is_interactive()` have `set` offer the proposal (default yes) like `check`, or record in R1 that refusal-with-proposal plus `check`'s prompt is how the decision is met.

<!-- fr:journal kind=finding scope=spec id=sr1-f12 created=2026-10-06T17:41:10+00:00 state=open review_scope=in -->
### sr1-f12 · finding [open] (reviewer: in scope) · The autonomous substitution writes files outside the repo before the cursor commit, with no rollback order

check: codebase. Evidence: §C dead+Choice branch; run_cmd.py:186-192 (`_RunWrites.remember`/`note` cover repo paths only); run_cmd.py:4203 (`_save_run_state`). Order is user models.yaml + agent files, then plan-journal append, then commit; a later failure leaves the binding and agent files changed with no journal entry — a silent substitution R11 forbids. Nor does the spec say whether the journal path goes through `remember()`. Fix: specify the order that keeps "recorded iff applied", or state that an advance failure after the binding write is reported loudly with the old → new pair.

<!-- fr:journal kind=finding scope=spec id=sr1-f1-resolved created=2026-10-06T17:41:10+00:00 state=fixed resolves=sr1-f1 -->
### sr1-f1-resolved · finding [fixed] · resolves sr1-f1: `_flat_brief` does not exist; the brief builder is `_build_brief`, and it serves every agent step

Renamed to `_build_brief` (run_cmd.py:3305); R6/§C state both keys are always present, lists only for `gate: operator` on a probed harness, else null, and that the key-set pin at test_run_cli.py:1095 grows by them.

<!-- fr:journal kind=finding scope=spec id=sr1-f2-resolved created=2026-10-06T17:41:10+00:00 state=fixed resolves=sr1-f2 -->
### sr1-f2-resolved · finding [fixed] · resolves sr1-f2: Several cited line numbers have drifted, and the description of `is_interactive` omits one condition

Background now cites models.py:70 and models_cmd.py:94, and states is_interactive's FR_NON_INTERACTIVE condition (trigger.py:295); R5 restates it.

<!-- fr:journal kind=finding scope=spec id=sr1-f3-resolved created=2026-10-06T17:41:10+00:00 state=fixed resolves=sr1-f3 -->
### sr1-f3-resolved · finding [fixed] · resolves sr1-f3: R8 checks only grouped phase dispatch, misses tiered flat agent steps, and names the wrong tier source

R8 now checks the tier `_open_dispatch` receives on BOTH paths (grouped `_dispatch_tier(... _effective_tier ...)` and flat `step.tier`, e.g. spec-review's `hard`); a None tier is not checked. §C names one guard `_guard_dispatch_binding` called before either path opens or saves anything.

<!-- fr:journal kind=finding scope=spec id=sr1-f4-resolved created=2026-10-06T17:41:10+00:00 state=fixed resolves=sr1-f4 -->
### sr1-f4-resolved · finding [fixed] · resolves sr1-f4: R4 is undefined for the spec's own motivating case: a dead model with no catalogue entry and no snapshot

R4 adds a third rule, the provider's `Did you mean` hint, for a dead model with no entry and no snapshot (gpt-6-sol's case); unknown dead price ranks the tier rule by newest. The 2x bound is now a predicate `is_autonomous(choice)` over `Choice.rule` and `price_ratio`; operator proposals are unbounded and show their ratio.

<!-- fr:journal kind=finding scope=spec id=sr1-f5-resolved created=2026-10-06T17:41:10+00:00 state=fixed resolves=sr1-f5 -->
### sr1-f5-resolved · finding [fixed] · resolves sr1-f5: The tier rule's ordering is undefined for the `orchestrator` binding, which R5 and R6 propose replacements for

R4's tier rule is phase tiers only; `orchestrator` gets the family rule and the provider hint.

<!-- fr:journal kind=finding scope=spec id=sr1-f6-resolved created=2026-10-06T17:41:10+00:00 state=fixed resolves=sr1-f6 -->
### sr1-f6-resolved · finding [fixed] · resolves sr1-f6: "Run journal" is not a journal scope; the spec records in two different journals, and the operator-decided entry lacks R11's fields

R11 defines the run journal: spec journal while the run has no plan artifact, plan journal after. R7 and R8 both require the five fields (old, new, reason, decider, rule).

<!-- fr:journal kind=finding scope=spec id=sr1-f7-resolved created=2026-10-06T17:41:10+00:00 state=fixed resolves=sr1-f7 -->
### sr1-f7-resolved · finding [fixed] · resolves sr1-f7: R3 (probe cache, 6 h TTL, catalogue snapshots) is cited by no acceptance row

New row model-binding-probe-cache cites R3 (verify none, unit tests with an injected clock — reason in ## Verification).

<!-- fr:journal kind=finding scope=spec id=sr1-f8-resolved created=2026-10-06T17:41:10+00:00 state=fixed resolves=sr1-f8 -->
### sr1-f8-resolved · finding [fixed] · resolves sr1-f8: Neither the Test Plan nor `## Verification` names the three candidate rows or their scenarios

## Verification now names the three candidate rows, their scenario scripts and the stub states each covers, and pins the status:active test in tests/unit/test_bindings_probe.py.

<!-- fr:journal kind=finding scope=spec id=sr1-f9-resolved created=2026-10-06T17:41:10+00:00 state=fixed resolves=sr1-f9 -->
### sr1-f9-resolved · finding [fixed] · resolves sr1-f9: parity row `opencode: enforced` overclaims for a surface proven only against a stub

parity row declared `opencode: partial` with a scope note citing model-binding-live-opencode.

<!-- fr:journal kind=finding scope=spec id=sr1-f10-resolved created=2026-10-06T17:41:10+00:00 state=fixed resolves=sr1-f10 -->
### sr1-f10-resolved · finding [fixed] · resolves sr1-f10: Unproven assumption that a mid-session agent-file rewrite reaches the next OpenCode dispatch

Added a Risk naming the unproven mid-session agent-file pickup; the live Test Plan step and the live row's reason name it as the property they prove; parity stays partial until then.

<!-- fr:journal kind=finding scope=spec id=sr1-f11-resolved created=2026-10-06T17:41:10+00:00 state=fixed resolves=sr1-f11 -->
### sr1-f11-resolved · finding [fixed] · resolves sr1-f11: The decision lists `fr models set` as a place to ask; R1 refuses instead

R1 now asks on a terminal (proposal, default yes) and refuses off one, matching the decision `ask-at-gates-else-decide`.

<!-- fr:journal kind=finding scope=spec id=sr1-f12-resolved created=2026-10-06T17:41:10+00:00 state=fixed resolves=sr1-f12 -->
### sr1-f12-resolved · finding [fixed] · resolves sr1-f12: The autonomous substitution writes files outside the repo before the cursor commit, with no rollback order

§C specifies the write order: remember+append+note the journal entry, then write the binding and materialise; a binding-write failure restores models.yaml and the journal bytes and exits 2 loudly, so a substitution is recorded iff applied.
