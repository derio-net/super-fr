# One record per unit — identity, cost, review and liveness on the run cursor

- **Issues:** extends [#503](https://github.com/derio-net/super-fr/issues/503) /
  [#499](https://github.com/derio-net/super-fr/issues/499); absorbs
  [#430](https://github.com/derio-net/super-fr/issues/430) (via #517's branch),
  [#518](https://github.com/derio-net/super-fr/issues/518), and the cost-attribution half of
  [#464](https://github.com/derio-net/super-fr/issues/464). Already folded in: #496, #500, #501
  (gh#519's branch).
- **Date:** 2026-09-20
- **Status:** design
- **Delivers in:** PR #508, on `feat/phase-holder-identity` (operator decision)

## 1. Background — one seam, five specs

On 2026-09-20, five sessions worked one seam in parallel: *what the orchestrator intends
versus what actually happened to a dispatched unit.* #503 (who holds it), #499 (don't dispatch
it twice), #464 (what it cost), #430 (was it reviewed), #518 (is anyone still working). Each
got its own spec. The run cursor now shows the seams.

### 1.A Four records, one key space

| record | home | keyed by | cardinality |
|---|---|---|---|
| `StepRecord.items` | cursor, per step | unit | one state |
| `StepRecord.dispatch` (#508) | cursor, per step | unit | **list** — every attempt |
| `RunState.accounting` (#464) | cursor, **top level** | unit | **one** — overwritten |
| journal `kind=review` (#517) | **journal** | **phase number** | one per phase |

On this branch's own cursor: 12 `accounting` keys, 10 `dispatch` keys, 9 overlapping — two
maps describing the same dispatches, already drifted.

### 1.B What the split cost, concretely

- **A live data-loss defect.** `dispatch[unit]` *appends*; `accounting[unit]` *assigns*, and a
  redispatch refreshes the snapshot by design (gh#519's
  `test_redispatch_refreshes_the_dispatch_time_and_that_units_snapshot`). So after
  `claim --abandoned` → `advance`, fr keeps the abandoned agent's **identity** and discards its
  **cost**. `_with_measurement`'s docstring states the broken assumption outright — *"serial
  dispatch makes that window hold exactly one dispatch"* — which `--redispatch` violates.
  #464's own goal, attributing spend to a dispatch, is defeated by a feature #508 added.
- **Two `schema_version: 3`s.** gh#514's telemetry migration and #508's dispatch-holder
  migration were both written `2 → 3`. A cursor written on either branch was unreadable on the
  other while both claimed the same stamp; neither PR's CI could see it.
- **Two #499 refusals that disagree.** #508 reads the dispatch record; gh#519 reads
  `items`/`state`. After `claim --abandoned` they give opposite answers, so the merged code
  breaks #508's own recovery path (decision u1 settles this).
- **Duplicated designs:** `PhaseSpec.tier`, the accounting renderer, the `from_phase`
  resolution, the two-mirror note in `AGENTS.md` — each built twice, one copy discarded.

### 1.C The same witness, five times

Every one of these issues is the sentence *"there is no state in which X is distinguishable
from not-X"*:

| issue | indistinguishable pair | witness |
|---|---|---|
| #503 | agent holding a phase / nobody holding it | an open attempt naming the agent |
| #499 | not yet dispatched / dispatched, awaiting resolve | an open attempt |
| #464 | spend of attempt 1 / spend of attempt 2 | cost recorded **per attempt** |
| #430 | review skipped / review passed clean | evidence recorded at resolve |
| #518 | run stalled / run still working | open attempts + cursor readiness |

One record per unit, holding its attempts, answers all five.

## 2. Goals / non-goals

**Goals**

1. One map, one home, one key space: `StepRecord.units` replaces `items`, `dispatch`, and
   `RunState.accounting` (decision u4).
2. Cost lives on the attempt — estimate *and* measurement (u2) — so a redispatch loses nothing.
3. A held unit is witnessed by its open attempt, and by nothing else (u1).
4. An obligation's *satisfaction* is recorded on the cursor at resolve time, with a reference
   to its *content* in the journal (u3).
5. `fr run check` can say a run is **idle** (advanceable, nobody working) or **stalled** (held
   implausibly long), and a Stop hook makes the first one an enforced gate on Claude Code (u5).

**Non-goals**

- **Verification of reported fields.** Unchanged from #508: the orchestrator's claims stay
  claims. Visibility, not enforcement.
- **The reflex half of #518.** The loop's cadence ending on a subagent report, and output
  style competing with the skill's autonomy contract, are prose problems. §4.G fixes what an
  artifact can; §4.H states the rest as prose and does not pretend otherwise.
- **Reading harness-private state.** No transcript spelunking beyond what gh#514's
  `fr.run.telemetry` already does for measurement.
- **Cross-session coordination** ("which session is working which issue") — the batching
  failure that motivated this spec is a process finding, recorded in §8, not designed here.

## 3. The line this spec redraws: control vs. content

`fr/run/model.py` has always said the cursor is the *control* log — "which step, what it
emitted, whether it succeeded" — and the journal is the *content* log. #517 kept reviews
wholly in the journal, honouring that. This spec crosses the line **deliberately and
narrowly**:

> An obligation's **satisfaction** is control. Its **content** is journal.

"Phase 2 was reviewed" is a fact about *where the run is* — control. *What the review found*
is content. The cursor records the first with a pointer to the second; it never copies
findings. This is the same shape `emitted` already has (the cursor records *that* a spec was
emitted and where; it does not contain the spec), so the precedent was always there.

## 4. Design

### 4.A The model

```python
class ContextEstimate(BaseModel):      # V1 sizes — was PhaseAccounting's first half
    journal_entries: int = 0
    journal_lines: int = 0
    handoff_chars: int = 0
    spec_bytes: int = 0
    plan_bytes: int = 0

class MeasuredTokens(BaseModel):       # V2 — all four or none (gh#514's invariant, kept)
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int

class Attempt(BaseModel):              # was DispatchRecord, now carrying its own cost
    dispatched: str
    agent: str | None = None
    agent_type: str | None = None
    harness: str | None = None
    model: str | None = None
    returned: str | None = None
    outcome: Literal["done", "failed", "abandoned"] | None = None
    estimate: ContextEstimate | None = None     # what fr assembled for THIS attempt
    measured: MeasuredTokens | None = None      # what THIS attempt burned

class UnitRecord(BaseModel):
    state: UnitState | None = None     # pending|running|done|failed|manual; see §4.B
    attempts: list[Attempt] = []       # oldest first; open = last with returned None
    evidence: dict[str, str] | None = None      # obligation name -> journal entry id
```

`StepRecord.units: dict[str, UnitRecord] | None` replaces `items` and `dispatch`.
`RunState.accounting` is removed. `MeasuredTokens` being a sub-model makes gh#514's
"all four or none" invariant **structural** — a partial measurement cannot be represented,
so `validate_run`'s partial-measurement check disappears rather than moving.

### 4.B Key grammar and the state rule

Three key forms, each with a rule `validate_run` enforces:

- `phase/<n>/<member-id>` — a grouped unit. Carries `state`.
- `step/<step-id>` — a flat `kind: agent` step. **Carries no `state`**: `StepRecord.state` is
  that fact's one home, and this spec exists because facts with two homes drift.
- `phase/<n>` — gh#496's manual-phase marker. `state: manual`, `attempts` empty, always.

### 4.C The witness (decision u1)

A unit is **held** iff its last attempt is open. `_held_record` is the one predicate;
`state == "running"` is never consulted to refuse. The unified `_already_running_refusal`
(already merged) names the holder from the attempt. A cursor adopted from disk has units with
no attempts; there the refusal falls back to `ALREADY RUNNING (dispatched <at>)` — already
built, already tested.

`claim --abandoned` closes the attempt and leaves `state: running`; the unit is not held, so
`advance` re-briefs and appends. `run-dispatch-abandon` survives;
`run-advance-refuses-running` is **re-worded to the same claim and merged into
`run-dispatch-refuses-second`** via `fr acceptance set-status` notes — one behaviour, one row.

### 4.D Cost per attempt (decision u2)

- `advance` writes `estimate` onto the attempt it opens (it already computes it, as
  `_accounting_snapshot`).
- `resolve` writes `measured` onto the attempt it closes. The measurement window becomes
  `[attempt.dispatched, attempt.returned]` — **per attempt**, which repairs
  `_with_measurement`'s "exactly one dispatch" assumption instead of restating it.
- `claim --abandoned` *also* attempts a measurement for the attempt it closes: an abandoned
  agent's spend is exactly the spend worth seeing.
- `fr run status`'s accounting section (gh#514's `_print_accounting`, kept) renders per
  attempt, under its unit, beside the holder line. Totals sum attempts, so a redispatched
  unit's total finally includes the abandoned one.

### 4.E Evidence (decision u3) — folding in gh#517

- Manifest `Step` gains an optional `evidence: tuple[str, ...] = ()`. The shipped `fr-goal`
  shape declares `evidence: [review]` on the `review-phase` member.
- `fr run resolve … --state done` on a unit whose step declares evidence **refuses** without
  `--evidence review=<journal-entry-id>`, and verifies the id against the plan journal using
  gh#517's own rule (`reviewed_phases`: a `kind=review` entry with `phase=N`). Verified ids
  are stored in `UnitRecord.evidence`. `--state failed` needs no evidence — a failed review
  unit met no obligation.
- gh#517's `fr journal check --require-reviews` **stays**, as the gate for plans with no
  cursor (adopted or pre-cursor work). Two gates, one rule, one verifier.
- **Reviews resolved before this gate existed are not retroactively failed.** The migration
  cannot invent evidence and does not try; `fr run check` reports such a unit as
  `done, unevidenced (predates the evidence gate)` — visible debt, never a failure. An
  obligation cannot be enforced backwards in time, and pretending otherwise would fail
  every in-flight run on the day the plugin updates.
- **A shape that declares no `evidence:` resolves exactly as before.** The gate is opt-in per
  step, so repo-authored workflows are untouched until they ask for it.
- "Review skipped" and "review passed clean" are now different states on the cursor:
  `done` with evidence, versus a unit that cannot reach `done` at all.
- **Mechanically:** branch `feat/journal-require-reviews` is merged into this one as the
  plan's first phase, as gh#519's was; its PR #517 closes as superseded.

### 4.F Migration — `run` 4 → 5, the first body-rewriting run migration

Both prior run migrations were stamp-only. This one **rewrites the body**:

1. each `items[k] = s` → `units[k] = {state: s}` (manual markers keep `state: manual`);
2. each `dispatch[k] = [...]` → `units[k].attempts`;
3. each `accounting[k]` → split into `estimate`/`measured` and attached to the **last**
   attempt of `units[k]`; a unit with accounting but no attempt (pre-#508 cursors) gets one
   synthesized attempt with `dispatched = accounting.at` and no identity — stated, not
   invented: that is when fr briefed it, and it is the only fact fr has;
4. `RunState.accounting` dropped.

It parses first and refuses rather than certifying a cursor it cannot read (the
`run_provenance` invariant), and is **idempotent on its output**.

**The legacy reader — a flaw this spec's first draft had.** Every existing run migration
"parses first" with `parse_run_state`, i.e. with the LIVE model. That was sound only because
every prior change was additive, so the live model stayed a superset of every old shape. This
change **removes** `items`, `dispatch` and `accounting` from an `extra="forbid"` model — so a
v2 cursor carrying `items` no longer parses, and the chain `2 → 3 → 4 → 5` would refuse every
old cursor at its FIRST hop, stranding exactly the files the framework exists to carry.

So the prior shape is frozen as `fr.run.legacy.RunStateV4` (a superset of versions 1–4, which
it can be precisely because those were all additive), and every hop up to and including
`4 → 5` reads with it; the live `RunState` is v5 only. The general rule goes into
`.claude/rules/artifact-versioning.md`: *the first migration that removes or moves a field
freezes the prior shape as a legacy model, and no migration may validate an old file against
the live one.* Found by auditing the blast radius after the operator called this rewrite
what it is.

Two edges, decided rather than left to the implementer:

- **A v4 cursor with a PARTIAL measurement** (some of the four token fields) is already
  invalid under gh#514's validator. The migration **refuses that cursor** and names the
  field — it never drops a figure silently to make `MeasuredTokens` constructible.
- **A cursor the migration cannot fully convert is left byte-identical.** A body-rewriting
  migration can half-write in a way a stamp-only one cannot, so the rewrite is built in
  memory and written once, through the framework's existing atomic writer. Per
`.claude/rules/artifact-versioning.md` the same PR runs `fr migrate artifacts --yes` over
this repo's own cursors. The chain test asserts every hop — `[2, 3, 4, 5]` — because that
assertion is the only collision guard this repo has (see §8).

### 4.F.1 Every other reader and writer — the blast radius, audited

`run_cmd.py` is not the only code that knows these maps:

- **`fr run adopt`** (`fr/run/adopt.py`) is the first WRITER of `items` — it records which
  phases of a half-implemented plan are already done. It now writes `units`, and a phase it
  finds complete becomes a `done` unit with **no attempts**: fr never dispatched it, and an
  empty list is the honest record of that. Inventing an attempt to look uniform would be the
  exact fabrication §3 of #508's spec forbids.
- **`fr/run/provenance.py`** walks a group's member keys for `fr run gates`; it reads `units`.
- **`fr/run/telemetry.py`**'s `measured_fields()` becomes `MeasuredTokens`.
- **The bridge is not coupled.** `fr_dispatch`, `fr_vk` and `fr_cncd` never load a run
  cursor — their `items` are work items and API payloads. Recorded here because AGENTS.md's
  bridge-audit rule requires the check, and so nobody has to re-derive the answer.
- **Archived cursors** under `implemented/runs/` (8 today) stay frozen: nothing re-parses
  them, and the migration's locator does not reach them.

### 4.G Liveness (decision u5) — the artifact half of #518

Two readings of the one record, both in `fr run check`:

- **idle** — the run is *advanceable and nobody is working*: cursor step not done, no gate
  pending, no open attempt, no failed unit. This is #518's exact observation (*"`fr run
  advance` would have printed the next phase's brief immediately"*). `fr run check --idle`
  exits **3** on it, naming the next action.
- **stalled** — an open attempt older than a threshold (`--stalled-after`, default 120m):
  #503's 11.5-hour executor, visible from fr instead of from the harness's private files.
  Reported, never a failure: fr cannot tell a long phase from a dead agent, and says so.

A Claude Code **`Stop` hook**, `fr-run-idle-guard.sh`, runs `fr run check --idle` for the
session's bound workspace (gh#500's session binding, already merged, is what makes the
lookup possible) and blocks the stop with the next command when the run is idle. It stays
silent in every legitimate case: a pending operator gate, a manual phase, a held unit (a
turn that ends while a background executor works is *correct* on Claude Code), a failed
step, a finished run, or no run at all. Fail-open on any error — a guard that wedges a
session over its own bug is worse than the stop it prevents.

One wrinkle the hook must tolerate, noted rather than fixed here: the session binding
file records `harness: "claude"` while `fr.harness.HARNESSES` says `"claude-code"` — two
vocabularies for one fact, from two subsystems. The hook keys on `worktree` only, so it is
unaffected; unifying the vocabularies is its own small issue.

This is a new enforcement surface, so it owns a `parity.yaml` row: `enforced` on
claude-code; `absent` on OpenCode and Hermes with a `scope_note` naming what each lacks.

### 4.H The half no artifact fixes

fr-goal §5/§6 gain two sentences of prose, stated as prose: the per-phase loop ends on a
*dispatch*, not on a report — report and dispatch in one turn; and the skill's autonomy
contract outranks an output-style preference. No tripwire can enforce a reflex; the Stop
hook catches its consequence instead.

## 5. Alternatives rejected

- **Measurement per attempt, estimate per unit** — the smaller cost-home fix. Rejected by the
  operator (u2): a re-dispatched unit re-assembles its context, so the estimate is per
  attempt too; and a split home would be this spec recreating its own subject.
- **Cursor reads the journal for reviews** (no cursor-side record). Honours the old line
  exactly but leaves "done without review" representable; the evidence gate makes it
  unrepresentable (u3).
- **Staged delivery** (fix cost home now, collapse later). Rejected (u4): an intermediate
  shape is one more thing for a parallel branch to diverge from.
- **Both witnesses must agree.** Wedges a run on a bad merge; and two witnesses for one fact
  is the defect, not a safeguard (u1).

## 6. Test Plan

**Gating the PR:**

1. `UnitRecord`/`Attempt` round-trip; a v4 cursor migrates to v5 with the body rewritten per
   §4.F, byte-stable on re-run; an unreadable cursor is refused and the rest still migrate.
2. The migration of a cursor with accounting-but-no-dispatch synthesizes exactly one
   identity-less attempt; with both, cost lands on the **last** attempt.
3. **The u2 regression:** `advance` → `claim --abandoned` → `advance` → `resolve`: both
   attempts retain their own estimate, and a measurement taken for each; totals include both.
4. **The u1 regression:** after `claim --abandoned`, `advance` re-briefs (exit 0) and
   appends; a unit with an open attempt is refused naming the holder; an adopted cursor
   falls back to ALREADY RUNNING.
5. `validate_run` enforces the three key forms' rules (§4.B): state on `step/` refused;
   attempts on a `phase/<n>` manual marker refused; at most one open attempt, and it is last.
6. `resolve --state done` on `review-phase` refuses without `--evidence review=<id>`,
   refuses an id that is not a `kind=review, phase=N` entry, accepts a real one, stores it;
   `--state failed` needs none. gh#517's `--require-reviews` still passes/fails as before.
7. `fr run check --idle` exits 3 exactly on: advanceable cursor, no gate, no open attempt,
   no failure — and 0 in each of the six legitimate-stop cases of §4.G, one test apiece.
8. Stalled: an open attempt older than the threshold is reported; exit code unchanged.
9. `fr-run-idle-guard.sh`: blocks an idle stop with the next command; silent in all six
   legitimate cases; fail-open on a broken `fr`. `parity.yaml` row + tripwire pairing pass.
10. Every gh#519 and gh#517 grafted test passes against the unified model.
11. `fr validate artifacts` over this repo's own migrated cursors; full CI gate.

**Post-merge, operator-driven** (extends #508's items 13–15):

16. On the live Claude Code run of item 13: `fr run status` shows cost **under each
    attempt**, and after a deliberate `claim --abandoned` + re-dispatch, both attempts'
    costs are present.
17. End a turn mid-run with the run idle: the Stop hook blocks and names `fr run advance`.
    End one while an executor works: it does not.
18. Try to resolve a `review-phase` unit `done` with no review entry: refused.

## 7. Acceptance rows

Eighteen rows, grouped by what could go wrong. A rewrite this size is pinned by what it
could **regress** at least as much as by what it adds — the operator's call, and the audit
it prompted found a chain-breaking flaw and an unmentioned writer before any code existed.

**Upgrade safety** — the riskiest part of a shape-*removing* change

| id | claim |
|---|---|
| `run-unit-record-migrates` | a v4 cursor's items, dispatch and accounting migrate into one unit map with no loss, idempotently |
| `run-legacy-cursors-still-migrate` | a v1/v2/v3 cursor still reaches the current version after fields left the live model |
| `run-migration-atomic-per-cursor` | an unconvertible cursor is left byte-identical, never half-rewritten; the rest still migrate |
| `run-upgrade-mid-run-keeps-holder` | a run upgraded while a phase is held still refuses a second dispatch and names the holder |

**The witness**

| id | claim |
|---|---|
| `run-adopted-cursor-refuses-double-dispatch` | an adopted cursor with no attempts still refuses to re-brief a running unit |
| `run-adopt-writes-unit-records` | `fr run adopt` writes a current cursor; complete phases are done units with no invented attempts |

**Cost**

| id | claim |
|---|---|
| `run-unit-cost-per-attempt` | a redispatched unit keeps every attempt's cost; totals include abandoned attempts |
| `run-abandoned-attempt-is-measured` | an abandoned attempt's spend is measured when it is abandoned |
| `run-status-cost-under-holder` | status shows each attempt's cost beneath its holder, estimate and measurement never blurred |

**Evidence**

| id | claim |
|---|---|
| `run-unit-review-evidence` | a review unit cannot be resolved done without journal evidence |
| `run-review-evidence-cannot-be-faked` | evidence must be a review entry for that same phase |
| `run-legacy-reviews-not-retro-failed` | pre-gate reviews show as unevidenced debt, never retroactively failed |
| `workflow-without-evidence-unchanged` | a shape declaring no evidence resolves exactly as before |

**Liveness**

| id | claim |
|---|---|
| `run-idle-detected` | `fr run check --idle` separates an advanceable-and-idle run from every legitimate stop |
| `run-idle-stop-guard` | on Claude Code, ending a turn on an idle run is blocked with the next command |
| `run-idle-guard-allows-waiting` | ending a turn while a dispatched executor works is allowed |
| `run-idle-guard-never-wedges` | the guard is silent with no bound run and fails open on any fr error |
| `run-stalled-reported-not-failed` | a unit held past the threshold is reported with its age, never failed |

Existing rows carried and re-pointed: `run-dispatch-holder-recorded`,
`run-dispatch-refuses-second` (absorbs gh#519's `run-advance-refuses-running`),
`run-dispatch-abandon`, `run-dispatch-harness-neutral`, `run-manual-phase-never-dispatched`,
`run-resolve-teaches-item-flag`, `run-start-binds-session`,
`run-telemetry-measured-claude-code` (re-pointed at per-attempt storage).

## 8. Process finding — recorded, not designed

Five sessions, one seam, no shared view. Costs observed in one day: two discarded
implementations, two `schema_version: 3`s, two refusals for one issue, three merges into this
branch, and a test that pinned a defect the sibling branch had already fixed. Two guards
would have been cheap: **batch issues that name the same structure into one spec**, and a
**registry-side check that two open branches have not allocated the same artifact version**
(today the chain-hop assertion is the only thing that notices, and only after merge).
Neither is designed here; both are why this spec exists.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
