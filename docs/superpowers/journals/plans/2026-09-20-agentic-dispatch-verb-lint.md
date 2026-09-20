# Journal: 2026-09-20-agentic-dispatch-verb-lint

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4t3 created=2026-09-20T15:09:48 -->
### no-refactor-p4t3 · discovery · no-refactor-because P4.T3

P4.T3 IS the quality gate — its two steps run the full CI gate as CI runs it (ruff, mypy, pytest with coverage, fr validate artifacts, fr acceptance check, fr harness parity --check, sync-opencode --check, bump-version --check) and then dogfood fr plan self-review on this plan itself. There is no code of its own to refactor: a refactor step here would either be a no-op or would invent work after every gate has already passed. The per-task refactor obligation is discharged inside P4.T1 and P4.T2, whose outputs (matrix rows, version manifests, the regenerated explainer) this task only verifies.

<!-- fr:journal kind=discovery scope=plan id=0bd7cd0adee6 created=2026-09-20T15:12:11 phase=1 -->
### 0bd7cd0adee6 · discovery · The corpus is 44/1444 now, not 43/1419 — the delta is this plan itself (phase 1)

Spec §2.D measured 43 plan folders / 1419 agentic steps during the brainstorm. The harness built in P1.T1 measures 44 parsed / 41 skipped / 1444 agentic steps over the same two roots.

The whole difference is the plan folder for THIS run: docs/superpowers/plans/2026-09-20-agentic-dispatch-verb-lint did not exist when the brainstorm ran, and it contributes exactly 25 agentic steps (1444 - 25 = 1419) and one parsed plan (44 - 1 = 43). plans_skipped is 41 on the nose, matching §2.D's count of unparseable folders (38 frozen fr_version pins + 3 PhaseDoc failures). Entries on disk: 106 vs the spec's 105 — again this plan.

So §2.D's numbers are confirmed, not contradicted, and phase 2's zero-hit assertion will run over a corpus that now includes this run's own dispatch-heavy plan text — which is the harder, better test. The floors stay at 30/1000 as the plan specifies: they are a 'did we read anything at all' tripwire, deliberately well below the true count so a couple of plans archiving or a fixture moving does not make them brittle.

<!-- fr:journal kind=finding scope=plan id=5661437b7bff created=2026-09-20T15:16:09 phase=1 state=open -->
### 5661437b7bff · finding [open] · Three unit tests already fail on this branch's base, before phase 1 touched anything (phase 1)

Running the full 'uv run pytest tests/unit -q --no-cov' during P1.T1.S3 gave 3 failed, 3145 passed, 80 skipped. None of the three is attributable to phase 1:

- tests/unit/test_run_workspace.py::test_a_forged_worktree_marker_in_a_plain_directory_is_refused
- tests/unit/test_run_workspace.py::test_an_external_marker_without_container_evidence_is_refused
- tests/unit/test_workflow_check.py::test_cli_all_fails_when_nothing_is_discoverable

Attribution: 'git log main..HEAD' on feat/plan-self-review-dispatch-verb-lint is three docs-only commits (spec, spec-review, plan); 'git diff --stat main...HEAD -- packages tests' is EMPTY. Phase 1's only code change is the new tests/unit/test_dispatch_lint_corpus.py, which no other module imports. So these fail identically on main.

Shape of the failures: the two test_run_workspace ones assert a substring ('not a linked git worktree', 'container evidence') against CliRunner output that rich has hard-wrapped mid-phrase ('...is not a linked git \nworktree'). Setting COLUMNS=200 does not change it, so the console width inside CliRunner is fixed — this is the known 'assert on rich-wrapped output' brittleness, not a behaviour regression. test_workflow_check's 'nothing is discoverable' case gets 'fr-goal: ok', i.e. a shipped manifest IS discoverable where the test expects none — an environment/resolution-order issue, again not phase-1 related.

Why it matters here: P4.T3 runs the full CI gate on this branch and will hit these three. They must be triaged separately (likely as a pre-existing defect on main, with its own fix), not silently absorbed into this run — and the phase-4 executor should not read them as damage from phases 1-3.

