# Journal: triage-batches

<!-- fr:journal kind=decision scope=spec id=d1-yes-gate created=2026-09-25T07:32:43 -->
### d1-yes-gate · decision · dispatch/merge/cancel act only with --yes; reverses the fr-triage 'writing to the forge' non-goal

Operator chose 'Act behind --yes' over 'dispatch acts, merge prints' and 'plan only' (2026-09-23).

<!-- fr:journal kind=decision scope=spec id=d2-runner-protocol created=2026-09-25T07:33:09 -->
### d2-runner-protocol · decision · Dispatch through the fr_dispatch runner protocol; new fr-herdr package; any run-unit runner

Operator chose a runner package over calling herdr from triage or prompt-only; then confirmed batching must work for any fr.runners runner.

<!-- fr:journal kind=decision scope=spec id=d3-conflicts created=2026-09-25T07:33:09 -->
### d3-conflicts · decision · Update, wait for CI, stop on real conflict; only version-file conflicts auto-resolve

Operator chose update/wait/stop and added: anticipate version bumps up front so CI builds early.

<!-- fr:journal kind=decision scope=spec id=d4-reserve-versions created=2026-09-25T07:33:10 -->
### d4-reserve-versions · decision · Reserve versions per batch at dispatch time

Operator's addition to d3. Squash merges rule out stacking, so the version-only conflict is resolved deterministically with the reserved number.

<!-- fr:journal kind=decision scope=spec id=d5-foreground-wait created=2026-09-25T07:33:10 -->
### d5-foreground-wait · decision · batch merge --yes blocks in the foreground; re-run resumes

Operator chose foreground over GitHub auto-merge or a dispatched merge queue.

<!-- fr:journal kind=decision scope=spec id=d6-forge-scope created=2026-09-25T07:33:11 -->
### d6-forge-scope · decision · Forge writes via GhClient; merge ops GitHub-only with declared refusal; forge parity is gh#611

Operator asked whether a forge parity table exists (none does) and had gh#611 filed.

<!-- fr:journal kind=decision scope=spec id=d7-forge-visibility created=2026-09-25T07:33:11 -->
### d7-forge-visibility · decision · Dispatch visible on the forge: fr:in-progress label, marker comment, early draft PR

Operator asked how the issue knows it was dispatched; approved reuse of the existing fr:in-progress LabelDef.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-09-25T07:33:11 -->
### spec-review-1 · review · Independent spec review (fr-spec-reviewer): 16 in scope, 1 out of scope

Findings s1-s17 below. Bridge question answered: diff.py/observe.py touch fr: labels only on plan-tracked issues.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-25T07:33:12 state=fixed review_scope=in -->
### s1 · finding [fixed] (reviewer: in scope) · No spec journal existed; decisions only checkable against the dispatch prompt — this journal now records d1-d7

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-25T07:33:12 state=fixed review_scope=in -->
### s2 · finding [fixed] (reviewer: in scope) · fr may import fr_dispatch only at apply_cmd.py — §3.C adds triage_batch_cmd.py as a second guarded soft point

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-25T07:33:13 state=fixed review_scope=in -->
### s3 · finding [fixed] (reviewer: in scope) · Registry never loads/constructs runners — §3.C adds load_runner + from_env construction contract

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-09-25T07:33:13 state=fixed review_scope=in -->
### s4 · finding [fixed] (reviewer: in scope) · can_dispatch ran after preflight/existing_dispatches — §3.C now calls it first

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-09-25T07:33:14 state=fixed review_scope=in -->
### s5 · finding [fixed] (reviewer: in scope) · WorkItem.tracking is str|None — issues move to payload, tracking=None, workflow/parent/inputs named

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-09-25T07:33:14 state=fixed review_scope=in -->
### s6 · finding [fixed] (reviewer: in scope) · Open-batch rule needed facts at load — moved to create/edit/dispatch; events list with cancel shape; partial is terminal; re-dispatch after cancel allowed

<!-- fr:journal kind=finding scope=spec id=s7 created=2026-09-25T07:33:15 state=fixed review_scope=in -->
### s7 · finding [fixed] (reviewer: in scope) · Retry of forge writes collided with live refusal — explicit retry path, idempotent via marker comment

<!-- fr:journal kind=finding scope=spec id=s8 created=2026-09-25T07:33:15 state=fixed review_scope=in -->
### s8 · finding [fixed] (reviewer: in scope) · Stale dispatch had no forge timestamp — uses the marker comment's createdAt, comments fetched only for fr:in-progress issues

