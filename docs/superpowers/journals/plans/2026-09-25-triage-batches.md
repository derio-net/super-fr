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

<!-- fr:journal kind=finding scope=plan id=r2p-f12b created=2026-09-25T21:40:51 phase=3 state=open review_scope=in -->
### r2p-f12b · finding [open] (reviewer: in scope) · Test Plan 4's can_dispatch-before-preflight ordering is exercised nowhere yet; phase 3 dispatch must test it (phase 3)

<!-- fr:journal kind=finding scope=plan id=r2p-handle created=2026-09-25T21:40:51 phase=3 state=open review_scope=in -->
### r2p-handle · finding [open] (reviewer: in scope) · DispatchEvent.handle is a required str but Runner.dispatch may return None; phase 3 must map None explicitly (phase 3)

<!-- fr:journal kind=finding scope=plan id=r2p-f14 created=2026-09-25T21:40:52 phase=3 state=open review_scope=in -->
### r2p-f14 · finding [open] (reviewer: in scope) · fr-triage SKILL.md still tells agents to write schema: 1 (lines 48, 65) (phase 3)

<!-- fr:journal kind=finding scope=plan id=r2p-envtest created=2026-09-25T21:40:53 phase=2 state=open review_scope=out -->
### r2p-envtest · finding [open] (reviewer: out of scope) · test_install_bridge_flag_writes_wrapper fails in the container: the container's uv-tool fr python cannot import fr_vk.bridge (phase 2)

<!-- fr:journal kind=finding scope=plan id=r2p-envtest-resolved created=2026-09-25T23:41:30 state=open resolves=r2p-envtest out_of_scope=true answered_by=agent -->
### r2p-envtest-resolved · finding [out-of-scope] · resolves r2p-envtest: test_install_bridge_flag_writes_wrapper fails in the container: the container's uv-tool fr python cannot import fr_vk.bridge

install.sh is byte-identical to main and the test passes on the host; in the container, install.sh --install-bridge resolves the container's uv-tool fr python, which was installed without fr_vk. A devcontainer environment gap, not caused by this change.

<!-- fr:journal kind=finding scope=plan id=r2p-f9-resolved created=2026-09-25T23:45:13 state=fixed resolves=r2p-f9 answered_by=agent -->
### r2p-f9-resolved · finding [fixed] · resolves r2p-f9: HerdrRunner.dispatch leaves a labelled tab after a failure past tab create, which existing_dispatches then reports live forever

HerdrRunner.dispatch wraps everything after tab create; on any failure it runs herdr tab close <tab_id> (best effort; a close failure never masks the original) and re-raises. Tests: test_fr_herdr_runner.py::test_a_failure_after_tab_create_closes_the_tab_and_reraises[start|prompt], ::test_a_failed_tab_close_does_not_mask_the_original_error. Commit 8a892abe.

<!-- fr:journal kind=finding scope=plan id=r2p-f12a-resolved created=2026-09-25T23:45:14 state=fixed resolves=r2p-f12a answered_by=agent -->
### r2p-f12a-resolved · finding [fixed] · resolves r2p-f12a: fr_dispatch.testing contract uses bare assert (silent under python -O)

fr_dispatch.testing checks go through _require(ok, msg), which raises AssertionError explicitly; no bare assert remains. Tests: test_run_unit_runner_contract.py::test_the_contract_still_bites_under_python_dash_o (child interpreter with -O), ::test_the_contract_module_has_no_bare_assert. Commit 5bf5bf95.

<!-- fr:journal kind=finding scope=plan id=r2p-f5-resolved created=2026-09-25T23:46:04 state=fixed resolves=r2p-f5 answered_by=agent -->
### r2p-f5-resolved · finding [fixed] · resolves r2p-f5: Duplicate member ids accepted (create/edit), then refused confusingly as 'in y, y'

Batch's ids validator refuses a key that appears more than once after normalisation ('a batch lists <key> more than once'); edit --add-issue no longer silently drops an existing member, so the model refuses it too. Tests: test_triage_batch_model.py::test_a_member_listed_twice_is_refused_naming_it, test_triage_batch_verbs.py::test_create_refuses_a_member_given_twice_and_writes_nothing, ::test_edit_refuses_adding_a_member_twice[member|twice].

