<!-- fr:journal-schema=4 -->
# Journal: 2026-11-28-alacarte-settings

<!-- fr:journal kind=decision scope=plan id=p1-schema-line-at-current created=2026-11-28T09:48:11+00:00 phase=1 -->
### p1-schema-line-at-current · decision · fr settings init renders the schema line at the current schema (3) (phase 1)

`#schema: 1` uncommented with every other line would name `workflows` and `forge.pr_sections` under schema 1, which R1 refuses. The init file's schema line now shows SCHEMA_VERSION, so a file uncommented whole still parses; the model default stays 1 (a file naming no schema-3 key may stay at 1).

<!-- fr:journal kind=decision scope=plan id=p1-push-checks-before-ask created=2026-11-28T09:48:11+00:00 phase=1 -->
### p1-push-checks-before-ask · decision · fr push runs the stealth content scan and the subject check before the ask (phase 1)

Under stealth every code push now asks. Asking the operator to approve a push fr then refuses (an fr path in the range, a subject off the template) wastes the approval, so `refuse_stealth_content` and `check_subjects` moved before `require_approval`; the squash and the pusher still run after it, and the pusher scans again.

<!-- fr:journal kind=decision scope=plan id=p1-driven-triage-message created=2026-11-28T09:48:11+00:00 phase=1 -->
### p1-driven-triage-message · decision · one push-ask-with-driven-triage rule, its message chosen by placement (phase 1)

A settings-check rule's message may now be a callable of the settings (`fr.settings.check.Message`), so the stealth wording (stealth forces git.push ask, remove the driven .fr/triage.yaml keys) keeps the rule's single id. Under stealth a tracking configuration space not created yet holds no triage file, so the rule reads nothing then instead of refusing every stealth check.

<!-- fr:journal kind=discovery scope=plan id=p1-stealth-walks-need-approval created=2026-11-28T09:48:11+00:00 phase=1 -->
### p1-stealth-walks-need-approval · discovery · forcing git.push/git.pr ask under stealth broke the stealth placement walks (phase 1)

tests/scenarios/placement-stealth.sh and _placement_walk.sh pushed code with `fr push` and delivered a PR the record emitted. Both now refuse under stealth (R7, R9). A scenario has no operator or harness, so `tests/scenarios/_ask_approve.sh` approves a request the way a session does: the request's own `fr journal add` line plus an answer in a Claude Code transcript built from the captured AskUserQuestion exchange (FR_TRANSCRIPT_ROOT). The walk's local-path origin names no forge repository, so `fr pr create` cannot reach the forge there; the walk asserts deliver's refusal and then records the PR on the cursor exactly as `fr pr create` does after the forge answers. The stealth content unit tests take the ask as approved (`approved_asks` in stealth_repo.py); the approval itself stays pinned in test_git_policy_push.py and test_settings_stealth.py.

<!-- fr:journal kind=discovery scope=plan id=p1-fast-tier-not-finished created=2026-11-28T09:48:11+00:00 phase=1 -->
### p1-fast-tier-not-finished · discovery · the fast tier was stopped at 2% (no failure yet) on a host at load ~50 (phase 1)

`uv run pytest --fr-scope origin/main -n 2 -q --no-cov` selected most of the suite (this change reaches fr.settings, run_cmd and the PR body) and ran about 1% per four minutes on a host other sessions held at load ~50: hours. It was stopped with no failure or error in its output. What ran in full instead, all green: every tests/unit/test_settings_*, test_workflow_available, test_workflow_check, test_pr_body_* (sections, cost, settle), test_deliver_pr_body, the stealth/placement/config/push/pr/git_policy units (192 + 472 tests), test_skill_stealth_push and the mirror tripwires, and the scenarios alacarte-settings, placement-stealth and placement-quiet on the installed candidate. ruff format, ruff check and mypy are clean. CI (`tests: ci`) is the suite evidence.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-28T09:48:11+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

discover_names was moved out of workflow_cmd.py as the green step itself; refuse_disabled is the one check every caller imports, nothing duplicated was left

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-28T09:48:11+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

required_sections is the one derivation render and deliver share; the render skips each off section in place, leaving nothing to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-28T09:48:11+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

the forced git keys live in one STEALTH_GIT mapping beside QUIET_FORGE and the render reads it; the push reorder was the cleanup

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-11-28T09:48:11+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

skill prose, mirrors, docs and a scenario; no code to clean

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-28T10:11:19+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · The stealth walk hand-records the PR on the cursor, so the stealth `fr pr create` ask is never walked (phase 1)

