---
name: fr-goal
description: >
  Run a feature goal end-to-end autonomously via the `fr-goal` workflow shape (optional
  shape-name argument; no argument resolves `fr-goal`): brainstorm, one batched Q&A, then
  spec → review → fr-plan → review → TDD implementation → review → single PR, fixing every
  finding, no intermediate approval gates. ALWAYS use when the operator invokes /fr-goal or
  /goal, says "build this autonomously", "ask your questions once then build it", "take this
  to a PR", hands a feature to run unattended, says "auto mode" or spec-to-PR.
---

# fr-goal

One operator touchpoint — the batched Q&A — from goal to reviewed PR, driven by a **workflow
shape** (spec §4.A, `2026-08-14-workflow-shapes-and-workitem-dispatch-design.md`): `fr run
start <shape> --branch <b>` (defaults to `fr-goal`), then loop `fr run advance <run-id>`.
**Shape lookup:** repo `docs/superpowers/workflows/<shape>.yaml` (overrides wholesale) →
`$FR_SHIPPED_WORKFLOWS_DIR` → the `fr` wheel's own copy → the Claude Code marketplace clone, so
shipped shapes resolve on a hermes pod or under OpenCode with no plugin installed. **`start` enters isolation itself** and writes the run inside that workspace — the
first action, before anything else ("start with X" changes the first work item, never the
first action); run every later command from the workspace it prints. **Bind the session** so the workspace is attributable, not `sessions=none`: pass `--session <id> --harness <h>` to `start` when your harness exposes its session id (a harness with a session-bind hook does it for you); otherwise `fr isolation attach --session <id> --branch <b> --harness <h>` binds it after the fact — traceability only, so a missing binding never blocks work. No devcontainer profile
→ pause for fr-init. `kind: cli` executes directly — exit code is the verdict, fix and
re-`advance` on failure. `kind: agent` never executes itself: it prints a dispatch brief
(skill/agent/needs/emits/tier/for_each) you fulfill per that step below, then `fr run resolve
<run-id> --step <id> --state done|failed [--emitted name=path ...]` (each `name` must be one
the step `emits`; a `spec`/`plan` path must exist and is stored repo-relative). `gate:
operator` blocks until you resolve it (same command; a gated `cli` step then runs on the next `advance`). Blocked → stop, say what you tried, ask. Another shape, same mechanics.

**`fr` refused with "artifacts … must be migrated"?** Expected — a pod, CI and an agent's Bash
tool are all non-interactive, where fr never migrates or commits by itself. Run `fr migrate
artifacts --yes` yourself and continue; it is exempt and needs no TTY. **Work already in
flight when your `fr` changed under it?** `fr run adopt <plan-dir|spec>` rebuilds a cursor
from disk, completed phases included, so the plan joins the run model instead of being
stranded — offered, never forced (`--yes --adopt` does all of them).

**Announce at start:** "I'm using fr-goal to run this goal autonomously."

**Interactive touchpoints (all else autonomous):** `brainstorm`'s batched Q&A (`gate: operator`),
with any cross-repo location question folded in; manual phases from `plan`; PR merge after
`deliver` — never self-merged — and the post-merge Test Plan.

### 1. brainstorm — batched Q&A, in isolation (`gate: operator`)
Invoke `fr-brainstorming`. Explore, collect EVERY operator-owned decision — including one
repo-location question per other repo of a cross-repo spec (ask only if not found on disk) —
into ONE batch (max 4, recommended first) put to the operator, then STOP; add a post-merge Test
Plan question when the deliverable deploys, a model-per-tier one if `fr models resolve` is
unbound. Log each answer as a spec-scope `decision`. **Hard gate:** an unanswered batch is a
stop signal — restate the open questions, never default. Resolve `--emitted spec=<path>`, adding
`--answered-by operator` once the operator actually answered (defaults to `agent` otherwise).

**Harness — questions:** Claude Code batches them into one `AskUserQuestion` call. Hermes and
OpenCode have no question tool: put the numbered batch in your reply and END THE TURN — an
unanswered batch is the same stop signal there, and clearing the gate unasked is recorded.

