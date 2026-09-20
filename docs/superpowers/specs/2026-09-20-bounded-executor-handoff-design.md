# Bounding the executor handoff, and the multiplier behind it — design

Status: draft (fr-brainstorming, 2026-09-20)
Branch: `feat/bounded-executor-handoff`
Issues: derio-net/super-fr#464 (12h / 766M tokens), #461 (duplicate reporting)
Operator decisions recorded in §4 (d1–d4).

## 1. Goal

#464's headline is that a ten-phase fr-goal run moved 766M tokens for a 4k-line
tool, with cache reads at 542x output and a monotonic per-phase climb. Its named
root cause is that `fr-phase-executor` inherits no conversation history, is
handed the journal instead, and nothing bounds that handoff.

**Most of what #464 asked for already shipped.** PR #465 (4.2.0, "fr-goal
methodology restoration") delivered the nested per-phase review loop, the
phase-1 skeleton mandate, refactor-or-justify, `fr journal handoff`, V1 context
accounting, the executor contract, and #461's return-only reporting rule. All
six `goal-*` acceptance rows sit at `ci`. This spec does not rebuild any of it.

What #465 left open is narrower and was found by measuring its own output:

- the handoff it shipped is a **discount, not a bound** — still monotonic, 2.4x
  growth over six phases, ending at 64% of the raw journal;
- the **multiplier** the prior spec itself identified as dominant (§2 of
  `2026-09-09-fr-goal-methodology-restoration-design.md`: "the full codebase +
  history re-read with no cache reuse across dispatches") was never attacked;
- **V2 telemetry** was deferred, so nothing can prove either half moved a number.

After this ships:

- `fr journal handoff` is **genuinely bounded** — a fixed finding collapses on
  its effective state, not only on its phase, and gate-bookkeeping entries stop
  riding in every handoff forever;
- the **executor contract carries context discipline**, so an executor stops
  paying for context it was already handed;
- `fr run status` reports **real Claude Code token figures** per phase, so the
  next run answers #464 with measurements rather than estimates.

### Non-goals

- Rebuilding anything #465 shipped (the loop, the skeleton mandate,
  refactor-or-justify, V1 accounting, the five contract norms).
- V2 transcript parsing for OpenCode and Hermes (d4 — a filed follow-up issue).
- Importing harness-level conformance testing (d4 — a filed follow-up issue).
- A hard size budget on the handoff (considered, not selected — see §6).
- Changing the journal's storage format or the plan artifact shape.
- Parallel phase execution; the isolation model; review discipline.

## 2. Background — measured, not recalled (2026-09-20)

All figures below were produced in this worktree with `uv run fr`, against the
real archived journal `docs/superpowers/implemented/journals/plans/
2026-09-18-harness-parity-matrix.md` (728 lines, 129,972 chars) and its plan.

**Handoff size by phase**, `fr journal handoff --scope plan --phase N`:

| phase | chars | share of raw |
|---|---|---|
| 1 | 35,079 | 27% |
| 2 | 47,027 | 36% |
| 3 | 46,888 | 36% |
| 4 | 50,438 | 39% |
| 5 | 66,227 | 51% |
| 6 | 83,131 | 64% |
| 7 | 68,907 | 53% |

Phase 6 is 2.4x phase 1. The bound discounts; it does not bound.

**Where the bytes are.** In phase 6's handoff, the `## Relevant context`
section — everything rendered *in full* — is ~77k of the 83k. The collapsed
`## Earlier history` is ~6k. So the collapse branch is barely reached.

**Why.** `compose_handoff` (`packages/fr/src/fr/journal/model.py:360-366`):

```python
for e in entries:
    if e.kind == "finding" and e.resolves is None and e.id in still_open:
        open_findings.append(serialize_entry(e))
    elif e.phase is None or e.phase in relevant:
        context.append(serialize_entry(e))      # FULL
    else:
        collapsed.append(_handoff_line(e))      # one line
```

Effective state is consulted only to route a finding into `## Open findings`.
Past that, `relevant = {phase, *depends_on}` decides, and two categories never
reach the collapse branch:

1. **Untagged entries — `e.phase is None` — render in full in every handoff,
   forever.** In this journal that is 14 `norefactor-*` entries, ~9.1k chars,
   present in *phase 1's* handoff as well as phase 6's. They are bookkeeping
   that #465's own refactor-or-justify gate manufactures at roughly three per
   phase. The gate created its own context tax.
2. **`fixed` findings tagged to a dependency phase render in full.** Phase 6
   declares `depends_on: [2, 3, 5]`, so it re-reads ~30 resolved findings
   (~30k chars) describing bugs that no longer exist.

