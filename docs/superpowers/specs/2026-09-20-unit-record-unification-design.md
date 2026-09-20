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
    session: str | None = None                 # harness session that dispatched it (§4.D.1)
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
- **What "exactly one dispatch" actually assumes — and why this spec stops relying on it.**
  The assumption is *run-wide and temporal*, not per-phase: gh#514's `select_dispatch` picks
  the one subagent transcript whose first record falls inside a TIME WINDOW, across the whole
  session. It holds today only because `fr run` enforces one writer at a time
  (`_resolve_member` refuses while another unit is running, and parallel execution is
  `fr apply --to <runner>`'s job, which never touches a run cursor). Two overlapping
  dispatches — two phases in parallel, or a redispatch racing a slow return — put two
  transcripts in one window, and `select_dispatch` then *"yields nothing"*: honest, but the
  measurement is lost.
  The unit record removes the dependency: an attempt that was **claimed** carries the
  harness's own `agent` id, which is also the transcript's filename
  (`subagents/agent-<agentId>.jsonl`). Measurement selects **by agent id** — exact under any
  concurrency — and falls back to the window only for an unclaimed attempt. The record
  itself is concurrency-safe (each unit owns its attempts); "one writer" is a policy of the
  shared worktree, never a limit of the model, and a future parallel shape must not have to
  rediscover that.
- `claim --abandoned` *also* attempts a measurement for the attempt it closes: an abandoned
  agent's spend is exactly the spend worth seeing.
- `fr run status`'s accounting section (gh#514's `_print_accounting`, kept) renders per
  attempt, under its unit, beside the holder line. Totals sum attempts, so a redispatched
  unit's total finally includes the abandoned one.

### 4.D.1 Stop, push, pick the run up on another host with another agent

The operator's question, and the first draft had no answer. **The cursor travels with the
branch. Nothing else does** — not the transcripts (`~/.claude/projects/…` is host-local), not
the session binding (`~/.cache/fr/sessions/` is host-local), not the agent, and not any work
the executor had not committed.

gh#514's `measure_unit` finds the transcript from the *current process environment*, so it
is session-local already: even on the SAME host, a new session cannot measure an attempt a
previous session dispatched. And the time-window fallback is actively dangerous across
sessions: host B resolves host A's open attempt at T2, the window `[T0, T2]` happens to
contain exactly one subagent that host B's *own* session dispatched for something unrelated,
and that stranger's cost is recorded against host A's attempt. Wrong, and plausible-looking.

So every attempt records the **`session`** that dispatched it — fr derives it from its own
environment when it opens the attempt, the same way it derives `harness` — and:

- a transcript is looked up by **(session, agent)**, in the *recorded* session's directory,
  not the current one. Same host, new session: found, measured. Another host: not there.
- the window fallback is allowed **only when the attempt's session IS the current session**.
  Otherwise the cost is `not observable from here` — never zero, never guessed, never
  borrowed. No hostname is recorded: a missing session directory already says "elsewhere",
  and a hostname in a committed cursor of a public repo is identity nobody needs.

What the second host sees, in order: the phase is **held** (its attempt is open), so
`advance` refuses — and says the holder was dispatched *from another session and cannot be
observed from here*, so the operator is not left waiting on an agent that died with its
host. Recovery is the designed one: `claim --abandoned` (or `advance --redispatch`), which
re-briefs from the last **commit**; the orphaned attempt stays in the unit's history with its
cost unobservable. The new session must be bound (`fr isolation up --branch … --session …`)
for the idle guard to find the run at all.

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

**One harness-neutral predicate, thin per-harness adapters.** The first draft said
"OpenCode and Hermes have no Stop hook". That was asserted, not checked — the same error
gh#494 documents, where a parity row said `absent` for a reason that did not survive the
binary. The operator supplied a survey of stop-like hooks across harnesses; per this repo's
standard it is a **lead, not a fact**, so what could be checked on the authoring machine was:

| harness | capability tier | basis |
|---|---|---|
| Claude Code | **block** — `Stop` hook returns `decision: "block"` + reason | known; exercised in the plan's hook phase |
| OpenCode 1.18.31 | **re-prompt** — cannot block a stop, can continue the session | **verified installed:** `session.idle` event in the SDK types, and a `/session/{id}/prompt_async` endpoint a plugin's `client` can call |
| Copilot CLI 1.0.84 | reportedly block (`agentStop`) | hooks system **verified installed** (`hooks` keyed by event; a user hook already exists here); the event's blocking semantics are not |
| Codex CLI, Agy | reportedly block | not installed here — unverified |
| Hermes | reportedly **observe** only (non-blocking stop events) | not installed here — unverified; the repo already registers `pre_tool_call` / `pre_llm_call` hooks on it |

So the design splits in two:

- **The predicate is fr's and is harness-neutral:** `fr run check --idle [--format json]`
  exits 3 on an idle run and prints the next command. Every adapter calls it; none
  re-derives it.
- **Adapters are as strong as their harness allows.** Shipped in this PR: Claude Code
  (**block**, `fr-run-idle-guard.sh`) and OpenCode (**re-prompt**, in `fr-opencode-plugin`:
  on `session.idle`, if the predicate says idle, send the next command back into the
  session). The OpenCode adapter stays `partial` in `parity.yaml` until a live run proves a
  plugin-originated prompt on idle actually executes — the #494 standard. Hermes is
  `absent` with a scope_note naming the observe-only lead; Codex and Copilot CLI are
  `unsupported` today across the whole matrix (fr ships nothing for them), and their rows
  gain a note that a block-tier adapter is ~20 lines once they are onboarded.

