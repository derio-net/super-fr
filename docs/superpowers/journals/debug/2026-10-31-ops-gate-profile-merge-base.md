<!-- fr:journal-schema=3 -->
# Journal: 2026-10-31-ops-gate-profile-merge-base

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-10-31T20:10:08+00:00 -->
### repro-1 · repro · stage 1 blames main-side profile changes on the PR

gh#1266: fr ops gate stage 1 refuses PR #N 'changes the ops profile' when the PR's own diff (origin/main...head) touches no .devcontainer path, but a later PR merged to main changed the profile. Two-dot diff origin/main head lists those main-side changes.

<!-- fr:journal kind=root-cause scope=debug id=rc-1 created=2026-10-31T20:10:18+00:00 -->
### rc-1 · root-cause · two-dot diff against main's tip

HostCheckout.changed_paths (commands/ops_gate_cmd.py) runs a two-dot 'git diff --name-only base head', which compares main's TIP with the PR head, so anything main gained since the fork counts as a PR change. The GateHost protocol docstring (ops/gate.py) specifies the same two-dot form. Both stage-1 checks (archived journals, ops profile) inherit it. gitseam.Checkout.changed_paths already uses ref...head (merge base) correctly.

<!-- fr:journal kind=finding scope=debug id=fix-1 created=2026-10-31T20:12:51+00:00 state=fixed -->
### fix-1 · finding [fixed] · diff from the merge base

ops_gate_cmd.HostCheckout.changed_paths now runs 'git diff --name-only --merge-base --end-of-options <base> <head> -- <paths>'; GateHost docstring updated. Failing-first test: tests/unit/test_ops_gate_cmd.py::test_changed_paths_are_what_the_pr_changed_not_what_main_gained (red before: main-side profile file listed; green after). Covers both stage-1 checks (archived journals, ops profile). A merged PR's head is an ancestor of main, so its diff is empty. Not addressed here: stage 1 still fetches feat/<slug> by name after the forge deletes it (a non-fatal warning).

<!-- fr:journal kind=review scope=debug id=review-1 created=2026-10-31T20:13:49+00:00 -->
### review-1 · review · self-review, PR #1267

Inline self-review of the diff. Both changed_paths callers (archived journals, ops profile) want PR-diff semantics, so --merge-base is correct for each. Raised: (1) unrelated histories now fail loudly instead of answering, accepted for a security gate; (2) the post-merge fetch of feat/<slug> warns after branch deletion, out of scope, non-fatal. No in-scope findings open.
