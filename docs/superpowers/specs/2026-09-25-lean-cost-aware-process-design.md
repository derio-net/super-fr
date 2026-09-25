# A lean, cost-aware fr pipeline

**Status:** design · **Branch:** `feat/lean-cost-aware-process` · **Journal:**
`docs/superpowers/journals/specs/2026-09-25-lean-cost-aware-process.md` ·
**Depends on:** gh#610 (`commit_paths`, `fr pickup --run`) merged first

## 1. Background

An audit of this repo's own paper trail (2026-09-25, published as the *Paper
Trail Audit* page, the brainstorm deliverable in §7) measured what super-fr's
artifacts cost to produce, who reads them, and what would break without them.
The token figures come from nine recent `/fr-goal` and `/fr-debugging` sessions
(2026-09-20 to 09-25), reconstructed after the fact from the harness's own
records: Claude Code session JSONL plus `subagents/`, and the per-session
`cost-state` record that carries `costUSD` per model.

| Measure | Value |
|---|---|
| Spend across the nine sessions (harness-reported) | $1,155.62 |
| Paperwork: reading, writing and checking specs, plans, journals, cursors, matrix | $348.87 (30.2%), 23–37% in every session |
| Implementation: reading and editing code, tests and linters | $380.00 (32.9%) |
| Main orchestrator session | 70% of spend; paperwork ≈ $237 there against ≈ $209 implementation |
| Bookkeeping calls (`fr journal add/resolve`, `fr plan edit --tick`, `fr run start/advance/resolve/claim`) | 867 calls in 866 messages (96% did nothing else), 6.1 per step-item (range 2.4–14.8) |
| Cost of those turns | $136.35 context carry (90%), $14.33 generation (10%) |
| Output of a mechanics call | 405–724 chars on average: readability, not the cost driver |
| fr's own `main_session` telemetry coverage | 81% (#597/#593) and 63% (#606) on the only two runs that carry it; 0 on the other seven |

Four findings drive this design:

1. **The cost is the number of turns, not the size of artifacts.** Every
   bookkeeping call is its own turn that re-reads the whole context. Merging N
   entries into one call removes N-1 context re-reads and keeps the (small)
   generation cost.
2. **Persisted per-attempt telemetry costs more than it returns.** `estimate`,
   `measured` and `main_session` drove the run kind from stamp 5 to 6 with its
   migration and frozen-reader work, cover a fraction of the real spend, carry no
   dollars and no activity split, and are read only by `fr run cost`,
   `fr run status` and `run/units.py`. The harness already records exact dollars.
3. **After-the-fact reconstruction is richer but fragile.** Claude Code prunes
   transcripts after `cleanupPeriodDays` (30 days by default); Hermes can prune
   ended sessions; transcripts live on the host that ran the session.
4. **In devcontainer mode, fr's transcript-reading code runs in the wrong
   place.** Every `fr run` goes through `fr isolation exec`, inside the
   container, where no harness env is forwarded and no transcript exists
   (`implemented/runs/2026-09-25-fix-605-agent-step-evidence-debt.yaml`: 6 of 7
   steps unmeasured, `harness: None` on almost every attempt;
   `…-fix-606-writes-dot-dir-prefix.yaml`, host-worktree mode: all 7 measured).
   The transcript-based gates (reviewer provenance, `operator_answered_since`,
   the `tests=` window) degrade silently to "recorded as claimed" there.

gh#610 (in flight) makes fr commit its own record writes through one committer,
`commit_paths`, once per fr invocation. This design keeps that seam and changes
the cadence: one mechanical call, and one commit, per workflow step.

## 2. Goals / non-goals

**Goals**
- A feature's token and dollar cost, per model, per step and per activity
  (paperwork, implementation, other), is captured on the host that ran it,
  stored centrally in `docs/superpowers/usage/<run-id>.yaml`, readable on any
  checkout, and rendered into the PR body. Claude Code, OpenCode and Hermes all
  produce it.
- Every agent step's bookkeeping is **one** `fr run resolve --record` call: no
  inference spent on applying entries, one commit, one line of output on success.
