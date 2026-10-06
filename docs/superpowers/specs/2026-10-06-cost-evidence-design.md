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
    `agent-<id>.jsonl` stream name), and the child session id on OpenCode and
    Hermes. A message from the session's own thread has no agent id.
R2. A usage `SessionEntry` records, per step, the main thread's figures apart
    from its subagents' figures (`steps_by_role`, keys `main` and `subagent`).
R3. A usage `SessionEntry` records, per cursor unit, the figures of each role
    that worked on it (`units`): `executor` and `orchestrator` on an
    `implement-phase` unit, `reviewer` and `orchestrator` on a `review-phase`
    unit, and `agent` on a flat `step/<id>` unit whose subagent (for example
    `fr-spec-reviewer` at `spec-review`) the cursor identifies. Subagent
    messages that match no unit are figured under `(unattributed)`. The
    attribution rules are in Design §B.
R4. Every figure in R2 and R3 carries turns, input, cache-write, cache-read and
    output tokens, plus dollars where the harness priced the session. Missing
    dollars are `None` (rendered `—`), never `0`, and fr never invents a price.
R5. The `usage` kind moves from version 1 to 2: a stamp bump, a registered
    migration and the structure validator. A version-1 file migrates by stamp
    only, and its absent R2/R3 figures read as "not observed". Every writer of
    a new usage file stamps the current version explicitly, so a fresh capture
    is never stale.
R6. The split is computed at capture, by the code that already writes the
    usage file (`session_entry`). It adds no step, no dispatch and no LLM turn
    to a run. `fr usage backfill`, which writes archived files, does not add
    the split.
R7. An attempt dispatched to a subagent (`agent_type` set) records the tier
    it was dispatched at (`tier`) and the model that tier resolved to at
    dispatch (`bound`). `resolve` never overwrites either; the model that ran
    stays in `model`. An orchestrator-run attempt records neither and keeps
    today's observed orchestrator model. The `run` kind moves from version 8
    to 9 with a stamp-only migration; older attempts have neither field, and
    read as "not recorded".
R8. `fr run cost` prints a per-step table (main and subagent columns, each
    with turns, cache-read and output tokens, and dollars) and a per-phase
    table with, for each agentic phase: tier, bound model, model that ran, and
    the executor, reviewer and orchestrator figures in the same columns. "Ran"
    is shown only for an attempt that recorded `bound` (written by a v9 `fr`),
    because before gh#637 `model` held the binding, not what ran. A phase
    whose observed `ran` model differs (by family) from `bound` is marked. An
    unobserved model renders `—` and is never marked as a mismatch.
R9. The rendered PR body's `## Cost` section carries the same two tables in
    Markdown.
R10. `fr usage compare --before <date|run-id> --after <date|run-id>` compares
     two sets of runs over the live and archived usage files, cursors of every
     version and plan journals. Per run it shows: phases, turns, main and
     subagent cache-read and output tokens, dollars (with how many runs were
     priced), review findings per phase and re-opened findings. Per set it
     shows medians and the sample size. It is read-only and deterministic.
R11. An audit document, `docs/superpowers/audits/2026-10-06-cost-evidence-audit.md`,
     answers from `fr usage compare` output (quoted, with the command):
     (a) #627, with the cutoff at #514's merge; (b) #793 item 5, with the
     cutoff at #792's merge; (c) #593's decision rules (main-session share of
     cost or tokens, and cache-read per main-session turn by step) and a
     recommendation between options 1 and 4. It states every data limit it
     hit: sample sizes, unpriced captures, confounds such as the model
     change, attempt `model`s written before gh#637 that hold the binding
     rather than what ran, and Hermes delegates that do not attribute.

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
- Hermes: the delegate's child session id (`readers/hermes.py`'s `owner`,
  already selected by `parent_session_id`). A Hermes cursor records the
  `delegate_task` handle as `Attempt.agent`, not that id, so these messages
  count as `subagent` in R2 and fall to `(unattributed)` in R3 unless the
  ids happen to match. The audit states this limit.

### B. Unit attribution (R3)

At capture, `session_entry` receives `units_by_agent(cursor)` today. It is
replaced by `unit_index(cursor)` in `fr/usage/file.py`, which returns for every
unit of every step:

- `agents`: the `agent` of each of the unit's non-synthesized attempts, plus
  the unit's `evidence.reviewer` when present;
- `intervals`: one half-open `(dispatched, returned]` interval per
  non-synthesized attempt, in seconds, the same convention as
  `rollup._step_of`. An attempt with no `returned` is open-ended only when
  `fr.run.units.open_attempt` says the unit is held; a synthesized attempt
  contributes no interval and no agent.

