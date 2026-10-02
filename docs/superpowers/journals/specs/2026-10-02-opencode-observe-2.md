# Journal: 2026-10-02-opencode-observe-2

<!-- fr:journal kind=discovery scope=spec id=input-batch-brief created=2026-10-02T19:06:33+00:00 input=true -->
### input-batch-brief · discovery · Operator brief — batch opencode-observe-2 (verbatim)

/fr-goal fr observes OpenCode sessions (run session, each child, what it returned); question answers, reviewer ids, cost and screenshot reads stop being the orchestrator's word

Batch `opencode-observe-2` of derio-net/super-fr: 6 issues, delivered as ONE pull request.

## super-fr#823: fr observes OpenCode sessions: the run's own session, each dispatched child, and what the child returned (one batch)
Umbrella, one batch: fr learns the OpenCode run session and each dispatched child session, then reads the reviewer's own output (#777 re-cut, #816 made-up reviewer), question answers (#809), file reads (#797) and cost (#636 discovery half) from opencode.db. Readers already exist (_opencode_wrote_since, usage/readers/opencode.py).
Note: Wave 9 `opencode-observe`, for the talk run. Merge after spec-review-loop (both touch spec-review).

## super-fr#797: visual evidence: recognise a file read in OpenCode's session store
read_file_since/shell_named_since read only Claude Code JSONL; on OpenCode every visual witness is unobserved, so checks 4–5 of the visual gate never observe a screenshot read. #817: PARTIAL in both take-10 runs.
Note: Proposed batch `opencode-evidence` (#816 #809 #797): read OpenCode's opencode.db the way the tests= gate already does.

## super-fr#809: OpenCode has a question tool, but the skill and parity.yaml say it doesn't; resolve silently records answered_by: agent
take 10 (#817, OpenCode + GitLab, fr 4.35.0): OpenCode 1.18.32 has a question tool, but fr-goal and parity.yaml say it does not; a record with no answered_by defaults to agent, and fr run gates prints "no operator answered it" into the PR body although one did.
Note: Proposed batch `opencode-evidence`; the default-to-agent must refuse instead.

## super-fr#816: review-phase record on OpenCode: a fabricated reviewer id and findings: none despite 6 reviewer findings
take 10 (#817, OpenCode + GitLab, fr 4.35.0) run B: review-phase recorded a made-up reviewer id and findings: none although three reviewer sessions raised 6 in-scope findings; unobserved on OpenCode, so fr accepted it.
Note: Proposed batch `opencode-evidence`: verify the reviewer id against dispatched child sessions in opencode.db.

## super-fr#848: fr run cost --recompute attributes a foreign Claude Code transcript to an OpenCode run
fr run cost --recompute attributes a foreign Claude Code transcript to an OpenCode run (take 11, fr arm), so a cost is shown that the run never incurred.
Note: Found by take 11 on 5.0.0. Same family as #637; belongs with the re-scoped #823.

## super-fr#561: parity.yaml: Hermes edit gate declared enforced while OpenCode is partial for the same shell-write gap
`parity.yaml` declares the edit gate `partial` on OpenCode (bash ungated) but `enforced` on Hermes, whose `pre_tool_call` covers only `write_file|patch` (`.hermes/config.snippet.yaml:13-14`); terminal writes reach only the bash guard (`partial`). Filed from the super-fr#564 review; the prose there already states the gap.
Note: Declaration-only fix (Hermes -> `partial` with a scope_note), plus `fr harness parity --check`'s observed side. Batch with super-fr#563.

## Why these belong together
Wave 11 of the post-talk closing order (2026-10-02). The one feature batch. fr learns the OpenCode run session and each child, so question answers, reviewer ids, cost and screenshot reads stop being the orchestrator's word. Draft PR #837 is the salvage; it must not touch the input.

## Delivery rules
- Work on branch `feat/batch-opencode-observe-2`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#823
  Closes derio-net/super-fr#797
  Closes derio-net/super-fr#809
  Closes derio-net/super-fr#816
  Closes derio-net/super-fr#848
  Closes derio-net/super-fr#561
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=decision scope=spec id=d-salvage created=2026-10-02T19:06:33+00:00 -->
### d-salvage · decision · Salvage: port #837, then finish

Round 1 Q1 → 'Port, then finish': new branch from main; #837's new modules/fixtures come over verbatim (observed.py, review_return.py, fixture builder, plugin session.ts), its run_cmd/telemetry hunks are re-applied by hand onto current main, the R5 input-coverage commit is dropped; phase 2 is reviewed afresh here, phase 3 built new.

<!-- fr:journal kind=decision scope=spec id=d-carry-837 created=2026-10-02T19:06:33+00:00 -->
### d-carry-837 · decision · Carry #837's operator decisions, drop coverage

Round 1 Q2 → 'Carry all, drop coverage': d-seam (one harness-neutral ObservedSession protocol), d-run-session (plugin shell.env exports FR_OPENCODE_SESSION_ID; fr walks parent_id to the top-level session), d-findings-block + d-finding-ids (reviewer ends with a findings block, brief-prescribed ids p<N>-r<k>, each a phase-N plan-journal finding with the same scope), d-answered-by-refuse (no default to agent; refuse on every harness), d-every-harness (return checks wherever the return is readable), d-parity-partial (OpenCode cells → partial + a verify: post-merge row re-running take 10 B; a follow-up flips to enforced) are this run's decisions unchanged. d-coverage-refuse is dropped with the input gates (#851).

<!-- fr:journal kind=decision scope=spec id=d-attribution created=2026-10-02T19:06:33+00:00 -->
### d-attribution · decision · #848: positive-evidence attribution only

Round 1 Q3 → 'Positive evidence only': --recompute (and fr archive's capture) use only sessions the cursor's attempts or the workspace bindings name, each with its own recorded harness; the ambient session is added only at a step's own resolve/advance capture. Nothing found → unavailable: no session found.

<!-- fr:journal kind=decision scope=spec id=d-hermes-partial created=2026-10-02T19:06:33+00:00 -->
### d-hermes-partial · decision · #561: Hermes edit gate → partial

Round 1 Q4 → 'Hermes → partial': the Hermes cell of fr-isolation-required becomes partial with a scope_note naming the write_file|patch scope and the terminal/execute_code gap.

<!-- fr:journal kind=decision scope=spec id=d-close-837 created=2026-10-02T19:06:33+00:00 -->
### d-close-837 · decision · Close #837 as superseded when this draft PR opens

Round 1 Q5 → 'Close as superseded': when this batch's draft PR opens, close #837 with a comment linking it; its branch and workspace stay until this one merges, then go with the close-out.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-10-02T19:15:52+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · §C threads `ambient` through candidates() only, but every caller reaches it through build_capture/capture/live_usage, and advance has no capture

check: codebase
target: spec
evidence: packages/fr/src/fr/usage/capture.py:181 (build_capture calls candidates), :219-233 (live_usage), :236-263 (capture); packages/fr/src/fr/run/cost.py:212 (the one direct caller); packages/fr/src/fr/archive.py:561; packages/fr/src/fr/commands/run_cmd.py:429-457, :5194
scope: the attribution design (R3, d-attribution) is this change's, and the threading it names does not match the code
The step paths never call `candidates` directly. `_capture_usage` calls `capture()`, which calls `build_capture`, which calls `candidates`. `live_usage` (the deliver render) and `fr archive` go through the same functions, so `capture`, `build_capture` and `live_usage` all need the keyword, and the spec should say what each defaults to. `run_cmd.py:433-446` is described as "`fr run resolve`/`advance`'s capture", but `advance` captures nothing. The real step-path call sites are `_capture_on_new_host` on resolve (:457) and deliver (:5194). Name the right functions and call sites so the plan cannot leave one path ambient by default.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-10-02T19:15:52+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · R10 drops two of the three `agent` defaults; the third one, and the validation after it, would refuse every resolve

check: codebase
target: spec
evidence: spec §F "No default (R10)" cites run_cmd.py:5289 and :4783 only; packages/fr/src/fr/commands/run_cmd.py:4904 (`_resolve_body(..., answered_by: str = "agent")`), :4920-4927 (`if answered_by not in ("operator", "agent")` → exit 2), :1198 (`_gate_provenance(claimed: str)`); packages/fr/src/fr/run/model.py:41 (docstring says resolve defaults to agent)
scope: R10 is this change's requirement; the design misses where the default and the check actually live
With the two cited defaults removed, `None` reaches `_resolve_body`. There it either picks up the third default at :4904, so nothing changes, or it fails the closed-set check at :4920 and every resolve is refused, gated or not. The design should say that `_resolve_body` takes `AnsweredBy | None`, that :4920 accepts `None`, and that the refusal fires only inside `_gate_provenance` on an unobserved gate (whose `claimed` becomes optional). The run/model.py:41 prose that states the old default should be updated too.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-10-02T19:15:52+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · R4 says every transcript gate uses the protocol, but §A leaves out `_phase_log_windows`, which still says OpenCode has no child-session reader

check: codebase
target: spec
evidence: packages/fr/src/fr/commands/run_cmd.py:2230-2260 (`_phase_log_windows`: `_this_session`, `witness_transcript`, `wrote_since`; :2247-2248 returns "fr has no child-session reader for opencode"); spec R4 and §A's list of gates
scope: R4 claims "every transcript gate"; this gate falls inside that claim and the change builds exactly the reader it lacks
The phase `tests=` witness reads the holder's transcript directly and hard-codes OpenCode and Hermes as unobservable. This branch adds a child-session reader, so after the change the gate's message is false and R4 is not met. Either route it through `observed_session(...).child(holder).wrote_windows` and add a Test Plan case, or scope it out explicitly in R4 and the Non-goals.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-10-02T19:15:52+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · §H's hedge that `fr.harness.observe` may learn a marker for run-session-identity does not fit the code: markers name hook scripts only

check: codebase
target: spec
evidence: packages/fr/src/fr/harness/observe.py:107-135 (a marker must name a shipped script under plugins/super-fr/hooks/, else HarnessError :129-133), :183-200 (observations are keyed by script); packages/fr-opencode-plugin/src/index.ts:20-23 (the claim handler, the same class of feature, deliberately has no marker)
scope: the new row is this change's; the spec leaves an unimplementable conditional in the design
`run-session-identity` is an interaction row with no hook script, and interaction rows are not observed. A `// super-fr-parity: run-session-identity` marker would make `fr harness parity --check` raise. State that the row is `kind: interaction`, that observe.py is unchanged, and that `session.ts` carries no marker, as claim.ts already does.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-10-02T19:15:52+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · Two of the six OpenCode cells §H 'moves to partial' are already partial, and §H points at the wrong Test Plan step

check: consistency
target: spec
evidence: packages/fr/src/fr/harness/parity.yaml:373-374 (dispatch-holder-identity opencode: partial), :434-435 (usage-capture opencode: partial); spec R13, §H "Parity rows", §H "Who flips OpenCode to `enforced`… Test Plan 13's last step"; Test Plan 13 vs 14
scope: internal to this spec's own design text
For `dispatch-holder-identity` and `usage-capture` only the `scope_note` changes, so say that rather than describe a state move. The follow-up issue's one job, flipping the cells to `enforced`, is the last step of Test Plan 14 (post-merge), not 13.

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-10-02T19:15:52+00:00 state=open review_scope=in -->
### s6 · finding [open] (reviewer: in scope) · Test Plan 8 expects `--recompute` to print `unavailable: no session found`, but nothing in the design produces that output

check: consistency
target: spec
evidence: packages/fr/src/fr/run/cost.py:196-218 (`recompute_entries` returns [] when there are no candidates); packages/fr/src/fr/usage/capture.py:207-208 (the NO_SESSION_FOUND placeholder exists only in build_capture); packages/fr/src/fr/commands/run_cmd.py:4175-4178 (`fr run cost` prints only "N read, M unavailable", never a reason); spec §C "yields the existing NO_SESSION_FOUND placeholder"
scope: R3 and Test Plan 8 are this change's; design and test disagree
§C calls the placeholder "existing" on the post-hoc path, but `recompute_entries` produces none, and even with one `fr run cost` would print counts, not the reason. The design should say that `recompute_entries` appends the placeholder when there are no candidates and that `fr run cost` prints unavailable reasons. Otherwise Test Plan 8 has to assert the count line.

<!-- fr:journal kind=finding scope=spec id=s7 created=2026-10-02T19:15:52+00:00 state=open review_scope=in -->
### s7 · finding [open] (reviewer: in scope) · Recording OpenCode sessions switches on the same-session comparison, and a child's session id will not match the recorded root

check: codebase
target: spec
evidence: packages/fr/src/fr/run/telemetry.py:341-351 (`dispatched_from_this_session` compares the recorded session with `current_session`); packages/fr/src/fr/commands/run_cmd.py:3233-3245 (`_dispatched_from_another_session` → `_already_running_refusal`), :2973 (`_open_dispatch` records a session only when the harness is claude-code); spec §B "Root session"
scope: this change is what starts filling `attempt.session` on OpenCode
Today an OpenCode attempt has `session=None`, so the comparison never fires. After the change, attempts carry the top-level id, while a command run from a child sees the child's id through `shell.env`, so a child's process reads the attempt as "dispatched from another session". §B lists `run_session` for "advance, capture, binding and window checks". Name `dispatched_from_this_session` as using `run_session` too, name the :2973 guard as the line that changes, and add a Test Plan case (a child's process on the root's attempt).

<!-- fr:journal kind=finding scope=spec id=s8 created=2026-10-02T19:15:52+00:00 state=open review_scope=in -->
### s8 · finding [open] (reviewer: in scope) · §E counts every non-executor child dispatched during review-phase as a reviewer owing a findings block, which looks too broad

check: consistency
target: spec
evidence: spec §E "Every child dispatched since the unit opened that is not a phase executor (by `agent_name`) counts as a reviewer of the unit, and each owes a block"; §H fixture "two `general` children (one returning a `findings` block, one not)"; plugins/super-fr/workflows/fr-goal.yaml:119-169 (review-phase also runs receiving-code-review, so the orchestrator may dispatch helpers to verify or fix findings)
scope: unsure — this may be #837's carried decision, but no recorded decision states it, and it makes an honest run refusable
An orchestrator that dispatches an investigation or fixer subagent other than `fr-phase-executor` while the review unit is open, an Explore agent for example, would be refused for that helper's missing block. Either scope "reviewer" to the dispatches the record names (`reviewer=` ids) or to the reviewer agent types, or state the rule as intended and say in fr-goal §6 that any other dispatch must wait until the unit resolves.

<!-- fr:journal kind=finding scope=spec id=s9 created=2026-10-02T19:15:52+00:00 state=open review_scope=in -->
### s9 · finding [open] (reviewer: in scope) · The fixture builder is described as 'ported', but a builder with three existing consumers is already on main

check: codebase
target: spec
evidence: tests/fixtures/usage/opencode/build.py:1-47 (exists on this branch); tests/fixtures/usage/NOTE.md:44-73 (opencode section and sha pin); consumers tests/unit/test_usage_readers.py:111, tests/unit/test_run_tests_log_opencode.py, tests/unit/test_run_opencode_reader.py; spec §H "Fixture"
scope: the fixture change is this spec's, and a verbatim port over a moved main can silently change existing assertions
Copying #837's builder verbatim (d-salvage) replaces a file main has since used. Adding a run tree also changes what `usage.readers.opencode.read` sums for the existing sessions, because it reads a session together with its children. Say whether the run tree is added beside the existing rows, keeping today's reader and tests-log assertions unchanged, and list those three test files as regression guards in the Test Plan.

<!-- fr:journal kind=finding scope=spec id=s10 created=2026-10-02T19:15:52+00:00 state=open review_scope=in -->
### s10 · finding [open] (reviewer: in scope) · The spec does not say whether the R5 holder fill runs before the visual witness's 'unclaimed' refusal

check: consistency
target: spec
evidence: packages/fr/src/fr/run/visual.py:468-482 (a holder unit with a matching dispatch and no claimed holder → "unclaimed" → VisualRefusedError :373-382); spec §D "Holder fill (R5)", "At resolve"
scope: both features are in this change; their interaction is unspecified
If the visual derive runs before the fill, a unit with exactly one matching child is refused as unclaimed even though R5 would have filled it. State that the fill runs first in resolve, and cover the case in Test Plan 5 or 6.

<!-- fr:journal kind=finding scope=spec id=s11 created=2026-10-02T19:15:52+00:00 state=open review_scope=in -->
### s11 · finding [open] (reviewer: in scope) · Decision d-close-837 (close #837 as superseded when the draft PR opens) is not in the spec

check: decisions
target: spec
evidence: journal d-close-837; the spec's opening paragraph says only that this run "supersedes draft PR #837"
scope: an operator decision about this run's delivery that the contract leaves out; tagged in because "the spec is the contract"
The spec should record that #837 is closed with a comment linking this draft PR when that PR opens, and that its branch and workspace stay until this PR merges and then go with the close-out. Without it, nothing after brainstorm carries the step.

<!-- fr:journal kind=finding scope=spec id=s12 created=2026-10-02T19:15:52+00:00 state=open review_scope=in -->
### s12 · finding [open] (reviewer: in scope) · The spec plans no update to the published explainer, which the explainers-currency rule requires for this change

check: codebase
target: spec
evidence: docs/explainers/01-fr-goal.md:361-373 (OpenCode session and claim behaviour, "records a session only when that harness owns the session variable it read"); .claude/rules/explainers-currency.md (minor bump or a changed skill pipeline triggers an update)
scope: this change alters OpenCode session recording, gate refusals and fr-goal skill prose, all of which the rule names as triggers
Add a Design or Scope line saying that 01-fr-goal.md and its rendered .html are updated, or that the PR body records why not.

<!-- fr:journal kind=finding scope=spec id=s13 created=2026-10-02T19:15:52+00:00 state=open review_scope=in -->
### s13 · finding [open] (reviewer: in scope) · The spec does not say where the review-phase brief's findings-block instruction lives, and the block's name collides with the existing `findings` evidence

check: consistency
target: spec
evidence: spec §E "The review-phase dispatch brief (and fr-goal §6) tells the reviewer…"; packages/fr/src/fr/commands/run_cmd.py:2737 (`_build_brief`); plugins/super-fr/workflows/fr-goal.yaml:144-152,169 and fr-goal-light.yaml:85 (review-phase already has a DERIVED `findings` evidence key)
scope: a design gap in this change's own surface
No file is named for the brief text, whether manifest, `_build_brief` or the skill alone, and both fr-goal.yaml and fr-goal-light.yaml run review-phase. The returned "`findings` block" also shares a name with the existing derived `findings` evidence (the closed-finding ids). Name the file that carries the instruction for both shapes, and give the block a name, or a sentence, that keeps the two apart.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-10-02T19:15:52+00:00 -->
### spec-review-1 · review · independent spec review: 13 findings

Findings raised: s1 (ambient threading and the capture call sites), s2 (answered_by default at :4904 and validation at :4920),
s3 (_phase_log_windows outside the protocol), s4 (observe markers are script-only), s5 (cells already partial; Test Plan 13 vs 14),
s6 (recompute placeholder and printed reason), s7 (same-session comparison with child ids), s8 (reviewer set too broad),
s9 (fixture builder already on main), s10 (holder fill vs visual order), s11 (d-close-837 missing), s12 (explainer currency),
s13 (location of the brief instruction; findings-name collision). Decisions d-salvage, d-carry-837, d-attribution and d-hermes-partial are honoured.
Every R1–R14 has a matrix row citing it (docs/acceptance/matrix.yaml:5600-5704). No spec dependence on the #851-removed blocks.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-10-02T19:15:52+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: §C threads `ambient` through candidates() only, but every caller reaches it through build_capture/capture/live_usage, and advance has no capture

§C: `ambient` is keyword-only with no default on candidates/build_capture/capture/live_usage; step call sites (_capture_usage/_capture_on_new_host :429-457, deliver :5194, pr_body live render) pass True; recompute_entries and archive :561 pass False; 'advance captures nothing' stated.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-10-02T19:15:52+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: R10 drops two of the three `agent` defaults; the third one, and the validation after it, would refuse every resolve

§F: all three defaults removed incl. _resolve_body :4904 → AnsweredBy | None; :4920 accepts None, still refuses a third value; _gate_provenance claimed optional, refusal only on an unobserved gate; run/model.py:41 docstring updated.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-10-02T19:15:52+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: R4 says every transcript gate uses the protocol, but §A leaves out `_phase_log_windows`, which still says OpenCode has no child-session reader

R4 names the phase tests= witness; §A routes _phase_log_windows (:2230) through observed_session(...).child(holder).wrote_windows; Test Plan 5a added.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-10-02T19:15:52+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: §H's hedge that `fr.harness.observe` may learn a marker for run-session-identity does not fit the code: markers name hook scripts only

§H: run-session-identity is kind: interaction, observe.py unchanged, session.ts carries no parity marker (as claim.ts).

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-10-02T19:15:52+00:00 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: Two of the six OpenCode cells §H 'moves to partial' are already partial, and §H points at the wrong Test Plan step

R13 and §H: four cells move to partial; dispatch-holder-identity and usage-capture change scope_note only; follow-up points at Test Plan 14.

<!-- fr:journal kind=finding scope=spec id=s6-resolved created=2026-10-02T19:15:52+00:00 state=fixed resolves=s6 -->
### s6-resolved · finding [fixed] · resolves s6: Test Plan 8 expects `--recompute` to print `unavailable: no session found`, but nothing in the design produces that output

§C: recompute_entries appends the NO_SESSION_FOUND placeholder with no candidates and fr run cost prints unavailable reasons under its count line.

<!-- fr:journal kind=finding scope=spec id=s7-resolved created=2026-10-02T19:15:52+00:00 state=fixed resolves=s7 -->
### s7-resolved · finding [fixed] · resolves s7: Recording OpenCode sessions switches on the same-session comparison, and a child's session id will not match the recorded root

§B: _open_dispatch :2973 guard records through run_session on any harness owning its key; dispatched_from_this_session uses run_session; Test Plan 7 adds a child's command on the root's attempt.

<!-- fr:journal kind=finding scope=spec id=s8-resolved created=2026-10-02T19:15:52+00:00 state=fixed resolves=s8 -->
### s8-resolved · finding [fixed] · resolves s8: §E counts every non-executor child dispatched during review-phase as a reviewer owing a findings block, which looks too broad

§E: a reviewer is a child named in `reviewer` evidence or whose return carries a review-findings fence; helpers owe nothing; residual gap stated; Test Plan 3 adds an unnamed helper that resolves.

<!-- fr:journal kind=finding scope=spec id=s9-resolved created=2026-10-02T19:15:52+00:00 state=fixed resolves=s9 -->
### s9-resolved · finding [fixed] · resolves s9: The fixture builder is described as 'ported', but a builder with three existing consumers is already on main

§H: the run tree is added beside main's existing builder rows under new session ids; the three existing consumers listed as regression guards in Test Plan 8.

<!-- fr:journal kind=finding scope=spec id=s10-resolved created=2026-10-02T19:15:52+00:00 state=fixed resolves=s10 -->
### s10-resolved · finding [fixed] · resolves s10: The spec does not say whether the R5 holder fill runs before the visual witness's 'unclaimed' refusal

§D: holder fill runs first in resolve, before the visual 'unclaimed' refusal; Test Plan 5 covers it.

<!-- fr:journal kind=finding scope=spec id=s11-resolved created=2026-10-02T19:15:52+00:00 state=fixed resolves=s11 -->
### s11-resolved · finding [fixed] · resolves s11: Decision d-close-837 (close #837 as superseded when the draft PR opens) is not in the spec

New §J records d-close-837: #837 closed with a link when the draft opened; branch/workspace go with the close-out.

<!-- fr:journal kind=finding scope=spec id=s12-resolved created=2026-10-02T19:15:52+00:00 state=fixed resolves=s12 -->
### s12-resolved · finding [fixed] · resolves s12: The spec plans no update to the published explainer, which the explainers-currency rule requires for this change

§J: docs/explainers/01-fr-goal.md updated and its .html regenerated in this PR.

<!-- fr:journal kind=finding scope=spec id=s13-resolved created=2026-10-02T19:15:52+00:00 state=fixed resolves=s13 -->
### s13-resolved · finding [fixed] · resolves s13: The spec does not say where the review-phase brief's findings-block instruction lives, and the block's name collides with the existing `findings` evidence

§E: _build_brief adds a review_findings key to every review-phase brief (both shapes); fr-goal §6 passes it verbatim; fence renamed `review-findings`, distinct from the derived `findings` evidence; R7 updated.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-02-opencode-observe-2-p2 created=2026-10-02T19:18:02+00:00 -->
### phase-split-2026-10-02-opencode-observe-2-p2 · decision · ask: #816 — reviewer identity and the returned review-findings check is its own reviewable ask

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-02-opencode-observe-2-p3 created=2026-10-02T19:18:03+00:00 -->
### phase-split-2026-10-02-opencode-observe-2-p3 · decision · ask: #809/#797/#561 — operator answers, visual reads, parity and prose

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-02-opencode-observe-2-p1 created=2026-10-02T19:18:04+00:00 -->
### tier-2026-10-02-opencode-observe-2-p1 · decision · hard: changes the session seam and capture attribution every transcript gate and every capture relies on

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-02-opencode-observe-2-p2 created=2026-10-02T19:18:05+00:00 -->
### tier-2026-10-02-opencode-observe-2-p2 · decision · hard: changes the review-phase resolve gate (reviewer verification, holder-fill ordering, findings refusal)
