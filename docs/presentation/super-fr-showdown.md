---
marp: true
theme: default
title: "super-fr under the microscope — half 1 (finished) + half 2 (preview)"
---

# super-fr under the microscope

Half 1: what ships and why (finished) · Half 2: fair fight, live later (preview)

Dev team · OpenCode · pinned model: OpenAI Terra, default effort
Thesis, open: **is all this ceremony worth it as models get more capable?**

---

## What super-fr is

Describe a feature → get back a reviewed PR. Two Claude Code plugins
(`super-fr`, `super-fr-dispatch`) plus a small CLI (`fr`) wrapping
[superpowers](https://github.com/obra/superpowers) with phase-structured plans,
mandatory git-worktree + devcontainer isolation, and an optional fan-out of a
merged plan's phases to autonomous runners (VibeKanban today, CNC daemon too).

Most of the time you type one thing: `/fr-goal <description>`.

---

## Two flows, one artifact family

Both flows share the spec (`docs/superpowers/specs/`) and the plan-as-folder
(`docs/superpowers/plans/<slug>/_meta.yaml + _prose.md + NN.yaml` per phase).

- **Flow 1 — goal to PR, locally:** brainstorm → spec → plan → TDD → review →
  single PR. Every phase lands as commits on one branch.
- **Flow 2 — dispatch to a runner:** `fr apply <plan> --to <runner>` mirrors each
  phase to a tracking Issue; a bridge daemon hands ready phases to the runner;
  each phase returns as its own PR. Without `--to`, `fr apply` is tracking-only.

One plan = one repo's worth of work; cross-repo features coordinate through the
shared spec's "Implementation Plans" section.

---

## The core bet: the pipeline is a manifest, not a script

`plugins/super-fr/workflows/fr-goal.yaml` — 7 steps. Each step declares:

- `kind: cli` → `fr` executes it directly; the exit code is the verdict.
  Nobody interprets the output.
- `kind: agent` → `fr` never executes it; it prints a dispatch brief
  (`skill/agent/needs/emits/tier/for_each`), you do the work, then
  `fr run resolve --step <id> --state done --emitted name=path`.
- `gate: operator` → hard stop until a person answers. One promised gate.
- `needs` / `emits` → named artifacts, so later steps find earlier outputs and
  `fr` can refuse to dispatch what doesn't exist yet.

Why: the engine stays a plain program you can re-run for the same answer, with
no path that could call a language model even by accident. Cost: the YAML alone
says nothing about *meaning* — that lives in the skills it points at.

---

## The run keeps its place (`fr run`)

`fr run start <shape> --branch <b>` resolves the shape, ensures isolation, and
writes `docs/superpowers/runs/<run-id>.yaml` **inside the workspace** — cursor +
one record per step (pending/running/blocked/done/failed) plus emitted paths.
`advance` moves it, `status` prints it, `check` fails loudly on a failed cursor.

Two details that matter: a failed step does **not** move the cursor (a stalled
run keeps reporting the same step), and the file rides the feature branch into
the PR — the reviewer sees the journey, not just the diff. Archived with the
plan after merge.

Why I chose it: without a cursor, progress lives in chat and dies with it.

---

## Isolation first — no unisolated fallback

`fr run start` creates the workspace **before** anything else: a git worktree at
`~/.cache/fr/worktrees/<repo>/<branch>` plus the repo's devcontainer profile.
Reads/edits happen on the host worktree; every build/test/lint goes through
`fr isolation exec -- …`. Secrets stay host-side
(`~/.config/fr/secrets/<repo>/<profile>.env`), least-privilege default profile.
`down` refuses while the PR is open, so cleanup can't race your final pushes.

Backstops, not a security boundary: `.fr-isolation` marker, the
`fr-isolation-required` edit hook (`plugins/super-fr/hooks/`), the
`fr-isolation-guard` bash guard. Escapes: enter isolation (the answer),
`.fr-isolation-allow`, or `FR_BASE_OK=1` for one deliberate base edit.

Why: a brainstorm that dies leaves the base pristine; a build never relocates.

---

## One batched Q&A, then autonomy

The agent studies the codebase first, then collects **every** operator-owned
decision into ONE question round (≤4, recommended-first) — including the
post-merge Test Plan question for deployables and a model-per-tier question if
unbound. Unanswered = hard stop, never a default.

After that: no spec/plan approval gates — those become agent-driven
review-and-fix passes. The agent stops only where a human is genuinely needed:
missing answers/access, secrets/UI/deploys (manual phases), the PR merge
(never self-merged), post-merge validation in the real environment.

Why: dripped interruptions and guessed scope are the two failure modes this kills.

---

## Spec + acceptance matrix: code ≠ proven behavior

Your answers become the spec; the checkable promises become rows in
`docs/acceptance/matrix.yaml` — one "operator can X" per row, starting at
`not-implemented`, flipped up (`skipped → ci/scheduled`) only with test
evidence, `failing` breaking CI by design. Born at brainstorm time, presented
with a one-line defense each, linked to plan phases (`acceptance: [ids]`,
self-review errors on unlinked Test-Plan rows).

Driven by `fr-acceptance`, gated per-PR by `acceptance-report.yml`.
Why: it stops completed code from being mistaken for proven behavior — and the
debt stays visible in the PR instead of being called done.

---

## Plan + self-review: the deterministic gate

`fr-plan` divides the spec into phases with TDD-shaped steps (P1.T1.S1 ids),
`depends_on`, per-phase `tier`, and acceptance links; manual work is corralled
into `[manual]` phases (back-loaded by default — ships unimplemented, operator
pushes to the same PR; front-loaded only when agentic work depends on it).

Then `fr plan self-review` runs as a `kind: cli` step: dependency cycles, manual
work hiding in agentic phases, unknown acceptance IDs, unresolvable shape refs —
exit code decides, nobody judges "looks fine". Fix, re-`advance`.

Why: catch orchestration bugs before tokens burn.

---

## Build → review → fix, in a loop

Per phase in dependency order, ONE `fr-phase-executor`
(`plugins/super-fr/agents/fr-phase-executor.md`) gets `fr pickup` + spec +
journal render: failing test first, implement, clean up. Model per phase `tier`
via `fr models resolve --harness <h>`. The journal **is** the handoff. Branch
pushed, PR **not** opened here (opening early orphaned fixes onto merged
branches — #320).

After each milestone: `requesting-code-review` over spec + plan + code; every
finding fixed with tests or refuted with reasoning — recorded as
`finding open|fixed|refuted`. Draft PR first, `gh pr ready` only after fixes +
full suite. Merge-race guard: draft state + merged-PR push guard +
post-merge content verification.

---

## Standalone skills: same discipline, smaller scope

- **`fr-brainstorming`** — superpowers brainstorming inside isolation from the
  first command; standalone = interactive with section approvals, under fr-goal
  = the batched-Q&A contract. Ends by presenting acceptance rows with defenses.
- **`fr-debugging`** — systematic-debugging in isolation (reuse the feature
  workspace if the bug surfaced mid-goal, else fresh `fix/<slug>`). Iron Law, four
  phases, debug journal flushed as-you-go (`repro/hypothesis/ruled-out/root-cause`),
  ONE fix-PR. Two hard stops only: no confident hypothesis, or 3 failed fixes →
  question the architecture.
- **`fr-plan` / `fr-execute` / `fr-isolation` / `fr-init` / `fr-progress`** —
  plan authoring, single-phase TDD execution, workspace lifecycle, first-run
  profile scaffolding interview, status/drift audit.

---

## Custom flows: `fr run` is a CLI every harness drives identically

Need a different pipeline? Author `docs/superpowers/workflows/<name>.yaml` —
repo file wins **wholesale** (no field merging: half-mine/half-shipped steps fail
invisibly). `fr workflow check` validates: unique ids, `cli` has `run:`, every
`needs` emitted upstream, no cycles, known capabilities. This very deck runs on
one (`presentation-showdown`: outline → experiment-design → review → instrument
→ record-compare → deliver-deck).

Shapes resolve repo → `$FR_SHIPPED_WORKFLOWS_DIR` → the `fr` wheel's own copy
(version-matched, so upgrades can't silently run stale shapes) → marketplace
clone — which is why `fr run start fr-goal` works on hosts with no plugin
installed at all.

---

## Integration points

- **Claude Code:** hooks (`fr-isolation-required`, `fr-phase-executor-guard` —
  the executor must NOT get its own worktree, #420 — plus push/sentinel guards),
  rules (`fr-worktree-override`, `fr-plan-override`, `no-claude-p-batch`),
  `fr-phase-executor` agent, status-line segment.
- **OpenCode:** TypeScript port of the edit guard
  (`packages/fr-opencode-plugin`, `tool.execute.before`), skills + instructions
  mirrored from canonical by `scripts/sync-opencode.py` (CI tripwires on drift).
- **Hermes:** skills under `~/.hermes/skills/fr/`, SOUL rules block, shell-hook
  guards (edits AND bash/push), `delegate_task(goal, context)` phase dispatch —
  the journal-fed brief travels in `context`. No shipped model bindings on
  purpose; first run asks and persists via `fr models set`.
- **Git servers:** `gh`/`glab`/`tea` behind `detect_backend()`; `fr apply`
  dry-run by default, reachability gate (plan + spec on `origin/HEAD` — runners
  check out main), label lifecycle `fr:ready → in-progress → pr-ready`
  (+`blocked`/`synced`/`manual`). Runners: `fr-vk` (VibeKanban MCP + cron
  bridge), `fr-cncd`.

---

## Half 2 preview: the fair fight (recordings pending)

Same seed prompt (`experiment/prompts/goal.md`, SPARK-4-derived), same pinned
model (Terra, default effort), unlimited-but-logged corrections, two fresh
branches from same `origin/HEAD`: fr-goal vs vanilla plan/execute. asciinema →
HyperFrames side-by-side, chapters at Q&A / spec / plan / implement / review /
PR. Runbook: `experiment/runbook.md`.

---

## The comparison — empty until measured (no presumed winner)

| Metric | fr-goal | Vanilla |
|---|---|---|
| Acceptance rows passed | … | … |
| Wall time / operator time | … | … |
| Tokens in/out, $ | … | … |
| Tests added, coverage Δ | … | … |
| Lint / typecheck clean? | … | … |
| Findings fixed / refuted / missed | … | … |
| Artifacts (spec/plan/journal/run) | … | … |

Closing question, not a verdict: **is all this ceremony worth it, given
increasing model capabilities?** The numbers decide — per task class, not in
general.
