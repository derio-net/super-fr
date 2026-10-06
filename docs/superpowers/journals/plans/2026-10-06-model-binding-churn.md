# Journal: 2026-10-06-model-binding-churn

<!-- fr:journal kind=discovery scope=plan id=p1-opencode-run-needs-closed-stdin created=2026-10-06T18:13:34+00:00 phase=1 -->
### p1-opencode-run-needs-closed-stdin · discovery · opencode run blocks forever when stdin is left open (phase 1)

Capturing the probe fixtures, `opencode run` with an inherited stdin produced no output for 90 s and was killed by timeout (rc 124). With `</dev/null` it answers in seconds. run_opencode therefore passes stdin=DEVNULL. Also observed: a dead model (ProviderModelNotFoundError) exited 1, not 0 as the spec background says, so classify never reads the return code.

<!-- fr:journal kind=discovery scope=plan id=p1-argument-injection-guard created=2026-10-06T18:13:34+00:00 phase=1 -->
### p1-argument-injection-guard · discovery · Binding values can arrive from the tracked repo models.yaml and reach opencode's argv (phase 1)

Coordinator-directed security fix. fr.bindings.valid_provider/valid_model_name/valid_model_id (provider ^[A-Za-z0-9][A-Za-z0-9._-]*$, model part ^[A-Za-z0-9][A-Za-z0-9._:-]*$). OpenCodeProber.probe returns unknown (`<m> is not a provider/model id`) and catalogue returns [] for an invalid value WITHOUT spawning; the model is passed as the single token --model=<id>. `fr models set` refuses (exit 2) an opencode id that is not provider/model, and for other harnesses a value starting with '-' or containing whitespace, before writing; claude-code bare ids such as claude-opus-5-5 still work. The stub opencode and fixtures README were updated for --model=. Existing opencode `set` tests that used bare names (m, s, h) now use p/m, p/s, p/h.

<!-- fr:journal kind=decision scope=plan id=p1-hint-only-without-lineage created=2026-10-06T18:13:34+00:00 phase=1 -->
### p1-hint-only-without-lineage · decision · Provider hint is tried only when the dead model has no entry and no snapshot (phase 1)

Spec R4 lists family, tier, hint in order but says the hint applies when neither rule above has inputs. Read literally: with no catalogue entry and no snapshot the family rule has no family and the tier rule has no dead price, so only the hint is tried (and a hinted pick is never autonomous). A dead model that does have lineage never uses the hint.

<!-- fr:journal kind=decision scope=plan id=p1-unknown-not-cached created=2026-10-06T18:13:34+00:00 phase=1 -->
### p1-unknown-not-cached · decision · ProbeCache stores only live and dead verdicts (phase 1)

An unknown (timeout, server error) is a transient failure; caching it for 6 h would hide recovery. fresh=True still bypasses for the others.

<!-- fr:journal kind=decision scope=plan id=p1-prober-seam created=2026-10-06T18:13:34+00:00 phase=1 -->
### p1-prober-seam · decision · fr.bindings.prober_for is the one monkeypatched factory; default_prober_for is its implementation (phase 1)

Callers must use fr.bindings.prober_for(...) via the module attribute. tests/conftest.py autouse fixture replaces it with an always-live, empty-catalogue prober and sets FR_MODELS_CACHE_DIR (a new override of the $HOME/.cache/fr/models path) so the suite never touches the real opencode or an operator's cache. Phase 2 tests monkeypatch the same name.

<!-- fr:journal kind=discovery scope=plan id=p1-check-exit-and-repo-layer created=2026-10-06T18:13:34+00:00 phase=1 -->
### p1-check-exit-and-repo-layer · discovery · fr models check on a repo-layer dead binding (phase 1)

check never rewrites docs/superpowers/models.yaml (R9): on a terminal it names the file and does not offer to apply; the dead binding still counts toward exit 1.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-06T18:13:34+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

check_bindings was already one function over choose_replacement/offers; nothing to extract beyond naming.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t7 created=2026-10-06T18:13:34+00:00 phase=1 -->
### no-refactor-p1-t7 · discovery · no-refactor-because P1.T7 (phase 1)

