<!-- fr:journal-schema=3 -->
# Journal: 2026-11-08-sweep-fixes

<!-- fr:journal kind=discovery scope=plan id=p1-printed-commands-nothing-beyond-r3-r5 created=2026-11-08T17:50:00+00:00 phase=1 -->
### p1-printed-commands-nothing-beyond-r3-r5 · discovery · The executing test found no printed command beyond R3-R5 that fails (phase 1)

With the R3-R5 fixes in place, every `fr` command the backfill dry-run block, the refusal hints, the --yes report, `fr gate pass` (dry run, retry line, devops form, discharge lines) and the tracker bodies print runs to exit 0 with placeholders filled. Reverting the R5 line makes it fail on the discharge command (--walk needs --harness, --model, --strategy), so the test bites. `gh issue close` lines are shape-checked only (parsed with shlex, argv layout asserted); the scenario runs the link and discharge commands through the installed fr.

<!-- fr:journal kind=discovery scope=plan id=p1-shlex-quotes-the-hash created=2026-11-08T17:50:00+00:00 phase=1 -->
### p1-shlex-quotes-the-hash · discovery · tracked_rows prints the issue ref shell-quoted (phase 1)

`shlex.quote` quotes `owner/repo#n` (the `#` is special), so the printed link command is `--issue 'example-org/widgets#1'`. That is correct shell, and the test extractor reads it with shlex; the R3 unit test pins the quoted form.

<!-- fr:journal kind=discovery scope=plan id=p1-error-prefix-false-positive created=2026-11-08T17:50:00+00:00 phase=1 -->
### p1-error-prefix-false-positive · discovery · Error messages begin with "fr gate backfill:" and are not commands (phase 1)

The extractor skips a match whose verb or subcommand token ends in a colon (`fr gate backfill: spec:...`), because fr prefixes its refusals that way. Without it every refusal reads as a command.

<!-- fr:journal kind=discovery scope=plan id=p1-retry-line-exit-code created=2026-11-08T17:50:00+00:00 phase=1 -->
### p1-retry-line-exit-code · discovery · A failed tracker close still exits 0 from fr gate pass --yes (phase 1)

`fr gate pass --yes` prints "re-run `fr gate pass ... --yes` to retry the close" when a tracker close errors, but exits 0 (only the backfill path raises). The test asserts the printed retry line, not an exit code. Not changed here; noted for review.

<!-- fr:journal kind=discovery scope=plan id=p1-scenario-gh-double created=2026-11-08T17:50:00+00:00 phase=1 -->
### p1-scenario-gh-double · discovery · printed-commands-run uses its own gh double (phase 1)

gate-backfill-apply's gh double cannot comment on or read a PR and does not take `issue close --comment`; the scenario's double (fixtures/printed-commands-run/bin/gh) is a copy extended for those. The acceptance matrix has no row for the scenario yet.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-08T17:50:00+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

Three one-line string changes in emitters; nothing to tidy.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-08T17:50:00+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

The change is a new test file; the extractor and runner were written once and are the tidy form.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-08T18:15:06+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · A same-status record with no notes wiped the row's note (phase 1)

The narrowed check in record/apply.py let any non-CLI record entry that names a row at its current status and no notes write an empty note. Verified at the `notes=item.notes or ""` line.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-08T18:15:06+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · A repeated link-only --notes was appended again (phase 1)

Issues are de-duplicated but notes were not, so a re-run gave `n; y; y`.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-08T18:15:06+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · The source scan named four modules, so a new emitter elsewhere was not caught (phase 1)

EMITTERS listed render, trackers, close and gate_cmd only.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-08T18:15:06+00:00 phase=1 state=open review_scope=out -->
### p1-r4 · finding [open] (reviewer: out of scope) · `fr gate pass --yes` exits 0 when a tracker close fails (phase 1)

It prints the retry line and exits 0. Pre-existing, in gate_cmd.py, and not touched by this change.

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-11-08T18:15:06+00:00 phase=1 -->
### review-phase-1 · review · Phase 1 review: 4 findings, 3 in scope and fixed (phase 1)

A dispatched reviewer read the diff against R1-R6. Findings p1-r1 to p1-r3 were verified against the code and fixed test-first, the tests seen failing before and passing after; p1-r4 is out of scope. Reviewer verdict: with fixes.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-08T18:15:06+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: A same-status record with no notes wiped the row's note (phase 1)

An item that moves nothing and names no note keeps the row's note; test_a_same_status_item_with_no_notes_keeps_the_rows_note.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-08T18:15:06+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: A repeated link-only --notes was appended again (phase 1)

A note already present as a segment is not appended; test_a_repeated_link_only_note_is_not_appended_twice.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-08T18:15:06+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: The source scan named four modules, so a new emitter elsewhere was not caught (phase 1)

The scan globs the whole gatebackfill package plus gate_cmd.py, and a comment says it is a guard, not a proof. It found one more literal, `fr debt`, which is prose.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-08T18:15:06+00:00 phase=1 state=open resolves=p1-r4 out_of_scope=true -->
### p1-r4-resolved · finding [out-of-scope] · resolves p1-r4: `fr gate pass --yes` exits 0 when a tracker close fails (phase 1)

