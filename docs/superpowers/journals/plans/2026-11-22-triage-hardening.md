<!-- fr:journal-schema=4 -->
# Journal: 2026-11-22-triage-hardening

<!-- fr:journal kind=decision scope=plan id=p1-admit-marker-json created=2026-11-22T22:40:36+00:00 phase=1 -->
### p1-admit-marker-json · decision · parse_admit does not share a JSON-in-comment helper with the claim marker (phase 1)

claims.parse_marker parses its JSON inline (prefix, suffix, pydantic model, MarkerError), and no shared helper exists to reuse. parse_admit reuses claims._created for ordering and claims.trusted_author for trust instead (P1.T2.S3).

<!-- fr:journal kind=decision scope=plan id=p1-admit-module created=2026-11-22T22:40:36+00:00 phase=1 -->
### p1-admit-module · decision · fr triage admit lives in commands/triage_admit_cmd.py, registered on triage_app (phase 1)

The plan named commands/triage_cmd.py; the verb is in its own module, imported at the end of triage_cmd.py like the other triage subcommand modules, so triage_cmd.py does not grow. The CLI path is still `fr triage admit`.

<!-- fr:journal kind=discovery scope=plan id=p1-docs-merge-protection created=2026-11-22T22:40:36+00:00 phase=1 -->
### p1-docs-merge-protection · discovery · docs/merge-protection.md covers intake.py and described the label-only admission (phase 1)

Its Issue intake section now describes the admit marker, withheld titles and the confirmed digest. The ready-fr label description (fr.labels) now names fr triage admit, which made docs/reference/dispatch-lifecycle.md stale; its stamp was bumped. Two older acceptance rows (intake-trust-eligibility, intake-batch-refuses-untrusted) named renamed tests and were amended in this feature's fragment.

<!-- fr:journal kind=finding scope=plan id=p1-sec-claim-advice created=2026-11-22T22:40:36+00:00 phase=1 state=fixed review_scope=in -->
### p1-sec-claim-advice · finding [fixed] (reviewer: in scope) · check's ignored-claims line told the operator to add any commenter to pr_authors (phase 1)

Anyone can post a claim-shaped marker, and pr_authors also grants intake trust. The line now reads `<key>  <login>: claim marker ignored (not a trusted login or member). If <login> is one of your driving accounts, add it to pr_authors in <repo>'s .fr/triage.yaml (this also admits its issues to batches); otherwise ignore it.` The check test pins it, and the skill says the same.

<!-- fr:journal kind=finding scope=plan id=p1-sec-admit-toctou created=2026-11-22T22:40:36+00:00 phase=1 state=fixed review_scope=in -->
### p1-sec-admit-toctou · finding [fixed] (reviewer: in scope) · fr triage admit could pin text the author edited after the operator read it (phase 1)

Per amended R2 the preview quotes the title and body as untrusted text (batch_dispatch.quote_untrusted) and prints the digest; --yes needs --digest and re-reads the issue just before writing, refusing (exit 2, nothing written, current digest printed) on a missing or different digest. Tests: --yes without --digest, a wrong digest, an edit between preview and write, and the matching digest writing. They were written after the change and then proven red against the previous command (5 failed).

<!-- fr:journal kind=finding scope=plan id=p1-sec-admit-escapes created=2026-11-22T22:40:36+00:00 phase=1 state=fixed review_scope=in -->
### p1-sec-admit-escapes · finding [fixed] (reviewer: in scope) · the admit preview printed hidden characters that could hide what the operator admits (phase 1)

quote_untrusted did not neutralise them. A new pure helper, fr.triage.batch_dispatch.visible, beside quote_untrusted, replaces with a visible escape (backslash-x or backslash-u hex) every character whose unicodedata category is Cc, Cf, Co, Cn, Zl or Zp (newline and tab kept), plus the variation selectors (U+FE00-FE0F, U+E0100-E01EF) and the Hangul fillers (U+115F, U+1160, U+3164, U+FFA0). A first denylist regex missed tag characters, U+2060, U+200E and variation selectors (a follow-up review), so the rule is by category; letters, CJK and emoji bases stay unescaped (test_visible_keeps_letters_cjk_and_emoji_bases). The admit preview applies it to the title and body lines only and prints one warning when anything was escaped; the digest stays over the raw text. Tests: test_the_preview_shows_hidden_characters_as_visible_escapes and test_visible_keeps_newlines_and_tabs_and_escapes_the_rest (red first, 2 failed).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-22T22:40:36+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