Scenario scripts share one sourced helper (_stub_opencode.sh) from the start; nothing duplicated to clean.

<!-- fr:journal kind=review scope=plan id=p1-review-r1 created=2026-10-06T18:33:26+00:00 phase=1 -->
### p1-review-r1 · review · phase 1 independent review: 9 findings (p1-r1..p1-r9), all in scope, all fixed in 25c7c4bb6 (phase 1)

Reviewed spec R1–R5, R10, R12, R3 and §A/§B/## Verification against git diff 37724adaf..HEAD. Targeted unit tests (78) and the 3 model_binding scenarios passed. Conformance confirmed: R1 terminal/off-terminal, R2 never reads catalogue status, R4 rule order + 5-probe cap + is_autonomous, R5 report/exit 1, R10 unprobed, R11 line fields, the argument-injection guard (single --model=<id> token, validated before spawn, per-harness set refusal). Raised p1-r1..p1-r9; each verified against the code by the orchestrator, then fixed test-first in 25c7c4bb6; full suite after the fix: 9754 passed, 105 skipped.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-06T18:33:26+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · ProbeCache crashes on corrupt entry types or unwritable HOME; write not atomic (phase 1)

probe.py ProbeCache: ProbeResult(**raw) unvalidated (`at` a string raises TypeError in check/run start); unguarded mkdir/write_text raises OSError; non-atomic write. Fix: validate and treat bad entries as a miss, temp+os.replace, swallow OSError.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-06T18:33:26+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · SnapshotStore does not type-validate entries; its write can raise OSError (phase 1)

catalogue.py SnapshotStore.get/remember: CatalogueEntry(**raw) unchecked, later TypeError in choose.py comparisons; OSError on a bad HOME crashes check_bindings. Fix: validate fields, guard writes.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-06T18:33:26+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · valid_model_id refuses real nested/@ opencode ids (phase 1)

fr/bindings/__init__.py _MODEL excluded '/' and '@', refusing openrouter/anthropic/claude-3.5 and vertex/claude@20240620 — a regression for fr models set. Fix: provider = first segment, tail allows nested and versioned forms.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-06T18:33:26+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · fr models check can propose the same model for two dead tiers (phase 1)

models_cmd.check_cmd/health.check_bindings computed all proposals from the original map; distinctness/ordering broken when two tiers die. Fix: choose sequentially, folding each pick in.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-10-06T18:33:26+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · set's dead path duplicates choose/catalogue logic and skips the R3 snapshot (phase 1)

models_cmd.set_cmd hand-built choose_replacement and read the catalogue without SnapshotStore.remember. Fix: one shared proposer in health.py.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-10-06T18:33:26+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · hint rule may propose another provider's model (phase 1)

choose.py:162 used a provider-qualified hint verbatim; R4 requires the same provider. Fix: require matching provider.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-10-06T18:33:26+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · prober catches only FileNotFoundError/TimeoutExpired (phase 1)

probe.py probe/catalogue: PermissionError/OSError or UnicodeDecodeError would crash; R2/Risks say never a crash. Fix: catch them.

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-10-06T18:33:26+00:00 phase=1 state=open review_scope=in -->
### p1-r8 · finding [open] (reviewer: in scope) · validators in fr/bindings/__init__ with function-local circular imports (phase 1)

probe.py imported fr.bindings inside methods. Fix: leaf module fr/bindings/ids.py, re-exported.

<!-- fr:journal kind=finding scope=plan id=p1-r9 created=2026-10-06T18:33:26+00:00 phase=1 state=open review_scope=in -->
### p1-r9 · finding [open] (reviewer: in scope) · missing tests for corrupt cache/snapshot, failed cache write, nested/@ ids (phase 1)

The robustness cases p1-r1..r3 break on had no tests. Fix: add them alongside the fixes.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-06T18:33:26+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: ProbeCache crashes on corrupt entry types or unwritable HOME; write not atomic (phase 1)

