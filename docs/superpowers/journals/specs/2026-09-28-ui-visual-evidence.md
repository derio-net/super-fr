# Journal: 2026-09-28-ui-visual-evidence

<!-- fr:journal kind=discovery scope=spec id=input-batch-prompt created=2026-09-28T19:15:38+00:00 input=true -->
### input-batch-prompt · discovery · Operator input: fr-goal batch prompt (ui-evidence-2)

UI evidence is visual: screenshots actually opened, and every named interaction exercised

Batch `ui-evidence-2` of derio-net/super-fr: 1 issues, delivered as ONE pull request.

## super-fr#779: Browser check isn't visual: UI evidence is a script's pass/fail; no screenshot is ever opened and named interactions go unexercised
Take 9: UI evidence was a Playwright script's pass/fail; no screenshot was ever opened and the named interactions (−, slider drag, the 20 cap, range labels) were never exercised. The scorer found four defects visible in one screenshot or drag; the plain comparison arm opened 6 screenshots.
Note: Operator-prioritised. Feature (fr-goal), batch `ui-evidence`: for a user-visible requirement, evidence names the screenshots actually opened (observable in the transcript) and each named control used at its limits.

## Why these belong together
Retry of the batch cancelled on 2026-09-28 at its question gate (#783): dispatch only after question-order (#783) merges. Wave 6, operator-prioritised. Take 9's browser check was a script's pass/fail: no screenshot opened, -, slider drag, the 20 cap and the range labels never tried, and four defects visible in one screenshot shipped. For a user-visible requirement, evidence at implement/review/deliver names the screenshots the agent opened (observable in the transcript) and the controls it used at their limits. Edits fr-execute and fr-goal prose and possibly an evidence reader; rebase against requirements-gate if both touch fr-goal SKILL.md.

## Delivery rules
- Work on branch `feat/batch-ui-evidence-2`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#779
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=discovery scope=spec id=input-issue-779 created=2026-09-28T19:15:38+00:00 input=true -->
### input-issue-779 · discovery · Operator input: super-fr#779 title and body

Browser check isn't visual: UI evidence is a script's pass/fail; no screenshot is ever opened and named interactions go unexercised

## What happened

The brief of the super-fr-3 feature-C recording asks: "Before delivering, the developer has checked basket mode in a browser (accepted, not accepted, staff check, back to single article) against the single-article view." In take 9 (fr 4.29.2), the executor wrote a Playwright script (`src/test/browser/basket.cjs`, run through `docker exec` because the devcontainer doesn't publish the demo port) and ran it 4 times; the orchestrator ran it again after the review fixes, and the closeout once more. **No screenshot was ever opened**: the only attempt to read one used the wrong directory and wasn't retried. The script never exercised −, the slider drag, the 20 cap, the range labels or any styling.

The scorer's browser check then found: the card-click side effect, a reading outside the ranges not drawn at all, the chart torn down on every slider move, the stale legend. All visible in one screenshot or one drag.

The plain comparison arm, given the same brief, opened 6 screenshots before delivering (take 8).

## Expected

When a requirement or acceptance row is user-visible UI, its evidence at `implement-phase` / `review-phase` / `deliver` includes:

- screenshots the agent actually opened (an image read of the file, observable in the transcript), for each state the requirement names, and
- the interactions the requirements name (each control used at least once, including its limits),

rather than a script's pass/fail alone. fr-execute / fr-goal say so in the browser-check step.

<!-- fr:journal kind=discovery scope=spec id=input-script-preference created=2026-09-28T19:15:38+00:00 input=true -->
### input-script-preference · discovery · Operator input: mid-brainstorm addendum (capture script preferred)

add that, if a script can be written to reliably retrieve the screenshots mechanically instead of driving via the agent, it should be preferred. That way the token cost is only paid once and each rerun only costs a script invocation (and viewing the images of course).

<!-- fr:journal kind=decision scope=spec id=d1-visual-row-flag created=2026-09-28T19:15:38+00:00 -->
### d1-visual-row-flag · decision · A UI requirement is marked on its acceptance row

Q1 answer: flag on the acceptance row (`visual`, beside `verify: post-merge`). Plan phases already link rows, so fr knows which phases and delivery owe visual evidence. Not a Requirements-grammar tag, not agent judgement.

<!-- fr:journal kind=decision scope=spec id=d2-transcript-verified created=2026-09-28T19:15:38+00:00 -->
### d2-transcript-verified · decision · fr verifies from the transcript that screenshots were opened

Q2 answer: evidence names the screenshot files; fr refuses unless each was opened with an image read since the unit opened, in the transcript of the agent that owes it (this session or a subagent it dispatched). Unreadable transcript -> recorded unobserved, like tests=.

<!-- fr:journal kind=decision scope=spec id=d3-reviewer-drives created=2026-09-28T19:15:38+00:00 -->
### d3-reviewer-drives · decision · The review-phase reviewer drives the UI itself

Q3 answer: the dispatched reviewer opens its own screenshots and tries the named controls at their limits itself; reading the executor's screenshots is not enough.

<!-- fr:journal kind=decision scope=spec id=d4-interactions-on-row created=2026-09-28T19:15:38+00:00 -->
### d4-interactions-on-row · decision · Interactions are named on the row and covered in the record

Q4 answer: the visual row lists its controls and limits; the evidence record maps each to a screenshot taken after using it; fr refuses a name with no screenshot. Coverage only, not image content.

<!-- fr:journal kind=decision scope=spec id=d5-fresh-at-deliver created=2026-09-28T19:15:38+00:00 -->
### d5-fresh-at-deliver · decision · deliver takes fresh screenshots

Q5 answer: review fixes land after phase screenshots, so the orchestrator opens new ones of the delivered build, as it re-runs the full suite itself.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-28T19:22:23+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · R5 and check 5 add a "committed, tracked on the branch" refusal the input never asked for

check: traceability
evidence: input-script-preference "if a script can be written to reliably retrieve the screenshots mechanically instead of driving via the agent, it should be preferred."; spec R5 ("a committed capture script is preferred"), §C check 5 ("the file is tracked on the branch"), §D ("commit it on the branch")
scope: this change makes the requirement say more than its quote and adds a gate refusal to it, so it is in scope
resolution: reinterpreted
The input asks for a script to be *preferred* when it can reliably retrieve the screenshots. It never says the script must be committed to the product repo, and it never says fr should refuse a record whose script is untracked. R5's "committed" and check 5's tracked-on-branch refusal add a condition, and that condition ships a test script in every UI PR. Resolve this `unconfirmed` with a note on what gets built, or drop "committed/tracked" so that check 5 only verifies the stage re-ran the named script.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-28T19:22:23+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · R4's text says less than the decisions it cites (d3 reviewer's own screenshots, d5 fresh at deliver)

check: traceability
evidence: spec R4 "Visual evidence is owed at implement-phase, review-phase and deliver." sourced from decision d3-reviewer-drives and d5-fresh-at-deliver; matrix row visual-evidence-reviewer-own-eyes (docs/acceptance/matrix.yaml:5155) cites only R4
scope: the requirement row is part of this spec and is narrower than its own cited sources
resolution: reinterpreted
R4 cites d3 and d5 but its text states neither. It does not say that the review-phase reviewer must drive the UI and open its own screenshots, and it does not say that deliver takes fresh screenshots of the delivered build. §C check 4 (the reviewer's transcript, "never the executor's") and check 3 (freshness) enforce behaviour that no requirement text states. The matrix row "reviewer-own-eyes" also points at an R4 that never mentions the reviewer. Carry the two decisions' own content into the requirement text. Do not reshape it to match §C.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-28T19:22:23+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · The freshness refusal (check 3) at implement-phase goes beyond d5, which asked only for fresh screenshots at deliver

check: traceability
evidence: spec §C check 3 ("modified at or after the unit opened" for every owing step); decision d5-fresh-at-deliver (deliver only); d2-transcript-verified (constrains when the image was OPENED, not when it was taken)
scope: a new user-visible refusal introduced by this design; unsure whether d2/d3 imply it, so tagged in
resolution: invented
d5 makes freshness a deliver-time rule, because review fixes land after the phase screenshots. d3 arguably implies fresh screenshots at review-phase ("opens its own screenshots"). Nothing in the input or the decisions asks for an mtime freshness refusal at implement-phase: d2 constrains only the *opening* to fall after the unit opened. Resolve this `unconfirmed` with a note, or limit check 3 to deliver and review-phase.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-09-28T19:22:23+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · The spec calls OpenCode's transcript unreadable, but fr already reads opencode.db for tests=; the parity states are also outside the vocabulary

check: codebase
evidence: spec §C "Unobservable (no readable transcript: OpenCode and Hermes today …)", §E, §F "Claude Code is verified; OpenCode and Hermes are recorded as unobserved (partial)"; packages/fr/src/fr/run/telemetry.py:1002 `_opencode_wrote_since`; packages/fr/src/fr/harness/parity.yaml:279-298 (deliver-tests-provenance: opencode `state: enforced`, with per-mode entries); parity states used in the file are enforced|partial|absent|unsupported|advisory
scope: a factual premise of this spec's own gate and parity row is wrong
Evidence gates can already read OpenCode's session store. The accurate statement is that no OpenCode reader recognises an *image read* yet. If that is to stay a non-goal, say so in those terms, and consider a follow-up. "verified" and "unobserved" are not parity states. Write the new `visual-evidence` row with the file's own vocabulary (e.g. claude-code `enforced` with per-mode entries as in deliver-tests-provenance; opencode `partial` or `absent`; hermes `unsupported`).

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-09-28T19:22:23+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · No image-read predicate exists and the spec never names or specifies the new transcript reader

check: codebase
evidence: packages/fr/src/fr/run/telemetry.py:243 `tool_use_ids` (reads only the orchestrator stream), :281 `attribute_dispatches` (maps subagent files, never scans their tool calls), :788 `_names` / :799 `orchestrator_wrote_since` (Bash-only); spec §A background "The same machinery can answer …", §C check 4
scope: check 4 is the core of this change and has no defined implementation seam
The telemetry module has no function that finds a file-read tool_use of a given path, and none that scans a *subagent* transcript's own tool calls. Check 4 (and check 5's "shell call naming it" in a subagent transcript) needs both. Name the new predicate(s) in the spec: what counts as an image read (tool name and input key, compared by resolved path), the time window, and None versus False semantics as in `subagent_dispatch_since`. That way the plan and the Test Plan's fixtures have one thing to target.

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-09-28T19:22:23+00:00 state=open review_scope=in -->
### s6 · finding [open] (reviewer: in scope) · Screenshot location is undefined for devcontainer mode, where fr run resolves on the host (the take-9 setup)

check: consistency
evidence: spec §B example paths `/tmp/shots/*.png`; §C check 3 (fr stats and hashes the file); Non-goals ("capture script can run inside the container through `fr isolation exec` and write into the bind-mounted worktree"); packages/fr/src/fr/isolation/where.py:119 `require_harness_host` (fr run refuses inside a devcontainer workspace)
scope: the design's own gate cannot pass in the default isolation mode without a location rule
In devcontainer mode a capture script run inside the container writes to the container's /tmp. The host-side `fr run resolve` then cannot stat or hash those files, and the host-side agent cannot open them. The Non-goals workaround, writing into the bind-mounted worktree, leaves untracked PNGs in the repo that can be committed, the same class as gh#638. The spec should say where shots must live: a path both the host resolve and the reading agent see, gitignored or outside the repo. It should also say whether check 3 refuses a shot path inside the worktree that is not ignored.

<!-- fr:journal kind=finding scope=spec id=s7 created=2026-09-28T19:22:23+00:00 state=open review_scope=in -->
### s7 · finding [open] (reviewer: in scope) · Two line citations in §A and §B are stale

check: codebase
evidence: spec §A cites `packages/fr/src/fr/record/model.py:137` for AcceptanceItem (actual :142); §B cites `:196` for StepRecord (actual :188)
scope: citations in this spec; trivial to fix
Update both line numbers. Every other citation checked resolves (see verified).

<!-- fr:journal kind=finding scope=spec id=s8 created=2026-09-28T19:22:23+00:00 state=open review_scope=in -->
### s8 · finding [open] (reviewer: in scope) · The Test Plan omits several design checks and contradicts the Visual validation rule

check: consistency
evidence: spec §A ("At least one [of states, interactions] is non-empty") vs Test Plan 1 ("empty lists refused"); §C check 3 (non-empty), check 4 witness selection (inline implement-phase → orchestrator stream; deliver → orchestrator stream), check 5 (script tracked on the branch); §A "`fr acceptance set-status` leaves the field alone"
scope: the Test Plan must cover what the design promises
Test 1 should read "both lists empty refused", because one empty list is valid per §A. Nothing tests the following: an empty (zero-byte) shot, an untracked named script, witness selection for an inline implement-phase and for deliver, or `set-status` preserving `visual`. Add them, or remove the corresponding design promises.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-28T19:22:23+00:00 -->
### spec-review · review · independent spec review: 8 findings

input-coverage:
```input-coverage
| span | coverage |
|---|---|
| "UI evidence is visual: screenshots actually opened, and every named interaction exercised" | R2, R3 |
| "Batch `ui-evidence-2` of derio-net/super-fr: 1 issues, delivered as ONE pull request." | context |
| "## super-fr#779: Browser check isn't visual: UI evidence is a script's pass/fail; no screenshot is ever opened and named interactions go unexercised" | context |
| "Take 9: UI evidence was a Playwright script's pass/fail; no screenshot was ever opened and the named interactions (−, slider drag, the 20 cap, range labels) were never exercised. The scorer found four defects visible in one screenshot or drag; the plain comparison arm opened 6 screenshots." | context |
| "Note: Operator-prioritised. Feature (fr-goal), batch `ui-evidence`:" | context |
| "for a user-visible requirement, evidence names the screenshots actually opened (observable in the transcript) and each named control used at its limits." | R1, R2, R3 |
| "## Why these belong together" | context |
| "Retry of the batch cancelled on 2026-09-28 at its question gate (#783): dispatch only after question-order (#783) merges. Wave 6, operator-prioritised. Take 9's browser check was a script's pass/fail: no screenshot opened, -, slider drag, the 20 cap and the range labels never tried, and four defects visible in one screenshot shipped." | context |
| "For a user-visible requirement, evidence at implement/review/deliver names the screenshots the agent opened (observable in the transcript) and the controls it used at their limits." | R1, R2, R3, R4 |
| "Edits fr-execute and fr-goal prose and possibly an evidence reader;" | R6, R2 |
| "rebase against requirements-gate if both touch fr-goal SKILL.md." | context |
| "## Delivery rules" | context |
| "- Work on branch `feat/batch-ui-evidence-2`." | context |
| "- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:" | context |
| "Closes derio-net/super-fr#779" | context |
| "- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels." | context |
| "Browser check isn't visual: UI evidence is a script's pass/fail; no screenshot is ever opened and named interactions go unexercised" | context |
| "## What happened" | context |
| "The brief of the super-fr-3 feature-C recording asks: "Before delivering, the developer has checked basket mode in a browser (accepted, not accepted, staff check, back to single article) against the single-article view." In take 9 (fr 4.29.2), the executor wrote a Playwright script (`src/test/browser/basket.cjs`, run through `docker exec` because the devcontainer doesn't publish the demo port) and ran it 4 times; the orchestrator ran it again after the review fixes, and the closeout once more. **No screenshot was ever opened**: the only attempt to read one used the wrong directory and wasn't retried. The script never exercised −, the slider drag, the 20 cap, the range labels or any styling." | context |
| "The scorer's browser check then found: the card-click side effect, a reading outside the ranges not drawn at all, the chart torn down on every slider move, the stale legend. All visible in one screenshot or one drag." | context |
| "The plain comparison arm, given the same brief, opened 6 screenshots before delivering (take 8)." | context |
| "## Expected" | context |
| "When a requirement or acceptance row is user-visible UI, its evidence at `implement-phase` / `review-phase` / `deliver` includes:" | R1, R4 |
| "- screenshots the agent actually opened (an image read of the file, observable in the transcript), for each state the requirement names, and" | R2 |
| "- the interactions the requirements name (each control used at least once, including its limits)," | R3 |
| "rather than a script's pass/fail alone." | R2 |
| "fr-execute / fr-goal say so in the browser-check step." | R6 |
| "add that, if a script can be written to reliably retrieve the screenshots mechanically instead of driving via the agent, it should be preferred." | R5 |
| "That way the token cost is only paid once and each rerun only costs a script invocation (and viewing the images of course)." | R5 |
```
decisions: d1–d5 are each reflected in the Decisions table and Design. d1 → §A. d2 → §C checks 4 and 5 plus the unobserved contract. d3 → §C check 4 review-phase witness and §E. d4 → §A/§B `shows` coverage (coverage only, per Non-goals). d5 → §C check 3 and §E §8. No spec section contradicts a decision. s2 and s3 cover where the requirement text or the design diverges from them.
verified:
- packages/fr/src/fr/acceptance/model.py:55 — `Row` (with `verify: Literal["post-merge"]` at :71)
- packages/fr/src/fr/record/model.py:142 — `AcceptanceItem` (spec says :137; see s7)
- packages/fr/src/fr/record/model.py:188 — `StepRecord` (spec says :196; see s7)
- packages/fr/src/fr/record/model.py:242 — `_SECTION_FIELDS`, with an `evidence` group
- packages/fr/src/fr/record/model.py:51 — RECORD_SCHEMA_VERSION = 3 (record 3 → 4 is the right hop)
- packages/fr/src/fr/workflow/artifacts.py:95 — ALWAYS_RECORD_SECTIONS includes `evidence` (so every step may carry it)
- packages/fr/src/fr/commands/run_cmd.py:1389 — `_VERIFIABLE_EVIDENCE`; :1404 — `_DERIVED_EVIDENCE` (within the cited 1386-1406)
- packages/fr/src/fr/commands/run_cmd.py:756 — `_check_step_drift`
- packages/fr/src/fr/commands/run_cmd.py:233 — `_note_unobserved`
- packages/fr/src/fr/commands/run_cmd.py:2133 — `_verify_tests_log`; :2155-2167 the gh#638 `<run>.records/` refusal; :2183 the one-second slack
- packages/fr/src/fr/run/telemetry.py:799 — `orchestrator_wrote_since`
- packages/fr/src/fr/run/telemetry.py:595 — `subagent_dispatch_since` (reviewer=<agent-id>)
- packages/fr/src/fr/run/telemetry.py:281 — `attribute_dispatches`
- packages/fr/src/fr/run/model.py:64 — `Attempt.agent` (the claimed holder)
- packages/fr/src/fr/types.py:111 — `PhaseHeader.acceptance`
- packages/fr/src/fr/requirements.py:331 — `rows_citing`
- packages/fr/src/fr/requirements.py:95 — `## Deferred from input` heading (optional; the spec has none, and none is needed)
- packages/fr/src/fr/artifacts/registry.py:393-397 — matrix current_version 2; :425-435 — record current_version 3
- packages/fr/src/fr/artifacts/matrix_verify.py — the template for matrix_visual exists
- packages/fr/src/fr/workflow/resolve.py:24-43 — the wheel copy resolves before the marketplace clone (backs §G's closing claim)
- plugins/super-fr/workflows/fr-goal.yaml:122,128,187 — implement-phase / review-phase / deliver; :175 and :205 the current evidence lists
- packages/fr/src/fr/harness/parity.yaml:261 — `deliver-tests-provenance` row exists
- packages/fr/src/fr/commands/acceptance_cmd.py:362,387,508 — `set-status` and `add` carry `--verify` (the pattern for `--visual-*`)
- plugins/super-fr/skills/fr-goal/SKILL.md:47,75,90,99 — §1, §5, §6, §8 exist as the spec names them
- plugins/super-fr/skills/fr-brainstorming/SKILL.md:100 — §3 Acceptance rows
- plugins/super-fr/skills/fr-execute/SKILL.md, plugins/super-fr/skills/fr-plan/SKILL.md, plugins/super-fr/agents/fr-phase-executor.md — exist
- plugins/super-fr — no "browser" or "screenshot" anywhere (confirms the Background claim)
- docs/explainers/01-fr-goal.md — names evidence gates (28 matches), so §H's regeneration is owed
- docs/acceptance/matrix.yaml:5131-5198 — six visual-evidence-* rows cite R1–R6; the live-run row is `verify: post-merge`

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-28T19:22:23+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: R5 and check 5 add a "committed, tracked on the branch" refusal the input never asked for

Removed the committed/tracked condition: R5 now reads 'a capture script is preferred', §D leaves committing to the implementer, and check 5 verifies only that the named script exists and that the stage re-ran it. Matrix row visual-evidence-capture-script text aligned.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-28T19:22:23+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: R4's text says less than the decisions it cites (d3 reviewer's own screenshots, d5 fresh at deliver)

R4's text now states d3 (the review-phase reviewer drives the UI and opens its own screenshots) and d5 (fresh screenshots of the delivered branch at deliver).

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-28T19:22:23+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: The freshness refusal (check 3) at implement-phase goes beyond d5, which asked only for fresh screenshots at deliver

Check 3's freshness rule is limited to review-phase (d3) and deliver (d5); at implement-phase only the opening must fall in the unit (d2), and the Test Plan pins a stale implement-phase shot as accepted.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-09-28T19:22:23+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: The spec calls OpenCode's transcript unreadable, but fr already reads opencode.db for tests=; the parity states are also outside the vocabulary

§C now says OpenCode's store is read (`_opencode_wrote_since`, telemetry.py:1002) but has no file-read detection; §F uses the file's vocabulary: claude-code enforced with per-mode entries, opencode/hermes advisory, codex/copilot-cli unsupported; non-goal names the OpenCode follow-up.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-09-28T19:22:23+00:00 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: No image-read predicate exists and the spec never names or specifies the new transcript reader

§C names the predicates: `read_file_since` and `shell_named_since` in fr.run.telemetry (three-valued, like subagent_dispatch_since), taking a transcript file, plus `witness_transcript` picking orchestrator vs holder/reviewer Dispatch.transcript; Read aliases via fr.usage.classify.

<!-- fr:journal kind=finding scope=spec id=s6-resolved created=2026-09-28T19:22:23+00:00 state=fixed resolves=s6 -->
### s6-resolved · finding [fixed] · resolves s6: Screenshot location is undefined for devcontainer mode, where fr run resolves on the host (the take-9 setup)

§B adds 'Where shots live': host-visible path; inside the repo it must be git-ignored; `<run>.records/` refused; devcontainer captures write to a git-ignored dir of the bind-mounted worktree. Check 3 enforces it; Test Plan covers the non-ignored refusal.

<!-- fr:journal kind=finding scope=spec id=s7-resolved created=2026-09-28T19:22:23+00:00 state=fixed resolves=s7 -->
### s7-resolved · finding [fixed] · resolves s7: Two line citations in §A and §B are stale

Citations corrected to record/model.py:142 (AcceptanceItem) and :188 (StepRecord).

<!-- fr:journal kind=finding scope=spec id=s8-resolved created=2026-09-28T19:22:23+00:00 state=fixed resolves=s8 -->
### s8-resolved · finding [fixed] · resolves s8: The Test Plan omits several design checks and contradicts the Visual validation rule

Test Plan 1 reads 'both lists empty refused, one empty accepted' and adds set-status preserving visual; 3 adds zero-byte and non-ignored shots and stale-at-implement accepted; 4 adds witness selection for inline implement-phase, dispatched implement-phase, review-phase and deliver, aliased read tool, and a missing script.
