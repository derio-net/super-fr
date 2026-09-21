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

<!-- fr:journal kind=finding scope=plan id=f7 created=2026-09-20T15:31:34 phase=4 state=fixed -->
### f7 · finding [fixed] · _complete_step silently deleted a step every dispatch record the moment it finished (phase 4)

Found by a phase-4 test written for the wrong reason (test_completing_a_step_does_not_erase_its_dispatch_history) and red on arrival. _complete_step does NOT model_copy the prior StepRecord — it constructs a fresh one and carries selected fields across by hand (gate, answered_by, items, members). `dispatch` was not in that list, so the entire map was dropped at completion.

Blast radius is larger than it looks, because a GROUPED step holds every phase unit in ONE record: the instant the last member resolved, `implement.dispatch` went from {phase/1/code: [...], phase/1/peer-review: [...], ...} to None. That is the whole run forensic trail — exactly what gh-503 asked to be able to read afterwards — deleted by the act of finishing, with nothing to report it, since the map is only ever READ by status/check and they would simply have found nothing there.

Phases 1-3 could not have caught this: their tests all assert on a dispatch map while the step is still running. Not a regression introduced by phase 4 — it has been true since phase 2 opened the first record.

FIXED: `dispatch=dict(prior.dispatch) if prior is not None and prior.dispatch else None` alongside items/members, with a comment naming the grouped blast radius. Pinned by a test that resolves BOTH members of a one-phase group and asserts the completed group still carries both keys with outcome done.

Note for whoever adds a field to StepRecord next: this constructor is a carry-forward-by-hand list, so a new durable field is dropped on completion BY DEFAULT. Phase 5 renders the holder from exactly this map — on a completed step it would have rendered nothing.

<!-- fr:journal kind=discovery scope=plan id=p4-refusal-wording created=2026-09-20T15:32:13 phase=4 -->
### p4-refusal-wording · discovery · The refusal wording: what phase 4 took from gh-499 and what it kept from the spec (phase 4)

P4.T1.S3 asked to compare the message against gh-499 own "Expected" block and match its shape where it is better. One thing was adopted, three were deliberately not.

ADOPTED — "anyway". gh-499 wrote "Re-brief anyway with:"; the spec wrote "Re-brief:". The adverb is the whole difference between a menu item and a warning, and re-briefing over a live holder is precisely the act that must not read as the obvious next step. The line is now "Re-brief anyway: fr run advance <run> --redispatch".

KEPT — "ALREADY HELD" over gh-499 "ALREADY RUNNING". RUNNING is already the value of items[key] and of StepRecord.state, and the point of this whole feature is that the DISPATCH RECORD, not items, answers "is somebody holding this". A message using the items vocabulary would have pointed the reader at the wrong field.

KEPT — the two-line holder block ("by agent <id> (<agent_type>, <harness>)" / "dispatched <ts> — not yet returned.") over gh-499 inline "(dispatched <ts>)". gh-499 could not ask for the holder id because in 4.5.2 nothing recorded one; now it does, and "not yet returned" names the exact predicate the refusal fired on.

KEPT — the column-aligned three-label block (Resolve it / Lost agent / Re-brief anyway). gh-499 had two escapes; the spec has three, and the middle one (claim --abandoned) is the one an operator with a genuinely lost agent needs and would not guess.

One wording constraint worth knowing if this message is ever edited: it must not contain the substring "dispatch brief", and (for the flat path) not "--item". Both are asserted, because the test for "prints NO brief" is an absence test and absences rot silently.

<!-- fr:journal kind=discovery scope=plan id=p4-pinned-the-bug created=2026-09-20T15:32:23 phase=4 -->
### p4-pinned-the-bug · discovery · A pre-existing test PINNED the gh-499 bug — rewritten, not deleted (phase 4)

tests/unit/test_run_cli.py::test_advance_agent_step_brief_is_re_emitted_idempotently_while_running asserted exit_code == 0 on a second advance over a running agent step. That is gh-499 verbatim, written down as an expectation and guarded by CI since phase 7 of the run-cursor work. Any fix to gh-499 was going to turn it red, and the tempting move — delete it — would have thrown away the two things it was ACTUALLY protecting, neither of which changed: advance still executes nothing for an agent step (the _boom monkeypatch, the structural half of no-claude-p-batch), and the step is still left running.

Rewritten as test_advance_onto_a_still_held_agent_step_refuses_and_still_executes_nothing: same fixture, same _boom, exit 2, plus a new assertion that the whole RunState is identical before and after (a refusal writes nothing). Its docstring says outright that it used to pin the bug, so a future reader does not read the rename as churn.