smoke run and a one-file change fragment: no code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-22T22:40:36+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the check output shares one _withheld_line helper and the pages one issue_title helper, written in GREEN; nothing left duplicated

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-22T22:40:36+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

docs, skill prose, generated mirrors and acceptance rows only: no code to clean

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-22T22:52:46+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · StaleInProgress titles (closed fr:in-progress/fr:claimed issues) skip intake withholding and reach facts, check, clean-labels and the Backlog page (phase 1)

collect.py _closed_in_progress stored the raw title; an outside author's edited title reached check (triage_cmd.py:830), clean-labels and render.py's closed-in-progress group.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-22T22:52:46+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · ignored_claims built from every comment_facts entry, including a repo skipped mid-loop (phase 1)

comment_facts was filled per issue inside the per-repo try; a later claim-read failure skipped the repo but left its entries.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-22T22:52:46+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · No test covers admission on the viewed (judged, no longer open) path (phase 1)

Matching marker admits, failed admit read stays local, ineligible viewed title blanked: untested.

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-11-22T22:52:46+00:00 phase=1 -->
### p1-review · review · Phase 1 review: 3 findings, all in scope, all fixed (phase 1)

Dispatched reviewer (separate context) reviewed R1-R5, R7 against spec and plan: digest over the untruncated body, fail-closed ready-fr path, shared comment read, admit --digest re-read, visible() by category, conditional pr_authors advice all verified. Raised p1-r1..p1-r3, fixed in c2e91280c. Notes not raised as findings: the glab/tea admit refusal is defence in depth (triage is GitHub-only); an authorless claim marker prints 'unknown author' (cosmetic).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-22T22:52:46+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: StaleInProgress titles (closed fr:in-progress/fr:claimed issues) skip intake withholding and reach facts, check, clean-labels and the Backlog page (phase 1)

c2e91280c: a stale entry keeps its title only when a trusted login wrote it (the closed list reads no association; fail closed); check, clean-labels and the page show key/URL and 'title withheld'. Test test_a_stale_in_progress_entry_by_an_outside_author_keeps_no_title, red before the fix.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-22T22:52:46+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: ignored_claims built from every comment_facts entry, including a repo skipped mid-loop (phase 1)

c2e91280c: per-repo comment facts merge only after the repo succeeds. Test test_a_repo_skipped_mid_loop_leaves_no_ignored_claims, red before the fix.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-22T22:52:46+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: No test covers admission on the viewed (judged, no longer open) path (phase 1)

c2e91280c: three viewed-path tests (admitted with matching marker; failed admit read local; ineligible viewed title blanked).

<!-- fr:journal kind=discovery scope=plan id=p2-sets-batch-cycle created=2026-11-23T00:10:17+00:00 phase=2 -->
### p2-sets-batch-cycle · discovery · batch.py cannot use triage/sets.py (import cycle), so its awaiting-live test stays (phase 2)

sets -> intake -> claims -> batch, so batch._all_closed keeps its own FR_AWAITING_LIVE label test (closed OR labelled, not the open-only is_awaiting_live), and batch_drive.awaiting_unlabelled is the inverse predicate (open and NOT labelled) with a lazy import. Every other copy now reads sets.py (check re-exports; views and render import it directly).

<!-- fr:journal kind=discovery scope=plan id=p2-obsolete-hold-narrowed created=2026-11-23T00:10:17+00:00 phase=2 -->
### p2-obsolete-hold-narrowed · discovery · obsolete takes over the awaiting-live hold for batches whose members are all in facts (phase 2)

A never-dispatched batch whose open members all await live and the rest are closed is now obsolete, so AWAITING_LIVE_HOLD only fires when a member is missing from facts. test_triage_awaiting_live's b-live batch gained a member absent from facts to keep exercising the hold, and a new test pins the obsolete precedence. Also extended beyond the spec's list: claims.releasing, the held-by skip, kanban's new Obsolete column and the card's already-closed line, the render batches_by_key and the pill CSS treat obsolete like cancelled.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-11-23T00:10:17+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

