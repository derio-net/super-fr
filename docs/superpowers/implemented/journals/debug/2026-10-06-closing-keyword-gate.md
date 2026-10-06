# Journal: 2026-10-06-closing-keyword-gate

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-06T16:35:25+00:00 -->
### repro · repro · Gate refuses keyword-like prose and misses a keyword split from its refs

Against origin/main 37724ada, `shared_closing_keywords`: 'fix colour #123' -> refused (suggests 'fix #123'); 'This fixes the regression from #12, reported in #34' -> refused; 'Closes\n#5, #6' -> [] (missed); 'Closes #5,\n#6' -> [] (missed); 'Closes #5 and #6' -> refused (correct, the #821 case).

<!-- fr:journal kind=hypothesis scope=debug id=h1 created=2026-10-06T16:35:26+00:00 -->
### h1 · hypothesis · One cause: the gate keys on line co-occurrence, not on an effective close

`_closing_lines` yields any line where a keyword and a ref co-occur, and `shared_closing_keywords` then needs a keyword before every ref. A line whose keyword closes nothing (no ref directly after it) is still policed: the false hit (#868). The unit is the physical line, so a keyword whose first ref or list continuation sits on the next line is never seen: the miss (#869). Both are the gate approximating GitHub's `<keyword>[:] <ref>` grammar by line co-occurrence. Prediction: anchoring on an effective close (keyword directly before a ref) and following that close across a soft line break fixes both and keeps every #821 case refused, because each of them contains an effective close.

<!-- fr:journal kind=finding scope=debug id=e1 created=2026-10-06T16:40:00+00:00 state=open -->
### e1 · finding [open] · Live: GitHub never links a keyword across a line break, but a wrapped ref list leaves its tail open

Probed 2026-10-06 on draft PR #1032 by editing its body and reading closingIssuesReferences (only the batch's own issues referenced): 'Closes #869 and #868' -> [869]; 'fix colour #868' -> []; 'Closes\n#868' -> []; 'Closes:\n#868' -> []; 'Closes #869,\n#868' -> [869]; 'Closes\n\n#868' -> []; 'Closes#868' -> []. So a keyword split from its FIRST ref closes nothing (line-scoped reading is right there, the same as #868's prose), while a ref LIST wrapped onto the next line closes its first ref only and the gate never sees the rest: that is #869's real hole. Same cause as h1.

<!-- fr:journal kind=ruled-out scope=debug id=h0 created=2026-10-06T16:40:00+00:00 -->
### h0 · ruled-out · Ruled out: scanning whole paragraphs instead of lines

A soft break renders as a space, so reading a paragraph as one line looks faithful, but under the strict rule it would refuse 'Closes #1\nRefs #2', the shape this repo's own PR bodies use (#860's did). The continuation must be narrower: a closing line whose tail after its last ref is only list separators, followed by a line that begins with a ref.

<!-- fr:journal kind=root-cause scope=debug id=rc created=2026-10-06T16:48:46+00:00 -->
### rc · root-cause · The gate keyed on line co-occurrence of a keyword and a reference, not on an effective close and its list

Confirms h1. `shared_closing_keywords` policed every line where a keyword and a ref co-occurred: a keyword that closes nothing (no ref directly after it) was refused (#868), and the physical line was the unit, so a ref list wrapped onto the next line had its tail unseen (#869). One cause, two symptoms; the evidence in e1 also shows a keyword split from its first ref closes nothing on GitHub, so that shape belongs with #868's prose, not with #869's hole.

<!-- fr:journal kind=finding scope=debug id=f1 created=2026-10-06T16:48:46+00:00 state=fixed -->
### f1 · finding [fixed] · Gate anchored on an effective close; wrapped reference lists read as one line

`fr.record.pr_body`: `_prose_lines` (code-skipping scan, now with fence sentinels) split from `_closing_lines`, whose behaviour for `closing_refs`/`referenced_refs` is unchanged. `shared_closing_keywords` reads `_wrapped_lines` (a line whose last ref is followed only by list glue joins a next line that opens on a ref), and skips a line where no keyword closes a ref directly after it. Red first: 2f1172bef/the #868 commit before 2728f5b63. Full suite: 9694 passed, 105 skipped.

<!-- fr:journal kind=finding scope=debug id=e1-resolved created=2026-10-06T16:49:00+00:00 state=fixed resolves=e1 -->
### e1-resolved · finding [fixed] · resolves e1: Live: GitHub never links a keyword across a line break, but a wrapped ref list leaves its tail open

Fixed by f1 (2728f5b63): the wrapped-list tail is read with its line; the split-keyword shape stays prose, as the live evidence shows GitHub links nothing there.

<!-- fr:journal kind=review scope=debug id=r1 created=2026-10-06T16:59:53+00:00 -->
### r1 · review · Independent review: 1 in-scope regression fixed, 1 refuted live, 1 accepted, 1 out of scope

Reviewer in a separate, read-only context (no shell; findings re-checked here by running the old and new gate side by side, then live on PR #1032). (1) IN SCOPE, FIXED: 'Closes GH-1 and #2' was refused before and passed after the narrowing, because the gate's ref pattern did not know GH-n. Live: 'Closes GH-869 and #868' -> [869]. Fixed by reading refs with _ISSUE_REF_GITHUB, red test first. (2) REFUTED: 'Closes (#1) and (#2)' also flipped to pass; live 'Closes (#868)' -> [] and 'Closes (#869) and (#868)' -> [], so GitHub closes nothing there and the old refusal was a #868-class false hit. Pinned by a test. (3) ACCEPTED: 'Closes #1\n#2 is the follow-up' is now refused. GitHub does leave #2 open there, so the refusal is right, only noisy, and needs a line that opens on a bare #n. (4) OUT OF SCOPE, pre-existing: a list wrapped inside a blockquote ('> Closes #1,\n> #2') is not joined; the old gate missed it too. Full suite after: 9698 passed, 105 skipped.

<!-- fr:journal kind=finding scope=debug id=o1 created=2026-10-06T16:59:53+00:00 state=open review_scope=out -->
### o1 · finding [open] (reviewer: out of scope) · A reference list wrapped inside a blockquote is not joined

'> Closes #1,\n> #2': _LIST_GLUE has no '>' so the quote's second line is not read as a continuation. Pre-existing (the line-scoped gate missed it too), rare, and not part of #869's live evidence, which covered plain line breaks.

<!-- fr:journal kind=finding scope=debug id=o1-resolved created=2026-10-06T16:59:54+00:00 state=open resolves=o1 out_of_scope=true -->
### o1-resolved · finding [out-of-scope] · resolves o1: A reference list wrapped inside a blockquote is not joined

Pre-existing: the gate before this change missed it too; not caused by this change. Recorded in the PR body for the operator to file or drop.
