# Cost evidence: per-phase tiers and overhead, main-session cost, handoff quality

Batch `cost-evidence`: super-fr#838, #793, #593, #627, delivered as one PR.

## Background

A run's cost is measured from the harness's own records (`fr/usage/readers/`),
projected into the `usage` artifact (`docs/superpowers/usage/<run>.yaml`,
`fr/usage/file.py`) at capture time, and read back by `fr run cost`
(`fr/run/cost.py`) and the PR body's `## Cost` section
(`fr/record/pr_body.py::_cost`). Since gh#637 the Claude Code reader folds a
session's subagent transcripts into its record
(`fr/usage/readers/claude_code.py::read`), and `resolve` overwrites an attempt's
`model` with the model the subagent's transcript says actually ran
(`fr/commands/run_cmd.py::_observed_model`).

Four questions remain unanswerable from what is recorded:

1. **Which tier, and which model, did each phase use?** (#838) The plan header
   names the tier. `advance` writes the tier's binding into `Attempt.model`
   (`run_cmd.py::_resolved_model`), and `resolve` then overwrites it with the
   observed model, so the binding at dispatch is lost.
2. **What did each extra phase cost the orchestrator and the reviewer, beside
   the executor?** (#793 item 4) A usage `SessionEntry` keys figures by step
   only, and `implement` is one step window covering every phase
   (`fr/usage/rollup.py::windows_from_cursor`, top-level steps only).
3. **What does the main session cost per step?** (#593 option 0) Subagent
   messages are folded into the main session's record, and `steps` sums both,
   so main-only figures per step cannot be separated. `Message.agent` holds the
   agent's TYPE (`super-fr:fr-phase-executor`), not its id, so nothing ties a
   message to a cursor unit.
4. **Did the 2026-09-20 bounded handoff (#514) lower phase quality, and did
   phase-per-ask sizing (#792, 2026-09-28) pay off?** (#627, #793 item 5) The
   data is spread over 60 usage files plus plan journals, with no tool to
   compare two sets of runs.

Measured while writing this spec: 42 of the 60 usage files in this repo carry
dollar figures, but only 2 of the 10 captures since 2026-10-02 do. Tokens and
turns are always present. #593's option 2 (an independent spec reviewer) has
already shipped as `plugins/super-fr/agents/fr-spec-reviewer`, which the
`spec-review` step dispatches.

## Requirements

R1. Every usage `Message` carries the id of the agent that produced it, as well
    as its type: the subagent's transcript id on Claude Code (the
    `agent-<id>.jsonl` stream name), the child session id on OpenCode, and none
    on Hermes. A message from the session's own thread has no agent id.
R2. A usage `SessionEntry` records, per step, the main thread's figures apart
    from its subagents' figures (`steps_by_role`, keys `main` and `subagent`).
R3. A usage `SessionEntry` records, per cursor unit, the executor's, the
    reviewer's and the orchestrator's figures (`units`). The attribution rules
    are in Design §B.
R4. Every figure in R2 and R3 carries turns, input, cache-write, cache-read and
    output tokens, plus dollars where the harness priced the session. Missing
    dollars are `None` (rendered `—`), never `0`, and fr never invents a price.
R5. The `usage` kind moves from version 1 to 2: a stamp bump, a registered
    migration and the structure validator. A version-1 file migrates by stamp
    only, and its absent R2/R3 figures read as "not observed".
R6. The split is computed at capture, by the code that already writes the
    usage file (`session_entry`). It adds no step, no dispatch and no LLM turn
    to a run.
R7. A dispatched attempt records the tier it was dispatched at (`tier`) and
    the model that tier resolved to at dispatch (`bound`). `resolve` never
    overwrites either; the model that ran stays in `model`. The `run` kind
    moves from version 8 to 9 with a stamp-only migration; older attempts have
    neither field, and read as "not recorded".
R8. `fr run cost` prints a per-step table with main and subagent columns, and
    a per-phase table with, for each agentic phase: tier, bound model, model
    that ran, and the executor, reviewer and orchestrator figures. A phase
    whose `ran` model differs (by family) from `bound` is marked.
R9. The rendered PR body's `## Cost` section carries the same per-phase table
    and the step table's main/subagent split, in Markdown.
R10. `fr usage compare --before <date|run-id> --after <date|run-id>` compares
     two sets of runs over the live and archived usage files, cursors and plan
     journals. Per run it shows: phases, turns, main and subagent tokens,
     dollars (with how many runs were priced), review findings per phase and
     re-opened findings. Per set it shows medians and the sample size. It is
     read-only and deterministic.
R11. An audit document, `docs/superpowers/audits/2026-10-06-cost-evidence-audit.md`,
     answers from `fr usage compare` output (quoted, with the command):
     (a) #627, with the cutoff at #514's merge; (b) #793 item 5, with the
     cutoff at #792's merge; (c) #593's decision rules (main-session share of
     cost or tokens, and cache-read per main-session turn by step) and a
     recommendation between options 1 and 4. It states every data limit it
     hit: sample sizes, unpriced captures, and confounds such as the model
     change.

## Design

### A. Agent identity on every message (R1)

`fr.usage.model.Message` gains `agent_id: str | None = None`. `UsageRecord` is
an in-memory model, not an artifact, so this needs no migration.

- Claude Code: `_messages(records, agent, agent_id)`. The subagent stream
  `agent-<id>.jsonl` gives `<id>`, which is the same id the cursor records as
  `Attempt.agent` and a review records as `evidence.reviewer` (the run
  `2026-10-06-feat-batch-forge-remainder` cursor and usage file show both).
- OpenCode: the message's owning session id when it differs from the parent
  session (`readers/opencode.py`, the `owner` already computed there).
- Hermes: `None`. Delegates are not attributable, so their messages count as
  `subagent` in R2 and as `(unattributed)` in R3.

### B. Unit attribution (R3)

At capture, `session_entry` already receives `units_by_agent(cursor)`. It is
widened to `unit_index(cursor)`, which returns for every unit of every step:

- `agents`: the `agent` of each of the unit's attempts, plus the unit's
  `evidence.reviewer` when present;
- `window`: from the first attempt's `dispatched` to the last attempt's
  `returned`, or open-ended when the unit is still held.

Each message is then attributed to:

- **executor** of unit U: a subagent message whose `agent_id` is among U's
  attempt agents and U's step is `implement-phase`;
- **reviewer** of unit U: a subagent message whose `agent_id` is U's
  `evidence.reviewer`, or among U's attempt agents, where U's step is
  `review-phase`;
- **orchestrator** of unit U: a main-thread message whose timestamp falls in
  U's window. Windows of a phase's implement and review units do not overlap;
  if two windows ever overlap, the message goes to the earlier-dispatched unit
  only, so nothing is counted twice;
- otherwise nothing: `(unattributed)` is reported for subagent messages that
  matched no unit, and main-thread messages outside every unit window stay in
  their step figure only.

The figure shape is `Figure` extended with `input`, `cache_write`,
`cache_read`, `output`, all `int | None = None` (R4). Dollars are split exactly
as `rollup` already splits them: by the harness's per-model figure over
price-weighted tokens, so units plus the rest still sum to the session.

Stored as:

```yaml
steps_by_role:
  main:     {brainstorm: {usd: …, turns: …, input: …, cache_write: …, cache_read: …, output: …}, …}
  subagent: {implement: {…}, …}
units:
  phase/1/implement-phase: {executor: {…}, orchestrator: {…}}
  phase/1/review-phase:    {reviewer: {…}, orchestrator: {…}}
  (unattributed):          {subagent: {…}}
```

`dump_usage` writes these field by field (the allowlist rule in `file.py`'s
docstring). Only unit keys, step names and numbers are added.

### C. The usage kind at version 2 (R5)

`fr/artifacts/registry.py`: `usage` `current_version` 1 → 2. `UsageFile`
already carries `schema_version: int = 1`. A new `fr/artifacts/usage_split.py`
registers a stamp-only `SchemaMigration` 1 → 2 (no field removed, so no frozen
legacy model is needed) and is imported by `fr/artifacts/__init__.py`. The
structure validator checks that `units` keys are unit keys or
`(unattributed)`, that role keys are in the closed sets above, and that no
figure is negative. The PR runs `fr migrate artifacts --yes` and commits the
result.

### D. Tier and binding on the attempt (R7)

`fr.run.model.Attempt` gains `tier: str | None = None` and
`bound: str | None = None`. `_open_dispatch` (where `advance` resolves
`_dispatch_tier` and `_resolved_model`) writes both, and stops writing the
binding into `model`. `model` is then set by a claim (`--model`) or by
`_observed_model` at resolve, which now compares against `bound`. The
synthesized-attempt validator adds `tier` and `bound` to the fields such an
attempt may not claim. `run` `current_version` 8 → 9, stamp-only migration in
a new `fr/artifacts/run_bound_model.py`. The existing `run` migrations already
read through `cursor_guard`'s frozen model; this hop adds a field and removes
nothing, so it reuses that guard and freezes nothing new. The chain test is
extended to `[…, 9]`.

### E. Rendering (R8, R9)

`fr/run/cost.py` gains `PhaseRow` (phase n, tier, bound, ran, executor,
reviewer, orchestrator figures) built by `phase_rows(state, entries)`.
Tier/bound/ran come from the phase's latest `implement-phase` attempt; figures
come from summing `units` across the effective entries. `summarize` also sums
`steps_by_role`. The command (`commands/run_cmd.py`'s `cost`) prints both
tables. `pr_body._cost` renders them as Markdown under the existing table. A
per-phase column with nothing observed prints `—`. Token columns are shown as
`cache-read / output`, compacted (`1.2M / 34k`), beside turns and dollars.

### F. `fr usage compare` (R10)

A new `fr/usage/compare.py` holds a pure function over loaded inputs; the
command lives in `commands/usage_cmd.py`. A selector is an ISO date (runs
whose `started` is before it, or on or after it) or a run id (that one run).
Inputs per run:

- the usage file (live, then archived), read through `effective_entries`;
- the cursor (`docs/superpowers/runs/`, then `implemented/runs/`), for phases
  and `started`;
- the plan journal (`journals/plans/`, then the archived one), for `finding`
  entries per phase and for findings that a resolution re-opened.

The output is a per-run table plus a per-set median row and `n`. A run missing
an input shows `—` in that column and is still counted. `usage` is already in
`READ_ONLY_COMMANDS`, so the migration gate never refuses it.

### G. The audit (R11)

Written in this PR's last agentic phase from real `fr usage compare` output,
pasted with the exact command. Third-party privacy: these are super-fr's own
runs, and no foreign host appears in usage files (`file.py`'s allowlist).

## Non-goals

- Running #593's 3-task × 2-harness measurement campaign. The audit says it is
  out of scope here.
- Repairing the missing dollar figures in recent Claude Code captures. That is
  a separate defect, filed as out of scope.
- Re-capturing or rewriting archived usage files to add the R2/R3 split.
  Archived artifacts are frozen; `compare` reports what they hold.
- Restarting the main session at step boundaries (#593 option 1). The audit
  only recommends.

## Test Plan

- Unit: reader tests carry `agent_id` (Claude Code fixture with a subagent
  stream; OpenCode with a child session; Hermes `None`).
- Unit: `session_entry` attribution covers executor, reviewer via evidence,
  orchestrator by window, overlapping windows counted once, and an unmatched
  subagent going to `(unattributed)`. Unit plus remainder sums to the session
  total.
- Unit: usage v1 → v2 and run 8 → 9 migrations; the chain asserts every hop;
  the validators refuse a bad role key or a negative figure.
- Unit: `advance` writes `tier`/`bound`; `resolve` keeps them and sets
  `model` to the observed one; a mismatch is marked in the phase table.
- Unit: `fr run cost` and `render_pr_body` show the per-phase table, with
  `—` for unobserved figures.
- Unit: `fr usage compare` over fixture runs: medians, `n`, a missing input
  shown as `—`, determinism.
- Post-merge — operator-driven: the next real `/fr-goal` run's PR body shows
  the per-phase table with tier, bound and ran filled.