<!-- fr:journal kind=finding scope=plan id=r2p-f6-resolved created=2026-09-25T23:48:34 state=fixed resolves=r2p-f6 answered_by=agent -->
### r2p-f6-resolved · finding [fixed] · resolves r2p-f6: save_batches: quoted top-level "batches": key gets a duplicate appended; a file starting with --- becomes two documents and can never take a batch

_TOP_KEY matches plain and quoted top-level keys; _body_bounds puts a prepended schema line after a leading --- (and %directives/comments) and appended batches before a trailing ..., so the file stays one document; all other bytes are kept. Tests: test_triage_batch_model.py::test_a_quoted_batches_key_is_replaced_not_duplicated, ::test_a_leading_document_marker_stays_one_document[plain|quoted|directive], ::test_a_document_end_marker_keeps_the_batches_inside_the_document, ::test_a_prepended_key_goes_after_the_document_start, ::test_a_write_keeps_every_other_byte. Commit c1422709.

<!-- fr:journal kind=finding scope=plan id=r2p-f7-resolved created=2026-09-25T23:48:34 state=fixed resolves=r2p-f7 answered_by=agent -->
### r2p-f7-resolved · finding [fixed] · resolves r2p-f7: Concurrent edit to batches: is silently lost between load and save_batches (widest in cancel); no compare-before-write

save_batches(path, batches, *, read=...) re-loads the file's current batches and refuses with 'judgements.yaml changed since it was read; re-run' (exit 2 from every verb via _write) when they differ from what the verb loaded; the file is left untouched. Tests: test_triage_batch_model.py::test_a_write_over_batches_changed_since_they_were_read_is_refused, test_triage_batch_verbs.py::test_cancel_refuses_to_overwrite_batches_changed_while_it_ran. Commit c1422709.

<!-- fr:journal kind=finding scope=plan id=r2p-f8-resolved created=2026-09-25T23:50:17 state=fixed resolves=r2p-f8 answered_by=agent -->
### r2p-f8-resolved · finding [fixed] · resolves r2p-f8: cancel can exit 2 after partial forge writes when a later op is unsupported; except Exception masks programming errors as forge failures

cancel now reads every member's comments before any write (the read is the only batch op glab/tea declare unsupported), so UnsupportedForgeOperation exits 2 with no label removed and no comment posted; per-member failures are caught as fr.hostclient.FORGE_ERRORS (GhError, GlabError, TeaError) only, so a programming error raises. Tests: test_triage_batch_verbs.py::test_cancel_probes_an_unsupported_backend_before_any_write, ::test_a_programming_error_during_cancel_is_not_reported_as_a_forge_failure (the existing forge-failure exit-1 test still passes with FakeGhError now a GhError).

<!-- fr:journal kind=finding scope=plan id=r2p-f13-resolved created=2026-09-25T23:51:33 state=fixed resolves=r2p-f13 answered_by=agent -->
### r2p-f13-resolved · finding [fixed] · resolves r2p-f13: Stale dispatch: empty createdAt raises in check (must always exit 0); an old closed linked PR suppresses stale reporting

check.stale_dispatches parses marker and collected_at through _aware(): missing, unparseable or naive times are skipped, so check always exits 0; only an OPEN or MERGED linked PR suppresses the report. collect's _with_marker ignores a marker comment with an empty created_at. Tests: test_triage_batch_verbs.py::test_an_unreadable_marker_time_is_skipped_never_raised[''|not-a-date|naive] (also runs the check command, exit 0), ::test_a_closed_unmerged_linked_pr_does_not_hide_a_stale_dispatch, ::test_a_merged_linked_pr_is_not_stale; test_triage_facts_schema3.py::test_a_marker_with_no_created_at_gives_no_dispatch_time.

<!-- fr:journal kind=finding scope=plan id=r2p-f4-resolved created=2026-09-25T23:52:35 state=fixed resolves=r2p-f4 answered_by=agent -->
### r2p-f4-resolved · finding [fixed] · resolves r2p-f4: Org collect aborts on one repo: invalid .fr/triage.yaml raises TriageError (not ForgeError) and list_issue_comments runs outside the per-repo try

