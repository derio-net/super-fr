<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-run-write-ledger

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-27T09:26:27+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the task is itself the move; run_cmd keeps thin alias imports and nothing else to clean

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-27T09:37:31+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · Layering test's planted case asserts only a count of 6; `from .. import commands` and `import fr.commands as c` are never planted (phase 1)

tests/unit/test_run_writes_layering.py planted test. A spelling that stopped firing could hide behind another hit, weaker than R2's "in any spelling".

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-27T09:37:31+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · test_record_review_fixes.py leaves a stray blank line after the def signature once the local import was removed (phase 1)

tests/unit/test_record_review_fixes.py:110, cosmetic, caused by this diff.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-27T09:37:31+00:00 phase=1 state=open review_scope=out -->
### p1-r3 · finding [open] (reviewer: out of scope) · AST layering guard cannot see dynamic imports or transitive typer imports; pre-existing limit of the approach (phase 1)

importlib.import_module and the lazy fr.usage.capture import are not judged. R2 asks for a syntactic check; this is the approach's limit, as with test_import_direction.py.

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-11-27T09:37:31+00:00 phase=1 -->
### p1-review · review · phase 1 code review: 3 findings (2 in scope, fixed; 1 out of scope) (phase 1)

Independent reviewer: faithful byte-for-byte move, patch target retargeted to fr.run.writes.commit_records, #1511 refusal unchanged, budget 8895 vs 8875 lines. Findings p1-r1, p1-r2 (fixed in 8a925e2f9), p1-r3 (out of scope). Verdict: ready to merge.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-27T09:37:31+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: Layering test's planted case asserts only a count of 6; `from .. import commands` and `import fr.commands as c` are never planted (phase 1)

Each spelling is now planted on its own with its exact expected hit, including `from .. import commands` and `import fr.commands as c` (8a925e2f9).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-27T09:37:31+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: test_record_review_fixes.py leaves a stray blank line after the def signature once the local import was removed (phase 1)

Stray blank line removed (8a925e2f9).

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-27T09:37:31+00:00 phase=1 state=open resolves=p1-r3 out_of_scope=true -->
### p1-r3-resolved · finding [out-of-scope] · resolves p1-r3: AST layering guard cannot see dynamic imports or transitive typer imports; pre-existing limit of the approach (phase 1)

Not caused by this change. A syntactic import guard is what R2 requires and what the repo's other boundary guard (test_import_direction.py) does; dynamic and transitive imports are outside both.

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-27T09:41:55+00:00 -->
### lens-review-1 · review · lens review: docs-accuracy and tests, no findings

docs-accuracy: both touched pages are stamp-only and still true (workflow-shapes.md lines 51-54 hold against writes.py:265 and run_cmd.py:245-247). tests: every monkeypatch of a moved lookup intercepts where it is called; the conflict refusal stays CLI-tested (test_run_durability.py:219); the layering guard plants each spelling. Shape file matches the diff in both reviews.