`unit_index` also yields the `units_by_agent` mapping, so brief re-keying keeps
working.

Each message is then attributed to at most one unit and one role:

- **subagent message** (`agent_id` set): the unit whose `agents` contain that
  id. The role follows the unit's step: `executor` for `implement-phase`,
  `reviewer` for `review-phase`, `agent` for a flat `step/<id>` unit. No
  match: `(unattributed)`, role `subagent`.
- **main-thread message**: role `orchestrator` of the unit whose interval
  contains its timestamp. When intervals overlap (a unit re-dispatched after a
  later unit opened), the interval with the latest `dispatched` that is at or
  before the timestamp wins, so a retry's messages go to the retry and nothing
  is counted twice. A main-thread message outside every interval stays in its
  step figure only.

The figure shape is `Figure` extended with `input`, `cache_write`,
`cache_read`, `output`, all `int | None = None` (R4).

**Dollars.** `rollup` gains a public `message_dollars(record, weights)`
returning each message's price-weighted share and the session's remainder:
billed models with no message, plus a per-model total that does not add up.
`rollup` itself and the R2/R3 split both use it, so the two splits cannot
drift. The remainder belongs to no role and no unit; it stays where `rollup`
puts it today, in `steps["(outside run)"]`. The invariants the tests assert,
for every figure field (usd where priced, turns, each token count):

- for every step `s` other than `(outside run)`:
  `steps_by_role.main[s] + steps_by_role.subagent[s] == steps[s]`;
- for `(outside run)`: the same, plus the remainder for usd;
- summed over every unit and role, plus `(unattributed)`, the result is at
  most the session's per-message total (main-thread messages outside every
  interval are the difference).

Stored as:

```yaml
steps_by_role:
  main:     {brainstorm: {usd: …, turns: …, input: …, cache_write: …, cache_read: …, output: …}, …}
  subagent: {implement: {…}, …}
units:
  step/spec-review:        {agent: {…}, orchestrator: {…}}
  phase/1/implement-phase: {executor: {…}, orchestrator: {…}}
  phase/1/review-phase:    {reviewer: {…}, orchestrator: {…}}
  (unattributed):          {subagent: {…}}
```

`dump_usage` writes these field by field (the allowlist rule in `file.py`'s
docstring). Only unit keys, step names and numbers are added.

**Callers of `session_entry`.** It takes `index: UnitIndex | None`:

- `capture.build_capture` (deliver, closeout, `resolve:<step>`) passes
  `unit_index(cursor)`, so live captures carry the split;
- `fr run cost --recompute` (`cost.recompute_entries`) passes it too, since
  it prints and never writes;
