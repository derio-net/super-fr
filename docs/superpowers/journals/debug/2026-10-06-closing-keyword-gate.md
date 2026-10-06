# Journal: 2026-10-06-closing-keyword-gate

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-06T16:35:25+00:00 -->
### repro · repro · Gate refuses keyword-like prose and misses a keyword split from its refs

Against origin/main 37724ada, `shared_closing_keywords`: 'fix colour #123' -> refused (suggests 'fix #123'); 'This fixes the regression from #12, reported in #34' -> refused; 'Closes\n#5, #6' -> [] (missed); 'Closes #5,\n#6' -> [] (missed); 'Closes #5 and #6' -> refused (correct, the #821 case).