Two adjacent tests were in the same position and got the same treatment: test_advance_{,grouped_member_}does_not_reopen_a_dispatch_record_while_still_running kept their assertions (still only one record) but now also assert exit 2 — without that they would pass just as well if advance had silently done nothing at all. And test_advance_is_idempotent_over_the_snapshot was switched to --redispatch, because a bare second advance now refuses before the snapshot code is reached, which would have left it green for a reason unrelated to what it claims to test.

General lesson for phases 5-6: grep the suite for tests that assert the CURRENT behaviour of the thing you are changing before assuming a red is your own.

<!-- fr:journal kind=discovery scope=plan id=p4-redispatch-green-on-arrival created=2026-09-20T15:32:36 phase=4 -->
### p4-redispatch-green-on-arrival · discovery · P4.T2 tests passed on arrival; two mutants used instead of a faked red (phase 4)

Honest record of a TDD deviation. --redispatch was already wired during P4.T1.S2, for two reasons that were not avoidable: _refuse_held own message names it (a refusal pointing at a flag that does not exist is a worse artifact than a slightly early implementation), and the abandon-then-append shares _close_dispatch with claim --abandoned from phase 3. So P4.T2.S1 six tests were green the first time they ran.

Rather than revert the wiring to manufacture a red, the tests were shown CAPABLE of failing by two mutants applied to a backed-up copy of run_cmd.py and then restored:

  M1 — "if not redispatch:" -> "if True:" (the flag ignored, both paths): 3 failed / 3 passed. The three survivors are exactly the ones that do not need the flag (the unheld no-op, the after-abandon no-op, the validate_run structural check).
  M2 — _open_dispatch overwrites the attempt list instead of appending: 3 failed / 3 passed. The failures are the forensic-trail assertions (old holder id still present, its abandoned timestamp untouched).

Both mutants killed, source restored from the backup, suite re-run green (165 at that point). This is weaker than a real red for ORDERING discipline but stronger than a red for the thing a red is a proxy for — that the test can distinguish the two worlds.

<!-- fr:journal kind=discovery scope=plan id=x-refusal-live created=2026-09-20T15:32:49 phase=4 -->
### x-refusal-live · discovery · The gh-499 refusal verified live against this run own cursor, writing nothing (phase 4)

Not a fixture. Ran `uv run fr run advance 2026-09-20-feat-phase-holder-identity` against the real cursor in this worktree while phase 4 itself was the held unit. Exit code read unpiped: 2.

  implement: phase/4/implement-phase is ALREADY HELD
    by agent a5b15f633d8225e2c (super-fr:fr-phase-executor, claude-code)
    dispatched 2026-09-20T13:08:53+00:00 — not yet returned.
    Waiting on that agent — do NOT dispatch again.
    Resolve it:      fr run resolve 2026-09-20-feat-phase-holder-identity --step implement-phase --item phase/4 --state done|failed
    Lost agent:      fr run claim 2026-09-20-feat-phase-holder-identity --step implement-phase --item phase/4 --abandoned
    Re-brief anyway: fr run advance 2026-09-20-feat-phase-holder-identity --redispatch

The holder it named is the phase-4 executor that ran the command — the orchestrator claimed the unit before dispatching, so fr correctly reported the tree busy TO its own occupant. That is exactly the double-dispatch gh-499 describes, caught on a real run instead of a grouped fixture.

Critically, the run file sha256 was IDENTICAL before and after (checked explicitly): the refusal writes nothing, so an orchestrator that hits it mid-run has not had its cursor moved, its accounting snapshot refreshed, or a second record appended. The `M` git status on that file predates this command and belongs to the orchestrator own claim — attributed, not assumed.

fr validate artifacts: 33 artifacts, all structurally valid, with the live cursor among them.

<!-- fr:journal kind=discovery scope=plan id=p4-acceptance-row-deferred created=2026-09-20T15:33:20 phase=4 -->
### p4-acceptance-row-deferred · discovery · run-dispatch-refuses-second left not-implemented at phase completion, matching phases 1-3 (phase 4)

fr plan edit --complete-phase 4 warned that acceptance row run-dispatch-refuses-second is still not-implemented. Left as-is, the same precedent phases 1, 2 and 3 already recorded (p3-acceptance-row-deferred, and phase 2 for run-dispatch-holder-recorded): the status flip is fr acceptance set-status work, done in phase 6 per that phase own steps, not per-phase.

The evidence phase 6 will want is in tests/unit/test_run_cli.py, all added here:
  test_advance_refuses_a_held_unit_and_prints_no_brief
  test_the_refusal_names_the_holder_agent_type_harness_and_dispatch_time
  test_the_refusal_says_an_unclaimed_agent_when_nobody_claimed
  test_the_refusal_prints_all_three_ways_forward
  test_advance_does_not_refuse_when_the_last_record_is_closed
  test_a_flat_agent_step_is_refused_the_same_way
  test_advance_onto_a_still_held_agent_step_refuses_and_still_executes_nothing