<!-- fr:journal kind=finding scope=spec id=s9 created=2026-09-25T07:33:16 state=fixed review_scope=in -->
### s9 · finding [fixed] (reviewer: in scope) · Checkout and .fr/triage.yaml undefined — new §3.I: --checkout, origin match, config read from origin/<default>

<!-- fr:journal kind=finding scope=spec id=s10 created=2026-09-25T07:33:16 state=fixed review_scope=in -->
### s10 · finding [fixed] (reviewer: in scope) · set over conflicted files fails — git checkout --theirs on version files first, tested with real multi-file manifests

<!-- fr:journal kind=finding scope=spec id=s11 created=2026-09-25T07:33:17 state=fixed review_scope=in -->
### s11 · finding [fixed] (reviewer: in scope) · Dispatch-time reservation order undefined — explicit order then dispatch sequence; merge reconcile re-numbers

<!-- fr:journal kind=finding scope=spec id=s12 created=2026-09-25T07:33:17 state=fixed review_scope=in -->
### s12 · finding [fixed] (reviewer: in scope) · head oid not fetched; files only on open PRs — headRefOid added to OPEN_PR_LIST_FIELDS, stated

<!-- fr:journal kind=finding scope=spec id=s13 created=2026-09-25T07:33:18 state=fixed review_scope=in -->
### s13 · finding [fixed] (reviewer: in scope) · in-progress stage missing from board sets — placed in IN_FLIGHT with a pill style

<!-- fr:journal kind=finding scope=spec id=s14 created=2026-09-25T07:33:18 state=fixed review_scope=in -->
### s14 · finding [fixed] (reviewer: in scope) · Test Plan gaps — items 3,7,9,13,15-17 added; merge integration fakes the forge

<!-- fr:journal kind=finding scope=spec id=s15 created=2026-09-25T07:33:19 state=fixed review_scope=in -->
### s15 · finding [fixed] (reviewer: in scope) · batch-<id> agent name collides across scopes — tab label is the full item id; agent name hashed

<!-- fr:journal kind=finding scope=spec id=s16 created=2026-09-25T07:33:19 state=fixed review_scope=in -->
### s16 · finding [fixed] (reviewer: in scope) · trigger.py docstring and bump-version description inaccurate — §5 amends docstring; §3.D globs and argument forms corrected

<!-- fr:journal kind=finding scope=spec id=s17 created=2026-09-25T07:33:20 state=open review_scope=out -->
### s17 · finding [open] (reviewer: out of scope) · 'present on gitlab and gitea' is moot while triage collect is GitHub-only

<!-- fr:journal kind=finding scope=spec id=s17-resolved created=2026-09-25T07:33:48 state=open resolves=s17 tracked_by=#611 answered_by=agent -->
### s17-resolved · finding [deferred → #611] · resolves s17: 'present on gitlab and gitea' is moot while triage collect is GitHub-only