Pre-existing exit code, not caused by this change; to be filed at deliver.

<!-- fr:journal kind=discovery scope=plan id=p2-guards-pass-before-change created=2026-11-08T18:26:06+00:00 phase=2 -->
### p2-guards-pass-before-change · discovery · The mid-line marker and manifest-named tests pass on the pre-change code (phase 2)

Only the whole-line digest test went red at RED. The mid-line and manifest-named cases already matched under the old OR-ing; they are kept as guards on the reorder, not as red-first proof.

<!-- fr:journal kind=decision scope=plan id=p2-manifest-before-marker created=2026-11-08T18:26:06+00:00 phase=2 -->
### p2-manifest-before-marker · decision · The manifest match is taken before the marker skip (phase 2)

A manifest that names an issue by number always makes it a look-alike, so a digest-marked issue the operator named stays a suggestion. The owned and own-ref exclusions still run first, as before.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-08T18:26:06+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

reread _lookalikes after the reorder: no dead branch remains; the reorder itself is the only change, the manifest match stays a nested if so the always-hit intent reads on its own line

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-08T18:29:48+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · The legacy digest marker was tested only under the viewer's author (phase 2)

R7 says whatever the author. The code has no author check, so behaviour is correct; the test coverage was the gap.

<!-- fr:journal kind=review scope=plan id=review-phase-2 created=2026-11-08T18:29:48+00:00 phase=2 -->
### review-phase-2 · review · Phase 2 review: 1 finding, in scope and fixed (phase 2)

A dispatched reviewer read the commit against R7 and 3.B and checked the routes back to a suggestion, the marker forms and import direction. Verdict: ready. Its one test-strength finding was fixed.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-08T18:29:48+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: The legacy digest marker was tested only under the viewer's author (phase 2)

The legacy-marker issue in the test is now stranger-authored.

<!-- fr:journal kind=discovery scope=plan id=p3-demoted-siblings-stay-in-section created=2026-11-08T18:41:17+00:00 phase=3 -->
### p3-demoted-siblings-stay-in-section · discovery · A demoted # Test Plan keeps its ### siblings inside the section (phase 3)

