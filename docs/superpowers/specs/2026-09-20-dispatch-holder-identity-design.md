# Dispatch holder identity — who is holding this phase?

- **Issue:** [#503](https://github.com/derio-net/super-fr/issues/503) (investigation + build);
  closes [#499](https://github.com/derio-net/super-fr/issues/499) (double-dispatch hazard)
- **Date:** 2026-09-20
- **Status:** design

## 1. Background — the asymmetry, explained

#503 observed that across two `/fr-goal` runs in one Claude Code session, **eight**
`fr-phase-executor` subagents were dispatched (five for gh#494, three for gh#498), and ten
hours later the harness's agent listing showed **two** — one of them gh#494's phase-2
executor, returned ten hours earlier, still resumable, with its worktree torn down by
`fr isolation down` and no container anywhere. The issue asked why one persisted and six were
reaped, "all dispatched the same way by the same orchestrator in the same session".

The answer is that **nothing about the dispatch differed, and nothing was ever reaped.**

### 1.A The durable record never lost anything

The session's subagent state lives under
`~/.claude/projects/<project>/<session-id>/subagents/`. For the session named in #503 it
holds all eight dispatches — eight `agent-<id>.meta.json`, eight `agent-<id>.jsonl`
transcripts — and the session's `tasks/` directory holds eight `<id>.output` symlinks
pointing back at them. Every `meta.json` is identical in dispatch shape:

```json
{ "agentType": "super-fr:fr-phase-executor", "description": "Implement phase 2",
  "toolUseId": "…", "spawnDepth": 1, "requestShape": "background",
  "requestNonInteractive": true, "model": "sonnet" }
```

The only field that varies across the eight is `model` — the tier binding, working as
designed. Every transcript ends the same way: `stop_reason: end_turn`, a normal handback.

So the listing is a **view over agents that are still non-terminal**, not a registry that
decays. Six executors were not reaped; they reached a terminal state and left the view. The
question is not "why were six removed" but "why did one never arrive".

### 1.B The discriminator: a timeout-promoted background child

Claude Code moves a foreground `Bash` command that exceeds its 120-second timeout into the
background rather than killing it. The executor's own `tool_result` records it verbatim:

```
Command did not complete within its 120s timeout and was moved to the background
(ID: b1fkw90hq). Output is being written to: …/tasks/b1fkw90hq.output.
```

**Five of the eight executors were promoted this way. None of them asked to be** — no
executor ever issued a `Bash` call with `run_in_background`. They ran `uv run ruff … && uv run
pytest …`, which is slower than 120 seconds on this repo.

An agent that stops while a promoted child is still alive gets a different completion notice:

| note | meaning |
|---|---|
| `A task-notification fires each time this agent stops with no live background children of its own.` | terminal; leaves the listing |
| `This agent stopped with background work of its own still running. It may resume on its own when that work completes or reports…` | **not terminal**; stays listed and resumable |

Two executors got the second note. `ad944a88…` (phase 3) stopped at `22:59:05Z` with a child
still running; the child finished at `22:59:10Z` and the agent re-notified **cleanly** at
`22:59:21Z` — it settled, and left the view.

`add889a…` (phase 2) never settled. It had two promoted children. The first completed before
it stopped. The second, promoted at `22:39:28Z`, was:

```bash
until grep -qE "passed in|failed in|error(s)? in" …/tasks/b1fkw90hq.output; do sleep 3; done
```

a poll loop watching the *first* child's output file for a pattern that never appeared. It ran
for **11.5 hours** and was finally reported `killed` at `2026-09-20T10:14:40Z`. For its whole
life the executor that launched it was non-terminal — which is exactly the window in which the
operator looked at the listing, twice.

**One live background child is the entire asymmetry.** It is a harness lifecycle interaction,
not an fr defect, and not a regression: `fr-phase-executor.md` and
`fr-phase-executor-guard.sh` are untouched since #465 / #422 / #390, as #503 already
established.

### 1.C Two hypotheses closed, one contributing cause found

- **The container hypothesis is dead.** #503 had already corrected the guess it floated on
  #499 — that the long-lived `docker run` from `fr isolation exec` was the background work —
  on the grounds that the worktree and container were gone while the agent stayed resumable.
  The transcripts close the remaining variant: the background work was a plain host shell,
  named in the executor's own `tool_result`, with no container involved. **Neither the
  devcontainer nor fr-isolation is implicated anywhere in this incident.**
- **Reaping the child does not retire the agent.** After `brgvv3xnw` was killed, the parent
  session recorded *no* subsequent clean notification for `add889a…`, though every other
  executor received one within ~20 seconds of finishing. There is therefore no
  orchestrator-side action that reliably retires such an agent — it is not `running`, so a
  stop does not apply. That is why the holder record below needs its own explicit close
  rather than relying on the harness to signal one.
- **The one part super-fr controls** is that the executor wrote the poll loop at all, and ran
  a multi-minute suite in the foreground where the timeout could promote it. §4.E fixes that.

### 1.D Why the traceability frame is the right one anyway

The investigation's conclusion — "this is a harness lifecycle artifact" — is only satisfying
because we could read the harness's private state directory. That is not a capability fr has,
Hermes and OpenCode expose nothing comparable, and none of it is available during a run when
it would matter. The durable gap #503 names stands regardless of the cause:

`fr.run.model.StepRecord` carries `state, at, gate, answered_by, emitted, exit, stdout, items,
members`. So `fr run status` can say `phase/2/implement-phase: running` — but not **which**
agent is running it, **when** it was dispatched, or whether it **ever returned**. There is a
single `at`, not a dispatched/returned pair.

fr already has this pattern one level too coarse: `fr isolation attach` / `up --session` record
which harness *session* holds a *workspace*. A *phase* is held by an *agent*, and nothing
records that link.

## 2. Goals / non-goals

**Goals**

1. `fr run status` answers "who is holding this phase, since when, and has it returned?"
2. `fr run advance` refuses to re-brief a unit that is already held, naming the holder.
3. An abandoned dispatch can be declared, freeing the unit without resolving the step.
4. The record is harness-neutral and written the same way on every harness.

**Non-goals**

- **Verification.** fr cannot prove the orchestrator reported the id it actually dispatched,
  any more than `--answered-by operator` proves a human answered. This records a *claim*, on
  the same documented terms `fr.harness` already uses for gates: visibility, not enforcement.
- Reading harness-private state. Nothing here parses `~/.claude`, `opencode.db`, or any
  equivalent. §1 did that once, by hand, to answer a question; it is not a supported surface.
- Reaping or stopping agents. fr has no such power and will not pretend to.
- Cost accounting (#464). The record makes attribution *possible*; spending it is separate.

## 3. The seam: what fr knows vs. what it is told

This is the load-bearing distinction, and the model encodes it.

| field | provenance |
|---|---|
| `dispatched` | **fr knows it.** `advance` wrote the brief; it timestamps its own act. |
| `agent_type`, `model` | **fr derives them** from the step and `fr models resolve`. |
| `agent`, `harness` | **reported.** The orchestrator says what it dispatched. Unverifiable. (`harness` is detected by fr when not given, which is a guess about the environment, not a claim about the agent.) |
| `returned`, `outcome` | **reported**, at `resolve` time. |

An unreported `agent` is recorded as absent, never guessed — the same reason
`--answered-by` defaults to `agent`: the weaker claim is what an unmodified caller records, so
nothing is silently upgraded.

## 4. Design

### 4.A `DispatchRecord` — a new model in `fr.run.model`

```python
DispatchOutcome = Literal["done", "failed", "abandoned"]

class DispatchRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dispatched: str                      # ISO 8601 — fr's own act
    agent: str | None = None             # reported harness agent/task id
    agent_type: str | None = None        # e.g. super-fr:fr-phase-executor
    harness: str | None = None           # one of fr.harness.model.HARNESSES
    model: str | None = None             # the resolved tier binding actually dispatched
    returned: str | None = None          # ISO 8601, set at resolve
    outcome: DispatchOutcome | None = None
```

`harness` is validated against `fr.harness.model.HARNESSES` when present and is otherwise
absent. There is no `"unknown"` member: `fr.harness.detect.detect_harness` already returns
`None` when it cannot tell, and inventing a fifth harness name to mean "we don't know" would
put a value in the record that no parity row can ever match.

`abandoned` exists because §1.C found there is no way to retire a non-returning agent from the
outside. It is the honest terminal state for "this dispatch is never coming back".

### 4.B Where it hangs: `StepRecord.dispatch`

```python
dispatch: dict[str, list[DispatchRecord]] | None = None
```

**A list per unit, not one record.** Every attempt is kept, oldest first: a `failed` unit that
is retried, a `--redispatch` after a lost agent, an `--abandoned` close. #503's third
motivation is forensic — *"after the fact, nothing attributes that commit to an agent"* — and
a map that overwrites the previous holder on retry answers that question exactly as badly as
having no record at all. The **open** dispatch, everywhere below, means the last element when
its `returned is None`; there is at most one, because §4.C refuses to open a second.

Keyed by the **unit key**, in two explicitly prefixed forms:

- a grouped `for_each` member → `phase/<n>/<member-id>`, exactly the `items` key;
- a flat `kind: agent` step → `step/<step-id>`.

The `step/` prefix is not cosmetic. The first draft of this spec claimed the two key spaces
were "disjoint by construction, because a step id may not contain `/`" — and that is **false**:
`fr.workflow.check.check_workflow` validates duplicate ids, dangling `needs`, cycles and
unknown capabilities, but it does **not** constrain the characters in a step id. A
repo-authored manifest with a step literally named `phase/1/implement-phase` is accepted
today. Rather than add an id-character rule to `fr workflow check` — a behaviour change that
could fail a manifest some repo already ships — the key carries its own namespace.

Optional and defaulted, like `items`, `members` and `accounting` before it.

### 4.B.1 Exactly when a record is opened

**A dispatch record is opened when, and only when, `advance` moves a `kind: agent` unit to
`running`.** Two consequences, both deliberate:

- **A gated step opens nothing.** `advance` prints a blocked step's brief while marking it
  `blocked`, not `running` — nothing was dispatched, so there is nothing to hold. `brainstorm`
  is the shipped example.
- **An orchestrator-run agent step still opens one.** In the shipped `fr-goal` shape only
  `implement` and `implement-phase` carry `agent:`; `spec-review`, `plan`, `review-phase` and
  `deliver` are `kind: agent` with `agent: null` — the orchestrator does that work itself.
  Their records open with `agent_type: None`, and `fr run status` renders them
  `held by the orchestrator`. This is the right answer rather than an exception, because #499's
  complaint is precisely that *nothing distinguishes "not yet dispatched" from "dispatched,
  awaiting resolve"* — and that is as true of a step the orchestrator runs itself, after a
  compaction, as it is of a subagent.

### 4.C CLI

**`fr run claim`** — new verb, the open half:

```
fr run claim <run-id> --step <s> [--item phase/<n>] --agent <id>
                      [--harness <h>] [--model <m>]
fr run claim <run-id> --step <s> [--item phase/<n>] --abandoned
```

- Requires an **open** dispatch record for that unit (i.e. `advance` briefed it). Claiming a
  unit that was never briefed is refused — a claim is an annotation on a dispatch fr made,
  not a way to invent one.
- Re-claiming the same unit with the same agent is idempotent. Re-claiming with a *different*
  agent while the first has not returned is **refused**: that is two writers, which is the
  whole hazard.
- `--abandoned` closes the record (`returned` = now, `outcome: abandoned`) and leaves the
  step's `items` entry `running`, so `advance` will brief it again. This is the sanctioned
  recovery for a lost executor, and it is a deliberate operator act with a name.
- `--harness` defaults to `fr.harness.detect.detect_harness(os.environ)`, so the common call
  is short; when detection returns `None` the field stays absent rather than guessing.

**`fr run advance`** — opens the record, and refuses a held unit:

- For a `kind: agent` step (flat or member), `advance` writes
  `DispatchRecord(dispatched=now, agent_type=step.agent, model=<resolved tier>)` — appended to
  `dispatch[key]` — alongside the existing `items[key] = "running"` write-claim. For a flat
  step there is no `items` entry; the record is the whole write-claim.
- If a record for that unit already exists **and** `returned is None`, `advance` exits **2**:

  ```
  implement: phase/2/implement-phase is ALREADY HELD
    by agent add889a73824c8413 (super-fr:fr-phase-executor, claude-code)
    dispatched 2026-09-19T22:26:07Z — not yet returned.
    Waiting on that agent — do NOT dispatch again.
    Resolve it:  fr run resolve <run> --step implement-phase --item phase/2 --state done|failed
    Lost agent:  fr run claim <run> --step implement-phase --item phase/2 --abandoned
    Re-brief:    fr run advance <run> --redispatch
  ```

  `--redispatch` closes the open record (`outcome: abandoned`) and **appends** a fresh one,
  then prints the brief. The old holder is not overwritten — it stays in the unit's list,
  which is the forensic trail #503 asks for.
- An **unclaimed** open record prints `by an unclaimed agent` in place of the id. The refusal
  still fires: fr knows a brief went out even when nobody said who took it.

This is #499's `advance` behaviour, exactly as that issue specified it, now backed by state
rather than inferred from `items`.

**`fr run resolve`** — closes the record:

- gains `--agent`, `--harness`, `--model`, applied only when the record has no `agent` yet
  (the late fallback). Supplying a *different* agent than the one claimed is refused.
- sets `returned` = now and `outcome` = the resolved `--state`.

**`fr run status`** — renders the holder under each unit:

```
cursor: implement
  implement: running
    phase/1/implement-phase: done
      ← add889a73824c8413 (claude-code, claude-sonnet-5) 22:26:07Z → 22:41:05Z done
    phase/2/implement-phase: running
      ← HELD BY a9a02f104b58d840c (claude-code, claude-opus-5) since 09:00:03Z
```

**`fr run check`** reports open dispatches, and counts unclaimed ones — the same nagging shape
`answered_by` already has. An unclaimed dispatch is visible debt, not an error.

### 4.D Artifact versioning

`StepRecord` gains a field and `RunState` is `extra="forbid"`, so a released `fr` raises on a
cursor this one writes. That is a **shape change** under `.claude/rules/artifact-versioning.md`
and ships all three pieces in this PR:

1. `run` kind `current_version` **2 → 3** in `fr.artifacts.registry`, and nowhere else.
2. A registered `SchemaMigration` `run-dispatch-holder`, modelled directly on
   `fr/artifacts/run_provenance.py` (the 1 → 2 precedent): **stamp-only, no body rewrite** —
   the new field is optional and absent is already correct for every v2 cursor — but it
   *parses first and refuses* rather than certifying a file it cannot read. Imported by
   `fr/artifacts/__init__.py`, because a migration nobody imports never runs.
3. The `run` structure validator learns `dispatch`, reached as `ArtifactKind.validate` and
   exercised by `fr validate artifacts`.

And, per the rule's second operational fact: **this PR runs `fr migrate artifacts --yes` and
commits the result**, or this repo's own `acceptance-report` workflow goes red the moment the
stamp moves.

### 4.E fr-goal §5 and the executor definition

**`plugins/super-fr/skills/fr-goal/SKILL.md` §5** gains the claim as a named step in the
per-phase loop: dispatch → `fr run claim … --agent <id>` → wait → `fr run resolve …`. The
harness-specific clauses stay scoped per harness, so
`test_tripwire_skill_tool_neutrality.py` keeps passing:

- Claude Code: the `Agent` call's returned task id is the `--agent` value.
- OpenCode: the child session id from its task tool.
- Hermes: `delegate_task`'s task handle.

**`plugins/super-fr/agents/fr-phase-executor.md`** gains the §1.B fix (decision d3):

> **Long commands, and what you must not leave behind.** A foreground `Bash` call that
> exceeds 120 seconds is moved to the background by the harness — you do not get to opt out,
> and the full test suite in this repo is well past that. Run a long suite with
> `run_in_background` *deliberately* and wait on it with a bounded loop, and before you hand
> back, make sure nothing you started is still polling. An unbounded
> `until … ; do sleep N; done` left running at handback keeps you non-terminal and resumable
> indefinitely — a second writer for a tree where `isolation: "worktree"` is forbidden by
> design (#420). One did exactly this for 11.5 hours (#503).

No tripwire: there is no hook point for "an agent left a poll loop running", and a test that
only guarded the wording would be enforcement theatre (decision d3).

**`packages/fr/src/fr/harness/parity.yaml`** — the `subagent-dispatch` row's summary gains a
sentence: dispatch is now recorded fr-side per unit, so the row points at observable state
instead of resting entirely on skill prose being followed (#503's fifth motivation).

## 5. Alternatives rejected

- **Fold the id into `resolve` only, no new verb.** No new CLI surface and no extra call per
  phase — but the identity arrives only when the agent returns, so "who is holding this phase
  right now", the issue's title, stays unanswerable while it matters. Rejected by the operator.
- **Put the record in `RunState` beside `accounting`.** Symmetrical with an existing
  top-level map, but a dispatch is a property *of a step's attempt*, and #503 asks for
  `StepRecord` by name. A second top-level map would also drift from `items`, which is the
  thing a dispatch is paired with.
- **Widen `items` from `dict[str, str]` to a model.** A shape change to a field every reader
  already handles, for no gain a sibling map does not give.
- **`advance` warns instead of refusing.** Safer against wedging a run whose executor died
  silently — but `--abandoned` and `--redispatch` already cover that case explicitly, and a
  warning on a printed brief trains exactly the habit #499 describes. Rejected by the operator.

## 6. Test Plan

**Gating the PR (CI + unit):**

1. `DispatchRecord` round-trips through `dump_run_state` / `parse_run_state`; a v2 cursor with
   no `dispatch` key parses unchanged.
2. `advance` opens a record with `dispatched`, `agent_type` and the resolved `model`, keyed
   `step/<id>` for a flat agent step and `phase/<n>/<member>` for a grouped member.
2b. A **gated** agent step (`brainstorm`) opens NO record — it is marked `blocked`, not
   `running` — while an **orchestrator-run** agent step (`spec-review`, `agent: null`) opens one
   with `agent_type: None`.
2c. A unit `--redispatch`ed, or failed and retried, keeps BOTH records in `dispatch[key]`,
   oldest first, with the earlier one closed.
3. `advance` on a held unit exits 2, names the holder id (and `an unclaimed agent` when none
   was claimed), and prints no brief; `--redispatch` exits 0, closes the old record
   `abandoned`, and prints the brief.
4. `claim` refuses an unbriefed unit; is idempotent for the same agent; refuses a second,
   different agent while the first is open.
5. `claim --abandoned` closes the record and leaves `items[key] == "running"`, so the next
   `advance` briefs it again.
6. `resolve` sets `returned`/`outcome`; `resolve --agent` fills an unclaimed record; `resolve
   --agent` disagreeing with a claimed one is refused.
7. `fr run status` prints the holder line for a held unit, the dispatched→returned pair for a
   settled one, and `held by the orchestrator` for a record with no `agent_type`.
8. `fr run check` counts open and unclaimed dispatches.
9. The `run` 2 → 3 migration stamps a readable cursor, refuses an unreadable one, and leaves
   every other cursor migrating (the `run_provenance` invariant).
10. `fr validate artifacts` accepts a cursor carrying `dispatch` and rejects a malformed one.
11. This repo's own artifacts pass `fr validate artifacts` after `fr migrate artifacts --yes`.
12. `fr harness parity --check` passes with the amended row.

**Post-merge, operator-driven (decision d4) — both harnesses:**

13. A live `/fr-goal` run on **Claude Code**: `fr run status` during a phase shows that phase
    held by the real subagent id, and after it returns shows the dispatched→returned pair with
    `harness: claude-code` and the tier's model. Transcript in the PR.
14. The same on **OpenCode**, recording `harness: opencode` and the child session id, proving
    the record is harness-neutral rather than Claude-shaped.
15. On one of those runs, deliberately `advance` twice for the same phase and confirm the
    refusal fires with the real holder id — the #499 behaviour, live.

## 7. Acceptance rows

| id | claim | level |
|---|---|---|
| `run-dispatch-holder-recorded` | `fr run status` names the agent holding a phase, since when | unit → live |
| `run-dispatch-refuses-second` | `fr run advance` refuses a held unit; `--redispatch` is the escape | unit → live |
| `run-dispatch-abandon` | An abandoned dispatch frees the unit without resolving the step | unit |
| `run-dispatch-harness-neutral` | The record is written identically on Claude Code and OpenCode | live (both) |
