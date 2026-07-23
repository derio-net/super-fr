---
name: fr-goal
description: >
  Run a feature goal end-to-end autonomously: brainstorm, one batched Q&A,
  then spec → review → fr-plan → review → TDD implementation → review →
  single PR, fixing every finding, no intermediate approval gates. ALWAYS
  use when the operator invokes /fr-goal or /goal, says "build this
  autonomously", "ask your questions once then build it", "take this to a
  PR", hands a feature to run unattended, says "auto mode" or spec-to-PR.
---

# fr-goal

One operator touchpoint — the batched Q&A — from goal to reviewed PR:
brainstorm → spec → fr-plan → TDD implementation → review → single PR, every
review fixing all it finds instead of pausing. Blocked → stop, say what you
tried, ask; a wrong guess costs more than a pause.

**Announce at start:** "I'm using fr-goal to run this goal autonomously."

**Interactive touchpoints (all else autonomous):** the batched Q&A (step 1,
operator-owned — unanswered = stop); a multi-project location question if the
filesystem can't answer it (3); manual phases (5); PR merge — never
self-merged — and the post-merge Test Plan (8–9).

### 1. Brainstorm with batched Q&A — in isolation

Invoke `fr-brainstorming` (runs `fr isolation up` first; no devcontainer
profile → pause for the fr-init interview). Isolation precedes EVERYTHING —
"start with X" changes the first work item, never the first action. Explore,
collect EVERY operator-owned decision, ask all in ONE AskUserQuestion call
(max 4, recommended first). Add a post-merge Test Plan question when the
deliverable deploys; if `fr models resolve` is unbound, add a model-per-tier
question. Batch stragglers. Log each answer as a spec-scope `decision` (§A).
**Hard gate:** an unanswered call is a stop signal — end the turn restating the
open questions; never default an answer.

### 2. Spec — then review it

Write `docs/superpowers/specs/<YYYY-MM-DD-slug>-design.md`, then review it
against the Q&A answers AND codebase reality (do the files/helpers/services it
names exist?). Fix every finding, logging a spec-scope `review`. A deploying
deliverable → spec carries a `## Test Plan` of post-merge steps, whose claims
are the brainstorm's acceptance rows (fr-brainstorming §3).

### 3. Multi-project check

For a cross-repo spec (`owner/repo:path` form), this session owns ONE repo's
plan and PR. For each other repo: locate its working copy; ask for a path/clone
only if not found — batch into the Q&A. Dispatch one agent per repo
(`isolation: "worktree"`) with the spec ref and this pipeline from step 4 — one
plan, one PR per repo.

### 4. Plan — fr-plan, then review it

Invoke `fr-plan`, skipping section-by-section approval (the spec encodes the
design). Keep TDD-shaped steps; fr-plan tags each phase a `tier`. Review:
`fr plan self-review` must pass (acceptance linkage) and the phases read back
against the spec. Fix, implement.

### 5. Manual phases — back-load by default

fr-plan's agentic-purity gate collects manual work into `[manual]` phases;
fr-goal adds placement policy (a mid-plan manual phase stalls the run):

- **Back-load by default:** ALL manual work in the LAST phase, no dependent
  agentic phase. The PR ships it unimplemented; the operator pushes it to the
  same PR (`--complete-phase N --note`).
- **Front-load only when agentic work depends on it.** Finish plan + review,
  open a PR of spec + plan (the instructions ARE the deliverable), pause;
  resume ONLY on the operator's go.
- **Multi-repo:** `depends_on` is within-plan only — cross-repo ordering lives
  in the spec + PR sequencing.

### 6. Implement — one subagent per phase, journal-fed, TDD

The step-1 workspace is the working copy (commands via `fr isolation exec`);
spec/plan aren't on main, so NOT dispatched (`fr apply --yes` refuses). Per phase
in dependency order, dispatch ONE phase-executor, brief = `fr pickup` + spec +
`fr journal render --scope plan`: TDD (`superpowers:test-driven-development`), journals discoveries/findings
(`fr journal add`), ticks steps / completes the phase, returns a structured
result — the journal IS the handoff (subagent inherits no history). Model =
phase `tier` via `fr models resolve --harness <h>` (unbound → set step 1); blocked
→ run inline; never a manual phase. **Harness — dispatch:** Claude Code uses the
`fr-phase-executor` Agent; Hermes Agent calls `delegate_task(goal, context)` with
the brief in `context` (subagents know nothing — pass all), serial; child loads `fr-execute`.

**The implementing layer pushes the branch ONLY — never opens the PR**: that
reorders deliver (8) ahead of review (7), orphaning fixes onto a merged branch
(#320, 3×). The orchestrator opens the **draft** PR ("Draft" = do not merge).

### 7. Review at milestones — fix everything found

After each milestone (completed phase, or full implementation for small plans),
invoke `superpowers:requesting-code-review` over spec + plan + code. Fix every
finding with tests; a wrong one gets refuting reasoning
(`superpowers:receiving-code-review`), never a silent drop. Record each as a
plan-scope `finding` (`--state open|fixed|refuted`) — the durable list step 8
derives the PR body from.

### 8. Deliver — one PR per repo, all artifacts aboard

Verify first (`superpowers:verification-before-completion`): full test-suite
output, self-review pass, steps ticked, `fr journal check --scope plan` clean.
Mergeable ONLY now (after step 7's fixes): `gh pr ready` on the draft — never
say "ready to merge" before this. PR body: summary + spec/plan paths; findings +
fixes (plus refutations) and decisions via `fr journal render --scope plan
--section findings`/`decisions`; the back-loaded manual phase marked
"unimplemented — operator pushes to this PR"; the Test Plan verbatim
("post-merge — operator-driven"); acceptance debt (`fr acceptance status`) and
rows-added-since-brainstorm (`fr acceptance check --added-since origin/main`),
each with a one-line defense. Stop; the operator merges.

### 9. Post-merge close-out

When the operator reports the merge: **first verify it reached `main`** via
`fr isolation verify-merge --branch <b>`; not verified → STOP and recover
(cherry-pick / fresh PR). Then drive the Test Plan if present, confirm phases
complete (`fr status`), `fr archive <plan-dir>`, housekeeping PR, `fr isolation
down` (or let gc reap it — it auto-reconciles merged workspaces on any up/down).
