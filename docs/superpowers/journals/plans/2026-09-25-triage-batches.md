# Journal: 2026-09-25-triage-batches

<!-- fr:journal kind=discovery scope=plan id=905f9846fce9 created=2026-09-25T20:38:46 phase=1 -->
### 905f9846fce9 · discovery · no-refactor-because P1.T1 (phase 1)

Red-only task: it writes failing tests and changes no production code, so there is nothing to refactor; the green task follows.

<!-- fr:journal kind=discovery scope=plan id=eb2d1827ddaf created=2026-09-25T20:38:48 phase=1 -->
### eb2d1827ddaf · discovery · no-refactor-because P1.T2 (phase 1)

Glue only (a schema literal, a list verb, a stub package and CI wiring); P1.T3 verifies it end to end and records a cleanup if one is needed.

<!-- fr:journal kind=discovery scope=plan id=d54428244b78 created=2026-09-25T20:38:51 phase=2 -->
### d54428244b78 · discovery · no-refactor-because P2.T6 (phase 2)

This task IS the phase's refactor and quality gate; a refactor step of a refactor step would be circular.

<!-- fr:journal kind=discovery scope=plan id=d92d3b3c2ec6 created=2026-09-25T20:38:52 phase=3 -->
### d92d3b3c2ec6 · discovery · no-refactor-because P3.T5 (phase 3)

Docs, skill prose, mirrors and the version bump: no production code is written, so there is nothing to refactor; the mirror and bump --check gates in P3.T6 cover correctness.

<!-- fr:journal kind=discovery scope=plan id=3cc7e3015849 created=2026-09-25T20:38:54 phase=3 -->
### 3cc7e3015849 · discovery · no-refactor-because P3.T6 (phase 3)

This task IS the phase's refactor and quality gate; a refactor step of a refactor step would be circular.

<!-- fr:journal kind=decision scope=plan id=model-override-opus-5-5 created=2026-09-25T22:44:49 -->
### model-override-opus-5-5 · decision · Operator: Opus 5.5 on every tier for this run

Operator (2026-09-25): run implementation with Opus 5.5 on every tier. Standing bindings (claude-code: mechanical=haiku-4.5, standard=sonnet-5, hard=opus-5.5) are left untouched; each dispatch passes Opus 5.5 explicitly and records it with fr run claim --model claude-opus-5-5.

<!-- fr:journal kind=discovery scope=plan id=31dca047ed37 created=2026-09-25T22:49:07 phase=1 -->
### 31dca047ed37 · discovery · Schema 2 judgements were pinned as refused by two existing tests (phase 1)

tests/unit/test_triage_cli.py::test_a_bad_judgements_file_exits_2_naming_it and tests/unit/test_triage_model.py (renamed to test_schema_3_in_judgements_is_refused_naming_the_file) used schema 2 as the unknown version. Both now use schema 3; the loader reads JUDGEMENTS_READS = (1, 2) while JUDGEMENTS_SCHEMA stays 1 as the write version until phase 2.

<!-- fr:journal kind=discovery scope=plan id=f531198b3826 created=2026-09-25T22:49:10 phase=1 -->
### f531198b3826 · discovery · Red run masked a malformed WorkItem id in the herdr stub test (phase 1)

P1.T1.S3's red run failed on ModuleNotFoundError: fr_herdr before any WorkItem was built, so the test's first ids (super-fr/<unit>) never reached WorkItem.__post_init__, which rejects them. Found in green; the test now uses one well-formed id per unit from the work_item grammar plus a guard that every Unit has an id. For phase 2's runner contract tests: build items through item_id/run_item_id.

<!-- fr:journal kind=discovery scope=plan id=162b015f5356 created=2026-09-25T22:49:11 phase=1 -->
### 162b015f5356 · discovery · fr-herdr wiring: root deps/sources and --cov added; README/HERMES lists and import-direction test not yet updated (phase 1)

A workspace member's fr.runners entry point is only registered once the root pyproject depends on it (dependencies + [tool.uv.sources]); --cov=fr_herdr was added to addopts too. Left for later phases: README.md/HERMES.md package lists, AGENTS.md repo-shape prose, and tests/unit/test_import_direction.py peer rules (fr_dispatch must not import fr_herdr; fr_herdr vs fr_vk/fr_cncd).

<!-- fr:journal kind=discovery scope=plan id=6b7920f90e3e created=2026-09-25T22:54:18 phase=1 -->
### 6b7920f90e3e · discovery · no-refactor-because P1.T3 (phase 1)