One clarifying sentence added to §3.F; non-GitHub triage belongs to the forge parity work (gh#611).

<!-- fr:journal kind=review scope=spec id=spec-review-2 created=2026-09-25T07:39:59 -->
### spec-review-2 · review · Second independent pass (fr-spec-reviewer) over the revised spec: 12 in scope, 1 out of scope

Verified s1-s16 (s7, s8, s9, s12, s15 partial or wrong in effect); findings r2-1..r2-13 below.

<!-- fr:journal kind=finding scope=spec id=r2-1 created=2026-09-25T07:40:00 state=fixed review_scope=in -->
### r2-1 · finding [fixed] (reviewer: in scope) · Batch PR files/head_oid never reached facts (linked PRs built from PR_LIST_FIELDS) — collect joins open-PR records into linked PRs; PullRequest gains files and head_oid

<!-- fr:journal kind=finding scope=spec id=r2-2 created=2026-09-25T07:40:00 state=fixed review_scope=in -->
### r2-2 · finding [fixed] (reviewer: in scope) · .fr/triage.yaml read only from a checkout yet needed by create/edit/check — collected via Forge.read_file_at_ref into Facts.config; launch defaults resolved at dispatch

<!-- fr:journal kind=finding scope=spec id=r2-3 created=2026-09-25T07:40:01 state=fixed review_scope=in -->
### r2-3 · finding [fixed] (reviewer: in scope) · Stale dispatch lacked a facts field and Forge method — Issue.dispatch_marker_at and Forge.list_issue_comments

<!-- fr:journal kind=finding scope=spec id=r2-4 created=2026-09-25T07:40:01 state=fixed review_scope=in -->
### r2-4 · finding [fixed] (reviewer: in scope) · Marker idempotency needed a comment read — uses Forge.list_issue_comments (GitHub-only, like collect)

<!-- fr:journal kind=finding scope=spec id=r2-5 created=2026-09-25T07:40:02 state=fixed review_scope=in -->
### r2-5 · finding [fixed] (reviewer: in scope) · Re-dispatch after the runner dropped the item started a second run — stage gate refuses past proposed/cancelled/abandoned; --repair redoes forge writes only

<!-- fr:journal kind=finding scope=spec id=r2-6 created=2026-09-25T07:40:02 state=fixed review_scope=in -->
### r2-6 · finding [fixed] (reviewer: in scope) · No stage for a PR closed unmerged; PR lookup undefined — abandoned stage, highest PR number wins, batch_prs lookup by head branch

<!-- fr:journal kind=finding scope=spec id=r2-7 created=2026-09-25T07:40:02 state=fixed review_scope=in -->
### r2-7 · finding [fixed] (reviewer: in scope) · Tab label/branch collide between repo- and org-scope triage — same repo+id is the same batch; branch gate refuses the second dispatch; Test Plan 6 corrected

<!-- fr:journal kind=finding scope=spec id=r2-8 created=2026-09-25T07:40:03 state=fixed review_scope=in -->
### r2-8 · finding [fixed] (reviewer: in scope) · Brief omitted the no-tracking-issue line — added to §3.C step 3

<!-- fr:journal kind=finding scope=spec id=r2-9 created=2026-09-25T07:40:03 state=fixed review_scope=in -->
### r2-9 · finding [fixed] (reviewer: in scope) · §3.G board untested — Test Plan 19 added; cited from triage-batch-merge-queue

<!-- fr:journal kind=finding scope=spec id=r2-10 created=2026-09-25T07:40:04 state=fixed review_scope=in -->
### r2-10 · finding [fixed] (reviewer: in scope) · fr-herdr omitted name/refresh/slot_budget and repo; package wiring — specified, repo on WorkItem, mypy/CI/workspace wiring

<!-- fr:journal kind=finding scope=spec id=r2-11 created=2026-09-25T07:40:04 state=fixed review_scope=in -->
### r2-11 · finding [fixed] (reviewer: in scope) · Batch ids normalisation unstated — KEY_RE + normalize_key like Pattern.ids; case-variant test

<!-- fr:journal kind=finding scope=spec id=r2-12 created=2026-09-25T07:40:05 state=fixed review_scope=in -->
### r2-12 · finding [fixed] (reviewer: in scope) · Reconcile relied on the behind-only update path — explicit re-slot step 3b, set runs in the scratch worktree

<!-- fr:journal kind=finding scope=spec id=r2-13 created=2026-09-25T07:40:05 state=open review_scope=out -->
### r2-13 · finding [open] (reviewer: out of scope) · Linked PRs never carry checks/mergeable/merge_state in facts (pre-existing collect behaviour)

<!-- fr:journal kind=finding scope=spec id=r2-13-resolved created=2026-09-25T07:40:06 state=open resolves=r2-13 out_of_scope=true answered_by=agent -->
### r2-13-resolved · finding [out-of-scope] · resolves r2-13: Linked PRs never carry checks/mergeable/merge_state in facts (pre-existing collect behaviour)

True and pre-existing; the r2-1 open-PR join fills these fields for linked open PRs as a side effect, so no separate issue is needed.

<!-- fr:journal kind=decision scope=spec id=d8-forge-adapter created=2026-09-25T20:16:44 -->
### d8-forge-adapter · decision · All batch forge ops go through the GhClient adapter; new ops GitHub-only, declared unsupported on glab/tea; collect stays on triage Forge until gh#611

Operator (2026-09-25): the forge should be generic. Asked whether collect should move onto GhClient here: no, keep focused, GitHub gets the attention for now; gh#611 should find this surface and decide concretely.

<!-- fr:journal kind=decision scope=spec id=d-reserve-order created=2026-09-26T01:11:02 -->
### d-reserve-order · decision · Reservations follow dispatch sequence; explicit order is a merge-time constraint (§3.D)

Adopted from the phase-3 implementer's plan decision p3-reserve-order and verified sound by the phase-3 reviewer (finding r3-f8). §3.D used to say both 'dispatch-time order is explicit order, then dispatch sequence' and 'the reservation is the next version after the highest of (source, every live reservation)'; read together they conflict when a batch with order 1 is dispatched after an unordered one. Chosen: the formula. A reservation is the next version after max(origin source version, every live reservation), bumped by the batch's level, in dispatch sequence; reusing a number already briefed to another live run would make two runs build the same version, and a monotonic reservation never does. The explicit order applies at merge time: reconcile (§3.F step 3b) re-slots any PR whose version is not its slot in the real order. Spec §3.D and Test Plan 11 amended to match.
