# Journal: 2026-10-02-batch-forge-honesty

<!-- fr:journal kind=ruled-out scope=debug id=e4fc50219a6f created=2026-10-02T18:05:55+00:00 -->
### e4fc50219a6f · ruled-out · The four members do not share one root cause

Batch premise: one root cause. Investigation of the code each issue names finds four independent defects in four modules:
- #803: tracking gate (`_tracking_gate`, triage_batch_cmd.py:473) is called only by dispatch (:801); cancel (:380-406), merge and `fr undispatch` (undispatch_cmd.py) write labels/comments ungated. Cause: #794 placed the gate per-verb, not at the forge-write seam.
- #490: fr_vk/pr_state.py closer seam is `Callable[[str, str, str], None]` (repo, issue, backend); the host derived from pr_url in `_close_linked_gh_issue` (:121) never reaches `_default_close_gh_issue` (:76). Cause: a backend string travels where a resolved client is needed.
- #804: apply_cmd.py:265 reads require_tracker(plan repo). Not a defect yet: the spec does not say whose setting governs; needs an operator decision.
- #800: gitseam.py:186 merge passes `-c rerere.enabled=false` but not `merge.directoryRenames=false`; git infers a directory rename when an archive empties runs/ or journals/plans/. Cause: git default config, unrelated to forge writes.
Shared theme (forge/tracker honesty) only for #803/#804; #490 and #800 are separate. Per the batch's debugging rules, stopping to ask before fixing any.

<!-- fr:journal kind=decision scope=debug id=2f7b0b916b2d created=2026-10-02T18:08:51+00:00 -->
### 2f7b0b916b2d · decision · Operator: fix all four in one PR; #804 — the plan repo's tracking setting governs

Asked after the split finding. Answer: keep the one-PR contract, one failing test + one fix per cause. #804: the plan repo's `tracking` governs `fr apply --yes` for a cross-repo plan (fr has no checkout of target_repo; the plan repo declared intent). Pin it with a test and state it in the spec + code.

<!-- fr:journal kind=repro scope=debug id=b6486b64443f created=2026-10-02T18:10:12+00:00 -->
### b6486b64443f · repro · #800 reproduced: emptied docs/runs/ makes the scratch merge report a phantom path

