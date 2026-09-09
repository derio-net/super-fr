---
marp: true
theme: default
title: "super-fr: every ceremony was a scar"
---

# super-fr: every ceremony was a scar

Half 1: the pain → the mechanism (finished) · Half 2: the receipts, live later (preview)

Cold-start friendly: no superpowers knowledge assumed.
Stance: **the ceremony earns its keep** — each piece exists because the
un-ceremonied version failed. Half 2 measures it.

- **Say:**
  - "This talk has two halves. First: why super-fr looks the way it does — every awkward piece was a real failure first."
  - "Second, later: the same feature built twice, fr-goal vs vanilla, same model, measured. I believe the ceremony pays. The numbers get a vote too."

---

## Orientation: what superpowers (and openspec) gave us

Both plugins supply what raw prompting lacks: **structure** — brainstorm a design,
write a plan, execute it, review. Openspec is the heavier, spec-artifact-driven
cousin; superpowers is the leaner loop (brainstorming, test-driven-development,
requesting/reviewing code review, finishing a branch). I settled on superpowers
as the base because lean composes — and then kept hitting the same gaps using it
for real features.

- **Say:**
  - "If you've never used either: they turn 'build X' from one giant prompt into stages with artifacts. That alone fixes 'the model forgot the design halfway through.'"
  - "Openspec leans on change-proposals; superpowers leans on a tight brainstorm→TDD→review loop. I picked superpowers because there was less to fight when I started bolting things on."
  - "Everything after this slide is a gap I actually hit, in order."

---

## Scar 1: two features at once was impossible

Working on multiple features meant one checkout, stashed halves, stray state —
and any brainstorm that died left litter in the base repo. So: **mandatory
worktree isolation**. `fr isolation up --branch <b>` cuts a worktree at
`~/.cache/fr/worktrees/<repo>/<branch>` from fresh `origin/<default>`, plus the
repo's devcontainer. Reads/edits on the host worktree; every command via
`fr isolation exec -- …`. Then the env problem surfaced: runs need tools AND
secrets without leaking them — hence **profiles** (`.devcontainer/<profile>/`)
with a host-side secrets env-file per profile, least-privilege default.

- **Say:**
  - "The first scar. I couldn't hold two features in my head because the repo couldn't hold them either."
  - "There is no unisolated fallback — that word 'mandatory' is doing work. A brainstorm that dies leaves the base pristine."
  - "Backstops, not a security boundary: `.fr-isolation` marker, the edit hook, the bash guard. Escapes exist and are documented."
- **Ref:** `plugins/super-fr/skills/fr-isolation/SKILL.md`, `plugins/super-fr/hooks/fr-isolation-required.sh`

---

## Scar 2: nothing tested what the user was promised

Unit tests passed and the feature still didn't do the thing. The missing layer
was **high-level acceptance**: concrete "operator can X" claims with evidence.
So the **acceptance matrix** (`docs/acceptance/matrix.yaml`): rows born at
brainstorm time (`fr acceptance add`, never hand-edited), starting at
`not-implemented`, flipped up (`skipped → ci/scheduled`) only with test
evidence, `failing` breaking CI by design. Plan phases link rows
(`acceptance: [ids]`); self-review errors on Test-Plan specs with zero links.

- **Say:**
  - "Green suite, broken promise. I needed a layer that says what the user can do now — and refuses to be called done without proof."
  - "Rows are presented with a one-line defense at brainstorm close. Silent row creation is not agreement on scope."
  - "The debt stays visible in the PR. That's the point — it's embarrassing by design."
- **Ref:** `fr acceptance {init,add,check,status,report}`, `.github/workflows/acceptance-report.yml`

---

## Scar 3: drift, and building the wrong thing confidently

Two related failures: the build wandered from the design (drift), and the design
was wrong but executed flawlessly. Three mechanisms answer them: the **walking
skeleton** (first agentic phase proves the hardest integration early or the plan
is fiction), **actual TDD with a refactoring step** (failing test → implement →
refactor-or-`no-refactor-because`), and **review after each phase**
(`requesting-code-review` over spec + plan + code; every finding fixed with
tests or refuted with reasoning — recorded `open|fixed|refuted`, never silently
dropped).

- **Say:**
  - "Drift is what happens when the plan is a rumor. The skeleton makes phase one prove the plan touches reality."
  - "'Actual TDD' is a dig at myself — I was writing tests after. The refactor step being explicit is what made it real."
  - "Review-per-phase, not review-at-end: a finding at the end is a rewrite; a finding per phase is a fix."
