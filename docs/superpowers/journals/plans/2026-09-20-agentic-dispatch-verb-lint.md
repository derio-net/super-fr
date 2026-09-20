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

<!-- fr:journal kind=finding scope=plan id=05793d7b5aa2 created=2026-09-20T15:50:03 phase=2 state=fixed -->
### 05793d7b5aa2 · finding [fixed] · Rich ate the escape route: '[manual]' and every '[error]' prefix were silently dropped by fr plan self-review (phase 2)

Found by P2.T3.S1, the end-to-end CLI test, and it is exactly the defect that test exists to catch. fr.plan_ops.self_review's message is correct in memory, but plan_cmd.self_review_cmd printed it with console.print(str(issue)) — rich parses '[...]' as a style tag and DROPS what it does not recognise. Observed output: '...or move the dispatch into a phase.' The four load-bearing tokens the spec pins are 'no Agent tool', 'task: deny', '[manual] phase', '#428'; three survived, the one naming the escape route did not.

The blast radius is wider than #428: str(ReviewIssue) is '[{severity}] {message}', so EVERY self-review issue has been printed without its severity prefix since the command shipped. A reader could not tell an error from a warn in the CLI output at all. Any other lint whose message carries brackets lost them too.

FIXED in packages/fr/src/fr/commands/plan_cmd.py: console.print(escape(str(issue))) with rich.markup.escape, plus a comment stating that a lint message is data, not markup. Pinned by tests/unit/test_v2_plan_ops.py::test_plan_self_review_cli_exits_1_and_names_both_escapes, which asserts all four tokens against whitespace-normalized output.

Deviation note: this is a one-line fix in a command module phase 2's step text does not name. It is in scope because P2.T3's contract is the end-to-end CLI verdict, and the message cannot 'carry' a token the CLI deletes on the way out.

<!-- fr:journal kind=discovery scope=plan id=e2b40b82b564 created=2026-09-20T15:50:22 phase=2 -->
### e2b40b82b564 · discovery · The shipped detector re-measures at 82 plans / 2113 agentic steps / 0 hits, and all three refinements are individually load-bearing (phase 2)

Re-measured with the REAL fr.plan_ops.self_review over corpus_plans(), not with the patterns applied to raw text.

Verdict: census Census(plans_parsed=82, plans_skipped=3, agentic_steps=2113), dispatch-gate hits = 0. Exactly the number phase 1 and spec 2.D predicted.

Counterfactuals, each run over the 286 PENDING agentic steps (1827 of 2113 are ticked and exempt):

1. Bare newline as an instruction boundary: 2 hits, both this plan — P2.T1.S2 'spawn or\nhand off to a subagent' and P3.T1.S2 'hand off to a subagent'. Both describe the executor contract; neither instructs. The refinement stands.

2. Bare mechanism nouns (Task tool / Agent tool / subagent_type with no instructional frame): 2 hits, both this plan — P2.T3.S1 and P2.T3.S2, quoting the verdict's own token list. (Phase 1 measured 3; the third was P2.T1.S2 before the plan was rewritten.) The refinement stands.

3. Stripping inline backticks as well as fences: the observed defect 'Dispatch `blog-craft:post-researcher` per post' stops matching entirely — the object IS the backticked name. The refinement stands.

One refinement NOT in the plan text, found while implementing: the punctuation boundary must require trailing whitespace, i.e. (?<=[.;:!?])\s+ rather than (?<=[.;:!?]). Without it 'fr_dispatch.tick()' reads as a sentence start, and so does the ellipsis in this plan's own P2.T1.S2 ('"...spawn or'), which would have flagged the step describing the refinement. It is the same principle as the soft-wrap rule — a boundary is a real sentence break, not any occurrence of the character.

