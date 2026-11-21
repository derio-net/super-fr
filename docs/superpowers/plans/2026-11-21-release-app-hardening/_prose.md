# Release app hardening — plan

One agentic phase. The asks are one reviewable change: the workflow's
environment, the script that sets it up, and the runbook that explains it each
depend on the others' shape.

The script replaces `scripts/configure-main-protection.sh`. It is tested only
with a stub `gh` and a stub `curl`; nothing here touches a live repo. The live
proof is the post-merge `release-app-setup-live` row, which the operator walks.

Test discipline on this host: run single test files only, never the full suite.
CI is the suite evidence (`tests: ci`).

Out of the phase: R16 (the PR body's operator steps) is written at `deliver`.
