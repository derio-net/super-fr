<!-- fr:journal-schema=4 -->
# Journal: 2026-11-17-suite-trust

<!-- fr:journal kind=repro scope=debug id=741daae6c2db created=2026-11-17T09:09:59+00:00 -->
### 741daae6c2db · repro · gh#1468: scenario fixture commits land in the live worktree when pytest inherits GIT_DIR

Sandbox repro: a linked worktree `wt`; `GIT_DIR=<live>/.git/worktrees/wt` (what a git hook and `git rebase -x` both export, observed); then the triage-closed-recovery fixture steps in a fresh tmp dir: `git init -q $PWD` (writes nothing, it reinitialises GIT_DIR), `git commit --allow-empty -m fixture` as scenario@example.invalid, `git checkout -b feat/fixture`. Result: the live worktree is on feat/fixture with an empty scenario commit; the tmp dir has no .git. Matches the retire-vk symptom exactly (first commit on the run branch, the rest on feat/fixture).
