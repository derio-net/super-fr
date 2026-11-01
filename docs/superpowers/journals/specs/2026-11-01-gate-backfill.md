<!-- fr:journal-schema=3 -->
# Journal: 2026-11-01-gate-backfill

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-01T15:02:28+00:00 input=true -->
### operator-brief · discovery · Operator brief (coordinator goal file), verbatim; private corpus paths redacted to <org>

# Goal: put old owed work into v6's gate lanes (`fr gate backfill`)

Work merged before v6 has no exit gates. Its owed live walks and manual operations hide in closed issues, hand-written trackers and audit files. Ship a command, working name `fr gate backfill` (naming is the spec's call), that brings that debt into v6's own machinery, so every repo has **one queue**: the board's "Needs you · Tester/DevOps" lanes, closed through `fr gate pass`.

Per repo, for each owed item:
- add the right `gate:tester` / `gate:devops` label to the merged PR that delivered the work;
- file or reuse an owed tracker through fr's marker mechanism (the one `fr archive` uses for owed actions, spec debt-engine R21);
- set `fr:awaiting-live` when only a walk remains.

Dry run by default; `--yes` writes, through the forge adapter only (`GhClient`).

## Why a command and not a migration

Artifact migrations are file-only and must be safe offline in CI; labels and issues live on the forge. A file-only migration may still be part of it: for example, giving old matrix rows that describe live walks `verify: live` so fr can see them.

## Read first

- `fr debt` (`packages/fr/src/fr/debt/`). It already folds every owed item per repo (journal > row > plan > issue), so build on it rather than writing a new finder.
- `fr/verification/exit.py` and `fr/gates.py`; `fr/archive_followups.py` (owed issues, `_existing_owed` dedup, markers); `fr/labels.py`.
- Real-world corpus: the operator's three org reconciliation reports (`<org>-triage-2026-10-31.md` §6 / §6.8) plus the recovered 2026-10-13 batch audit verdicts. These show which shapes of owed work exist: closed-with-unmet-ask issues, unticked manual phases, walk-owed rows, unfiled audit gaps.
- Open questions to settle in the spec: how to find the delivering PR for an old item; what happens to an issue already closed by `Closes` (reopen, or a linked owed tracker; both reconciliations recommend linked trackers); repos with `tracking: none`; and the related super-fr#1268 (labels created only when actually needed).

## Constraints

- fr-goal's normal pipeline. One question round, asked in this pane.
- Heavy suites only via the shared test slot. Prefer CI.
- Change fragment (minor); never edit versions. The PR stays draft.
- Test Plan steps carry a cost line (super-fr#1260). The live walk is "walked on first real use": the per-repo sweep that follows, not a rehearsal.
- super-fr is public: the corpus is private, so cite it only by shape, never by repo names outside derio-net. Fixtures use fictional names.
- A parallel run is changing the migration gate (super-fr#1242). Stay out of `fr/artifacts/trigger.py`.

## Coordinator corpus update (mid-round, 2026-11-01), summarised by shape

1. `fr archive` has no dry run but files forge issues; backfill must preview by default, archive probably wants `--dry-run` (in scope or follow-up).
2. Hand-made pre-v6 trackers carry no `fr-owed` marker, so archive filed duplicates of them; decide adopt-vs-file-and-close and how to match.
3. Marker trust: `owned_owed_key` reuses only this account's `fr:owed` issues with the marker last; say what happens to issues opened by others.
4. `fr archive --branch` sees only that branch; backfill must be repo-wide.
5. Stale unticked manual phases (months old, probably done): a review step before filing (age, ticked count; tick / n/a / keep owed).
6. Walk rows `not-implemented` but `verify: live` should be `walk-owed`; pre-v5 `skipped` rows need a strategy; a person's call where evidence is only a note.
7. Parked repos/areas need a record-but-don't-surface mode.
8. Closed-with-unmet-ask: all three reconciliations chose linked trackers, no reopens, with a link comment.
Also: the board's Tester/DevOps lanes show only triage-batch PRs; the spec must say how backfilled items reach them.

<!-- fr:journal kind=decision scope=spec id=d1-input created=2026-11-01T15:02:28+00:00 decided_by=operator -->
### d1-input · decision · Candidates = fr debt's fold + an optional operator manifest

Operator (Q1): fr debt + manifest (`--from <yaml>`) for closed-with-unmet-ask issues and audit gaps. Spec R2, §B.

<!-- fr:journal kind=decision scope=spec id=d2-delivering-pr created=2026-11-01T15:02:28+00:00 decided_by=operator -->
### d2-delivering-pr · decision · Delivering PR by an evidence chain, never guessed

Operator (Q2): manifest pr → run branch → commit that added the plan/spec → linked issue PR; confirmed merged; unresolved reported, not acted on. Spec R3, §C.

<!-- fr:journal kind=decision scope=spec id=d3-board created=2026-11-01T15:02:28+00:00 decided_by=operator -->
### d3-board · decision · The board shows gate-labelled merged PRs in this PR

Operator (Q3): collect reads merged PRs carrying held gate labels (facts schema bump) and the Needs-you Tester/DevOps lanes list them. Spec R13, §I.

<!-- fr:journal kind=decision scope=spec id=d4-closed-issue created=2026-11-01T15:02:28+00:00 decided_by=operator -->
### d4-closed-issue · decision · Closed issue with an unmet ask: linked owed tracker, never reopen

Operator (Q4). Spec R6, §F.

<!-- fr:journal kind=decision scope=spec id=d5-pass-closes created=2026-11-01T15:02:28+00:00 decided_by=operator -->
### d5-pass-closes · decision · fr gate pass closes the fr-owned trackers naming the PR and gate

Operator (Q5): by the PR marker. Spec R12, §H.

<!-- fr:journal kind=decision scope=spec id=d6-tracking-none created=2026-11-01T15:02:28+00:00 decided_by=operator -->
### d6-tracking-none · decision · tracking none: PR gate labels only

Operator (Q6): no tracker, comment or fr:awaiting-live; owed items still reported. Spec R10.

<!-- fr:journal kind=decision scope=spec id=d7-1268 created=2026-11-01T15:02:28+00:00 decided_by=operator -->
### d7-1268 · decision · Adopt #1268's lazy-label rule; leave collect's fix to #1268

Operator (Q7). Spec R6, §G.1.

<!-- fr:journal kind=decision scope=spec id=d8-repo-files created=2026-11-01T15:02:28+00:00 decided_by=operator -->
### d8-repo-files · decision · Forge only; print the repo-file commands; no artifact migration

Operator (Q8): gate stays in READ_ONLY_COMMANDS; nothing in registry.py or trigger.py. Spec R11, R14.

<!-- fr:journal kind=decision scope=spec id=d9-verification created=2026-11-01T15:02:28+00:00 decided_by=operator -->
### d9-verification · decision · candidate pre-merge + one live post-merge row under gate tester

Operator (Q9). Spec ## Verification; the live row is walked on first real use (Test Plan 1).

<!-- fr:journal kind=decision scope=spec id=d10-unmarked-trackers created=2026-11-01T15:02:28+00:00 decided_by=operator -->
### d10-unmarked-trackers · decision · Unmarked trackers adopted only by an explicit decision; adoption closes fr's duplicate

Agent, from corpus update 2 (no second round was forecast). Look-alikes are suggestions in the plan file. Spec R9, §E, §F.

<!-- fr:journal kind=decision scope=spec id=d11-foreign-issues created=2026-11-01T15:02:28+00:00 decided_by=operator -->
### d11-foreign-issues · decision · Issues written by others are never reused, edited or closed

Agent, from corpus update 3: adopt allows a comment and labels only. Spec R8.

<!-- fr:journal kind=decision scope=spec id=d12-review-step created=2026-11-01T15:02:28+00:00 decided_by=operator -->
### d12-review-step · decision · The plan file is the review step; stale manual phases default to review

Agent, from corpus update 5: dry run → edit decisions → --yes; review entries are skipped. Spec R5, §E.

<!-- fr:journal kind=decision scope=spec id=d13-park created=2026-11-01T15:02:28+00:00 decided_by=operator -->
### d13-park · decision · Parked scope is a persistent park decision

Agent, from corpus update 7. Spec §E.

<!-- fr:journal kind=decision scope=spec id=d14-archive-dry-run created=2026-11-01T15:02:28+00:00 decided_by=operator -->
### d14-archive-dry-run · decision · fr archive --dry-run is a follow-up, not built here

Agent, from corpus update 1: backfill gives the sweep its preview; the archive change is separate scope.

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · gate_for has no rule for spec:<slug>#step<n> or issue:<ref> keys, which the fold yields

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · Adopting an issue (or a labelled hand-made tracker) feeds a second issue:<ref> candidate back into the fold

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · The §I dedup hides closed-out batch PRs: lane_of never places a batch that has a close-out event

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · A PR holding both gates: collect's two label lists return it twice, and the lane rule puts it in Tester only

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · §I does not define the unsupported-forge warning, the partial-collect carry of gated_prs, or the new GhClient method

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · The `commit` step names the planning PR, not the delivering one, for plans merged before their code

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · _run_branches reads live cursors only, but §C.2 relies on it for live and archived cursors

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · plan:<name>#p<n> covers every open phase of a merged plan, not only manual ones, yet always gets devops

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · R11's `fr closeout outcome --na` applies to Test Plan steps, not plan phases; the per-key command mapping is undefined

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · R11's 'not-implemented row that names a live walk' has no detection rule, and the brief's skipped rows go unaddressed

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · Closing a tracker at gate pass leaves the debt open, and the next backfill or archive re-files it

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-12 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-12 · finding [open] (reviewer: in scope) · No retry path when R12's tracker close fails: a re-run of `fr gate pass` refuses on the swapped label

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-13 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-13 · finding [open] (reviewer: in scope) · The adopt marker names no PR or gate, so §H cannot find 'the adopted tracker for that PR' without guessing

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-14 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-14 · finding [open] (reviewer: in scope) · The `fr gate pass` lines the spec prints refuse: --notes is missing, and devops on an old PR needs --no-run-evidence or --run

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-15 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-15 · finding [open] (reviewer: in scope) · `--yes` refusals and plan-file drift are not stated (no plan file, other repo, adopt target, re-resolved PR or gate)

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-16 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-16 · finding [open] (reviewer: in scope) · The lazy-label rule is stated for gate:<g> only, while the fr:owed / fr:awaiting-live path through file_owed_ends creates labels up front

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-17 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-17 · finding [open] (reviewer: in scope) · `park` prints only a count, which contradicts R1/R10's 'summary of every candidate'

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-18 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-18 · finding [open] (reviewer: in scope) · Gate pass through the driver route bypasses R12's tracker close

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-19 created=2026-11-01T15:16:32+00:00 state=open review_scope=in -->
### sr-19 · finding [open] (reviewer: in scope) · Agent decisions d10–d14 are stamped decided_by=operator in the spec journal

Raised by the dispatched fr-spec-reviewer (spec-review-1).

<!-- fr:journal kind=decision scope=spec id=d10-unmarked-trackers-agent created=2026-11-01T15:16:32+00:00 decided_by=agent -->
### d10-unmarked-trackers-agent · decision · Unmarked trackers adopted only by an explicit decision; adoption closes fr's duplicate

Supersedes d10-unmarked-trackers, stamped operator in error: the agent's decision, from corpus update 2. Spec R9, §B, §E, §F.

<!-- fr:journal kind=decision scope=spec id=d11-foreign-issues-agent created=2026-11-01T15:16:32+00:00 decided_by=agent -->
### d11-foreign-issues-agent · decision · Issues written by others are never reused, edited or closed

Supersedes d11-foreign-issues (stamped operator in error): the agent's decision, from corpus update 3. Spec R8.

<!-- fr:journal kind=decision scope=spec id=d12-review-step-agent created=2026-11-01T15:16:32+00:00 decided_by=agent -->
### d12-review-step-agent · decision · The plan file is the review step; stale manual phases default to review

Supersedes d12-review-step (stamped operator in error): the agent's decision, from corpus update 5. Spec R5, §E.

<!-- fr:journal kind=decision scope=spec id=d13-park-agent created=2026-11-01T15:16:32+00:00 decided_by=agent -->
### d13-park-agent · decision · Parked scope is a persistent park decision, listed under its own heading

Supersedes d13-park (stamped operator in error): the agent's decision, from corpus update 7. Spec §E.

<!-- fr:journal kind=decision scope=spec id=d14-archive-dry-run-agent created=2026-11-01T15:16:32+00:00 decided_by=agent -->
### d14-archive-dry-run-agent · decision · fr archive --dry-run is a follow-up, not built here

Supersedes d14-archive-dry-run (stamped operator in error): the agent's decision, from corpus update 1.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-01T15:16:32+00:00 -->
### spec-review-1 · review · spec review of 2026-11-01-gate-backfill-design

19 findings raised: sr-1 to sr-19, all in scope, all fixed in the spec (see resolutions).

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: gate_for has no rule for spec:<slug>#step<n> or issue:<ref> keys, which the fold yields

Fixed: §D table gives spec: keys devops when the spec's run gate is devops else tester; issue: keys take the manifest gate else None → review, refused by --yes until set (R4).

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: Adopting an issue (or a labelled hand-made tracker) feeds a second issue:<ref> candidate back into the fold

Fixed: §B drops an issue: candidate that is an adopt target or a backfill tracker, and defaults a look-alike to review naming the key it may track (R2).

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: The §I dedup hides closed-out batch PRs: lane_of never places a batch that has a close-out event

Fixed: §I drops a gated_prs entry only when lane_of placed its batch in a lane or its ledger is unknown; closed-out batch PRs appear via gated_prs; the row's verification line names the case.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: A PR holding both gates: collect's two label lists return it twice, and the lane rule puts it in Tester only

Fixed: collect dedupes by (repo, number); R13 states one lane, tester first, else devops.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: §I does not define the unsupported-forge warning, the partial-collect carry of gated_prs, or the new GhClient method

Fixed: §I names GhClient.list_merged_prs_by_label, the keyword-only Forge method, TruncatedList gated-prs, Facts.gated_unread/GatedUnread with describe(), the --only carry, and a gated-unread Need.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: The `commit` step names the planning PR, not the delivering one, for plans merged before their code

Fixed: §C reads the merge's diff locally; a docs/-only PR is planning: true and defaults to review (R3).

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: _run_branches reads live cursors only, but §C.2 relies on it for live and archived cursors

Fixed: §C.2 reads live and archived cursors through one shared helper (gate_cmd._cursors moved onto it), maps row:/spec: candidates via the origin spec and its plans, and reports several merged PRs as an ambiguity defaulting to review.

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: plan:<name>#p<n> covers every open phase of a merged plan, not only manual ones, yet always gets devops

Fixed: §B reads the phase header; §D gives an agentic open phase no gate (review); Background corrects the merged_manual_open description.

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: R11's `fr closeout outcome --na` applies to Test Plan steps, not plan phases; the per-key command mapping is undefined

Fixed: §E gives a key-kind × decision table with exact commands and required flags, refusing undefined cells; na requires a note.

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: R11's 'not-implemented row that names a live walk' has no detection rule, and the brief's skipped rows go unaddressed

Fixed: §E row reconcile uses effective_strategy being post-merge; rows are listed, not plan entries; Non-goals give skipped rows to fr migrate artifacts, which the chore runs first.

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: Closing a tracker at gate pass leaves the debt open, and the next backfill or archive re-files it

Fixed: §G.1 skips all writes on a passed PR and prints the key's discharge command; §H prints each closed tracker's discharge command (R6, R12).

<!-- fr:journal kind=finding scope=spec id=sr-12-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-12 -->
### sr-12-resolved · finding [fixed] · resolves sr-12: No retry path when R12's tracker close fails: a re-run of `fr gate pass` refuses on the swapped label

Fixed: §H — fr gate pass on a PR with gate:<g>-passed and no gate:<g> runs only the close helper (R12).

<!-- fr:journal kind=finding scope=spec id=sr-13-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-13 -->
### sr-13-resolved · finding [fixed] · resolves sr-13: The adopt marker names no PR or gate, so §H cannot find 'the adopted tracker for that PR' without guessing

Fixed: distinct markers fr-gate-adopt:<key> gate:<g> pr:<n> and fr-gate-link:<key> tracker:<ref>; adopt adds fr:owed so §H reads only fr:owed issues and their comments.

<!-- fr:journal kind=finding scope=spec id=sr-14-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-14 -->
### sr-14-resolved · finding [fixed] · resolves sr-14: The `fr gate pass` lines the spec prints refuse: --notes is missing, and devops on an old PR needs --no-run-evidence or --run

Fixed: §F defines the printed pass command with --notes and, for devops, --run <id> or --no-run-evidence, and states how a pre-fr-ops run's evidence folds.

<!-- fr:journal kind=finding scope=spec id=sr-15-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-15 -->
### sr-15-resolved · finding [fixed] · resolves sr-15: `--yes` refusals and plan-file drift are not stated (no plan file, other repo, adopt target, re-resolved PR or gate)

Fixed: new R15 and §A — what is applied is what was reviewed; a missing or other-repo plan refuses; a drifted PR/gate, a bad adopt target or a mismatched tracker marker skips the entry with a line.

<!-- fr:journal kind=finding scope=spec id=sr-16-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-16 -->
### sr-16-resolved · finding [fixed] · resolves sr-16: The lazy-label rule is stated for gate:<g> only, while the fr:owed / fr:awaiting-live path through file_owed_ends creates labels up front

Fixed: §F backfill files its own trackers; §G ensures fr:owed and fr:awaiting-live just before first use; R6 says every label.

<!-- fr:journal kind=finding scope=spec id=sr-17-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-17 -->
### sr-17-resolved · finding [fixed] · resolves sr-17: `park` prints only a count, which contradicts R1/R10's 'summary of every candidate'

Fixed: parked entries are listed one per line under a Parked heading (R1, §E, d13).

<!-- fr:journal kind=finding scope=spec id=sr-18-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-18 -->
### sr-18-resolved · finding [fixed] · resolves sr-18: Gate pass through the driver route bypasses R12's tracker close

Fixed: §H's close_gate_trackers sits beside pass_gate and both routes (fr gate pass, the driver's rows-walked pass) call it (R12).

<!-- fr:journal kind=finding scope=spec id=sr-19-resolved created=2026-11-01T15:16:32+00:00 state=fixed resolves=sr-19 -->
### sr-19-resolved · finding [fixed] · resolves sr-19: Agent decisions d10–d14 are stamped decided_by=operator in the spec journal

Fixed: the brainstorm record omitted answered_by: agent on d10–d14; this record supersedes each with an agent-attributed decision (…-agent), so the PR body attributes them correctly.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-01T15:16:34+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  board-lanes-gated-prs: none
  gate-backfill-apply-ledger: tester
  gate-backfill-delivering-pr: none
  gate-backfill-dry-run-plan: tester
  gate-backfill-first-real-sweep: tester
  gate-backfill-tracker-trust: none
  gate-pass-closes-backfill-trackers: none
row_kinds:
  board-lanes-gated-prs: none
  gate-backfill-apply-ledger: candidate
  gate-backfill-delivering-pr: none
  gate-backfill-dry-run-plan: candidate
  gate-backfill-first-real-sweep: live
  gate-backfill-tracker-trust: none
  gate-pass-closes-backfill-trackers: none
run_gate: tester
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-01-gate-backfill-p2 created=2026-11-01T15:19:52+00:00 -->
### phase-split-2026-11-01-gate-backfill-p2 · decision · ask: --yes apply (labels, trackers, adopt, idempotency, refusals; R6–R10, R15) is its own reviewable ask

Spec Requirements group; see plan _prose.md.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-01-gate-backfill-p3 created=2026-11-01T15:19:57+00:00 -->
### phase-split-2026-11-01-gate-backfill-p3 · decision · ask: fr gate pass closing backfill trackers on both routes with a retry (R12) is its own ask

Spec Requirements group; see plan _prose.md.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-01-gate-backfill-p4 created=2026-11-01T15:20:03+00:00 -->
### phase-split-2026-11-01-gate-backfill-p4 · decision · ask: the board listing gate-labelled merged PRs (R13) is its own ask, independent of apply

Spec Requirements group; see plan _prose.md.
