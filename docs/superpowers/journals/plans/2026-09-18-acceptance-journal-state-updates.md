# Journal: 2026-09-18-acceptance-journal-state-updates

<!-- fr:journal kind=decision scope=plan id=plan-shape created=2026-09-18T11:05:02 -->
### plan-shape · decision · Sequence acceptance then journal mutations

Acceptance owns the report-regeneration mutation pattern, so it is the walking skeleton. Journal updates follow with parser-preserving rewrite and duplicate safety.

<!-- fr:journal kind=decision scope=plan id=acceptance-mutation-design created=2026-09-18T11:08:25 -->
### acceptance-mutation-design · decision · Validated textual row replacement

Phase 1 validates requested status and evidence through the Row/ref grammar before replacing only the selected YAML row. PyYAML node marks retain the matrix header and untouched row text; report rendering remains best-effort after a valid write.

<!-- fr:journal kind=review scope=plan id=phase-1-review created=2026-09-18T11:09:01 -->
### phase-1-review · review · Phase 1 review passed

Reviewed acceptance mutation implementation and focused tests. Both explicit commands validate before targeted rewrites, preserve comments, retain add duplicate rejection, and use the shared best-effort report sync path.

<!-- fr:journal kind=finding scope=plan id=acceptance-row-comments-lost created=2026-09-18T11:13:13 phase=1 state=fixed -->
### acceptance-row-comments-lost · finding [fixed] · Row comments lost by YAML reconstruction (phase 1)

Review found that serializing the target row with PyYAML stripped inline, block, and surrounding comments. Resolved by applying source-span scalar replacements for status and notes and a targeted insertion for added level evidence, leaving existing row text and comments intact.

<!-- fr:journal kind=decision scope=plan id=acceptance-row-comments-resolution created=2026-09-18T11:13:14 phase=1 -->
### acceptance-row-comments-resolution · decision · Comment-preserving acceptance mutations (phase 1)

Regression coverage exercises both set-status and add-level against field, nested-level, inline, and surrounding comments. Mutations now preserve those comments while retaining validation, rollback, and report synchronization.

<!-- fr:journal kind=finding scope=plan id=acceptance-level-alias-hazard created=2026-09-18T11:16:56 phase=1 state=fixed -->
### acceptance-level-alias-hazard · finding [fixed] · Aliased level nodes can target another row (phase 1)

Review found add-level relied on PyYAML-resolved node marks, so a selected row using levels: *alias could insert evidence into the anchor owner. Resolved by rejecting aliases and anchors in every mutable field before source-span edits.

<!-- fr:journal kind=decision scope=plan id=acceptance-alias-resolution created=2026-09-18T11:16:57 phase=1 -->
### acceptance-alias-resolution · decision · Fail closed on mutable YAML aliases and anchors (phase 1)

The comment-preserving mutation path inspects each mutable field source expression and returns exit 2 without writes when it carries an alias or anchor. The regression proves an aliased target levels field remains byte-identical.

<!-- fr:journal kind=finding scope=plan id=acceptance-optional-fields created=2026-09-18T11:20:51 phase=1 state=fixed -->
### acceptance-optional-fields · finding [fixed] · Optional mutable fields could not be materialized (phase 1)

Review found add-level rejected valid rows that omitted levels or used levels: {}, and set-status --note rejected rows without notes. Resolved with selected-row source-span insertions before status and expansion of an empty levels mapping, preserving neighboring comments.

<!-- fr:journal kind=decision scope=plan id=acceptance-optional-fields-resolution created=2026-09-18T11:20:51 phase=1 -->
### acceptance-optional-fields-resolution · decision · Materialize optional acceptance fields locally (phase 1)

Focused regressions cover omitted levels, empty levels: {}, and omitted notes. New fields are inserted only inside the selected row at its status boundary; mutable alias and anchor expressions remain fail-closed.

<!-- fr:journal kind=finding scope=plan id=acceptance-existing-level-loss created=2026-09-18T11:23:57 phase=1 state=fixed -->
### acceptance-existing-level-loss · finding [fixed] · Adding evidence duplicated an existing level key (phase 1)

Review found add-level appended a second requested level key when that level already existed, allowing YAML parsing to discard old evidence. Resolved by extending the existing flow or block sequence in place and checking the reloaded selected row equals the intended replacement.

<!-- fr:journal kind=decision scope=plan id=acceptance-existing-level-resolution created=2026-09-18T11:23:57 phase=1 -->
### acceptance-existing-level-resolution · decision · Extend existing evidence sequences in place (phase 1)

Focused tests cover commented flow and block sequences and prove both old and new refs survive. Post-write validation now compares the selected reloaded Row with the requested replacement, rolling back on a mismatch.

<!-- fr:journal kind=finding scope=plan id=acceptance-flow-levels-and-duplicates created=2026-09-18T11:27:10 phase=1 state=fixed -->
### acceptance-flow-levels-and-duplicates · finding [fixed] · Flow mappings and duplicate keys bypassed lifecycle safety (phase 1)

Final audit found add-level rejected valid flow levels mappings and did not cover empty level sequences; matrix loading also accepted duplicate YAML keys before mutation. Resolved by extending flow mapping/sequence edits, retaining comments, and using the shared strict loader in load_matrix.