For scale: a naive \bdispatch\b over all 2113 steps hits 292 (spec 2.D's 237 was the smaller enforcing-read corpus).

<!-- fr:journal kind=discovery scope=plan id=4f601edccc3a created=2026-09-20T15:50:33 phase=2 -->
### 4f601edccc3a · discovery · The first fence-exemption fixture was vacuous — it passed with _strip_fenced_code deleted (phase 2)

P2.T2.S1(c) asks for 'a dispatch verb inside a fenced block yields NO issue'. The obvious fixture was:

  Write the fixture the cold reader consumes:\n\n```\nDispatch the cold-reader agent over the draft\n```

It passed. It also passed with the strip removed, because the opening fence itself sits between the ':' boundary and the verb, so the head pattern never reached 'Dispatch' on the raw text either. The test asserted nothing about the exemption it was named for — this repo's recurring defect, a check that reports success while doing nothing.

Fixed by giving the fenced block its OWN instruction boundary, a list marker:

  Quote the rejected wording in the skill's example block:\n\n```\n- Dispatch the cold-reader agent over the draft\n```

Raw text matches ('- Dispatch the cold-reader'); stripped text does not. The test now carries an explicit assertion that the raw fixture still matches _RE_DISPATCH_HEAD, so a future edit cannot quietly make it vacuous again. Mutation-verified: with 'scanned = step.text' substituted for 'scanned = _strip_fenced_code(step.text)', the test fails and the other 13 dispatch tests still pass.

Generalisable: for an EXEMPTION test, the fixture must be one the detector would otherwise fire on. Asserting the positive match alongside the exemption is the cheapest way to pin that.

<!-- fr:journal kind=finding scope=plan id=ebfd1af6071a created=2026-09-20T15:54:58 phase=2 state=open -->
### ebfd1af6071a · finding [open] · Phase 2's two acceptance rows are still not-implemented — phase 4 owes the flip (phase 2)

'fr plan edit --complete-phase 2' warned: 'phase 2 completed but its acceptance rows are still not-implemented: goal-agentic-dispatch-purity, goal-dispatch-lint-precision'.

Left deliberately. The plan assigns the matrix work to P4.T1, and .claude/rules/acceptance-matrix.md requires the status move to carry evidence refs plus a --notes reason, which is a phase-4 shape ('fr acceptance set-status --id ... --status ci --level unit=... --notes ...'). Flipping them here would either duplicate P4.T1 or land a half-cited row.

The refs phase 4 needs now exist:
- goal-dispatch-lint-precision -> super-fr:tests/unit/test_dispatch_lint_corpus.py::test_the_dispatch_gate_scores_zero_on_this_repos_own_plans (82 plans / 2113 agentic steps / 0 hits)
- goal-agentic-dispatch-purity -> super-fr:tests/unit/test_v2_plan_ops.py::test_self_review_errors_on_dispatch_verb_in_agentic_step and ::test_plan_self_review_cli_exits_1_and_names_both_escapes

Closes when P4.T1 runs set-status on both.

<!-- fr:journal kind=discovery scope=plan id=b6c9cc6229ea created=2026-09-20T16:27:10 phase=2 -->
### b6c9cc6229ea · discovery · Correction to e2b40b82b564: the 'fr_dispatch.tick()' half of the trailing-whitespace rationale was wrong (phase 2)

Journal entries are append-only, so this corrects e2b40b82b564 rather than rewriting it.

That entry justified requiring trailing whitespace on the punctuation boundary — (?<=[.;:!?])\\s+ rather than (?<=[.;:!?]) — with two examples. One is right, one is not.

RIGHT: the ellipsis. '"...spawn or' has '.' immediately before 'spawn'; without the \\s+ that reads as a sentence start and this plan's own P2.T1.S2 is flagged. Now pinned by a true-negative fixture carrying the literal text, so the rule is defended in the precision direction and not only in the recall direction.

WRONG: 'fr_dispatch.tick()'. That string matches under NEITHER variant, because no dispatch verb follows the '.' — 'tick()' does. It was cited from reasoning about what the pattern could do, not from running it. Re-checked: with the \\s+ removed, 'GREEN: implement fr_dispatch.tick() so it dispatches phases to the runner' still does not match.

The lesson is the one this run keeps re-learning: a rationale sentence is a claim, and a claim that was not executed is a guess wearing evidence's clothes. The entry's verdict stands (the refinement is real and now mutation-tested); one of its two supporting facts did not.

<!-- fr:journal kind=finding scope=plan id=6f0e2519d163 created=2026-09-20T16:27:58 phase=2 state=fixed -->
### 6f0e2519d163 · finding [fixed] · Phase-2 review: the ZERO-hits claim was measured over the wrong population, and seven pattern defects followed from it (phase 2)

Seven defects, all confirmed by the reviewer against shipped code and re-confirmed here before fixing. Recorded together because they share one root cause.

ROOT CAUSE. The corpus regression ran the real self_review and filtered its issues — gate-accurate, and blind by construction to 1835 of 2113 agentic steps, because the gate exempts ticked ones. The comment in plan_ops.py claimed "ZERO over the same 2113 agentic steps". Measured: _RE_DISPATCH_HEAD was genuinely 0/2113, but _RE_DISPATCH_MECHANISM had 1 live hit — 2026-09-19-opencode-subagent-dispatch P4.T1.S2, matched 'subagent_type:', state 'x'. The test was green because the step is ticked. The exemption is also temporal: that plan, read a week earlier, was unticked, and the gate would have errored on it at authoring time — exactly when this gate is meant to be usable.

C1. Pattern 2 was entirely undefended: replacing _RE_DISPATCH_MECHANISM with a never-matching regex left 85/85 green, so half of normative §4.A was deletable in silence. FIXED with three true positives ("Use the fr-phase-executor agent for each phase", "Call the Task tool with subagent_type: general-purpose", "Invoke the code-reviewer subagent on the diff").

C2. The frameless subagent_type[:=] arm is DROPPED. In YAML and markdown that token is a key name — a mention, not a call site — which is why it hit a legitimate live plan, and the in-flight 2026-09-20-opencode-tier-binding-reaches-dispatch would have hit it next, at error severity, while being authored. The framed form still catches "Call the Task tool with subagent_type: general-purpose".

I1. The head window spanned newlines while pattern 2's did not. FIXED: [^.;:!?\n]{0,60}?. It costs the verb-and-object-split-by-wrap shape; the cost is taken deliberately and pinned by test_self_review_dispatch_gate_does_not_look_across_a_line_break.

I2. The boundary anchored POSITION, not MOOD. FIXED three ways: bare verb stems only (no -es/-ed/-ing); a negative lookahead refusing "of" plus copulas/modals after the verb; and lookbehinds excluding e.g./i.e./etc./cf./vs., which all satisfy punctuation-then-whitespace while continuing a sentence. A FOURTH defect surfaced while writing the fixture that isolates the first: the bare stem "dispatch" matched the PREFIX of "dispatching", so the mood rule bought nothing until a trailing \b was added. It was found only because the new true negative was written to isolate that one element — the general lesson of this round.

I3. _FENCED_CODE_RE mis-paired 4-backtick fences. Verified against the old regex: a ````markdown block quoting a ```-fenced one paired the outer opener with the INNER closer and left "- Dispatch the cold-reader agent over the draft" UN-FENCED and matching. That is worse than stripping too little — the gate fires on a step whose only crime is quoting the thing it forbids, and it is the exact shape phases 3/4 must write into SKILL.md. FIXED with a backreference on the captured opening run (a longer closer is accepted). Unterminated fences now strip to end of text, decided explicitly: for a precision-first gate, an opened block means everything after it is content.

I4. Any backticked word:word counted as an agent object, re-admitting the 42-hit class of §2.D (plan:my-slug, fr:synced, fr.tracker:GithubTracker, start:end, cli:app). FIXED: every object arm requires a role word. The backticked arm is kept and is NOT redundant — it is what makes the REPORTED match the complete token including its closing backtick; the unbackticked colon arm catches a glued name (blog-craft:postresearcher) where the role word has no word boundary. Both now die under mutation.

I5. Pattern 2 had no instruction anchor and admitted using/calling/invokes. FIXED: the same _INSTRUCTION_BOUNDARY as pattern 1, bare stems only, plus a required non-empty modifier between "the" and the role word — which is what separates naming an agent from "Use the agent frontmatter in plugins/super-fr/agents/fr-phase-executor.md".

ALSO: _pending_agentic_steps renamed _not_ticked_steps (it checked neither "agentic" nor "pending" — it yields '-' too).

VERIFICATION. A 15-mutant sweep now kills every element of §4.A: each pattern, the window's newline exclusion, the bare stems, the verb word boundary, the predicate guard, the abbreviation lookbehinds, the fence backreference, the unterminated-fence decision, both object arms, the role-word requirement, the mechanism anchor, the mechanism stems, the non-empty modifier, and the fence strip itself. Before this round, four of those elements had no test that noticed their removal.

RE-MEASURED after all seven fixes: 82 plans / 2113 agentic steps / 1835 ticked / 278 pending. HEAD 0 over all, 0 over pending. MECHANISM 0 over all, 0 over pending. The pattern-level corpus test now asserts that over ALL steps, and it goes red (naming slug, step id, state and matched text) if the frameless subagent_type arm is restored.

<!-- fr:journal kind=discovery scope=plan id=29da23f914cb created=2026-09-20T16:28:14 phase=2 -->
### 29da23f914cb · discovery · The deliberate d2 recall baseline: four dispatch shapes the gate does not flag, and why (phase 2)

Decision d2 is precision over recall, and this is the bill for it — written down so that a future reader deciding whether to widen the gate is arguing against a known list rather than discovering it.

Shapes the gate does NOT flag today, each a real instruction to dispatch:

  "Launch a subagent to gather evidence"
  "Run the code-reviewer agent over the diff"
  "Ask the cold-reader agent for a verdict"
  "Send the draft to the cold-reader agent"

The verb list is closed at dispatch / delegate to / spawn / hand off to / fan out to. "Launch", "run", "ask" and "send" are all far more common in ordinary plan steps than in dispatch instructions — "Run the test suite" is the single most common step shape in this corpus — so adding them trades a large precision loss for a small recall gain. §2.D is the evidence that the trade goes the wrong way: this is a repo about dispatch, and a gate that fires on prose gets switched off.

Two further priced gaps, both pinned by tests rather than merely stated:

  * verb and object split by a hard wrap ("Dispatch the\ncold-reader agent") — the window excludes \n, because one that spans newlines lets an object on an unrelated wrapped line manufacture a hit;
  * a dispatch instruction inside a fenced block — stripped as content, which is what makes it safe for a skill to quote a rejected step.

If a real defect ever escapes through one of these, the right response is to add the specific shape and re-run both halves of the corpus measurement, not to loosen an anchor. Every element of the current shape dies under mutation, so a widening that breaks precision will show up as a red test naming the plan, the step and the matched text.

<!-- fr:journal kind=finding scope=plan id=9002f8a61068 created=2026-09-20T16:28:48 phase=2 state=open -->
### 9002f8a61068 · finding [open] · Out of scope, needs its own issue: 40 command-layer print sites interpolate into rich unescaped, and one can crash the parse-error reporter (phase 2)

OUT OF SCOPE for #428 — recorded open, deliberately not fixed here. It needs its own issue.

The #428 work fixed ONE print site (plan_cmd.py self_review_cmd, finding 05793d7b5aa2: rich was silently dropping "[manual]" and every "[error]"/"[warn]" severity prefix). That fix was in scope because the phase-2 contract is the end-to-end CLI verdict. The class it belongs to is not.

Scope of the class, measured in this checkout: 40 sites under packages/fr/src/fr/commands/ interpolate an exception or other runtime value into a rich markup string as print(f"...{e}"), out of 123 console.print(f"...") sites overall. None escapes.

Two failure modes, both reproduced:

  Console.print("parse error: [manual] phase missing")
    -> "parse error:  phase missing"          # token silently DROPPED

  Console.print("parse error: unexpected [/red] token")
    -> rich.errors.MarkupError: closing tag '[/red]' at position 24
       doesn't match any open tag                # RAISES

The second is the serious one. plan_cmd.py:358 is

    err_console.print(f"[red]parse error:[/red] {e}")

so if a PlanSchemaError message ever contains a "[/...]"-shaped token — a step text, a YAML fragment, a path, anything quoted back from the plan being parsed — then `fr plan self-review` crashes with a MarkupError while trying to report the parse error. The diagnostic destroys its own diagnosis, and the traceback names rich rather than the plan.

Shape of the fix, when someone takes it: rich.markup.escape at the interpolation boundary, i.e. escape the DATA and leave the literal markup alone — escape(str(e)) inside an f-string whose "[red]" tags are author-written. A blanket markup=False would also kill the intended colouring. A tripwire over packages/fr/src/fr/commands/ for print(f"...{...}") without escape() is plausible but needs care: many interpolations are values the author knows are safe (ints, enum members, already-escaped text), so the useful rule is probably narrower — "no unescaped interpolation of an exception or of file-sourced text".

Closes when that issue ships. Until then, any command that echoes parsed-file content is one bracket away from crashing on the error it exists to report.

<!-- fr:journal kind=finding scope=plan id=1e6e265c4887 created=2026-09-20T16:52:24 phase=3 state=fixed -->
### 1e6e265c4887 · finding [fixed] · The contract prose tripped the tool-neutrality tripwire — naming `Agent` in a skill needs an all-harness clause (phase 3)

Writing the #428 contract into fr-execute/fr-plan named two harness-specific tools (`Agent`, `task: deny`), and tests/unit/test_tripwire_skill_tool_neutrality.py failed on four files — both canonical skills and both .opencode mirrors:

  plugins/super-fr/skills/fr-execute/SKILL.md:74: names 'Agent' (claude-code) outside a scoped clause naming more than one harness
  plugins/super-fr/skills/fr-plan/SKILL.md:81: names 'Agent' (claude-code) outside a scoped clause ...

The agent file (plugins/super-fr/agents/fr-phase-executor.md) is NOT scanned — only skills are — so the same sentence is legal there and illegal one file over. That asymmetry is correct (the agent file is already per-harness by construction, and its four .opencode variants are generated) but it is a trap for anyone writing the same contract into both.

FIXED two different ways, deliberately:

1. fr-execute keeps the concrete tools inside a `**Harness — dispatch:**` clause naming all three supported harnesses (fr.harness.prose requires len(SUPPORTED_HARNESSES) == 3 labels in the span). Worth the four lines: the clause is where the Hermes fact had to be stated, and it is the load-bearing one — Claude Code omits `Agent` from the frontmatter grant and OpenCode's generated agent sets `task: deny`, but on Hermes NOTHING denies a further `delegate_task` (.hermes/config.snippet.yaml registers hooks only; there is no per-agent tool grant). On that harness the prose contract is the entire enforcement, which is exactly why spec §4.B insists the contract live in the skill and not only in the Claude Code agent file.

2. fr-plan drops the tool names entirely — "the phase executor has no dispatch tool on any harness" — because the bullet is operator-facing planning guidance where the per-harness mechanics are noise, and a clause there would cost three lines against a hard line cap (see the sibling finding).

<!-- fr:journal kind=finding scope=plan id=06f27ad3cc42 created=2026-09-20T16:52:53 phase=3 state=fixed -->
### 06f27ad3cc42 · finding [fixed] · Both skills phase 3 must edit sat at exactly the 120-line cap, so every new line was paid for out of neighbouring prose (phase 3)

tests/unit/test_skill_validation.py::test_under_120_lines is a hard cap (<= 120, no allowlist). Before phase 3, fr-execute/SKILL.md and fr-plan/SKILL.md were BOTH at exactly 120 — measured by stashing this phase's diff. So §4.B's and §4.C's prose could not simply be added: fr-execute went to 137 and fr-plan to 127 on the first green pass, and both failed.

This is a structural fact about editing these two files, not a one-off: a cap that is already met means the next contract someone ships has the same bill, and the obvious way to pay it — rewrapping — is the exact move the sibling test test_no_hyphenated_word_is_broken_across_lines exists to catch (a line ending in letter+hyphen renders as a space, and its docstring records three such defects introduced by precisely this pressure).

Paid, keeping content, by compressing prose adjacent to the edit rather than dropping any norm:

fr-execute (-17 to land at 120): intro and announce merged; "When creating the PR for an agentic phase:" folded into the heading and the `fr pickup` title-template pointer into the bullet it describes; label-lifecycle intro, the `closed` bullet and the `fr apply` tail each one line tighter; step 1's pickup output note 4 -> 3 lines; step 5's PR caveat 7 -> 7 with tighter wording to free the surrounding lines; step 6's idempotence note re-wrapped; the v1-migration preamble 2 -> 1; and the new Constraints bullet cut to a single line ("A dispatch instruction is a BLOCKER, never a tick or a skip (step 3)").

fr-plan (-7): intro and announce merged; the `NN.yaml` bullet and the cross-repo-completeness bullet one line tighter each; "## Dependency declarations" four bullets folded into the sentence they restated (-4); the new outcomes bullet written in 6 lines rather than 7.

Everything removed was redundancy or restatement; no rule, pointer or token disappeared (test_skill_validation's per-skill required tokens, "flip"/"fr acceptance" for fr-execute and "acceptance:"/"fr acceptance add" for fr-plan, all still pass, as do the fr pickup / fr apply / pr-ready / TDD-cycle pins).

One casualty worth naming: fr-execute's paragraph says "A tick claims performance" where the agent file says "A tick is a claim of performance" — the fuller phrasing measured at 121 lines. If anyone reclaims a line there, spend it on that sentence.

<!-- fr:journal kind=discovery scope=plan id=3ba26d5efb5d created=2026-09-20T16:52:54 phase=3 -->
### 3ba26d5efb5d · discovery · P3.T2.S1 names two mirror guards; there are THREE mirrors — .hermes/skills/fr/ has its own script and tripwire (phase 3)

The plan step says: run scripts/sync-opencode.py, then verify test_tripwire_opencode_skills_sync.py and test_opencode_agent_mirror.py. Both were green — and the full suite still failed on tests/unit/test_tripwire_hermes_skills_sync.py::test_mirror_has_no_drift, because .hermes/skills/fr/ is a THIRD byte-for-byte mirror of plugins/super-fr/skills/, regenerated by a DIFFERENT script (scripts/sync-hermes.py, which also writes .hermes/SOUL.d/super-fr-rules.md from the shipped rules).

So any edit to a canonical SKILL.md owes three commands, not one:

  uv run python scripts/sync-opencode.py     # .opencode/skills, instructions, commands, 4 agent variants
  uv run python scripts/sync-hermes.py       # .hermes/skills/fr/, .hermes/SOUL.d/
  uv run pytest tests/unit/test_tripwire_opencode_skills_sync.py tests/unit/test_opencode_agent_mirror.py tests/unit/test_tripwire_hermes_skills_sync.py -q --no-cov

Not a defect in the plan so much as a documentation gap that the plan inherited: AGENTS.md's "Skills/rules: canonical source vs. generated mirrors" section names only sync-opencode.py and its two tripwires. The Hermes mirror exists, is tracked, and is gated in CI by the same full-suite run, so the only thing missing is the pointer. Worth adding to AGENTS.md in a future pass (out of scope for #428, which touches no mirror machinery).

<!-- fr:journal kind=discovery scope=plan id=6a35a818840e created=2026-09-20T16:53:06 phase=3 -->
### 6a35a818840e · discovery · A prose-token test is blind to the markup it sits in: '**no `Agent` tool`' passed every assertion (phase 3)

While refactoring P3.T1.S4 I typed "**no \`Agent\` tool\`" into fr-execute — a bold-open with a backtick where the bold-close belonged, which renders as a stray literal run rather than bold text. tests/unit/test_skill_tokens.py stayed green through it, because the token it pins ("no \`Agent\` tool") is a substring of the malformed string.

Caught by eye on the grep-back, not by a test. That is the honest limit of a token test and it is the right limit — pinning rendered markup would mean rendering the skill, which nothing in this repo does — but it is worth stating where the tests live: these assertions defend that a CONTRACT is still stated, not that it is stated well or even legibly. The same blindness covers a token that survives inside a sentence whose meaning has been inverted.

Cheap mitigation used here, and recommended for the next prose edit: after the tests go green, grep the token back with context (grep -n "Agent\` tool" on all three surfaces) and read the line, rather than trusting the green.

<!-- fr:journal kind=finding scope=plan id=6325b88c63f3 created=2026-09-20T16:53:29 phase=3 state=open -->
### 6325b88c63f3 · finding [open] · Phase 3's acceptance row goal-executor-refuses-tick is still not-implemented — phase 4 owes the flip, refs below (phase 3)

Same shape as ebfd1af6071a (the two phase-2 rows), left open for the same reason: the plan assigns matrix work to P4.T1, and .claude/rules/acceptance-matrix.md requires the move to carry evidence refs plus a --notes reason via `fr acceptance set-status`, which is a phase-4 shape. `fr plan edit --complete-phase 3` warned as designed.

The ref phase 4 needs now exists:

  goal-executor-refuses-tick -> super-fr:tests/unit/test_skill_tokens.py::test_fr_phase_executor_names_the_dispatch_refusal and ::test_fr_execute_names_the_dispatch_refusal

Be honest in the --notes about what those prove: they pin that the prose contract is PRESENT on both surfaces (agent file and fr-execute skill), which is all a prose contract can be checked for automatically. They cannot show an executor obeyed it. The only thing that can is a live run against a plan containing a dispatch step — and #428's whole design is that such a plan no longer passes `fr plan self-review`, so the enforcement pair is: the lint stops the step being authored (pinned by executable tests in test_v2_plan_ops.py / test_dispatch_lint_corpus.py), and the prose catches a step that predates the lint or arrives from outside.

Closes when P4.T1 runs set-status on it.

<!-- fr:journal kind=finding scope=plan id=p3-i1-harness-overclaim created=2026-09-20T17:05:30 phase=3 state=fixed -->
### p3-i1-harness-overclaim · finding [fixed] · I1: fr-plan claimed 'no dispatch tool on any harness' while fr-execute, in the same commit, said the opposite (phase 3)

Review finding, verified independently. fr-plan/SKILL.md said the phase executor 'has no dispatch tool on any harness'; fr-execute/SKILL.md's new Harness clause said 'on Hermes only this contract stops a further delegate_task'. Both cannot be true, and fr-execute's is the correct one: .hermes/config.snippet.yaml registers hooks matching only 'write_file|patch' and 'terminal|execute_code' — nothing matches delegate_task — and .hermes/ has no agent directory at all, so there is no per-agent grant that could deny it. plugins/super-fr/hooks/fr-phase-executor-guard.sh says as much ('Hermes needs no sibling'). The overclaim was born of compression pressure: dropping the tool names to avoid a three-line harness clause widened a two-harness fact into a three-harness one, and the third harness is exactly where it fails. FIXED: 'is a leaf, not an orchestrator' — same line count, and it echoes the agent file's opening sentence, which reinforces the one-contract framing P3.T1.S4 was for. Worth keeping in view: on Hermes the prose IS the enforcement, which is the whole argument for spec §4.B putting the contract in the skill and not only in the agent file.

<!-- fr:journal kind=finding scope=plan id=p3-i2-fr-ready-qualifier created=2026-09-20T17:05:31 phase=3 state=fixed -->
### p3-i2-fr-ready-qualifier · finding [fixed] · I2: compressing the fr:ready bullet made its condition stricter than the code (phase 3)

Review finding, verified against packages/fr/src/fr/render.py. The bullet went from 'has a tracking_issue but no assignee, no draft PR, and no open non-draft PR' to 'a tracking_issue, no assignee, no draft or non-draft PR', dropping the 'open' qualifier. _item_state computes has_open_pr_nondraft as 'pr.state == OPEN and not pr.draft and not pr.merged', so as compressed the doc says any CLOSED or MERGED linked PR disqualifies fr:ready forever — which is not what the renderer does. Low operational blast radius (a merged PR usually means the phase is done anyway), but it is a CONDITION changed, which the phase's 'redundancy only' compression claim did not cover. FIXED with four characters: 'no open draft or non-draft PR'. The general lesson is recorded in the line-cap finding: a hard line cap turns prose edits into a compression negotiation, and conditions are the first casualty because qualifiers read as filler.

<!-- fr:journal kind=discovery scope=plan id=p3-tool-neutrality-scope created=2026-09-20T17:05:31 phase=3 -->
### p3-tool-neutrality-scope · discovery · The tool-neutrality tripwire scans SKILL.md only — agent files are ungated (phase 3)

Noted by review, not a defect. fr.harness.prose.scan_prose covers */SKILL.md under the three skill trees, so plugins/super-fr/agents/fr-phase-executor.md and the four .opencode/agent/*.md may name Agent and 'task: deny' freely, while the identical sentence one file over in a SKILL.md requires a clause naming all three harnesses. That asymmetry is defensible — an agent file is per-harness by construction — but it means the next contract edit can pass every gate in the agent file and fail in the skill, which is exactly what happened here. Recorded so the next editor is not surprised.

<!-- fr:journal kind=discovery scope=plan id=b87b7e78beec created=2026-09-20T17:08:56 phase=4 -->
### b87b7e78beec · discovery · The corpus counts this plan, so any ticked-step number written into an artifact is stale the moment the next step is ticked (phase 4)

While writing the goal-dispatch-lint-precision row notes I nearly pinned 'N of the corpus's 2113 agentic steps are ticked'. Measured live during P4.T1 it is 1841; test_dispatch_lint_corpus.py's own docstrings say 1827 (DISPATCH_GATE_TOKEN) and 1835 (test_the_dispatch_gate_scores_zero_on_this_repos_own_plans). All three are 'right' — they were measured at different moments.

The cause is that corpus_plans() reads the LIVE plans root, which contains 2026-09-20-agentic-dispatch-verb-lint itself. Every fr plan edit --tick I run during phase 4 increments the corpus's ticked count. The corpus is self-referential by design (that is what makes the precision claim honest — it measures the repo's real plans, including the one shipping the detector), but it means a ticked count is a moving measurement and does not belong in any artifact that is not regenerated.

What IS stable and safe to cite: plans_parsed=82, agentic_steps=2113, gate hits=0, pattern hits=0 (the tick state changes, the step population does not, until a new plan lands). The floors MIN_PLANS=70 / MIN_AGENTIC_STEPS=1800 are deliberately below the live numbers for exactly this reason.

So the matrix row notes say 'the large majority of the corpus' rather than a number. The two stale docstring counts are cosmetic and pre-existing; left alone rather than churned, since the next tick would stale them again. If anyone wants them accurate, the fix is to state them as a proportion or to drop the absolute.

<!-- fr:journal kind=discovery scope=plan id=3c469a2a805b created=2026-09-20T17:11:53 phase=4 -->
### 3c469a2a805b · discovery · The explainer renderer's --isolated warning reproduces on this machine — verified with a deliberate control render (phase 4)

explainers-currency.md documents the codehilite trap being found twice: run the render from inside the worktree and the project venv's pygments leaks in; run it from / on a machine with a GLOBAL pygments and --isolated is still needed. Both halves were treated as prose until now. P4.T2.S2 measured them.

Verification render (the one the rule prescribes), from / with --isolated, on the UNMODIFIED 01-fr-goal.md:
  cmp exit 0 — byte-identical to the committed page
  sha256 3cfef3f777a196849dc7788748259f3e794b8b43b18939e4b17652615f9b2661 on both files

Control render, identical in every way EXCEPT dropping --isolated, still from /:
  differ: char 1000383, line 210

So on this host, in 2026-09, the second trap is live: running from / is necessary and NOT sufficient. Anyone who reads the rule and takes only the 'run it from /' half away will produce a page diff of hundreds of lines they did not write, and — worse — will not know which lines are theirs.

Two practical notes for the next editor:
1. The fr-isolation bash guard requires a command to LEAD with 'cd <worktree>'. The render must run from /. Both hold at once with a subshell: 'cd <worktree> && W=$PWD && ( cd / && uv run --isolated ... "$W/docs/explainers/01-fr-goal.md" -o "$W/docs/explainers/01-fr-goal.html" )'. Absolute paths built from $W are what make the subshell work.
2. Render the verification probe to the scratchpad, not over the committed page. If the probe is NOT byte-identical you still have the committed page intact to diff against, which is the whole point of doing the check first.

After the real edit the page diff was exactly 5 added / 1 removed lines, all of them the new sentence and its rewrap — which is the outcome the byte-identity check buys you.
