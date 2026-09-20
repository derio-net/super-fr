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

<!-- fr:journal kind=finding scope=plan id=p1-preexisting-install-bridge created=2026-09-20T11:55:51 phase=1 state=fixed -->
### p1-preexisting-install-bridge · finding [fixed] · Pre-existing, environment-caused test_install_bridge failure (unrelated to this phase) (phase 1)

Full suite (uv run pytest -q --basetemp=/tmp/sb) is 3303 passed / 85 skipped / 1 failed: tests/integration/test_install_bridge.py::test_install_bridge_flag_writes_wrapper. Not caused by this phase's diff — the same devcontainer-global-uv-tool-install state already documented in docs/superpowers/journals/plans/2026-09-19-opencode-subagent-dispatch.md and 2026-09-20-opencode-tier-binding-reaches-dispatch.md: the globally uv-tool-installed fr at /home/vscode/.local/share/uv/tools/fr/bin/python cannot import fr_vk.bridge (the test uses the real host env, not the sandboxed fake_home fixture). Marked fixed rather than open: a known, already-documented environment artifact, not a regression for a later phase to chase.

<!-- fr:journal kind=finding scope=plan id=f1 created=2026-09-20T14:02:59 phase=1 state=fixed -->
### f1 · finding [fixed] · DispatchRecord documented the returned/outcome pairing but nothing enforced it (phase 1)

The field docstring said outcome is 'None exactly when returned is None', and no validator held it. A half-closed record answers 'is this dispatch open?' differently depending on which half a reader looks at — returned without outcome reads as still-held while carrying a return timestamp; outcome without returned reads as held forever by an agent that already finished. Since every consumer (status naming the holder, advance refusing a second, check counting debt) keys on exactly that question, the invariant cannot live at each call site. FIXED: a model_validator(mode='after') on DispatchRecord refuses either half alone, with a test covering all four combinations. One existing phase-1 test constructed outcome without returned and was corrected.

<!-- fr:journal kind=finding scope=plan id=f2 created=2026-09-20T14:02:59 phase=1 state=fixed -->
### f2 · finding [fixed] · Spec 4.D's 'the run structure validator learns dispatch' produced no code change (phase 1)

structure.py was not in phase 1's diff. The executor's own report explains why — the two new validator tests 'passed immediately since validate_run already delegates to RunState' — which is an honest note but means a test that never went red and a spec item effectively unimplemented. Delegation covers the TYPE shape and nothing else: a dispatch key of any spelling, an empty attempt list, two simultaneously open records, or an open record that is not the last all parse cleanly. The last of those is the invariant the entire double-dispatch refusal rests on. FIXED: validate_run now reports all four, with four tests that were red first. Deliberately placed in the structure validator rather than the model — advance/claim/resolve build every key themselves, so a violation only arrives by hand-edit or bad merge, and refusing it in parse_run_state would make a damaged cursor unreadable by the very commands needed to repair it.

<!-- fr:journal kind=finding scope=plan id=p1-preexisting-install-bridge-resolved created=2026-09-20T14:03:00 phase=1 state=refuted resolves=p1-preexisting-install-bridge -->
### p1-preexisting-install-bridge-resolved · finding [refuted] · resolves p1-preexisting-install-bridge: Pre-existing, environment-caused test_install_bridge failure (unrelated to this phase) (phase 1)

The OBSERVATION is correct and independently verified: I ran tests/integration/test_install_bridge.py::test_install_bridge_flag_writes_wrapper on the host at this phase's HEAD and it passes, so the devcontainer failure is an environment artifact and not a regression. What is wrong is the state it was filed under. It was recorded state=fixed, and nothing was fixed — the PR body derives its findings-and-fixes section from this journal, so a finding claiming a fix that never happened is precisely the 'reports success while doing nothing' defect this repo keeps naming. Resolved refuted rather than fixed: as a code finding it does not stand, and the environment observation is preserved here and in the two prior plan journals it cites.

<!-- fr:journal kind=discovery scope=plan id=x-workflow-check-env created=2026-09-20T14:07:55 phase=1 -->
### x-workflow-check-env · discovery · test_cli_all_fails_when_nothing_is_discoverable is pre-existing and host-dependent — NOT fixed here (phase 1)

