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

- **Out-of-scope is a fold state, written the way `deferred` is.**
  `fr journal resolve <id> --state out-of-scope --note "<why this change did
  not cause it>"`. `--note` is already required. The record is written as
  `state=open` plus an `out_of_scope=true` header token, never as a new
  `state=` value. This is exactly the `deferred` precedent
  (`journal/model.py`, the `EffectiveFindingState` comment):
  - `parse_journal` projects named tokens only, so an older `fr` ignores the
    new token and reads the finding as still **open**. That fails closed.
  - `EffectiveFindingState` gains `out-of-scope`. `open_finding_ids` counts
    only `open`, so the `review-phase` findings gate, `fr journal check` and
    `journal-check` stop counting it without further change.
  - A later `deferred --tracked-by <issue>` supersedes it. The last record
    wins, as the existing fold already works.
- **No journal version bump.** No older reader is broken, because the parser
  ignores unknown tokens. The `test_a_header_token_this_fr_does_not_know_is_ignored_not_fatal`
  guard is what keeps that true.
- **The reviewer's tag is persisted.** Finding entries gain an optional
  `review_scope=in|out` token, which the orchestrator copies from the
  reviewer's tag when it journals the finding. `fr journal render` shows each
  finding's tag. A finding tagged `in` but resolved `out-of-scope` renders as
  **reclassified by the orchestrator**, so moving a reviewer's in-scope finding
  out quietly is visible in the PR body.
- **Operator guard, enforced in the fold.** A finding whose effective state
  moves from `out-of-scope` to `fixed` requires the `fixed` record to carry
  `answered_by=operator`:
  - Enforced where every path meets: the fold used by `fr journal check` and
    the `review-phase` findings gate. That covers both `fr journal resolve`
    and `fr journal add --resolves … --state fixed`.
  - A violation is reported as an **unauthorized fix** and fails the check.
    It is not silently counted.
  - `--answered-by operator` is a new flag on both `resolve` and
    `add --resolves`.
  - **Claude Code** verifies it like the brainstorm gate does, with
    `operator_answered_since(<created time of the out-of-scope record>)`. With
    no answered question since then, the command refuses.
  - **OpenCode and Hermes** have no question tool, so the flag is recorded as
    stated and is advisory. A `parity.yaml` row says so.
- **Classification moment.** Three review briefs ask the reviewer to tag each
  finding `in-scope` or `out-of-scope` with a one-line reason: the
  `review-phase` manifest comment, fr-goal SKILL §6, and the new spec reviewer
  of §E. SKILL §2's "Fix every finding" is reworded to the same rule. The
  categories:
  - **in scope:** the change is wrong, incomplete, or worse than it needs to
    be. An asymptotically worse algorithm than necessary is in scope.
  - **out of scope:** true, but not caused by this change (pre-existing,
    adjacent, nice-to-have).
  - **refuted:** as today.
- **Delivery, with no new touchpoint.** `deliver` renders findings from
  **both** the spec and plan journals, and gives out-of-scope findings their
  own PR-body section. That section asks the operator which to file as issues.
  The question rides the existing merge touchpoint and never blocks
  `deliver`. After merge, each "file it" answer becomes `deferred
  --tracked-by #N` in the post-merge close-out. An unanswered one stays
  `out-of-scope`, which is visible and non-blocking.

### C. Proportionality report (gh#597 §4)

- **Plan input, following the `tier` and `skeleton` precedent.** `PhaseHeader`
  gains two optional, defaulted fields, both omitted from dumps when unset:
  - `files: tuple[str, ...] = ()` holds the repo-relative globs the phase
    expects to touch (`*` spans `/`, as in `.fr-isolation-allow`);
  - `estimate_lines: int | None = None` is the expected added plus deleted
    lines.

  This is the same treatment `tier`, `skeleton` and `acceptance` got. There is
  **no plan stamp bump**: `PlanMeta` and `PhaseDoc` stay `Literal[2]`. A plan
  that uses either field raises its `fr_version` floor to this release, which
  is the plan kind's existing "must update your fr_version" mechanism (the
  `types.py` module docstring). `fr plan create` writes that floor whenever
  the phases file sets either field. `fr-plan` asks for both fields per
  agentic phase. `fr plan self-review` **warns**, never fails, on an agentic
  phase with no `files`.