tests/scenarios/_placement_walk.sh wrote the PR URL onto the cursor without ever running `fr pr create`, so R7's forced `git.pr` ask had unit coverage only. See p1-review.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-28T10:11:19+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · R9 "each push asks for its own approval" has no test (phase 1)

Nothing approved a push, pushed, and then showed that the next code push asks again under a new request. See p1-review.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-28T10:11:19+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · The stealth-forge-explicit message does not name the fix (phase 1)

settings/check.py said stealth refuses a contrary value, but not what to do about it. See p1-review.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-28T10:11:19+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · forge.pr_sections and workflows.disabled are missing from the settings section of docs/explainers/01-fr-goal.md (phase 1)

Only `fr settings init` and the workflow-shapes reference described the new keys. See p1-review.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-28T10:11:19+00:00 phase=1 state=open review_scope=out -->
### p1-r5 · finding [open] (reviewer: out of scope) · 01-fr-goal.md says stealth never pushes the target's branch, which is loose beside `fr push` (phase 1)

This was loose before this change. See p1-review.

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-11-28T10:11:19+00:00 phase=1 -->
### p1-review · review · independent code review of phase 1: 5 findings (4 in scope, 1 out of scope) (phase 1)

The reviewer checked R1–R10 against the code with a file:line for each. It found no correctness bug and no fail-open path. Settle-fix pushes go through `fr push`, and every other product-branch pusher refuses or is out of scope. settings.yaml is not an artifact kind, so it owes no migration, and the module budget holds. It judged the executor's extra behaviour changes sound.
The findings are test and message gaps: p1-r1..p1-r4 in scope, all fixed. p1-r5 is out of scope and fixed too, because it is one sentence on a page this change already edits.

<!-- fr:journal kind=lens scope=plan id=lens-tests-1 created=2026-11-28T10:11:19+00:00 phase=1 lens=tests step=review-phase -->
### lens-tests-1 · lens · Stealth tests now take the forced ask as approved through a fixture, so the ask's own coverage needs checking across the whole feature (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-28T10:11:19+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: The stealth walk hand-records the PR on the cursor, so the stealth `fr pr create` ask is never walked (phase 1)

The walk now runs `fr pr create` under stealth. It shows the refusal with a `git.pr` ask request, approves it through `fr_approved`, and shows the approved command going past the ask to the forge. The local-path origin names no forge, so the cursor recording that follows stays hand-written.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-28T10:11:19+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: R9 "each push asks for its own approval" has no test (phase 1)

Added test_git_policy_push.py::test_each_push_asks_anew_once_an_approved_one_has_pushed. It approves and pushes, then shows that the next commit's push refuses under a new request and pushes nothing.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-28T10:11:19+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: The stealth-forge-explicit message does not name the fix (phase 1)

The message now ends "remove the key from the tracking repo's settings file".

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-28T10:11:19+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: forge.pr_sections and workflows.disabled are missing from the settings section of docs/explainers/01-fr-goal.md (phase 1)

Added "Fewer PR-body sections" and "Fewer workflow shapes" bullets to the settings section, and extended the Repo settings table row.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-28T10:11:19+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: 01-fr-goal.md says stealth never pushes the target's branch, which is loose beside `fr push` (phase 1)

Reworded the sentence. fr never commits its own files on the target's branch, and pushes it only through `fr push`, on the operator's approval.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · Stealth phase evidence is described as always a local log, but a declared tests: ci still briefs the fast tier with tests_log: none

01-fr-goal.md and the fr-goal skill. See l-review.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-docs-accuracy-r2 · finding [open] (reviewer: in scope) · The Repo settings table row, edited by this change, gives the pre-S1 quiet and stealth settings paths

01-fr-goal.md:1385. See l-review.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-docs-accuracy-r3 · finding [open] (reviewer: in scope) · The shape file names WorkflowsSettings and ForgeSettings.pr_sections; the classes are Workflows and PrSections

See l-review.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r4 created=2026-11-28T10:39:06+00:00 state=open review_scope=out -->
### l-docs-accuracy-r4 · finding [open] (reviewer: out of scope) · 01-fr-goal.md's quiet and stealth passages still describe the settings as a root settings.yaml on origin/fr or the tracking branch

Older S1 staleness this change did not cause. See l-review.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · Stealth _driven_triage reads an unfetched tracking config branch as no driven scope, silently

settings/check.py. See l-review.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-errors-r2 · finding [open] (reviewer: in scope) · A disabled default shape refuses adopt and migrate's adopt without naming --workflow

