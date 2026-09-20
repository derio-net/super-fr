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