Both shipped adapters find the run through the session binding (gh#500, already merged),
stay silent in every legitimate case — a pending operator gate, a manual phase, a **held**
unit (a turn that ends while a background executor works is *correct*), a failed step, a
finished run, no run at all — and fail open on any error.

**The loop breaker.** A guard that always blocks can trap a session: `advance` keeps
failing, or the model keeps stopping, and the hook keeps refusing. (The operator's survey
notes one harness ships a built-in cap on consecutive continuations for exactly this.) So
the guard acts **at most once per cursor position**: it remembers, host-locally, the
position it last acted on for this session, and lets the stop through if nothing has moved
since. Claude Code also passes `stop_hook_active` when a continuation was itself caused by
a stop hook; the guard honours it as a second, independent brake.

This is a new enforcement surface, so it owns a `parity.yaml` row with the states above.

### 4.H The half no artifact fixes

#518 names three causes, and **none of them is a state problem**:

1. *The loop's cadence ends on a report.* An executor's return arrives as a message, and the
   natural reply to a delivered report is to summarise it and stop.
2. *Review-and-fix is done inline*, so every iteration ends with the orchestrator holding a
   pile of findings — peak pressure to report, exactly where the skill wants no pause.
3. *Output style competes with the skill's contract.* An `explanatory` style tells the model
   to surface insight as it goes; nothing says the skill's autonomy contract wins.

A record describes what happened. It cannot change what a model is *inclined to do* at a
turn boundary — that is what "reflex" means here. So the fix has two layers, and this spec
is explicit about which is which:

- **The prose layer (weak, portable).** fr-goal §5/§6 are re-cut so an iteration's natural
  END is a dispatch, not a report: *"when an executor returns — review, fix, push, then in
  the SAME turn `fr run advance` and dispatch the next unit; report after dispatching, never
  instead of it."* And one sentence of precedence: *"this skill's autonomy contract outranks
  an output-style preference; insight is welcome, ending a turn on it mid-run is not."*
  This is exactly the kind of instruction #518 watched fail three times in a day, which is
  why it is not the only layer.
- **The artifact layer (strong, Claude Code only).** §4.G's Stop hook does not try to fix
  the reflex; it catches its CONSEQUENCE — a turn ending while the run is idle — and hands
  back the next command.

The two compose: prose lowers how often the guard fires; the guard catches what prose
misses. Where a harness has no shipped adapter — Hermes today — **prose is all there is**,
and the `parity.yaml` row says so rather than implying parity; on OpenCode the adapter
continues the session instead of blocking the stop, which is weaker and is declared as such. This session is its own
evidence: it ran in `explanatory` style and ended turns on reports at several points that
were not operator gates.

### 4.I The day this lands — in-flight and archived work, spelled out

Only the **`run`** kind changes version (4 → 5). Plans, journals, specs and the matrix are
untouched: no plan is rewritten, no `fr_version` floor moves (this is a minor bump, inside
every plan's `<5.0.0`).

**A plan in flight WITH a run cursor.** The first `fr` command after the plugin updates hits
the CLI-entry gate. In a terminal, on a feature branch, with no uncommitted edit to the
cursor, fr migrates and commits it. In an agent's Bash tool, CI or a pod it **refuses** with
the six-line message, and the agent runs `fr migrate artifacts --yes` itself — the standing
behaviour, unchanged. After that:

- every unit keeps its state; every recorded dispatch becomes an attempt; recorded cost
  moves onto the last attempt. **A phase that was held stays held** and still names its
  holder (`run-upgrade-mid-run-keeps-holder`).
- review units already resolved `done` show as `done, unevidenced (predates the evidence
  gate)` — debt, never a failure. **Reviews still to come in that same run DO need
  evidence**, because the shipped `fr-goal` shape now declares it; the refusal names the
  flag, and the updated skill tells the orchestrator to pass it. Manifest drift does not
  trip: drift checks step and member ids, not fields.
- a cursor fr cannot convert (unreadable, or carrying a partial measurement) is left
  byte-identical and named; every other cursor still migrates.

**A plan in flight with NO cursor** (pre-cursor work, or never adopted): nothing migrates,
nothing breaks. `fr migrate artifacts` still *offers* adoption, and `fr run adopt` now
writes a v5 cursor directly. gh#517's `fr journal check --require-reviews` remains its gate.

**Other open branches.** Each run's cursor lives on its own branch, so it migrates in its
own worktree the first time that branch meets this version. Checked on 2026-09-20: no other
open branch bumps the `run` kind, so no third version collision is pending.

**The idle guard only reaches session-bound runs.** It finds the run through gh#500's
session binding. Runs started before that binding existed show `sessions=none` and are
invisible to it — silent, by the fail-open rule. It protects runs started after this lands,
or attached by hand with `fr isolation attach`.

**Archived work is frozen, and stays frozen.** Everything under
`docs/superpowers/implemented/` — plans, journals, specs, and the 8 archived run cursors —
is outside every locator: never migrated, never validated, never rewritten. Archived cursors
keep their old shape (`items` / `dispatch` / `accounting`) forever. Nothing in fr re-parses
them (`archive.py` only moves files), so the live model no longer understanding them breaks
nothing. They remain readable by a person, and `fr.run.legacy.RunStateV4` can still parse
one on demand — a small dividend of the legacy reader. A plan archived AFTER this lands
takes its cursor along at v5; `fr archive` is not exempt from the gate, so it can never
archive an unmigrated one.

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

Twenty-three rows, grouped by what could go wrong. A rewrite this size is pinned by what it
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
| `run-pickup-on-another-host` | a run pushed mid-phase and picked up on another host shows the orphaned holder, refuses a double dispatch, and recovers via `--abandoned` |
| `run-adopt-writes-unit-records` | `fr run adopt` writes a current cursor; complete phases are done units with no invented attempts |

**Cost**

| id | claim |
|---|---|
| `run-unit-cost-per-attempt` | a redispatched unit keeps every attempt's cost; totals include abandoned attempts |
| `run-abandoned-attempt-is-measured` | an abandoned attempt's spend is measured when it is abandoned |
| `run-cost-attributed-by-agent-id` | a claimed attempt's cost is selected by its agent id, so overlapping dispatches neither lose nor swap measurements |
| `run-cost-never-misattributed-across-sessions` | an attempt dispatched from another session or host is never assigned this session's subagent costs; its cost shows as not observable |
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
| `run-idle-reprompt-opencode` | on OpenCode, an idle run is continued by re-injecting the next command on `session.idle` |
| `run-idle-guard-acts-once-per-position` | the guard acts at most once per cursor position, so a failing `advance` cannot trap a session in a loop |
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
| 2026-09-20-unit-record-unification | `derio-net/super-fr` | `2026-09-20-unit-record-unification` | — |
