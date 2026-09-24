# fr-goal: findings in scope, proportionality, per-step cost, independent spec review

- **Date:** 2026-09-24
- **Status:** designed
- **Origin:** gh#597 (measures 1 and 4), gh#593 (options 0 and 2)
- **Goal:** keep an fr-goal PR the size of its change, and make the run's
  own cost and its spec review observable, without weakening the
  evidence-backed verification that is fr-goal's clearest win.

## 1. Problem

gh#597 compared fr-goal against a plain "plan first" agent on a real
feature. The two produced behaviourally identical code. fr-goal was 4× slower,
7× more expensive and 3–4× larger. Two of the causes it names are
procedural and are addressed here:

- **Scope ratchet.** The skill says "fix every finding". Nothing asks whether
  a finding belongs to the change. Independent reviewers always find
  something, much of it pre-existing, so every finding becomes code in the
  feature PR. The fr-goal manifest makes this structural:
  `review-phase --state done` refuses while any finding against the phase is
  still effectively open. The only non-blocking exit for a true finding that
  is not this change's is `deferred --tracked-by <issue>`, which requires an
  issue to exist *now*.
- **No proportionality check.** Nothing compares the delivered diff with the
  plan. A scratch fixture that nothing loads shipped in the observed PR.

gh#593 found that the cost has moved to the one context nothing bounds, the
**main session**, and that `spec-review` is a bare `kind: agent` step: the
author reviews its own spec in the same session, with no evidence. Its
options 0 (measure per step) and 2 (independent spec reviewer) are the cheap,
decision-enabling ones.

The cursor already records an `Attempt` for every orchestrator-run flat step
(`step/spec-review`, `step/plan`, `step/deliver`) with window, session and
model. Its `measured` field is always empty, because
`fr.run.telemetry.measure_dispatch` only looks for a sidechain (subagent)
transcript. The main thread's usage for that window is in the same session
file.

## 2. Design

### A. Findings: fix in scope, file the rest (gh#597 §1)

- **New resolution state `out-of-scope`.** `fr journal resolve <id> --state
  out-of-scope --note "<why this change did not cause it>"`. The note is
  required. `EffectiveFindingState` gains `out-of-scope`. It is **not open**:
  the `review-phase` findings gate, `fr journal check` and `journal-check` do
  not count it. A later `deferred --tracked-by <issue>` supersedes it (last
  record wins, the existing fold).
- **Operator guard, structural.** `fr journal resolve --state fixed` on a
  finding whose effective state is `out-of-scope` exits 2 unless the new flag
  `--answered-by operator` is passed. It is the same vocabulary as `fr run
  resolve --answered-by`, and the record carries it as an `answered_by`
  header token. "An out-of-scope finding is never fixed in the feature PR
  without an operator decision" is therefore an invariant, not prose.
- **Classification moment.** The review brief (the `review-phase` manifest
  comment, fr-goal SKILL §6, and the new spec reviewer of §E) asks the
  reviewer to tag each finding `in-scope` or `out-of-scope` with a one-line
  reason:
  - **in scope:** the change is wrong, incomplete, or worse than it needs to
    be. An asymptotically worse algorithm than necessary is in scope.
  - **out of scope:** true, but not caused by this change (pre-existing,
    adjacent, nice-to-have).
  - **refuted:** as today.

  The orchestrator's decision is the resolution record itself.
- **Delivery.** `fr journal render --section findings` renders out-of-scope
  findings as their own group. `deliver` puts that group in the PR body and
  offers the operator an issue per finding. The operator's choice becomes
  `deferred --tracked-by #N`, or the finding stays `out-of-scope`.
- **Artifact versioning.** A journal with `state=out-of-scope` or an
  `answered_by` token is rejected by an older `fr`, so this is a shape change for the `journal` kind: stamp 1 → 2,
  a registered migration (stamp only; no body change, since every v1 journal
  is a valid v2), and the structure validator accepting the new state. This
  is the journal kind's first move past 1. The plan decides where its stamp is
  carried, per `.claude/rules/artifact-versioning.md`.

### C. Proportionality report (gh#597 §4)

- **Plan input.** `PhaseHeader` gains two optional, defaulted fields:
  - `files: tuple[str, ...] = ()` holds the repo-relative globs the phase
    expects to touch (`*` spans `/`, as in `.fr-isolation-allow`);
  - `estimate_lines: int | None = None` is the expected added plus deleted
    lines.

  `PhaseHeader` is `extra="forbid"`, so this is a plan shape change: stamp
  2 → 3, a stamp-only migration, and validator support. `fr-plan` asks for both
  fields per agentic phase. `fr plan self-review` **warns** (never fails) on an
  agentic phase with no `files`.