Verification-only task; the loader change (a read-versions tuple in _check_schema) and the stub runner needed no cleanup pass. Full suite, ruff, mypy (incl. packages/fr-herdr/src) and bump-version --check all green.

<!-- fr:journal kind=finding scope=plan id=r1-1 created=2026-09-25T20:59:03 phase=1 state=fixed review_scope=in -->
### r1-1 · finding [fixed] (reviewer: in scope) · Schema-1 files could carry batches (spec 3.A) — Judgements now refuses batches unless schema 2; test added (phase 1)

<!-- fr:journal kind=finding scope=plan id=r1-2 created=2026-09-25T20:59:04 phase=1 state=fixed review_scope=in -->
### r1-2 · finding [fixed] (reviewer: in scope) · No import-boundary tripwire for fr_herdr — fr/fr_dispatch never import fr_herdr; fr_herdr never imports fr.triage (self-tested pattern) (phase 1)

<!-- fr:journal kind=finding scope=plan id=r1-3 created=2026-09-25T20:59:05 phase=1 state=fixed review_scope=in -->
### r1-3 · finding [fixed] (reviewer: in scope) · Nothing checked HerdrRunner against the Runner protocol — TYPE_CHECKING assignment; mypy verified to fail on drift (phase 1)

<!-- fr:journal kind=finding scope=plan id=r1-4 created=2026-09-25T20:59:06 phase=1 state=fixed review_scope=in -->
### r1-4 · finding [fixed] (reviewer: in scope) · HERMES.md mypy line omitted packages/fr-herdr/src — added (phase 1)

<!-- fr:journal kind=finding scope=plan id=r1-docs created=2026-09-25T20:59:06 phase=3 state=open review_scope=in -->
### r1-docs · finding [open] (reviewer: in scope) · README package table, HERMES.md package prose and an AGENTS.md fr-herdr bullet are owned by no phase — P3.T5.S2 widened to own them (phase 3)

<!-- fr:journal kind=finding scope=plan id=r1-5 created=2026-09-25T20:59:07 phase=1 state=open review_scope=out -->
### r1-5 · finding [open] (reviewer: out of scope) · fr_cncd missing from test_fr_imports_no_siblings banned set (pre-existing) (phase 1)

<!-- fr:journal kind=finding scope=plan id=r1-5-resolved created=2026-09-25T20:59:07 state=open resolves=r1-5 out_of_scope=true answered_by=agent -->
### r1-5-resolved · finding [out-of-scope] · resolves r1-5: fr_cncd missing from test_fr_imports_no_siblings banned set (pre-existing)

Pre-existing gap in test_import_direction.py, not caused by this change.

<!-- fr:journal kind=finding scope=plan id=r1-6 created=2026-09-25T20:59:08 phase=1 state=open review_scope=out -->
### r1-6 · finding [open] (reviewer: out of scope) · Registering herdr under fr.runners lets fr apply --to herdr pass the runner-name check and project runner:herdr onto phase issues it will never take (phase 1)

<!-- fr:journal kind=finding scope=plan id=r1-6-resolved created=2026-09-25T20:59:09 state=open resolves=r1-6 out_of_scope=true answered_by=agent -->
### r1-6-resolved · finding [out-of-scope] · resolves r1-6: Registering herdr under fr.runners lets fr apply --to herdr pass the runner-name check and project runner:herdr onto phase issues it will never take

Follows from the spec's decision to register herdr under fr.runners (d2); herdr refuses phase units in can_dispatch, so the items are refused visibly, not lost. Listed in the PR for the operator.

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-09-25T20:59:09 phase=1 -->
### review-phase-1 · review · Phase 1 review (feature-dev:code-reviewer, separate context): 7 findings (phase 1)

In scope and fixed: r1-1, r1-2, r1-3, r1-4. In scope, moved to phase 3: r1-docs. Out of scope: r1-5, r1-6. No correctness bug found; schema-2 downgrade on write not possible in this phase (nothing writes judgements yet).

<!-- fr:journal kind=discovery scope=plan id=p2-norefactor-t1 created=2026-09-25T23:03:44 phase=2 -->
### p2-norefactor-t1 · discovery · no-refactor-because P2.T1 (phase 2)

The one reusable gh call (the head-branch PR list) went straight into fr.gh as list_prs_by_head beside list_prs/list_open_prs; the remaining new RealGhClient methods each shape a different gh JSON document once, so a shared helper would only rename _run_gh+json.loads. The unsupported glab/tea side is one mixin (fr.ghclient.UnsupportedBatchOps) with one raising method per operation, so there is no duplication to remove. GhError now keeps stdout, because gh pr checks answers on exit 8.
