<!-- fr:journal-schema=3 -->
# Journal: 2026-10-31-ops-gate-profile-merge-base

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-10-31T20:10:08+00:00 -->
### repro-1 · repro · stage 1 blames main-side profile changes on the PR

gh#1266: fr ops gate stage 1 refuses PR #N 'changes the ops profile' when the PR's own diff (origin/main...head) touches no .devcontainer path, but a later PR merged to main changed the profile. Two-dot diff origin/main head lists those main-side changes.