tests/unit/test_triage_gitseam.py::test_an_archive_that_empties_a_live_directory_is_not_a_rename — main moves the last file of docs/runs/ into docs/implemented/runs/; the PR adds docs/runs/new.yaml. `Worktree.merge('origin/main')` returns ['docs/implemented/runs/new.yaml'] (exists on neither side), with merge.directoryRenames=conflict (git's default).

<!-- fr:journal kind=root-cause scope=debug id=ec7d0d7c107f created=2026-10-02T18:10:59+00:00 -->
### ec7d0d7c107f · root-cause · #800: the scratch merge inherits git's directory-rename detection

gitseam.Worktree.merge overrode rerere only. With merge.directoryRenames at git's default (conflict), an archive that empties docs/runs/ reads as a rename of the directory, so the PR's new cursor is relocated to implemented/runs/ and reported as a conflict on a path neither side has.

<!-- fr:journal kind=finding scope=debug id=6f8d6bfbd307 created=2026-10-02T18:11:00+00:00 state=fixed -->
### 6f8d6bfbd307 · finding [fixed] · #800 fixed: -c merge.directoryRenames=false on the scratch merge

gitseam.py Worktree.merge; pinned by test_an_archive_that_empties_a_live_directory_is_not_a_rename (real repo, failed first). It is the only git merge fr runs (grep: no other merge/rebase call site in packages/*/src). The base clone's local merge.directoryRenames=false workaround can be dropped once this ships.

<!-- fr:journal kind=root-cause scope=debug id=4295173f790f created=2026-10-02T18:12:42+00:00 -->
### 4295173f790f · root-cause · #803: the tracking gate is per verb, and only apply/dispatch call it

require_tracker is called from apply_cmd._apply_one and triage_batch_cmd._tracking_gate (dispatch only, :801). batch cancel (:380-406, edit_issue_labels + comment_issue) and fr undispatch (comment_issue + edit_issue_state) never call it. batch merge was named by the issue but writes nothing to an issue: batch_merge.py's only forge writes are pr_merge (the forge, not the tracker) — ruled out, left ungated. Failing tests: test_tracking_none.py::test_cancel_* / test_undispatch_*.

<!-- fr:journal kind=finding scope=debug id=470478ca7664 created=2026-10-02T18:13:49+00:00 state=fixed -->
### 470478ca7664 · finding [fixed] · #803 fixed: cancel and undispatch call the tracking gate before any forge call

triage_batch_cmd.batch_cancel_command calls _tracking_gate (new --checkout option, as dispatch) when the batch reached the forge; undispatch_cmd calls require_tracker on the plan's repo root, exit 2 with --yes, warning otherwise. Pinned by test_tracking_none.py::test_cancel_yes_refuses_* / test_cancel_dry_run_warns_* / test_cancel_yes_still_acts_* / test_undispatch_*. Behaviour change: cancel --yes on a dispatched batch now needs a clone of the batch's repo (cwd or --checkout), the same requirement dispatch --yes already has.

<!-- fr:journal kind=finding scope=debug id=688b5932ef3a created=2026-10-02T18:14:23+00:00 state=fixed -->
### 688b5932ef3a · finding [fixed] · #804 settled: the plan repo's tracking governs a cross-repo plan

No defect: a decision. apply_cmd._apply_one already calls require_tracker on the plan's repo root; the operator chose that as the rule (decision 2f7b0b916b2d). Stated in a comment at the call and pinned by test_tracking_none.py::test_a_cross_repo_plan_is_gated_by_the_plan_repos_tracking (spies require_tracker: called once, with the plan repo root, never the target). undispatch follows the same rule. The spec (2026-09-28-fr-profiles-services-design.md) is archived under implemented/ and frozen, so the rule is recorded here and in the code, not there.

<!-- fr:journal kind=root-cause scope=debug id=6bea8e7c05bd created=2026-10-02T18:16:27+00:00 -->
### 6bea8e7c05bd · root-cause · #490: the closer seam carries a backend string, so the host never reaches the client

pr_state's injectable closer is Callable[[repo, issue, backend], None]; _close_linked_gh_issue (:157) resolves only backend_for_url(pr_url) and _default_close_gh_issue (:112) calls client_for_backend(backend) with no host — glab defaults to gitlab.com. reconcile_done_issues has the same defect and a second one: it takes the backend from the card title's tag even when the card has a PR URL naming the real forge. pr_observe (:59-61) already resolves (backend, host) from a URL correctly — the pattern to share. Bridge audit: no fr_dispatch dependence on the seam; production callers (bridge_cli.py:542,559) never inject a closer. Failing tests: test_bridge_pr_state.py::test_the_default_close_targets_the_self_hosted_host, test_done_reconcile.py::test_reconcile_closes_on_the_self_hosted_host_of_the_cards_pr.

<!-- fr:journal kind=finding scope=debug id=f048cad85393 created=2026-10-02T18:18:13+00:00 state=fixed -->
### f048cad85393 · finding [fixed] · #490 fixed: the closer seam passes a resolved client, not a backend string

pr_state.Closer = Callable[[repo, issue, GhClient], None]; _client_for_url resolves (backend_for_url, self_hosted_hostname) exactly as pr_observe does; _close_linked_gh_issue and reconcile_done_issues (via _client_for_card: the PR URL when it names the title's repo, else the title tag, hostless) resolve before calling the closer. Option 2 of the issue — removes the backend-string shape rather than widening the arity. Pinned by test_the_default_close_targets_the_self_hosted_host, test_the_default_close_passes_no_host_for_a_saas_url, test_reconcile_closes_on_the_self_hosted_host_of_the_cards_pr. Test doubles now receive a client; tests/unit/fakes.forge_of maps it back to the forge name. Production callers (bridge_cli.py:542,559) inject nothing, so they are unchanged. Not touched: triage_batch_cmd.make_client(url) also drops the host (same class, noted by the bridge audit) — out of scope here.

<!-- fr:journal kind=review scope=debug id=26d8ad28e48f created=2026-10-02T18:31:29+00:00 -->
### 26d8ad28e48f · review · Independent adversarial review: no defects found

A separate reviewer read the changed files (gitseam, triage_batch_cmd, undispatch_cmd, apply_cmd, pr_state, tests). Confirmed: every gate runs before make_client / any forge call / the judgements.yaml write; --repair still gated; malformed declarations fail closed; client resolution in pr_state sits inside the existing non-fatal try on both paths; no stranded seam callers. Low-severity, not acted on: (1) cancel --yes outside a clone reports the '--checkout <path>: its origin is X' message dispatch already uses; (2) the cancel/dispatch dry-run warning reads the cwd clone without an origin check — --yes is strict, so no safety impact. Both pre-date this branch in dispatch and are shared, not introduced. Its note that red-green was unverified is answered by history: each failing test was committed before its fix (6806732d, 962c866e^, 1f84fad2^) and observed failing. Full suite: 7660 passed, 97 skipped; ruff, format, mypy, fr validate artifacts, change-fragment gate all green.