25c7c4bb6: ProbeCache._valid + write_json_atomic (temp + os.replace, OSError swallowed). Tests test_bindings_probe::test_a_corrupt_probe_cache_is_a_miss_never_a_crash, ::test_a_failing_cache_write_never_crashes_and_leaves_no_temp_file, ::test_the_cache_is_written_atomically_via_replace.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-06T18:33:26+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: SnapshotStore does not type-validate entries; its write can raise OSError (phase 1)

25c7c4bb6: SnapshotStore.get validates every field, remember uses write_json_atomic. Tests test_bindings_catalogue::test_corrupt_snapshot_fields_count_as_absent, ::test_a_failing_snapshot_write_never_crashes.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-06T18:33:26+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: valid_model_id refuses real nested/@ opencode ids (phase 1)

25c7c4bb6: fr/bindings/ids.py accepts nested and @-versioned ids, still refusing whitespace, '=' and a leading '-'. Test test_bindings_probe::test_a_model_id_must_be_provider_slash_model.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-06T18:33:26+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: fr models check can propose the same model for two dead tiers (phase 1)

25c7c4bb6: check_bindings chooses sequentially in tier order, folding each pick in. Tests test_bindings_health::test_two_dead_tiers_never_get_the_same_replacement, test_models_cmd::TestCheck::test_two_dead_tiers_get_distinct_proposals, ::test_an_accepted_change_is_folded_into_the_next_choice.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-10-06T18:33:26+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: set's dead path duplicates choose/catalogue logic and skips the R3 snapshot (phase 1)

25c7c4bb6: health.propose_for is the one proposer (catalogue read, snapshot remember, choose), used by set and check_bindings. Tests test_bindings_health::test_propose_for_remembers_the_snapshot_and_chooses, test_models_cmd::TestSetProposalSharesTheHealthChooser::test_a_dead_set_remembers_the_snapshot_of_the_dead_model.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-10-06T18:33:26+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: hint rule may propose another provider's model (phase 1)

25c7c4bb6: a provider-qualified hint is used only on the dead model's provider. Test test_bindings_choose::test_a_hint_naming_another_provider_is_not_used.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-10-06T18:33:26+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: prober catches only FileNotFoundError/TimeoutExpired (phase 1)

25c7c4bb6: probe/catalogue catch OSError and UnicodeDecodeError → unknown / []. Test test_bindings_probe::test_os_and_decode_errors_are_unknown_and_empty_never_a_crash.

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-10-06T18:33:26+00:00 phase=1 state=fixed resolves=p1-r8 -->
### p1-r8-resolved · finding [fixed] · resolves p1-r8: validators in fr/bindings/__init__ with function-local circular imports (phase 1)

25c7c4bb6: validators in leaf fr/bindings/ids.py, module-level import, re-exported. Test test_bindings_probe::test_the_validators_live_in_a_leaf_module_and_are_re_exported.

<!-- fr:journal kind=finding scope=plan id=p1-r9-resolved created=2026-10-06T18:33:26+00:00 phase=1 state=fixed resolves=p1-r9 -->
### p1-r9-resolved · finding [fixed] · resolves p1-r9: missing tests for corrupt cache/snapshot, failed cache write, nested/@ ids (phase 1)

25c7c4bb6: the tests named under p1-r1..r4 cover the gap.

<!-- fr:journal kind=decision scope=plan id=p2-choice-carries-tried created=2026-10-06T18:57:34+00:00 phase=2 -->
### p2-choice-carries-tried · decision · Choice gains a non-identity `tried` field so a refusal names every candidate probed (phase 2)

R8 says a refusal names the candidates fr tried. NoChoice already carried them; an operator-only Choice (ratio > 2, or the hint rule) did not. `fr.bindings.choose.Choice` now has `tried: tuple[str, ...] = field(default=(), compare=False)`, filled by every rule, so phase 1's equality assertions are unaffected.

<!-- fr:journal kind=decision scope=plan id=p2-no-run-journal-refuses created=2026-10-06T18:57:34+00:00 phase=2 -->
### p2-no-run-journal-refuses · decision · An autonomous pick with no run journal yet (no plan, no spec emitted) refuses rather than substitutes (phase 2)

