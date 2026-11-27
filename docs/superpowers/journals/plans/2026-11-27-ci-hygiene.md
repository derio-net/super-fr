<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-ci-hygiene

<!-- fr:journal kind=discovery scope=plan id=ci-shards-partition-green-at-once created=2026-11-27T20:40:17+00:00 phase=1 -->
### ci-shards-partition-green-at-once · discovery · test_ci_shards partition test was green at once (phase 1)

P1.T4.S1 pins the coupling of the partition test to the ci.yml matrix shard count rather than catching a bug, so it passed immediately by design.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-27T20:40:17+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

nothing to clean: one permissions block added to ci.yml

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-27T20:40:17+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

nothing to clean: whole-file deletions and sentence removals

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-27T20:40:17+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

nothing to clean: docstring and token-set edits are the change itself

<!-- fr:journal kind=review scope=plan id=review-p1-1 created=2026-11-27T20:42:54+00:00 phase=1 -->
### review-p1-1 · review · phase 1 code review: no findings (phase 1)

Independent reviewer checked R1-R5 against spec, plan and the 21-file diff: both workflows and
every live mention retired; floors.py token set identical on 3.14, regex unchanged; shard test reads
the matrix; the UV_PYTHON and permissions tests read workflow-level keys only (job blocks cannot
satisfy them; `on:` quirk handled); no ci.yml job loses a permission it uses; level refs resolve.
Raised none. Orchestrator ran sync-opencode.py --check and sync-hermes.py --check: clean.
Notes below threshold: tests glob *.yml only (spec says *.yml); .test_durations keeps one deleted id (harmless).

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-27T20:44:38+00:00 -->
### lens-review-1 · review · lens review: docs-accuracy and security, no findings

docs-accuracy: both touched pages (fr-progress explainer, docs-currency stamp) true of the code; shape file matches the diff.
security: no ci.yml job without its own block uses a token beyond contents: read (no gh, GH_TOKEN, secrets or REST; artifacts/cache use the runtime token); the retirement removes a pull-requests: write job and a runtime pip install from a tag; UV_PYTHON pins widen nothing.