check, render and the board share one derive_batch_stage and stale_members helper written in GREEN; nothing left duplicated

<!-- fr:journal kind=review scope=plan id=p2-review created=2026-11-23T00:16:17+00:00 phase=2 -->
### p2-review · review · Phase 2 review: no blocking bug; four in-scope findings, one spec sentence (phase 2)

Separate reviewer (read-only) over 795a43043..4aa4fca42 against R6, R8-R10. Confirmed: a
dispatched batch never derives obsolete; a member missing from facts keeps it proposed;
every stage reader handles obsolete. Findings p2-r1..p2-r5 below; each verified against the code.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-23T00:16:17+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · kanban: obsolete is not a terminal stage, so an all-obsolete wave is never hidden by the cutoff (phase 2)

kanban.py _TERMINAL_STAGES / Card.terminal omit obsolete while finished_waves counts it finished.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-23T00:16:17+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · kanban: an Obsolete-column card falls through to the 'finished' hint (phase 2)

fallback_hint had no obsolete branch; the card read "finished" with no pointer to batch cancel.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-23T00:16:17+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · batch._all_closed's awaiting-live test duplicates sets.is_awaiting_live with no test pinning them (phase 2)

The import cycle keeps the copy; nothing failed if the two drifted.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-23T00:16:17+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · claims.releasing / owed_claims treating obsolete like cancelled had no test (phase 2)

Dropping "obsolete" from releasing left the suite green.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-23T00:16:17+00:00 phase=2 state=open review_scope=out -->
### p2-r5 · finding [open] (reviewer: out of scope) · Spec §E says the awaiting-live hold still applies to a batch with a lifecycle event; the code never reaches it (phase 2)

The drive only dispatches stage proposed, and any batch with a lifecycle event derives another stage.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-23T00:16:17+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: kanban: obsolete is not a terminal stage, so an all-obsolete wave is never hidden by the cutoff (phase 2)

Kept obsolete non-terminal on purpose: R9 wants the operator to see it and run batch cancel, and a
cutoff would hide exactly that card. Card.terminal's docstring now says so, and
test_an_obsolete_card_points_at_batch_cancel_and_is_never_cut_off pins that an obsolete wave
card is never cut off a year later.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-23T00:16:17+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: kanban: an Obsolete-column card falls through to the 'finished' hint (phase 2)

New HINT_OBSOLETE ("obsolete: every member closed, retire it with batch cancel") for the
obsolete column; the same test fails without it.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-23T00:16:17+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: batch._all_closed's awaiting-live test duplicates sets.is_awaiting_live with no test pinning them (phase 2)

test_all_closed_agrees_with_the_set_apart_awaiting_live_predicate checks _all_closed against "closed or sets.is_awaiting_live" over five issue shapes.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-23T00:16:17+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: claims.releasing / owed_claims treating obsolete like cancelled had no test (phase 2)

test_an_obsolete_wave_batch_releases_its_claims pins releasing() and owed_claims() for an obsolete wave batch against a proposed one.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-23T00:16:17+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: Spec §E says the awaiting-live hold still applies to a batch with a lifecycle event; the code never reaches it (phase 2)

The spec sentence now says the hold applies to a never-dispatched batch with a member missing from the facts, and why a batch with a lifecycle event needs none.

<!-- fr:journal kind=decision scope=plan id=p3-snapshot-pr-keys created=2026-11-23T00:51:53+00:00 phase=3 -->
### p3-snapshot-pr-keys · decision · key_repos resolves OWNER/REPO#n keys (snapshot PR keys) as the repo named in full (phase 3)

A snapshot's prs map is keyed owner/repo#n while issues use name#n. key_repos now maps a slash name to the scope member of that name (else the name itself), so the visibility read targets the right repo. Debt repos enter guard_state as their own repo names under a synthetic key.

<!-- fr:journal kind=discovery scope=plan id=p3-previous-for-carry created=2026-11-23T00:51:53+00:00 phase=3 -->
### p3-previous-for-carry · discovery · the finished judged-PR carry reads previous facts on full collects too (phase 3)