R11 requires recorded iff applied. A run that has emitted neither a spec nor a plan has no run journal to record in, so `_guard_dispatch_binding` exits 2 there (naming the `fr models set` line) instead of applying an unrecorded substitution. Not reachable on the shipped fr-goal shape, whose first tiered step (spec-review) needs the spec.

<!-- fr:journal kind=decision scope=plan id=p2-wording-module created=2026-10-06T18:57:34+00:00 phase=2 -->
### p2-wording-module · decision · fr.bindings.wording is the one formatter for both deciders (phase 2)

`Substitution` (harness, tier, old, new, reason, decider, rule, price_ratio) with `substitution_line` (R11), `decision_title`/`decision_body` (the five fields plus the price ratio) and `proposal_text`/`ratio_text`, moved out of models_cmd. `fr models set/check` and the run guard both print through it.

<!-- fr:journal kind=decision scope=plan id=p2-guard-restore-unnotes created=2026-10-06T18:57:34+00:00 phase=2 -->
### p2-guard-restore-unnotes · decision · A failed substitution also drops the journal from the pending cursor commit (phase 2)

`_RunWrites.remember` is a no-op outside the step-record engine, so the guard keeps its own pre-write bytes of both files and restores them itself; it also removes the journal from `_RunWrites.paths`, so the advance's always-run commit carries nothing for a substitution that was not applied. The guard is called before anything is marked running, so a refusal leaves the cursor byte-identical.

<!-- fr:journal kind=discovery scope=plan id=p2-explainer-not-touched created=2026-10-06T18:57:34+00:00 phase=2 -->
### p2-explainer-not-touched · discovery · docs/explainers/01-fr-goal.md does not describe the model-per-tier question (phase 2)

It mentions models only as a dispatch-record fact (§ who is holding) and in the configuration table row "Model per phase tier"; the question round's tier/binding questions are not described, so per spec §D no explainer edit or .html regeneration is owed.

<!-- fr:journal kind=discovery scope=plan id=p2-t1-refactor-landed-at-green created=2026-10-06T18:57:34+00:00 phase=2 -->
### p2-t1-refactor-landed-at-green · discovery · P2.T1.S3's `_binding_health` helper was written at GREEN (phase 2)

Both call sites (start notice, gated brief) and later the guard read `run_cmd._binding_health`, written once at GREEN; the refactor step confirmed nothing duplicated was left and ran ruff + mypy clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-10-06T18:57:34+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

skill prose, generated mirrors, a parity row, an AGENTS.md paragraph and a matrix status: no code to clean

<!-- fr:journal kind=review scope=plan id=p2-review-r1 created=2026-10-06T19:27:19+00:00 phase=2 -->
### p2-review-r1 · review · phase 2 independent review: 7 findings (p2-r1..r6 in scope, fixed in 8244ae448; p2-r7 out of scope) (phase 2)

Reviewed spec R6–R9, R11, §C, §D against git diff 25c7c4bb6..HEAD. Ran test_run_binding_guard + test_run_cli (287 passed), the four mirror/neutrality/parity tripwires (26 passed), sync-opencode/sync-hermes --check, fr harness parity --check, fr acceptance check, ruff/mypy — all green. Confirmed R8 placement on both dispatch paths with the exact `_open_dispatch` tier, byte-identical cursor on refusal, redispatch/retry coverage, autonomy only via is_autonomous, R9 repo-layer refusal, R11 write order and same-commit journal entry, R6 brief keys, R7 skill text, generated mirrors, parity row partial. Raised p2-r1..p2-r7; the orchestrator verified each against the code; p2-r1..r6 fixed test-first in 8244ae448 (full suite after: 9775 passed, 105 skipped); p2-r7 predates this change.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-06T19:27:19+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · guard runs full check_bindings on every tiered OpenCode dispatch (phase 2)

_guard_dispatch_binding → _binding_health → check_bindings: an uncached `opencode models` spawn plus live offer probes per dispatch, discarded. Fix: read the cached verdict first; catalogue and choose only on dead; no offers.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-10-06T19:27:19+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · partial materialise reported as SUBSTITUTED (phase 2)