After demoting, `### Notes` sits under `## Test Plan`, so list items there read as steps (the section ends only at the next # or ## heading). That is the spec's own example and R9; the tests use prose under Notes. A writer with a list under such a sibling gets those items as steps.

<!-- fr:journal kind=discovery scope=plan id=p3-repair-read-bytes-for-crlf created=2026-11-08T18:41:17+00:00 phase=3 -->
### p3-repair-read-bytes-for-crlf · discovery · The repair reads bytes, not read_text, to keep CRLF (phase 3)

Path.read_text translates CRLF to LF, and write_text_atomic writes newline='' so the old _fn silently normalised a CRLF spec. _fn now decodes read_bytes; _applies still uses read_text, which is fine for a predicate.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-11-08T18:41:17+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

the change was deleting one predicate clause; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-11-08T18:41:17+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

a new scenario script and its registration; nothing existing to tidy

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-08T18:44:58+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · The demotion keyword set had no pin against fr's section readers (phase 3)

A new keyword reader added later would be swallowed by demotion with no red test.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-08T18:44:58+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · The near-miss form list omitted multi-digit and multi-level prefixes (phase 3)

The list is hand-written. The repair has no separate predicate, so the risk is small.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-08T18:44:58+00:00 phase=3 state=open review_scope=out -->
### p3-r3 · finding [open] (reviewer: out of scope) · Non-UTF-8 spec bytes raise UnicodeDecodeError in the repair (phase 3)

`_applies` already raised through read_text, so this is not new. It fails loud and corrupts nothing. How the gate reports a raising `applies` was not examined.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-11-08T18:44:58+00:00 phase=3 state=open review_scope=out -->
### p3-r4 · finding [open] (reviewer: out of scope) · The reader folds heading lines inside the Test Plan into the previous step's text (phase 3)

Lazy continuation in the reader, and the same for an exact `## Test Plan` with children. Not caused by this change.

<!-- fr:journal kind=review scope=plan id=review-phase-3 created=2026-11-08T18:44:58+00:00 phase=3 -->
### review-phase-3 · review · Phase 3 review: 4 findings, 2 in scope and fixed (phase 3)

A dispatched reviewer ran real shapes through the repair (siblings, children, fences, CRLF, sole h1, level six) and found the behaviour correct. It judged the demoted `###` sibling to be the writer's own hierarchy, not a false-step defect: those items were children of the Test Plan before and after, as with an exact heading. Findings p3-r1 and p3-r2 were hardening and are fixed.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-08T18:44:58+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: The demotion keyword set had no pin against fr's section readers (phase 3)

test_the_demotion_keywords_are_exactly_the_sections_fr_reads_by_keyword scans the package's keyword readers and compares them with the repair's set.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-08T18:44:58+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: The near-miss form list omitted multi-digit and multi-level prefixes (phase 3)

The form list now includes `12.` and `6.1.2`.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-08T18:44:58+00:00 phase=3 state=open resolves=p3-r3 out_of_scope=true -->
### p3-r3-resolved · finding [out-of-scope] · resolves p3-r3: Non-UTF-8 spec bytes raise UnicodeDecodeError in the repair (phase 3)

Pre-existing through read_text and fails loud; not caused by this change.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-11-08T18:44:58+00:00 phase=3 state=open resolves=p3-r4 out_of_scope=true -->
### p3-r4-resolved · finding [out-of-scope] · resolves p3-r4: The reader folds heading lines inside the Test Plan into the previous step's text (phase 3)

A reader quirk that holds for an exact heading too; not caused by this change.

<!-- fr:journal kind=finding scope=plan id=p4-manifest-only-unknowable-without-from created=2026-11-08T19:24:31+00:00 phase=4 state=open review_scope=in -->
### p4-manifest-only-unknowable-without-from · finding [open] (reviewer: in scope) · A manifest-only key cannot be recognised on a dry run that omits --from (phase 4)

R14 says a manifest-only key is never discharged, but nothing outside the manifest says a key came from one: its tracker reads like any other. Safe reading implemented: with `--from`, a manifest NEW item (`kind:` set) never closes, even with evidence; an override stays closable, because the fold holds that key. Without `--from`, the key still needs positive evidence, so a key with no row, phase or outcome is never discharged. The gap left: a manifest item whose key names a real row, phase or step that has genuinely reached a done state closes on that evidence when `--from` is omitted. Tests: test_a_manifest_only_key_is_untouched and test_a_manifest_new_item_with_evidence_stays_the_manifests_claim. Closing the gap would need a marker on the tracker body; the spec does not ask for one, so this is for the orchestrator to judge.

<!-- fr:journal kind=discovery scope=plan id=p4-open-issue-refusal-scope created=2026-11-08T19:24:31+00:00 phase=4 -->
### p4-open-issue-refusal-scope · discovery · The dry run refused any owed key held by its tracker alone, not only an issue key (phase 4)

`render.open_issue_refusals` tested the fold source only, so a `row:` or `plan:` key held by its own tracker exited 2 with "adopt row:x", a command that cannot exist. Its docstring says `issue:` keys. It surfaced because a tracked-only tracker on a checkout R15 refuses stays in the entries. Narrowed to `issue:` keys, since an exit 2 there would have hidden R15's note.

<!-- fr:journal kind=discovery scope=plan id=p4-superseded-owed-stays-held created=2026-11-08T19:24:31+00:00 phase=4 -->
### p4-superseded-owed-stays-held · discovery · A step recorded ran over an open owed entry is still held by the journal (phase 4)

`fr closeout outcome --ran --supersede` leaves the owed entry open, so the effective outcome reads ran while the fold's journal source still holds the key. R14 requires both, so this is not discharged until the entry is resolved. `discharge_command` already prints `fr journal resolve` first for such a key, so the printed route gets there. Pinned by test_an_open_owed_entry_superseded_to_ran_is_still_held_by_the_journal and stated in docs/gate-backfill.md.

<!-- fr:journal kind=discovery scope=plan id=p4-discharged-set-is-not-only-fixed created=2026-11-08T19:24:31+00:00 phase=4 -->
### p4-discharged-set-is-not-only-fixed · discovery · journal_owed's discharged set holds every entry no longer open, not only fixed ones (phase 4)

`open_owed_ids` reads anything but `open` as closed, so a hand-written refuted or deferred record lands in the set the plan said to reuse. `fr journal resolve` refuses those states on an owed entry, so only a hand edit or `journal add --resolves` reaches it. R14 says resolved fixed, so `EvidenceReader.fixed_keys` intersects the set with the effective state `fixed`.

<!-- fr:journal kind=discovery scope=plan id=p4-adopted-issue-comes-back-as-candidate created=2026-11-08T19:24:31+00:00 phase=4 -->
### p4-adopted-issue-comes-back-as-candidate · discovery · Dropping an adopt decision would make the adopted issue a refused candidate (phase 4)

R15 drops a recorded `adopt` on a discharged key. `collect_candidates` learns adopted issues from that decision, so the next dry run would offer `issue:<ref>` as a bare owed candidate and exit 2 until the operator closed it. `list_closes` therefore returns every foreign issue carrying this account's tracked-only comment, and the command removes those from the candidates with "a tracker, not a candidate". The comments are read on `--yes` as well, or that run would report a new candidate.

<!-- fr:journal kind=discovery scope=plan id=p4-closing-comment-is-one-line created=2026-11-08T19:24:31+00:00 phase=4 -->
### p4-closing-comment-is-one-line · discovery · The closing comment stays on one line because the adopted close command carries it (phase 4)

The printed `gh issue close --comment` is read one line per command, and a plan phase's discharge has several `--tick` lines. `position` joins them with `; `, which the printed-commands extractor reads as separate commands inside the backtick span.

<!-- fr:journal kind=discovery scope=plan id=p4-no-new-printed-verb created=2026-11-08T19:24:31+00:00 phase=4 -->
### p4-no-new-printed-verb · discovery · No new fr verb is printed, and tracker text avoids naming the backfill as a command (phase 4)

COVERED_VERBS is unchanged. The tracked-only closing lines and the close comment say "the next gate backfill" in prose, since a literal command in a body would be executed by the printed-commands test against whatever decisions that plan file holds. The new `gh issue close` line is shape-checked in test_every_command_the_keep_and_close_flows_print_runs.

<!-- fr:journal kind=decision scope=plan id=p4-another-holders-marker-blocks-the-close created=2026-11-08T19:24:31+00:00 phase=4 -->
### p4-another-holders-marker-blocks-the-close · decision · A foreign owed issue carrying the key's marker keeps the tracker open (phase 4)

R14 allows no source but the key's own tracker, and the debt fold reads a marker on any owed-labelled issue, whoever wrote it. So such an issue blocks the close, with a note. A stranger can delay a close this way and cannot cause one, which is the safe direction. Two fr-owned trackers of one key do not block each other.

<!-- fr:journal kind=decision scope=plan id=p4-keep-on-a-discharged-key created=2026-11-08T19:24:31+00:00 phase=4 -->
### p4-keep-on-a-discharged-key · decision · --keep on an already discharged key still says the key is owed (phase 4)

R10 words the comment that way and R12 speaks of closing comments, so the operator's explicit --keep wins; the next backfill closes that tracker on its evidence. Nothing is lost either way, and the alternative would overrule an explicit flag.

<!-- fr:journal kind=decision scope=plan id=p4-close-command-reprinted created=2026-11-08T19:24:31+00:00 phase=4 -->
### p4-close-command-reprinted · decision · An adopted issue's close command is printed again on later runs (phase 4)

R13 asks that a second run writes nothing, not that it goes quiet. The issue is the operator's to close and fr holds no other reminder, so a later dry run (as a note) and `--yes` print the line again with no write.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-11-08T19:24:31+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

discharged_evidence was written as small per-kind readers over one cached EvidenceReader; nothing was left to tidy.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t3 created=2026-11-08T19:24:31+00:00 phase=4 -->
### no-refactor-p4-t3 · discovery · no-refactor-because P4.T3 (phase 4)

The listing and apply's re-check were written once in their final shape; the task ends with text and doc edits, nothing to clean.

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-11-08T20:56:47+00:00 phase=4 state=open review_scope=in -->
### p4-r1 · finding [open] (reviewer: in scope) · A row in a debt status closed through a journal owed entry resolved fixed (phase 4)

Reproduced by the reviewer unless noted in the review entry. test_p4_r1_a_row_in_a_debt_status_is_never_discharged_by_its_journal

<!-- fr:journal kind=finding scope=plan id=p4-r2 created=2026-11-08T20:56:47+00:00 phase=4 state=open review_scope=in -->
### p4-r2 · finding [open] (reviewer: in scope) · Any entry kind but owed read as a recorded outcome (phase 4)

Reproduced by the reviewer unless noted in the review entry. Only `discovery` counts, which is what --ran and --na both write; test_p4_r2_an_entry_of_another_kind_named_like_a_step_is_not_an_outcome

<!-- fr:journal kind=finding scope=plan id=p4-r3 created=2026-11-08T20:56:47+00:00 phase=4 state=open review_scope=in -->
### p4-r3 · finding [open] (reviewer: in scope) · An adopted issue authored by fr's own account was treated as owned and skipped (phase 4)

Reproduced by the reviewer unless noted in the review entry. Comments are read for any fr:owed issue owned_owed_key does not accept, in all four places; the test_p4_r3 tests with same-account fixtures

<!-- fr:journal kind=finding scope=plan id=p4-r4 created=2026-11-08T20:56:47+00:00 phase=4 state=open review_scope=in -->
### p4-r4 · finding [open] (reviewer: in scope) · A checkout of another repo was read as this PR's evidence (phase 4)

Reproduced by the reviewer unless noted in the review entry. _evidence_root requires the checkout's identity to equal --repo, using owed_identity because origin_slug follows insteadOf and a mirrored checkout would lose its evidence; test_p4_r4_a_checkout_of_another_repo_is_no_checkout

<!-- fr:journal kind=finding scope=plan id=p4-r5 created=2026-11-08T20:56:47+00:00 phase=4 state=open review_scope=in -->
### p4-r5 · finding [open] (reviewer: in scope) · --keep on a discharged key said still owed, then the next backfill closed it (phase 4)

Reproduced by the reviewer unless noted in the review entry. It still converts, and says it reads as discharged and that the next backfill closes it; test_p4_r5_keep_on_a_discharged_key_converts_and_says_the_backfill_closes_it

<!-- fr:journal kind=finding scope=plan id=p4-r6 created=2026-11-08T20:56:47+00:00 phase=4 state=open review_scope=in -->
### p4-r6 · finding [open] (reviewer: in scope) · R14 and the doc said a manifest item never closes, which is untrue without --from (phase 4)

Reproduced by the reviewer unless noted in the review entry. Spec R14 and Risks, and docs/gate-backfill.md, now state it; no code change

<!-- fr:journal kind=finding scope=plan id=p4-r7 created=2026-11-08T20:56:47+00:00 phase=4 state=open review_scope=in -->
### p4-r7 · finding [open] (reviewer: in scope) · --yes --from ignored the manifest's claim on a recorded close (phase 4)

Reproduced by the reviewer unless noted in the review entry. test_p4_r7_yes_from_a_manifest_honours_its_claim_on_a_recorded_close

<!-- fr:journal kind=finding scope=plan id=p4-r8 created=2026-11-08T20:56:47+00:00 phase=4 state=open review_scope=in -->
### p4-r8 · finding [open] (reviewer: in scope) · Narrowed open_issue_refusals silenced a key held only by a stranger's marker (phase 4)

Reproduced by the reviewer unless noted in the review entry. It refuses with the working adopt route; test_p4_r8_a_key_held_by_a_strangers_marker_is_refused_with_the_working_route

<!-- fr:journal kind=finding scope=plan id=p4-r9 created=2026-11-08T20:56:47+00:00 phase=4 state=open review_scope=in -->
### p4-r9 · finding [open] (reviewer: in scope) · R15's clean check missed untracked evidence under status.showUntrackedFiles=no (phase 4)

Reproduced by the reviewer unless noted in the review entry. --untracked-files=normal; the hidden-untracked case of the R15 tests

<!-- fr:journal kind=finding scope=plan id=p4-r10 created=2026-11-08T20:56:47+00:00 phase=4 state=open review_scope=in -->
### p4-r10 · finding [open] (reviewer: in scope) · An adopted key passed on two gates was listed twice (phase 4)

Reproduced by the reviewer unless noted in the review entry. test_p4_r10_two_tracked_only_comments_for_one_key_list_one_close

<!-- fr:journal kind=finding scope=plan id=p4-r11 created=2026-11-08T20:56:47+00:00 phase=4 state=open review_scope=in -->
### p4-r11 · finding [open] (reviewer: in scope) · Repeated scans and reads (phase 4)

Reproduced by the reviewer unless noted in the review entry. One per-run holder index, one journal parse per reader, a --keep pass reuses its reads; the test_p4_r11 tests. debt/engine.py gained an optional journals= for this, with default behaviour unchanged

<!-- fr:journal kind=finding scope=plan id=p4-r12 created=2026-11-08T20:56:47+00:00 phase=4 state=open review_scope=in -->
### p4-r12 · finding [open] (reviewer: in scope) · R12's claim was not guarded by R15's conditions (phase 4)

Reproduced by the reviewer unless noted in the review entry. test_p4_r12_evidence_is_stated_only_when_r15_holds

<!-- fr:journal kind=finding scope=plan id=p4-r13 created=2026-11-08T20:56:47+00:00 phase=4 state=open review_scope=out -->
### p4-r13 · finding [open] (reviewer: out of scope) · A failed tracker write on the first gate pass route exits 0 (phase 4)

Predates this phase, and is the same defect as p1-r4. --keep makes it easier to miss, and the retry line is still printed.

<!-- fr:journal kind=decision scope=plan id=p4-yes-beside-a-strangers-marker created=2026-11-08T20:56:47+00:00 phase=4 -->
### p4-yes-beside-a-strangers-marker · decision · --yes on a plan still at owed files fr's own tracker beside a stranger's marker (phase 4)

The dry run refuses the key (p4-r8), but a plan left at `owed` still files a tracker at --yes. That is the old behaviour for non-issue keys, and the tracker then holds the key, so nothing is lost. Left as is.

<!-- fr:journal kind=discovery scope=plan id=p4-entries-superseded-by-review created=2026-11-08T20:56:47+00:00 phase=4 -->
### p4-entries-superseded-by-review · discovery · Two earlier phase 4 entries are superseded by the review fixes (phase 4)

p4-keep-on-a-discharged-key: --keep now says the key reads as discharged (p4-r5). p4-another-holders-marker-blocks-the-close: the behaviour stands, and its scan is now the per-run holder index (p4-r11).

<!-- fr:journal kind=review scope=plan id=review-phase-4 created=2026-11-08T20:56:47+00:00 phase=4 -->
### review-phase-4 · review · Phase 4 review: 13 findings, 12 in scope and fixed (phase 4)

A dispatched reviewer ran probe scenarios over real git and the fake client, trying to make fr close what it should not. It could not close a stranger's issue or act on a forged marker. It did close a tracker on a failing row (p4-r1) and wrote false evidence from another repo's checkout (p4-r4). p4-r8's --yes note and p4-r12 were by reading. The executor checked and fixed all twelve test-first; a few tests were not seen failing on the old code, as its return says. Diff size judged justified: about 1270 of 2047 inserted lines at review were tests.

<!-- fr:journal kind=finding scope=plan id=p4-r1-resolved created=2026-11-08T20:56:47+00:00 phase=4 state=fixed resolves=p4-r1 -->
### p4-r1-resolved · finding [fixed] · resolves p4-r1: A row in a debt status closed through a journal owed entry resolved fixed (phase 4)

test_p4_r1_a_row_in_a_debt_status_is_never_discharged_by_its_journal

<!-- fr:journal kind=finding scope=plan id=p4-r2-resolved created=2026-11-08T20:56:47+00:00 phase=4 state=fixed resolves=p4-r2 -->
### p4-r2-resolved · finding [fixed] · resolves p4-r2: Any entry kind but owed read as a recorded outcome (phase 4)

Only `discovery` counts, which is what --ran and --na both write; test_p4_r2_an_entry_of_another_kind_named_like_a_step_is_not_an_outcome

<!-- fr:journal kind=finding scope=plan id=p4-r3-resolved created=2026-11-08T20:56:47+00:00 phase=4 state=fixed resolves=p4-r3 -->
### p4-r3-resolved · finding [fixed] · resolves p4-r3: An adopted issue authored by fr's own account was treated as owned and skipped (phase 4)

Comments are read for any fr:owed issue owned_owed_key does not accept, in all four places; the test_p4_r3 tests with same-account fixtures

<!-- fr:journal kind=finding scope=plan id=p4-r4-resolved created=2026-11-08T20:56:47+00:00 phase=4 state=fixed resolves=p4-r4 -->
### p4-r4-resolved · finding [fixed] · resolves p4-r4: A checkout of another repo was read as this PR's evidence (phase 4)

_evidence_root requires the checkout's identity to equal --repo, using owed_identity because origin_slug follows insteadOf and a mirrored checkout would lose its evidence; test_p4_r4_a_checkout_of_another_repo_is_no_checkout

<!-- fr:journal kind=finding scope=plan id=p4-r5-resolved created=2026-11-08T20:56:47+00:00 phase=4 state=fixed resolves=p4-r5 -->
### p4-r5-resolved · finding [fixed] · resolves p4-r5: --keep on a discharged key said still owed, then the next backfill closed it (phase 4)

It still converts, and says it reads as discharged and that the next backfill closes it; test_p4_r5_keep_on_a_discharged_key_converts_and_says_the_backfill_closes_it

<!-- fr:journal kind=finding scope=plan id=p4-r6-resolved created=2026-11-08T20:56:47+00:00 phase=4 state=fixed resolves=p4-r6 -->
### p4-r6-resolved · finding [fixed] · resolves p4-r6: R14 and the doc said a manifest item never closes, which is untrue without --from (phase 4)

Spec R14 and Risks, and docs/gate-backfill.md, now state it; no code change

<!-- fr:journal kind=finding scope=plan id=p4-r7-resolved created=2026-11-08T20:56:47+00:00 phase=4 state=fixed resolves=p4-r7 -->
### p4-r7-resolved · finding [fixed] · resolves p4-r7: --yes --from ignored the manifest's claim on a recorded close (phase 4)

test_p4_r7_yes_from_a_manifest_honours_its_claim_on_a_recorded_close

<!-- fr:journal kind=finding scope=plan id=p4-r8-resolved created=2026-11-08T20:56:47+00:00 phase=4 state=fixed resolves=p4-r8 -->
### p4-r8-resolved · finding [fixed] · resolves p4-r8: Narrowed open_issue_refusals silenced a key held only by a stranger's marker (phase 4)

It refuses with the working adopt route; test_p4_r8_a_key_held_by_a_strangers_marker_is_refused_with_the_working_route

<!-- fr:journal kind=finding scope=plan id=p4-r9-resolved created=2026-11-08T20:56:47+00:00 phase=4 state=fixed resolves=p4-r9 -->
### p4-r9-resolved · finding [fixed] · resolves p4-r9: R15's clean check missed untracked evidence under status.showUntrackedFiles=no (phase 4)

--untracked-files=normal; the hidden-untracked case of the R15 tests

<!-- fr:journal kind=finding scope=plan id=p4-r10-resolved created=2026-11-08T20:56:47+00:00 phase=4 state=fixed resolves=p4-r10 -->
### p4-r10-resolved · finding [fixed] · resolves p4-r10: An adopted key passed on two gates was listed twice (phase 4)

test_p4_r10_two_tracked_only_comments_for_one_key_list_one_close

<!-- fr:journal kind=finding scope=plan id=p4-r11-resolved created=2026-11-08T20:56:47+00:00 phase=4 state=fixed resolves=p4-r11 -->
### p4-r11-resolved · finding [fixed] · resolves p4-r11: Repeated scans and reads (phase 4)

One per-run holder index, one journal parse per reader, a --keep pass reuses its reads; the test_p4_r11 tests. debt/engine.py gained an optional journals= for this, with default behaviour unchanged

<!-- fr:journal kind=finding scope=plan id=p4-r12-resolved created=2026-11-08T20:56:47+00:00 phase=4 state=fixed resolves=p4-r12 -->
### p4-r12-resolved · finding [fixed] · resolves p4-r12: R12's claim was not guarded by R15's conditions (phase 4)

test_p4_r12_evidence_is_stated_only_when_r15_holds

<!-- fr:journal kind=finding scope=plan id=p4-r13-resolved created=2026-11-08T20:56:47+00:00 phase=4 state=open resolves=p4-r13 out_of_scope=true -->
### p4-r13-resolved · finding [out-of-scope] · resolves p4-r13: A failed tracker write on the first gate pass route exits 0 (phase 4)

Pre-existing exit code on the first pass route, not caused by this change; to be filed at deliver with p1-r4.

<!-- fr:journal kind=finding scope=plan id=p4-manifest-only-unknowable-without-from-resolved created=2026-11-08T20:56:47+00:00 phase=4 state=refuted resolves=p4-manifest-only-unknowable-without-from -->
### p4-manifest-only-unknowable-without-from-resolved · finding [refuted] · resolves p4-manifest-only-unknowable-without-from: A manifest-only key cannot be recognised on a dry run that omits --from (phase 4)

Not a code defect: a key naming a real row, phase or step has real evidence, shown in the dry run. R14 and the Risks line now state this, and docs/gate-backfill.md follows them. The `claimed` guard stays for --from.

<!-- fr:journal kind=decision scope=plan id=p5-noop-line-on-its-own created=2026-11-08T21:21:16+00:00 phase=5 -->
### p5-noop-line-on-its-own · decision · R16's line is printed on its own, beside the reason, not inside "nothing to release" (phase 5)

`Plan` gains `noop`, and `prepare` and `dry_run` print it as a line of its own, so the
Test Plan's walk can look for the exact text. `Plan.why` keeps the gate reason and is printed
on the line before it: without that, a run that could not read the gate state ("HTTP 502")
would show only the no-op, and the reason an RC or final was not cut would be lost.

<!-- fr:journal kind=decision scope=plan id=p5-failed-diff-refuses created=2026-11-08T21:21:16+00:00 phase=5 -->
### p5-failed-diff-refuses · decision · A failing git diff refuses the run (phase 5)

`installable_changed` raises `CalledProcessError`, and `release._installable_changed` turns
that (or a missing git) into `ReleaseError`, exit 1. Choosing to cut an RC instead would also
fail towards releasing, but a tree git cannot diff is not one to stage a release on, and a
red job is seen. A real failure is tested: an RC tag listed with no ref behind it.

<!-- fr:journal kind=discovery scope=plan id=p5-env-keyword-on-installable-changed created=2026-11-08T21:21:16+00:00 phase=5 -->
### p5-env-keyword-on-installable-changed · discovery · installable_changed takes an env keyword the spec's signature does not show (phase 5)

AGENTS.md says every git command but the two pushes runs credential-free, and `_git` is how
release.py keeps that. The new module runs its own git, so it takes `env`, and release.py
passes `_credential_free_env()`. A test records the env the diff really ran with. The list of
credentials stays in one place.

<!-- fr:journal kind=discovery scope=plan id=p5-refs-tags-and-bytes created=2026-11-08T21:21:16+00:00 phase=5 -->
### p5-refs-tags-and-bytes · discovery · The diff names refs/tags/<tag> and decodes bytes itself (phase 5)

A branch named like a tag would otherwise win or be ambiguous, which a test pins. The output
is read as bytes and decoded with `os.fsdecode`, because `text=True` raises on a path the
runner's locale cannot decode, and a decoding crash is not a `ReleaseError`.

<!-- fr:journal kind=discovery scope=plan id=p5-dry-run-mixes-tree-and-commits created=2026-11-08T21:21:16+00:00 phase=5 -->
### p5-dry-run-mixes-tree-and-commits · discovery · --dry-run reads fragments from the working tree but the diff from commits (phase 5)

An uncommitted fragment still counts as pending, while uncommitted code does not count as an
installable change, because `installable_changed` compares the tag with HEAD. That is the
right comparison for the real run, which resets to origin/main first. It is why
`test_dry_run_says_it_would_cut_an_rc` now commits a code path as its fixture.

<!-- fr:journal kind=discovery scope=plan id=p5-untagged-rc-reaches-the-recovery-by-the-version-line created=2026-11-08T21:21:16+00:00 phase=5 -->
### p5-untagged-rc-reaches-the-recovery-by-the-version-line · discovery · An untagged RC reaches its recovery because its version line differs from every tag (phase 5)

With the RC's tag missing, the compared tag is an older one, and the release commit's own
version surfaces (`pyproject.toml`, `uv.lock`) are installable paths. So the diff is always
true, `_not_backwards` returns nothing new and `finish` tags HEAD. Tests pin this with a docs
merge above the RC and with an older RC tag below it.

<!-- fr:journal kind=discovery scope=plan id=p5-fixtures-changed created=2026-11-08T21:21:16+00:00 phase=5 -->
### p5-fixtures-changed · discovery · Seventeen existing tests changed their fixtures, none their assertions (phase 5)

Fifteen moved from `world.fragment` to the new `world.change`, which lands code and then the
fragment. `test_dry_run_says_it_would_cut_an_rc` and
`test_p7_r2_a_pr_in_git_log_but_missing_from_the_read_is_unknown_never_a_final` land a code
path directly. `test_release_py_reads_the_forge_and_hands_fr_the_facts` lands only a fragment
and still passes, because it asserts the read and the facts, which come before this check.

<!-- fr:journal kind=discovery scope=plan id=p5-gate-backfill-doc-sentence created=2026-11-08T21:21:16+00:00 phase=5 -->
### p5-gate-backfill-doc-sentence · discovery · docs/gate-backfill.md never described when an RC is cut, so it gained one parenthesis (phase 5)

The spec lists this page as updated, while the plan's steps name only `compute` and
`AGENTS.md`. The page's one mention of a held release now says a housekeeping merge cuts no RC.
The acceptance row `release-skips-rc-nothing-installable` is not moved here: this step's
record carries no acceptance section.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t1 created=2026-11-08T21:21:16+00:00 phase=5 -->
### no-refactor-p5-t1 · discovery · no-refactor-because P5.T1 (phase 5)

A new module of two short functions, written once; there was nothing to tidy.

<!-- fr:journal kind=finding scope=plan id=p5-r1 created=2026-11-08T21:38:19+00:00 phase=5 state=open review_scope=in -->
### p5-r1 · finding [open] (reviewer: in scope) · AGENTS.md said an unknown gate state is never a refusal, but a failing git diff refuses there (phase 5)

The clause needed scoping to the gate state.

<!-- fr:journal kind=finding scope=plan id=p5-r2 created=2026-11-08T21:38:19+00:00 phase=5 state=open review_scope=in -->
### p5-r2 · finding [open] (reviewer: in scope) · The release.yml header and release_status.py still stated the old RC rule (phase 5)

Those comments are read first when a Release run does nothing.

<!-- fr:journal kind=finding scope=plan id=p5-r3 created=2026-11-08T21:38:19+00:00 phase=5 state=open review_scope=out -->
### p5-r3 · finding [open] (reviewer: out of scope) · An RC tag above HEAD's line that HEAD does not contain makes every run cut another RC (phase 5)

Reproduced with a hand-pushed tag on a sibling commit. The comparison tag stays on the higher tag, whose tree always differs. By reading, the old `_merged_since` looped the same way (the reviewer did not run the base commit). It needs a hand-pushed tag; the normal flow cannot produce it.

<!-- fr:journal kind=review scope=plan id=review-phase-5 created=2026-11-08T21:38:19+00:00 phase=5 -->
### review-phase-5 · review · Phase 5 review: 3 findings, 2 in scope and fixed (phase 5)

A dispatched reviewer drove nine fixture histories through compute, trying to make releases stop silently. It could not: a no-op fires only when HEAD's installable tree equals the tag's, so that tag already carries the code, and a wrong comparison tag costs a spare RC. It also checked the denylist's lookalike paths, the tripwire by reading, the workflow's cut=false guard, and that the 17 changed fixtures moved no assertion.

<!-- fr:journal kind=finding scope=plan id=p5-r1-resolved created=2026-11-08T21:38:19+00:00 phase=5 state=fixed resolves=p5-r1 -->
### p5-r1-resolved · finding [fixed] · resolves p5-r1: AGENTS.md said an unknown gate state is never a refusal, but a failing git diff refuses there (phase 5)

AGENTS.md scopes the clause to the gate state and names the failing diff.

<!-- fr:journal kind=finding scope=plan id=p5-r2-resolved created=2026-11-08T21:38:19+00:00 phase=5 state=fixed resolves=p5-r2 -->
### p5-r2-resolved · finding [fixed] · resolves p5-r2: The release.yml header and release_status.py still stated the old RC rule (phase 5)

The release.yml header and the release_status.py docstring state the rule.

<!-- fr:journal kind=finding scope=plan id=p5-r3-resolved created=2026-11-08T21:38:19+00:00 phase=5 state=open resolves=p5-r3 out_of_scope=true -->
### p5-r3-resolved · finding [out-of-scope] · resolves p5-r3: An RC tag above HEAD's line that HEAD does not contain makes every run cut another RC (phase 5)

Same exposure before this change by reading, and needs a hand-pushed tag; to be filed at deliver.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved-2 created=2026-11-08T21:44:15+00:00 phase=1 state=open resolves=p1-r4 tracked_by=https://github.com/derio-net/super-fr/issues/1389 -->
### p1-r4-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1389] · resolves p1-r4: `fr gate pass --yes` exits 0 when a tracker close fails (phase 1)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1389.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved-2 created=2026-11-08T21:44:29+00:00 phase=3 state=open resolves=p3-r3 tracked_by=https://github.com/derio-net/super-fr/issues/1390 -->
### p3-r3-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1390] · resolves p3-r3: Non-UTF-8 spec bytes raise UnicodeDecodeError in the repair (phase 3)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1390.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved-2 created=2026-11-08T21:44:43+00:00 phase=3 state=open resolves=p3-r4 tracked_by=https://github.com/derio-net/super-fr/issues/1391 -->
### p3-r4-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1391] · resolves p3-r4: The reader folds heading lines inside the Test Plan into the previous step's text (phase 3)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1391.

<!-- fr:journal kind=finding scope=plan id=p4-r13-resolved-2 created=2026-11-08T21:44:57+00:00 phase=4 state=open resolves=p4-r13 tracked_by=https://github.com/derio-net/super-fr/issues/1392 -->
### p4-r13-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1392] · resolves p4-r13: A failed tracker write on the first gate pass route exits 0 (phase 4)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1392.

<!-- fr:journal kind=finding scope=plan id=p5-r3-resolved-2 created=2026-11-08T21:45:10+00:00 phase=5 state=open resolves=p5-r3 tracked_by=https://github.com/derio-net/super-fr/issues/1393 -->
### p5-r3-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1393] · resolves p5-r3: An RC tag above HEAD's line that HEAD does not contain makes every run cut another RC (phase 5)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1393.
