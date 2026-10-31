<!-- fr:journal-schema=3 -->
# Journal: 2026-10-31-ops-gate-profile-merge-base

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-10-31T20:10:08+00:00 -->
### repro-1 · repro · stage 1 blames main-side profile changes on the PR

gh#1266: fr ops gate stage 1 refuses PR #N 'changes the ops profile' when the PR's own diff (origin/main...head) touches no .devcontainer path, but a later PR merged to main changed the profile. Two-dot diff origin/main head lists those main-side changes.

<!-- fr:journal kind=root-cause scope=debug id=rc-1 created=2026-10-31T20:10:18+00:00 -->
### rc-1 · root-cause · two-dot diff against main's tip

HostCheckout.changed_paths (commands/ops_gate_cmd.py) runs a two-dot 'git diff --name-only base head', which compares main's TIP with the PR head, so anything main gained since the fork counts as a PR change. The GateHost protocol docstring (ops/gate.py) specifies the same two-dot form. Both stage-1 checks (archived journals, ops profile) inherit it. gitseam.Checkout.changed_paths already uses ref...head (merge base) correctly.