collect_facts reads each fr:in-progress issue's comments (_marker_at) inside the per-repo try, which now catches TriageError (ForgeError and read_config's invalid-config refusal): org scope records Skipped(repo, reason) and collects the rest; repo scope re-raises. Tests: test_triage_facts_schema3.py::test_org_scope_skips_a_repo_whose_config_is_invalid, ::test_org_scope_skips_a_repo_whose_comment_read_fails, ::test_repo_scope_still_fails_loudly_on_a_comment_read (plus the existing repo-scope malformed-config refusal).

<!-- fr:journal kind=finding scope=plan id=r2p-f1-resolved created=2026-09-25T23:56:40 state=fixed resolves=r2p-f1 answered_by=agent -->
### r2p-f1-resolved · finding [fixed] · resolves r2p-f1: Redispatch after an abandoned PR still derives abandoned: batch_pr counts PRs from before the last dispatch (batch.py:104-118); _batch_prs on_branches short-circuit hides a later merged no-Closes PR (collect.py:505)

PR_LIST_FIELDS reads createdAt; PullRequest.created_at (optional; FACTS_SCHEMA stays 3). batch_pr keeps only PRs with created_at >= the last dispatch's at (unknown creation is kept), and collect's _batch_prs skips the head lookup only when a collected PR of THIS dispatch is on the branch. Tests: test_triage_batch_model.py::test_a_redispatch_after_an_abandoned_pr_is_dispatched, ::test_a_new_pr_after_the_redispatch_is_pr_open, ::test_a_merged_no_closes_pr_after_the_redispatch_is_found, ::test_a_pr_created_exactly_at_the_dispatch_belongs_to_it; test_triage_facts_schema3.py::test_a_pr_carries_its_created_at, ::test_a_linked_pr_from_before_the_dispatch_does_not_skip_the_lookup. Commit e1e677d6.

<!-- fr:journal kind=finding scope=plan id=r2p-f3-resolved created=2026-09-25T23:56:40 state=fixed resolves=r2p-f3 answered_by=agent -->
### r2p-f3-resolved · finding [fixed] · resolves r2p-f3: Collect's batch head lookups are unbounded: every batch with a dispatch event, including terminal ones, forever (§3.F says one per dispatched batch)

collect passes the previous facts.json's batch_prs as known_batch_prs; a batch whose known PR of the current dispatch is MERGED or CLOSED is terminal: that PR is carried into the new batch_prs and its branch is not looked up. batch_branches now carry the dispatch time. Tests: test_triage_facts_schema3.py::test_a_batch_already_terminal_in_the_previous_facts_costs_no_lookup[MERGED|CLOSED], ::test_a_known_pr_that_is_not_terminal_for_this_dispatch_is_looked_up_again[earlier|open], ::test_a_second_collect_does_not_look_up_a_batch_found_merged_by_the_first (3 collects, 1 lookup). Commit e1e677d6.

<!-- fr:journal kind=finding scope=plan id=r2p-f2-resolved created=2026-09-25T23:57:06 state=fixed resolves=r2p-f2 answered_by=agent -->
### r2p-f2-resolved · finding [fixed] · resolves r2p-f2: triage-batch-state moved to ci while r2p-f1 exists; re-verify after the fix

Re-verified after r2p-f1: every derived stage incl. redispatch-after-abandoned is now covered, so status ci holds. Row notes updated with fr acceptance set-status (ci -> ci) naming test_a_redispatch_after_an_abandoned_pr_is_dispatched, test_a_new_pr_after_the_redispatch_is_pr_open, test_a_merged_no_closes_pr_after_the_redispatch_is_found and test_triage_facts_schema3.py::test_a_linked_pr_from_before_the_dispatch_does_not_skip_the_lookup; unit level test_triage_facts_schema3.py added. fr acceptance check passes.

<!-- fr:journal kind=review scope=plan id=review-phase-2 created=2026-09-26T00:08:58 phase=2 -->
### review-phase-2 · review · Phase 2 review (general-purpose reviewer with shell, separate context): 13 findings + 1 out of scope (phase 2)

In scope, fixed with tests: r2p-f1 (medium: redispatch after abandoned PR derived abandoned), r2p-f2, r2p-f3, r2p-f4, r2p-f5, r2p-f6, r2p-f7, r2p-f8, r2p-f9, r2p-f12a, r2p-f13. Filed against phase 3: r2p-f10, r2p-f11, r2p-f12b, r2p-handle, r2p-f14. Out of scope: r2p-envtest (container-only uv-tool fr lacks fr_vk; install.sh unchanged, passes on host). Implementer decisions p2-dispatch-handle and p2-withdrawn-marker judged sound; privacy clean.