- **Command.** `fr plan proportionality <plan-dir> [--base <ref>]`. The base
  defaults to `origin/<default>`, via the same helper `fr status` uses since
  #592. It always exits 0 and prints three sections:
  1. **Unreferenced new files.** Added files whose repo-relative path, and
     whose stem when it is at least 4 characters, appear in no other tracked
     file. fr's own artifacts (spec, plan, journals, runs, acceptance reports)
     are exempt.
  2. **Out-of-plan touches.** Changed files matching no phase's `files` glob,
     with the same artifact exemptions. A touch is *justified* when a journal
     finding or deviation entry names its path, and the report says which
     entry. When no phase declares `files`, this section says so rather than
     flagging every file.
  3. **Size.** Added plus deleted lines against the summed `estimate_lines`.
     Above 2× the report flags it and asks for a justification line in the PR
     body. With no estimate, the size is printed without a ratio.
- **Delivery: derived evidence, not a new step.** `deliver` gains `evidence:
  [tests, proportionality]`. Like `review-phase`'s `findings`, it is
  **derived**: `fr run resolve --step deliver --state done` runs the report
  itself and stores its SHA-256 on the unit's evidence. The caller never
  passes it, and `--evidence proportionality=` is refused. The orchestrator
  pastes the same report into the PR body. A new step would drift every
  in-flight cursor; an evidence key does not, because drift compares step ids.
- **Report first.** Nothing in the report blocks. Whether any section should
  become a gate is a later decision, made with runs' reports in hand.

### D. Main-session cost per step (gh#593 option 0)

- **Shape.** `StepRecord.main_session: MainSessionUsage | None`, where
  `MainSessionUsage` = `input_tokens`, `cache_creation_input_tokens`,
  `cache_read_input_tokens`, `output_tokens` (all required, matching
  `MeasuredTokens`' atomicity), plus `turns: int` and `cost_usd: float | None`.
  The last is only what the harness itself reports.
- **Window.** fr-goal's top-level steps are sequential, so a step's window is
  `(previous step's at, this step's at]`, with the run's `started` bounding the
  first. Measuring the **step** rather than the attempt covers `brainstorm`,
  which has no attempt, and the whole `implement` loop, including the
  orchestrator's dispatch, handoff and debugging turns.
- **When.** Written at the moment fr marks a top-level step `done` (`resolve`
  for agent steps, `advance` for cli steps). Like all telemetry, it never
  raises: an unreadable source leaves `main_session` absent, which reads as
  "not observable", never zero.
- **Claude Code reader.** A new `TranscriptReader.measure_main_session(session,
  start, end)` sums assistant records in the session file with
  `isSidechain` not true, a real model and a timestamp in the window. Records
  are deduplicated by message id, because Claude Code writes one record per
  content block with the same usage. `turns` counts distinct message ids.
  `cost_usd` is `None`.
- **OpenCode reader.** `OpenCodeReader` reads the session database read-only
  (default `~/.local/share/opencode/opencode.db`, overridable by
  `FR_OPENCODE_DB`). The session is the run's bound session when one is
  recorded. Otherwise it is the **unique** top-level session
  (`parent_id IS NULL`) whose `directory` is the run's workspace or its base
  clone and which has assistant messages in the window. More than one
  candidate means nothing is recorded, never a guess. Tokens come from each
  assistant message's `data.tokens`, with `reasoning` folded into
  `output_tokens`, a mapping the reader's docstring states. `cost_usd` is the
  sum of `data.cost`. OpenCode *dispatch* measurement stays `None`, unchanged
  and stated.
- **Hermes** has no reader and records nothing. `fr.harness`'s `parity.yaml`
  gains a `main-session-cost` row: claude-code and opencode wired, hermes
  absent.
- **Reporting.** `fr run cost <run-id>` prints gh#593's table. For each
  top-level step it shows turns, the four token figures, cache-read per turn
  and cost when known, then a subagent line summing `attempts[].measured`. A
  missing measurement prints as `—`, never `0`.
- **Artifact versioning.** This adds a field to an `extra="forbid"` model that
  a released `fr` reads, so it is a shape change: run stamp 5 → 6, a
  stamp-only migration, and validator support. The change is additive, so no
  legacy model is frozen. The chain assertion extends to
  `[2, 3, 4, 5, 6]`.

### E. Independent spec review (gh#593 option 2)

- **Agent.** A new `plugins/super-fr/agents/fr-spec-reviewer.md`: read-only
  (Read, Grep, Glob), `standard` tier. Its brief checks three things. The
  spec must match the spec journal's `decision` entries (the operator's Q&A).
  Every file, helper, command and service the spec names must exist. The
  spec must be internally consistent. It tags each finding in-scope or
  out-of-scope (§A) and returns them as a structured list. It writes nothing.
  The orchestrator journals its findings as spec-scope `finding` entries and
  one `review` entry naming the reviewer's dispatch id.