### 2. spec-review
Review the spec against the Q&A answers AND codebase reality (do the named
files/helpers/services exist?). Fix every finding, log a spec-scope `review`. Cross-repo
spec: this session owns ONE repo's plan + PR; for each other repo, dispatch one agent
(`isolation: "worktree"` — right *here*: a fresh pipeline in a *different* repo) with the
spec ref and this pipeline from `plan` onward — one plan, one PR per repo.

### 3. plan — fr-plan, then review it
Invoke `fr-plan`, skipping section-by-section approval (the spec encodes the design). Keep
TDD-shaped steps (red → green → refactor, or a `no-refactor-because:` journal justification);
fr-plan tags each phase a `tier`. Phase 1 is the walking skeleton — CI green on a trivial test,
minimum runtime exercised, external fixtures captured never constructed. `fr plan self-review`
must pass and phases must read back against the spec. fr-plan's agentic-purity gate collects manual
work into `[manual]` phases; **back-load by default** (last phase, no dependent agentic phase —
PR ships it unimplemented, operator pushes to the same PR); **front-load only when agentic work
depends on it** (spec+plan PR, pause for the go). Multi-repo `depends_on` is within-plan only. Resolve `--emitted plan=<path>`.

### 4. plan-review
`fr run advance` runs `fr plan self-review {{ artifacts.plan }}` — deterministic, exit code is the verdict. Fix findings against the spec and re-`advance`; no `resolve` needed (`cli` steps self-complete).

