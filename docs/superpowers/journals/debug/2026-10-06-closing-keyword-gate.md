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