collect_facts_counted already receives previous on every collect (only is None means no partial); the carry map of CLOSED/MERGED judged_prs is built from it once before the judged loop, independent of keep.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-23T00:51:53+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

snapshot reading and key extraction were written once in GREEN (strict_snapshots); nothing duplicated

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-11-23T00:51:53+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

a one-line guard in a constant script; nothing to clean

<!-- fr:journal kind=review scope=plan id=p3-review created=2026-11-23T00:56:56+00:00 phase=3 -->
### p3-review · review · Phase 3 review: no blocking defect; four in-scope findings, one out (phase 3)

Separate reviewer (read-only) over 3cf55f53c..682755ad4 against R11-R13. Confirmed: an OPEN
judged PR is re-viewed, never carried; no PR is viewed in a skipped repo; a failed view_pr is
recorded unviewed; an unreadable snapshot raises, a missing snapshots dir reads empty; the
key_repos full-name path and the debt key never fail open. Each finding verified against the code.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-23T00:56:56+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · A debt-only privacy refusal reads '<repo>#debt is an issue of <repo>' (phase 3)

privacy.refusal worded the synthetic debt key as an issue that does not exist.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-23T00:56:56+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · The R13 test only string-checks the guard and never runs the script (phase 3)

A guard that no longer returns early, or a DOM read moved above it, would stay green.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-23T00:56:56+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · Thin R12 tests: no out-of-scope full PR key, no missing snapshots dir (phase 3)

The member-repo PR key is already covered (the existing PR test uses a member repo). Missing:
a full key of a repo outside the scope, and a state dir with no snapshots/. A malformed debt key
reaches client_for, which is the pre-existing path for every repo and still refuses.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-11-23T00:56:56+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · CollectStats.viewed counts a past-limit PR once though it costs two single reads (phase 3)

The stat is documented as what a collect cost in single reads; view_pr was not counted.

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-11-23T00:56:56+00:00 phase=3 state=open review_scope=out -->
### p3-r5 · finding [open] (reviewer: out of scope) · A carried CLOSED judged PR that is later reopened stays carried as closed (phase 3)

The same holds for carried closed issues before this change; the spec chose the carry.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-23T00:56:56+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: A debt-only privacy refusal reads '<repo>#debt is an issue of <repo>' (phase 3)

privacy.DEBT_KEY_SUFFIX names the synthetic key, and refusal() words it as "a carried snapshot
holds debt figures of <repo>". test_a_debt_only_leak_is_worded_as_debt_not_as_an_issue.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-23T00:56:56+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: The R13 test only string-checks the guard and never runs the script (phase 3)