<!-- fr:journal kind=discovery scope=plan id=pre-existing-red-root-causes created=2026-09-20T15:18:31 phase=1 -->
### pre-existing-red-root-causes · discovery · Root causes for the three pre-existing red tests: both are host-dependent tests, not regressions (phase 1)

Chased down after phase 1 reported them (finding 5661437b7bff). Neither is caused by this branch — `git diff --stat origin/main...HEAD` is docs-only plus one standalone new test module nothing imports.

(1) test_run_workspace.py::test_a_forged_worktree_marker_in_a_plain_directory_is_refused and ::test_an_external_marker_without_container_evidence_is_refused — rich hard-wraps the CLI error at the console width CliRunner reports on this host, so the real output reads 'is not a linked git \nworktree' while the test asserts the unwrapped substring 'not a linked git worktree'. The assertion is width-dependent; it passes wherever the wrap lands elsewhere.

(2) test_workflow_check.py::test_cli_all_fails_when_nothing_is_discoverable — the test empties the shipped dir and monkeypatches packaged_shipped_workflows_dir to None, but the resolver has a FOURTH source: the Claude Code marketplace clone. ~/.claude/plugins/marketplaces/derio-net--super-fr/plugins/super-fr/workflows/fr-goal.yaml exists on any machine with super-fr installed, so 'fr-goal: ok' is discovered and exit_code is 0. 'Nothing is discoverable' is unreachable on an operator machine — the test can only pass on a host where super-fr is NOT installed, i.e. CI.

Both are the same defect class: a test asserting a property of the host rather than of the code. OUT OF SCOPE for #428 (the operator scoped this run to the dispatch-verb lint). Consequence for P4.T3, which runs the full gate: these three must be accepted as pre-existing on this host, verified to be exactly these three and no more. Worth its own issue; surfaced in the PR body for the operator to decide.

<!-- fr:journal kind=finding scope=plan id=c1-corpus-api created=2026-09-20T15:35:25 phase=1 state=fixed -->
### c1-corpus-api · finding [fixed] · C1: the corpus API discarded tick state and fences, making phase 2's zero-hit assertion unsatisfiable (phase 1)

Review finding, confirmed and measured. agentic_steps() yielded raw step text only, but spec §4.A exempts ticked steps and strips fenced code — and 1826 of the corpus's 2113 agentic steps are ticked (86%). P2.T2.S2 as written ('run the detector over agentic_steps() and assert ZERO hits') could not pass, and would have forced phase 2 to re-implement the gate's exemptions inside the test, the single most likely place for them to drift from the shipped gate. FIXED: corpus_plans() now exposes the parsed plans as the primary phase-2 feed, so the corpus regression runs the REAL fr.plan_ops.self_review and inherits agentic-only + state=='x' for free; agentic_steps() widened to a CorpusStep NamedTuple carrying the state so the raw measurement stays expressible. 02.yaml P2.T2.S2 rewritten to match.

<!-- fr:journal kind=finding scope=plan id=c2-plan-trips-own-gate created=2026-09-20T15:35:25 phase=1 state=fixed -->
### c2-plan-trips-own-gate · finding [fixed] · C2: the plan's own step text tripped the gate it specifies — and the nominal mechanism tokens were the reason (phase 1)

Review finding, confirmed by measurement. P2.T1.S2, P2.T3.S1 and P2.T3.S2 carried 'Agent tool' / 'subagent_type' unfenced; under spec §4.A as first written, all three would error the moment the detector landed, and P4.T3.S2 (which dogfoods self-review on this very plan) would fail. Root cause was NOT the plan text: bare 'Agent tool' and 'Task tool' are ordinary nouns in a repo that documents dispatch, and over the whole corpus the nominal form flagged exactly 3 steps, ALL 3 of them this plan describing what the executor lacks. A gate whose only real-world hits are the plan implementing it is measuring the wrong thing. FIXED in the spec: pattern 2 now requires an instructional frame — (use|call|invoke) the <X> (agent|subagent|Task tool|Agent tool), or subagent_type immediately followed by : or =. Measured 0 hits on the corpus, still catches 'Call the Task tool with subagent_type: general-purpose'.

<!-- fr:journal kind=finding scope=plan id=w1-soft-wrap-anchor created=2026-09-20T15:35:26 phase=1 state=fixed -->
### w1-soft-wrap-anchor · finding [fixed] · Found while re-measuring: a soft line-wrap faked an instruction boundary (phase 1)

