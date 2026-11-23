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
