# Journal: 2026-10-11-cloud-driver-fail-loud

<!-- fr:journal kind=repro scope=debug id=40e18dbaae3e created=2026-10-11T19:11:31+00:00 -->
### 40e18dbaae3e · repro · Batch cloud-driver-fail-loud: all 3 members' defects still open on main 1248d439

Confirmed by reading main @ 1248d439, not reproduced live (needs a Claude Code cloud session).
- #1099.1 runner.py:84-95 dispatch passes payload branch for every item incl. closeouts.
- #1099.2 mailbox.py status map has no init-error input; a session that never started maps to working.
- #1100.1 gitseam.py:391-400 default_branch raises on unset origin/HEAD.
- #1100.2 gitseam.py:518-528 fast_forward refuses a detached/non-default checkout.
- #1100.4 binary_identity.py:86 re-pin warning still fires after a by-design self-update.
- #1098.1 batch_dispatch.py:68 brief installs fr only when missing, never when outdated.
- #1098.2 brief does not require the batch skill nor end BLOCKED without it.
- #1100 comment: verify-merge / pickup read PRs over GraphQL regardless of forge.api.

<!-- fr:journal kind=hypothesis scope=debug id=92bf67c16b08 created=2026-10-11T19:11:50+00:00 -->
### 92bf67c16b08 · hypothesis · Not one root cause: ~14 independent defects across 6 subsystems sharing a theme

Shared theme only: cloud code paths assume host-like preconditions (current fr, skills loaded, origin/HEAD set, base clone on default branch, PR readable over GraphQL, session started) and proceed or misreport instead of checking. Each defect has its own cause and fix site: worker brief (batch_dispatch), claude-cloud runner + mailbox, gitseam, binary_identity, cloud doctor/docs, isolation verify-merge + pickup forge seam. Per the batch's debugging rule, stopping to ask before fixing.

<!-- fr:journal kind=decision scope=debug id=fa423899838d created=2026-10-11T19:52:50+00:00 -->
### fa423899838d · decision · Operator: fix all ~14 defects in this one PR

Asked at the multi-cause stop (2026-10-11). Answer: fix everything here, one failing test per defect, all three members close. Order: E,F (runner/mailbox) → H,I (gitseam/close-out) → G (pass exit) → L (restore line) → K (re-pin noise) → J (merge_method doctor) → D (isolation default in cloud) → M (verify-merge/pickup over forge.api) → A,B,C (worker brief).

<!-- fr:journal kind=hypothesis scope=debug id=926aa6ecdc62 created=2026-10-11T20:50:07+00:00 -->
### 926aa6ecdc62 · hypothesis · #1100 comment (verify-merge/pickup 403): not GraphQL routing; the cloud proxy origin URL, if it is http://…@127.0.0.1:<port>/git/<owner>/<repo>

Ruled out: routing. Both verify-merge (isolation/local.py _pr_from) and pickup (run/closeout.py pr_body) go through hostclient.client_for -> client_for_backend, which picks RealGhRestClient under forge.api: rest, identically at v5.18.1 and HEAD.
Candidate: _hosts.origin_slug keeps the WHOLE remote path (git/<owner>/<repo> for a proxy URL) and host_for returns the proxy host (127.0.0.1, not SaaS) so GH_HOST=127.0.0.1; triage avoids both via gitseam.repo_of_url (last two segments) + client_for_url(github URL). Unverified: no artifact records the cloud origin URL shape. Asking the operator before fixing.

<!-- fr:journal kind=root-cause scope=debug id=6b5b07dd25ea created=2026-10-11T20:56:51+00:00 -->
### 6b5b07dd25ea · root-cause · Shared class, separate causes: cloud paths assumed host preconditions

#1099.1 runner dispatched payload.branch for close-outs. #1099.2 the status row never asked for last_init_error. #1099.3 _conflict built its line with _stopped_line, which always set failed_write. #1100.1 default_branch refused on unset origin/HEAD. #1100.2 fast_forward refused any non-default checkout, even the driver's own. #1100.3 the doctor never ran choose_method. #1100.4 judge warned on any same-dir upgrade. #1100.5 drive pass discarded fetch_now's result. #1098.1-3 the brief installed fr only when missing, never named the skill, and accepted agents by file. #1098.4 _target defaulted to devcontainer with no cloud check.