- A stale or lost session can still be picked up at any point, including
  mid-step.
- ATDD stays: acceptance rows are born at brainstorm.
- The audit mechanism is a product: an engine in the `fr` wheel plus a thin
  `fr-audit` skill that regenerates both brainstorm pages.
- The isolation mode (host-worktree | devcontainer | external) is a first-class
  dimension of harness parity, and a devcontainer-mode run captures real usage.

**Non-goals**
- Editing or deleting any historic artifact. Archives stay frozen; the backfill
  (§5.B.5) only adds new files.
- A thinner orchestrator that dispatches `plan` or `deliver` to subagents.
  Decision d6: quiet mechanics now; measure with `usage/` before adding context
  hand-offs.
- A Hermes live walk. Hermes is marked *implemented, not live-verified* in
  `parity.yaml`.
- Investigating whether the bounded executor handoff (2026-09-20) lowered
  quality. The data here cannot settle it (§8); it is filed as an issue.
- Moving the runner path (`fr-execute` under `fr apply --to <runner>`) onto step
  records. Its verbs get cheaper for free (§5.C.6); switching it is a follow-up.
- Coarsening plan ticks. They are not duplicates of the cursor (§5.C.5), and
  once applied inside `resolve` they cost no turns.

## 3. Operator decisions (brainstorm Q&A, 2026-09-25)

- **d1 Scope:** one spec covering usage (A), the lean process (B) and the
  architecture page plus audit (C), in as few phases as possible. Heuristic:
  fewer, larger sessions keep more decision context.
- **d2 Backward reads:** old `fr` versions need not read new artifacts; the
  plugin is updated instead. New `fr` still migrates old artifacts forward.
- **d3 Run state stays in git**, so fr can pick up stale sessions. Bookkeeping
  becomes mechanical (scripts, minimal output, no inference) and is committed
  when it should be, with the gates holding. Rejected: run state outside git
  while running.
- **d4 One record file per workflow step**, applied by one
  `fr run resolve --record`. Rejected: commit trailers for `implement-phase`;
  batch flags on today's verbs.
- **d5 Usage is captured once per host and stored centrally** in
  `docs/superpowers/usage/<run-id>.yaml`, archived at closeout with the other fr
  artifacts. Existing telemetry is migrated into it. Hosts are opaque labels.
  Rejected: on-demand reconstruction only (fails when data is pruned or on
  another host); a block in the cursor; one append-only ledger (merge
  conflicts); outside git.
- **d6 ATDD rows at brainstorm,** written by the brainstorm record; reports stay
  committed; `skipped` keeps its meaning (manually verified at least once).
- **d7 Orchestrator reads:** quiet mechanics now, thin orchestrator only if
  `usage/` later shows it pays for its hand-offs.
- **d8 Ticks and verbs stay.** Ticks serve intra-phase resume, the runner path
  and GitHub sync. Verbs serve the runner path, fr-acceptance, fr-debugging and
  humans; they become one-entry records through the same engine.
- **d9 Phases:** 1 audit mechanism, 2 usage persistence, 3 step records, 4
  post-merge live walk (manual). No Hermes walk.
- **d10 `fr run` / `fr usage` execute on the harness host** in every isolation
  mode; in devcontainer mode `fr isolation exec` refuses them and prints the
  host-side command.

## 4. Principle

**Turns are the unit of cost; fr owns every mechanical step.** An agent's job is
judgement and content. Anything fr can derive, validate or apply from data on
disk costs zero turns when fr does it inside a call that is already happening,
and a full context re-read when an agent does it as its own call. So each step
hands fr one data file, and fr does the rest in one process.

## 5. Design

### A. The audit mechanism (phase 1)