The dependency scoping itself is **correct** and should not change: phase-1 and
phase-4 findings are properly absent from phase 6's handoff. The docstring's
claim that "a phase-10 executor stops re-reading 39 fixed findings in full"
holds only for fixed findings in *non-dependency* phases; real plans depend on
their predecessors, so in practice it rarely fires.

**The cost model that sets the scope.** Cache reads accumulate as the sum of
context size over *turns*, not once per dispatch: every tool call re-reads the
whole accumulated context. So the handoff is paid **once per turn**, not once
per phase. At ~21k tokens and ~150 executor turns, phase 6's handoff accounts
for roughly 3M of its 45.7M cache reads — about 7–10%. Worth fixing, and it is
the half that can be measured deterministically today. The remaining ~90% is
what the executor accumulates *inside its own session*: file re-reads, verbatim
tool output, and dead ends. That is the multiplier, and §5.B attacks it.

**Already shipped, verified on disk, and deliberately untouched:**

- `plugins/super-fr/skills/fr-plan/SKILL.md:84` — "Prefer 4–6 phases: every
  additional phase re-reads the accumulated handoff, so cost grows
  superlinearly with phase count". This is #464 suggestion 1, in place.
- `plugins/super-fr/agents/fr-phase-executor.md:69` — "**The return value is
  the only reporting channel.** … do not also send it as a message
  (super-fr#461)", mirrored into all four `.opencode/agent/` files and pinned
  by a token tripwire. #461 is delivered in prose; this spec closes it by
  verification, not by new code.

**Claude Code transcripts carry the numbers.** Checked against a live
`~/.claude/projects/<cwd-slug>/<session-id>.jsonl`: every assistant record's
`message.usage` carries `input_tokens`, `cache_creation_input_tokens`,
`cache_read_input_tokens` and `output_tokens` — exactly #464's four columns.
Records also carry `isSidechain`, `cwd`, `gitBranch`, `parentUuid` and
`sessionId`, so subagent turns are separable from orchestrator turns. V2 for
this harness is a real parser, not a hopeful one.

## 3. Principle — fix the rule, not the symptom

The same engine/transport split this repo already applies to telemetry and
dispatch applies here. The bound belongs in `fr.journal.model.compose_handoff`
as a **rule about entry state**, reachable by any shape or harness through
`fr journal handoff`. The discipline belongs in the **executor contract**,
which every harness mirrors. Neither belongs in fr-goal prose, because prose
without a mechanism is precisely what drifted between #390 and #464.

A second principle, earned from #465: **a gate that writes to the journal must
pay its own context cost.** The refactor-or-justify gate is good and stays; what
it writes must be tagged so the existing machinery can bound it.

## 4. Operator decisions (asked once, batched, 2026-09-20)

- **d1 Scope — both, sequenced.** Presented with the finding that the literal
  ask already shipped, the operator chose to build both remaining halves in one
  plan: bound-tightening as the walking skeleton (measurable immediately), then
  executor context discipline and telemetry. Rejected: bound-only (leaves ~90%
  of the cost), multiplier-only (unmeasurable until telemetry lands),
  verify-and-close (the two leaks are real and measured).
- **d2 Collapse rule — state-first.** An entry's effective state decides first:
  `fixed`/`refuted` findings collapse to one line even in dependency phases;
  open findings, decisions and discoveries stay full when dependency-relevant.
  Rejected as the primary rule: a hard size budget.
- **d3 `no-refactor-because` — tag it to its phase.** The justification keeps
  living in the journal, but carries `--phase`, so the existing dependency and
  state rules bound it. Rejected: moving it onto the plan task yaml (correct
  home, but a plan artifact shape change owing a stamp bump plus a registered
  migration); special-casing the kind inside `compose_handoff`.
- **d4 Telemetry — V2 for Claude Code only, plus two filed issues.** Parse this
  harness's transcript into V1's existing `PhaseAccounting`. Hermes and OpenCode
  stay labeled estimates. Two issues are owed *as part of this run*: backfilling
  V2 for OpenCode and Hermes, and investigating whether harness-level testing can
  be imported from `derio-net/agnostic-fr` ("convert any repo to agent-agnostic
  form, proven by cross-harness conformance tests (deterministic mock-model
  driven)" — verified 2026-09-20; private, inside the `derio-net` org, so not
  third-party).

## 5. Design

### A. The bound (pillar 1)

**A1. State-first collapse.** `compose_handoff` gains one rule ahead of the
dependency test: an entry whose **effective** state is closed collapses to one
line regardless of phase. Concretely, the `elif` becomes a three-way decision —
open findings render full (unchanged); a `finding` whose effective state is
`fixed` or `refuted` collapses; everything else (every non-finding kind) keeps
today's dependency rule.

**A resolution record collapses with its target, with one exception the first
draft of this section missed.** Re-opening is a first-class documented path
(`fr journal add --resolves <id> --state open`), and there "the record is
history" is false: collapsing it drops the only text saying why the finding is
live again, while the original report still renders in full under its stale
state. So the rule asks the fold about the finding an entry *speaks for* — its
target when it resolves one, itself otherwise. Found by the phase-2 review,
which noted the code implemented this section faithfully and the blind spot was
upstream, here.

**The collapsed line reports effective state.** A journal is an append-only log,
so each record correctly states what was true when written and `serialize_entry`
keeps printing that; a handoff reports what is true *now*. Printing the record's
own field sent an executor after ten findings the measured journal had already
closed — the cost this bound exists to remove, recovered in cheaper form. Effective state is
already computed for `## Open findings` via `open_finding_ids`, and is the same
fold `fr journal check` uses, so no new state machinery is introduced — the fix
is to consult it one branch earlier.

Rationale for keeping decisions and discoveries dependency-scoped: a decision is
never "closed" — it still constrains the phase that depends on it — and a
discovery's whole purpose is that a trap is paid for once. Only findings have a
lifecycle that makes them historical.

**A2. Untagged entries stop being unbounded — by making the choice explicit,
not by guessing.** The first draft proposed defaulting `--phase` from "the plan
cursor". Spec-review refuted it: `load_run_state` requires a run id, there is no
current-run resolver, and this repo currently has three live runs under
`docs/superpowers/runs/`, so there is no unambiguous cursor to read.

Instead, `fr journal add --scope plan` requires **either** `--phase N` **or** an
explicit `--global`. Passing neither is an error naming the consequence ("an
untagged entry renders in full in every handoff, at every phase"). Explicit
beats defaulted here: a global plan-scope entry is legitimate but rare, and the
current failure mode is that omitting the flag is both the easiest path and the
expensive one.

The root cause is verified in the shipped prose, not inferred: the executor
contract's own example reads `fr journal add --scope plan --slug <plan-slug>
--kind discovery|finding …` with no `--phase` — in the canonical agent and all
four `.opencode/agent/` mirrors. Those five lines gain `--phase N` in this PR
(the mirrors via `scripts/sync-opencode.py`, never by hand).

Scope of the CLI change: `--scope plan` only. Spec and debug journals have no
phases and are untouched, and `fr journal resolve` keeps its own path. The two
shipped callers are the executor contract and `fr-execute`, both updated here.
Existing untagged entries in live journals are unaffected — the journal artifact
shape does not change, only what new writes are required to carry, so no
migration is owed.

**A3. The measurement is the test — and the bar is the true property, not a
flattering one.** The first draft of this spec asserted that handoff size stops
growing with phase number. Categorising phase 6's real handoff refutes that, and
the refutation is recorded here rather than quietly dropped:

| category | entries | chars | fate |
|---|---|---|---|
| fixed findings | 26 | 37,556 | collapse → ~3.1k |
| `norefactor-*`, non-dependency phase | 5 | 3,515 | collapse → ~0.6k |
| `norefactor-*`, dependency phase | 9 | 6,557 | **stays full** (see A4) |
| open findings | 4 | 6,339 | stays — actionable |
| decisions + discoveries | 22 | 28,298 | stays — forward value |

Phase 6 lands near **46k** (a 45% cut from 83,131), and phase 1 near **24k**.
That is still 1.9x, because what remains is decisions and discoveries from
dependency phases — content a later phase genuinely needs. Asserting
non-monotonicity would mean dropping it, which is the one failure the handoff
contract ("missing anything → STOP, do not guess") exists to prevent.

So the shipped assertion is the property that is both true and load-bearing:
**a closed entry contributes O(1) characters to the handoff regardless of its
body size.** A unit test composes handoffs over a synthetic ten-phase journal
whose findings carry deliberately large bodies, and asserts that growing those
bodies does not grow the handoff. That assertion fails before this change (bodies
render in full) and passes after. A second test pins the ceiling on a
finding-dominated journal, where closed entries dominate and the handoff does
flatten.

**A4. The known residual, stated rather than hidden.** d3 tags
`no-refactor-because` entries to their phase, which bounds them only for phases
the current one does not depend on — 9 entries / 6,557 chars still render in full
at phase 6. This is a real limit of the chosen option, not an oversight: the
alternative that removes it (collapsing justification entries by kind) was
considered and rejected in d3. The post-merge measurement reports the residual,
and §6 keeps that option available if it proves to matter.

### B. The multiplier (pillar 2)

**B1. Executor context discipline, in the contract.** `fr-phase-executor.md`
gains a sixth norm beside the existing five, mirrored to the four
`.opencode/agent/` files and pinned by the existing token tripwire:

- do not re-read what the handoff already states — the handoff is the record of
  what earlier phases found, and re-deriving it from the code costs the context
  the handoff exists to save;
- read the narrowest thing that answers the question (`grep`/`sed -n` over a
  range, not the whole file), and do not re-read a file you have already read in
  this session unless you changed it;
- never paste verbatim tool output into the return — the return carries the test
  command and a pass/fail summary, and the journal carries the detail. This is
  the caller-side half of #461 that the issue itself flagged as
  under-attributed.

**B2. `fr-goal`'s dispatch brief stops asking for what the contract forbids.**
#461 records that the orchestrator's own prompts asked executors to paste
verbatim test output, inflating both copies. §5's brief guidance says the
opposite explicitly, so the caller and the contract agree.

### C. V2 telemetry — Claude Code (pillar 2)

`fr run` gains a harness-scoped transcript reader, `fr.run.telemetry`, with one
concrete implementation for Claude Code. It locates the transcript for a run's
session, sums `message.usage` over the records belonging to a dispatched
`(phase, member)` unit, and records `input_tokens`,
`cache_creation_input_tokens`, `cache_read_input_tokens` and `output_tokens`
into the existing `PhaseAccounting` for that unit.

- **Attribution — corrected by phase 1's capture, which is what phase 1 is
  for.** This section originally said subagent turns carry `isSidechain: true`
  in the orchestrator's stream and a dispatch is attributed by walking
  `parentUuid` back to the `Agent` tool_use. **That is wrong**, and the
  captured fixture disproves it. The real shape:

  ```
  ~/.claude/projects/<cwd-slug>/
      <session-id>.jsonl                      # orchestrator: isSidechain false throughout
      <session-id>/subagents/
          agent-<agentId>.jsonl               # subagent: isSidechain true throughout
          agent-<agentId>.meta.json           # carries toolUseId, agentType, model
  ```

  The two streams are **separate files**. Attribution is file-to-file: the
  subagent file's companion `agent-<agentId>.meta.json` carries the `toolUseId`
  of the `Agent` tool_use in the orchestrator stream that dispatched it. Three
  further corrections, each pinned by a test: `parentUuid` inside a subagent
  file chains only that subagent's own turns and starts at `null`; `sessionId`
  is the *orchestrator's*, so attribution cannot key on it (the subagent's own
  identity is `agentId`, absent from orchestrator records); and `cwd` stays
  pinned to the harness's launch directory even when the agent worked entirely
  inside a worktree, so it cannot identify a phase either.

  The timestamp-window fallback is retained as a *fallback only* — serial
  dispatch makes it unambiguous — but it is no longer needed as the primary
  mechanism, because `toolUseId` is an exact key.

  Two smaller shape facts the capture added: `message.usage` carries more than
  the four named keys (`cache_creation`, `output_tokens_details`,
  `server_tool_use`, `service_tier`, `inference_geo`, `speed`, sometimes
  `iterations`), so a parser must **project** onto the four rather than assume
  the object's shape; and a session file interleaves many record types with no
  usage at all, so a parser must select on `type == "assistant"` first.
- **Shape:** `PhaseAccounting` gains four optional, defaulted int fields. Per
  `.claude/rules/artifact-versioning.md` this **is** a shape change — `RunState`
  is `extra="forbid"`, and a released `fr` reading a cursor carrying the new keys
  raises. The plan therefore ships the stamp bump, a registered migration, and
  the structure validator update **in the same PR**, and runs
  `fr migrate artifacts --yes` over this repo's own artifacts.
- **Degradation is loud, never silent.** No transcript, an unreadable one, or an
  unattributable unit records nothing and says so in `fr run status`; the V1
  estimate line remains and stays labeled an estimate. A measured figure and an
  estimated one are never rendered as the same thing.
- **Not a harness API.** Nothing here asks the harness for tokens; it reads a
  file the harness already writes. OpenCode and Hermes keep V1 estimates until
  the filed follow-up lands.

### D. Closing the issues honestly

`#461` is delivered and is closed by **verification, not code**: a test asserts
the norm is present in the canonical agent and in all four OpenCode mirrors
(extending the existing token tripwire rather than adding a parallel one). The
PR body states plainly which parts of #464 shipped in #465, which ship here, and
which are deferred to the two filed issues — so the issue trail records that the
first three suggestions were already answered.

Two issues are filed as part of this run (d4): V2 for OpenCode and Hermes, and
the `derio-net/agnostic-fr` harness-conformance investigation.

### E. Phase shape — this plan takes its own advice

fr-plan's guidance is "prefer 4–6 phases". A plan about the cost of phase count
that shipped ten phases would refute itself. Target: **five phases**, phase 1
the walking skeleton per the shipped mandate — the measurement harness (A3) on a
synthetic journal with CI green — so every later phase is verified against a
real before/after number rather than against a reading of the diff.

## 6. Alternatives considered

- **Hard size budget on the handoff** (`--max-chars`, collapse oldest-first
  until under it). Guarantees a true bound at any journal size, but can drop an
  entry the phase needed, which is the one failure the handoff contract
  ("missing anything → STOP, do not guess") is built to prevent. Rejected as the
  primary rule (d2); still available later as a backstop if A1/A2 prove
  insufficient on a pathological journal.
- **Recency window.** Rejected already by #465 (d2 there) and still wrong:
  it drops dependency-relevant old findings.
- **Moving `no-refactor-because` onto the plan task yaml.** The correct home on
  the merits, but it is a plan artifact shape change owing a stamp bump and a
  registered migration, for a bookkeeping line. Rejected (d3) as disproportionate.
- **Special-casing the `norefactor-` prefix in `compose_handoff`.** Cheapest,
  but it teaches the composer about one caller's id convention and leaves
  untagged entries unbounded in general. Rejected (d3).
- **Bound-only, or multiplier-only.** Rejected by d1: the bound alone leaves
  ~90% of the cost, and the multiplier alone cannot be shown to have worked
  until telemetry exists.
- **V2 for all three harnesses now.** Rejected (d4): each parser is
  unverifiable without a real run on that harness, so two of the three would
  ship unproven. Filed instead.

## 7. Test Plan

Unit (`tests/unit`):

- `compose_handoff` state-first collapse — a fixed finding tagged to a
  dependency phase collapses to one line; an open finding in the same phase
  still renders full; decisions and discoveries keep dependency scoping; a
  resolution record collapses with its finding.
- **Closed entries cost O(1)** — handoffs composed over a synthetic ten-phase
  journal whose closed findings carry deliberately large bodies; growing those
  bodies must not grow the handoff (the assertion that fails before this change).
  A second case pins the ceiling on a finding-dominated journal.
- `fr journal add --scope plan` requires `--phase N` or `--global`; passing
  neither is an error naming the consequence; `--global` still yields an
  untagged entry; spec and debug scopes are unaffected.
- Contract tripwires — the sixth norm present in the canonical agent and all
  four `.opencode/agent/` mirrors; the #461 norm asserted in the same place (§D).
- Telemetry — usage summed per unit from a fixture transcript; sidechain records
  attributed to the right unit; missing/unreadable/unattributable transcripts
  degrade loudly and leave the estimate labeled; `fr run status` renders measured
  and estimated figures distinguishably.
- Artifact versioning — the `run` stamp bump, its registered migration, and
  `fr validate artifacts` over this repo's own artifacts.

Operator-driven, post-merge:

1. Run a small real `/fr-goal` (3 phases) and confirm `fr run status` reports
   **measured** Claude Code token figures per phase, not estimates.
2. Compare that run's per-phase handoff sizes against the before-figures in §2,
   and report the A4 residual (`norefactor-*` entries in dependency phases).
3. Confirm the two follow-up issues exist and are accurate.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-09-20-bounded-executor-handoff | `derio-net/super-fr` | `2026-09-20-bounded-executor-handoff` | — |

## 8. Acceptance rows (born here; presented at spec review)

| id | capability | acceptance | level |
|---|---|---|---|
| `handoff-closed-entries-bounded` | fr-goal-cost | A closed journal entry (fixed or refuted finding, resolution record) contributes a constant amount to an executor handoff regardless of its body size, including within dependency phases. | unit |
| `handoff-entries-always-tagged` | fr-goal-cost | Writing a plan-scope journal entry forces an explicit choice between a phase tag and `--global`, so no entry renders in full in every handoff by accident. | unit |
| `executor-context-discipline` | fr-goal-cost | The executor contract forbids re-deriving what the handoff states and pasting verbatim tool output into the return, on every harness that mirrors the agent. | unit + tripwire |
| `run-telemetry-measured-claude-code` | fr-goal-cost | `fr run status` reports real per-phase token figures parsed from the Claude Code transcript, and degrades loudly to a labeled estimate when it cannot. | unit |