<!-- fr:journal kind=finding scope=plan id=r2p-f12b-resolved created=2026-09-26T00:19:49 state=fixed resolves=r2p-f12b answered_by=agent -->
### r2p-f12b-resolved · finding [fixed] · resolves r2p-f12b: Test Plan 4's can_dispatch-before-preflight ordering is exercised nowhere yet; phase 3 dispatch must test it

dispatch --yes calls runner.can_dispatch before preflight/existing_dispatches/dispatch; a refusal reaches no backend call. Tests: test_triage_batch_dispatch.py::test_can_dispatch_is_consulted_before_preflight (calls == [can_dispatch]) and ::test_the_protocol_calls_run_in_the_spec_order

<!-- fr:journal kind=finding scope=plan id=r2p-handle-resolved created=2026-09-26T00:19:50 state=fixed resolves=r2p-handle answered_by=agent -->
### r2p-handle-resolved · finding [fixed] · resolves r2p-handle: DispatchEvent.handle is a required str but Runner.dispatch may return None; phase 3 must map None explicitly

A None handle from Runner.dispatch is recorded as the item id (the runner's own identity for the dispatch, which existing_dispatches matches). Test: test_triage_batch_dispatch.py::test_a_runner_without_a_handle_records_the_item_id

<!-- fr:journal kind=decision scope=plan id=p3-reserve-order created=2026-09-26T00:19:58 phase=3 -->
### p3-reserve-order · decision · Dispatch-time reservation is max(source, every live reservation) + bump; explicit order is honoured at merge (phase 3)

Spec 3.D says both 'dispatch-time order is explicit order, then dispatch sequence' and 'the reservation is the next version after the highest of (source, every live reservation)'. Read literally together they conflict when a batch with order 1 is dispatched after an unordered one. Chosen: the formula. Reusing a number already briefed to another live run would make two runs build the same version; a monotonic reservation never does. The explicit order is a merge-time constraint: batch merge's reconcile (3.F step 3b) re-slots any PR whose version is not its slot in the real order. Tests: test_triage_batch_version.py::test_the_reservation_follows_the_highest_live_reservation, ::test_slots_follow_merge_order_and_each_batchs_bump; test_triage_batch_dispatch.py::test_successive_dispatches_reserve_successive_versions.

<!-- fr:journal kind=finding scope=plan id=r2p-f10-resolved created=2026-09-26T00:25:01 state=fixed resolves=r2p-f10 answered_by=agent -->
### r2p-f10-resolved · finding [fixed] · resolves r2p-f10: wait_required_checks returns at once on [] right after a push, causing a spurious protection stop in merge; pr_required_checks exit-8 branch unverified

wait_required_checks takes grace (default 120 s): an empty answer inside it is 'not registered yet' and is polled again; merge always waits after its own push. The exit-8 branch is pinned: pending JSON on stdout is read, exit 8 with no output raises rather than reading as []. Tests: test_forge_adapter_batch_ops.py::test_wait_required_checks_waits_for_checks_to_appear_after_a_push, ::test_wait_required_checks_accepts_none_required_once_the_grace_passes, ::test_pr_required_checks_raises_on_a_pending_exit_with_no_output, ::test_pr_required_checks_reads_the_output_of_a_pending_exit

<!-- fr:journal kind=finding scope=plan id=r2p-f11-resolved created=2026-09-26T00:25:02 state=fixed resolves=r2p-f11 answered_by=agent -->
### r2p-f11-resolved · finding [fixed] · resolves r2p-f11: §3.J tripwire lists two files by name; phase-3 modules are uncovered, and merge/checkout need a git seam outside the subprocess ban

The 3.J tripwire globs packages/fr/src/fr/triage/batch*.py and commands/triage_batch*.py; git (and the repo-declared set/relock) run only in fr/triage/gitseam.py, which is outside the glob and has its own guard: no fr.gh/glab/tea/collect import, no gh/glab/tea literal, exactly two subprocess.run sites. Tests: test_forge_adapter_batch_ops.py::test_the_batch_globs_find_every_batch_module, ::test_no_batch_module_reaches_a_forge_cli_or_triage_forge[*], ::test_the_git_seam_runs_git_and_declared_commands_only

<!-- fr:journal kind=decision scope=plan id=p3-merge-method created=2026-09-26T00:25:03 phase=3 -->
### p3-merge-method · decision · batch merge takes --method (default squash); the adapter has no 'repo default merge method' read (phase 3)

Spec 3.F step 2 says pr_merge(..., method=<repo default>), but the 3.J adapter table adds no operation that reads a repo's allowed/default merge method, and adding one would widen the adapter beyond the spec. So merge takes --method merge|squash|rebase, default squash (this repo's own history is squash merges). A repo that disallows the method refuses the merge on the forge, which merge reports verbatim and stops on: a safe failure, never a silent different merge. Test: test_triage_batch_merge.py::test_an_up_to_date_pr_at_its_slot_merges_with_its_head (--method merge reaches pr_merge).