plus the six --redispatch tests and the thirteen resolve/close tests in the same file.

<!-- fr:journal kind=discovery scope=plan id=x-f7-mutation-verified created=2026-09-20T15:38:52 phase=4 -->
### x-f7-mutation-verified · discovery · f7's fix mutation-verified: the pinning test genuinely catches the deletion (phase 4)

Phase 4's f7 (a grouped step's entire dispatch history deleted by _complete_step) is the most consequential finding of the run, so the fix was checked rather than taken on report. Removed the single carry-forward line from _complete_step: test_completing_a_step_does_not_erase_its_dispatch_history FAILS. Restored it: passes. The test is load-bearing, not decorative. Worth restating the executor's own note, because it generalises beyond this PR: _complete_step builds a fresh StepRecord and carries fields across BY HAND, so any durable field added to StepRecord in future is dropped at completion by default. That is a trap with no compiler or type-checker behind it — extra='forbid' catches unknown keys, not forgotten ones.

<!-- fr:journal kind=discovery scope=plan id=x-refusal-verified-independently created=2026-09-20T15:38:52 phase=4 -->
### x-refusal-verified-independently · discovery · The gh-499 refusal verified independently on this run's live cursor (phase 4)

Re-ran the executor's live check rather than accepting the transcript. fr run advance against a run whose phase/4/implement-phase was genuinely held: exit 2; zero JSON brief lines on stdout (asserted by counting, since gh-499's complaint is precisely that a brief reads as an instruction to act); the holder named with agent id, agent_type and harness plus the dispatch timestamp; three copy-pastable escapes carrying the unit's own --step/--item. The run file's sha256 was byte-identical before and after, so the refusal writes nothing. That is gh-499's 'Expected' block satisfied on a real run, not a fixture.

<!-- fr:journal kind=discovery scope=plan id=x-model-captured-at-dispatch-time created=2026-09-20T15:38:52 phase=4 -->
### x-model-captured-at-dispatch-time · discovery · A mid-run models.yaml change proved model records the binding AT DISPATCH TIME (phase 4)

phase/3/implement-phase recorded model claude-sonnet-5 at 12:35Z; phase/3/review-phase recorded claude-opus-5 at 13:08Z — both resolve tier 'standard'. Investigated as a suspected resolution bug. It is not one: ~/.config/fr/models.yaml was modified at 13:00Z (mtime), rebinding standard from claude-sonnet-5 to claude-opus-5, and no executor ran fr models set (checked every subagent transcript). So the two records disagree because the operator's config changed between them, and each captured what was actually resolved when its dispatch happened. That is the field behaving exactly as intended — a config that changes mid-run does not retroactively rewrite what was dispatched — and it is a better demonstration of why model is recorded per-dispatch rather than derived on read than any test could be.

<!-- fr:journal kind=discovery scope=plan id=x-abandon-live created=2026-09-20T15:38:53 phase=4 -->
### x-abandon-live · discovery · --abandoned live-verified by closing this run's own bootstrap-era open records (phase 4)

Three records on this run's cursor were opened by advance in phases 2-3 and could never be closed by their own resolve, because resolve-closes-the-record is phase 4's P4.T3 and their steps were resolved before it existed: phase/2/review-phase, phase/3/implement-phase, phase/3/review-phase. Left alone they would have made this PR's own artifact permanently claim three held units that nothing holds — the feature contradicted by its own dogfooding. Closed each with fr run claim --abandoned (rc=0 each); fr validate artifacts still reports all 33 structurally valid, including the at-most-one-open and open-is-last invariants. abandoned is the honest outcome here: not 'it failed', but 'no resolve will ever close this', which is exactly what section 1.C defines it for. Live evidence for the run-dispatch-abandon acceptance row. Unrelated but worth recording: the first attempt reported rc=2 three times because of a zsh/bash difference, not the feature — zsh does not word-split an unquoted parameter, so  passed one joined argument.

<!-- fr:journal kind=discovery scope=plan id=x-f7-label-collision created=2026-09-20T15:38:53 phase=4 -->
### x-f7-label-collision · discovery · Commit 3ac2b88's message calls the width fix 'f7'; the journal's f7 is a different finding (phase 4)

The phase-3 review commit message labels the test_run_workspace width fragility 'f7'. No journal entry with that id was ever created for it — it is recorded as the resolution record on x-run-workspace-marker-wrap. Phase 4 then legitimately created finding f7 for the _complete_step deletion. So the two do not collide in the journal (which fr journal check reads), only in one pushed commit message. Not rewriting a pushed commit over a label; recording it here so the PR body, which derives findings from the journal, names f7 as the _complete_step bug and does not inherit the mislabel.