```
 Claude Code ─┐ ~/.claude/projects/<proj>/<session>.jsonl + subagents/*.jsonl + cost-state
 OpenCode ────┼ ~/.local/share/opencode/opencode.db (message, part)       ─► one reader each
 Hermes ──────┘ ~/.hermes/state.db (sessions, messages, session_model_usage)          │
                                                                                       ▼
                  UsageRecord (normalized, per session): session, harness, role, models,
                  messages[ts, model, tokens{input, cache_write, cache_read, output},
                           tool_calls[{name, target}]], cost{usd, source}
                                                                                       │
                  classify(tool call) → paperwork | implementation | other  (pure)
                                                                                       │
                  rollups: per model · per activity · per step (cursor timestamps)
                                                                                       │
                  fr usage report → table (PR body) · HTML page (fr-audit skill)
```

1. **Readers.** `fr/usage/readers/` gains one reader per harness behind a
   `UsageReader` protocol. It extends the two readers `fr/run/telemetry.py`
   already has (Claude Code, OpenCode) rather than duplicating them, and adds
   Hermes. Each reader dedupes by message id: Claude Code writes one record per
   content block, the #597 lesson, now applied once for all harnesses.
2. **Dollars come from the harness when it has them**: `cost-state.modelUsage[*].costUSD`
   (Claude Code), `message.data.cost` (OpenCode; `$0` for free models, an
   estimate for Copilot-routed ones), `sessions.actual_cost_usd` or
   `estimated_cost_usd` (Hermes). When per-activity or per-step dollars are
   needed, each model's harness dollars are split by price-weighted tokens with
   fixed ratios only (input 1, 5-min cache write 1.25, 1-h cache write 2, cache
   read 0.1, output 5). No list price is invented. `source` is `exact`,
   `estimated` or `none`; `none` renders as `—`, never `0`.