test_the_issues_filter_script_runs_without_throwing_when_the_filter_bar_is_absent runs SCRIPT
under node against a document whose every other DOM read throws; it fails with the guard
removed. Skipped where node is absent (GitHub's runners have it).

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-23T00:56:56+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: Thin R12 tests: no out-of-scope full PR key, no missing snapshots dir (phase 3)

Added test_a_snapshot_pr_key_of_a_repo_outside_the_scope_is_read_not_skipped and
test_no_snapshots_directory_adds_no_key_and_no_repo. The malformed debt key keeps the old
client_for path, which refuses (not fail-open).

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-11-23T00:56:56+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: CollectStats.viewed counts a past-limit PR once though it costs two single reads (phase 3)

collect now counts the view_pr read too; the CollectStats docstring and the count test say three reads.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-11-23T00:56:56+00:00 phase=3 state=open resolves=p3-r5 out_of_scope=true -->
### p3-r5-resolved · finding [out-of-scope] · resolves p3-r5: A carried CLOSED judged PR that is later reopened stays carried as closed (phase 3)

Not caused by this change; a carried closed issue already behaved this way, and R11 asks for the carry.

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-23T01:22:03+00:00 -->
### lens-review-1 · review · Lens review: docs-accuracy, security and tests over the whole feature diff

Three separate read-only reviewers, one per lens, over 0bca17ec3..031bc27b8. docs-accuracy: 2
findings; security: 4 in, 3 out; tests: 7 in. Each verified against the code before fixing;
fixes in 031bc27b8 and f3a179dea..1e93a0598.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-23T01:22:03+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · labels.py READY_FR comment still said 'Never applied by fr'; fr triage admit applies it

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2 created=2026-11-23T01:22:03+00:00 state=open review_scope=in -->
### l-docs-accuracy-r2 · finding [open] (reviewer: in scope) · fr-triage explainer's check list omitted ignored claims, obsolete batches and stale members

<!-- fr:journal kind=finding scope=plan id=l-security-r1 created=2026-11-23T01:22:03+00:00 state=open review_scope=in -->
### l-security-r1 · finding [open] (reviewer: in scope) · fr triage admit hardcoded github.com: the glab/tea refusal never fired and a same-named github.com repo was read and written

<!-- fr:journal kind=finding scope=plan id=l-security-r2 created=2026-11-23T01:22:03+00:00 state=open review_scope=in -->
### l-security-r2 · finding [open] (reviewer: in scope) · admission was checked only at collect; batch dispatch judged stored or carried facts, so an edit since the last collect dispatched

<!-- fr:journal kind=finding scope=plan id=l-security-r3 created=2026-11-23T01:22:03+00:00 state=open review_scope=in -->
### l-security-r3 · finding [open] (reviewer: in scope) · privacy guard parsed only top-level snapshots/*.json while the state ref carries all of snapshots/

<!-- fr:journal kind=finding scope=plan id=l-security-r4 created=2026-11-23T01:22:03+00:00 state=open review_scope=in -->
### l-security-r4 · finding [open] (reviewer: in scope) · an outside author closing all their admitted members makes a batch obsolete, which meets after-dependencies

<!-- fr:journal kind=finding scope=plan id=l-security-r5 created=2026-11-23T01:22:03+00:00 state=open review_scope=out -->
### l-security-r5 · finding [open] (reviewer: out of scope) · outside-author PR titles are never withheld (prs, gated_prs, batch_prs, judged_prs)

<!-- fr:journal kind=finding scope=plan id=l-security-r6 created=2026-11-23T01:22:03+00:00 state=open review_scope=out -->
### l-security-r6 · finding [open] (reviewer: out of scope) · the admit digest pins title and body only; later outsider comments reach a worker reading the thread

<!-- fr:journal kind=finding scope=plan id=l-security-r7 created=2026-11-23T01:22:03+00:00 state=open review_scope=out -->
### l-security-r7 · finding [open] (reviewer: out of scope) · the privacy guard ignores other state-ref entries (merge-stops.json, history/, issues/, requests/sessions yaml)

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-23T01:22:03+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · privacy snapshot tests asserted only refusals; an over-refusing guard stayed green

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-23T01:22:03+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · obsolete cancel with a wave and claims, the drive's held exclusion and its wave finish were untested

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-23T01:22:03+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · no test that dispatch/adopt refuses an obsolete batch; its refusal text spoke of a prior dispatch

<!-- fr:journal kind=finding scope=plan id=l-tests-r4 created=2026-11-23T01:22:03+00:00 state=open review_scope=in -->
### l-tests-r4 · finding [open] (reviewer: in scope) · the Issues page's obsolete exclusion from batch tags was untested

<!-- fr:journal kind=finding scope=plan id=l-tests-r5 created=2026-11-23T01:22:03+00:00 state=open review_scope=in -->
### l-tests-r5 · finding [open] (reviewer: in scope) · malformed admit-marker cases all failed the digest regex, so the version/extra-key checks were not isolated

<!-- fr:journal kind=finding scope=plan id=l-tests-r6 created=2026-11-23T01:22:03+00:00 state=open review_scope=in -->
### l-tests-r6 · finding [open] (reviewer: in scope) · admit failure paths untested; a label-then-comment failure said 'admission not written'

<!-- fr:journal kind=finding scope=plan id=l-tests-r7 created=2026-11-23T01:22:03+00:00 state=open review_scope=in -->
### l-tests-r7 · finding [open] (reviewer: in scope) · the executing filter-script test was skipped wherever node was missing, CI included

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-23T01:22:03+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: labels.py READY_FR comment still said 'Never applied by fr'; fr triage admit applies it

031bc27b8: the comment says fr applies it only through fr triage admit --yes, with a trusted fr-admit marker.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2-resolved created=2026-11-23T01:22:03+00:00 state=fixed resolves=l-docs-accuracy-r2 -->
### l-docs-accuracy-r2-resolved · finding [fixed] · resolves l-docs-accuracy-r2: fr-triage explainer's check list omitted ignored claims, obsolete batches and stale members

031bc27b8: the list gains the three sets, the cancel command and the pr_authors caution; reviewed stamp names it.

<!-- fr:journal kind=finding scope=plan id=l-security-r1-resolved created=2026-11-23T01:22:03+00:00 state=fixed resolves=l-security-r1 -->
### l-security-r1-resolved · finding [fixed] · resolves l-security-r1: fr triage admit hardcoded github.com: the glab/tea refusal never fired and a same-named github.com repo was read and written

f3a179dea: admit takes an issue URL (its host; GitLab's /-/issues/ path keeps the GitLab adapter, which
refuses before any read) or --host; a URL that disagrees with --host refuses; the preview prints the
host. A bare owner/repo#n still means github.com, the convention _host_of and collect already follow,
and the preview now says so. Tests test_admit_on_a_gitlab_host_refuses_before_any_read and four more.

<!-- fr:journal kind=finding scope=plan id=l-security-r2-resolved created=2026-11-23T01:22:03+00:00 state=fixed resolves=l-security-r2 -->
### l-security-r2-resolved · finding [fixed] · resolves l-security-r2: admission was checked only at collect; batch dispatch judged stored or carried facts, so an edit since the last collect dispatched

41ca88d6f: fr/triage/admit_recheck.recheck_admitted re-reads each member admitted by its marker alone and
recomputes the digest in dispatch_batch, after the stage gate and before any forge write or event (the
driver dispatches through it). A mismatch or a failed read refuses. Spec R2 and §B amended.
test_dispatch_yes_refuses_an_admitted_member_edited_or_unreadable_since_collect fails with the call removed.

<!-- fr:journal kind=finding scope=plan id=l-security-r3-resolved created=2026-11-23T01:22:03+00:00 state=fixed resolves=l-security-r3 -->
### l-security-r3-resolved · finding [fixed] · resolves l-security-r3: privacy guard parsed only top-level snapshots/*.json while the state ref carries all of snapshots/

5bb13b9f1: strict_snapshots refuses any snapshots/ entry that is not a top-level .json file; test_a_snapshots_entry_the_strict_reader_does_not_parse_refuses[json.bak|old/a.json].

<!-- fr:journal kind=finding scope=plan id=l-security-r4-resolved created=2026-11-23T01:22:03+00:00 state=refuted resolves=l-security-r4 -->
### l-security-r4-resolved · finding [refuted] · resolves l-security-r4: an outside author closing all their admitted members makes a batch obsolete, which meets after-dependencies

The operator's recorded round-1 decision (d-obsolete-stage) is that an obsolete batch meets its
dependencies. A batch whose members are all closed has no work left to wait for: the dependent batch's
ordering is about that work, and fr triage check lists every obsolete batch for the operator.

<!-- fr:journal kind=finding scope=plan id=l-security-r5-resolved created=2026-11-23T01:22:03+00:00 state=open resolves=l-security-r5 out_of_scope=true -->
### l-security-r5-resolved · finding [out-of-scope] · resolves l-security-r5: outside-author PR titles are never withheld (prs, gated_prs, batch_prs, judged_prs)

PR titles were never withheld before this change; the intake trust boundary this spec moves is issues'. Needs its own design.

<!-- fr:journal kind=finding scope=plan id=l-security-r6-resolved created=2026-11-23T01:22:03+00:00 state=open resolves=l-security-r6 out_of_scope=true -->
### l-security-r6-resolved · finding [out-of-scope] · resolves l-security-r6: the admit digest pins title and body only; later outsider comments reach a worker reading the thread

Comments were never pinned; the spec pins the issue's content (title and body) by decision. A separate design question.

<!-- fr:journal kind=finding scope=plan id=l-security-r7-resolved created=2026-11-23T01:22:03+00:00 state=open resolves=l-security-r7 out_of_scope=true -->
### l-security-r7-resolved · finding [out-of-scope] · resolves l-security-r7: the privacy guard ignores other state-ref entries (merge-stops.json, history/, issues/, requests/sessions yaml)

Those ref entries were unchecked before this change; R12 named snapshots only.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-23T01:22:03+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: privacy snapshot tests asserted only refusals; an over-refusing guard stayed green

5bb13b9f1: test_a_snapshot_naming_only_public_repos_passes_a_public_state_repo and test_a_private_state_repo_passes_a_snapshot_naming_private_repos.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-23T01:22:03+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: obsolete cancel with a wave and claims, the drive's held exclusion and its wave finish were untested

b2182e1e9: test_cancelling_an_obsolete_waved_batch_releases_its_written_claims, test_a_foreign_held_obsolete_batch_emits_no_held_action (with a proposed control), test_a_wave_of_an_obsolete_and_a_cancelled_batch_reports_its_duplicates_once_finished.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-23T01:22:03+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: no test that dispatch/adopt refuses an obsolete batch; its refusal text spoke of a prior dispatch

c0a318308: batch_dispatch.obsolete_refusal for dispatch and adopt names the cancel command; two tests pin it.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4-resolved created=2026-11-23T01:22:03+00:00 state=fixed resolves=l-tests-r4 -->
### l-tests-r4-resolved · finding [fixed] · resolves l-tests-r4: the Issues page's obsolete exclusion from batch tags was untested

b4b04955c: test_a_member_of_an_obsolete_batch_is_not_tagged_in_batch, with a proposed control.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5-resolved created=2026-11-23T01:22:03+00:00 state=fixed resolves=l-tests-r5 -->
### l-tests-r5-resolved · finding [fixed] · resolves l-tests-r5: malformed admit-marker cases all failed the digest regex, so the version/extra-key checks were not isolated

f98d35bfa: each malformed case fails for one reason (valid 64-hex elsewhere), plus upper-case, extra-key and length cases and test_latest_admit_skips_a_marker_with_no_created_at.

<!-- fr:journal kind=finding scope=plan id=l-tests-r6-resolved created=2026-11-23T01:22:03+00:00 state=fixed resolves=l-tests-r6 -->
### l-tests-r6-resolved · finding [fixed] · resolves l-tests-r6: admit failure paths untested; a label-then-comment failure said 'admission not written'

6fda19416: a failed read exits 2 writing nothing; a comment failure after the label exits 1 saying the label is on, the issue is not admitted, and the exact re-run.

<!-- fr:journal kind=finding scope=plan id=l-tests-r7-resolved created=2026-11-23T01:22:03+00:00 state=fixed resolves=l-tests-r7 -->
### l-tests-r7-resolved · finding [fixed] · resolves l-tests-r7: the executing filter-script test was skipped wherever node was missing, CI included

e4a318589: skipped only when node is missing and CI is unset; with CI=1 and no node it fails.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved-2 created=2026-11-23T01:23:36+00:00 phase=3 state=open resolves=p3-r5 tracked_by=https://github.com/derio-net/super-fr/issues/1631 -->
### p3-r5-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1631] · resolves p3-r5: A carried CLOSED judged PR that is later reopened stays carried as closed (phase 3)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1631.

<!-- fr:journal kind=finding scope=plan id=l-security-r5-resolved-2 created=2026-11-23T01:23:36+00:00 state=open resolves=l-security-r5 tracked_by=https://github.com/derio-net/super-fr/issues/1632 -->
### l-security-r5-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1632] · resolves l-security-r5: outside-author PR titles are never withheld (prs, gated_prs, batch_prs, judged_prs)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1632.

<!-- fr:journal kind=finding scope=plan id=l-security-r6-resolved-2 created=2026-11-23T01:23:36+00:00 state=open resolves=l-security-r6 tracked_by=https://github.com/derio-net/super-fr/issues/1633 -->
### l-security-r6-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1633] · resolves l-security-r6: the admit digest pins title and body only; later outsider comments reach a worker reading the thread

Filed at deliver as https://github.com/derio-net/super-fr/issues/1633.

<!-- fr:journal kind=finding scope=plan id=l-security-r7-resolved-2 created=2026-11-23T01:23:36+00:00 state=open resolves=l-security-r7 tracked_by=https://github.com/derio-net/super-fr/issues/1634 -->
### l-security-r7-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1634] · resolves l-security-r7: the privacy guard ignores other state-ref entries (merge-stops.json, history/, issues/, requests/sessions yaml)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1634.