<!-- fr:journal kind=discovery scope=plan id=p3-version-files-overlap created=2026-09-26T00:27:54 phase=3 -->
### p3-version-files-overlap · discovery · Declared version files are excluded from merge-order overlaps and the forecast (phase 3)

Every batch PR bumps the repo's version files, so counting them made every pair of batches overlap: the 3.F rule 'not adjacent where avoidable' could never avoid anything and the board forecast listed pyproject.toml on every step. pr_open_queue now drops files matching the repo's version.files globs from each entry's overlap set (QueueEntry.files); merge resolves exactly those conflicts itself (3.F step 3). Test: test_triage_batch_merge.py::test_declared_version_files_are_not_overlaps.

<!-- fr:journal kind=discovery scope=plan id=p3-t4-green-first created=2026-09-26T00:27:54 phase=3 -->
### p3-t4-green-first · discovery · P3.T4's integration test passed on first run; mutation-checked instead (phase 3)

The execution path (scratch worktree, --theirs, set, commit, push, wait, cleanup) was written in batch_merge.py alongside P3.T3's refusals, so the real-git test was green when first run. To show it is not vacuous it was run against two mutations: skipping take_theirs (both tests red) and never removing the scratch worktree (the cleanup assertion red); both restored.

<!-- fr:journal kind=finding scope=plan id=r1-docs-resolved created=2026-09-26T00:29:48 state=fixed resolves=r1-docs answered_by=agent -->
### r1-docs-resolved · finding [fixed] · resolves r1-docs: README package table, HERMES.md package prose and an AGENTS.md fr-herdr bullet are owned by no phase — P3.T5.S2 widened to own them

README.md Components table gains an fr-herdr row; HERMES.md 'Where things are' names fr-herdr among the adapters; AGENTS.md gains an fr-herdr bullet under packages/ and documents the batch verbs in the fr/triage paragraph. Commit 892b9295 (docs, no test: prose)

<!-- fr:journal kind=finding scope=plan id=r2p-f14-resolved created=2026-09-26T00:29:49 state=fixed resolves=r2p-f14 answered_by=agent -->
### r2p-f14-resolved · finding [fixed] · resolves r2p-f14: fr-triage SKILL.md still tells agents to write schema: 1 (lines 48, 65)

fr-triage SKILL.md now says schema: 2 (loop step 3 and the example), documents batches/events, loop step 5 and the --yes rule; mirrors regenerated. Tests: test_fr_triage_skill_example.py::test_the_skill_teaches_schema_2_and_batches, ::test_the_skill_names_the_batch_verbs_and_the_yes_rule

<!-- fr:journal kind=discovery scope=plan id=p3-gate-fixes created=2026-09-26T00:41:56 phase=3 -->
### p3-gate-fixes · discovery · P3.T6 gate: the skill line cap and the older triage seam tripwire both caught phase-3 changes (phase 3)

The first full run had two failures, both from this phase: (1) test_skill_validation's 120-line cap — the batch additions took fr-triage/SKILL.md to 162 lines; condensed and reflowed to 120 with loop step 5, the --yes rule and schema 2 intact (the skill-example tests pin them). (2) test_triage_collect.py::test_fr_triage_touches_gh_only_in_collect banned subprocess across fr.triage except collect.py, independent of the 3.J batch tripwire; gitseam.py is now its second, narrower exception (subprocess allowed, fr.gh still banned). The targeted runs had been green: only the full suite saw either. Re-run: 5566 passed, 89 skipped, exit 0.