- **Ref:** `plugins/super-fr/skills/fr-execute/SKILL.md`, `plugins/super-fr/skills/fr-goal/SKILL.md`

---

## Scar 4: the markdown plan didn't survive contact

The original superpowers plan was one markdown file: unmergeable, untickable by
tooling, position kept in the model's head. So I broke it up: **plan-as-folder**
(`docs/superpowers/plans/<slug>/` — `_meta.yaml`, `_prose.md`, one `NN.yaml`
per phase, step ids `P1.T1.S1`) — plus a **durable run cursor**
(`docs/superpowers/runs/<run-id>.yaml` via `fr run start/advance/resolve`).
`fr plan self-review` runs as a deterministic gate: dependency cycles, manual
work hiding in agentic phases, unknown acceptance IDs, unresolvable shape refs —
exit code decides, nobody judges "looks fine."

- **Say:**
  - "A plan the tooling can't read is a wish. Per-phase files also kill the parallel-merge conflict."
  - "The cursor is the other half: failed step holds position, the file rides the branch into the PR, so the reviewer sees the journey."
  - "Self-review before any token burns on implementation — orchestration bugs are cheapest here."
- **Ref:** `plugins/super-fr/workflows/fr-goal.yaml`, `packages/fr/src/fr/commands/run_cmd.py`

---

## Scar 5: the session rotted as it grew

Long runs compacted, forgot, and bled context across phases. Answer: **one
subagent per phase, journal-fed** — `fr pickup` plus the spec plus
`fr journal render --scope plan` is the whole handoff; discoveries are written
down phase by phase, and acceptance rows flip only on evidence. Phase difficulty
routes the model: per-phase `tier` (`mechanical|standard|hard`) resolved via
`fr models` (repo override > user, per harness). And the one hard lesson (#420):
the phase executor must NOT get its own worktree — a second worktree cut from
`main` can't see the spec/plan, writes get denied, yet dispatch succeeds, so the
run looks healthy while doing nothing.

- **Say:**
  - "Session creep is the silent killer of long runs. The journal is the handoff — phases don't remember, they read."
  - "Tiers are honesty about difficulty: don't burn the big model on mechanical work, don't starve the hard phase."
  - "#420 is my favorite scar: the run was green and nothing happened. Two isolations don't compose."
- **Ref:** `plugins/super-fr/agents/fr-phase-executor.md`, `plugins/super-fr/hooks/fr-phase-executor-guard.sh`

---

## The frame that holds the scars: workflow shapes (the core idea)

Every mechanism above is a step; the **shape** is the list of steps, as data.
`plugins/super-fr/workflows/fr-goal.yaml` — 6 steps plus 2 grouped children
under `implement`. `kind: cli` executes (exit code = verdict);
`kind: agent` never executes — it prints a dispatch brief you fulfill, then
`fr run resolve`. `gate: operator` is the one promised stop. `needs`/`emits`
wire the artifacts. `fr workflow check` rejects dup ids, command-less `cli`
(which would exit-0 doing nothing), dangling `needs`, cycles, unknown
capabilities. A repo overrides wholesale (`docs/superpowers/workflows/<name>.yaml`
— never merged; half-mine/half-shipped fails invisibly). This very deck runs on
one: `presentation-showdown`.

- **Say:**
  - "This is the slide I'd save if the projector died. Everything so far is a step; the shape is what turns steps into a pipeline you can validate, resolve, and re-run."
  - "The engine is a plain program with no path to an LLM — every judgment call happens on the far side of a visible handoff."
  - "Thesis in one line: the ceremony is not overhead, it's the scar tissue — and it's data, so it's checkable."
- **Ref:** `packages/fr/src/fr/workflow/{model,check,resolve}.py`

---

## fr-goal end to end (what the shape runs)

Brainstorm → ONE batched Q&A (≤4, recommended-first, unanswered = stop) → spec →
spec-review → plan → `plan self-review` → per-phase TDD executors → per-phase
review → draft PR → `gh pr ready` only when green → operator merges (never
self-merged) → `verify-merge` (content-presence, squash-safe) → post-merge Test
Plan walked through together → archive + teardown. Manual work
(secrets/UI/deploys) rides `[manual]` phases: back-loaded by default (ships
unimplemented, operator pushes to the same PR), front-loaded only when agentic
work depends on it. Two more scars inside: #320 (PRs opened before review left
fixes orphaned on merged branches — hence draft-first + push guard) and the
merge-race guard (draft state + post-merge content verification).

