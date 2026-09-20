# The `fr run` cursor tells the truth about what it is waiting for

Four bugs filed 2026-09-20 — #499, #501, #500, #496 — all in `fr/run` and `fr/workflow`,
delivered as one PR.

## 1. Problem

Four reports, one shape: **the cursor knows more than it says.**

| # | Symptom | Where the fact already exists |
|---|---|---|
| #499 | `fr run advance` re-emits a byte-identical dispatch brief for a `kind: agent` step already `running` | `fr run status` prints `phase/2/implement-phase: running` |
| #501 | `advance` prints a composite id (`phase/1/implement-phase`) that `resolve --step` rejects as "not found in workflow" | the JSON brief beside it already carries `step` and `item` separately |
| #500 | `fr run start` enters isolation but binds no session, so every fr-goal workspace reports `sessions=none` | `fr isolation attach` exists and repairs it mid-flight |
| #496 | `for_each: phase` builds a dispatch brief for a `tag: manual` phase | `_group_phases` parses the plan that carries `tag`, then returns bare numbers |

Two of them are narrowings: a richer upstream fact — a step's `running` state, a phase's
`tag` — is discarded at the point where it would have been load-bearing.

### 1.1 Why #499 is worse here than the same bug elsewhere

fr-goal §5 dispatches phase executors **into the isolation worktree that already exists**,
and `isolation: "worktree"` is forbidden for them by design (#420, hook-refused). The usual
protection against two agents colliding in one tree is therefore *unavailable on purpose*. A
second dispatch of the same phase means two `fr-phase-executor`s editing the same files,
ticking the same plan steps and committing onto the same branch concurrently.

It is easy to trigger without carelessness: in Claude Code every `kind: agent` step is a turn
boundary, so the orchestrator routinely re-enters the loop cold, and `advance` is its natural
first call. `advance` is idempotent-looking for `cli` steps, which trains the habit.

### 1.2 #500 reproduced itself

The first command of the pipeline that produced this spec —
`fr run start fr-goal --branch fix/fr-run-cursor-cluster` — created a workspace that
`fr isolation status` immediately reported as `sessions=none`, beside sibling workspaces
entered via `fr isolation up` carrying a uuid. The mechanism is in
`plugins/super-fr/hooks/fr-session-bind.sh`: its verb regex is start-anchored on
`fr isolation (up|exec|down)`, which `fr run start` cannot match (journal `x1`).

### 1.3 #496 is not "manual phases are a mistake"

`fr plan self-review`'s agentic-purity gate *manufactures* `[manual]` phases, and fr-goal §3
makes back-loading their **default** disposition ("last phase, no dependent agentic phase —
PR ships it unimplemented, operator pushes to the same PR"). A rule that refused every manual
phase would reject the exact plan shape fr-goal's own planner is specified to produce.

The defect is that `for_each: phase` treats a **typed** set as homogeneous. The fix is
therefore structural, not behavioural — see §3.D.

### 1.4 The trailing rule is a codification, not a new constraint

Measured across this repo before §3.D was committed to:

| Corpus | Plans | Manual phase not in the trailing block |
|---|---|---|
| `docs/superpowers/plans/` (live) | 4 | 0 |
| `docs/superpowers/implemented/plans/` (archived) | 80 | 0 |
| `tests/**/fixtures/**` plan folders | 16 | 0 |

Every plan this repo has ever produced already satisfies the invariant §3.D introduces. That
is the argument for enforcing it: the rule is not asking authors to change how they write
plans, it is making the way they already write them checkable — and closing the one shape
(`agentic, manual(unticked), agentic`) that nobody has written yet and that the run model would
silently mis-execute if they did.

## 2. Goal

`fr run advance` never hands out something that reads as an instruction to act when the
correct action is to wait, to split a flag, or to leave the work to a human — and every
refusal names the command that clears it.

### Non-goals

- Making `advance` execute `kind: agent` steps. That asymmetry is deliberate and documented.
- A third `fr run resolve --state` value (`deferred`/`manual`), which #496 offers as its
  option 2. The structural rule in §3.D removes the need for one: no brief is ever built for a
  manual phase, so there is no outcome to record (journal `d4`, `d6`).
- Changing the shipped `fr-goal` shape's step list. `_check_step_drift` refuses to advance any
  run started against a different list, so adding a step restarts every in-flight run.
- Any change to `fr_dispatch` / `fr_vk`. The bridge's item-level gate is untouched.

## 3. Design

### A. #499 — `advance` refuses a step that is already running

Two call sites, one rule.

**Top-level `agent` step** (`advance_cmd`): today `if record.state != "running": mark running`
then unconditionally print the brief. New: when `record.state == "running"`, print the refusal
and exit 2.

**Grouped `for_each` member** (`_advance_group`): today the pending-picker is
`next(key for key in expected if items.get(key) != "done")`, which cannot tell `running` from
`pending`. New: if any expected key is `running`, that key is the refusal's subject.

The refusal (exit 2, stderr) names the dispatch time from `record.at` and both ways forward:

```
implement: phase/2/implement-phase is ALREADY RUNNING (dispatched 2026-09-20T11:04:12Z).
  Waiting on that agent — do NOT dispatch again.
  resolve it:      fr run resolve <run-id> --step implement-phase --item phase/2 --state done|failed
  re-brief anyway: fr run advance <run-id> --redispatch
```

`--redispatch` is a new boolean flag on `advance`. It re-emits the brief for the outstanding
unit only (it never selects a *different* unit, never resets an item to `pending`, and never
overrides a `cli` step), refreshes `at`, and rewrites that unit's accounting snapshot. It is
the deliberate escape for a genuinely lost agent.

**`--redispatch` with nothing outstanding exits 2**, naming the fact, rather than quietly
degrading into an ordinary `advance`. The operator reaching for it believes an agent is running;
if none is, the mental model is wrong and saying so is the whole point of this section. The
`fr-goal` loop never passes the flag, so the strictness costs the normal path nothing.

Exit 2 is chosen because it is already this module's code for every refusal —
not-running, already-done, second-writer. A distinct exit 3 was offered and declined
(journal `d1`): nothing in-repo consumes `fr run`'s exit codes programmatically, so the
precision would buy a wider CLI contract for no reader.

**Unchanged:** the `gate: operator` path. A blocked gated `agent` step still prints its brief,
because the skill named in it is *how the operator's question gets asked* — the gate stops the
run, not the harness's view of the step. `_gate_pending` is evaluated before this check, so the
two never interact.

### B. #501 — teach the flag, and pre-empt the error

**The refusal becomes actionable.** `_find_step` raises `step <id> not found in workflow <w>`,
which invites the reader to check the shape file. New: before raising, if the id contains `/`
and its tail matches a member step of a grouped `for_each`, say so:

```
step 'phase/1/implement-phase' not found in workflow 'fr-goal'.
It is a grouped `for_each` member, which takes two flags:
  --step implement-phase --item phase/1
```

Option 2 from the issue — accepting the composite in `--step` and splitting it internally —
was declined (journal `d2`): it hides the flag rather than teaching it, and leaves two spellings
of one id.

**And the error is pre-empted.** `advance` already prints the composite in its human line; it
now also prints the exact resolve command. That line goes **before** the JSON brief, never
after: `run_cmd` already treats the brief as the line a naive `tail -1` parses off stdout, and
the gate-degradation notice carries the same ordering constraint with a comment saying why.

```
implement: dispatch brief (phase/1/implement-phase)
  resolve with: fr run resolve <run-id> --step implement-phase --item phase/1 --state done|failed
{"agent": "super-fr:fr-phase-executor", ...}
```

The composite stays the display id and the `items`-map key — it is one canonical form, shown
in `fr run status`, and the flags are taught beside it.

### C. #500 — bind the session on all three surfaces

All three of the issue's options, because each covers a hole the others leave (journal `d3`).

1. **`fr run start --session <id> --harness <h>`** — passed through to
   `fr.isolation.sessions.attach(workspace_root, branch, session, harness)` after
   `ensure_run_workspace` returns. Harness-neutral: it is the CLI surface every harness drives
   identically. `state_dir` resolves through `_git_common_dir`, so `attach` works whether the
   run was born in the base clone's workspace or inside the linked worktree.

   **Non-fatal.** A failed bind warns on stderr and the run proceeds. Bindings are traceability,
   not enforcement (`fr-isolation-required.md`: "the edit gate never consults a binding"), so a
   bind failure must never cost the operator a started run.

2. **`fr-session-bind.sh` matches `fr run start`.** The hook's verb regex is extended from
   `fr isolation (up|exec|down)` to also recognise `fr run start … --branch <b>`, reusing the
   existing `--branch` extraction and the existing leading-`cd` folding. This is what makes the
   Claude Code path work with **no agent cooperation at all** — an agent cannot reliably know its
   own session id, so a flag alone would leave the common path unbound.

   `fr-session-bind` already owns a `parity.yaml` row, so no new surface is declared; only its
   `summary` changes. Its `opencode: absent` / `hermes: absent` states are unchanged and remain
   honest — which is precisely why (1) exists.

3. **fr-goal SKILL.md §0** names `fr isolation attach --session <id> --branch <b> --harness <h>`
   as the documented fallback. The issue's own observation stands: the skill text never mentions
   `attach` at all, so there is today no documented path by which an fr-goal run becomes
   traceable.

### D. #496 — a structural invariant, checked at authoring

The reframing that makes this cheap: **where may a manual phase sit** is an invariant, and
invariants can be checked before anything runs. A *behaviour* ("what does the loop do when it
meets one?") can only be observed at dispatch.

#### D.1 The rule

> No manual phase may be **outstanding** when an agentic phase after it runs.

Concretely, a `tag: manual` phase is valid iff it is in the plan's **trailing block** *or* is
already `plan_locally_complete` (`render.py:232` — `completion.at` set, or steps non-empty and
all ticked).

```
VALID   1 agentic, 2 agentic, 3 agentic, 4 [manual]          back-loaded (fr-goal §3 default)
VALID   1 agentic, 2 agentic, 3 [manual], 4 [manual]         a trailing BLOCK, not just one
VALID   1 [manual] (ticked), 2 agentic, 3 agentic            front-loaded, go given (fr-goal §3)
ERROR   1 agentic, 2 [manual] (unticked), 3 agentic          phase 3 would wait on a human
```

The "or already complete" clause is what keeps fr-goal §3's front-load exception expressible
(journal `d5`): that flow *ends* with the operator ticking the phase's steps, so by loop time it
has nothing to dispatch. Position-only would have made §3 unexpressible — a doctrine rewrite
riding on a bug-fix cluster.

`depends_on` is checked alongside position, because position alone is not the invariant: an
agentic phase declaring `depends_on: [4]` where 4 is an **outstanding** trailing manual phase
reintroduces the hazard by other means. Same rule, same severity.

**Both halves key on *outstanding*, not on *manual*** — and the distinction is load-bearing
rather than pedantic (review `r4-f1`). Making the dependency half unconditional over every
manual phase reads as the stricter and therefore safer choice; it is not. fr-goal §3 front-loads
a manual phase "only when agentic work depends on it", so the dependency *is* what front-loading
means, and the canonical shape is:

```
1 [manual]  (ticked — the operator did the work and gave the go)
2 agentic   depends_on: [1]          <-- the reason phase 1 was front-loaded at all
```

An unconditional rule errors on that forever, with no remedy that preserves the plan's meaning:
dropping the dependency discards a true fact about build order, and making phase 2 manual
abandons the automation. That would make §3 unexpressible — exactly what decision `d5` chose
"trailing OR already complete" to avoid. A dependency on an already-complete manual phase waits
on nobody; a dependency on an unticked one still errors, trailing or not.

#### D.2 Where it fires — three places, earliest first

1. **`fr.plan_ops.self_review`, `severity="error"`.** The primary gate. fr-goal's `plan-review`
   step is `kind: cli` running `fr plan self-review {{ artifacts.plan }}`, and a `cli` step's
   exit code is its verdict — so a mis-shaped plan fails **before phase 1 is ever dispatched**,
   with the plan author positioned to fix it. This is the "caught early and fail loudly" the
   rule exists for, in a checkpoint that already exists.

2. **`implement` group preflight**, once, before the first unit is dispatched. Defence in depth:
   a plan reached via `fr run adopt`, or run under a repo-authored shape, can arrive at the loop
   without `self_review` ever having run. Same message, exit 2.

3. **Never at dispatch.** A `tag: manual` phase does not produce a dispatch brief under any
   circumstances. There is no code path that offers one to an agent.

#### D.3 What the cursor records

`for_each: phase` enumerates **agentic phases only**; `_expected_group_items` shrinks
accordingly and the completion arithmetic counts only what was dispatched. The trailing block is
recorded in the same group's `items` map at item granularity:

```yaml
implement:
  state: done
  items:
    phase/3/implement-phase: done
    phase/3/review-phase: done
    phase/4: manual          # trailing block — never dispatched
```

`items` values are already free-form strings, so this needs **no schema change and no artifact
version bump**. `fr run status` renders it with every other item. Group completion names it:

```
implement: done (6 members done; phase 4 trailing manual, ships unimplemented — operator pushes to the PR)
```

A real `manual` step in `fr-goal.yaml` was declined (journal `d6`): `_check_step_drift` refuses
to advance any run started against a different step list, so it would restart every in-flight
fr-goal run for a gain the items map already delivers.

**Both writers of `items` change.** `fr.run.adopt.build_run_state` reconstructs per-phase item
state independently of `advance`; if only `advance` learned about manual phases, a resumed run
would disagree with a started one. `plan_phase_numbers` grows a tag-aware sibling and both
callers use it.

**And the member refusal gets its own message.** `_resolve_member` today rejects an unexpected
key with "not a phase member of 'implement' — expected phase/<n> for phases [1,2,3]", which for
a manual phase reads as a bug in the phase list. It now names the reason:

```
phase/4/implement-phase: phase 4 is `tag: manual` and is deliberately never dispatched.
  Its record is the plan's own steps plus the PR's "unimplemented — operator pushes to this PR".
```

### E. What is deliberately left alone

- `fr run check`'s exit code. It is a narrow freshness gate; #496 suggested it might report a
  manual phase resolved `done` with no ticked steps, but under §D that state is now
  unreachable — the key is never in `expected`, so `_resolve_member` refuses it outright.
- The `gate: operator` brief-printing path (§3.A).
- `fr_dispatch.reachability` and the item-level dispatch gate. Different axis, untouched.

## 4. Risks and mitigations

| Risk | Mitigation |
|---|---|
| A plan already in flight has a non-trailing unticked manual phase; the new `self_review` error blocks its `plan-review` step | **Measured, not assumed: zero such plans exist.** All 4 live plans and all 80 archived plans put their manual phase last, as do all 16 on-disk fixture plan folders (§1.4). Should one appear, the message names the phase and both remedies (tick it, or move it to the trailing block) — intended behaviour, not a regression. |
| Tests that build a plan *inline* (rather than from a fixture folder) may construct a non-trailing manual phase and assert `self_review` passes | Not measurable by scanning fixture folders, so the plan budgets for it explicitly: the phase that adds the rule runs the full suite and fixes any such construction, rather than discovering it at PR time. |
| `--redispatch` becomes the habitual way past the #499 refusal, restoring the hazard | It is the only flag whose help text says what it costs; the refusal names `resolve` **first** and `--redispatch` second, and the PR body records the reasoning. Prose, honestly — there is no mechanism here, and the spec says so. |
| The hook's extended regex mis-parses a `fr run start` embedded in a compound command | The hook reads only the FIRST line and is start-anchored, exactly as today; a non-leading `fr run start` does not match, which is a missed bind (harmless) rather than a wrong one. |
| `attach` silently no-ops when isolation state is missing | It raises `IsolationError`, which §3.C.1 catches and reports as a warning naming the branch. |

## 5. Test Plan (post-merge, operator-driven)

Automated coverage lands in CI per phase. These four need a real run, because three of the
four bugs were found by *running* the pipeline: every unit fixture creates its runs in the
workspace and so satisfies the assumptions by construction — the same blind spot that produced
the `_existing_run_for_workflow` bug.

1. **#499 live** — start an `/fr-goal` run, let `implement` dispatch a phase executor, and call
   `fr run advance` again mid-flight. Expect the ALREADY RUNNING refusal and exit 2; then
   `--redispatch` and confirm it re-briefs the same unit and no other.
2. **#501 live** — paste the composite id into `resolve --step` and confirm the error teaches
   the two flags; confirm `advance`'s hint line precedes the JSON and that `tail -1` still
   yields parseable JSON.
3. **#500 live** — `fr run start` on a fresh branch in Claude Code, then `fr isolation status`:
   expect `sessions=<uuid>`, not `sessions=none`. Repeat with the hook disabled and the explicit
   `--session` flag.
4. **#496 live** — run a plan whose last phase is `[manual]` (this plan is one) and confirm:
   no brief is built for it, `fr run status` shows `phase/<n>: manual`, `implement` completes,
   and `deliver` still opens the PR. Then author a plan with a *middle* unticked manual phase
   and confirm `fr plan self-review` fails it with the §D.1 message.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-20-fr-run-cursor-cluster | `derio-net/super-fr` | `2026-09-20-fr-run-cursor-cluster` | — |

## References

- #499, #501, #500, #496 — the four reports
- #420 — why `fr-phase-executor` must not get its own worktree (the premise of §1.1)
- `docs/superpowers/implemented/specs/2026-08-14-workflow-shapes-and-workitem-dispatch-design.md` §4.A/§4.B
- `docs/superpowers/implemented/specs/2026-09-18-harness-parity-matrix-design.md` §3.D (gate provenance)
- `docs/superpowers/specs/2026-09-04-worktree-traceability-design.md` §5.A (session bindings)
- `docs/superpowers/journals/specs/2026-09-20-fr-run-cursor-cluster.md` — decisions d1–d7
