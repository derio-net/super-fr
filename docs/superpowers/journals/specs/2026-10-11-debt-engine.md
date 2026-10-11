# Journal: 2026-10-11-debt-engine

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-11T17:23:03+00:00 input=true -->
### operator-brief · discovery · Operator brief (batch debt-engine, super-fr#1121)

Batch brief (as typed): `/fr-goal fr debt: one debt engine, a weekly Technical debt issue, split the skipped status` — batch `debt-engine` of derio-net/super-fr, 1 issue, ONE PR; branch `feat/batch-debt-engine`; draft PR once the spec is committed with `Closes derio-net/super-fr#1121`; no member issue as a phase tracking_issue. Why together: operator priority (2026-10-11); brainstorm first, the skipped split is an artifact migration; replaces the five parked acceptance-debt digests.

## super-fr#1121: Technical debt digest: one weekly '<repo>: Technical debt' issue (acceptance + plans) via an fr debt engine; triage reads it; split the overloaded 'skipped' status

## Problem

Debt is invisible and keeps growing. Every repo carries two kinds of it, and today nothing surfaces either one where the operator actually looks:

- **Acceptance debt.** `acceptance-report.yml` upserts a weekly "Acceptance debt" issue per repo (marker `fr-acceptance-digest`). The SessionStart nag (`fr-acceptance-nag.sh`) only fires inside the repo the session sits in.
- **Plan debt.** Plans that merged complete but were never archived, and in-progress plans that went stale. `fr status` and `fr-progress` list them on demand only. `test_tripwire_unarchived_plans.py` warns in super-fr's own CI only. There's no weekly issue and no session nag.

The org-wide triages run on 2026-10-10 (three scopes, about 240 issues) parked every "Acceptance debt" issue as a tier-6 tracker. A digest issue holding 60 rows can't be ranked, batched or closed, so in practice the debt drops out of view.

## Proposal

### A. One engine: `fr debt`

Add an `fr debt` command to the `fr` wheel that computes a repo's debt as structured data. Everything below calls it; nothing re-derives debt.

- **acceptance:** rows by status (but see C, which changes what counts).
- **plans, three categories that need different responses:**
  - **merged complete, not archived:** bookkeeping that `fr archive` fixes mechanically. Uses `fr.archive.merge_evidence(...).complete_on_ref`, the one definition of "merged".
  - **in progress, stale:** no commits on the branch and no PR activity in N days (configurable). Real debt that needs an operator decision: resume, re-scope or abandon.
  - **in progress, active:** not debt, so not listed. Listing it would turn the issue into noise.
- Possibly: specs with no plan, and journals with open findings (`fr journal check`).

### B. The weekly issue becomes `<repo>: Technical debt`

- It has two sections, Acceptance and Plans, rendered from `fr debt`.
- Keep recognizing the old `fr-acceptance-digest` marker, so existing open issues are **renamed in place**, not duplicated. Write a new marker going forward.
- **One attached action, where it's mechanical:** for merged-complete-unarchived plans, the weekly job opens (or refreshes) one archive PR, rather than only reporting them.

### C. Triage reads the debt; it doesn't rank the issue

- `fr triage collect` recognizes the digest marker and reads `fr debt` per repo.
- The digest gets a set of its own (like `awaiting live`): never ranked, never "unplaced".
- The board gets a **Debt** panel per repo, with counts and a trend from the existing snapshots (for example "acceptance not-implemented 28 → 30 since the last report").
- The work inside it becomes ordinary batches, such as "archive sweep" or "backfill acceptance rows for theme X".

## "skipped" is overloaded, and that blocks any honest debt count

`skipped` is documented as "verification exists, not in CI". In practice it covers at least four different situations. Live examples from this repo's matrix (SessionStart nag, 2026-10-10):

| row | what "skipped" actually means here |
|---|---|
| `isolation-suite-lifecycle` | **Proven once, live:** "the live worktree+container walk was proven at the 2.4.0 release, not in CI" |
| `acceptance-pipeline-rows` | **Live walk owed:** "end-to-end toy walk (Test Plan item 4) owed post-merge" |
| `acceptance-added-since` | **Process, not automatable:** "the PR-body defense is process — demonstrated in PR #352, not automated" |
| (others) | **Automatable but unwired:** a test exists and could run in CI, but doesn't |

