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
