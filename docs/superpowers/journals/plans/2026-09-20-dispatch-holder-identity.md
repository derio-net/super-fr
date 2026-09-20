# Journal: 2026-09-20-dispatch-holder-identity

<!-- fr:journal kind=discovery scope=plan id=nr-p1t3 created=2026-09-20T13:40:42 phase=1 -->
### nr-p1t3 · discovery · no-refactor-because P1.T3 (phase 1)

P1.T3 writes no production code. It runs `fr migrate artifacts --yes` over this repo's own cursors (the dogfooding .claude/rules/artifact-versioning.md requires in the same PR as a stamp bump) and then the full CI gate. There is nothing authored to clean up; the refactor for phase 1's actual code lives in P1.T1.S3 and P1.T2.S3. Inventing a refactor step here would mean inventing something to change in generated artifacts, which the same rule forbids — migrated files are produced by the framework, never hand-edited.

<!-- fr:journal kind=discovery scope=plan id=nr-p6t2 created=2026-09-20T13:40:42 phase=6 -->
### nr-p6t2 · discovery · no-refactor-because P6.T2 (phase 6)

P6.T2's three steps are a one-line parity summary edit, a GENERATED mirror regeneration (`scripts/sync-opencode.py`), and matrix status flips through `fr acceptance set-status`. Two of the three produce files it is a documented error to hand-edit — sync-opencode.py overwrites its output and a CI tripwire catches drift, and the matrix rule says statuses move by command, never by hand. A refactor step over generated output is exactly the hand-edit those guards exist to prevent.

<!-- fr:journal kind=discovery scope=plan id=nr-p6t3 created=2026-09-20T13:40:43 phase=6 -->
### nr-p6t3 · discovery · no-refactor-because P6.T3 (phase 6)

P6.T3 is the release tail: `scripts/bump-version.py minor` (whose outputs are version-bearing manifests the repo forbids hand-editing), the explainer regeneration (whose .html carries a do-not-hand-edit banner and is produced by a renderer in another repo), and the full CI gate. The only authored prose is the explainer's .md, and its quality pass is inside S2 — the byte-for-byte unmodified re-render that must pass before the real render is the verification step, and it is stronger than a refactor step would be.