Not in the review; surfaced by running the refined patterns over the corpus. The head anchor treated a bare newline as a sentence boundary, and plan step text is hard-wrapped prose — so phase 3's own step, 'A step instructing you to dispatch, delegate to, spawn or\nhand off to a subagent is a BLOCKER', matched purely because the wrap landed before the verb. It describes the contract; it instructs nothing. This would have fired on ordinary prose forever. FIXED: an instruction boundary is start-of-text, real punctuation (.;:!?), or a list marker starting a line — never a bare newline. A list item is a fresh instruction and keeps its anchor; a wrap is a formatting artifact. Re-measured: 9/9 curated true positives (now including the list-marker form), 7/7 true negatives, 0 hits across 2113 corpus steps.

<!-- fr:journal kind=finding scope=plan id=i1-enforce-fr-version created=2026-09-20T15:35:26 phase=1 state=fixed -->
### i1-enforce-fr-version · finding [fixed] · I1: 'the skip is unavoidable' was untrue, and fixing it grew the corpus by 50% for free (phase 1)

Review finding, confirmed. fr.parser.parse takes enforce_fr_version and its own docstring says that gate 'must never apply to a purely historical read', naming fr.spec.compute_status as the caller that passes False. A corpus scan is exactly such a read. Measured: enforcing gives 44 plans / 1444 steps with 41 skips; not enforcing gives 82 plans / 2113 steps with only 3 (genuine PhaseDoc failures). FIXED: the harness now passes enforce_fr_version=False and the comment states the reasoning instead of claiming necessity. Critically, the verdict is unchanged — the refined patterns score 0 hits on BOTH corpora, so widening it cost no adjudication and bought a 50% larger evidence base. This also resolves I2 (see below).

<!-- fr:journal kind=finding scope=plan id=i2-floor-headroom created=2026-09-20T15:35:26 phase=1 state=fixed -->
### i2-floor-headroom · finding [fixed] · I2: the floors were coupled to the next major fr bump, with zero headroom (phase 1)

Review finding, confirmed. Under the enforcing read, 14 of the 44 parsing plans carry a <5.0.0 ceiling, so fr 5.0.0 would drop the corpus to exactly 30 plans / 1047 steps — the old >=30 floor passing by a margin of zero, and going red the next time a plan is archived, for a reason unrelated to the lint. FIXED by I1's enforce_fr_version=False, which decouples the corpus from the version entirely; floors re-baselined to >=70 plans / >=1800 steps against today's 82 / 2113.

<!-- fr:journal kind=finding scope=plan id=i3-per-root-floor created=2026-09-20T15:35:27 phase=1 state=fixed -->
### i3-per-root-floor · finding [fixed] · I3: aggregate floors do not defend the live-plans root, which is where the gate actually bites (phase 1)

Review finding, confirmed and measured. Live plans are 5 of 82 (134 of 2113 steps). Rename, move or typo that root and the aggregate is still 77 plans / 1979 steps — comfortably over every floor — while the plans authors are writing RIGHT NOW are never read. FIXED: test_every_corpus_root_contributes asserts each root exists and contributes at least 3 plans.

<!-- fr:journal kind=finding scope=plan id=i4-lru-cache created=2026-09-20T15:35:27 phase=1 state=fixed -->
### i4-lru-cache · finding [fixed] · I4: the corpus was parsed once per consumer, and phase 2 adds more consumers (phase 1)

Review finding, confirmed (0.87s per full parse; 3 parses per module run). FIXED: functools.lru_cache(maxsize=1) on _parse_corpus, returning a tuple so a cached value cannot be mutated by a caller. Module runtime fell from 2.84s to 1.33s despite a 50% larger corpus and an extra test.

<!-- fr:journal kind=finding scope=plan id=m2-blank-step-text created=2026-09-20T15:35:27 phase=1 state=fixed -->
### m2-blank-step-text · finding [fixed] · M2: isinstance(text, str) waved through a step whose text had vanished (phase 1)

Review finding, confirmed (0 of 2113 blank today, min length 7). FIXED: assert step.text.strip().
