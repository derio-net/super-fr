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