<!-- fr:journal kind=finding scope=plan id=r3-f1 created=2026-09-26T00:54:44 phase=3 state=open review_scope=in -->
### r3-f1 · finding [open] (reviewer: in scope) · HIGH: dispatch launches the runner, then the open-batch rule / compare-before-write refuses in _write: no event, no forge write, batch stuck (re-run says live, --repair refuses) (phase 3)

<!-- fr:journal kind=finding scope=plan id=r3-f2 created=2026-09-26T00:54:47 phase=3 state=open review_scope=in -->
### r3-f2 · finding [open] (reviewer: in scope) · HIGH: take_theirs checks out main's WHOLE version file, discarding the PR's other edits in it (e.g. a new dependency in pyproject.toml); exceeds d3 (phase 3)

<!-- fr:journal kind=finding scope=plan id=r3-f3 created=2026-09-26T00:54:49 phase=3 state=open review_scope=in -->
### r3-f3 · finding [open] (reviewer: in scope) · MEDIUM: batch merge never checks collected-config freshness (spec §3.I), yet runs its version.files/set/relock (phase 3)

<!-- fr:journal kind=finding scope=plan id=r3-f4 created=2026-09-26T00:54:52 phase=3 state=open review_scope=in -->
### r3-f4 · finding [open] (reviewer: in scope) · MEDIUM: p3-merge-method squash default can silently merge with the wrong method; read the repo default via gh repo view (viewerDefaultMergeMethod/*Allowed), --method as override (phase 3)

<!-- fr:journal kind=finding scope=plan id=r3-f5 created=2026-09-26T00:54:55 phase=3 state=open review_scope=in -->
### r3-f5 · finding [open] (reviewer: in scope) · MEDIUM: branch bumps to 4.22.0 but origin/main (#628) is already 4.22.0; rebase and bump minor to 4.23.0 (phase 3)

<!-- fr:journal kind=finding scope=plan id=r3-f6 created=2026-09-26T00:54:58 phase=3 state=open review_scope=in -->
### r3-f6 · finding [open] (reviewer: in scope) · A re-run force-removes the scratch worktree kept for inspection, destroying manual fixes (phase 3)

<!-- fr:journal kind=finding scope=plan id=r3-f7 created=2026-09-26T00:54:59 phase=3 state=open review_scope=in -->
### r3-f7 · finding [open] (reviewer: in scope) · commit_all runs git add --all after set/relock in the scratch worktree, pushing any untracked artifacts to another run's PR (phase 3)

<!-- fr:journal kind=finding scope=plan id=r3-f8 created=2026-09-26T00:55:01 phase=3 state=open review_scope=in -->
### r3-f8 · finding [open] (reviewer: in scope) · p3-reserve-order sound but spec §3.D and Test Plan 11 still describe explicit-order-first reservation; amend the spec (phase 3)

<!-- fr:journal kind=finding scope=plan id=r3-f9 created=2026-09-26T00:55:03 phase=3 state=open review_scope=in -->
### r3-f9 · finding [open] (reviewer: in scope) · --repair ignores batch stage: re-labels closed/released issues on merged or abandoned batches; restrict to dispatched/pr-open (phase 3)

<!-- fr:journal kind=finding scope=plan id=r3-f10 created=2026-09-26T00:55:05 phase=3 state=open review_scope=in -->
### r3-f10 · finding [open] (reviewer: in scope) · Test quality: weakened 'path named' assert; integration test lacks a version file with non-version content and the 3b re-slot against real git (phase 3)

<!-- fr:journal kind=finding scope=plan id=r3-f11 created=2026-09-26T00:55:08 phase=3 state=open review_scope=in -->
### r3-f11 · finding [open] (reviewer: in scope) · Git seam tripwire does not stop batch modules from running arbitrary commands through run_declared/_run (phase 3)

<!-- fr:journal kind=finding scope=plan id=r3-f12 created=2026-09-26T00:55:10 phase=3 state=open review_scope=in -->
### r3-f12 · finding [open] (reviewer: in scope) · git merge in the scratch worktree inherits operator rerere config, which can silently resolve a non-version conflict; pass -c rerere.enabled=false (phase 3)

