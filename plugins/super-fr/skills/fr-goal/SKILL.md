---
name: fr-goal
description: >
  Run a feature goal end-to-end autonomously: brainstorm, ask one batched
  Q&A, then spec → review → fr-plan → review → TDD implementation → review →
  single PR, fixing every review finding, with no intermediate approval
  gates. ALWAYS use when the operator invokes /fr-goal or /goal, says "build
  this autonomously", "ask your questions once then build it", "take this to
  a PR", hands over a feature to run unattended, mentions "auto mode", or
  asks for the full spec-to-PR pipeline in one shot.
---

# fr-goal

One operator touchpoint from goal to reviewed PR: brainstorm context → ONE
batched Q&A → spec → review → fr-plan → review → TDD implementation → review
→ single PR. Every review fixes all it finds; the operator's autonomy
instruction replaces each superpowers approval pause with a review-and-fix
pass. When blocked: stop, say what's blocked and what you tried, and ask — a
wrong guess shipped in a PR costs more than a paused run.

**Announce at start:** "I'm using fr-goal to run this goal autonomously."

## What stays interactive

| Moment | Why |
|---|---|
| The batched Q&A (once, at brainstorm) | Design decisions are operator-owned |
| Multi-project repo location | Access question — only if the filesystem can't answer it |
| Manual phases | Secrets, UI ops, deploys are human-only — see placement policy |
| PR merge | The agent never self-merges |
| Post-merge Test Plan | Proves real deployment; needs the operator's environment |

### 1. Brainstorm with batched Q&A — in isolation

Invoke `fr-brainstorming` (runs `fr isolation up` first; no devcontainer
profile → pause for the fr-init interview). Isolation precedes EVERYTHING —
exploration, measurements, cluster ops included; an operator "start with X"
changes the first work item, never the first action. Explore, collect EVERY
operator-owned decision, ask all in ONE AskUserQuestion call (max 4 questions,
recommended first). Include a post-merge Test Plan question ONLY when the
deliverable deploys (service/bot/infra), never pure code. Batch stragglers.

### 2. Spec — then review it

Write `docs/superpowers/specs/<YYYY-MM-DD-slug>-design.md`, then review it
against the Q&A answers AND codebase reality (do the files/helpers/services it
names exist?). Fix every finding. Test Plan chosen → spec carries a `## Test
Plan` of post-merge steps.

### 3. Multi-project check

For a cross-repo spec (`owner/repo:path` form), this session owns ONE repo's
plan and PR. For each other repo: locate its working copy yourself (sibling
dirs, usual roots); ask for a path/clone only if not found — batch into the
Q&A. Dispatch one agent per repo (`isolation: "worktree"`) with the spec ref
and this pipeline from step 4. One plan, one PR per repo.

### 4. Plan — fr-plan, then review it

Invoke `fr-plan`, skipping section-by-section approval (the spec encodes the
design). Keep v2 plan-as-folder, TDD-shaped steps. Review: `fr plan self-review`
must pass and the phases read back against the spec (all covered). Fix, implement.

### 5. Manual phases — back-load by default

fr-plan's agentic-purity gate collects manual work into dedicated `[manual]`
phases. fr-goal adds placement policy (a mid-plan manual phase stalls the run):

- **Back-load by default:** ALL manual work in the LAST phase, no agentic phase
  depending on it. The PR ships it deliberately unimplemented, marked for the
  operator, who implements and pushes to the same PR (`fr plan edit --complete-phase N --note`).
- **Front-load only when agentic work genuinely depends on it.** Finish plan +
  review, open a PR of spec + plan (the manual instructions ARE the
  deliverable), pause; resume ONLY on the operator's go.
- **Multi-repo:** model cross-repo deps — `depends_on` is within-plan only, so
  ordering lives in the spec and PR sequencing (a secret in one repo may gate
  another's phases).

### 6. Implement — fr-execute local mode, TDD, no subagents

The step-1 isolation workspace is the working copy — every command through
`fr isolation exec`. Run phases via `fr-execute` in LOCAL mode (plan-dir +
phase), NOT dispatched (spec/plan aren't on main, `fr apply --yes` refuses).
Implement inline, not via subagents (the context needs the Q&A + spec history).
TDD per step; tick steps / complete phases via `fr plan edit`. Never a manual phase.

**The implementing layer pushes the branch ONLY — it never opens the PR**
(inline, or a delegated multi-repo builder). Opening it here reorders deliver
(8) ahead of review (7), letting the operator merge before fixes exist — they
orphan onto a merged branch (#320, 3×). The orchestrator opens a **draft** PR
for visibility — unmergeable until step 8, its "Draft" badge meaning "do not merge yet".

### 7. Review at milestones — fix everything found

After each milestone (completed phase, or full implementation for small plans),
invoke `superpowers:requesting-code-review` over spec + plan + code. Fix every
finding immediately, with tests; a factually wrong one gets refuting reasoning
(`superpowers:receiving-code-review`), never a silent drop. Keep a findings list.

### 8. Deliver — one PR per repo, all artifacts aboard

Verify first (`superpowers:verification-before-completion`): full test-suite
output, self-review pass, steps ticked. The PR goes mergeable ONLY now (after
step 7's fixes): `gh pr ready` on the draft — never say "ready to merge" before
this. PR body: summary + spec/plan paths; review findings and their fixes (plus
any refuted finding); the back-loaded manual phase marked "unimplemented —
operator pushes to this PR"; the Test Plan verbatim, labeled "post-merge —
operator-driven". Stop; the operator merges.

### 9. Post-merge close-out

When the operator reports the merge: **first verify the fix reached `main`** —
run `fr isolation verify-merge --branch <b>` (squash/rebase/merge-safe: checks
the branch's changes are present on `origin/main`, not commit ancestry, and the
PR is MERGED; exit 1 = not verified). Not verified → STOP and recover
(cherry-pick / fresh PR). Then drive the Test Plan if present (agent runs
checks, operator confirms what it can't reach), confirm phases complete (`fr
status`), `fr archive <plan-dir>`, commit via a housekeeping PR, `fr isolation
down`.