workflow/available.py. See l-review.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-errors-r3 · finding [open] (reviewer: in scope) · The disabled-shape refusal says this repo's settings; under stealth the value lives in the tracking repo

workflow/available.py. See l-review.

<!-- fr:journal kind=finding scope=plan id=l-errors-r4 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-errors-r4 · finding [open] (reviewer: in scope) · fr run start's disabled refusal fires before the existing-run check and hides the resume path

commands/run_cmd.py. See l-review.

<!-- fr:journal kind=finding scope=plan id=l-errors-r5 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-errors-r5 · finding [open] (reviewer: in scope) · Stealth nothing-to-push uses _code_pending, true for a branch absent on the remote with no code

commands/push_cmd.py. See l-review.

<!-- fr:journal kind=finding scope=plan id=l-errors-r6 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-errors-r6 · finding [open] (reviewer: in scope) · The shape file's stealth push diagram puts the scans before the code-pending return

See l-review.

<!-- fr:journal kind=finding scope=plan id=l-errors-r7 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-errors-r7 · finding [open] (reviewer: in scope) · _body_settings swallows SettingsError into defaults with no signal

record/pr_body.py. See l-review.

<!-- fr:journal kind=finding scope=plan id=l-errors-r8 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-errors-r8 · finding [open] (reviewer: in scope) · STEALTH_GIT was inserted between SERVABLE_PLACEMENTS and its docstring

settings/load.py. See l-review.

<!-- fr:journal kind=finding scope=plan id=l-security-r1 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-security-r1 · finding [open] (reviewer: in scope) · Stealth nothing-to-push is decided from remote-tracking refs, not the remote

A stale or hand-made ref makes fr push report nothing to push while the target would move (fails safe, misreports). See l-review.

<!-- fr:journal kind=finding scope=plan id=l-security-r2 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-security-r2 · finding [open] (reviewer: in scope) · The shape file's push diagram contradicts the code's order

Same as l-errors-r6. See l-review.

<!-- fr:journal kind=finding scope=plan id=l-security-r3 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-security-r3 · finding [open] (reviewer: in scope) · Orphaned SERVABLE_PLACEMENTS docstring in settings/load.py

Same as l-errors-r8. See l-review.

<!-- fr:journal kind=finding scope=plan id=l-security-r4 created=2026-11-28T10:39:06+00:00 state=open review_scope=out -->
### l-security-r4 · finding [open] (reviewer: out of scope) · The transcript approval stealth relies on can be supplied by any process that sets FR_TRANSCRIPT_ROOT and the session id

Predates this change (run/telemetry.py); this change makes it the only stealth gate. See l-review.

<!-- fr:journal kind=finding scope=plan id=l-security-r5 created=2026-11-28T10:39:06+00:00 state=open review_scope=out -->
### l-security-r5 · finding [open] (reviewer: out of scope) · Other product-repo writers (triage batch publish and create_pr, debt create_pr, the ops gate push) never consult git.push/git.pr

Each needs an operator --yes; none is new here. See l-review.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · The stealth fr pr create ask has no unit test, and the approved_asks docstring misnames where approval is pinned

See l-review.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · The alacarte scenario never shows another shape still starts

See l-review.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · Row s2-stealth-confirm cites only alacarte-settings.sh, which never runs fr pr create

See l-review.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-tests-r4 · finding [open] (reviewer: in scope) · R6's stealth init rendering push and pr at ask is untested

See l-review.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-tests-r5 · finding [open] (reviewer: in scope) · R7's explicit git.pr auto contrary refusal is untested

See l-review.

<!-- fr:journal kind=finding scope=plan id=l-tests-r6 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-tests-r6 · finding [open] (reviewer: in scope) · No test shows a push refused by its checks leaves no request

See l-review.

<!-- fr:journal kind=finding scope=plan id=l-tests-r7 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-tests-r7 · finding [open] (reviewer: in scope) · The advance/resolve/reshape test patches refuse_disabled instead of disabling the shape in settings

See l-review.

<!-- fr:journal kind=finding scope=plan id=l-tests-r8 created=2026-11-28T10:39:06+00:00 state=open review_scope=in -->
### l-tests-r8 · finding [open] (reviewer: in scope) · A test named for the durable copy asserts nothing about it

See l-review.

<!-- fr:journal kind=review scope=plan id=l-review created=2026-11-28T10:39:06+00:00 -->
### l-review · review · lens review (docs-accuracy, errors, security, tests): 24 findings, 20 in scope, 4 out of scope