- **Command.** `fr plan proportionality <plan-dir> [--base <ref>]`. It diffs
  against the **merge-base** of `HEAD` and the base. The base defaults to
  `fr.git.remote_default_ref`. When that returns `None` or a `GitRefusal`, the
  report says it could not determine a base, names `--base`, and prints
  nothing else. It always exits 0. The report's first line records the
  merge-base SHA so it can be reproduced. Its sections:
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
  itself and stores `<merge-base-sha>:<sha256-of-report>` on the unit's
  evidence. The caller never passes it, and `--evidence proportionality=` is
  refused. The orchestrator pastes the report into the PR body. Drift compares
  step and member ids only, so an evidence key strands no cursor. Runs already
  in flight do pick up the obligation at their `deliver`, which is intended.
- **Report first.** Nothing in the report blocks. Whether any section should
  become a gate is a later decision, made with runs' reports in hand.

### D. Main-session cost per step (gh#593 option 0)

- **Shape.** `StepRecord.main_session: MainSessionUsage | None`, where
  `MainSessionUsage` has:
  - `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`
    and `output_tokens`, all required, matching `MeasuredTokens`' atomicity;
  - `turns: int`;
  - `sessions: int`, the number of harness sessions summed;
  - `cost_usd: float | None`, set only when the harness itself reports a cost.
- **Window.** fr-goal's top-level steps are sequential, so a step's window is
  `(previous top-level step's at, this step's at]`, with the run's `started`
  bounding the first. A previous step's `at` never moves once it is `done`.
  Timestamps are compared at **second precision**: a transcript timestamp
  is truncated to the second before the comparison, because `_now()` records
  whole seconds. Turns before `fr run start` belong to no step and are not
  measured. Measuring the **step** rather than the attempt covers
  `brainstorm`, which has no attempt, and the whole `implement` loop,
  including the orchestrator's dispatch, handoff and debugging turns.
- **When.** Written inside `_complete_step` when the outcome is `done`. That is
  the one place every completion path meets: `resolve` of agent steps,
  `advance` of cli steps, and `advance`'s completion of the `implement`
  group. It never raises. An unmeasurable step leaves `main_session` absent,
  which reads as "not observable", never zero.
- **Which sessions.** The candidate set is:
  - every distinct `Attempt.session` recorded on the run;
  - plus every session the workspace binding lists for the run's branch
    (`fr isolation attach` / `up --session`);
  - plus this process's current session.

  Each session is measured over the window and the results summed. If any
  candidate session is unreadable, nothing is recorded: a partial sum would be
  reported as a measurement, and gh#514 rules that out. A run resumed in a new
  session is therefore counted in full, not under-counted.
- **One shared dedupe (fixes an existing over-count).** Claude Code writes one
  transcript record per content block, each repeating the whole message's
  `usage`. On this spec's own brainstorm transcript, 27 of 40 assistant message
  ids appear on more than one record, each copy with identical usage. The
  existing `read_claude_code` sums every record, so `attempts[].measured`
  **over-counts** today. A single helper that deduplicates by `message.id`
  serves both the existing subagent reader and the new main-session reader.
  Otherwise `fr run cost` would show a correct main-session row beside an
  inflated subagent line. Previously recorded `measured` values are historical
  and are **not** rewritten. `fr run cost` labels any unit resolved before this
  release as possibly over-counted.
- **Claude Code reader.** `TranscriptReader.measure_main_session(session,
  start, end)` sums the deduplicated assistant records whose `isSidechain` is
  not true, whose model is real, and whose timestamp falls in the window.
  `turns` counts distinct message ids. `cost_usd` is `None`.
