# Journal: 2026-09-20-unit-record-unification

<!-- fr:journal kind=discovery scope=plan id=nr-p1t3 created=2026-09-20T21:57:05 phase=1 -->
### nr-p1t3 · discovery · no-refactor-because P1.T3 (phase 1)

P1.T3 writes no production code. S1 CAPTURES real run cursors byte-for-byte as fixtures — refactoring a captured fixture would turn it into a constructed one, which is the exact thing the walking-skeleton rule forbids. S2 runs the full CI gate. Phase 1's authored code is refactored in P1.T2.S3.

<!-- fr:journal kind=discovery scope=plan id=nr-p7t2 created=2026-09-20T21:57:05 phase=7 -->
### nr-p7t2 · discovery · no-refactor-because P7.T2 (phase 7)

P7.T2 is acceptance status flips through fr acceptance set-status and a version bump through scripts/bump-version.py. Both produce files the repo documents as never hand-edited (the matrix, its three generated reports, nine version manifests, uv.lock). A refactor step over generated output is the hand-edit those rules exist to prevent.

<!-- fr:journal kind=discovery scope=plan id=nr-p7t3 created=2026-09-20T21:57:05 phase=7 -->
### nr-p7t3 · discovery · no-refactor-because P7.T3 (phase 7)

P7.T3 is the explainer and the final gate. The .html is produced by a renderer in another repo and carries a do-not-hand-edit banner; the .md's quality pass is inside S1 itself — the byte-for-byte re-render of the UNMODIFIED source that must pass before the real render, which is a stronger check than a refactor step. S2 is the CI gate.

<!-- fr:journal kind=decision scope=plan id=d-tier-override created=2026-09-20T22:02:25 -->
### d-tier-override · decision · Session-scoped tier override: hard -> Fable 5.1, standard -> Opus 5

Operator instruction for THIS session only. fr models has no session or env override — bindings live in ~/.config/fr/models.yaml, which every other session on this machine reads — so writing it would have changed their dispatches too. Kept session-scoped instead: the model is passed on the dispatch call itself, and fr is told the truth with fr run claim --model, which overrides the binding fr derived when it opened the attempt. Reading this run's cursor: a hard-tier attempt is OPENED with model claude-opus-5 (what models.yaml says) and corrected to claude-fable-5-1 by its claim a moment later. standard already resolves to claude-opus-5, so only hard differs. This is the derived-vs-reported seam of #508's spec section 3 doing its job.

<!-- fr:journal kind=decision scope=plan id=p1-redispatch-conflict created=2026-09-20T22:19:50 phase=1 -->
### p1-redispatch-conflict · decision · A SECOND design conflict, not covered by u1: --redispatch on a never-dispatched unit. gh#519's refusal kept. (phase 1)