One dispatched reviewer per lens over the whole feature diff. Security found no way for code to reach a stealth target without a verified approval. In scope: 19 fixed and 1 refuted (l-errors-r7). Out of scope: l-docs-accuracy-r4, l-security-r4 and l-security-r5, each filed at deliver. l-security-r2 and r3 duplicate l-errors-r6 and r8.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: Stealth phase evidence is described as always a local log, but a declared tests: ci still briefs the fast tier with tests_log: none

01-fr-goal.md and the fr-goal skill (and mirrors) now say no phase uses tests: ci as its own evidence. A phase's evidence is a local log, or under a declared tests: ci its fast tier with tests_log: none.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-docs-accuracy-r2 -->
### l-docs-accuracy-r2-resolved · finding [fixed] · resolves l-docs-accuracy-r2: The Repo settings table row, edited by this change, gives the pre-S1 quiet and stealth settings paths

The row now gives .fr/settings.yaml on fr-config (quiet) and <target-dir>/.fr/settings.yaml on <branch>-config (stealth). Lines 1505 and 1600 are corrected too.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-docs-accuracy-r3 -->
### l-docs-accuracy-r3-resolved · finding [fixed] · resolves l-docs-accuracy-r3: The shape file names WorkflowsSettings and ForgeSettings.pr_sections; the classes are Workflows and PrSections

The shape file names Workflows.disabled and Forge.pr_sections (PrSections).

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r4-resolved created=2026-11-28T10:39:06+00:00 state=open resolves=l-docs-accuracy-r4 out_of_scope=true -->
### l-docs-accuracy-r4-resolved · finding [out-of-scope] · resolves l-docs-accuracy-r4: 01-fr-goal.md's quiet and stealth passages still describe the settings as a root settings.yaml on origin/fr or the tracking branch

The policy-key lines (1505, 1600) are fixed here. The quiet switch passage (init --quiet and the origin/fr switch) describes S1's switch move, which this change did not touch and which needs its own check against config/space.py.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: Stealth _driven_triage reads an unfetched tracking config branch as no driven scope, silently

Under stealth, an unfetched tracking config branch now prints a notice naming git fetch origin <branch>-config. It still reads no driven scope, because a first stealth run's branch may not exist yet. Pinned in test_settings_stealth.py.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-errors-r2 -->
### l-errors-r2-resolved · finding [fixed] · resolves l-errors-r2: A disabled default shape refuses adopt and migrate's adopt without naming --workflow

refuse_disabled now names --workflow and an available shape (fr run adopt <plan> --workflow <s>, fr run start <s>). Migrate's adopt prints that message per plan.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-errors-r3 -->
### l-errors-r3-resolved · finding [fixed] · resolves l-errors-r3: The disabled-shape refusal says this repo's settings; under stealth the value lives in the tracking repo

The message names where workflows.disabled is read for the placement. Under stealth that is the tracking repo's settings file, not the target's.

<!-- fr:journal kind=finding scope=plan id=l-errors-r4-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-errors-r4 -->
### l-errors-r4-resolved · finding [fixed] · resolves l-errors-r4: fr run start's disabled refusal fires before the existing-run check and hides the resume path

fr run start's disabled refusal adds the line: a run already on this branch keeps going: fr run status, fr run advance <id>.

<!-- fr:journal kind=finding scope=plan id=l-errors-r5-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-errors-r5 -->
### l-errors-r5-resolved · finding [fixed] · resolves l-errors-r5: Stealth nothing-to-push uses _code_pending, true for a branch absent on the remote with no code

fr push uses git_policy.push.push_moves_remote, so a branch absent on the remote whose HEAD adds no commit is nothing to push. Pinned in tests/unit/test_push_moves_remote.py.

<!-- fr:journal kind=finding scope=plan id=l-errors-r6-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-errors-r6 -->
### l-errors-r6-resolved · finding [fixed] · resolves l-errors-r6: The shape file's stealth push diagram puts the scans before the code-pending return

The shape file's diagram follows the code's order.

<!-- fr:journal kind=finding scope=plan id=l-errors-r7-resolved created=2026-11-28T10:39:06+00:00 state=refuted resolves=l-errors-r7 -->
### l-errors-r7-resolved · finding [refuted] · resolves l-errors-r7: _body_settings swallows SettingsError into defaults with no signal

The fallback renders every section (a superset of what settings could switch off), so it fails toward more required sections, never fewer. deliver loads the settings itself and refuses an unreadable file with its cause, so no cause is hidden.

