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
