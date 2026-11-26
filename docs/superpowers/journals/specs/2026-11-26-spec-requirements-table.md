<!-- fr:journal-schema=4 -->
# Journal: 2026-11-26-spec-requirements-table

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-26T10:59:51+00:00 input=true -->
### brief · discovery · Operator brief

in the Spec document, the Requirements are not easily human-readable, when rendered by markdown previewers. Let's wrap them in a table please. Also, I want to understand how we are using fr-isolation now together with the various supported harnesses. Can we simplify/improve the isolation if we play with the harnesses, instead of doing our own thing?

<!-- fr:journal kind=decision scope=spec id=scope-table-only created=2026-11-26T16:04:45+00:00 decided_by=operator -->
### scope-table-only · decision · This spec covers the Requirements table only; the fr-isolation simplification gets its own brainstorm next

Operator chose "Table now, isolation next". The isolation map (marker, sentinel, three decision copies, WorktreeCreate takeover, per-harness gaps) informs a separate brainstorm on its own branch.

<!-- fr:journal kind=decision scope=spec id=migration-rewrites created=2026-11-26T16:04:45+00:00 decided_by=operator -->
### migration-rewrites · decision · The spec 1 -> 2 migration rewrites live R<n>. lists into the table

Operator chose "Rewrite to table" over stamp-only. The hop builds the body in memory, round-trips the parsed requirements, writes once, and leaves an unconvertible spec byte-identical and reported. Archived specs are never touched.

<!-- fr:journal kind=decision scope=spec id=verify-candidate created=2026-11-26T16:04:45+00:00 decided_by=operator -->
### verify-candidate · decision · Verification strategy is candidate

Operator chose candidate. A scenario installs the branch, migrates a fixture list spec and checks the installed fr reads the table to the same requirements. Gate developer; nothing post-merge.