- **OpenCode reader.** `OpenCodeReader` reads the session database read-only
  (default `~/.local/share/opencode/opencode.db`, overridable by
  `FR_OPENCODE_DB`). OpenCode sessions are never bound automatically, because
  `current_session` reads only `CLAUDE_CODE_SESSION_ID`. The candidate set is
  therefore usually the workspace bindings made with `fr isolation attach
  --harness opencode`. When the set is empty, the fallback is the **unique**
  top-level session (`parent_id IS NULL`) whose `directory` is the run's
  workspace or its base clone and which has assistant messages in the window.
  More than one candidate means nothing is recorded, never a guess.
  - Tokens come from each assistant message's `data.tokens`. `reasoning` is
    folded into `output_tokens`, and the reader's docstring says so.
  - `cost_usd` is the sum of `data.cost`.
  - OpenCode *dispatch* measurement stays `None`, unchanged and stated.
- **Hermes** has no reader and records nothing.
- **Parity.** `parity.yaml` gains an `interaction` row, `main-session-cost`:
  claude-code `enforced`, opencode `partial` (not live-proven), hermes
  `absent`.
- **Reporting.** `fr run cost <run-id>` prints gh#593's table. For each
  top-level step it shows turns, sessions, the four token figures,
  cache-read per turn, and cost when known. A subagent line sums
  `attempts[].measured`. A missing measurement prints as `—`, never `0`.
- **Artifact versioning.** This adds a field to the `extra="forbid"`
  `StepRecord` that a released `fr` reads, so it is a shape change: run stamp
  5 → 6, a stamp-only registered migration, and validator support. The change
  is additive, so no legacy model is frozen. The every-hop chain assertion
  extends to `[2, 3, 4, 5, 6]`.

### E. Independent spec review (gh#593 option 2)

- **Agent.** A new `plugins/super-fr/agents/fr-spec-reviewer.md`: read-only
  (Read, Grep, Glob). It is given `tier: standard` on the manifest step. Its
  brief checks three things:
  - the spec matches the spec journal's `decision` entries (the operator's
    Q&A);
  - every file, helper, command and service the spec names exists, with a
    file:line citation for each;
  - the spec is internally consistent.

  It tags each finding in-scope or out-of-scope (§A), returns them as a
  structured list, and writes nothing. The orchestrator journals them as
  spec-scope `finding` entries carrying `review_scope`, plus one `review`
  entry naming the reviewer's dispatch id.
- **Manifest.** `spec-review` gains `agent: super-fr:fr-spec-reviewer`,
  `tier: standard` and `evidence: [review, reviewer, findings]`.
- **Evidence gate for a flat step.** Today `review`, `reviewer` and `findings`
  are all in `_PHASE_EVIDENCE`, and `_verify_reviewer` asserts a phase, so a
  flat `step/…` unit refuses all three. The verifier generalizes to a
  per-step journal target:
  - `review-phase` → plan journal, `phase=N` (unchanged);
  - `spec-review` → spec journal, no phase. `review` must be a
    `kind=review` spec entry created after the step opened. `findings` is
    derived from the spec journal's open findings.
  - For a flat step, `reviewer` has no implementer to exclude.
  - Its rule is dispatch provenance: on **Claude Code**, the id must be a
    subagent this session dispatched after the step opened
    (`subagent_dispatch_since`). The orchestrator has no agent id, so it can
    never satisfy this. An unreadable transcript is recorded as claimed with a
    warning, as today.
  - On **OpenCode and Hermes** there is no dispatch reader, so the id is
    recorded as claimed.
  - `parity.yaml` gains an `interaction` row, `spec-review-independence`:
    claude-code `enforced`, opencode and hermes `advisory`.
- **Mirrors and install.**
  - `scripts/sync-opencode.py` generates the OpenCode per-tier agent files.
  - Both sync scripts regenerate the fr-goal skill mirrors.
  - `install.sh` ships the agent.
  - The plan checks whether the org agent-worktree hook forces a worktree on
    a read-only agent. Only if it does, `ensure-phase-executor-allowlist.sh`
    is generalized to allowlist this agent too.

