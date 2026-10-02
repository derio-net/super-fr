# Journal: 2026-10-02-acceptance-integrity

<!-- fr:journal kind=repro scope=debug id=7450e8a5efc5 created=2026-10-02T17:38:25+00:00 -->
### 7450e8a5efc5 · repro · #470: insert_row emits an invalid matrix when rows are flush-left

Reproduced in-process: a matrix whose `rows:` items are flush-left (`- id:`, PyYAML's default dump) fails `yaml.safe_load` after `fr.acceptance.edit.insert_row` — on BOTH paths (same-capability insert and new-capability append). `render_row_block` unconditionally prefixes every line with two spaces, so the new item is indented deeper than its siblings and parses as a continuation of the previous row's mapping.

<!-- fr:journal kind=hypothesis scope=debug id=2bd438baedc7 created=2026-10-02T17:38:27+00:00 -->
### 2bd438baedc7 · hypothesis · The batch does not share one root cause

Investigation of the 8 members finds at least five independent causes, each in a different place: (1) #470 render_row_block hardcodes a 2-space item indent (edit.py); (2) #531 split_ref carries the #L fragment through and check.py strips it for existence only — no anchor validation exists; (3) #769 set_status_cmd's commit subject is always '{old} → {new}' (acceptance_cmd.py:486); (4) #655 record engine _check_drops never compares drops against additions, while the CLI does (acceptance_cmd.py:443); (5) #654/#656 wording + missing test on _refuse_unknown_levels/merge_levels; (6) #663/#676 are matrix-data chores, not code. They share a SURFACE (the acceptance edit helpers), not a cause. Per the brief's debugging rule, stopping to ask before fixing any.

<!-- fr:journal kind=ruled-out scope=debug id=829530044400 created=2026-10-02T18:29:28+00:00 -->
### 829530044400 · ruled-out · One root cause for the batch

Ruled out: the members share a surface (the acceptance edit helpers), not a cause. Operator chose to fix all in one PR, each with its own failing test, and chose name anchors (not a line-target tripwire) for #531.

<!-- fr:journal kind=root-cause scope=debug id=fccfc573a40b created=2026-10-02T18:29:32+00:00 -->
### fccfc573a40b · root-cause · #470: render_row_block hardcodes a two-space item indent

edit.render_row_block prefixed every line with two spaces whatever the file used; under flush-left rows the new item nests into the previous row's mapping, so the engine's final parse refuses and rolls back.

<!-- fr:journal kind=root-cause scope=debug id=9bad1c05c48c created=2026-10-02T18:29:34+00:00 -->
### 9bad1c05c48c · root-cause · #531: nothing interprets a .py fragment

split_ref carries the fragment through; check strips it for existence only; reports render it raw. A line anchor's rot is therefore invisible. Measured live: 27 of 78 #L anchors had slid (several onto helpers), 3 name anchors named tests #628 deleted, and one ref had fused two refs with a comma — all passing check.

<!-- fr:journal kind=root-cause scope=debug id=4cf7889208cc created=2026-10-02T18:29:37+00:00 -->
### 4cf7889208cc · root-cause · #769: set-status's subject is always '{old} → {new}'

acceptance_cmd.set_status_cmd and the record engine's report line format the transition unconditionally, so a levels-only move logs 'skipped → skipped'.

<!-- fr:journal kind=root-cause scope=debug id=8416c0313aac created=2026-10-02T18:29:39+00:00 -->
### 8416c0313aac · root-cause · #655: _check_drops never compares drops with additions

The CLI refuses a ref named in both --level and --drop-level before building the record; the engine, reachable without the CLI, did not.

<!-- fr:journal kind=finding scope=debug id=f-fixes created=2026-10-02T18:29:41+00:00 state=fixed -->
### f-fixes · finding [fixed] · Fixed: all eight members, failing tests first

tests/unit/test_acceptance_integrity.py (committed red in 59421ee7). Fixes: indentation derived from the existing items (#470); fr.acceptance.anchors + check/engine/report changes + Repair matrix-name-anchors, with Repair gaining companions/also_wrote so it regenerates the committed reports (#531); edit.describe_move (#769); refusal wording (#654); merge_levels test (#656); engine contradiction refusal (#655); rows re-pointed through the record engine (#663, #676, and the 27 rotted/4 dead anchors). run-records-observed-models moved ci → skipped: its served-model-over-alias half lost its only test in #628.

<!-- fr:journal kind=review scope=debug id=8b8d13e0b3a6 created=2026-10-02T18:47:11+00:00 -->
### 8b8d13e0b3a6 · review · Independent review of the branch: 5 findings, 4 fixed

A separate read-only reviewer context raised: (1) replace_row dropped a column-0 section comment between rows, a regression from #470's scan change — fixed + test; (2) the repair's regex had no left boundary (own repo 'fr' inside 'super-fr:') — fixed + test; (3) the repair wrote the matrix before rendering reports, so a failed render left it half-done and never retried — fixed + test; (5) the gate runs the predicate per command — a textual .py#L pre-check skips parse and git. Not fixed: (4) is_test_node follows pytest's default names, so a unittest-style 'FooTests' class is never a conversion target. Its anchors are left for a human and check names them, so there is no mis-conversion; it is a known limit, deliberately conservative.