<!-- fr:journal kind=finding scope=debug id=fixed-1099 created=2026-10-11T20:56:54+00:00 state=fixed -->
### fixed-1099 · finding [fixed] · #1099 fixed: close-out base branch, init error blocks, handled conflict no failed write

Tests (all red first): test_claude_cloud_mailbox.py#test_a_closeout_starts_on_the_default_branch_never_the_deleted_batch_branch, test_claude_cloud_status.py#test_a_session_that_failed_to_start_is_blocked_with_its_init_error, test_triage_batch_drive_cmd.py#test_a_conflict_the_pass_handles_is_no_failed_write, test_triage_driver_adapter.py#test_the_cloud_close_out_switches_its_own_clone_and_starts_on_the_default_branch.

<!-- fr:journal kind=finding scope=debug id=fixed-1100 created=2026-10-11T20:56:57+00:00 state=fixed -->
### fixed-1100 · finding [fixed] · #1100 items 1-5 fixed: origin/HEAD, own-clone switch, doctor merge_method, re-pin silence, restore line

Tests (all red first): test_triage_gitseam.py (origin_head_is_unset, switch x2), test_cloud_remedy.py (merge_method x4), test_fr_binary_identity.py#test_an_upgraded_install_in_a_cloud_session_is_silent, test_triage_driver_pass.py#test_a_pass_that_restored_the_state_says_so_and_a_warm_pass_does_not. The comment (verify-merge/pickup 403) is NOT fixed: see hypothesis 926aa6ecdc62.

<!-- fr:journal kind=finding scope=debug id=fixed-1098 created=2026-10-11T20:56:59+00:00 state=fixed -->
### fixed-1098 · finding [fixed] · #1098 fixed: worker updates stale fr, requires its skill, checks agents by type; cloud isolation defaults to host-worktree

Tests (all red first): test_triage_worker_brief.py (stale fr, skill required, debug skill, agents by dispatchability), test_isolation_cmd.py#test_target_default_in_a_cloud_session_is_host.

<!-- fr:journal kind=ruled-out scope=debug id=db70bccbcaeb created=2026-10-11T21:04:37+00:00 -->
### db70bccbcaeb · ruled-out · Proxy-origin hypothesis refuted: a cloud clone's origin is https://github.com/<owner>/<repo>

Operator, 2026-10-11: a cloud session's origin is https://github.com/derio-net/super-fr. origin_slug gives derio-net/super-fr and host_for gives None, so neither the slug nor GH_HOST explains the failure.

<!-- fr:journal kind=finding scope=debug id=deferred-1100-comment created=2026-10-11T21:06:42+00:00 state=open -->
### deferred-1100-comment · finding [open] · #1100 comment deferred to #1142: GraphQL read despite api: rest needs a cloud repro

Operator chose a follow-up (2026-10-11).

<!-- fr:journal kind=finding scope=debug id=deferred-1100-comment-resolved created=2026-10-11T21:07:10+00:00 state=open resolves=deferred-1100-comment tracked_by=derio-net/super-fr#1142 -->
### deferred-1100-comment-resolved · finding [deferred → derio-net/super-fr#1142] · resolves deferred-1100-comment: #1100 comment deferred to #1142: GraphQL read despite api: rest needs a cloud repro

needs a cloud repro; operator chose a follow-up

<!-- fr:journal kind=review scope=debug id=8534907754df created=2026-10-11T21:08:23+00:00 -->
### 8534907754df · review · Self-review of the diff: one finding, fixed

Reviewed every source hunk. Finding: test_isolation_cmd.py's mode fixture did not clear CLAUDE_CODE_REMOTE, so the suite run inside a cloud session would flip test_target_default_is_local; fixed and verified with CLAUDE_CODE_REMOTE=true. Checked and accepted: a skipped or waiting conflict also no longer exits 1 (nothing failed; documented in _conflict); fast_forward(switch) leaves untracked files alone (checkout refuses itself if one would be overwritten); the init-error fold stores state failed, which the next status read overwrites. Suite evidence is CI on #1141 (operator: no local full suite).