Only the last one is plainly debt. "Proven once" is evidence that may have gone stale. "Walk owed" is a scheduled obligation (and overlaps `fr:awaiting-live` and the matrix's `verify` / `walks` fields from the verification-strategies work). "Process" may never move. Counting all four as one number gives a figure that grows for good reasons and bad, and can't be acted on.

**Ask:** split `skipped` into explicit statuses, or derive the meaning from the row's `verify` strategy and `walks`, which may already carry it. Suggested names: `unwired`, `walk-owed`, `walked` (with a date or release, and maybe an age-out), and `manual` / `process`. Migrate existing rows through the artifact-migration framework (a matrix-kind stamp bump, `.claude/rules/artifact-versioning.md`). The term itself is easy to misread: "skipped" sounds like "a test was skipped", not "verification lives outside CI".

## D. Owed operator actions: nothing slips through, and one place to find them

**Gap (found 2026-10-11).** A close-out (`fr/run/closeout.py`) says "run the spec's Test Plan", and what happens to a step the session can't or shouldn't run is left to its judgement. Real case: derio-net/frank#835 ran Test Plan steps 1–3, and left step 4 to the operator because it means a ~10-minute bot outage. The session happened to file it as frank#834. Had it only written "left to the operator" in the PR body, the step would have disappeared when the housekeeping PR merged.

Today owed actions survive only through:
- `fr:awaiting-live`, but only for steps that are post-merge matrix rows;
- a held plan with an unticked `[manual]` phase, visible only via `fr status`;
- whatever the session chose to file.

### D.1 No silent skip

- Every Test Plan step gets an **explicit outcome at close-out**: `run` (with evidence), `owed` (an operator action, saying why) or `n/a` (with a reason).
- The close-out can't finish, and `fr archive --branch` holds, until every step has one, the same way an open journal finding blocks `fr journal check` today.
- An `owed` step is made durable mechanically, never by session judgement:
  - one journal entry recording the step, why it's owed and who owes it;
  - one issue labelled as an owed walk (reuse `fr:awaiting-live`, or add a sibling such as `fr:owed`, a design decision) that names the step and the command or check that completes it.
- The same applies to a `[manual]` plan phase left unticked at archive. "Held" stays the archive behaviour, but it also gets an owed entry and an issue, so it stops being visible only through `fr status`.

### D.2 One query: what does this repo owe?

`fr debt` (proposal A) gets an **Owed** section, folded from sources that already exist:
- open `fr:awaiting-live` / owed issues;
- held plans with an unticked manual phase;
- unwalked post-merge acceptance rows;
- journal entries of the owed kind with no resolution, **including in archived journals**.

Journals are a natural record for this. They're append-only, `fr journal resolve` already closes an entry with a RESOLUTION RECORD, and `fr.archive_followups` already reads archived journals' open ends. So an owed step logged at close-out stays queryable after `fr archive` moves the journal to `implemented/`, and it's discharged by `fr journal resolve <id> --fixed` with the walk's evidence, which also closes its issue.

The weekly `<repo>: Technical debt` issue (B) and the triage Debt panel (C) render this section like the others.

### D.3 Constraints

- A new journal entry kind is a **shape change**: the kinds are a closed vocabulary (`decision`, `review`, `discovery`, `finding`, `repro`, `hypothesis`, `ruled-out`, `root-cause`). It ships with a stamp bump, a registered migration and the structure validator, per `.claude/rules/artifact-versioning.md`. Reusing `finding` with an `owed` state is the alternative to weigh.
- The close-out brief is read by a fresh session with no memory, so the per-step outcome must come from a structured source (the spec's Test Plan, parsed), not from the session's recollection.

## Deliberately out of scope: the ratchet

A CI gate that fails a PR adding net-new debt was considered and **deferred**. It's not always practical (a new spec legitimately creates `not-implemented` rows). It's worth revisiting only after `skipped` is split, at which point a ratchet on `unwired` alone might be cheap and fair.

## Acceptance

- `fr debt` on this repo reports the three plan categories and acceptance by (new) status, as JSON and as text.
- The weekly workflow renames an existing "Acceptance debt" issue to `<repo>: Technical debt` in place, and opens or refreshes one archive PR when merged-unarchived plans exist.
- `fr triage check` lists the digest in its own set, and the board shows a per-repo Debt panel with a trend.
- The `skipped` split ships with a registered matrix migration, and every existing row lands in exactly one new status.
- A close-out with a Test Plan step that has no recorded outcome can't finish, and every `owed` step leaves a journal entry plus an issue (scenario test: a skipped step is never silently dropped).
- `fr debt` lists owed actions from open owed/awaiting-live issues, held manual phases, unwalked post-merge rows and unresolved owed journal entries, archived journals included, and `fr journal resolve` with evidence removes an entry from that list.


--- comment ---
## Another instance: derio-net/agent-images, 2026-10-11

Found while delivering derio-net/agent-images#164. fr 5.19.3 asked to migrate artifacts, and `fr migrate artifacts` reported **"2 in-flight plan(s) have no run cursor"**, offering adoption. Neither plan was in flight. Both delivery PRs had **merged**:

| plan | PR | what's left unticked |
|---|---|---|
| `2026-07-23--agents--agent-images-version-sweep` | #155, merged | phase 6 "Branch build validation" (3 steps) · phase 7 `[manual] omnictl target discovery` (2 steps) |
| `2026-08-03-hermes-ssh-bun-runtime` | #158, merged | phase 3 `[manual] Operator: build the branch, merge, hand the SHA to frank` (2 steps) |

This is the "merged, not archived" category (A) colliding with D.1's held `[manual]` phase:

- **Nothing surfaced it for about two months.** Neither plan was archived, and the unticked manual phases were visible only through fr's own tooling. The operator's working assumption was "they're stalled".
- **The leftover steps are a mix of dead and owed work.** Hermes phase 3 and version-sweep phase 6 are effectively done or moot: the PR merged, and main's push build replaced the branch build. Version-sweep phase 7 (omnictl target discovery) may be a **real owed operator action**. Today nothing records which is which: no owed entry, no issue.
- **Adoption can't express "merged, steps owed".** `fr run adopt <plan> --branch feat/... --pr <merged PR URL>` lands both cursors on **`implement pending`**, because the manual phases are unticked and no `kind=review` entries exist. A run whose PR merged weeks ago now reads as in implementation. Under D.1 these would be `owed` outcomes, or `n/a` with a reason, recorded at close-out, and `fr debt` would list version-sweep phase 7 under **Owed** instead of inventing a cursor.
- **Adoption has a pitfall.** Without `--branch`, `fr run adopt` derives the run id from the checked-out branch. Run from an unrelated fix branch, it bound the version-sweep plan to `2026-10-11-fix-batch-agent-session-once`, and the second plan's adopt then collided on that id. I caught it and reverted it before pushing. For a plan whose PR merged, the branch could be inferred from the PR, or adopt could refuse when the checked-out branch isn't the plan's.

The runs are now adopted as `2026-10-11-feat-upstream-version-sweep` and `2026-10-11-feat-hermes-ssh-bun-runtime`, riding in agent-images#164.

<!-- fr:journal kind=decision scope=spec id=scope-all created=2026-10-11T17:23:03+00:00 -->
### scope-all · decision · Scope: all of A–D in one PR

Operator chose all of #1121 (engine, weekly issue, triage panel, skipped split, owed actions incl. the close-out per-step gate) in this one PR.

decider: operator (Round 1/2 question round)

<!-- fr:journal kind=decision scope=spec id=status-names created=2026-10-11T17:23:03+00:00 -->
### status-names · decision · skipped → unwired / walk-owed / walked / manual

Four explicit statuses; 27 of 38 skipped rows carry no verify/walks, so derivation from existing fields was ruled out by measurement.

decider: operator (Round 1/2 question round)

<!-- fr:journal kind=decision scope=spec id=migration-rule created=2026-10-11T17:23:03+00:00 -->
### migration-rule · decision · Mechanical migration rule + hand reclassification here

pass walk → walked; effective post-merge strategy → walk-owed; else → unwired. super-fr's own rows are then reclassified by hand with set-status (R7).

decider: operator (Round 1/2 question round)

<!-- fr:journal kind=decision scope=spec id=walked-not-debt created=2026-10-11T17:23:03+00:00 -->
### walked-not-debt · decision · walked is not debt; show its age

walked rows are listed with the latest passing walk's date; no age-out rule in this PR.

decider: operator (Round 1/2 question round)

<!-- fr:journal kind=decision scope=spec id=stale-days created=2026-10-11T17:23:03+00:00 -->
### stale-days · decision · Stale in-progress plan: 14 days, configurable

No commit on plan dir or run branch and no PR activity for 14 days; `stale_days` in .fr/debt.yaml or --stale-days.

decider: operator (Round 1/2 question round)

<!-- fr:journal kind=decision scope=spec id=archive-pr created=2026-10-11T17:23:03+00:00 -->
### archive-pr · decision · Weekly job opens/refreshes one draft archive PR, all forges

Fixed branch chore/debt-archive-sweep; never marked ready or merged by the bot. Only plans merged longer than stale_days ago, so a just-merged plan's own close-out is not pre-empted (#660/#664).

decider: operator (Round 1/2 question round)

<!-- fr:journal kind=decision scope=spec id=panel-source created=2026-10-11T17:23:03+00:00 -->
### panel-source · decision · Triage Debt panel reads JSON embedded in the issue body

collect stays forge-only; one engine, no re-derivation; trend from triage snapshots.

decider: operator (Round 1/2 question round)

<!-- fr:journal kind=decision scope=spec id=owed-kind created=2026-10-11T17:23:03+00:00 -->
### owed-kind · decision · New `owed` journal kind

Journal stamp 1 → 2 with migration + validator; an open owed entry never fails `fr journal check` (the finding+token alternative would fail closed on older fr).

decider: operator (Round 1/2 question round)

<!-- fr:journal kind=decision scope=spec id=owed-label created=2026-10-11T17:23:03+00:00 -->
### owed-label · decision · New `fr:owed` label

Sibling of fr:awaiting-live, with its own never-ranked triage set.

decider: operator (Round 1/2 question round)

<!-- fr:journal kind=decision scope=spec id=verification created=2026-10-11T17:23:03+00:00 -->
### verification · decision · Verification: candidate + live rows

Run strategy candidate; the weekly issue rename and the CI archive PR rows are `live`.

decider: operator (Round 1/2 question round)

<!-- fr:journal kind=decision scope=spec id=pr-token created=2026-10-11T17:23:03+00:00 -->
### pr-token · decision · Archive PR token: optional FR_DEBT_TOKEN, fallback to the workflow token

With the fallback the PR body says CI will not run until a push (GitHub does not run workflows on PRs opened with GITHUB_TOKEN).

decider: operator (Round 1/2 question round)

<!-- fr:journal kind=decision scope=spec id=owed-always-filed created=2026-10-11T17:23:03+00:00 -->
### owed-always-filed · decision · Owed entries are always filed at archive

Independent of --issues/--no-issues; skipped only under tracking: none.

decider: operator (Round 1/2 question round)

<!-- fr:journal kind=decision scope=spec id=outcome-verb created=2026-10-11T17:23:03+00:00 -->
### outcome-verb · decision · `fr closeout outcome` records Test Plan step outcomes

--ran --evidence | --owed --why | --na --reason, step ranges; writes spec-journal entries test-plan-step-<n>; `fr archive --branch` holds until every step has one.

decider: operator (Round 1/2 question round)

<!-- fr:journal kind=decision scope=spec id=gate-reach created=2026-10-11T17:23:03+00:00 -->
### gate-reach · decision · The archive hold applies to every close-out

Older Test Plans with unit-test bullets take one ranged `--na --reason 'in CI'` command.

decider: operator (Round 1/2 question round)

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-10-11T17:23:44+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: design-risk. Round 1's archive-PR, owed-kind and scope answers left four code-level gaps (GITHUB_TOKEN PRs run no CI; --no-issues opt-out; no structured outcome record; legacy Test Plan bullets) checked against the code before round 2.
