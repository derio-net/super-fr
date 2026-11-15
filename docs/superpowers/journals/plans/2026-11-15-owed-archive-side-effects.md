<!-- fr:journal-schema=4 -->
# Journal: 2026-11-15-owed-archive-side-effects

<!-- fr:journal kind=discovery scope=plan id=p1-closeout-owed-fake-gh created=2026-11-15T19:41:29+00:00 phase=1 -->
### p1-closeout-owed-fake-gh · discovery · tests/scenarios/closeout-owed's recording gh needed an `issue view` answer (phase 1)

Closing an owed issue now reads the one issue (R14), so the existing closeout-owed
scenario's fake gh gained `gh issue view` (record with author and state). Without it
the scenario's discharge step failed on an unexpected call.

<!-- fr:journal kind=discovery scope=plan id=p1-existing-manual-owed-test-contradicted-r7 created=2026-11-15T19:41:29+00:00 phase=1 -->
### p1-existing-manual-owed-test-contradicted-r7 · discovery · a held single-plan archive used to record and file its manual-phase owed entry (phase 1)

test_archive_owed's manual-phase test pinned the behaviour R7 removes (single-plan
refusal wrote and filed owed). It now covers `--all` off the default branch (records and
files), a single-plan refusal (writes nothing) and the default-branch hold (prints
`would record owed`). The --branch hold shares _write_manual_owed, so it is covered by
the same default-branch check.

<!-- fr:journal kind=discovery scope=plan id=p1-followups-test-pinned-old-contract created=2026-11-15T19:41:29+00:00 phase=1 -->
### p1-followups-test-pinned-old-contract · discovery · test_archive_followups pinned follow-ups running after a refused follower move (phase 1)

R7 says a refusal runs no follow-up, so that test now asserts no follow-up and that the
staged plan move was undone. The first CI run also showed two unrelated concurrency
tests (tests/unit/test_hooks_worktree.py) failing on a loaded shard; they pass here.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-15T19:41:29+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

the helper moved verbatim into fr.git; docs.load keeps a thin wrapper, nothing else to tidy

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-15T19:41:29+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

the lookup result type was introduced in this task and is already minimal

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-15T19:41:29+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

a one-call swap of the listing for view_issue_record; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-15T19:41:29+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

scenario scripts share one sourced world builder (_owed_world.sh) from the start

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-15T20:21:10+00:00 phase=1 -->
### review-p1 · review · Phase 1 code review (R7-R9, R12-R14, fr.git helper): 4 in scope, 2 out (phase 1)