<!-- fr:journal kind=finding scope=plan id=r3-f13 created=2026-09-26T00:55:12 phase=3 state=open review_scope=in -->
### r3-f13 · finding [open] (reviewer: in scope) · Config freshness compares committer dates (%cI); compare ancestry/commit identity instead (phase 3)

<!-- fr:journal kind=finding scope=plan id=r3-f14 created=2026-09-26T00:55:15 phase=3 state=open review_scope=out -->
### r3-f14 · finding [open] (reviewer: out of scope) · Live reservations only see the current scope's judgements; a repo and an org triage can reserve the same number (reconcile at merge still prevents a clash) (phase 3)

<!-- fr:journal kind=finding scope=plan id=r3-f14-resolved created=2026-09-26T00:55:18 state=open resolves=r3-f14 out_of_scope=true answered_by=agent -->
### r3-f14-resolved · finding [out-of-scope] · resolves r3-f14: Live reservations only see the current scope's judgements; a repo and an org triage can reserve the same number (reconcile at merge still prevents a clash)

Follows from the spec's per-scope triage state design, not from this phase; merge-time reconcile keeps merged versions unique.

<!-- fr:journal kind=finding scope=plan id=r3-f1-resolved created=2026-09-26T01:12:11 state=fixed resolves=r3-f1 answered_by=agent -->
### r3-f1-resolved · finding [fixed] · resolves r3-f1: HIGH: dispatch launches the runner, then the open-batch rule / compare-before-write refuses in _write: no event, no forge write, batch stuck (re-run says live, --repair refuses)

Verified: check_open_membership/compare-before-write ran only in _write after runner.dispatch. Now a write gate (open-batch rule + save_batches dry_run) runs before can_dispatch and again immediately before runner.dispatch; a post-launch write failure exits 1 naming handle, branch, reserved version and the exact '--repair --yes --handle H --reserved-version V' command; --repair records the missing event only when the runner reports the item live. Tests: test_triage_batch_dispatch.py::test_a_redispatch_that_would_break_the_open_batch_rule_never_reaches_the_runner, ::test_a_change_to_judgements_before_launch_is_refused_before_the_runner, ::test_an_event_write_failing_after_launch_names_the_handle_and_the_recovery, ::test_repair_records_the_missing_dispatch_of_a_live_run, ::test_repair_records_nothing_for_a_run_the_runner_does_not_hold, ::test_repair_needs_the_reserved_version_when_the_repo_reserves

<!-- fr:journal kind=finding scope=plan id=r3-f2-resolved created=2026-09-26T01:12:16 state=fixed resolves=r3-f2 answered_by=agent -->
### r3-f2-resolved · finding [fixed] · resolves r3-f2: HIGH: take_theirs checks out main's WHOLE version file, discarding the PR's other edits in it (e.g. a new dependency in pyproject.toml); exceeds d3

Verified: take_theirs replaced the whole file. Now a conflicted version file is taken from main only when the PR's change to it (merge-base -> PR head) is the quoted version alone (batch_version.only_version_changed); a lockfile changed further only with a declared relock (then relocked); anything else aborts, stops and names the path. Tests: test_triage_batch_merge_git.py::test_a_pr_that_changed_a_version_file_beyond_the_version_stops_the_queue (red against the old rule), test_triage_batch_merge.py::test_a_version_file_the_pr_changed_beyond_the_version_is_a_real_conflict, ::test_a_lockfile_changed_beyond_the_version_is_taken_and_relocked, ::test_a_lockfile_changed_beyond_the_version_without_relock_stops, test_triage_batch_version.py::test_only_version_changed

<!-- fr:journal kind=finding scope=plan id=r3-f3-resolved created=2026-09-26T01:12:22 state=fixed resolves=r3-f3 answered_by=agent -->
### r3-f3-resolved · finding [fixed] · resolves r3-f3: MEDIUM: batch merge never checks collected-config freshness (spec §3.I), yet runs its version.files/set/relock

batch merge now fetches and holds check_config_fresh (shared _fresh_config with dispatch) before planning or reading the merge method. Test: test_triage_batch_merge.py::test_merge_refuses_a_collected_config_that_differs_from_origin

