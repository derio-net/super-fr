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