### 5. implement — grouped per-phase loop, journal-fed, TDD
The run's workspace is the working copy (`fr isolation exec`); spec/plan aren't on main yet, so NOT dispatched (`fr apply --yes` refuses). `implement` is a grouped `for_each`: per phase in dependency order, dispatch ONE phase-executor for `implement-phase` — brief = `fr pickup` + spec + `fr journal handoff --scope plan --phase N`: TDD (`superpowers:test-driven-development`), journals discoveries/findings (`fr journal add … --phase N`), ticks steps / completes the phase, returns a structured result — pass/fail summary and journal ids, never pasted output (return is the only reporting channel, #461) — the handoff IS the context. Model = the brief's `resolved_tier` (falls back to the phase header's `tier` only when the brief lacks that key — an older `fr`) via `fr models resolve --harness <h>` (unbound → set at step 1); `resolved_tier: null` is the untiered case the dispatch clause below already handles, not a fourth rule; blocked → run inline; never a manual phase.
**Per phase the loop is dispatch → claim → wait → review → resolve → advance, and that last arrow is the next dispatch: the cycle closes, it does not stop.** Name a dispatch's holder as soon as your harness tells you who it is: `fr run claim <run-id> --step implement-phase --item phase/<n> --agent <id>` (`--harness` defaults to what fr detects, `--model` when you know it). It annotates the record `advance` already opened — fr times its own act and resolves the tier's model, but only YOU know which agent took it — so "who is holding phase 2 *right now*" is answerable while it matters, not only after the return (#503). `advance` then REFUSES a unit whose record is still open: exit 2, naming the holder, no brief printed — #499's double-dispatch hazard, now backed by recorded state instead of inferred from `items`.
Executor lost, or never coming back? `fr run claim <run-id> --step implement-phase --item phase/<n> --abandoned` closes the record and leaves the unit `running`, so the next `advance` briefs it again; `fr run advance <run-id> --redispatch` closes it and re-briefs in one move. Neither erases the old holder — records accumulate oldest-first per unit, which is the trail #503 asked for. `fr run status` shows who holds each unit and since when (harness beside model: a tier resolves FOR a harness, never in the abstract), with each attempt's context estimate and, where the transcript is reachable, what it actually billed — the two differ by orders of magnitude and are not comparable; `fr run check` counts open and unclaimed dispatches as debt, not failure.
**Picking the run up somewhere else?** The cursor travels with the branch; transcripts, session bindings and the agent do not. So a unit whose holder was dispatched from ANOTHER session says so — `advance`'s refusal names it, and its cost reads `not observable from here` rather than zero or a borrowed figure (fr never measures a window another session opened). That agent may have died with its host, so do not wait on it: close it with `claim … --abandoned` (or `advance --redispatch`) and re-brief from the last COMMIT — uncommitted work did not travel either. Bind the new session (`fr isolation up --branch … --session …`, or `fr isolation attach`) or the idle guard below cannot find the run at all.
**Harness — dispatch:** Claude Code uses the `fr-phase-executor` Agent without `isolation: "worktree"`
— **mustn't**, not "needn't" (#420, hook-refused): the flag cuts a *second* worktree from main where
spec/plan are invisible and writes are denied, yet the dispatch succeeds, so the run looks healthy
while nothing happens. The two isolations don't compose. (Contrast §2's cross-repo agents, which
*keep* the flag — each starts a fresh pipeline in a different repo; these share this one's workspace.)
Hermes `delegate_task(goal, context)` carries the brief in `context`, serial; child loads
`fr-execute`. OpenCode dispatches the same brief, serially, through its task tool as `subagent_type: fr-phase-executor-<tier>`: the call carries no model, so the agent NAME is the only place a tier can live. Two cases take the untiered `fr-phase-executor` instead — a phase declaring no `tier`, and a tier that is UNRESOLVED (`fr models resolve` prints nothing) — and you journal which: a tier agent with no binding just inherits the session model, a row indistinguishable from a working tiered dispatch, whereas the untiered name makes the absence visible.
The `--agent` id you claim with is whatever that dispatch handed you: on Claude Code the task id the `Agent` call returns, on OpenCode the child session id its task tool returns, on Hermes the `delegate_task` handle. WHEN you learn it differs too: Claude Code hands the task id back at once, so claim while the executor works; a dispatch call that BLOCKS (OpenCode's task tool) returns the id only with the result — claim it when the call returns, before you resolve, and until then `fr run status` reads `HELD BY an unclaimed agent`. Never invent one — an unclaimed record still refuses a second dispatch, it just can't say who it is waiting on.
Price stated, not hidden: ~7x an inline run ($7.59 measured against ~$1), bought for the fastest measured wall clock (56.2 min against 77.6 and 105.2) and real per-phase context isolation; inline only when dispatch is unavailable. An executor that both returns and messages: keep the return, log the drop (#461).

### 6. review-phase — per phase, inside the loop, then push (never a PR)
After each `implement-phase` return, resolve it, then `fr run advance <run-id>` again to brief `review-phase` — a unit nothing briefed cannot be resolved (exit 2), because the brief is what opens its record — and run it: BOTH skills its brief lists, in order: `superpowers:requesting-code-review` over spec + plan + code, then `superpowers:receiving-code-review` on what it raised (verify each finding against the code; fix it with a test, or refute it with reasoning — never a silent drop, never performative agreement); record each as a plan-scope `finding` (`--state open|fixed|refuted`) — the next phase's handoff includes them, `deliver` derives the PR body from it; later-fixed findings close with `fr journal resolve` (`--id <f> --state fixed --note <why>`), never by re-adding the id (a silent no-op). **Push the branch ONLY — never open the PR** (#320, 3×). Resolve `implement` done only once every phase's BOTH members land.
**The review is closed with EVIDENCE, not an assertion.** Write it first — `fr journal add --scope plan --slug <s> --kind review --phase N` naming the findings raised, or that none were — then `fr run resolve <run-id> --step review-phase --item phase/<n> --state done --evidence review=<entry-id> --model <the model you are running on>` (you ran this unit yourself, so fr records no model for it unless you say). Without `--evidence` that resolve exits 2 and names the flag; the id is verified against the plan journal, so it must be a `kind=review` entry for THAT phase — another phase's review, or a `finding`, is refused. `--state failed` needs none: a failed review met no obligation, and demanding proof of one would make a failure unreportable. So "review skipped" and "review passed clean" are now different states — the first cannot reach `done` at all. **Nor can a review whose findings were left lying:** the step also owes `findings`, which fr DERIVES from the journal and you never pass (`--evidence findings=` is refused) — `done` exits 2 while any finding filed against THAT phase is still open, printing the `fr journal resolve … --state fixed` line for each (`refuted` with reasoning when it is wrong); fr then records the ids it saw closed, or `none`. A finding that belongs to a later phase is filed against that phase (`--phase M`) and gates its review instead. A unit from before this gate reads `done, unevidenced (predates the evidence gate)`: visible debt, never a failure, never retroactively failed. §7 is the same rule read a second time, for phases no cursor ever walked — it still fails delivery without the entry.
**An iteration ENDS ON A DISPATCH, not a report** (#518). When an executor returns: review, fix, push, resolve the review with its evidence, then IN THE SAME TURN `fr run advance <run-id>` and dispatch the next unit — report AFTER dispatching, never instead of it. A delivered report plus a pile of just-fixed findings is peak pressure to summarise and stop, which is precisely where a run strands. This skill's autonomy contract outranks an output-style preference: insight is welcome, ending a turn on it mid-run is not. The only legitimate turn ends are an operator gate, a genuine block, a unit HELD by a working executor, and the finished run.
**Harness — idle guard:** `fr run check --idle` is the harness-neutral predicate — exit 3 iff the run is advanceable and nobody is working, naming the next command; every adapter calls it, none re-derives it. Claude Code registers a stop-time hook that refuses to end a turn on an idle run and hands that command back; it acts at most once per cursor position (stopping on purpose just means stopping again), and a turn ending while a unit is HELD is correct and is never blocked. Two costs, stated: it calls the `fr` on PATH, so a stale global install exits 2 and SILENTLY disables it, and it adds one `fr` start-up — roughly two seconds — to every turn end of a bound session. OpenCode cannot block a stop, so its plugin continues the session with that command instead: weaker, and not yet proven on a live session. Hermes has no adapter — there, the prose above is all there is.

### 7. journal-check — the review-owed gate, run by the cursor
`fr run advance` runs `fr journal check --scope plan --plan-dir {{ artifacts.plan }} --require-reviews` — exit code is the verdict (#430: an instruction-only obligation gets absorbed). Fails on a locally-complete, non-manual phase with no `kind=review` entry naming it; fix by completing/journaling that review, then re-`advance` (`cli` steps self-complete). Strands runs started against the older shape, by design — recover by moving the stranded `docs/superpowers/runs/<id>.yaml` aside FIRST (`adopt` refuses while a run exists for the same shape+branch, which is exactly the stranded case), then `fr run adopt <plan-dir> --branch <b> --run-id <fresh>`; it re-dispatches every completed phase's `review-phase` and does not carry the old cursor's gate provenance.

### 8. deliver — one PR per repo, all artifacts aboard
Verify first (`superpowers:verification-before-completion`): full test-suite output, self-review
pass, steps ticked, `journal-check` passed (§7 — it folds resolution records, so close each fixed finding with `fr journal resolve` rather than explaining it away). Open the **draft** PR:
summary + spec/plan paths; findings + fixes (+ refutations) and decisions via
`fr journal render --scope plan --section findings`/`decisions`; an **Operator gates** section
verbatim from `fr run gates <run-id>` (never blank — a run that never asked says so itself); the
back-loaded manual phase marked "unimplemented — operator pushes to this PR"; the Test Plan
verbatim ("post-merge — operator-driven"); acceptance debt (`fr acceptance status`) and
rows-added-since-brainstorm (`fr acceptance check --added-since origin/main`), each with a
one-line defense. The body carries a Ready-checklist guard (CI green, explicit review ok, no
commits since the ok). ONLY when all three hold: `gh pr ready`, remove the guard — never say
"ready to merge" before this, never self-merge, never flip it manually. Resolve `deliver` done;
nothing follows it. Stop; the operator merges.

### Post-merge close-out
When the operator reports the merge: **first verify it reached `main`** via `fr isolation
verify-merge --branch <b>`; not verified → STOP and recover (cherry-pick / fresh PR). Then
drive the Test Plan if present, confirm phases complete (`fr status`), `fr archive
<plan-dir>`, housekeeping PR, `fr isolation down` (or let gc reap it).
