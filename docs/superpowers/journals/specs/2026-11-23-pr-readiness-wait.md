<!-- fr:journal-schema=4 -->
# Journal: 2026-11-23-pr-readiness-wait

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-23T07:59:36+00:00 input=true -->
### brief · discovery · Operator brief

I've noticed that, when super-fr delivers a draft PR, either via fr-goal or fr-debugging or the closeout PR, it doesn't wait to see whether it can merge cleanly or whether CI is green. I think a repo-level setting should be introduced that sets these behaviors. These default behaviors can be overriden per feature/bug is needed.

<!-- fr:journal kind=decision scope=spec id=d-managed-exempt created=2026-11-23T08:38:54+00:00 decided_by=operator -->
### d-managed-exempt · decision · Driver-managed PRs are exempt; settle applies only outside the wave driver

The wave merge queue admits only driver-managed PRs (batch, collected close-out, archive, export, housekeeping) and already hands conflicts and red combinations back to their sessions. A second fix loop would compete with its hand-backs and void its lease or a close-out's recorded head, so the operator chose to exempt them (enforced in code by branch prefix).

<!-- fr:journal kind=decision scope=spec id=d-default-fix created=2026-11-23T08:38:54+00:00 decided_by=operator -->
### d-default-fix · decision · The repo default is fix

Outside the driver, the delivering session waits for mergeability and CI and fixes a conflict (merge origin/<base>, never rebase or force-push) or a red check, up to three rounds. Never ready, never merged.

<!-- fr:journal kind=decision scope=spec id=d-two-keys created=2026-11-23T08:38:54+00:00 decided_by=operator -->
### d-two-keys · decision · Two keys, git.settle.conflicts and git.settle.ci, each off|report|fix

The operator chose separate keys over one.

<!-- fr:journal kind=decision scope=spec id=d-override-recorded created=2026-11-23T08:38:54+00:00 decided_by=operator -->
### d-override-recorded · decision · Overrides live in the spec's Verification section or a debug-journal decision, with a reason

Recorded and reviewable; rendered in the PR body. No hidden CLI flag.

<!-- fr:journal kind=decision scope=spec id=d-deliver-witness created=2026-11-23T08:38:54+00:00 decided_by=operator -->
### d-deliver-witness · decision · fr-goal enforces settle as a derived deliver witness

Under fix, deliver refuses while conflicting or red and holds (exit 75) while pending, so fixes land before deliver is done and the tests evidence covers the fixed tree.

<!-- fr:journal kind=decision scope=spec id=d-verification created=2026-11-23T08:38:54+00:00 decided_by=operator -->
### d-verification · decision · CI over the fake forge plus one live post-merge walk gated on tester

Every logic row is proven by the CI suite (strategy none, CI named); row pr-settle-live is walked post-merge on a sandbox PR.

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-23T08:38:54+00:00 lens=errors step=brainstorm -->
### lens-errors-1 · lens · Exit codes and pending/unknown/unsupported handling are the risky part
