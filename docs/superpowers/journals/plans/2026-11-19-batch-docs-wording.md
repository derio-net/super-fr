<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-batch-docs-wording

<!-- fr:journal kind=discovery scope=plan id=p1-bracket-set created=2026-11-19T11:24:46+00:00 phase=1 -->
### p1-bracket-set · discovery · R5's test flagged more strings than the spec listed (phase 1)

Besides init scaffold --tool, acceptance_cmd.py:755,1137,1141 and triage_batch_cmd.py:773, `fr plan create`'s docstring (`[row-ids]`, `[globs]`) lost its brackets too; all escaped.

<!-- fr:journal kind=discovery scope=plan id=p1-ste-first-sentence created=2026-11-19T11:24:46+00:00 phase=1 -->
### p1-ste-first-sentence · discovery · cli.md STE FAILs came from 13 help first sentences (phase 1)

The tree carries only the first sentence (sync-readme.first_sentence), so each fix split the docstring's opening into a short first sentence and kept the remaining facts as following sentences; the pinned checker reports no FAIL.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-19T11:24:46+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the R1 hint text appears in one message only; nothing to share

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-19T11:24:46+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

prose-only edits; the new test file is already minimal