<!-- fr:journal kind=finding scope=plan id=l-errors-r8-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-errors-r8 -->
### l-errors-r8-resolved · finding [fixed] · resolves l-errors-r8: STEALTH_GIT was inserted between SERVABLE_PLACEMENTS and its docstring

The docstrings are back under their constants.

<!-- fr:journal kind=finding scope=plan id=l-security-r1-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-security-r1 -->
### l-security-r1-resolved · finding [fixed] · resolves l-security-r1: Stealth nothing-to-push is decided from remote-tracking refs, not the remote

push_moves_remote reads the remote live (commits_the_push_adds and ls-remote of the branch). A stale or hand-made remote-tracking ref no longer reads as nothing to push. Pinned in test_push_moves_remote.py (stale ref, fast-forward onto main).

<!-- fr:journal kind=finding scope=plan id=l-security-r2-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-security-r2 -->
### l-security-r2-resolved · finding [fixed] · resolves l-security-r2: The shape file's push diagram contradicts the code's order

Same fix as l-errors-r6.

<!-- fr:journal kind=finding scope=plan id=l-security-r3-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-security-r3 -->
### l-security-r3-resolved · finding [fixed] · resolves l-security-r3: Orphaned SERVABLE_PLACEMENTS docstring in settings/load.py

Same fix as l-errors-r8.

<!-- fr:journal kind=finding scope=plan id=l-security-r4-resolved created=2026-11-28T10:39:06+00:00 state=open resolves=l-security-r4 out_of_scope=true -->
### l-security-r4-resolved · finding [out-of-scope] · resolves l-security-r4: The transcript approval stealth relies on can be supplied by any process that sets FR_TRANSCRIPT_ROOT and the session id

The transcript reader and its environment overrides predate this change, and protecting them needs a design of its own (where fr may trust a transcript).

<!-- fr:journal kind=finding scope=plan id=l-security-r5-resolved created=2026-11-28T10:39:06+00:00 state=open resolves=l-security-r5 out_of_scope=true -->
### l-security-r5-resolved · finding [out-of-scope] · resolves l-security-r5: Other product-repo writers (triage batch publish and create_pr, debt create_pr, the ops gate push) never consult git.push/git.pr

These writers predate this change, each needs an operator --yes, and none is reachable from fr-goal's stealth path. Making them read the git policy is its own change.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: The stealth fr pr create ask has no unit test, and the approved_asks docstring misnames where approval is pinned

Added test_stealth_pr_create_asks_and_stores_a_pr_request (no stub). The approved_asks docstring names where the request and the approval are pinned.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: The alacarte scenario never shows another shape still starts

alacarte-settings.sh now starts fr-goal on another branch after the refusal and checks its cursor was written.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: Row s2-stealth-confirm cites only alacarte-settings.sh, which never runs fr pr create

s2-stealth-confirm gains the placement-stealth scenario (which walks fr pr create's ask) and unit levels for the pr-create ask, pr auto and push_moves_remote.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-tests-r4 -->
### l-tests-r4-resolved · finding [fixed] · resolves l-tests-r4: R6's stealth init rendering push and pr at ask is untested

The stealth init test asserts push and pr render at ask.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-tests-r5 -->
### l-tests-r5-resolved · finding [fixed] · resolves l-tests-r5: R7's explicit git.pr auto contrary refusal is untested

An explicit git.pr auto is pinned as stealth-forge-explicit.

<!-- fr:journal kind=finding scope=plan id=l-tests-r6-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-tests-r6 -->
### l-tests-r6-resolved · finding [fixed] · resolves l-tests-r6: No test shows a push refused by its checks leaves no request

A stealth push refused by its subject check leaves no request and prints no ask.

<!-- fr:journal kind=finding scope=plan id=l-tests-r7-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-tests-r7 -->
### l-tests-r7-resolved · finding [fixed] · resolves l-tests-r7: The advance/resolve/reshape test patches refuse_disabled instead of disabling the shape in settings

The test disables fr-goal-light in real schema-3 settings on origin's default branch and checks the setting is in force first.

<!-- fr:journal kind=finding scope=plan id=l-tests-r8-resolved created=2026-11-28T10:39:06+00:00 state=fixed resolves=l-tests-r8 -->
### l-tests-r8-resolved · finding [fixed] · resolves l-tests-r8: A test named for the durable copy asserts nothing about it

Renamed to ..._on_the_live_pr. The durable copy is asserted by test_the_durable_render_lacks_an_off_section.
