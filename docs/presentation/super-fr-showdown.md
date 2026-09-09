---
marp: true
theme: default
title: "super-fr under the microscope"
---

# super-fr under the microscope

Half 1: what ships and why · Half 2: fair fight (fr-goal vs vanilla)

Dev team · OpenCode · model: OpenAI Terra, default effort — Thesis: **is the ceremony worth it?**

---

## What super-fr is (one slide)

Describe a feature → reviewed PR. Two plugins + `fr` CLI wrapping superpowers:
phase-structured plans, mandatory worktree + devcontainer isolation, optional
fan-out to async runners. Same artifacts both flows: spec + plan-as-folder.

---

## Two flows, shared artifacts

- Flow 1 local `/fr-goal`: one session, one branch, single PR.
- Flow 2 `fr apply --to <runner>`: merged plan → per-phase Issues → one agent
  per phase, one PR each. Tracking-only without `--to`.

---

## fr-goal is a manifest, not a script

`plugins/super-fr/workflows/fr-goal.yaml`: 7 steps. `kind: cli` = deterministic,
exit code is verdict. `kind: agent` = brief + `fr run resolve`. `gate: operator`
= one promised stop. Bet: engine stays a plain program with no LLM call path.

---

## Run cursor (`fr run`)

`start/advance/resolve/status/check` + `runs/<id>.yaml` committed on the branch.
Failed step holds the cursor. Bet: resumable, reviewable in the PR, survives
compaction. Cost: one more artifact to keep honest.

---

## Isolation first

`fr run start` ensures worktree + devcontainer BEFORE brainstorming. Exec-bridge:
edits on host, every command via `fr isolation exec`. No unisolated fallback.
Bet: dead brainstorms leave base pristine. Cost: profile setup per repo.

---

## One batched Q&A

Explore first, then ≤4 questions, recommended-first, unanswered = hard stop.
Bet: kills dripped interruptions + guessed scope. Cost: front-loaded latency.

---

## Spec + acceptance matrix

Spec records design; `docs/acceptance/matrix.yaml` rows
(`not-implemented → skipped → ci/scheduled`, `failing` breaks CI) pin each
"operator can X". Self-review errors on unlinked Test-Plan rows.
Bet: code ≠ proven behavior. Cost: rows must be written + defended.

---

## Plan + self-review (deterministic gate)

Phases with TDD steps, `depends_on`, `tier`, `acceptance:` links.
`fr plan self-review`: cycles, hidden manual work, bad IDs. Bet: catch
orchestration bugs before tokens burn. Cost: plan authoring discipline.

---

## Manual phases + build/review loop

`[manual]` back-loaded by default (ships unimplemented, operator pushes to same
PR). Per-phase executors, journal-fed handoff, per-tier models. Every review
finding fixed or refuted with reasoning; draft PR → `ready` only after fixes +
full suite. Bets: secrets don't masquerade as agent work; fixes don't orphan
onto merged branches (#320, merge-race guard).

---

## Standalone: fr-brainstorming / fr-debugging

Interactive design-in-isolation; Iron-Law debugging with debug journal
(`repro/hypothesis/ruled-out/root-cause`) and two hard stops
(no-confident-hypothesis, 3-failed-fixes → question architecture).

---

## Custom flows + integrations

- Shapes: repo `workflows/<name>.yaml` wins wholesale, `fr workflow check`.
  This very deck runs on one (`presentation-showdown`).
- Harnesses: Claude Code hooks/rules; OpenCode TS plugin + mirrored
  skills/instructions; Hermes skills/hooks + `delegate_task(goal, context)`.
- Git servers: `gh`/`glab`/`tea`, dry-run `apply`, reachability gate
  (on `origin/HEAD`), label lifecycle, VK/CNCD runners.

---

## Half 2: fair fight — PENDING RECORDINGS

Same prompt (`experiment/prompts/goal.md`, SPARK-4-derived), same model,
unlimited-but-logged corrections. asciinema → HyperFrames side-by-side.
Comparison table filled from measurements only — no presumed winner.

---

## The question (not a verdict)

| Metric | fr-goal | Vanilla |
|---|---|---|
| Acceptance rows passed | … | … |
| Wall / operator time | … | … |
| Tokens in/out, $ | … | … |
| Tests, coverage Δ, lint/typecheck | … | … |
| Findings fixed/refuted/missed | … | … |

**Is all this ceremony worth it, given increasing model capabilities?**
The numbers above decide — per task class, not in general.