Full suite at phase 1: 3313 passed, 80 skipped, 1 failed — tests/unit/test_workflow_check.py::test_cli_all_fails_when_nothing_is_discoverable. It asserts `fr workflow check --all` exits 1 when no manifest is discoverable, and gets `fr-goal: ok`: the test's empty_shipped fixture does not suppress the marketplace-clone fallback, so on a machine with super-fr installed the real shipped fr-goal.yaml is still found. VERIFIED pre-existing rather than assumed: the identical failure reproduces on the feat/bounded-executor-handoff worktree, which does not contain this phase's diff. It also cannot be caused by it — this phase touched fr/run/model.py and fr/artifacts/*, none of which is on fr workflow check's path. Recorded as a discovery, NOT a finding: it is a real defect in the repo's test isolation but out of scope for this PR, and filing it as a finding would either block the journal gate or invite the false 'fixed' this phase already produced once (see p1-preexisting-install-bridge). The PR body should say plainly that it is unfixed.

<!-- fr:journal kind=finding scope=plan id=f3 created=2026-09-20T14:07:56 phase=1 state=fixed -->
### f3 · finding [fixed] · Piping a backgrounded suite through `tail` masks pytest's exit code — the notification said 0 on a red run (phase 1)

I ran the full suite as `uv run pytest -q --basetemp=... 2>&1 | tail -20` in the background. The completion notification reported 'exit code 0' while the output itself ended '1 failed, 3313 passed'. A shell pipeline's status is the LAST command's, so tail's success masked pytest's failure — and the same pipe is why the output file stayed zero bytes until the process exited, since tail cannot emit until its input closes. This matters beyond one command: plan step P6.T3.S3 instructs a future phase to background the full gate and paste its tails, and an executor that follows that literally would report a green gate over a red suite — the 'reports success while doing nothing' defect in its purest form. FIXED in the plan: P1.T3.S2 and P6.T3.S3 now say to capture the exit code explicitly (write the raw output to a file, tail the FILE, and echo ${PIPESTATUS[0]} or avoid the pipe), and spec section 4.E's executor clause says the same, so the shipped guidance carries it rather than just this journal.

<!-- fr:journal kind=finding scope=plan id=f3-resolved created=2026-09-20T14:08:46 phase=1 state=fixed resolves=f3 -->
### f3-resolved · finding [fixed] · resolves f3: Piping a backgrounded suite through `tail` masks pytest's exit code — the notification said 0 on a red run (phase 1)

Exactly what changed, since the entry named one file it should not have. Changed: spec section 4.E's executor clause gained a paragraph ('And read the right exit code') covering both the masked status and the empty-until-exit output file; plan steps P4.T3.S3 and P6.T3.S3 — the two forward-looking steps that tell a later phase to background the gate and paste tails — now say to redirect to a file, tail the FILE, and report PIPESTATUS[0] or the unpiped code. NOT changed: P1.T3.S2, which the original entry also named. That step is already executed and ticked; rewriting the text of a completed step would edit the record of what was actually done, which is the opposite of what a journal is for. The guidance it needed is carried by the spec clause that ships.

<!-- fr:journal kind=discovery scope=plan id=p2-model-from-phase-unresolved created=2026-09-20T14:26:11 phase=2 -->
### p2-model-from-phase-unresolved · discovery · advance opens dispatch records; model resolves via fr.models but 'from_phase' itself is not yet a real tier (phase 2)

Implemented per spec §4.B.1: `_open_dispatch` (new helper in run_cmd.py) appends a
DispatchRecord exactly when `advance` moves a unit to `running` — the flat `kind:
agent` branch and `_advance_group`'s write-claim both call it; `_gate_pending` does
not. `model` is resolved via `fr.models.resolve(harness, tier, repo_cfg, user_cfg)`
with `harness = fr.harness.detect.detect_harness(os.environ)`; an undetectable
harness or an unbound tier both leave `model: None` rather than guessing (spec §4.A).

Caveat for phase 5/6 (status rendering / harness-neutral acceptance) and anyone
reading a real run's cursor: the shipped `fr-goal.yaml`'s `implement`/
`implement-phase` steps carry `tier: from_phase`, a LITERAL string, not yet
resolved to a real per-phase tier anywhere in `fr run` — `_build_member_brief`'s
`tier` field already surfaces it unresolved, and this phase's `_open_dispatch`
deliberately mirrors that exact behaviour (P2.T1.S2 scoped it to reusing
`_build_member_brief`'s existing fallback, nothing more). So on a real /fr-goal
run today, `implement`/`implement-phase` dispatch records will carry `model: null`
unless an operator's models.yaml happens to bind a tier literally named
`from_phase` — expected, not a bug in this phase, but worth knowing before anyone
reads a live run's dispatch records and expects a concrete model name there. Real
per-phase tier resolution (PhaseHeader.tier feeding `from_phase`) is out of this
spec's scope (see AGENTS.md's note that `FR_GOAL_PHASE_DISPATCH` is "not yet
resolved from a real manifest end to end").

Also: `fr plan edit --complete-phase 2` warned that acceptance row
run-dispatch-holder-recorded is still not-implemented. Expected and left as-is,
matching phase 1's precedent (same warning, same row, completion note left blank)
— the row is shared across phases 1/2/5/6, and P6.T2's own no-refactor-because
note already says the matrix status flips happen there via `fr acceptance
set-status`, not per-phase.

<!-- fr:journal kind=finding scope=plan id=f4 created=2026-09-20T14:31:33 phase=2 state=fixed -->
### f4 · finding [fixed] · tier: from_phase is a sentinel, not a tier — every real fr-goal dispatch recorded model: null (phase 2)

The shipped fr-goal shape carries tier: from_phase on both implement and implement-phase. Step.tier is a free str precisely so a shape can say that; PhaseHeader.tier's vocabulary is mechanical|standard|hard. So _resolved_model handed 'from_phase' to fr models resolve, which can only ever miss — meaning the model field, one of #503's five stated motivations (cost attribution, #464), would have been null on every dispatch that actually goes to a subagent. The one place it matters. FIXED: PHASE_TIER_SENTINEL is named once; _phase_header_tier reads the plan phase's own tier the same way _accounting_snapshot already reads the plan, degrading to None on anything unreadable rather than failing a dispatch; _dispatch_tier resolves the sentinel at the grouped call site, where phase_n is in scope. _resolved_model ALSO refuses the sentinel defensively, because a flat step has no phase to resolve against and a models.yaml carrying a from_phase: key would otherwise bind it by coincidence. The BRIEF still emits from_phase verbatim and a test asserts it: there the sentinel is an instruction to the harness to look the phase up, which is a different job from recording what was sent.

<!-- fr:journal kind=finding scope=plan id=f5 created=2026-09-20T14:31:33 phase=2 state=fixed -->
### f5 · finding [fixed] · The model assertion passed by binding a models.yaml key literally named from_phase (phase 2)

test_advance_grouped_member_opens_a_dispatch_record wrote 'claude-code:\n  from_phase: claude-opus-5' and asserted model == 'claude-opus-5'. Its own docstring said 'here both are from_phase, the shipped fr-goal shape's literal tier name' — so the gap in f4 was seen and worked around rather than surfaced. No operator would ever write that key: fr models set only accepts the real tiers. A green test over behaviour that does nothing real is the defect class this repo names most often. FIXED: the test now binds a REAL tier and reaches it through the sentinel and the phase header, so it fails if the resolution regresses; two new tests cover the sentinel resolving and an unresolvable sentinel leaving model absent. The _started_grouped_with_plan fixture gained an optional phase_tier so a plan phase header can carry a tier at all.

<!-- fr:journal kind=discovery scope=plan id=p3-abandon-needs-reopen-fix created=2026-09-20T14:54:11 phase=3 -->
### p3-abandon-needs-reopen-fix · discovery · abandon requires advance's reopen guard to key off the dispatch record, not items/state (phase 3)

Spec §4.C's `--abandoned` leaves `items[key]`/step `state` at `running` on purpose (only the
dispatch closes, not the step) — but `_advance_group`'s and the flat branch's existing
"do not reopen a dispatch while nothing changed" guard compared `record.state`/`record.items`
before vs after, which stay byte-identical across an abandon. So a plain `advance` right after
`claim --abandoned` reprinted the same brief (that part already worked, unconditionally) but
never appended the second `DispatchRecord` the plan's P3.T2.S1(c) test requires — the forensic
trail would have silently stopped at the abandoned entry.

Added `_dispatch_needs_open(record, key)`: True when `key` has no dispatch attempts yet, or its
last attempt is CLOSED (`returned is not None`); False while the last attempt is OPEN (the
genuine idempotent-while-running case, unchanged). Both `_advance_group` and `advance_cmd`'s
flat `kind: agent` branch now gate `_open_dispatch` on this instead of solely on the
items/state diff. Phase 4's own "does NOT refuse when the last record is closed" case
(P4.T1.S1(e), a failed unit retried) is the same predicate — `_dispatch_needs_open` is written
so phase 4 can reuse it rather than re-deriving "is the last record for this key closed" a
second time.

<!-- fr:journal kind=finding scope=plan id=x-run-workspace-marker-wrap created=2026-09-20T14:55:06 phase=3 state=open -->
### x-run-workspace-marker-wrap · finding [open] · test_run_workspace.py: two marker-refusal tests fail on this host — rich line-wrapping, not this phase (phase 3)

Full-suite run (uv run pytest -q --no-cov, backgrounded + bounded-polled) surfaced 3 failures,
not the 1 already journalled as x-workflow-check-env:

- tests/unit/test_run_workspace.py::test_a_forged_worktree_marker_in_a_plain_directory_is_refused
- tests/unit/test_run_workspace.py::test_an_external_marker_without_container_evidence_is_refused
- tests/unit/test_workflow_check.py::test_cli_all_fails_when_nothing_is_discoverable (the known one)

Verified pre-existing and unrelated to this phase: `git stash` (removing every change phase 3
made) and re-running just the two new failures reproduces them identically on aeb4e14 (the
phase-2 commit this phase started from). Root cause looks environment-dependent: the refusal
message wraps at this host's terminal width, e.g. "...is not a linked git \nworktree..." —
the assertion checks for the substring "linked git worktree" (with a space), which a
newline-broken wrap defeats. Not chased further per the dispatch brief's "known pre-existing
failure, do not chase it" instruction, which named only x-workflow-check-env; recording this
one too so phase 4+ (or whichever phase next runs the full suite) doesn't mistake it for a
regression it introduced.

<!-- fr:journal kind=discovery scope=plan id=p3-acceptance-row-deferred created=2026-09-20T14:55:15 phase=3 -->
### p3-acceptance-row-deferred · discovery · run-dispatch-abandon left not-implemented at phase completion, matching phases 1/2 precedent (phase 3)

`fr plan edit --complete-phase 3` warned that acceptance row `run-dispatch-abandon` is still
not-implemented. Left as-is, same precedent phase 2's journal already recorded for
`run-dispatch-holder-recorded`: the status flip is `fr acceptance set-status` work, done in
phase 6 per that phase's own no-refactor-because notes, not per-phase.

<!-- fr:journal kind=finding scope=plan id=f6 created=2026-09-20T15:03:55 phase=3 state=fixed -->
### f6 · finding [fixed] · fr plan create silently dropped every phase tier — the upstream reason model is null (phase 3)

Found by dogfooding: this run's own live dispatch records carried no model even after f4 fixed the from_phase sentinel. detect_harness returns claude-code correctly and models.yaml binds the tiers, so the resolution chain was sound — but the plan's phase headers had no tier at all. Root cause: PhaseSpec (fr/plan_ops.py) has fields for number/title/tag/depends_on/tasks/acceptance/skeleton and NO tier, and plan_cmd builds PhaseSpec(...) from the phases file without reading p['tier']. So fr plan create --phases-file accepts a tier: key and discards it, and the documented --phases-file shape never mentioned tier (nor acceptance). Every plan scaffolded this way is untiered, which makes fr-goal section 5's 'Model = phase tier via fr models resolve' unsatisfiable and fr-plan's own claim that it 'tags each phase a tier' false. This is two layers deep: f4 fixed the sentinel, this fixes the source the sentinel points at — model could not have been non-null without BOTH. FIXED: PhaseSpec.tier, emitted only when set (the acceptance/skeleton byte-stability rule), validated at create time against phase_tiers() so an unknown tier is refused rather than scaffolding a plan fr.parser cannot read back; plan_cmd passes p.get('tier'); the docstring's shape now lists tier AND acceptance. Four tests. This plan's own six phases had their intended tiers restored.

<!-- fr:journal kind=discovery scope=plan id=x-claim-live created=2026-09-20T15:03:55 phase=3 -->
### x-claim-live · discovery · fr run claim verified live against this run's own cursor (phase 3)

Not a fixture: claimed the real open dispatch for phase/3/implement-phase on run 2026-09-20-feat-phase-holder-identity with the actual executor agent id. Results, exit codes read WITHOUT a masking pipe: same-agent re-claim rc=0 (idempotent); different agent while open rc=2, message naming both ids and pointing at resolve or --abandoned; unknown phase item rc=2; --agent combined with --abandoned rc=2. The resulting record carries dispatched, agent, agent_type=super-fr:fr-phase-executor, harness=claude-code (auto-detected, not passed) and model=claude-sonnet-5. That is fr answering 'who is holding this phase' on a real run, which is the whole of #503's ask and the evidence the run-dispatch-holder-recorded acceptance row wants.

<!-- fr:journal kind=finding scope=plan id=x-run-workspace-marker-wrap-resolved created=2026-09-20T15:03:56 phase=3 state=fixed resolves=x-run-workspace-marker-wrap -->
### x-run-workspace-marker-wrap-resolved · finding [fixed] · resolves x-run-workspace-marker-wrap: test_run_workspace.py: two marker-refusal tests fail on this host — rich line-wrapping, not this phase (phase 3)

Fixed rather than waived, because it would have tripped every remaining phase executor: they run under fr isolation exec where the failure reproduces, and it does NOT reproduce on the host, so each would have had to re-diagnose it. Root cause is rich soft-wrapping a refusal mid-phrase, so 'not a linked git worktree' in result.output is an assertion about terminal width. Already root-caused once — the comment above test_harness_matrix.py's parity-table tests names these exact two tests and says they 'pass only because Linux CI's tmp paths are short' — and fixed only there. Applied this repo's existing idiom (' '.join(output.split()), as in test_v2_pickup.py and test_plan_acceptance_links.py) to all four substring assertions in test_run_workspace.py, not just the two that happened to fail: a fourth one broke at COLUMNS=60 while I was verifying. Added a width-parametrized regression guard in the same shape test_harness_matrix.py uses. Verified green at COLUMNS 40/60/80/100/120/200/400.
