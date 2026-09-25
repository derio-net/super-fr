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

<!-- fr:journal kind=discovery scope=plan id=p2-live-gh-shapes created=2026-09-25T23:09:11 phase=2 -->
### p2-live-gh-shapes · discovery · Live-verified gh shapes behind the adapter and collect (2026-09-25, derio-net/super-fr, read-only) (phase 2)

The contents API resolves ref=HEAD to the default branch, so collect reads .fr/triage.yaml with ref HEAD and needs no default-branch lookup; an absent file answers 'Not Found (HTTP 404)', which collect treats as no config (any other forge failure propagates like the list calls). gh pr checks --required on a branch with none prints 'no required checks reported on the <branch> branch' (mapped to []); gh issue view --json comments returns {comments: [...]}. Not verified live: the exit-8 pending answer of gh pr checks (from gh's docs) — phase 4's live walk exercises it.

<!-- fr:journal kind=decision scope=plan id=p2-withdrawn-marker created=2026-09-25T23:09:12 phase=2 -->
### p2-withdrawn-marker · decision · A withdrawal comment uses its own marker prefix, fr-batch-withdrawn: (phase 2)

Spec §3.E says cancel posts 'a marker comment' and stale dispatch dates the 'fr-batch marker comment'. If both used <!-- fr-batch:<item> -->, a cancelled-then-redispatched batch would be dated by its withdrawal, and phase 3's --repair idempotency check would see the withdrawal as 'already posted'. So fr.triage.model defines batch_marker (<!-- fr-batch:<item> -->) and withdrawn_marker (<!-- fr-batch-withdrawn:<item> -->); the dispatch prefix never matches the withdrawn one. collect dates by the LATEST dispatch marker. Phase 3: repair/dispatch idempotency should treat a dispatch marker as present only when it is newer than the latest withdrawn marker for the same item, else a re-dispatch after cancel posts nothing.

<!-- fr:journal kind=discovery scope=plan id=p2-norefactor-t2 created=2026-09-25T23:09:12 phase=2 -->
### p2-norefactor-t2 · discovery · no-refactor-because P2.T2 (phase 2)

The collect additions are four small named functions (join_open, read_config, _with_marker, _batch_prs) called once each from collect_facts; the three test Forge doubles (FakeForge, the CLI and skeleton doubles) each gained the two new reads and a 404 read_file_at_ref, and FakeForge.anchor_reads() filters the config read out of the anchor-read assertions. Nothing duplicated remains to fold.

<!-- fr:journal kind=discovery scope=plan id=p2-refactor-t3 created=2026-09-25T23:12:48 phase=2 -->
### p2-refactor-t3 · discovery · P2.T3 refactor: the batches dumper relies on model_dump's field order (phase 2)

_dump_batches first merged the id back and re-ordered keys by Batch.model_fields; both were redundant (id has no default, model_dump keeps field order), so it is now one model_dump(exclude_defaults=True) per batch. Beyond the spec's listed load checks, Batch also refuses members in two repos (spec §6 non-goal: cross-repo batches) and lowercases its id before the slug check, which is what makes 'case-colliding batch ids' a real uniqueness check. Events use AwareDatetime so time-ordering can never compare naive with aware.

<!-- fr:journal kind=discovery scope=plan id=p2-t4-phase3-handoff created=2026-09-25T23:19:21 phase=2 -->
### p2-t4-phase3-handoff · discovery · What phase 2's verbs leave in place for phase 3's dispatch and merge (phase 2)

(1) fr/commands/triage_batch_cmd.py now exists and holds every batch verb; batch_app stays defined in triage_cmd.py, which imports triage_batch_cmd LAST (E402) so either module can load first. Phase 3 adds dispatch there, behind the find_spec soft point. (2) fr.triage.batch.resolve_launch(batch, config) already implements batch -> defaults.launch -> refuse, unit-tested; dispatch should call it with facts.config_for(repo). (3) fr.triage.batch.planned_merge_order is the BOARD's forecast only (explicit order, then id; shared files with later steps); spec §3.F's full order (non-adjacent overlaps, fewest overlaps, lowest tier) is phase 3's P3.T3 and should replace or refine it, then the board can call the same function. (4) batch_item_id(repo, id) spells <repo>/run/batch-<id> without importing fr_dispatch; a test pins it equal to run_item_id. (5) make_client(url) in triage_batch_cmd is the adapter factory tests replace; the URL's host comes from any collected issue URL of the repo. (6) cancel on a proposed batch appends the event only (it never reached the forge); cancel of cancelled/merged/partial/abandoned exits 2. A cancel event's time is max(now, last event) so clock skew never breaks the time-order load rule; dispatch should do the same.

<!-- fr:journal kind=discovery scope=plan id=p2-norefactor-t4 created=2026-09-25T23:19:22 phase=2 -->
### p2-norefactor-t4 · discovery · no-refactor-because P2.T4 (phase 2)

The verbs share their I/O through _load_state/_scope from triage_cmd and one _write (open-batch rule, then save_batches); the engine functions (suggest, planned_merge_order, withdrawn_already, resolve_launch) are pure in fr.triage.batch. The stale set is one function beside classify. Nothing duplicated remained after the tidy that removed local imports and asserts from the command module before commit.

<!-- fr:journal kind=discovery scope=plan id=p2-herdr-shapes created=2026-09-25T23:23:44 phase=2 -->
### p2-herdr-shapes · discovery · herdr CLI shapes behind HerdrRunner, and the one fixture that is not a capture (phase 2)

Captured live 2026-09-25 (read-only, inside the operator's herdr session): tab list/get and pane list print a JSON envelope {id, result:{...}, type}; herdr --skill documents that tab create returns .result.tab and .result.root_pane, and that agent names must match [a-z][a-z0-9_-]{0,31}. tests/fixtures/herdr/tab-list.json is a capture with the operator's tab labels replaced; tab-create.json is ASSEMBLED from the documented keys and captured object shapes, because a live capture would have opened a tab in the operator's session. Its README says so. HerdrRunner reads only .result.root_pane.pane_id from it; phase 4's live walk should replace it with a real capture.

<!-- fr:journal kind=decision scope=plan id=p2-dispatch-handle created=2026-09-25T23:23:45 phase=2 -->
### p2-dispatch-handle · decision · Runner.dispatch may return an opaque handle; herdr's cwd comes from an optional checkout payload key (phase 2)

Spec §3.C says HerdrRunner 'returns the pane id as the handle', but the Runner protocol typed dispatch -> None, so a str-returning implementation fails the mypy conformance assignment (r1-3). The protocol now types dispatch -> str | None (tick ignores the value; vk/cncd still return None). Separately, herdr needs --cwd <checkout> but the spec's payload lists only brief/harness/model/branch/reserved_version/issues; the runner reads an OPTIONAL payload key 'checkout' and falls back to its own cwd. Phase 3's dispatch should put the resolved --checkout path in payload['checkout'] and record the returned handle in the dispatch event.

<!-- fr:journal kind=discovery scope=plan id=p2-norefactor-t5 created=2026-09-25T23:23:45 phase=2 -->
### p2-norefactor-t5 · discovery · no-refactor-because P2.T5 (phase 2)

HerdrRunner was written with the shape S4 asks for: every herdr call goes through _run_herdr (one subprocess seam, JSON envelope parsed once, HerdrError carrying herdr's words) and HARNESSES is the one harness table (kind + model flag). The contract helpers are three functions (run_item, check_constructible, check_run_unit_contract) with no shared state. The package test's 'stub' wording was updated to the real runner.

<!-- fr:journal kind=finding scope=plan id=r2p-f1 created=2026-09-25T21:40:42 phase=2 state=open review_scope=in -->
### r2p-f1 · finding [open] (reviewer: in scope) · Redispatch after an abandoned PR still derives abandoned: batch_pr counts PRs from before the last dispatch (batch.py:104-118); _batch_prs on_branches short-circuit hides a later merged no-Closes PR (collect.py:505) (phase 2)

<!-- fr:journal kind=finding scope=plan id=r2p-f2 created=2026-09-25T21:40:42 phase=2 state=open review_scope=in -->
### r2p-f2 · finding [open] (reviewer: in scope) · triage-batch-state moved to ci while r2p-f1 exists; re-verify after the fix (phase 2)

<!-- fr:journal kind=finding scope=plan id=r2p-f3 created=2026-09-25T21:40:43 phase=2 state=open review_scope=in -->
### r2p-f3 · finding [open] (reviewer: in scope) · Collect's batch head lookups are unbounded: every batch with a dispatch event, including terminal ones, forever (§3.F says one per dispatched batch) (phase 2)

<!-- fr:journal kind=finding scope=plan id=r2p-f4 created=2026-09-25T21:40:43 phase=2 state=open review_scope=in -->
### r2p-f4 · finding [open] (reviewer: in scope) · Org collect aborts on one repo: invalid .fr/triage.yaml raises TriageError (not ForgeError) and list_issue_comments runs outside the per-repo try (phase 2)

<!-- fr:journal kind=finding scope=plan id=r2p-f5 created=2026-09-25T21:40:45 phase=2 state=open review_scope=in -->
### r2p-f5 · finding [open] (reviewer: in scope) · Duplicate member ids accepted (create/edit), then refused confusingly as 'in y, y' (phase 2)

<!-- fr:journal kind=finding scope=plan id=r2p-f6 created=2026-09-25T21:40:46 phase=2 state=open review_scope=in -->
### r2p-f6 · finding [open] (reviewer: in scope) · save_batches: quoted top-level "batches": key gets a duplicate appended; a file starting with --- becomes two documents and can never take a batch (phase 2)

<!-- fr:journal kind=finding scope=plan id=r2p-f7 created=2026-09-25T21:40:47 phase=2 state=open review_scope=in -->
### r2p-f7 · finding [open] (reviewer: in scope) · Concurrent edit to batches: is silently lost between load and save_batches (widest in cancel); no compare-before-write (phase 2)

<!-- fr:journal kind=finding scope=plan id=r2p-f8 created=2026-09-25T21:40:47 phase=2 state=open review_scope=in -->
### r2p-f8 · finding [open] (reviewer: in scope) · cancel can exit 2 after partial forge writes when a later op is unsupported; except Exception masks programming errors as forge failures (phase 2)

<!-- fr:journal kind=finding scope=plan id=r2p-f9 created=2026-09-25T21:40:48 phase=2 state=open review_scope=in -->
### r2p-f9 · finding [open] (reviewer: in scope) · HerdrRunner.dispatch leaves a labelled tab after a failure past tab create, which existing_dispatches then reports live forever (phase 2)

<!-- fr:journal kind=finding scope=plan id=r2p-f12a created=2026-09-25T21:40:49 phase=2 state=open review_scope=in -->
### r2p-f12a · finding [open] (reviewer: in scope) · fr_dispatch.testing contract uses bare assert (silent under python -O) (phase 2)

<!-- fr:journal kind=finding scope=plan id=r2p-f13 created=2026-09-25T21:40:49 phase=2 state=open review_scope=in -->
### r2p-f13 · finding [open] (reviewer: in scope) · Stale dispatch: empty createdAt raises in check (must always exit 0); an old closed linked PR suppresses stale reporting (phase 2)

<!-- fr:journal kind=finding scope=plan id=r2p-f10 created=2026-09-25T21:40:50 phase=3 state=open review_scope=in -->
### r2p-f10 · finding [open] (reviewer: in scope) · wait_required_checks returns at once on [] right after a push, causing a spurious protection stop in merge; pr_required_checks exit-8 branch unverified (phase 3)

<!-- fr:journal kind=finding scope=plan id=r2p-f11 created=2026-09-25T21:40:50 phase=3 state=open review_scope=in -->
### r2p-f11 · finding [open] (reviewer: in scope) · §3.J tripwire lists two files by name; phase-3 modules are uncovered, and merge/checkout need a git seam outside the subprocess ban (phase 3)