The brief counted the 9 red tests as 7 wording + 1 conflict. Actual split: 3 u1 (abandon -> re-brief, grouped/flat/closed-record), 2 wording (ALREADY RUNNING -> HELD), 2 renderer gaps (the unified refusal dropped agent_type; one test named the internal step/<id> key), 1 dead-code merge fallout (p1-manual-tag-dead), and ONE more real conflict: test_redispatch_on_an_unheld_unit_is_exactly_a_plain_advance (gh#508: exit 0, behaves as plain advance) and test_redispatch_with_nothing_outstanding_is_refused (gh#519: exit 2) ran the SAME command on the SAME fixture and asserted opposite exit codes. Both cannot pass. Kept gh#519's, because it is the only one that is SPECIFIED: its spec section 3.A says '--redispatch with nothing outstanding exits 2', the explainer publishes it, and matrix row run-advance-refuses-running cites it. gh#508's spec never addresses the unheld case; its test pinned an implementation choice. The gh#508 test is rewritten (not deleted) as test_redispatch_on_a_never_dispatched_unit_is_refused_and_records_nothing and now owns what its sibling does not check: the refused command leaves NO dispatch record. Unaffected and still green: --redispatch after claim --abandoned exits 0 (the unit is still running = outstanding, just not held). Operator may overrule; it is a one-test, one-branch change.

<!-- fr:journal kind=discovery scope=plan id=p1-witness-shape created=2026-09-20T22:19:50 phase=1 -->
### p1-witness-shape · discovery · What phases 2-3 inherit: _hold_on is the one held-question; running is lifecycle everywhere else (phase 1)

run_cmd.py now has: _dispatch_needs_open/_held_record (is the LAST record open - unchanged) and _hold_on(record, key, *, running) -> _Hold | None, the ONLY function either refusal call site asks. _Hold.holder is the open DispatchRecord, or None for the fallback (running AND no record at all for that key - never for a unit with a closed record). Phase 3 re-points it at UnitRecord.attempts; the rule does not change. _refuse_held (gh#508's renderer) was dead after the gh#519 fold-in and is deleted; _already_running_refusal is the one renderer and now names agent_type via _dispatch_descriptor_suffix(with_agent_type=True) - status lines are unchanged. Remaining == "running" hits are all lifecycle and say so: which unit is outstanding (what --redispatch re-briefs), the once-per-group preflight, the save guards, --redispatch's nothing-is-running refusal, and resolve's single-writer guard (an --abandoned unit still blocks resolving a DIFFERENT unit - intended). Note for phase 4: on a re-brief after --abandoned the group's at is NOT refreshed (nothing reads it once a record exists) and accounting[unit] is still overwritten - that is u2's defect, untouched here.

<!-- fr:journal kind=discovery scope=plan id=p1-fallback-green-on-arrival created=2026-09-20T22:19:51 phase=1 -->
### p1-fallback-green-on-arrival · discovery · TDD deviation: the three recordless-fallback tests passed on arrival; two mutants stand in for the red (phase 1)

P1.T2.S1 asks for one more RED test. The fallback is behaviour gh#519 already had, so a test pinning it cannot be red before the fix - the risk is the FIX removing it. Verified by mutation instead, after green: M1 (_hold_on returns None when there is no record) fails exactly test_a_running_member_with_no_dispatch_record_is_still_refused and its flat sibling; M2 (fallback widened to every running unit = pre-u1 behaviour) fails exactly the three abandon tests. Both reverted, byte-compared. The recordless shape is built by dispatching through the real CLI and dropping only the dispatch map - and it is a real shape: run 2->3->4 are stamp-only, and gh#517's own cursor arrived as 'deliver: running' with no dispatch.

<!-- fr:journal kind=discovery scope=plan id=p1-manual-tag-dead created=2026-09-20T22:19:51 phase=1 -->
### p1-manual-tag-dead · discovery · Merge fallout: gh#496's 'tag: manual' resolve message was dead code behind _unit_key (phase 1)

test_resolving_a_manual_phase_member_names_the_tag was one of the 9. _resolve_member calls _unit_key (gh#508) first, which refused with the generic 'not a phase member' text before gh#519's manual-phase message could run. Moved the message INTO _unit_key - the one place a unit key is validated - so fr run claim gets it too, and deleted the unreachable re-validation.

<!-- fr:journal kind=discovery scope=plan id=p1-merge-notes created=2026-09-20T22:19:51 phase=1 -->
### p1-merge-notes · discovery · gh#517 fold-in: what differed from the plan's expectation (phase 1)

(1) The fr-goal SKILL.md and both mirrors merged with NO conflict (117 lines, cap 120); verified line-by-line that every line either side added survives. Real conflicts the plan did not list: fr/journal/model.py and tests/integration/test_fr_goal_shape.py - both pure both-sides-added, both kept. (2) One semantic conflict with no marker: gh#517's TestCheckRequireReviews seeded an untagged plan-scope finding, which main's gh#464 refuses (6 tests red); the seed now passes --global. (3) Explainer .html: the plan said 'ours for now', but gh#517 renumbers section headings, so an ours page FAILS test_tripwire_explainers_fresh. Regenerated per explainers-currency.md (from /, --isolated). The byte-for-byte pre-check did NOT match - not the renderer: HEAD's committed .html was already behind HEAD's .md (the gh#519 fold-in took the .md prose but kept an older page). Every diverging line was .md prose. Phase 7 regenerates again. The five .md conflicts were all SKILL.md line citations; set to the MERGED file's ranges (implement 75-87, review 89-94, journal-check 96-97, deliver 99-111, close-out 113-117). Other citations in that page were not audited - phase 7. (4) Matrix: theirs added 3 rows, changed 0, removed 0; rebuilt by row block; 170 rows.

<!-- fr:journal kind=finding scope=plan id=p1-f-run-stranded created=2026-09-20T22:19:52 phase=1 state=open -->
### p1-f-run-stranded · finding [open] · ORCHESTRATOR ACTION: folding in gh#517 strands THIS run's cursor (manifest drift: added journal-check) (phase 1)

gh#517 adds a journal-check step to the shipped fr-goal manifest. This run (docs/superpowers/runs/2026-09-20-unit-record-unification.yaml, untracked, cursor=implement, phase/1 held) was started against the old step list, so every verb that resolves the manifest now exits 2: verified with the read-only 'fr run gates' -> 'was started against a different version of fr-goal@1 (added: journal-check)'. advance, resolve, claim and gates all go through _resolve_manifest_for_state; status and check still work. By design (gh#517 SKILL section 7), not a bug - but the orchestrator cannot 'fr run resolve' phase 1. Documented recovery: move the cursor aside FIRST (adopt refuses while a run exists for the same shape+branch), then fr run adopt <plan-dir> --branch feat/phase-holder-identity --run-id <fresh>. Costs: the old cursor's dispatch records, accounting and gate provenance do not carry over. The same applies to the other live fr-goal cursors on this branch (2026-09-20-feat-phase-holder-identity, fix-fr-run-cursor-cluster, ...) if anyone advances them. I did not touch the cursor - it is the orchestrator's. Open until the orchestrator recovers or rules on it.

<!-- fr:journal kind=discovery scope=plan id=p1-fixtures-and-gate created=2026-09-20T22:27:18 phase=1 -->
### p1-fixtures-and-gate · discovery · Captured cursors (8 files, v1-v4) and the phase-1 gate: full suite 0 failed (phase 1)

FIXTURES: tests/fixtures/run_cursors/v{1,2,3,4}/, two per version, each written with git show <rev>:<path>; NOTE.md records source path, rev, last-touching commit, git blob id and SHA-256; tests/unit/test_run_cursor_fixtures.py pins the SHA-256s so a capture cannot be quietly edited (it deliberately does NOT parse them with the live RunState - phase 3 replaces that model). Worth knowing for phases 2-3: v1 means NO schema_version key at all, not 'schema_version: 1'. v2/2026-09-20-journal-require-reviews-v2.yaml is gh#517's cursor as it was BEFORE the fold-in migrated it - an in-flight run with a flat 'deliver: running' and no dispatch map, i.e. the u1 fallback shape in a real file. v4/2026-09-20-feat-phase-holder-identity.yaml carries items + dispatch (multiple attempts, claimed and abandoned) + accounting; v4/...cursor-cluster carries the 'phase/7: manual' marker and was stamp-migrated 2->4. v3/...bounded-executor-handoff has measured token figures, v3/...phases-file-tier has none. NOT captured: this plan's own cursor (untracked, so no committed bytes) - the only one with a CLAIMED OPEN hold; capture it from git show once committed. GATE (CLAUDE* unset, exit codes read from files): pytest -q full = rc 0, 3590 passed / 80 skipped / 0 failed, coverage 91.95%; test_cli_all_fails_when_nothing_is_discoverable (gh#463) PASSED here rather than failing as predicted. ruff check/format --check, mypy (4 trees), bump-version --check, acceptance check (170 rows), acceptance report --check, validate artifacts (48), harness parity --check, both sync --check, bun test (15 pass): all rc 0.

<!-- fr:journal kind=review scope=plan id=rev-p1 created=2026-09-20T22:31:02 phase=1 -->
### rev-p1 · review · Phase 1 reviewed: witness mutation-verified, redispatch decision upheld, no new findings (phase 1)

Reviewed against spec 4.C and decision u1. (1) _hold_on is the single witness predicate and both refusal call sites ask only it (grep-verified: two callers). (2) MUTATION-VERIFIED independently of the executor's own check: making state witness again ('if running' without never_recorded) fails exactly test_advance_after_abandon_briefs_again_and_appends_a_second_record, test_advance_after_abandon_briefs_a_flat_step_again_too and test_advance_does_not_refuse_when_the_last_record_is_closed — the three abandon tests, nothing else; restored byte-identical, 227 pass with CLAUDE* unset. (3) The executor found a SECOND real conflict the orchestrator had not listed — advance --redispatch on a never-dispatched unit exits 0 in gh#508's test and 2 in gh#519's — and kept gh#519's refusal. UPHELD: it is the only specified behaviour (gh#519 spec 3.A), it is published in the explainer, and refusing is the honest answer when there is nothing to re-dispatch; gh#508's test was rewritten to pin that no record is left behind, not deleted. (4) Fixtures are captured via git show with pinned SHA-256s and deliberately NOT parsed by the live model, which is what phases 2-3 need. (5) Deviation accepted: the explainer .html was regenerated rather than kept 'ours', because gh#517 renumbers headings and the freshness tripwire fails otherwise. No new findings from review.

<!-- fr:journal kind=discovery scope=plan id=x-p1-lost-dispatch-history created=2026-09-20T22:31:02 phase=1 -->
### x-p1-lost-dispatch-history · discovery · Manifest drift stranded this run's cursor, and the documented recovery discards its dispatch history (phase 1)

Folding in gh#517 added a journal-check step to the shipped fr-goal manifest, so the cursor adopted an hour earlier hit drift: advance, resolve, claim and gates all refuse; only status and check still read it. The documented recovery — move the cursor aside, re-adopt under a fresh run id — rebuilds state from the PLAN, so phase 1 returns as done with NO attempts: who held it, on which harness, with which model, is gone from the cursor. Preserved here instead, verbatim from the stranded file: {"phase/1/implement-phase": [{"agent": "a77988a78252d0c9f", "agent_type": "super-fr:fr-phase-executor", "dispatched": "2026-09-20T20:02:03+00:00", "harness": "claude-code", "model": "claude-fable-5-1"}]}. Worth knowing for the spec's unit record: drift recovery is a second way, besides _complete_step (finding f7), that a holder history can be silently dropped. Not designed here — adopt carrying units forward from a moved-aside cursor is its own question.

<!-- fr:journal kind=finding scope=plan id=p1-f-run-stranded-resolved created=2026-09-20T22:31:20 phase=1 state=fixed resolves=p1-f-run-stranded -->
### p1-f-run-stranded-resolved · finding [fixed] · resolves p1-f-run-stranded: ORCHESTRATOR ACTION: folding in gh#517 strands THIS run's cursor (manifest drift: added journal-check) (phase 1)

Recovered by the documented path: the drifted cursor was moved aside (kept in the session scratchpad, not deleted) and the plan re-adopted as run 2026-09-20-unit-record-unification-r2, which lands on implement with phase 1 already done. Its dispatch history does not survive adoption, so it was preserved verbatim in discovery x-p1-lost-dispatch-history first. The gh#517 review obligation the executor flagged is met by entry rev-p1.

<!-- fr:journal kind=discovery scope=plan id=p2-accessor-surface created=2026-09-20T22:54:17 phase=2 -->
### p2-accessor-surface · discovery · The accessor surface phase 3 re-implements, and the two signatures that exist only for it (phase 2)

fr/run/units.py is now the ONLY module in packages/fr/src/fr that names .items/.dispatch/.accounting on a cursor (plus model.py, legacy.py, artifacts/). Surface, all pure: unit_state / unit_states / with_unit_state / with_unit_states / unit_keys / attempts / open_attempt / with_attempt_appended / with_last_attempt_replaced / with_units_carried_forward / fan_out_states, and the cost half accounted_keys / estimate_of / estimated_at / measured_of / with_estimate / with_measured. Plus UnitAttempt, a type alias phase 3 re-points from DispatchRecord to Attempt — run_cmd constructs UnitAttempt(dispatched=..., agent_type=..., harness=..., model=...) and annotates with it, so that swap is one line in units.py and zero in run_cmd.py.

TWO SIGNATURES EXIST FOR PHASE 3 AND LOOK ODD TODAY. (1) The cost WRITERS take step_id, the READERS do not; today accounting is a top-level map that does not record which step owns a key, so with_estimate/with_measured ignore the step_id they are given. In v5 the cost hangs off an attempt inside a step's record, so the writer needs it and the reader still scans. It is taken NOW so phase 3 changes no call site. (2) with_estimate takes at= explicitly rather than stamping _now(). See p2-estimate-ordering.

NAMES THAT CHANGED from the plan step's list, and why. estimate_of/measured_of/open_attempt/attempts/with_attempt_appended/with_last_attempt_replaced/unit_keys/unit_state/with_unit_state are all as specified. Added: unit_states + with_unit_states (the bulk merge _advance_group and _resolve_member both do — {**states, **manual_markers} — needs a map, and a wholesale state write is exactly the operation that could drop attempts in v5, so it is a named function with a test rather than an assignment); with_units_carried_forward (finding f7, see p2-f7-one-function); fan_out_states; accounted_keys; estimated_at (the measurement window's start, which is PhaseAccounting.at today and attempt.dispatched in v5 — a separate accessor so ContextEstimate need not carry a timestamp).

<!-- fr:journal kind=discovery scope=plan id=p2-estimate-ordering created=2026-09-20T22:54:46 phase=2 -->
### p2-estimate-ordering · discovery · SURPRISE for phase 3: the estimate must be WRITTEN after _open_dispatch, but COMPUTED before it (phase 2)

_advance_group used to compute the accounting snapshot and hold it in a local dict, applying it at save time with state.model_copy(update={accounting: snaps}). Top-level, so order did not matter. In v5 the estimate hangs off an attempt, and the attempt is opened by _open_dispatch several statements LATER. Writing early would have nothing to attach to.

But the snapshot's timestamp is load-bearing in the other direction: it is the START of the measurement window (_with_measurement reads it), and the docstring's claim that it 'precedes every transcript record of the unit it dispatched' is true only because it is stamped before the brief is built. Computing it late would move it after the dispatch.

So the two are SPLIT: estimate_at = _now() and estimate = _accounting_snapshot(...) stay where they were; units.with_estimate(state, step.id, pending, estimate, at=estimate_at) runs at save time, after _open_dispatch. That is why with_estimate takes at= instead of stamping itself. Phase 3 must keep both halves: in v5, at= becomes the attempt's own , which is the same moment recorded once instead of twice — and if phase 3 instead reuses the attempt's dispatched (stamped INSIDE _open_dispatch, i.e. later), the window start moves after the brief and the measurement silently starts measuring from the wrong edge.

Related: _accounting_snapshot now returns a ContextEstimate with NO  field at all, precisely so the timestamp cannot be carried twice.

<!-- fr:journal kind=discovery scope=plan id=p2-estimate-ordering-corr created=2026-09-20T22:55:25 phase=2 -->
### p2-estimate-ordering-corr · discovery · Correction to p2-estimate-ordering: two words the shell ate, restored (phase 2)

`p2-estimate-ordering` was written with a shell command whose double-quoted body let zsh eat two backtick-quoted words. The journal is append-only, so the two gaps are restored here rather than rewritten there.

Line 5 of that entry should read: *"in v5, `at=` becomes the attempt's own **`dispatched`**, which is the same moment recorded once instead of twice."*

Its last line should read: *"`_accounting_snapshot` now returns a `ContextEstimate` with NO **`at`** field at all, precisely so the timestamp cannot be carried twice."*

Operational note for anyone journalling from a shell: pass `--body "$(cat <file>)"` with the file written from a single-quoted heredoc. Backticks inside a double-quoted `--body` are command substitution, and the failure is SILENT for anything that happens to be a valid command — here `at` is a real binary, so it ran and printed its usage while the word vanished from the entry.

<!-- fr:journal kind=discovery scope=plan id=p2-fixture-population created=2026-09-20T22:55:43 phase=2 -->
### p2-fixture-population · discovery · The captured cursors, corrected and characterised: no unit has two attempts, and the synthesized attempt is the COMMON case (phase 2)

Phase 1's `NOTE.md` says `v4/2026-09-20-feat-phase-holder-identity.yaml` carries *"`dispatch` (several attempts per unit, claimed and abandoned)"*. Read literally that is wrong, and it cost a red test: it is several UNITS with one attempt each, some claimed and some abandoned. **No unit in any of the eight captured cursors has more than one attempt.** `--redispatch` and `claim --abandoned` shipped days before the capture and no real run has used either twice on one unit yet.

So every multi-attempt assertion in phases 2 and 3 has to be built by APPENDING to a captured unit through the accessors (`units.with_attempt_appended`), which is still derived from a capture — never by typing YAML. `tests/unit/test_run_units_access.py::CLAIMED` records this in the fixture's own docstring so phase 3 does not rediscover it.

**Other facts about the captured population, verified mechanically across all eight:**

- **No orphan accounting keys.** Every key in every `accounting` map is owned by exactly one step's `items` or `dispatch`. So the 4 -> 5 rewrite's owner lookup never has to guess, and its orphan refusal is a guard, not a live path.
- **No partial measurements.** Unsurprising — gh#514's validator already calls one invalid — so the partial-measurement refusal is tested by DELETING one figure from a captured cursor.
- **The majority shape is `accounting` with no `dispatch` at all.** `v4/…cursor-cluster.yaml` has six accounted units and an empty dispatch map; so do both v3s, both v2s and the v1 with accounting. §4.F's "synthesized identity-less attempt" clause is therefore the COMMON case, not the edge — most units in most migrated cursors will end up with exactly one attempt carrying nothing but `dispatched` and `estimate`.
- **A flat `step/<id>` unit really exists in a capture.** `HOLDER`'s `deliver` step has `dispatch: {step/deliver: [...]}` and no `items` at all, so §4.B's "a flat step's unit carries no state" is witnessed rather than asserted.
- **`HOLDER`'s `phase/2/review-phase` attempt has NO `agent_type`** — an orchestrator-run member (`agent: null`). Phase 3's renderers must keep treating that as "the orchestrator", not as a missing value.

<!-- fr:journal kind=decision scope=plan id=p2-legacy-divergences created=2026-09-20T22:55:56 phase=2 -->
### p2-legacy-divergences · decision · The frozen v4 reader diverges from a literal copy twice, both to avoid stranding cursors (phase 2)

`fr/run/legacy.py` holds `DispatchRecordV4` / `StepRecordV4` / `PhaseAccountingV4` / `RunStateV4` + `parse_run_state_v4`, pinned by SHA-256 of each class's `inspect.getsource` in `legacy.FROZEN_CLASS_SHA256` and checked by `tests/unit/test_run_legacy.py`. It parses all eight captured cursors, v1 through v4.

**It is NOT a literal copy, and the two divergences are deliberate:**

1. **The vocabularies are inlined** (`STEP_STATES_V4`, `DISPATCH_OUTCOMES_V4`, `ANSWERED_BY_V4` plus the `Literal`s themselves) instead of imported from `fr.run.model`. A frozen reader that followed a live vocabulary stops being a reader of v4 the moment the vocabulary grows.
2. **`DispatchRecordV4` drops the `harness` field validator.** The live model checks `harness` against `fr.harness.model.HARNESSES` and should. But that is a live vocabulary too: retire a harness and every cursor that recorded it becomes unreadable, therefore unmigratable — precisely the "stranding the files the framework exists to carry" failure §4.F names. This reader's job is to READ what fr wrote; the live `parse_run_state` and `fr validate artifacts` still check the vocabulary on the way out.

It DOES keep `extra="forbid"` and the returned/outcome pair validator: a superset of v1-v4 is not a superset of everything, and a half-closed record is as wrong in a v4 file as in a v5 one.

The tripwire hashes the four CLASSES, not the module, on purpose — `v4_to_v5` lives in the same file and is not frozen.

<!-- fr:journal kind=decision scope=plan id=p2-migration-refusals created=2026-09-20T22:56:12 phase=2 -->
### p2-migration-refusals · decision · v4_to_v5 refuses three ways, and two of the three are not in the spec (phase 2)

`fr.run.legacy.v4_to_v5(data: dict) -> dict` — pure, no I/O, no clock, input never mutated (it deep-copies). It does NOT touch `schema_version`: the migration runner writes the stamp, and a body rewrite that also stamped would be two facts in one function. Idempotent on its own output for all eight captures.

**Three refusals, all raising `RunMigrationError` (a `RunStateError` subclass) and naming the key:**

1. a **partial measurement** — §4.F's stated edge. Names the missing field(s).
2. an **accounting key no step records** — nowhere to attach, and dropping a figure to make a cursor convertible is the silent data loss this spec is against. NOT in §4.F; decided here. No captured cursor has one.
3. an **accounting entry with no `at` on a unit with no attempt** — neither an attempt to hang the cost on nor a moment to synthesize one from. NOT in §4.F; decided here. Every captured snapshot has an `at`, so this too is a guard.

Because the function is pure, "a cursor the migration cannot fully convert is left byte-identical" comes for free: there is no half-written state to flush, the caller simply never gets a value. Phase 3's runner `fn` must preserve that — build in memory, write once, through the framework's atomic writer.

**Owner lookup:** `accounting` is top-level and does not say which step owns a key, so the rewrite builds `owner_of` from every step's `items` + `dispatch` first, and attaches each snapshot under that step. `setdefault` means the first step wins if a key were ever in two (none is, verified across all eight).

**Two output shapes worth knowing for phase 3:** a manual marker converts to exactly `{"state": "manual"}` — no `attempts` key at all, not an empty list; and a synthesized attempt is exactly `{"dispatched": <accounting.at>, "estimate": {...}}` — no identity fields, no `outcome`, and no `measured` unless all four figures were there.

<!-- fr:journal kind=decision scope=plan id=p2-model-order-deviation created=2026-09-20T22:56:25 phase=2 -->
### p2-model-order-deviation · decision · Deviation from plan step order: ContextEstimate and MeasuredTokens landed in T1, not T2 (phase 2)

P2.T1 was specified as "accessors only"; P2.T2 adds the models. But the cost accessors have to RETURN something, and returning the storage type (`PhaseAccounting`) would have meant re-porting every caller in phase 3 — defeating the whole point of the phase. So `ContextEstimate` and `MeasuredTokens` were added in T1, where the accessor layer needs them, with their tests in `test_run_unit_models.py` alongside `Attempt` and `UnitRecord`.

What this bought immediately: `estimate_of` returns a `ContextEstimate` and `measured_of` returns a `MeasuredTokens` or `None` — so gh#514's "all four or none" invariant is already STRUCTURAL at the accessor boundary, before the model swap. A partial snapshot reads as no measurement, which is byte-for-byte what `PhaseAccounting.measured_tokens` did, so behaviour is unchanged.

Also in T1 rather than T2, for the same reason: `units.UnitAttempt`, the type alias `run_cmd.py` now constructs and annotates with. `DispatchRecord` is no longer named anywhere in `run_cmd.py`.

Two other order notes for phase 3: `PhaseAccounting` and `DispatchRecord` are still exported from `fr.run.model` and still used by `fr/artifacts/structure.py` and by existing tests — phase 3 removes them, and `structure.py`'s partial-measurement check disappears with them (§4.A) rather than moving.

<!-- fr:journal kind=discovery scope=plan id=p2-f7-one-function created=2026-09-20T22:56:37 phase=2 -->
### p2-f7-one-function · discovery · f7's fix is now one function, not a field list — and so is every wholesale state write (phase 2)

`_complete_step` used to rebuild a `StepRecord` from scratch listing `items=`, `members=` and `dispatch=` as three separate carry-forward expressions — the shape that once dropped the whole run's holder history at the moment a step FINISHED (f7), silently, because only `status`/`check` read it.

It now builds the record without any unit data and applies `units.with_units_carried_forward(new_record, prior)` as ONE call. `members` stays a plain field: it is a manifest fact, not a unit. In v5 the two halves are one object, so a partial copy would be a NEW defect in a NEW shape — making it unexpressible is the point, and `tests/unit/test_run_units_access.py::test_units_carried_forward_keeps_states_and_attempts_together` is the guard.

Same rationale drives `with_unit_states`, which is a function rather than an assignment: `_advance_group` and `_resolve_member` both write the state map wholesale (`{**states, **manual_markers}`), which in v5 is exactly the operation that could drop a unit's attempts. Today the guarantee is free because the maps are separate; there is a test on it so that it survives the day it stops being free.

<!-- fr:journal kind=discovery scope=plan id=p2-exit-grep created=2026-09-20T22:56:54 phase=2 -->
### p2-exit-grep · discovery · The exit-criterion grep: git grep -E silently matches nothing (no \b in POSIX ERE) — use grep -rnE (phase 2)

**The plan step's command finds nothing on this machine, and that is not a pass.** `git grep -nE` uses POSIX ERE, which has no `\b`; the pattern silently matches nothing and `git grep` exits 1, which reads like "clean". Use BSD/GNU `grep -rnE` instead — `grep -rnE '\.items\b|\.dispatch\b|\.accounting\b' packages/fr/src/fr`.

Result after phase 2, with the four exempt paths (`fr/run/units.py`, `fr/run/model.py`, `fr/run/legacy.py`, `fr/artifacts/`) filtered out: **56 hits, and every single one is literally `.items()`** — a `dict.items()` call on a mapping that is not a cursor map. Verified mechanically rather than by eye:

    grep -rnE '\.items\b|\.dispatch\b|\.accounting\b' packages/fr/src/fr \
      | grep -vE '/fr/run/units\.py:|/fr/run/model\.py:|/fr/run/legacy\.py:|/fr/artifacts/' \
      | grep -vE '\.items\(\)'        # -> no output

and separately:

    grep -rnE '\.dispatch\b|\.accounting\b' packages/fr/src/fr \
      | grep -vE '/fr/run/units\.py:|/fr/run/model\.py:|/fr/run/legacy\.py:|/fr/artifacts/'
                                       # -> no output

So there are ZERO remaining `.dispatch` / `.accounting` references anywhere outside the four, and zero `.items` attribute accesses. Prose mentions were rewritten too (`run_cmd._unit_key`'s docstring, `adopt.MANUAL_ITEM`'s, `provenance._gated_steps`'s) so phase 3's rename does not leave stale field names in comments.

<!-- fr:journal kind=finding scope=plan id=f-p2-blind-grep created=2026-09-20T23:03:06 phase=2 state=fixed -->
### f-p2-blind-grep · finding [fixed] · The plan's own exit-criterion grep could not match anything, so it could not fail (phase 2)

The orchestrator's own plan step P2.T1.S3 made a grep the phase's exit criterion: git grep -nE '\.items\b|\.dispatch\b|\.accounting\b'. It can never match: git grep -E is POSIX ERE, which has no \b, so it found NOTHING and exited 1 — which reads exactly like "no direct accesses left". Verified independently: on fr/run/units.py, a file containing six such accesses, git grep -E returns rc=1 while plain grep -E finds all six. A verification that cannot fail is not a verification; this is the exit-code family of defects (f3, f11, the inert set -e) in a fifth disguise, and this time it was authored into the plan. FIXED by the executor not trusting the pass: re-run with grep -rnE, 56 hits, every one mechanically shown to be a dict.items() call (filtering '\.items\(\)' leaves nothing; '\.dispatch\b|\.accounting\b' alone leaves nothing). Re-verified by the orchestrator: 0 direct accesses outside the accessor layer. No other plan step uses \b with git grep (checked). Rule going forward: run a verification command against a KNOWN POSITIVE first, to prove it can fail.

<!-- fr:journal kind=review scope=plan id=rev-p2 created=2026-09-20T23:03:07 phase=2 -->
### rev-p2 · review · Phase 2 reviewed: behaviour-preserving by proof, exit criterion re-verified, three deviations accepted (phase 2)

Phase 2 reviewed against spec 4.A, 4.B, 4.F and the plan. (1) Exit criterion met and re-verified with a grep that can actually fail: zero direct accesses to items/dispatch/accounting outside fr/run/units.py, model.py, legacy.py and fr/artifacts/. (2) ZERO test edits confirmed from git: four new test files, no modified ones — so the refactor is behaviour-preserving by the only proof available, the pre-existing suite (3590 -> 3713 = exactly the 123 new tests). (3) Frozen-source tripwire present (hash-pinned). (4) Three deviations ACCEPTED: ContextEstimate/MeasuredTokens landed a task early because an accessor must return something and returning the storage type would have forced re-porting every caller in phase 3; the legacy reader deliberately DROPS the harness validator, because HARNESSES is a live vocabulary and a retired harness would make every cursor that recorded it unmigratable — the exact stranding the legacy reader exists to prevent; v4_to_v5 refuses two cases beyond the spec's one (an accounting key no step records; accounting with no timestamp on a unit with no attempt), both induced from real captures. (5) Two facts the spec had wrong or thin, now amended: accounting WITHOUT dispatch is the MAJORITY shape across the captured cursors, so the synthesized identity-less attempt is the common migration case, not an edge; and in v5 there is ONE timestamp — the attempt's dispatched — with ContextEstimate carrying no 'at', so the moment cannot be recorded twice and drift. One finding, against the orchestrator's own plan: f-p2-blind-grep.

<!-- fr:journal kind=decision scope=plan id=p3-synthesized-not-a-hold created=2026-09-20T23:46:33 phase=3 -->
### p3-synthesized-not-a-hold · decision · A synthesized attempt carries cost, never a hold — new Attempt.synthesized marker, NOT in the brief (phase 3) (phase 3)

**The design hole phase 3 found, and the one decision in this phase that was NOT in the brief.** Spec §4.F step 3 has the rewrite synthesize an identity-less attempt (`dispatched = accounting.at`, plus the estimate) for every unit that had a cost snapshot and no dispatch record — the MAJORITY of real units (`p2-fixture-population`). Spec §4.C says a unit is held iff its last attempt is open. The synthesized attempt has no `returned`, because fr never knew one. Put together, every pre-#508 unit of every migrated cursor read as HELD.

Found by running migrated captures end to end, not by reading: `test_open_attempt_is_none_when_every_attempt_returned` went red on `HOLDER` the moment `_state()` was re-pointed at the real rewrite. Consequences, all verified:

1. `fr run check` reported every finished unit of an older cursor as `is open` (it rides the PR body).
2. **`fr run advance` REFUSED TO RETRY a `failed` unit of an in-flight run**, naming a holder that never existed — v4 simply re-briefed it. This is the one that would have blocked real runs on upgrade day.
3. `fr run status` rendered it `held by the orchestrator`, because an absent `agent_type` on a RECORDED attempt means exactly that. These units were phase executors.

**Decision: `Attempt.synthesized: Literal[True] | None`, and the witness skips it — "a synthesized attempt carries COST, never a HOLD".** `units.open_attempt` ignores it; new accessor `units.dispatch_recorded(record, key)` answers "is there any WITNESS?" and is what `_hold_on`'s recordless fallback now asks (it used to ask `not attempts`). Net effect: a migrated unit behaves EXACTLY as it did while its cost lived in the v4 `accounting` map, which no witness ever read — `running` is still refused on state (`ALREADY RUNNING (dispatched <at>)`), `failed` is re-briefed and the retry is appended BESIDE the synthesized attempt, `done` is inert.

Rejected: (a) closing the synthesized attempt — needs a `returned` timestamp fr does not have, and `returned`/`outcome` are one fact by model validator; any value would be invented. (b) consulting unit state in the witness (`done`/`failed` => not held) — puts state back into u1's predicate, and the retry path would then append a second OPEN attempt and fail `validate_run`. (c) inferring "synthesized" from "no identity fields at all" — an orchestrator-run review on an undetectable harness with no tier binding looks identical.

Guards: the model REFUSES identity/`returned`/`outcome` on a synthesized attempt; `validate_run` requires it to be the unit's FIRST attempt and never counts it as open. Mutation-verified: dropping the skip in `open_attempt` fails 7 tests, weakening `dispatch_recorded` fails 2.

`legacy.py` WAS edited — `_attach_cost` writes `"synthesized": True` and `v4_to_v5`'s docstring says why. Those are NOT among the four hash-pinned classes; `FROZEN_CLASS_SHA256` is untouched and `test_run_legacy.py` is green. Phase 2's `test_accounting_with_no_dispatch_synthesizes_one_identityless_attempt` now pins `{dispatched, estimate, synthesized}`. Spec §4.A and §4.F amended in place, marked as phase-3 amendments.

**Phases 4-6:** cost accessors (`estimate_of`/`measured_of`/`estimated_at`) read the unit's LAST attempt, synthesized or not — so a `running` synthesized-only unit is still measured at `resolve`, onto the synthesized attempt. Anything that walks `units.attempts()` to reason about HOLDERS or sessions (§4.D.1, §4.G liveness) must skip `synthesized` ones; anything reasoning about COST must not.

<!-- fr:journal kind=finding scope=plan id=p3-phase-key-broader created=2026-09-20T23:46:34 phase=3 state=fixed -->
### p3-phase-key-broader · finding [fixed] · Spec 4.B's 'phase/<n> is state: manual, always' is refuted by a captured cursor; validate_run enforces 'never any attempts' instead (phase 3) (phase 3)

Spec §4.B said `phase/<n>` is "gh#496's manual-phase marker — `state: manual`, `attempts` empty, always", and the brief repeated it. A captured cursor refutes the "always": `tests/fixtures/run_cursors/v1/2026-09-09-feat-issue-464.yaml` carries `phase/1: pending` .. `phase/5: pending`. That is a FLAT `for_each: phase` step (no member steps), and `fr run adopt` still writes it today (`adopt.build_run_state`'s `else:` branch).

Caught by `test_every_captured_cursor_migrates_all_the_way_to_current`, which asserts `validate_run(path) == []` on every migrated capture: enforcing `state: manual` would have failed `fr validate artifacts` on every such cursor the moment it migrated — turning CI red for a file fr wrote correctly.

**What `validate_run` enforces instead:** a `phase/<n>` unit carries a `state` (any `UnitState`) and NEVER any attempts. That is what the marker and the flat unit have in common, and it is the part that matters: fr dispatches a phase's MEMBERS, never the phase (`advance` refuses a member-less `for_each` outright). Spec §4.B amended in place.

The other §4.B rules are enforced as written: `step/<id>` carries no `state` (and must record SOMETHING — attempts or evidence); `phase/<n>/<member>` must carry one; at most one open attempt and it is the last; unknown key forms refused. Also new: a cursor carrying `units` under `schema_version < 5` is reported (`UNIT_RECORD_SCHEMA_VERSION`) — it replaces the v3 "measured tokens under a v2 stamp" check, which disappeared with `accounting`, and it is exactly the state the migration's crash window leaves.

<!-- fr:journal kind=finding scope=plan id=p3-f-stale-cursor-invisible created=2026-09-20T23:46:34 phase=3 state=fixed -->
### p3-f-stale-cursor-invisible · finding [fixed] · find_run_for_plan could not see a not-yet-migrated cursor: the migrate preview offered to adopt plans that already had one (phase 3) (phase 3)

§4.F.1's blast-radius audit missed one reader: `fr.archive.find_run_for_plan` — behind both `fr archive` and adoption's "does this plan already have a run?" (`adoptable_plans`). It parsed each cursor with the LIVE model and `continue`d on `RunStateError`. The live model no longer knows `items`, so **a not-yet-migrated cursor was indistinguishable from no cursor.**

Seen live, not theorised: the moment the registry moved to 5, `uv run fr migrate artifacts` (the PREVIEW) over this repo printed "6 in-flight plan(s) have no run cursor" and offered to adopt four plans that already had one. After `--yes` it said 2, correctly.

The preview is merely wrong. The dangerous path is a cursor the 4 -> 5 rewrite REFUSES (partial measurement): it stays v4 indefinitely, and `fr migrate artifacts --yes --adopt` — migration first, adoption second — would then write a SECOND cursor for the same plan beside it.

Fix: `archive._read_any_version` tries the live parser, then `fr.run.legacy.parse_run_state_v4`. `emitted.plan` and `run` are the same facts in every version; nothing is written. RED first: `test_run_adopt.py::test_a_plan_whose_cursor_is_still_in_the_v4_shape_is_not_offered_for_adoption`, on the captured held cursor.

Audited the rest while there (`grep -rnE 'parse_run_state\(|load_run_state\('` over `packages/fr/src/fr`): the only other readers are `commands/run_cmd.py`, all behind the CLI-entry gate (not exempt), so they never see a stale cursor except under `FR_SKIP_MIGRATION=1`. `fr_dispatch`/`fr_vk`/`fr_cncd` still never load a cursor.

<!-- fr:journal kind=discovery scope=plan id=p3-accessors-v5 created=2026-09-20T23:47:20 phase=3 -->
### p3-accessors-v5 · discovery · The v5 accessor layer: what moved in run_cmd (four places), the one-timestamp wiring and its trap, and what is still unwritten (phase 3) (phase 3)

What the v5 accessor layer looks like, for phases 4-6. `fr/run/units.py` is still the ONLY module outside `model.py`, `legacy.py` and `fr/artifacts/` that touches the shape — re-verified with a grep that can fail (known positive: 11 hits inside `units.py`; outside the four exempt paths, zero attribute accesses to `.units`/`.items`/`.dispatch`/`.accounting`).

**Callers barely moved, as designed.** `run_cmd.py` changed in exactly four places: `_open_dispatch` gained `at=` (below); `_hold_on` asks `units.dispatch_recorded` instead of `not units.attempts`; `_render_dispatch_attempt` has a `synthesized` branch; `_complete_step` is a `model_copy` (below). `adopt.py`, `provenance.py`, `telemetry.py`: zero logic changes.

**ONE timestamp — how it is wired, and the trap.** `_advance_group` takes `estimate_at = _now()` BEFORE assembling the estimate and building the brief, and passes that SAME value to `_open_dispatch(..., at=estimate_at)` (the attempt's `dispatched`) and to `units.with_estimate(..., at=estimate_at)`. `with_estimate` RAISES `ValueError` if `at` is not the last attempt's `dispatched`, or if there is no attempt. The trap: `_now()` has one-second resolution, so wiring the two moments apart almost never shows — hence `test_the_attempt_is_dispatched_at_the_moment_its_estimate_was_assembled`, which makes the clock tick on every read (mutation-verified: drop `at=estimate_at` and it fails with the ValueError). The flat `kind: agent` branch passes no `at` and records no estimate; `_open_dispatch` stamps it there, still before the brief is printed.

**Cost is per ATTEMPT on disk, per UNIT through the accessors.** `estimate_of` / `measured_of` / `estimated_at` / `accounted_keys` answer for the unit's LAST attempt. Earlier attempts keep their own figures on the cursor (`test_cost_is_per_attempt_a_redispatch_does_not_overwrite_the_abandoned_spend`), but NOTHING RENDERS THEM YET and `claim --abandoned` does not measure yet — that is decision u2 / §4.D, phase 4's. `fr run status`'s accounting block is unchanged in shape: one line per accounted unit, key-sorted.

**`with_unit_states` never drops history.** A key omitted from a wholesale state write keeps its attempts/evidence, stateless, instead of being deleted (guard, not a live path — every caller widens the map).

**`_complete_step` is `prior.model_copy(update=…)`** — carry-by-default, so the next durable field on `StepRecord` survives completion without anyone remembering it. `members` with an empty list would now stay `[]` rather than becoming `None`; no writer produces one. `units.with_units_carried_forward` therefore has NO caller in `src/` any more; kept (with its test) for a caller that builds a record from scratch, flagged here so review can delete it instead.

**`dump_run_state` drops an empty `attempts`.** A never-dispatched unit is `{state: done}` on disk — the same bytes the rewrite writes — and `test_a_migrated_capture_and_a_native_dump_are_the_same_data` pins migrated == native for all nine captures. `units` sits after `members` in `StepRecord` so key order matches the rewrite's too.

**Gone from `fr.run.model`:** `DispatchRecord`, `PhaseAccounting`, `MEASURED_TOKEN_FIELDS`, `MEASURED_TOKENS_SCHEMA_VERSION`. New: `UNIT_RECORD_SCHEMA_VERSION = 5`, `Attempt.synthesized`. `UnitRecord.evidence` and `Attempt.session` exist and are UNWRITTEN — phases 5 and 4 respectively.

<!-- fr:journal kind=discovery scope=plan id=p3-migration-module created=2026-09-20T23:47:21 phase=3 -->
### p3-migration-module · discovery · run 4->5: the migration module, the crash window it survives (not in the spec), and what 'byte-identical' means through a chain (phase 3) (phase 3)

`fr/artifacts/run_unit_record.py` — the first BODY-REWRITING run migration, 4 -> 5 — and what is true of the chain now.

- **Every hop reads with the frozen model.** `run_cursor.cursor_guard` uses `parse_run_state_v4`; `run_dispatch_holder` had its OWN copy of that guard (reading with the live model) and now uses the shared one, so there is one guard, not two. Tripwire: `test_no_run_migration_names_the_live_parser` (regex proven against a known positive in the test itself); behavioural half: `test_each_stamp_only_hop_reads_a_cursor_the_live_model_may_no_longer_know`.
- **Chain `[2, 3, 4, 5]`, every hop asserted**, from/to both (`test_the_run_kind_is_reachable_all_the_way_from_version_one_to_five`). `test_every_captured_cursor_migrates_all_the_way_to_current` runs the SHIPPED registry over all nine captures and asserts the exact hop list per file, the live parse, and `validate_run == []`.
- **Build in memory, write once**: `v4_to_v5` -> `write_text_atomic`. No write at all when the rewrite changes nothing (so a unit-less cursor keeps its bytes; the pre-existing "stamps it and rewrites no body" tests still hold). A failing `os.replace` leaves bytes + mtime identical and no temp file.
- **Refusals** raise `UnreadableRunCursorError` / its subclass `UnconvertibleRunCursorError` (wrapping `RunMigrationError`), naming the field. Note what "byte-identical" means through the CHAIN: a v3 cursor with a partial measurement is honestly stamped 3 -> 4 by the stamp-only hop (it reads fine) and THEN refused at 4 -> 5, so its stamp line moved and its body did not. A v4 one is byte- and mtime-identical. Both asserted.
- **The crash window — NOT in the spec.** `fn` writes the body, the RUNNER writes the stamp afterwards. A crash between leaves a v5 body under `schema_version: 4`; the frozen reader is `extra="forbid"` and refuses `units`, so a naive `fn` would refuse that file forever — and it is by construction an in-flight run's cursor. `fn` accepts a body that is ALREADY wholly v5 (no legacy map anywhere AND the live model reads it) and returns, letting the runner finish. That is the one legitimate use of the live parser in a migration and is allowed by name in the tripwire. `units` beside a legacy map is still refused. `validate_run` reports the same state (`units` under a stamp < 5).

**This repo's own cursors:** `uv run fr migrate artifacts --yes` migrated all six and — note — does NOT commit ("6 migrated, not committed"); committed by hand as `a3b1d9a`. The rule added to `.claude/rules/artifact-versioning.md` is a five-point section, mirrored by `scripts/sync-opencode.py`.

<!-- fr:journal kind=discovery scope=plan id=p3-live-upgrade created=2026-09-20T23:47:21 phase=3 -->
### p3-live-upgrade · discovery · run-upgrade-mid-run-keeps-holder, demonstrated live on the cursor dispatching this phase — what happened, step by step (phase 3) (phase 3)

Acceptance row `run-upgrade-mid-run-keeps-holder`, demonstrated LIVE on the cursor that was dispatching this phase (`docs/superpowers/runs/2026-09-20-unit-record-unification-r2.yaml`), in this order:

1. The cursor was v4, UNCOMMITTED, holding an open claimed attempt on `phase/3/implement-phase` (this executor). Committed as-is first (`b7fd771`) — the gate holds back a dirty artifact, and committed bytes are what a capture needs.
2. **Captured** from `git show b7fd771:<path>` as `tests/fixtures/run_cursors/v4/2026-09-20-unit-record-unification-r2.yaml` (SHA-256 pinned in `NOTE.md`) — the first captured cursor with a HELD unit, which `NOTE.md` had listed as owed since phase 1. There are now NINE captures.
3. Registry moved to 5. `uv run fr run status <run>` and `fr run check <run>`: both exit 2 with the six-line refusal ("non-interactive ... preview: fr migrate artifacts / apply: fr migrate artifacts --yes / bypass ..."). Expected, and nothing was written.
4. `uv run fr migrate artifacts` (preview): 6 would migrate. `--yes`: 6 migrated, 0 failed, not committed; nothing was held back because nothing was dirty.
5. `uv run fr run advance <run>` on the migrated cursor: **exit 2**, "phase/3/implement-phase is ALREADY HELD by agent a6003d674a7d2ef75 (super-fr:fr-phase-executor, claude-code, claude-fable-5-1) (dispatched 2026-09-20T21:04:30+00:00) — not yet returned", and the cursor's SHA-256 was unchanged by the refusal. `fr run check`: exit 0, one open line naming the same holder. `fr run status`: every unit state, all four attempts, all four cost lines incl. the 31,789,276-token measurement on `phase/2/implement-phase`.

The same scenario is `tests/unit/test_run_upgrade_in_flight.py` on the capture, plus `test_the_holder_can_still_resolve_its_unit_after_the_migration` (the held executor's own `resolve` closes THE SAME attempt — one attempt, identity and cost intact). "Equivalent `check` output" is asserted against the FROZEN legacy reader's view of the same capture, an independent path sharing no code with the v5 model.

<!-- fr:journal kind=review scope=plan id=rev-p3 created=2026-09-21T00:01:50 phase=3 -->
### rev-p3 · review · Phase 3 reviewed: two spec refutations upheld, synthesized-attempt fix mutation-verified on real captures (phase 3)

Phase 3 reviewed against spec 4.A, 4.B, 4.C, 4.F and artifact-versioning.md. The executor refuted two parts of the orchestrator's spec with evidence, and both refutations are UPHELD.

(1) Spec 4.F step 3 (synthesize an identity-less attempt for cost that predates the dispatch record — the MAJORITY migration case) and spec 4.C (a unit is held iff its last attempt is open) were JOINTLY wrong: a synthesized attempt has no 'returned', so every pre-#508 unit of every migrated cursor read as HELD, fr run check listed finished units as open, and fr run advance refused to retry a failed unit while naming a holder that never existed. Fix upheld: Attempt.synthesized marks it, the witness skips it, the model refuses identity/returned/outcome on it. The rejected alternatives were the right ones to reject — closing it needs a 'returned' fr never had (invention), and consulting state in the witness re-pollutes decision u1. VERIFIED INDEPENDENTLY on real captures: 30 synthesized attempts across three captured cursors, zero wrongly held. MUTATION-VERIFIED: dropping the skip from open_attempt fails exactly 7 tests, the count the executor reported, including the failed-unit-retry one. (The orchestrator's FIRST mutation attempt silently did not apply and 'passed' — caught only because the script printed whether it mutated. A check that cannot fail, again.)

(2) Design decision 4 said a phase/<n> key is always 'state: manual'. A CAPTURED v1 cursor carries 'phase/1: pending' (a flat for_each step, which fr run adopt still writes). The rule is now: a phase/<n> unit carries a state and never any attempts.

(3) A reader the orchestrator's blast-radius audit MISSED: fr.archive.find_run_for_plan parsed cursors with the live model and skipped unparseable ones, so a not-yet-migrated cursor looked like NO cursor — the migrate preview offered to adopt plans that already had one, and --yes --adopt would have written a SECOND cursor beside any the rewrite refuses. Now falls back to the legacy reader.

Frozen reader intact: legacy.py changed by 8 lines, all in the unfrozen v4_to_v5 rewrite; the four hash-pinned classes are untouched. Live upgrade demonstrated on this run's own cursor: held before, held and still named after. Review's own change: removed units.with_units_carried_forward and its two tests — dead once _complete_step became model_copy(update=...), which carries every field by construction and so closes finding f7's trap structurally rather than by a maintained list.

<!-- fr:journal kind=discovery scope=plan id=p4-cost-surface created=2026-09-21T00:36:35 phase=4 -->
### p4-cost-surface · discovery · Cost per attempt: the accessor + writer surface phases 5-7 inherit, and the three strings that changed (phase 4)

**What phases 5-7 inherit from the cost flip.** Every attempt now carries its OWN cost, end to end, and nothing reads "the unit's cost" to render or total any more.

**`fr/run/units.py` — three new accessors, four old ones with no caller left.**
- `last_attempt(state, key)` — the attempt every cost WRITE lands on. It hands back the `Attempt` whole rather than a timestamp, because a measurement needs four of its fields at once: `dispatched`/`returned` (the window) and `(session, agent)` (which transcript).
- `accounted_attempts(state) -> tuple[(key, Attempt), ...]` — key-sorted, oldest attempt first within a unit. What `fr run status` renders and totals.
- `dispatched_attempts(state) -> int` — the denominator, now ATTEMPTS. Counting units reported better coverage than there is the moment one unit was redispatched.
- `estimate_of` / `measured_of` / `estimated_at` / `accounted_keys` still answer the per-UNIT (last-attempt) question and now have ZERO callers in `src/`. See `p4-per-unit-accessors-callerless` — flagged for review, not deleted.

**`_with_measurement` (run_cmd) — four refusals, each a fact.** No attempt; no estimate (no window was ever opened — a flat `kind: agent` step); `returned is None`; already measured. The third is what keeps a `synthesized` attempt unmeasurable by construction: it has no `returned` because fr never knew one, so the migrated cost carrier can never be re-estimated or measured. Before phase 4 it WAS measurable, over a window `[synthesized.dispatched, now]` that could span days. The fourth is what stops a `resolve` after a `claim --abandoned` from rewriting the abandoned attempt's figure.

**Both closers measure.** `resolve` (as before) and `claim --abandoned` (new: `_claim_abandon` now calls `_with_measurement` on the attempt it just closed). The spend that produced nothing is the spend worth seeing.

**Wording that CHANGED and may break a phase-5/6/7 assertion:**
- `measured total: N tok over X of Y dispatched attempts` — was `dispatched units`. Same for the `none` variant.
- the per-unit estimate line lost its `<key>: ` prefix; it sits under its attempt now, so the key is the line above.
- everything else is gh#514's wording verbatim, deliberately: `measured: N tok billed across the dispatch's turns (...) — cumulative harness accounting, NOT comparable to the one-dispatch ~N tok estimate above`, and `not measured: no transcript figure for this unit — the ~N tok above is an ESTIMATE`.

**No shape change to `Attempt`.** `session`, `estimate`, `measured` were all already on the v5 model (phase 3 left `session` unwritten); the registry stays at run v5 and no migration was needed.

<!-- fr:journal kind=decision scope=plan id=p4-session-two-defences created=2026-09-21T00:36:57 phase=4 -->
### p4-session-two-defences · decision · Cross-session cost: TWO defences, not one — and the 4.D.1 test that passed under the wrong mutation (phase 4)

**Two independent defences, and the spec only names one of them.**

Spec 4.D.1 says a transcript is looked up by `(session, agent)` in the RECORDED session's directory, and that the window fallback is allowed only when the attempt's session is the current one. Implemented, both — and they are genuinely two mechanisms, which the mutation testing proved by accident:

1. **`claude_code_session(env, session=None)` resolves the RECORDED session first** (`session or current_session(env)`). It must NEVER fall back to the current session's directory when the recorded one is absent: that fallback is exactly the road to the stranger. Mutation (`session_id = current_session(env)`): 2 tests fail.
2. **`select_for_attempt(..., same_session)` shuts the window** for anything this session did not dispatch. Mutation (drop the two-line gate): 3 tests fail.

**The trap I walked into, recorded because it is this repo's recurring one.** My first version of the 4.D.1 test — host B resolving host A's open attempt while B's own session holds exactly one unrelated subagent in the window — passed under mutation (2), because defence (1) had already refused it at the directory lookup. A test that names a mechanism and is defended by a different one is a test that cannot fail for its stated reason. The fix was to assert BOTH layers explicitly in that test (`claude_code_session(env, "sess-a") is None`, and `select_for_attempt(..., same_session=False) is None` with the `same_session=True` call returning the stranger as non-vacuity). Every mutation run printed whether the mutation applied; both did.

**`same_session` is a PROOF, never a default.** `dispatched_from_this_session(env, session)` returns False when EITHER side is None. So:
- attempt has no `session` (every pre-phase-4 attempt, every harness with no session concept) -> window shut, agent-id path still open (it is exact);
- this process has no session id -> window shut.
Not knowing where an attempt came from is not the same as knowing it came from here.

**No hostname, anywhere.** `test_no_hostname_is_recorded_or_read_anywhere_in_telemetry` pins it (no `gethostname`, no `socket`, no `platform.node`). A missing session directory already says "elsewhere", and a hostname in a public repo's committed cursor is identity nobody needs.

**Rename:** `telemetry.measure_unit` is gone; `measure_attempt(env, *, session, agent, start, end)` replaced it. Its four arguments are one attempt's four facts. `measure_dispatch` and `ClaudeCodeReader.measure` gained `agent=` and `same_session=`, both defaulting to the old behaviour so the reader Protocol stays satisfiable by a second harness that has no session concept.

<!-- fr:journal kind=discovery scope=plan id=p4-status-layout created=2026-09-21T00:37:19 phase=4 -->
### p4-status-layout · discovery · status renders cost beneath each holder; the third absence ('not observable from here') and the refusal's new sentence (phase 4)

**Three sections, four renderers.** `status_cmd`'s body is now four lines: `_render_cursor`, `_render_step_and_items`, and `_print_accounting` behind an `if units.accounted_attempts(state)`. The per-attempt renderers sit under the second: `_render_dispatch_attempt` (the holder line, unchanged) and `_render_attempt_cost` (new — gh#514's `_print_accounting` body, moved verbatim except for the key prefix).

**What it looks like on this run's own cursor** (rendered live before committing):

```
    phase/3/implement-phase: done
      agent a6003d674a7d2ef75 (claude-code, claude-fable-5-1) 2026-09-20T21:04:30+00:00 -> 2026-09-20T22:02:04+00:00 done
        journal 25 entries/197 lines, handoff 20647 chars, spec+plan 73750 chars (~23599 tok est)
        measured: 56092764 tok billed across the dispatch's turns (in 522, cache-create 643986, cache-read 55292865, out 155391) - cumulative harness accounting, NOT comparable to the one-dispatch ~23599 tok estimate above
```

That is a 2,377x gap between estimate and measurement on a real phase — the ratio gh#514's wording exists for, now sitting directly under the agent that produced it.

**The third absence.** A cost line with no measurement now has TWO forms, and they are different facts:
- `not measured: no transcript figure for this unit — the ~N tok above is an ESTIMATE` — a figure that could still arrive;
- `not observable from here: this attempt was dispatched from another session, whose transcripts did not travel with the branch — the ~N tok above is an ESTIMATE` — one this session can never produce.
The predicate is `_cost_observable_here` and it is deliberately the same rule as the refusal's (`_dispatched_from_another_session`), both reading `telemetry.dispatched_from_this_session`. An attempt with NO recorded session prints the first, not the second: not knowing is not knowing.

**The refusal.** `_already_running_refusal` gains one sentence when the holder's session is not this one: "Dispatched from ANOTHER session: this one cannot see whether that agent is alive, and its cost is not observable from here. If it died with its host (a run picked up on another machine), close it with the `lost agent` line below." The `lost agent: fr run claim ... --abandoned` line was already there; the sentence is what tells the operator to reach for it rather than wait. `test_advance_refusing_its_own_sessions_holder_says_nothing_about_sessions` pins that the ORDINARY refusal does not acquire it — every other refusal fr prints means "someone is working", and this one must stay distinguishable.

**One test rewritten rather than patched.** `test_run_upgrade_in_flight.py` asserted `f"{key}: journal {n} entries" in flat`, which the moved rendering deletes. It now finds the indented BLOCK under the unit's own line (`_unit_block`) and asserts the estimate is inside it — strictly stronger than the prefix was, because it fails if the figure lands under the wrong unit.

<!-- fr:journal kind=discovery scope=plan id=p4-session-test-discipline created=2026-09-21T00:38:03 phase=4 -->
### p4-session-test-discipline · discovery · A test that passed only because the machine was a Claude Code session, caught by the phase that made session identity load-bearing (phase 4)

**A test in this file passed only because the authoring machine was a Claude Code session — and phase 4 is the phase that catches that.**

`test_resolve_records_measured_tokens_for_the_unit_it_closes` ran its `advance` through the bare `_invoke` helper (no session declared) and its `resolve` through `_invoke_measurable` (session `sess-1`). Click's `CliRunner(env=...)` MERGES into `os.environ` rather than replacing it, so on a developer machine inside Claude Code the advance inherited the operator's real `CLAUDE_CODE_SESSION_ID`. That did not matter while the window was unconditional. The moment the window required `attempt.session == current session`, the test went red under `env -u CLAUDE_CODE_SESSION_ID` and stayed green without it — the signature the phase brief warned about, reproduced exactly.

Fixed by declaring the session on the `advance` too, with the reason written into the docstring. **Every new test in phase 4 declares both the harness and the session id**; `tests/unit/test_run_telemetry.py`'s `_env` helper exists only to make that the path of least resistance. The full suite was run throughout as `env -u CLAUDECODE -u CLAUDE_PLUGIN_ROOT -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_CODE_SESSION_ID uv run pytest`.

**The fixture rule held.** The overlap and cross-session cases are built from the CAPTURED transcript (`tests/fixtures/transcripts/`), not authored: `transcript_sessions.add_dispatch` copies the captured orchestrator tool_use record and the captured subagent stream, and re-keys only timestamp / agent id / tool_use id / usage. Two calls with the same timestamp IS the overlap case. Nothing in phase 4 invents a transcript shape.

**One consequence for phases 5-7:** an `fr run advance` from a session fr cannot identify opens an attempt with `session: None`, and such an attempt can only ever be measured by AGENT ID. If nothing claims it, its cost is unrecoverable by design. That is the honest trade for never borrowing a window.

<!-- fr:journal kind=discovery scope=plan id=p4-per-unit-accessors-callerless created=2026-09-21T00:38:17 phase=4 -->
### p4-per-unit-accessors-callerless · discovery · Four per-unit cost accessors now have no caller in src/ — flagged for review, not deleted (phase 4)

**REVIEW DECISION OWED, same shape as phase 3's `with_units_carried_forward`.**

After phase 4, `units.estimate_of`, `units.measured_of`, `units.estimated_at` and `units.accounted_keys` have **no caller in `src/`**. `_with_measurement` moved to `units.last_attempt` (it needs the whole attempt, not a timestamp), and `fr run status` moved to `units.accounted_attempts` / `units.dispatched_attempts`, because the per-UNIT question cannot see a redispatched unit's earlier attempt — it shows the retry and hides the abandoned spend, which is the defect section 4.D exists to fix.

Verified with a grep that can fail (`grep -rn "units\.<name>(" packages/*/src`, counted): `with_measured` 1, `last_attempt` 1, `accounted_attempts` 2, `dispatched_attempts` 1, and the four above 0.

They are NOT dead the way `with_units_carried_forward` was, which is why I flagged rather than deleted: `tests/unit/test_run_cli.py`'s `_Snapshot`/`_accounting` helpers read a unit's cost through them instead of through the storage — precisely the seam `fr/run/units.py` exists to offer — and `tests/unit/test_run_units_access.py` covers them directly. Deleting them would push those tests onto `.attempts[-1].estimate` and put shape knowledge back into the test file the v5 flip took it out of.

**What review should decide:** keep them as the sanctioned per-unit read (accepting a public surface with no production caller), or delete them and give the tests a different reader. Noted in `fr/run/units.py`'s cost-section comment too, so the question is visible at the code and not only here.
