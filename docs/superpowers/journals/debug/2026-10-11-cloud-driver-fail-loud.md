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