<!-- fr:journal kind=discovery scope=plan id=p5-acceptance-row-deferred created=2026-09-20T15:56:18 phase=5 -->
### p5-acceptance-row-deferred · discovery · p5-acceptance-row-deferred: run-dispatch-holder-recorded left not-implemented at phase completion (phase 5)

fr plan edit --complete-phase 5 warned that acceptance row run-dispatch-holder-recorded
is still not-implemented. Left as-is, matching the precedent phases 1-4 already recorded
(p1/p2/p3/p4-acceptance-row-deferred): the status flip is fr acceptance set-status work,
done in phase 6 per that phase's own steps, not per-phase.

Evidence phase 6 will want, all in tests/unit/test_run_cli.py:
  test_status_renders_held_by_and_the_claimed_identity
  test_status_renders_an_unclaimed_open_dispatch
  test_status_renders_a_settled_dispatch
  test_status_renders_held_by_the_orchestrator
  test_status_shows_every_record_of_a_unit_oldest_first
  test_status_output_is_byte_identical_for_a_run_with_no_dispatch_data
  test_check_reports_an_open_dispatch_with_its_claimed_holder
  test_check_counts_an_unclaimed_open_dispatch_as_debt_not_a_failure
  test_check_does_not_count_a_closed_dispatch_as_open_or_unclaimed
  test_check_reports_an_orchestrator_open_dispatch_without_counting_it_unclaimed

Plus a live before/after fr run status and fr run check against this run's own cursor
(2026-09-20-feat-phase-holder-identity), recorded in x-p5-status-check-live.

<!-- fr:journal kind=discovery scope=plan id=x-p5-status-check-live created=2026-09-20T15:56:35 phase=5 -->
### x-p5-status-check-live · discovery · x-p5-status-check-live: fr run status/fr run check verified live against this run's own cursor (phase 5)

Ran both commands against 2026-09-20-feat-phase-holder-identity's real cursor before and
after phase 5's change (before captured by git-stashing only run_cmd.py, exit 0 both times).

