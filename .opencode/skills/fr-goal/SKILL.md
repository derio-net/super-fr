---
name: fr-goal
description: >
  Run a feature goal end-to-end autonomously via the `fr-goal` workflow
  shape (optional shape-name argument; no argument resolves `fr-goal`):
  brainstorm, one batched Q&A, then spec → review → fr-plan → review → TDD
  implementation → review → single PR, fixing every finding, no
  intermediate approval gates. ALWAYS use when the operator invokes
  /fr-goal or /goal, says "build this autonomously", "ask your questions
  once then build it", "take this to a PR", hands a feature to run
  unattended, says "auto mode" or spec-to-PR.
---

# fr-goal

One operator touchpoint — the batched Q&A — from goal to reviewed PR, driven by a **workflow
shape** (spec §4.A, `2026-08-14-workflow-shapes-and-workitem-dispatch-design.md`): `fr run
start <shape> --branch <b>` (defaults to `fr-goal`; a repo
`docs/superpowers/workflows/<shape>.yaml` overrides the shipped one wholesale), then loop
`fr run advance <run-id>`. **`start` enters isolation itself** and writes the run inside
that workspace — the first action, before anything else ("start with X" changes the first
work item, never the first action); run every later command from the workspace it prints. No
devcontainer profile → pause for fr-init. `kind: cli` executes directly — exit code is the
verdict, fix and re-`advance` on failure. `kind: agent` never executes itself: it prints a
dispatch brief (skill/agent/needs/emits/tier/for_each) you fulfill per that step below, then
`fr run resolve <run-id> --step <id> --state done|failed [--emitted name=path ...]`. `gate:
operator` blocks until you resolve it (same command; a gated `cli` step then runs on the
next `advance`). Blocked → stop, say what you tried, ask. Another shape, same mechanics;
below narrates the shipped `fr-goal` shape.

**Announce at start:** "I'm using fr-goal to run this goal autonomously."

**Interactive touchpoints (all else autonomous):** `brainstorm`'s batched
Q&A (`gate: operator` — unanswered = stop), with any cross-repo location question folded in;
manual phases from `plan`; PR merge after `deliver` — never self-merged — and the post-merge
Test Plan.

### 1. brainstorm — batched Q&A, in isolation (`gate: operator`)
Invoke `fr-brainstorming`. Explore, collect EVERY operator-owned decision — including one
repo-location question per other repo of a cross-repo spec (ask only if not found on disk) —
into ONE AskUserQuestion call (max 4, recommended first); add a post-merge Test Plan
question when the deliverable deploys, a model-per-tier one if `fr models resolve` is
unbound. Log each answer as a spec-scope `decision`. **Hard gate:** an unanswered call is a
stop signal — restate the open questions, never default. Resolve with `--emitted
spec=<path>` once written.

### 2. spec-review
Review the spec against the Q&A answers AND codebase reality (do the named
files/helpers/services exist?). Fix every finding, log a spec-scope `review`. Cross-repo
spec: this session owns ONE repo's plan + PR; for each other repo, dispatch one agent
(`isolation: "worktree"` — right
*here*: a fresh pipeline in a *different* repo) with the spec ref and this
pipeline from `plan` onward — one plan, one PR per repo.

### 3. plan — fr-plan, then review it
Invoke `fr-plan`, skipping section-by-section approval (the spec encodes the design). Keep
TDD-shaped steps; fr-plan tags each phase a `tier`. `fr plan self-review` must pass and
phases must read back against the spec. fr-plan's agentic-purity gate collects manual work
into `[manual]` phases; **back-load by default** (last phase, no dependent agentic phase —
PR ships it unimplemented, operator pushes to the same PR);
**front-load only when agentic work depends on it** (plan + review, open
a spec+plan PR, pause for the operator's go). Multi-repo `depends_on` is within-plan only.
Resolve with `--emitted plan=<path>`.

### 4. plan-review
`fr run advance` runs `fr plan self-review {{ artifacts.plan }}` — deterministic, exit code
is the verdict. Fix findings against the spec and re-`advance`; no `resolve` needed (`cli`
steps self-complete).

### 5. implement — one subagent per phase, journal-fed, TDD
The run's workspace is the working copy (`fr isolation exec`); spec/plan aren't on main yet,
so NOT dispatched (`fr apply --yes` refuses). Per phase in dependency order, dispatch ONE
phase-executor, brief = `fr pickup` + spec + `fr journal render --scope plan`: TDD
(`superpowers:test-driven-development`), journals discoveries/findings (`fr journal add`),
ticks steps / completes the phase, returns a structured result — the journal IS the handoff.
Model = phase `tier` via `fr models resolve --harness <h>` (unbound → set at step 1);
blocked → run inline; never a manual phase. **Harness — dispatch:** Claude Code uses the
`fr-phase-executor` Agent **without `isolation: "worktree"`** — not "needn't", **mustn't**
(#420, hook-refused): the flag cuts a *second* worktree from main where spec/plan are
invisible and writes are denied, yet the dispatch succeeds, so the run looks healthy while
nothing happens. The two isolations don't compose. (Contrast §2's cross-repo agents, which *keep* the flag — each starts a fresh pipeline in a different repo; these share this one's workspace.) Hermes calls `delegate_task(goal,
context)` with the brief in `context`, serial; child loads `fr-execute`. **Push the branch
ONLY — never open the PR**: opening here reorders `deliver` ahead of `review`, orphaning
fixes onto a merged branch (#320, 3×). Resolve `implement` done only once every phase lands.

### 6. review — fix everything found
After each milestone (completed phase, or full implementation for small plans), invoke
`superpowers:requesting-code-review` over spec + plan + code. Fix every finding with tests;
a wrong one gets refuting reasoning (`superpowers:receiving-code-review`), never a silent
drop. Record each as a plan-scope `finding` (`--state open|fixed|refuted`) — `deliver`
derives the PR body from this durable list.

### 7. deliver — one PR per repo, all artifacts aboard
Verify first (`superpowers:verification-before-completion`): full test-suite output,
self-review pass, steps ticked, `fr journal check
--scope plan` clean. Open the **draft** PR ("Draft" = do not merge):
summary + spec/plan paths; findings + fixes (+ refutations) and decisions via `fr journal
render --scope plan --section findings`/`decisions`; the back-loaded manual phase marked
"unimplemented — operator pushes to this PR"; the Test Plan verbatim ("post-merge —
operator-driven"); acceptance debt (`fr acceptance status`) and rows-added-since-brainstorm
(`fr acceptance check --added-since origin/main`), each with a one-line defense. Mergeable
ONLY now (after step 6's fixes): `gh pr ready` — never say "ready to merge" before this.
Resolve `deliver` done; nothing follows it. Stop; the operator merges.

### Post-merge close-out
When the operator reports the merge: **first verify it reached `main`** via `fr isolation
verify-merge --branch <b>`; not verified → STOP and recover (cherry-pick / fresh PR). Then
drive the Test Plan if present, confirm phases complete (`fr status`), `fr archive
<plan-dir>`, housekeeping PR, `fr isolation down` (or let gc reap it).