<!-- fr:journal kind=finding scope=plan id=r3-f4-resolved created=2026-09-26T01:12:27 state=fixed resolves=r3-f4 answered_by=agent -->
### r3-f4-resolved · finding [fixed] · resolves r3-f4: MEDIUM: p3-merge-method squash default can silently merge with the wrong method; read the repo default via gh repo view (viewerDefaultMergeMethod/*Allowed), --method as override

Added GhClient.repo_merge_methods (RealGhClient: gh repo view --json viewerDefaultMergeMethod,mergeCommitAllowed,squashMergeAllowed,rebaseMergeAllowed, shape captured live; glab/tea raise UnsupportedForgeOperation naming gh#611). merge defaults to the repo's default; --method is an override refused when disallowed; no usable default among several allowed asks for --method. Spec 3.F/3.J amended; supersedes decision p3-merge-method. Tests: test_forge_adapter_batch_ops.py::test_repo_merge_methods_reads_the_viewer_default_and_the_allowed_methods, ::test_glab_and_tea_declare_each_batch_operation_unsupported[repo_merge_methods], test_triage_batch_merge.py::test_the_merge_method_defaults_to_the_repos_default, ::test_an_explicit_method_the_repo_disallows_is_refused, ::test_no_repo_default_among_several_allowed_methods_asks_for_one

<!-- fr:journal kind=finding scope=plan id=r3-f6-resolved created=2026-09-26T01:12:32 state=fixed resolves=r3-f6 answered_by=agent -->
### r3-f6-resolved · finding [fixed] · resolves r3-f6: A re-run force-removes the scratch worktree kept for inspection, destroying manual fixes

Checkout.add_worktree replaces a kept scratch worktree only when git status (untracked included) is clean; one with local changes is refused naming its path and the discard command (git worktree remove --force <path>); a non-worktree directory is refused too. Tests: test_triage_gitseam.py::test_a_kept_worktree_with_local_changes_is_refused_by_name, ::test_a_kept_worktree_with_an_untracked_file_is_refused, ::test_a_clean_kept_worktree_is_replaced, ::test_a_directory_that_is_not_a_worktree_is_refused; test_triage_batch_merge_git.py::test_a_kept_worktree_with_a_manual_fix_is_never_replaced

<!-- fr:journal kind=finding scope=plan id=r3-f7-resolved created=2026-09-26T01:12:36 state=fixed resolves=r3-f7 answered_by=agent -->
### r3-f7-resolved · finding [fixed] · resolves r3-f7: commit_all runs git add --all after set/relock in the scratch worktree, pushing any untracked artifacts to another run's PR

Worktree.commit_all(message, version_files) stages git add --update plus untracked paths matching the declared version.files globs only, never --all. Tests: test_triage_gitseam.py::test_commit_all_stages_tracked_changes_and_version_files_only; test_triage_batch_merge_git.py::test_the_version_update_commits_no_untracked_build_output (set leaves setv.log behind)

<!-- fr:journal kind=finding scope=plan id=r3-f8-resolved created=2026-09-26T01:12:41 state=fixed resolves=r3-f8 answered_by=agent -->
### r3-f8-resolved · finding [fixed] · resolves r3-f8: p3-reserve-order sound but spec §3.D and Test Plan 11 still describe explicit-order-first reservation; amend the spec

Spec 3.D and Test Plan 11 amended: reservations follow dispatch sequence (next after max(origin, every live reservation)); explicit order applies at merge-time reconcile. Recorded in the spec journal as decision d-reserve-order crediting p3-reserve-order and the reviewer's verification. Tests (unchanged, already pin it): test_triage_batch_version.py::test_the_reservation_follows_the_highest_live_reservation, test_triage_batch_dispatch.py::test_successive_dispatches_reserve_successive_versions

<!-- fr:journal kind=finding scope=plan id=r3-f9-resolved created=2026-09-26T01:12:46 state=fixed resolves=r3-f9 answered_by=agent -->
### r3-f9-resolved · finding [fixed] · resolves r3-f9: --repair ignores batch stage: re-labels closed/released issues on merged or abandoned batches; restrict to dispatched/pr-open

--repair on a batch whose last event is a dispatch refuses unless its stage is dispatched or pr-open (merged, partial, abandoned refused, no forge write). Tests: test_triage_batch_dispatch.py::test_repair_refuses_a_batch_that_is_no_longer_in_flight[abandoned|merged|partial], ::test_repair_completes_a_batch_in_flight[dispatched|pr-open]