Independent reviewer read the post-change files for diff 3b8e06ddb..a46fbfa52 against spec R7-R9 and R12-R14.
Found sound: label-filtered owed lookup failing closed (R12), UnsupportedForgeOperation keeping owed in the journal (R13),
close by number with OPEN and ownership checks (R14), the fr.git helper move, and both scenario fixtures.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-15T20:21:10+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · R7 undo covers only ArchiveError inside archive_plan_dir; a later failure (sweep, repair) or an OSError in the move leaves the plan move staged (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-15T20:21:10+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · No test for R8 preview or R9 recording on the --branch hold path (_archive_branch_plan) (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-15T20:21:10+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · Refusal-runs-no-follow-up spied only for Exit(2); the exception path has a loose assertion over an empty log (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-15T20:21:10+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · _owed_step's could-not-file warning lacks soft_wrap, so Rich can split the phrase the scenario greps (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-15T20:21:10+00:00 phase=1 state=open review_scope=out -->
### p1-r5 · finding [open] (reviewer: out of scope) · head_on_default_branch treats an unreadable default ref as off-default; GitUnavailableError from it is uncaught in _write_manual_owed (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-15T20:21:10+00:00 phase=1 state=open review_scope=out -->
### p1-r6 · finding [open] (reviewer: out of scope) · _forge_lists_issues keys on detect_backend()=='github' rather than the adapter's own capability (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-15T20:21:10+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: R7 undo covers only ArchiveError inside archive_plan_dir; a later failure (sweep, repair) or an OSError in the move leaves the plan move staged (phase 1)

6ef3b862f + 7f0861b71: undoing_staged_moves wraps the whole single-plan span from _with_followups; archive_plan_dir undoes on BaseException. Tests inject failures at _report_sweep, spec_archive_sweep, _repair_in_passing and an OSError in _archive_run, asserting byte-identical status and index; all failed before the fix.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-15T20:21:10+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: No test for R8 preview or R9 recording on the --branch hold path (_archive_branch_plan) (phase 1)

a97bd8d94: two --branch tests in test_archive_owed.py — default branch prints 'would record owed' with tree and index unchanged; off default the owed entry is recorded.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-15T20:21:10+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: Refusal-runs-no-follow-up spied only for Exit(2); the exception path has a loose assertion over an empty log (phase 1)

6ef3b862f: parametrized spy test (RuntimeError, SettingsError) asserts _after_moves never runs and the tree is unchanged; test_a_placement_refusal_writes_nothing now asserts exit_code == 2 and 'Nothing was written'.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-15T20:21:10+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: _owed_step's could-not-file warning lacks soft_wrap, so Rich can split the phrase the scenario greps (phase 1)

6ef3b862f: soft_wrap=True on the could-not-file-owed print.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-15T20:21:10+00:00 phase=1 state=open resolves=p1-r5 out_of_scope=true -->
### p1-r5-resolved · finding [out-of-scope] · resolves p1-r5: head_on_default_branch treats an unreadable default ref as off-default; GitUnavailableError from it is uncaught in _write_manual_owed (phase 1)

Spec R3 deliberately counts an unreadable default ref as off the default branch; the uncaught GitUnavailableError path predates this change (git absent fails every archive command).

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-15T20:21:10+00:00 phase=1 state=open resolves=p1-r6 out_of_scope=true -->
### p1-r6-resolved · finding [out-of-scope] · resolves p1-r6: _forge_lists_issues keys on detect_backend()=='github' rather than the adapter's own capability (phase 1)

_forge_lists_issues predates this change; R13 states GitHub-only listing today, and the backend-vs-adapter duplication is not introduced here.

<!-- fr:journal kind=discovery scope=plan id=p2-r5-exemption-is-vacuous created=2026-11-15T21:46:47+00:00 phase=2 -->
### p2-r5-exemption-is-vacuous · discovery · R5's premature_closes exemption needs no code — its candidates are only held refs (phase 2)

premature_closes only ever flags a closing line whose ref is in its holding, narrowed
or tracking sets, so "drop a discharged ref unless it is held" changes nothing: an
unheld discharged Closes was never refused, and a held one still is (the hold wins,
R5). The R5 behaviour lives in the render (held -> `Refs <ref> — held: <reason>`, via
the new held_issues over the shared _held_sets) and in deliver's R4 check (a held ref
is not required). tests/unit/test_owed_close_at_merge.py pins both directions.

<!-- fr:journal kind=discovery scope=plan id=p2-journal-diff-not-feature-diff created=2026-11-15T21:46:47+00:00 phase=2 -->
### p2-journal-diff-not-feature-diff · discovery · the discharged set cannot use feature_diff itself — it exempts docs/superpowers/ (phase 2)

fr.proportionality.feature_diff drops fr's own artifacts (EXEMPT_PREFIXES), journals
included, so discharged_owed takes feature_merge_base (the same base) and runs its
own `git diff --name-only --diff-filter=AM` over the live and archived journal dirs.
A journal archived on the branch is compared with its copy at the default ref under
either path, so the move alone discharges nothing.

<!-- fr:journal kind=discovery scope=plan id=p2-placement-journals-not-listed created=2026-11-15T21:46:47+00:00 phase=2 -->
### p2-placement-journals-not-listed · discovery · under quiet/stealth placement the section lists nothing; resolve's printed Closes line is the route (phase 2)

Journals then live outside the product checkout (artifact_root != repo root), so the
branch's diff cannot show a discharge. discharged_owed returns [] there, as it does
with no default ref or merge-base; R2's printed line remains the operator's route.

<!-- fr:journal kind=discovery scope=plan id=p2-closeout-owed-scenario-moved created=2026-11-15T21:46:47+00:00 phase=2 -->
### p2-closeout-owed-scenario-moved · discovery · tests/scenarios/closeout-owed.sh discharged on its housekeeping branch and expected a close (phase 2)

R1 makes that resolve close nothing, so step 5 now asserts the deferred close (the
printed Closes line, no issue comment/close in the gh log). The on-main close is
covered by the new owed-close-at-merge scenario.

<!-- fr:journal kind=discovery scope=plan id=p2-fr-goal-keeps-no-resolve-example created=2026-11-15T21:46:47+00:00 phase=2 -->
### p2-fr-goal-keeps-no-resolve-example · discovery · the fr-goal skill may not carry a `fr journal resolve` example (phase 2)

tests/unit/test_skill_journal_resolve_examples.py (spec 2026-10-06 R13) refused the
first wording of the owed-close-at-merge note; it now says "discharging an owed entry
(resolving it `fixed`)" with no command example.

<!-- fr:journal kind=discovery scope=plan id=p2-debt-owed-fixture-on-main created=2026-11-15T21:46:47+00:00 phase=2 -->
### p2-debt-owed-fixture-on-main · discovery · test_debt_owed's fixture repo now has HEAD on main with an origin/main ref (phase 2)

The existing close tests ran in a repo with no default ref, which R3 now reads as off
the default branch; _repo commits once, writes refs/remotes/origin/main and keeps HEAD
on main unless a test asks for a feature branch.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-15T21:46:47+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

own_issue moved verbatim into fr.owed_refs (dropping journal_cmd's unused _SAFE_REPO); the new _close_at_merge is one branch, nothing to extract

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-15T21:46:47+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

premature_closes' hold computation was extracted into _held_sets in the GREEN step so held_issues shares it; the T3.S3 refactor then split discharged_owed

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-11-15T21:46:47+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

a shell scenario sourcing the shared _owed_world.sh builder and a skill/explainer paragraph; nothing to clean

<!-- fr:journal kind=decision scope=plan id=p2-quiet-stealth-close-now created=2026-11-15T22:06:23+00:00 phase=2 -->
### p2-quiet-stealth-close-now · decision · Under quiet/stealth placement resolve closes the owed issue at once: the discharge never travels with the PR (phase 2)

Orchestrator decision on review finding p2-r3. Under quiet and stealth the journals live in the placement's artifact root, outside the product checkout, so a discharge commit never reaches the product PR and its Closes line could never close the issue. Resolve keeps its pre-change behaviour there (close at once, same forge settings, ownership and OPEN checks); the PR body's Owed actions discharged section says Not applicable and deliver skips the R4 check. Spec R15.

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-11-15T22:42:49+00:00 phase=2 -->
### review-p2 · review · Phase 2 code review (R1-R6 close at merge): 7 in scope, 1 out (phase 2)

Independent reviewer ran git diff a42d9dc7d..1c3c167f2 against spec R1-R6 and the touched unit tests (94 passed).
Found sound: the resolve gate off the default branch (no forge client built), archived-journal discharge detection with
subtraction of resolutions already on the default ref, cross-repo filed_as dropped, the R5 premature_closes claim, and
closeout-owed step 5 as a valid negative.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-15T22:42:49+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · The render's Refs-held line reads as a closing ref when a row or decision id contains close/fix/resolve, so deliver refuses fr's own body (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-15T22:42:49+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · R4 deliver check fails open: discharged_owed returns [] on an unreadable default ref, merge-base, diff or identity (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-15T22:42:49+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · Under quiet/stealth the section is always None and unenforced while resolve claims the PR body closes it; the issue never closes (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-15T22:42:49+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · Held-issue deliver tests monkeypatch run_held_issues; the real hold -> Refs render -> both gates chain is untested (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-15T22:42:49+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · _refuse_unclosed_owed swallows every exception from run_held_issues (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-11-15T22:42:49+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · owed-close-at-merge.sh header claims more than it proves and drops the discharge-comment assertion (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-11-15T22:42:49+00:00 phase=2 state=open review_scope=in -->
### p2-r7 · finding [open] (reviewer: in scope) · 01-fr-goal.md and the fr-goal skill state the listing and refusal unconditionally (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r8 created=2026-11-15T22:42:49+00:00 phase=2 state=open review_scope=out -->
### p2-r8 · finding [open] (reviewer: out of scope) · normalize_issue_ref's _URL_REF accepts any host, so a foreign-host URL with the same path satisfies the owed closing check (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-15T22:42:49+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: The render's Refs-held line reads as a closing ref when a row or decision id contains close/fix/resolve, so deliver refuses fr's own body (phase 2)

346afa141: held ids rendered as code spans and closing_refs strips code spans before keyword matching; render -> premature_closes tests with keyword-bearing ids fail without the change.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-15T22:42:49+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: R4 deliver check fails open: discharged_owed returns [] on an unreadable default ref, merge-base, diff or identity (phase 2)

346afa141: discharged_owed raises UnreadableDischargeError naming the input; _refuse_unclosed_owed refuses by name (exit 2); the section reads Unknown. Per-input tests plus a deliver-level refusal.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-15T22:42:49+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: Under quiet/stealth the section is always None and unenforced while resolve claims the PR body closes it; the issue never closes (phase 2)

05fac35a1 + 346afa141 + e18f76dc7 + f4f13de55: spec R15 — under quiet/stealth resolve closes at once (discharge_travels); the section reads Not applicable and deliver's check stands aside. Decision p2-quiet-stealth-close-now; row owed-close-at-merge cites R15. Real quiet-repo tests.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-15T22:42:49+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: Held-issue deliver tests monkeypatch run_held_issues; the real hold -> Refs render -> both gates chain is untested (phase 2)

346afa141: two deliver tests on a real acceptance fragment (walk-owed row whose issues: names the owed issue) — render then deliver passes both gates; a hand-written Closes for it is still refused.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-15T22:42:49+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: _refuse_unclosed_owed swallows every exception from run_held_issues (phase 2)

346afa141: catches only AcceptanceError and UnreadableJournalError and refuses by name; other exceptions propagate (tested).

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-11-15T22:42:49+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: owed-close-at-merge.sh header claims more than it proves and drops the discharge-comment assertion (phase 2)

8b12ea489: header narrowed to R1-R3; the default-branch close asserts the Discharged evidence comment.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-11-15T22:42:49+00:00 phase=2 state=fixed resolves=p2-r7 -->
### p2-r7-resolved · finding [fixed] · resolves p2-r7: 01-fr-goal.md and the fr-goal skill state the listing and refusal unconditionally (phase 2)

277b78577: explainer and fr-goal skill state the this-repo filter, repo-placement-only listing, and the unreadable-input refusal; mirrors regenerated.

<!-- fr:journal kind=finding scope=plan id=p2-r8-resolved created=2026-11-15T22:42:49+00:00 phase=2 state=open resolves=p2-r8 out_of_scope=true -->
### p2-r8-resolved · finding [out-of-scope] · resolves p2-r8: normalize_issue_ref's _URL_REF accepts any host, so a foreign-host URL with the same path satisfies the owed closing check (phase 2)

normalize_issue_ref's host-agnostic URL reading predates this change (premature_closes has used it since it shipped); this change only reuses it.

<!-- fr:journal kind=decision scope=plan id=p3-dry-run-in-place-under-placement created=2026-11-15T23:24:33+00:00 phase=3 -->
### p3-dry-run-in-place-under-placement · decision · Under quiet/stealth the dry run runs in place and previews; elsewhere it runs in a scratch checkout (phase 3)

The scratch copy cannot carry a stealth marker or the placement worktree, and `_record_merged(preview=True)` is read-only by construction (`space_for(create=False)`), so those modes skip the copy. Any refused (unknown) forge call makes the exit code 1 even when the real run's code was 0.

<!-- fr:journal kind=discovery scope=plan id=p3-dry-run-prints-scratch-path-for-absolute-plan created=2026-11-15T23:24:33+00:00 phase=3 -->
### p3-dry-run-prints-scratch-path-for-absolute-plan · discovery · A plan given as an absolute path echoes the scratch path in "archived:" lines (phase 3)

The plan argument is translated into the scratch tree, so an absolute path prints as the scratch location; a relative path prints as typed. Cosmetic only.

<!-- fr:journal kind=discovery scope=plan id=p3-sync-readme-no-change created=2026-11-15T23:24:33+00:00 phase=3 -->
### p3-sync-readme-no-change · discovery · --dry-run changes no generated table (phase 3)

The README and cli.md tables list commands, not options, so sync-readme.py wrote nothing, and `fr docs check` is clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-11-15T23:24:33+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

new module written once; nothing to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-15T23:24:33+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

new module written once; nothing to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t4 created=2026-11-15T23:24:33+00:00 phase=3 -->
### no-refactor-p3-t4 · discovery · no-refactor-because P3.T4 (phase 3)

a scenario script and a registration; nothing to clean

<!-- fr:journal kind=decision scope=plan id=p3-dry-run-stale-refuses created=2026-11-15T23:50:22+00:00 phase=3 -->
### p3-dry-run-stale-refuses · decision · fr archive --dry-run over stale artifacts refuses with the gate's message, exit 2, in every context; it never migrates or commits (phase 3)

Review p3-r3. The migration gate treats `archive … --dry-run` as a context that may not write (`trigger.asks_for_dry_run`, not READ_ONLY_COMMANDS): nothing stale, the dry run proceeds; something stale, it refuses as the opt-out row does, CI included. A dry run cannot honestly preview a run that would migrate first.

<!-- fr:journal kind=decision scope=plan id=p3-dry-run-cannot-tell-refuses created=2026-11-15T23:50:23+00:00 phase=3 -->
### p3-dry-run-cannot-tell-refuses · decision · Under quiet or stealth, a dry run that cannot see what the real run would read refuses by name, exit 2, never 'nothing to archive' (phase 3)

Review p3-r5. Cases: no fr worktree yet under quiet; a stealth tracking clone that is gone, unreachable or not synced with its tracking ref. Checked by fr.placement.preview.cannot_tell before anything resolves the placement's space, in the gate and in the command. R10 amended: exit-code parity holds except where the preview refuses because it cannot tell.
