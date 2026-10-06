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