3. **Hermes is coarser.** Its `messages` table has one `token_count` per message
   and `tool_calls` as JSON, so its activity split is token-count-weighted, and
   ACP sessions store zero tokens (hermes-agent#6775). The reader says so in the
   record (`attribution: coarse`).
4. **The classifier** is a pure function of `(tool name, command or path)`. It
   unwraps `fr isolation exec --`, strips `VAR=… &&` and `cd … &&` prefixes, and
   classifies by `fr` verb first, then path (`docs/superpowers/`,
   `docs/acceptance/` → paperwork; `packages/`, `tests/`, `plugins/`, test and
   lint runs → implementation), then `git`/`gh` → other. A message with several
   tool calls splits its usage evenly across them; one with none is narration
   (other).
5. **Commands.** `fr usage collect --run <id> | --session <id>` writes normalized
   records to `$HOME/.cache/fr/usage/` (not committed). `fr usage report
   [--run <id>…] [--format table|html]` renders. Both are read-only with respect
   to registered artifacts until phase 2 adds capture.
6. **`fr-audit` skill** (thin, the `fr-triage` pattern): which runs to compare,
   how to read the split, and authoring the *future-state* half of an
   architecture page from a spec. The future state is design, so it cannot be
   measured.
7. **Failure:** an unreadable source yields `unavailable: <reason>` for that
   session. It never raises and never counts as zero.

### B. Usage persistence (phase 2)

1. **The file.** `docs/superpowers/usage/<run-id>.yaml`, a new artifact kind
   `usage` at version 1, with a structure validator and the duplicate-key check.

   ```yaml
   schema_version: 1
   run: <run-id>
   captures:                  # one entry per host; a re-capture replaces its own host's entry
     - host: h-3f9a2c1e       # sha256(run_id + hostname)[:8]
       harness: claude-code
       mode: host-worktree    # host-worktree | devcontainer | external
       captured_at: <iso8601>
       at: deliver            # deliver | closeout | resolve:<step> | migrated | backfill
       sessions:
         - session: <id>
           role: main         # main | subagent:<agent_type>
           models:
             claude-opus-5-5: {input: 0, cache_write: 0, cache_read: 0, output: 0,
                               usd: 0.0, usd_source: exact}
           activity: {paperwork: {usd: 0.0, turns: 0}, implementation: {…}, other: {…}}
           steps: {brainstorm: {usd: 0.0, turns: 0}}
           briefs: {phase/1/implement-phase: 347}   # dispatch-brief chars, from the transcript
         - session: <id>
           unavailable: "transcript pruned"
   ```

   No totals are stored; readers sum on read. The per-step rollup is stored
   because it needs the transcript, which may not survive.
2. **Privacy allowlist.** Stored: model ids, provider *names*, token counts,
   dollars, session ids (already in cursors), step ids, brief sizes, the
   isolation mode. Never stored: hostnames, provider base URLs (Hermes'
   `billing_base_url`), paths, prompts or message content. The host label is
   stable within a run and carries no name.
3. **Capture points.** All three ride calls that already happen, cost no
   inference, and commit through gh#610's `commit_paths`:

   | When | Captures |
   |---|---|
   | `fr run resolve --step deliver` | every session the cursor records that is readable on this host, plus the current one |
   | closeout: `fr archive` | the closeout session, as its own capture; then the file moves to `implemented/usage/` with the plan |
   | any `fr run resolve` on a host with no capture yet | that host's sessions (runners, pods, cross-machine resume) |

   Capture never fails its step.
4. **Run 6 → 7.** `Attempt.estimate`, `Attempt.measured` and
   `StepRecord.main_session` are removed.
   - A removed field freezes the prior shape: `fr.run.legacy.RunStateV6` beside
     `RunStateV4`, vocabularies inlined, source SHA-pinned. Every hop names a
     frozen reader; the chain test extends to `[2, 3, 4, 5, 6, 7]`.
   - The 6 → 7 migration **moves** a live cursor's figures into its `usage/`
     file (`at: migrated`, `usd_source: none`) before stripping them, all in
     memory, one atomic write per file. A cursor it cannot convert stays
     byte-identical and is reported. The rewriting function recognises a cursor
     already wholly v7 (the crash window between body and stamp).
   - `fr run cost` reads `usage/` (active, then `implemented/usage/`);
     `--recompute` re-derives from local transcripts where they exist.
     `fr run status` drops its cost column. `run/units.py`'s estimate and
     measured readers and their per-unit tripwire go.
   - This PR runs `fr migrate artifacts --yes` on its own live cursors.
5. **Backfill.** `fr usage backfill`, run once by the operator. It *reads*
   archived runs (left byte-identical, hash-checked) and any transcripts still
   on this host, and writes new `implemented/usage/<run-id>.yaml` files with
   `at: backfill`.
6. **Where it runs (d10).** `fr run *` and `fr usage *` execute on the harness
   host:

   | Mode | Harness runs | `fr run` runs | Refusal |
   |---|---|---|---|
   | host-worktree | host | host (`fr isolation exec` already runs there) | none |
   | devcontainer | host | host: `cd <worktree> && [uv run] fr run …` | **yes** |
   | external (prepared pod or container, e.g. Hermes) | inside the container | inside the container, which is the harness host | none |

   - **Bridge layer.** `fr isolation exec` refuses an inner `fr run` / `fr usage`
     in devcontainer mode, exit 2, printing the exact host-side command built
     from the given arguments. The command uses `uv run fr` when the worktree
     contains `packages/fr` (this repo), else bare `fr`.
   - **In-process layer.** `fr run` / `fr usage` refuse when the repo they
     operate on carries a devcontainer-mode `.fr-isolation` marker **and**
     container evidence exists. This catches `bash -c`, `python -m fr` and
     scripts the bridge cannot see. It keys on the operated repo's marker, not
     on env, so test suites running `fr run` against temp repos inside a
     container are unaffected, and external mode (also a container) is never
     refused.
   - The host-side form must pass `fr-isolation-guard.sh` and its OpenCode and
     Hermes adapters.
   - Ephemeral pods (external mode) lose transcripts at teardown; capture at
     `deliver`, at the first `resolve` on a new host and at `fr archive` covers
     them, and `parity.yaml` states that dependency.
7. **Transcript gates stop degrading silently.** Wherever a gate cannot observe
   (no harness detected, no readable transcript), it records `unobserved` in the
   step's evidence and prints a warning, which is never quiet.
8. **Parity.** `parity.yaml` gains an isolation-mode dimension for usage capture
   and each transcript gate, per harness. Claude Code and OpenCode:
   live-verified in phase 4 (OpenCode noted "$0 for free models, estimated for
   Copilot-routed"). Hermes: *implemented, not live-verified (pod-only, no walk
   scheduled); per-message attribution coarse; ACP sessions report zero tokens
   (hermes-agent#6775)*. Claude Code's existing `enforced` claims on transcript
   gates are restated per mode.

### C. Step records (phase 3)

1. **The record.** `docs/superpowers/runs/<run-id>.records/<step>[__<item>].yaml`,
   kind `record` at version 1: tracked while in progress, committed with the
   agent's normal commits, and deleted by the `resolve` that applies it, in the
   same commit. Nothing new persists after a step.

   ```yaml
   schema_version: 1
   run: <run-id>
   step: implement-phase
   item: phase/2
   outcome: done                  # done | failed | blocked
   ticks: [P2.T1.S1, P2.T1.S2]
   refactor: {P2.T2: "none: two tuple entries, nothing to extract"}
   journal:
     - {kind: decision, id: d-p2-guard, title: "…", body: "…"}
     - {kind: finding, id: p2-f1, title: "…", body: "…", review_scope: in}
   resolves:
     - {id: p2-f1, state: fixed, body: "…"}
   acceptance:                    # brainstorm only
     - {id: …, capability: …, acceptance: …, origin: …, status: not-implemented}
   evidence: {review: r-p2, reviewer: <agent-id>}
   ```

2. **`fr run resolve --step <id> [--item <unit>] --record <file>`:**
   1. **Validates against the manifest.** The step's `emits:` decides the allowed
      sections (`journal` only where it emits `journal:<scope>`, `ticks` and
      `refactor` only on `implement-phase`, `acceptance` only on `brainstorm`,
      `resolves` on review steps). An unknown section, tick id or finding id, or
      a malformed entry, refuses the whole record with **nothing applied**.
   2. **Runs the step's existing gates** unchanged: review witness, operator
      guard on out-of-scope fixes, `deliver`'s `tests=` log, and the refactor
      check, which moves here from plan self-review (a task without a refactor
      step needs a `refactor:` reason). `no-refactor-because` journal entries are
      no longer required.
   3. **Applies everything in memory, writes atomically, commits once** through
      `commit_paths`: ticks, journal entries, acceptance rows (reports
      regenerated once), the cursor move, and at `deliver` the usage capture.
   4. **Prints one line**, e.g.
      `implement-phase phase/2 done · 3 ticked · 1 decision · 1 open finding · next: review-phase · a1b2c3d`.
      Warnings and refusals print in full.
3. **The template is the interface.** `fr pickup` and the dispatch brief carry a
   pre-filled record for the step: run, step and item set, only the allowed
   sections, and the plan's step ids listed. No agent needs `--help` mid-run.
   A resumed session is shown any in-progress record ("record in progress: 4
   ticks, 2 decisions") and continues it.
4. **`deliver` renders the PR body.** `resolve --step deliver` writes
   `pr-body.md` from both journals and `usage/`: in-scope findings, the
   out-of-scope section (or "none"), proportionality, and the cost table. The
   agent passes it to the PR. `resolve` then reads the live PR body through
   `fr.gh` and refuses `deliver` if a required section is missing, so a PR like
   #612 (no out-of-scope section) cannot be delivered.
5. **Ticks stay.** They are not duplicates of the cursor: `fr pickup` reads them
   for intra-phase resume (`commands/pickup_cmd.py:65`), `fr-execute` on the
   runner path has no cursor, and `render`/`diff`/`apply`, `fr status` and the
   spec roll-up read them. Applied inside `resolve`, they cost no turns.
6. **Verbs stay, as one-entry records.** `fr journal add/resolve`,
   `fr plan edit --tick/--complete-phase` and `fr acceptance add/set-status`
   build a single-entry record and hand it to the same apply engine. One code
   path for validation, gates, atomic write and commit; the verbs inherit quiet
   output and single-commit behaviour. The pipeline skills stop teaching them;
   the runner path, fr-acceptance, fr-debugging and humans keep using them.
7. **Per-step bookkeeping after this change:**

   | Step | Agent turns spent on bookkeeping |
   |---|---|
   | `brainstorm` | appends ride other messages, then 1 `resolve` |
   | `spec-review`, `review-phase` | the reviewer's structured return is the record, then 1 `resolve` |
   | `implement-phase` | appends ride the executor's edits, then 1 `resolve` |
   | `plan-review`, `journal-check` | 0 (`advance`, as today) |
   | `deliver` | 1 `resolve` (renders the PR body, captures usage) |

   Measured projection (§1 sample): bookkeeping turns fall from 6.1 to 1–2 per
   step, saving $91–$114 of the $150.68 those turns cost, about 8–10% of total
   spend. The remaining paperwork lines (reading $104, gates $35, `--help` $27)
   are addressed by the template (no `--help`), one-line gate output, and d7's
   later measurement.

### D. Brainstorm deliverables (no phase)

Built during the brainstorm with throwaway scripts; phase 1 regenerates both with
the product and they become its golden output.

- **Architecture page:** current versus future super-fr, as component diagrams,
  each component annotated with its measured cost (runtime spend from §1) and
  its maintenance weight (source and test lines).
- **Paper Trail Audit,** updated in place: the per-harness reconstruction, the
  bookkeeping measurement behind §5.C.7, the handoff investigation (§8) and this
  design's decisions.

## 6. Artifacts, versions, mirrors

- **Kinds:** `usage` v1 (new), `record` v1 (new, transient), `run` 6 → 7 (fields
  removed, frozen `RunStateV6`, migration, validator). Each is registered in
  `fr.artifacts.registry`, imported so its migration runs, and exercised by
  `fr validate artifacts`.
- **Version:** minor bump (new `fr usage` group and `fr-audit` skill, new
  mandatory pipeline behaviour), the next minor after gh#610's.
- **Skills and agents:** `fr-goal`, `fr-brainstorming`, `fr-execute` (verbs only),
  `fr-debugging` (records for the debug scope), `fr-phase-executor` and
  `fr-spec-reviewer` return shapes, and the new `fr-audit`. Then **both**
  `scripts/sync-opencode.py` and `scripts/sync-hermes.py`, and install wiring for
  the new skill (`test_install_copies_*`).
- **Workflow manifest:** both copies of `fr-goal.yaml` (`plugins/super-fr/workflows/`,
  `packages/fr/src/fr/workflows/`) stay identical; `emits:` becomes the record
  schema.
- **Parity:** `parity.yaml` rows per harness × isolation mode (§5.B.8).
- **Explainers:** `docs/explainers/01-fr-goal.md` describes the pipeline, so it is
  updated and re-rendered per the explainers-currency rule (`--isolated`).
- **AGENTS.md:** repo-shape entries for `fr/usage`, `usage/`, records and the
  host-side rule.
- **Acceptance:** `fr-goal-main-session-cost` is re-pointed, not superseded: its
  claim (per-step cost for the operator) is now delivered by `usage/`'s per-step
  rollup. Its levels move to the usage tests; it stays `skipped` until phase 4.

## 7. Test Plan

1. **Readers.** Fixtures per harness, redacted: Claude Code JSONL with duplicated
   `message.id` records plus `cost-state`; an OpenCode SQLite subset (`message`,
   `part`); a Hermes `state.db` built from the documented schema. Totals match
   the harness figure within rounding; an unreadable source gives `unavailable`.
2. **Classifier.** Table tests over real command shapes: `fr isolation exec --`
   wrapped, `R=… &&` prefixed, heredocs, `--help`, path-based reads.
3. **Golden audit.** Re-deriving the nine-session sample reproduces the published
   shares (paperwork 23–37% per session, 30.2% pooled) within 0.5 points.
4. **Usage kind.** Validator, duplicate keys, one entry per host, re-capture
   replaces only its own host, archive moves the file with the plan.
5. **Privacy.** A capture on a fixture host named `laptop.corp.example` stores no
   hostname, base URL, path or message content.
6. **Run 6 → 7.** Frozen `RunStateV6`, every-hop chain `[2…7]`, figures moved into
   `usage/`, an unconvertible cursor byte-identical, a wholly-v7 body under a v6
   stamp completed.
7. **Backfill.** Writes new files only; archived runs hash-identical before and
   after.
8. **Host-side rule.** `fr isolation exec -- fr run …` in devcontainer mode exits 2
   with the right host command (`uv run fr` here, `fr` in a consumer fixture);
   `bash -c '… fr run …'` inside a devcontainer-mode repo is refused in process;
   a temp repo inside a container and an external-mode repo are not refused. The
   host-side form passes the bash guard and both adapters.
9. **Unobserved gates.** With no harness detected, a transcript gate records
   `unobserved` and prints a warning.
10. **Records.** Per step, only manifest-allowed sections are accepted; an invalid
    record applies nothing; gates still fire; one `resolve` gives one commit, a
    clean tree and one stdout line; warnings print in full.
11. **Verbs.** `fr journal add`, `fr plan edit --tick` and `fr acceptance
    set-status` route through the apply engine (one-entry record), with
    unchanged CLI behaviour otherwise.
12. **Stale session.** Session A commits a partial record; session B, via
    `fr pickup`, sees it, completes it and resolves.
13. **PR body.** `deliver` refuses when the live PR body lacks the out-of-scope
    section.
14. **`fr-audit`.** The skill's engine regenerates both brainstorm pages from the
    sample.
15. **Post-merge (manual, phase 4).** A live `/fr-goal` on Claude Code and on
    OpenCode, at least one of them in **devcontainer** mode. Bar: its `usage/`
    file has readable sessions, `fr run cost` renders on another checkout, and
    bookkeeping turns per step ≤ 2 (baseline 6.1).

## 8. The handoff-quality hypothesis (recorded, not investigated)

The operator suspects a recent quality drop, possibly from the bounded executor
handoff (2026-09-20). What the data shows:
- Executors are not starved: subagents made 557 paperwork reads (1.9M chars,
  3.4k average), fetching what the brief collapses.
- Collapsed findings do not return: 7 re-open records across all journals, none
  describing a re-broken earlier fix.
- There is no baseline: per-phase review findings (`evidence.findings`) are
  recorded only from 2026-09-21, and the bound, mandatory independent reviewers
  and a model change (Opus 5 → Opus 5.5) landed within the same days.

It is filed as an issue. This design adds the missing baseline: `usage/` records
dispatch-brief sizes and per-step cost, and step records carry review findings.

## 9. Acceptance rows

Born with this spec (`not-implemented`), presented at the end of the brainstorm:

| id | acceptance | target level |
|---|---|---|
| `usage-reconstruct-cross-harness` | The operator can reconstruct a run's cost per model, step and activity from Claude Code, OpenCode or Hermes session data | unit |
| `usage-captured-at-deliver` | Delivering a run stores its usage in `docs/superpowers/usage/<run-id>.yaml` without an extra agent turn | int |
| `usage-readable-on-any-host` | `fr run cost` shows a delivered run's cost on a checkout that never ran it | int |
| `usage-privacy-no-host-identity` | A usage file never contains a hostname, base URL, path or message content | unit |
| `usage-devcontainer-captures` | A devcontainer-mode run's usage file has readable sessions | manual → int |
| `step-record-one-resolve` | Each agent step's bookkeeping is one `fr run resolve --record`, one commit, one line | int |
| `step-record-atomic-refusal` | An invalid record changes nothing | unit |
| `stale-session-resumes-record` | A new session picks up an in-progress step record and completes it | int |
| `bookkeeping-turns-per-step` | A live run spends at most 2 bookkeeping turns per step | manual |
| `deliver-pr-body-sections` | A PR missing a required fr-rendered section cannot be delivered | int |
| `audit-pages-regenerated` | The operator can regenerate the audit and architecture pages from run data | int |

## Implementation Plans

| Plan | Status |
|---|---|
