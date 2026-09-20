# `--phases-file` tier ingestion, and the rest of the chain to dispatch

**Issue:** [#434](https://github.com/derio-net/super-fr/issues/434)
**Date:** 2026-09-20
**Status:** design

## Background

`fr plan create --phases-file` silently drops `phase.tier`. The value is
discarded at ingestion, one layer upstream of the `extra="forbid"` on
`PhaseHeader` that would otherwise have complained, so the plan scaffolds
successfully and looks right until someone goes looking for the field.

Verified live on this worktree at `fr 4.8.0`. A phases file carrying all three
optional header fields produced:

```
{'number': 1, 'title': 'One', 'tag': 'agentic', 'depends_on': [],
 'tracking_issue': None, 'acceptance': ['row-a'], 'skeleton': True}
```

`acceptance` and `skeleton` survived; `tier` did not.

### The mechanism

Two places mirror the same omission:

- `fr/plan_ops.py:103` — `PhaseSpec` has `number`, `title`, `tag`,
  `depends_on`, `tasks`, `acceptance`, `skeleton`, and no `tier`. There is no
  field to receive the value.
- `fr/commands/plan_cmd.py:160` — the `--phases-file` ingestion loop is a
  hardcoded field whitelist that mirrors that omission.

`PhaseHeader.tier` itself has been correct since **3.12.0** (commit `4e04e6e`,
"fr-goal subagent execution — journal-fed, tier-selected phase dispatch").
Only the writer is broken.

### Three breaks, not one

Investigating #434's relationship to [#498](https://github.com/derio-net/super-fr/issues/498)
turned up two further gaps in the same chain. All three must close for a tier
to reach a dispatched subagent:

| # | Break | Where |
|---|---|---|
| 1 | `--phases-file` drops `tier` | `plan_cmd.py:160`, `plan_ops.py:103` |
| 2 | Nothing instructs a planner to write a tier | `fr-plan/SKILL.md` — the word `tier` does not appear |
| 3 | `fr` never resolves the `from_phase` sentinel | `run_cmd.py:628` |

Break 2 matters because fr-goal §3 asserts "fr-plan tags each phase a `tier`",
and fr-plan's own skill never says to. Break 3 is that `tier: from_phase` in the
shipped manifest is a *policy sentinel* that nothing in `fr` resolves:
`_build_member_brief` returns `member.tier if member.tier is not None else
group.tier`, so the dispatch brief hands the orchestrator the literal string
`"from_phase"`. The join from sentinel to a concrete tier is delegated entirely
to the LLM orchestrator via fr-goal §5 prose.

### What this means for #498 — the premise, corrected

The framing that prompted this work was that `tier` "currently never reaches the
plan on any harness at all", and that this would explain most of #498. **That is
not what the evidence shows, and the correction is the more useful finding.**

Two live plans in this repo carry real tiers:
`2026-09-19-opencode-subagent-dispatch` and
`2026-09-20-opencode-tier-binding-reaches-dispatch`. They got there by hand-edit,
not by `create()`. The evidence is key order: `_build_phase_doc` appends
`acceptance` and `skeleton` at the **end** of the header dict, whereas in both
plans `tier` sits between `tag` and `depends_on` — where `PhaseHeader` declares
it, and where a human or agent editing the YAML would naturally insert it.
`create()` cannot produce that ordering.

So #434 is **not** the root cause of #498. #498's observed artifact was an
installed OpenCode agent file with no `model:` line — a genuinely independent
break, correctly diagnosed and correctly fixed by #504. What #434 contributes to
that chain is narrower but still live:

- tier arrival is **unreliable and undocumented** — it depends on a planning
  agent choosing to insert a key no skill instructs it to write and no CLI path
  accepts. #434 reports this workaround being applied three times in another
  repo, each time caught only by chance;
- post-#504 the gap is **more** dangerous, not less. The installed agent files
  now carry correct models, so an untiered dispatch looks exactly like working
  tiering. The absence moved from one silent place to another.

This correction is recorded rather than quietly absorbed, because the
alternative — shipping a fix under a claim the evidence does not support — is
the same defect class both issues are about.

### A row that overclaims

`docs/acceptance/matrix.yaml` row `fr-goal-phase-tiering` sits at `status: ci`
claiming *"fr-plan annotates each phase with a tier; the orchestrator dispatches
that phase's subagent at the mapped model"*. Its unit levels pin
`PhaseHeader.tier` and `fr models resolve` **in isolation**; nothing pins that a
tier a planner writes reaches a plan, and until this spec ships it cannot. This
is the pattern #498 named: a row reading `ci` for a capability broken upstream
of everything it tests.

## Goals

1. `--phases-file` round-trips `tier`, emitted only when set so pre-tier plans
   stay byte-stable — exactly the `acceptance`/`skeleton` treatment.
2. A regression test for the **class**, not the instance: every `PhaseHeader`
   field survives `--phases-file`, derived from the model so the next added
   field is covered without an edit.
3. `fr-plan` instructs planners to assign a tier, making fr-goal §3's existing
   claim true.
4. `fr plan self-review` gains the two gates `acceptance`/`skeleton` already
   have or imply: an `fr_version` floor probe for `tier`, and a warning when an
   agentic phase declares none.
5. The dispatch brief carries a resolved tier for the phase it names.
6. The matrix says what is actually pinned.

## Non-goals

- **A new CLI verb for editing phase headers.** `fr plan edit` is state-only
  (`--tick`, `--complete-phase`); `acceptance` and `skeleton` are likewise
  settable only at create or by hand-editing the YAML, which fr-plan step 6
  explicitly sanctions. `tier` gets the same treatment, no more.
- **Re-litigating #498.** #504 fixed the binding→agent-file loop. This spec
  corrects the record about the relationship and closes the upstream half.
- **A live OpenCode subagent dispatch assertion.** That claim stays with the
  `opencode-subagent-dispatch` row, deliberately at `skipped`. See §Test Plan.
- **An artifact stamp bump or migration.** `PhaseHeader.tier` has existed since
  3.12.0; the model is unchanged and only the writer moves. No kind's shape
  changes, no released `fr` reads anything new, so the artifact-versioning rule
  is not triggered. Stated explicitly because "a field starts being written" is
  close enough to a shape change to deserve the argument rather than silence.

## Decisions

Each was put to the operator as one batched question and answered.

**D1 — Scope includes the fr-plan prose.** The CLI fix alone leaves `tier`
reachable but unrequested. `fr-plan/SKILL.md` gains the tier instruction, and
`.opencode/skills/fr-plan/SKILL.md` is regenerated via
`scripts/sync-opencode.py` (never hand-edited; a tripwire fails on drift).

**D2 — Both self-review gates ship.**

- *Floor probe*: warn when a plan carries a `tier` while its `fr_version`
  admits a pre-3.12.0 `fr`, which would die on a raw pydantic "extra field"
  error. Mirrors `_acceptance_link_issues`' 3.7.0 probe exactly. Accepted
  consequence, disclosed before the decision: this fires immediately on the two
  live tiered plans in this repo, which genuinely do carry the
  under-floored default `>=3.0.0,<5.0.0`.
- *Untiered warning*: warn when an agentic phase declares no `tier`, making the
  silent untiered fallback observable at plan time (#498's "fail visibly"
  doctrine). Also fires on this repo's pre-tier plans — accepted.

Both are `severity="warn"`, so neither changes an exit code and neither can
break CI. That matches the `acceptance`/`skeleton` probes.

**D3 — Patch bump, 4.8.0 → 4.8.1.** The behaviour shipped in 3.12.0; this
restores it rather than adding it, and the fr-plan prose documents an obligation
fr-goal already asserted. Per AGENTS.md, patch is the default for CLI fixes and
skill copy.

**D4 — Verification is unit plus an in-repo end-to-end.** An integration test
scaffolds a tiered plan through `--phases-file` and drives `fr run advance` to
the point of emitting a dispatch brief, asserting the brief carries that phase's
tier. It stops short of a real subagent but covers the whole `fr`-side chain in
CI.

**D5 — The brief gains `resolved_tier`; `tier` keeps its meaning.** Resolving
`from_phase` in place would have broken the documented property that the brief
is a faithful, exhaustive echo of every `Step` field — a property
`test_the_dispatch_brief_is_exhaustive_of_steps_agent_relevant_fields` derives
from the model rather than restating. Instead the member brief adds a new
`resolved_tier` key carrying the named phase's actual tier:

```json
{"item": "phase/3", "tier": "from_phase", "resolved_tier": "hard"}
```

`tier` stays the manifest's literal. No existing key changes meaning, so no
harness parsing the brief today is broken. The **group** brief gets no
`resolved_tier` — a group spans every phase, so there is no single tier to
resolve; only an item-scoped member brief can answer the question.

`resolved_tier` is `null` when the phase declares no tier, which is the
observable form of D2's untiered warning at dispatch time rather than plan time.

## Design

### A. Ingestion (breaks 1)

`PhaseSpec` gains `tier: Literal["mechanical", "standard", "hard"] | None =
None`. `_build_phase_doc` emits it beside its two siblings, omitted when `None`:

```python
if ps.tier is not None:
    phase_header["tier"] = ps.tier
```

Emission position follows `acceptance`/`skeleton` (appended after
`tracking_issue`), not `PhaseHeader`'s declaration order. Key order in the dump
is cosmetic — `PhaseHeader` parses either — and matching the existing emitter
keeps `_build_phase_doc` one consistent rule instead of two.

`plan_cmd.py`'s ingestion passes `tier=p.get("tier")`.

An invalid tier string must be rejected in `create()`'s **pre-flight loop**,
beside the existing `ps.number < 1` check — not left to `PhaseHeader`'s
`Literal` at the post-write re-parse. The module already states the doctrine
in that loop's comment: *"validate every external precondition BEFORE mutating
the filesystem"*, because the schema gate *"would only reject at the post-write
re-parse, stranding the folder"*. A typo'd `tier: hrad` would otherwise leave a
half-built plan folder behind and block the corrected re-run, which is #133's
failure mode exactly. This was missed in the first draft of this spec and
caught at spec-review.

The `--phases-file` docstring currently documents `skeleton` but neither
`acceptance` nor `tier`; it gains both.

### B. The class-level regression test (goal 2)

`PhaseHeader.model_fields`-derived: for every optional field on the model, a
phases file setting it must produce it in the dumped header. Derived from the
model, so the next field added to `PhaseHeader` is covered without touching the
test — which is the point, since the whitelist is what drifted.

### C. fr-plan prose (break 2)

The skill's phase-authoring rules gain a tier clause: every agentic phase
declares a `tier` (`mechanical | standard | hard`); manual phases do not (they
are never dispatched to a model). The vocabulary is derived from
`fr.types.PHASE_TIERS` rather than restated, consistent with how
`fr.opencode_agents` already sources the closed set.

### D. Self-review gates (D2)

A new `_tier_issues(plan)`, assembled alongside `_acceptance_link_issues` and
`_skeleton_issues`. Two `warn`s as described in D2; the floor probe reuses the
`SpecifierSet(...).contains("3.11.99", prereleases=True)` shape, with the same
`InvalidSpecifier` pass-through (the parser already fails loud on malformed
constraints).

### E. The resolved tier in the dispatch brief (break 3, D5)

`_advance_group` already computes `phase_n` and already parses the plan for
`_accounting_snapshot`, so reading the phase's tier costs nothing new.
`_build_member_brief` takes the resolved tier as a parameter and emits it as
`resolved_tier`. The group brief (`_build_brief`) is untouched.

### F. Matrix (goal 6)

- `fr-goal-phase-tiering` — correct the notes to state what its unit levels
  actually pin (the model and the resolver, in isolation) and what they did not
  until now (that a planner's tier reaches the plan). Add the new evidence refs.
  Status moves via `fr acceptance set-status` with the reason recorded, never a
  hand-edit.
- A new row for the round-trip claim, born `not-implemented` and flipped to
  `ci` when the phase lands.

## Test Plan

1. **Unit — `tier` round-trips `--phases-file`**, and is omitted from the dump
   when unset (byte-stability for pre-tier plans). An invalid tier value is
   refused by the pre-flight loop with a non-zero exit and **no plan folder
   left on disk** — the stranding case, asserted directly.
2. **Unit — class-level**: every optional `PhaseHeader` field survives
   `--phases-file`, derived from `model_fields`.
3. **Unit — self-review**: the floor probe warns on an under-floored constraint
   and stays silent on `>=3.12.0`; the untiered warning fires on an agentic
   phase with no tier and not on a manual one.
4. **Unit — brief**: a member brief carries `resolved_tier` for the phase it
   names, `null` when the phase declares none; the group brief carries no
   `resolved_tier`; the existing exhaustive-echo test still passes unchanged.
5. **Integration — in-repo end-to-end**: scaffold a tiered plan through
   `--phases-file`, drive `fr run advance` to the `implement` group's first
   member, assert the brief's `resolved_tier` equals the tier the phases file
   declared. This is the first test in the repo that joins ingestion to
   dispatch.
6. **Post-merge, operator-driven — not claimed by CI**: no automated level
   dispatches a real subagent and reads back the session row's model. That live
   claim remains with `opencode-subagent-dispatch` at `skipped`, whose scope
   correction already records why.

## Risks

- **The two new warnings fire on this repo's existing plans.** Known, disclosed,
  accepted at D2. They are `warn`, so no gate turns red. The alternative —
  suppressing them for pre-existing plans — would mean the gates never fire on
  precisely the plans that need them.
- **`resolved_tier` is a new key in a shape three harnesses parse.** Additive
  and ignorable; no existing key changes meaning. A harness that does not read
  it behaves exactly as today.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