materialize_agents reports change.problem without raising; the guard warned and printed SUBSTITUTED while the dispatched tier's agent file could still name the dead model. Fix: treat a problem on the dispatched tier's file as a failed apply (restore, exit 2).

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-10-06T19:27:19+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · substitution journal id is count-based and can collide (phase 2)

run_cmd.py:3731 n = 1 + count of numeric suffixes; non-contiguous suffixes give a duplicate id that fr validate artifacts fails. Fix: max suffix + 1.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-10-06T19:27:19+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · guard tests miss restore, flat refusal, redispatch, repeated id (phase 2)

Only set_binding raising was pinned. Fix: tests for materialise raising, flat-path refusal byte-identity, guard on --redispatch, repeated substitution id.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-10-06T19:27:19+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · no-op _remember(journal) and duplicated set+materialise path (phase 2)

run_cmd.py:3720 _remember is a no-op on advance (guard=None); the guard re-implemented models_cmd._apply_binding, which spec §B calls the one write path. Fix: drop the call; one shared apply_binding.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-10-06T19:27:19+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · member briefs lack dead_bindings/binding_offers (phase 2)

_build_member_brief (run_cmd.py:4026) claims the same keys as the step brief; R6 says every agent-step brief carries them. Fix: add both as null.

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-10-06T19:27:19+00:00 phase=2 state=open review_scope=out -->
### p2-r7 · finding [open] (reviewer: out of scope) · corrupt models.yaml crashes fr run start after save (phase 2)

load_models raises ModelsError/YAMLError; _orchestrator_model_notice → _resolved_model already raises it before the new code. Pre-existing; _binding_health is equally unguarded but never reached first.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-06T19:27:19+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: guard runs full check_bindings on every tiered OpenCode dispatch (phase 2)

8244ae448: the guard reads the cached verdict only; on dead it reads the catalogue and chooses via health.propose_for; never offers. Test test_run_binding_guard::test_a_live_binding_at_dispatch_reads_no_catalogue_and_probes_no_offer.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-10-06T19:27:19+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: partial materialise reported as SUBSTITUTED (phase 2)

8244ae448: a problem on the dispatched tier's agent file takes the restore path (SUBSTITUTION NOT APPLIED, exit 2). Test test_run_binding_guard::test_a_dispatched_tier_agent_file_left_unrewritten_is_not_a_substitution.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-10-06T19:27:19+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: substitution journal id is count-based and can collide (phase 2)

8244ae448: _substitution_id = max numeric suffix + 1. Tests test_run_binding_guard::test_two_substitutions_of_one_tier_get_distinct_ids, ::test_a_substitution_id_never_reuses_a_taken_suffix.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-10-06T19:27:19+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: guard tests miss restore, flat refusal, redispatch, repeated id (phase 2)

8244ae448: tests test_a_raising_materialise_restores_and_rematerialises_the_old_binding, test_a_flat_path_refusal_leaves_the_cursor_byte_identical, test_the_guard_runs_on_redispatch, plus the two p2-r3 tests (test_run_binding_guard).

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-10-06T19:27:19+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: no-op _remember(journal) and duplicated set+materialise path (phase 2)

8244ae448: _remember(journal) removed; new fr.bindings.apply.apply_binding is the one write path used by models_cmd._apply_binding and the guard (which keeps its restore).

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-10-06T19:27:19+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: member briefs lack dead_bindings/binding_offers (phase 2)

8244ae448: _build_member_brief carries dead_bindings/binding_offers as null; _MEMBER_BRIEF_KEYS and test_member_briefs_carry_no_operator_input pin it.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-10-06T19:27:19+00:00 phase=2 state=open resolves=p2-r7 out_of_scope=true -->
### p2-r7-resolved · finding [out-of-scope] · resolves p2-r7: corrupt models.yaml crashes fr run start after save (phase 2)

Not caused by this change: a corrupt models.yaml already crashed fr run start via _orchestrator_model_notice → _resolved_model → load_models before this PR; the new _binding_health is never reached first. Worth its own fix (warn instead of crash in both notices).