- `backfill` (new archived files) and `refreshed_file` (re-pricing an
  archived file's entry) pass `None`, so they write no `steps_by_role` and no
  `units`. That keeps the non-goal: archived files are not re-shaped.

### C. The usage kind at version 2 (R5)

`fr/artifacts/registry.py`: `usage` `current_version` 1 → 2. Every `UsageFile`
constructor that writes a new file passes `schema_version` explicitly, from a
`current_usage_schema_version()` helper read from the registry, mirroring
`RunState`'s creators (`fr/run/model.py`). The sites are `capture.py` (two),
`backfill.py` and `artifacts/run_usage_split.py`. The model's default stays 1,
so a file without a stamp still reads as version 1. A new
`fr/artifacts/usage_split_v2.py` registers the 1 → 2 `SchemaMigration`,
imported by `fr/artifacts/__init__.py`. Its `fn` parses the file with the live
`parse_usage` (still a superset, because nothing is removed) and refuses one
that does not parse, rather than certifying it. The body is not rewritten, and
nothing is frozen. `SessionEntry._unavailable_carries_no_figures` also covers
`steps_by_role` and `units`. The structure validator (`structure.validate_usage`)
checks that `units` keys are unit keys or `(unattributed)`, that role keys
are in the closed sets above, and that no figure is negative. The PR runs
`fr migrate artifacts --yes` and commits the result.

### D. Tier and binding on the attempt (R7)

`fr.run.model.Attempt` gains `tier: str | None = None` and
`bound: str | None = None`. In `_open_dispatch`, for an attempt with
`agent_type` set, `advance` writes `tier` (from `_dispatch_tier`) and
`bound` (from `_resolved_model`), and stops writing the binding into `model`.
For an orchestrator-run attempt (`agent_type` None), nothing changes:
`model` keeps `orchestrator_model`'s observation, and `tier`/`bound` stay
None. This is the rule the comment at that site already records after
"seven false claude-opus-5 reviews". On a subagent attempt, `model` is then
set by a claim (`--model`) or by `_observed_model` at resolve, which compares
against `bound` (falling back to `model` for an attempt opened before this
change). Unobservable leaves `model` None, rendered `—`. The
synthesized-attempt validator adds `tier` and `bound` to the fields such an
attempt may not claim.

`run` `current_version` 8 → 9, in a new `fr/artifacts/run_bound_model.py`
imported by `fr/artifacts/__init__.py`. It follows the 7 → 8 precedent
(`artifacts/run_driver.py`), not `cursor_guard`: `cursor_guard` parses with
the frozen v1–v4 reader and would refuse every v8 cursor. The `fn` refuses
unless the body already reads as v8 under the live model (`_already_v8`),
which stays a superset while the change only adds fields. The body is not
rewritten, and nothing is frozen. The chain test
(`test_migration_runner.py`) asserts every hop up to `[…, 8, 9]`.

### E. Rendering (R8, R9)

`fr/run/cost.py` gains `PhaseRow` (phase n, tier, bound, ran, mismatch flag,
and executor, reviewer, orchestrator figures) built by
`phase_rows(state, entries)`. Tier, bound and ran come from the phase's latest
non-synthesized `implement-phase` attempt. Ran is shown only when that attempt
recorded `bound`, and the mismatch flag uses `_model_family`, moved to
`fr/models.py` so both callers share it. Figures sum `units` across the
effective entries; the phase's `orchestrator` is the sum over its implement
and review units. `summarize` also sums `steps_by_role` into the step rows.
The command (`commands/run_cmd.py`'s `cost`) prints both tables, and
`pr_body._cost` renders them as Markdown, replacing today's step table. Every
dollar column has turns and `cache-read / output` tokens beside it, compacted
(`1.2M / 34k`); a figure nothing observed prints `—`.

### F. `fr usage compare` (R10)

A new `fr/usage/compare.py` holds a pure function over loaded inputs; the
command lives in `commands/usage_cmd.py`. A selector is an ISO date (runs
whose `started` is before it, or on or after it) or a run id (that one run).
Inputs per run:

- the usage file (live, then archived), read through `effective_entries`;
- the cursor (`docs/superpowers/runs/`, then `implemented/runs/`), read raw
  and tolerantly, because archived cursors are never migrated and runs before
  2026-09-20 are v1–v4. Phases are counted from v5+ `units` or v1–v4 `items`
  through `fr.run.legacy`'s reader, as `usage/backfill.py` already does, and
  `started` from the top level;
- the plan, found through the cursor's `steps.plan.emitted.plan` (run ids are
  not plan slugs), and its journal (`journals/plans/`, then the archived one).
  Findings per phase are journal `finding` entries grouped by their `phase`
  field. Re-opened findings are those whose resolution fold
  (`fr.journal.model`) shows a re-open record.

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
  stream; OpenCode and Hermes with a child session).
- Unit: `session_entry` attribution covers executor, reviewer via evidence,
  a flat-step `agent` (spec-reviewer), orchestrator by interval, a retried
  unit whose interval overlaps a later unit (counted once, to the retry), a
  synthesized attempt (no interval), shared endpoints (half-open), and an
  unmatched subagent going to `(unattributed)`. The three §B invariants hold.
- Unit: `backfill` and `refreshed_file` write no split; a fresh capture is
  stamped `schema_version: 2`.
- Unit: usage v1 → v2 and run 8 → 9 migrations, including the refusal of an
  unparseable body; the chain asserts every hop; the validators refuse a bad
  role key or a negative figure.
- Unit: `advance` writes `tier`/`bound` on a subagent attempt only;
  `resolve` keeps them and sets `model` to the observed one; an orchestrator
  attempt keeps its observed model; a mismatch is marked, and an unobserved
  model is `—` and not marked.
- Unit: `fr run cost` and `render_pr_body` show both tables, priced and
  unpriced (tokens and turns present, dollars `—`), and "ran" is `—` for an
  attempt with no `bound`.
- Unit: `fr usage compare` over fixture runs, including a pre-v5 cursor:
  medians, `n`, a missing input shown as `—`, determinism.
- Post-merge — operator-driven: the next real `/fr-goal` run's PR body shows
  the per-phase table with tier, bound and ran filled.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-06-cost-evidence | `derio-net/super-fr` | `2026-10-06-cost-evidence` | — |