BEFORE (dispatch map present on disk, but status/check couldn't render it yet):
  implement: running
    phase/2/review-phase: done
    phase/3/implement-phase: done
    ...
  (no holder lines at all — the whole point of the phase)

AFTER:
  phase/2/review-phase: done
      the orchestrator 2026-09-20T12:35:32+00:00 -> 2026-09-20T13:38:19+00:00 abandoned
  phase/3/implement-phase: done
      agent a5dbd5f0e9bdf3362 (claude-code, claude-sonnet-5) 2026-09-20T12:35:34+00:00 -> 2026-09-20T13:38:19+00:00 abandoned
  phase/3/review-phase: done
      the orchestrator (claude-opus-5) 2026-09-20T13:08:36+00:00 -> 2026-09-20T13:38:19+00:00 abandoned
  phase/4/implement-phase: done
      agent a5b15f633d8225e2c (claude-code, claude-opus-5) 2026-09-20T13:08:53+00:00 -> 2026-09-20T13:36:11+00:00 done
  phase/4/review-phase: done
      the orchestrator (claude-opus-5) 2026-09-20T13:39:21+00:00 -> 2026-09-20T13:39:21+00:00 done
  phase/5/implement-phase: running
      HELD BY agent a182c94fe152e508c (claude-code, claude-sonnet-5) since 2026-09-20T13:39:22+00:00

`fr run check` on the same run: exit 0, one line — "implement: phase/5/implement-phase is
open — HELD BY agent a182c94fe152e508c (claude-code, claude-sonnet-5) since ..." — and no
"unclaimed dispatch" line, because phase/5's own record was claimed. `fr validate artifacts`:
33 artifacts, all structurally valid, including this live cursor.

Confirms two design decisions made in this phase, not literally spelled out in spec §4.C's
illustration:
  - agent_type: None (an orchestrator-run kind:agent member, e.g. review-phase) renders
    "the orchestrator" as the WHO, in both the held and settled line shapes — not just the
    open case the spec's own prose describes. `phase/3/review-phase` and `phase/4/review-phase`
    are the live evidence this reads sensibly for a CLOSED record too.
  - `fr run check`'s unclaimed count deliberately EXCLUDES agent_type is None records: an
    orchestrator-run step never reports an `agent` for itself, so counting it would make
    every ordinary fr-goal run report permanent "unclaimed" debt on spec-review/review-phase/
    deliver. Pinned by test_check_reports_an_orchestrator_open_dispatch_without_counting_it_unclaimed.

<!-- fr:journal kind=finding scope=plan id=f8 created=2026-09-20T16:01:26 phase=5 state=fixed -->
### f8 · finding [fixed] · advance detected the harness to resolve the model, then threw it away (phase 5)

Seen in the live status output phase 5 produced: 'the orchestrator (claude-opus-5)' — a model with no harness beside it. _resolved_model called detect_harness(os.environ) privately to pick the binding and discarded the result, so a record could carry model=claude-opus-5 with harness=null while fr knew at that exact moment which harness chose it. A tier does not resolve to a model in the abstract; it resolves for a harness, so the two belong to the same record. Worse for an orchestrator-run step (agent_type None): nothing ever claims one, so nothing would fill the harness in later — permanently half-described. FIXED: _open_dispatch detects once, records it, and PASSES it to _resolved_model, which no longer detects anything itself; the recorded harness is therefore by construction the one that chose the recorded model. Two tests. Two existing tests needed their fixtures corrected rather than their assertions weakened: both had been pinning the absence this fixes, and both ran advance on the ambient environment — which in this process is a Claude Code session, so they were asserting against whatever the machine happened to be. They now declare their harness explicitly (one undetectable, one pinned via FR_HARNESS), which is what they always meant.

<!-- fr:journal kind=finding scope=plan id=f9 created=2026-09-20T16:16:16 phase=6 state=fixed -->
### f9 · finding [fixed] · The explainer's SKILL.md line references went stale the moment §5 was rewritten (phase 6)

docs/explainers/01-fr-goal.md cites fr-goal/SKILL.md by LINE RANGE in six places. Rewriting §5 to add the claim loop shrank it by three lines (the 120-line skill cap forced repacking rather than appending), so every reference below it pointed three lines high: ':81-95' for the implement loop landed mid-clause, ':97-102' straddled the §6/§7 boundary, ':104-114' and ':116-120' likewise. Nothing checks these — test_tripwire_explainers_fresh.py compares the rendered page against its own source's headings, not the source's claims about another file. FIXED by re-deriving all four against the new heading boundaries and switching them to whole-section ranges (:78-91 implement, :92-97 review-phase, :99-111 deliver, :113-117 close-out), which survive a body edit that does not move a heading. Worth knowing for the next skill edit: a published page can be made wrong by a diff that never touches it.

<!-- fr:journal kind=discovery scope=plan id=x-explainer-render-verified created=2026-09-20T16:16:27 phase=6 -->
### x-explainer-render-verified · discovery · x-explainer-render-verified: the unmodified re-render came back byte-identical before anything was written (phase 6)

Per .claude/rules/explainers-currency.md, the renderer was verified BEFORE the real render: rendered the UNMODIFIED docs/explainers/01-fr-goal.md from / (not the worktree) with 'uv run --isolated --no-project --with markdown --with pyyaml python $B/tools/render_explainer.py ... --style broadsheet --embed-fonts' to a scratch file, and 'cmp' against the committed 01-fr-goal.html reported no difference — byte-identical, exit 0. Both load-bearing flags held on this host: from / and --isolated. The real render afterwards produced a 62-line HTML diff consisting only of the paragraphs actually written (the 'Six commands' rewrite, the new 'Who is holding this phase right now?' section, the implement-loop paragraph) — no codehilite explosion, no reflowed code blocks. That is what the verification buys: the page diff is exactly the prose diff.

<!-- fr:journal kind=discovery scope=plan id=x-p6-audience-audit created=2026-09-20T16:16:44 phase=6 -->
### x-p6-audience-audit · discovery · x-p6-audience-audit: P6.T1.S3's re-read, and the one asymmetry it confirmed is correct (phase 6)

Re-read both files as each audience, per the gh-420 root cause (a constraint living only where the wrong reader looks).

ORCHESTRATOR reads the agent's 'description:' frontmatter. It already carries the one thing an orchestrator must not get wrong - dispatch WITHOUT isolation: 'worktree', with the reason - and nothing phase 6 added belongs there: the long-command/poll-loop clause is executor behaviour the orchestrator cannot control.

EXECUTOR reads the body. It now carries the §4.E clause next to 'What you return', where it belongs: both failures are about the handback (one leaves you non-terminal, the other reports a green gate over a red suite).

The asymmetry worth stating: NOTHING in the executor definition mentions 'fr run claim', and that is correct, not an omission. An executor cannot claim its own dispatch - it does not know its own harness-assigned id; only the orchestrator that dispatched it ever sees that. So the claim lives entirely in fr-goal §5, and the recovery moves (claim --abandoned, advance --redispatch) live there too, beside the 'executor lost' case that is the only time an orchestrator needs them. A reader of either file gets the whole of its own job.

Cross-check performed both ways: every body constraint the orchestrator must act on is dual-sited (#461's return-not-message is in §5's dispatch clause; 'never open a PR' is in §6/§7), and every §5 duty the executor must honour is in its own body.

<!-- fr:journal kind=discovery scope=plan id=x-p6-cited-test-names created=2026-09-20T16:16:59 phase=6 -->
### x-p6-cited-test-names · discovery · x-p6-cited-test-names: two test names written into an acceptance note from memory did not exist (phase 6)

The first 'fr acceptance set-status --id run-dispatch-refuses-second' note cited test_advance_refuses_a_held_unit_by_name and test_the_refusal_prints_no_brief. Neither exists: the real ones are test_advance_refuses_a_held_unit_and_prints_no_brief and test_the_refusal_names_the_holder_agent_type_harness_and_dispatch_time. Caught by grepping tests/unit/test_run_cli.py for every name before moving on, and corrected with a second set-status (ci -> ci, allowed, notes rewritten) before anything was committed.

Why it matters beyond a typo: matrix notes are evidence refs a later reader greps for. A row whose notes name a test that does not exist reads exactly like a row whose test was deleted - the acceptance-matrix checks verify the LEVEL paths (files), not the test names inside the prose. So the discipline is: paste test names from a grep, never from recall. The phase-5 handoff (p5-acceptance-row-deferred) did this correctly by listing the names verbatim, which is why the holder-recorded row's note needed no correction.

<!-- fr:journal kind=discovery scope=plan id=x-p6-f6-f8-placement created=2026-09-20T16:17:17 phase=6 -->
### x-p6-f6-f8-placement · discovery · x-p6-f6-f8-placement: where the two user-visible side fixes were folded into the prose (phase 6)

This PR carries two fixes that are user-visible beyond the dispatch record, and phase 6 had to decide where they belong.

f6 (fr plan create --phases-file silently dropped every phase tier): the explainer's implement section now states plainly that 'Each phase carries a difficulty tier, assigned when the plan was written, and that tier is what chooses the model the phase is implemented with.' That sentence was FALSE for --phases-file plans before f6 - the tier existed in the plan prose and never reached dispatch, so every record showed model: null. Stating the behaviour rather than narrating the bug is the right register for a published explainer; the bug itself is in the journal and the PR body.

f8 (advance detected the harness to resolve the model, then discarded it): surfaced in both fr-goal §5 ('harness beside model: a tier resolves FOR a harness, never in the abstract') and, at length, in the explainer's new section ('A tier does not resolve to a model in the abstract; it resolves for a particular harness, so the two are kept in the same record'). It is also now in the parity row's summary, which names agent type, model AND the harness that resolved it as what advance records.

Neither got its own explainer section: both are properties of the dispatch record the new section already introduces, and a second section would have split one idea in two.

<!-- fr:journal kind=finding scope=plan id=f10 created=2026-09-20T16:19:47 phase=6 state=fixed -->
### f10 · finding [fixed] · Phase 6's mirror step named only sync-opencode.py — the HERMES mirror drifted and the full suite caught it (phase 6)

P6.T2.S2 says 'run scripts/sync-opencode.py and commit the regenerated .opencode/ mirrors', and the tripwires it names are the opencode ones ('-k "opencode and sync"'). All of that passed. But super-fr mirrors canonical skills to TWO harnesses: scripts/sync-hermes.py writes .hermes/skills/fr/<name>/SKILL.md and .hermes/SOUL.d/super-fr-rules.md, guarded by tests/unit/test_tripwire_hermes_skills_sync.py::test_mirror_has_no_drift. Editing plugins/super-fr/skills/fr-goal/SKILL.md therefore drifted the Hermes mirror too, and the targeted tripwire run could not see it - only the FULL suite did, which is exactly why the phase's last step runs the whole thing.

FIXED: ran 'uv run python scripts/sync-hermes.py' (no flag writes), which regenerated .hermes/skills/fr/fr-goal/SKILL.md, then '--check' (in sync) and the tripwire (green).

The general shape, worth carrying: a step that names ONE generator by name is a step that will be followed literally. Anyone editing a canonical skill/rule in this repo runs BOTH sync scripts - AGENTS.md's 'Skills/rules: canonical source vs. generated mirrors' section documents the opencode half in detail and the hermes half only by implication.

<!-- fr:journal kind=discovery scope=plan id=x-p6-notification-said-zero created=2026-09-20T16:19:59 phase=6 -->
### x-p6-notification-said-zero · discovery · x-p6-notification-said-zero: the harness's own completion notice reported exit 0 for a suite that exited 1 (phase 6)

Phase 6 ran the full gate backgrounded as 'uv run pytest -q > file 2>&1; echo $? > file.rc'. The harness's task-completion notification read 'Background command "Run full test suite in background" completed (exit code 0)' - the exit status of the compound command (the trailing 'echo'), not of pytest. The .rc file said 1, and the suite had two failures (the hermes mirror drift of f10, plus the known-preexisting x-workflow-check-env).

This is finding f3 recurring in a different disguise: f3 was 'pytest | tail exits with tail's status'; this is 'anything appended after pytest owns the exit code the harness reports'. The defence is identical and is the only one that works: write the raw status to a file and read the FILE. Had the notification been trusted, phase 6 would have committed a red tree and reported it green - which is precisely the failure class this plan's own executor clause (now in plugins/super-fr/agents/fr-phase-executor.md) warns about.

<!-- fr:journal kind=discovery scope=plan id=p6-harness-neutral-deferred created=2026-09-20T16:23:41 phase=6 -->
### p6-harness-neutral-deferred · discovery · p6-harness-neutral-deferred: run-dispatch-harness-neutral stays not-implemented, on purpose, and its notes say so (phase 6)

fr plan edit --complete-phase 6 warned that acceptance row run-dispatch-harness-neutral is still not-implemented. Unlike phases 1-5's deferrals (which were 'phase 6 will flip it'), this one is final for this PR and the warning is expected.

The row claims the dispatch record is written IDENTICALLY on Claude Code and OpenCode, each recording its own harness and agent id. No unit test can show that: a fixture asserting it would only assert that fr writes what fr writes, and the harness half comes from detect_harness reading a real environment. It closes with post-merge Test Plan items 13 and 14 - a real /fr-goal run on each harness, transcripts in the PR.

The other three rows moved not-implemented -> ci in this phase via fr acceptance set-status (run-dispatch-holder-recorded, run-dispatch-refuses-second, run-dispatch-abandon). This one's --notes were rewritten in place (not-implemented -> not-implemented) to record the deliberate decision rather than leaving it looking like an oversight - which is the whole point of the acceptance-matrix rule's 'statuses move explicitly, never silently', applied to a status that deliberately did not move.

<!-- fr:journal kind=discovery scope=plan id=x-p6-refs-verified created=2026-09-20T16:27:30 phase=6 -->
### x-p6-refs-verified · discovery · f9's re-derived explainer refs verified against the skill; three pre-existing sloppy ones left alone (phase 6)

Checked f9 rather than accepting it. Diffing the explainer's fr-goal SKILL.md refs against origin/main shows exactly six changed — 104-114 (twice), 116-120, 81-95, 97-102, plus a new 78-91 — which matches the report. The skill's sections moved from 43/56/63/74/78/95/102/116 to 43/56/63/74/78/92/99/113: section 5 got THREE LINES SHORTER while gaining the whole claim loop, which is why everything below it shifted up and why the file is still inside its 120-line cap at 117. Each re-derived range now lands on an exact section boundary: 78-91 is section 5, 92-97 section 6, 99-111 section 7, 113-117 the post-merge close-out. Three other fr-goal refs (49-56, 58-64, 69-74) end one line into the FOLLOWING section — but they are byte-identical to origin/main and every one of them targets lines above 78, which this PR did not move. Pre-existing imprecision, not introduced here, and deliberately not fixed: the rule's own tripwire cannot check line refs at all, so tidying them would be unverifiable churn in a file whose renderer lives in another repo. Worth an issue, not a drive-by.

<!-- fr:journal kind=discovery scope=plan id=x-p6-gates-reverified created=2026-09-20T16:27:30 phase=6 -->
### x-p6-gates-reverified · discovery · Every phase-6 gate re-run independently by the orchestrator (phase 6)

Not taken on report: fr 4.9.0 and bump-version --check agree across all nine manifests; fr acceptance check 128 rows OK (ci 105, skipped 18, not-implemented 5); fr harness parity --check agrees with the registration files; BOTH mirror generators clean (sync-opencode.py --check and sync-hermes.py --check — finding f10 is exactly that there are two, and the plan step named only one); fr validate artifacts 33 artifacts valid; and the four prose tripwires (skill tool-neutrality, skill validation, harness parity, explainers freshness) pass 107/107. The fr-goal skill is 117 lines against its 120 cap, and the executor clause in fr-phase-executor.md carries both halves of spec section 4.E — the 120-second auto-promotion with its 11.5-hour example, and the piped-exit-code trap.

<!-- fr:journal kind=finding scope=plan id=f11 created=2026-09-20T17:28:46 phase=6 state=fixed -->
### f11 · finding [fixed] · Three tests asserted a concrete model while reading the harness from the ambient environment — green locally, red on CI (phase 6)

CI failed on exactly three tests, all 'assert None == claude-opus-5'-shaped: test_advance_grouped_member_opens_a_dispatch_record, test_advance_resolves_the_from_phase_sentinel_against_the_plan_phase_header, test_advance_flat_agent_step_opens_a_dispatch_record_under_the_step_prefix. Reproduced locally first by clearing CLAUDECODE and friends: the same three, nothing else. Cause: a tier resolves to a model only FOR a harness, and _open_dispatch calls detect_harness(os.environ). This process IS a Claude Code session, so detection succeeded ambiently on my machine and returned None on a CI runner, where no harness marker exists. The production behaviour is correct — spec section 4.A says nothing is guessed — so the tests were wrong, not the code. This is MY miss, and specifically a narrow application of something I had already written down: f8's review note said two tests 'ran advance on the ambient environment, which in this process is a Claude Code session, so they were asserting against whatever the machine happened to be'. I fixed the two that broke and did not audit the ones that were passing for the same accidental reason. _invoke_as_harness's own docstring warns about this hazard in as many words; the helper existed and these tests did not use it. FIXED: all three now declare FR_HARNESS=claude-code. Audited every harness-dependent assertion in the file rather than patching the three that failed: four others assert a concrete harness/model but pass those values explicitly to claim/resolve, so they never consult detection. Verified by running the whole file, and then the whole suite, with every CLAUDE* signal stripped.

<!-- fr:journal kind=finding scope=plan id=f12 created=2026-09-20T17:49:25 phase=6 state=fixed -->
### f12 · finding [fixed] · Merging gh#506 made two tests assert against a tier they never chose — a duplicate YAML key (phase 6)

After merging origin/main, two dispatch tests failed with model=None while harness recorded correctly. Cause: gh#506 added tier: standard to the shared plan fixture tests/unit/fixtures/v2_plan_minimal/01.yaml, and my _started_grouped_with_plan helper INSERTED its own tier: line after 'tag: agentic' rather than setting one. The header then carried two tier keys, and PyYAML silently resolves a duplicate to the LAST occurrence — the fixture's standard, not the hard the test asked for. Exactly the hazard .claude/rules/artifact-versioning.md names for matrix.yaml, arriving in a test fixture where no validator looks. FIXED: the helper now strips any existing tier before inserting, so it SETS rather than appends. Two further details mattered: phase_tier=None must keep meaning 'leave the fixture alone', because gh#506's own test_advance_grouped_step_member_brief_resolves_the_phases_tier relies on the fixture's default — my first fix stripped it and broke their test. So stripping is now an explicit strip_tier=True, which my untiered test uses. And that untiered test had been passing for the wrong reason: its comment claimed 'fixture phase header has no tier' while the fixture had one; it only passed because it also forces detect_harness to None, which zeroes model regardless. Green tests hiding a false premise, one more time.

<!-- fr:journal kind=finding scope=plan id=f13 created=2026-09-20T19:12:59 phase=6 state=fixed -->
### f13 · finding [fixed] · Two branches allocated run schema_version 3 in parallel; nothing detected it (phase 6)

Merging origin/main a second time brought gh#514's run_telemetry migration, written as 2 -> 3 for PhaseAccounting's four measured token fields. This branch's run_dispatch_holder was also written as 2 -> 3. Two different 'version 3's of the same artifact kind existed simultaneously on two branches: a cursor written by either was unreadable by the other while both claimed the same stamp. .claude/rules/artifact-versioning.md assumes a kind has one linear history — correctly — but nothing anywhere checks that two branches have not allocated the same number, and neither PR's CI could have caught it because each was internally consistent. FIXED by stacking: run is now current_version=4 and the dispatch-holder migration is 3 -> 4, purely because it merged second. Five tests had to move with it — four mine, asserting 3, and one of gh#514's that hardcoded 'schema_version: 3' in a string replace. That last one is MY change breaking THEIR test, and it is fixed by deriving the stamp from current_version rather than by patching the literal, so the next bump does not repeat this. The chain test now asserts every hop ([2, 3, 4]) rather than just the endpoint, because that assertion is the closest thing to a collision guard this repo has.

<!-- fr:journal kind=discovery scope=plan id=x-abandon-live-corr created=2026-09-20T23:03:06 phase=4 -->
### x-abandon-live-corr · discovery · Correction to x-abandon-live: three words the shell ate (phase 4)

Correction to x-abandon-live: its last sentence lost three words to the shell. It reads "zsh does not word-split an unquoted parameter, so  passed one joined argument" and should read: so `set -- $u` passed one joined argument. The entry was written with a double-quoted --body containing backticks, which zsh treats as command substitution: `set -- $u` actually RAN (harmlessly) and its empty output replaced the words. Found when phase 2 of the unit-record plan hit the same hazard and named it; a scan of every journal this session authored found this one instance. The journal is append-only, so the fix is this entry. Bodies are passed from single-quoted heredoc files from here on.