### Cross-cutting

- **Version:** minor bump (new commands, new agent, new mandatory evidence).
- **Explainer:** `docs/explainers/01-fr-goal.md` is updated and re-rendered
  (`.claude/rules/explainers-currency.md`).
- **Non-goal, restated from gh#597:** nothing here weakens `deliver`'s
  `--evidence tests=<log>` gate.

## 3. Test Plan

**In this PR:**

1. Journal, out-of-scope state:
   - `resolve --state out-of-scope` writes `state=open` plus `out_of_scope=true`
     and folds to `out-of-scope`.
   - An older-style parse (unknown token ignored) reads it as open.
   - `deferred --tracked-by` supersedes it.
   - The `review-phase` findings gate and `fr journal check` pass when the
     only unresolved findings are out-of-scope.
2. Journal, operator guard:
   - A `fixed` record after `out-of-scope` fails `fr journal check` as an
     unauthorized fix without `answered_by=operator`, via both `resolve` and
     `add --resolves`.
   - It passes with the flag.
   - On Claude Code, `--answered-by operator` is refused when no question was
     answered since the out-of-scope record.
3. Journal render: a `review_scope=in` finding resolved `out-of-scope` renders
   as reclassified. `deliver`'s render includes spec-scope findings.
4. Plan fields: `files` and `estimate_lines` round-trip and are omitted when
   unset. `fr plan create` raises the `fr_version` floor when either is set.
   `self-review` warns on an agentic phase with no `files`.
5. Proportionality:
   - A fixture repo with an unreferenced new file, an out-of-plan touch (one
     justified by a journal entry, one not), and diffs above and below 2× of
     `estimate_lines` produces the expected three sections, diffed from the
     merge-base.
   - With no `files` declared, the report says so.
   - With no determinable base, it names `--base`.
   - It always exits 0.
6. `deliver` resolve derives and stores `<merge-base>:<sha256>` and refuses a
   caller-supplied `proportionality=`. The stored hash equals the SHA-256 of
   the same command's output at the same merge-base.
7. Run migration: the chain asserts every hop `[2, 3, 4, 5, 6]`, and `fr
   validate artifacts` passes on this repo after `fr migrate artifacts --yes`.
8. Dedupe: a transcript fixture with three records sharing one message id is
   counted once by both the subagent reader and the main-session reader.
9. Claude Code main-session reader: sidechain, main-thread and out-of-window
   records, with timestamps that differ from a step's `at` only below one
   second, yield exact sums and turns. Two candidate sessions are summed. An
   unreadable candidate yields nothing.
10. `_complete_step` writes `main_session` on every `done` path: agent resolve,
    cli advance, and group completion by advance.
11. OpenCode reader: a fixture SQLite database with two top-level sessions and
    one child session yields the bound session's sums and cost. Two unbound
    sessions that both qualify yield nothing. The child session is ignored.
12. `fr run cost` renders measured, unmeasured (`—`), subagent and
    possibly-over-counted rows.
13. Spec-review evidence gate: `resolve --step spec-review --state done`
    refuses in each of these cases:
    - there is no spec-journal `review` entry created after the step opened;
    - a spec-scope finding is still open;
    - the reviewer id is one this session did not dispatch after the step
      opened.

    The shipped manifest passes `fr workflow check`.
14. The mirror, install and parity tripwires stay green with the new agent and
    both new `parity.yaml` rows.

**Post-merge, operator-driven:**

15. Run `/fr-goal` on a small public `derio-net` task under Claude Code, then
    under OpenCode. In each run:
    - `fr run cost` shows a measured row for every top-level step;
    - `spec-review` was answered by a dispatched `fr-spec-reviewer`;
    - the PR body carries the proportionality report and an out-of-scope
      section, or states there is none.

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