- **Manifest.** `spec-review` gains `agent: super-fr:fr-spec-reviewer` and
  `evidence: [review, reviewer, findings]`. The evidence verifier generalizes
  from "plan journal, `kind=review` with `phase=N`" to a per-step journal
  scope: `spec-review` verifies against the **spec** journal with no phase.
  `reviewer` keeps its existing rule: fr refuses an id that is not a subagent
  this session dispatched after the step opened, which excludes the
  orchestrator that wrote the spec.
- **Mirrors and install.** OpenCode per-tier agent files are generated by
  `scripts/sync-opencode.py`. The fr-goal skill mirrors are regenerated by
  both sync scripts. `install.sh` ships the agent, and the org
  agent-worktree allowlist gains it if the hook would otherwise force a
  worktree on it.

### Cross-cutting

- **Version:** minor bump (new command, new agent, new mandatory evidence).
- **Explainer:** `docs/explainers/01-fr-goal.md` is updated and re-rendered
  (`.claude/rules/explainers-currency.md`).
- **Non-goal, restated from gh#597:** nothing here weakens `deliver`'s
  `--evidence tests=<log>` gate.

## 3. Test Plan

**In this PR:**

1. Journal: `resolve --state out-of-scope` requires a note, folds to a
   non-blocking state, and is superseded by `deferred --tracked-by`. The
   `review-phase` findings gate and `fr journal check` pass with only
   out-of-scope findings open. `resolve --state fixed` on an out-of-scope
   finding exits 2 without `--answered-by operator` and succeeds with it.
2. Journal, plan and run migrations: each kind's chain reaches its new version,
   and `fr validate artifacts` passes on this repo after `fr migrate artifacts
   --yes`.
3. Proportionality: a fixture repo with an unreferenced new file, an
   out-of-plan touch (one justified by a journal entry, one not), and a diff
   above and below 2× of `estimate_lines` produces the expected three
   sections. With no `files` declared, the report says so. It always exits 0.
4. `deliver` resolve derives and stores the proportionality evidence and
   refuses a caller-supplied `proportionality=`.
5. Claude Code main-session reader: a synthetic transcript with sidechain and
   main-thread records, duplicate message ids and records outside the window
   yields exact sums and turns.
6. OpenCode reader: a fixture SQLite database with two top-level sessions and
   one child session yields the bound session's sums and cost, nothing when
   two unbound sessions qualify, and ignores the child session.
7. `fr run cost` renders measured, unmeasured (`—`) and subagent rows.
8. Spec-review evidence gate: `resolve --step spec-review --state done`
   refuses without a spec-journal `review` entry, refuses while a spec-scope
   finding is open, and refuses a reviewer id equal to the orchestrator's.
   The shipped manifest passes `fr workflow check`.
9. Mirror, install and parity tripwires stay green with the new agent and
   the new `parity.yaml` row.

**Post-merge, operator-driven:**

10. Run `/fr-goal` on a small public `derio-net` task under Claude Code, then
    under OpenCode. `fr run cost` shows a measured row for every top-level
    step. `spec-review` was answered by a dispatched `fr-spec-reviewer`. The
    PR body carries the proportionality report and an out-of-scope group, or
    states there is none.

## 4. Scope

**Deferred to follow-up issues:**

- gh#597 §3 (Performance section in spec, plan, tests and review);
- gh#597 §2 and gh#593 option 1 (a cheaper orchestrator model, or restarting
  it at step boundaries). Both issues gate these on measurements, which §D
  makes possible;
- gh#593's measurement campaign itself, which is operational, not code.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-24-fr-goal-scope-proportion-cost | `derio-net/super-fr` | `2026-09-24-fr-goal-scope-proportion-cost` | — |