<!-- fr:journal kind=decision scope=plan id=acceptance-flow-levels-and-duplicates-resolution created=2026-09-18T11:27:10 phase=1 -->
### acceptance-flow-levels-and-duplicates-resolution · decision · Strict parse and complete levels collection support (phase 1)

The lifecycle commands now cover omitted levels, empty flow mappings, block mappings, flow mappings, empty sequences, flow sequences, and block sequences. load_matrix fails closed on any duplicate YAML mapping key before every CLI mutation; focused cases assert the source is byte-identical on rejection.

<!-- fr:journal kind=review scope=plan id=phase-1-final-review created=2026-09-18T11:27:27 -->
### phase-1-final-review · review · Phase 1 review passed after safety fixes

Independent reviews found and closed comment preservation, alias, optional fields, existing evidence, flow/empty collection, and duplicate YAML key hazards. Final focused suite passes.

<!-- fr:journal kind=discovery scope=plan id=journal-update-implementation created=2026-09-18T11:29:44 phase=2 -->
### journal-update-implementation · discovery · Journal finding updates preserve durable context (phase 2)

The update command resolves active or archived source journals, validates the complete parsed journal before writing, and rebuilds entry blocks through the canonical serializer while retaining the leading preamble and entry order.

<!-- fr:journal kind=review scope=plan id=phase-2-review created=2026-09-18T11:31:21 phase=2 -->
### phase-2-review · review · Phase 2 journal lifecycle review passed (phase 2)

Focused journal CLI and model tests confirm canonical finding-state rewrites, immutable metadata retention, preamble and order preservation, archived-source writes, duplicate-create rejection, and fail-closed validation without writes.

<!-- fr:journal kind=finding scope=plan id=journal-duplicate-id-review created=2026-09-18T11:33:40 phase=2 state=fixed -->
### journal-duplicate-id-review · finding [fixed] · Journal update accepted ambiguous source IDs (phase 2)

Review found duplicate source IDs parsed successfully, so update could rewrite multiple entries selected by the same ID.

Parser-level duplicate ID detection now rejects ambiguous journals before any update write; focused CLI and parser regressions prove byte-identical rejection.

<!-- fr:journal kind=finding scope=plan id=journal-scope-validation-review created=2026-09-18T11:33:40 phase=2 state=fixed -->
### journal-scope-validation-review · finding [fixed] · Journal update resolved paths before scope validation (phase 2)

Review found an invalid --scope reached the journal scope directory lookup and raised KeyError instead of returning a clean validation error.

Mutating journal commands validate scope before resolving paths, returning exit 2 with a clean message rather than KeyError.

<!-- fr:journal kind=finding scope=plan id=journal-truncated-delimiter-review created=2026-09-18T11:36:11 phase=2 state=fixed -->
### journal-truncated-delimiter-review · finding [fixed] · Truncated journal delimiters were treated as entry body (phase 2)

Final review found that parser scanning ignored delimiter-prefixed lines lacking the closing comment suffix, allowing update canonicalization to drop the truncated marker and following body content.

Every delimiter-prefixed line is now parsed as a delimiter candidate; an unterminated marker raises JournalParseError so update leaves the source byte-identical. Regression also pins render fail-open and check fail-closed.

<!-- fr:journal kind=review scope=plan id=phase-2-truncated-delimiter-review created=2026-09-18T11:36:48 phase=2 -->
### phase-2-truncated-delimiter-review · review · Final truncated-delimiter review passed (phase 2)

Parser scanning now rejects truncated delimiter candidates before canonical rewrite; CLI update preserves source bytes, render remains fail-open, and check remains fail-closed.

<!-- fr:journal kind=finding scope=plan id=journal-header-heading-review created=2026-09-18T11:38:09 phase=2 state=fixed -->
### journal-header-heading-review · finding [fixed] · Journal parser accepted ambiguous headers and globally scanned headings (phase 2)

Final review found unknown and repeated header fields were accepted, and title recovery could take a matching heading from preamble or prose rather than the entry block.

The parser now rejects unknown or duplicate header fields and derives each title only from that entry block’s canonical heading, validating its id, kind, state, and present phase before update can write.

Legacy finding headings whose state differs from their marker remain readable for render/check/handoff, but parse marks them rewrite-unsafe and journal update rejects the whole journal byte-identically.

<!-- fr:journal kind=review scope=plan id=phase-2-header-heading-review created=2026-09-18T11:39:13 phase=2 -->
### phase-2-header-heading-review · review · Final header and heading review passed (phase 2)

Strict header key and duplicate validation plus block-local canonical heading parsing prevent ambiguous metadata and title corruption during journal update rewrites.

<!-- fr:journal kind=review scope=plan id=phase-2-legacy-heading-compatibility-review created=2026-09-18T11:42:05 phase=2 -->
### phase-2-legacy-heading-compatibility-review · review · Final legacy heading compatibility audit passed (phase 2)

Archived marker-versus-heading state mismatches remain readable without modifying frozen artifacts. Journal update detects the private rewrite-safety marker and refuses canonical rewrites that would silently repair legacy text.

<!-- fr:journal kind=review scope=plan id=phase-2-final-review created=2026-09-18T11:43:24 -->
### phase-2-final-review · review · Phase 2 review passed

Independent review findings on duplicate IDs, invalid scopes, malformed delimiters, ambiguous headers/headings, and archived legacy state markers are resolved. Final compatibility audit found no findings.