- **Say:**
  - "One operator touchpoint on the happy path. Everything else is the agent working the shape."
  - "Manual phases are labeled, not hidden. That's a moral position disguised as a schema field."
  - "The agent never merges. Merge is yours, and the Test Plan after it is driven together."
- **Ref:** `plugins/super-fr/skills/fr-goal/SKILL.md`, `docs/explainers/01-fr-goal.md`

---

## Standalone skills (same discipline, smaller scope)

- **`fr-brainstorming`** — interactive design-in-isolation with section approvals
  (under fr-goal it obeys the batched contract instead). Ends presenting
  acceptance rows with defenses.
- **`fr-debugging`** — Iron-Law debugging in isolation (reuse the feature
  workspace if found mid-goal, else fresh `fix/<slug>` from `origin/<default>`).
  Debug journal flushed as-you-go (`repro/hypothesis/ruled-out/root-cause`);
  two hard stops only: no confident hypothesis, or 3 failed fixes → question the
  architecture. ONE fix-PR, body rendered from the journal.
- **`fr-plan` / `fr-execute` / `fr-init` / `fr-progress`** — authoring, single-phase
  execution, first-run profile interview, read-only status/drift audit.

- **Say:**
  - "You don't always need the whole pipeline. The skills are the pipeline's steps, usable alone, same isolation."
  - "Debugging's journal is the one I'd steal for any workflow: the rejected-hypothesis trail is what compaction eats first."

---

## Integrations in 4 minutes (cut candidate)

- **Claude Code:** full hook surface (edit gate, bash guard, executor guard,
  push guard, session bind/unbind, worktree create/remove, acceptance nag),
  4 rules, executor agent, status-line segment, `derio-net--super-fr`
  marketplace (the bare org name is retired — two repos evicted each other).
- **OpenCode:** TS port of the edit guard (`tool.execute.before`) — known gap,
  bash ungated; skills/instructions mirrored by `sync-opencode.py` with CI
  tripwires. Never hand-edit generated files.
- **Hermes:** skills + SOUL rules block + shell-hook guards (edits AND bash),
  `delegate_task(goal, context)` carrying the journal-fed brief; no shipped
  model bindings — first run asks, `fr models set` persists.
- **Git servers + runners:** `gh`/`glab`/`tea` behind `detect_backend()`;
  `fr apply` dry-run by default; reachability gate (on `origin/HEAD`);
  `fr:ready → fr:in-progress → fr:pr-ready → (closed)` + `fr:blocked`,
  `fr:synced`, `manual`; `fr-vk` / `fr-cncd` runners via the `fr-dispatch`
  protocol.

- **Say:**
  - "If time dies, this is the slide that dies. One line each: Claude is the reference harness, OpenCode is edit-gated with a known bash gap, Hermes dispatches through context, git servers are a detected backend, not a rewrite."
  - "The install rule that matters: version bump on any shipped behavior change, or clients cache-stall."

---

## Half 2 preview: the receipts (recordings pending)

Same seed prompt (`experiment/prompts/goal.md`, SPARK-4-derived), same pinned
model (Terra, default effort), unlimited-but-logged corrections, two fresh
branches from same `origin/HEAD`: fr-goal vs vanilla plan/execute. asciinema →
HyperFrames side-by-side, chapters at Q&A / spec / plan / implement / review /
PR. Runbook: `experiment/runbook.md`.

- **Say:**
  - "Half 2 is the audit. Same prompt, same model, every nudge logged — then we count."
  - "I come in believing the ceremony pays. The table gets to disagree with me."

---

## The comparison — empty until measured

| Metric | fr-goal | Vanilla |
|---|---|---|
| Acceptance rows passed | … | … |
| Wall time / operator time | … | … |
| Tokens in/out, $ | … | … |
| Tests added, coverage Δ | … | … |
| Lint / typecheck clean? | … | … |
| Findings fixed / refuted / missed | … | … |
| Artifacts (spec/plan/journal/run) | … | … |

My position: **the ceremony earns its keep** — each row above should favor the
run that can't lose the design, the evidence, or its place. If a row doesn't,
that's a scar I haven't earned yet — and a shape change with its own migration.
