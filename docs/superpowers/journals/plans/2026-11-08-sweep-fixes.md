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
