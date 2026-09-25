# Journal: 2026-09-25-flat-agent-step-evidence-debt

<!-- fr:journal kind=decision scope=spec id=post-merge-verification created=2026-09-24T22:55:04 -->
### post-merge-verification · decision · Post-merge verification

Operator confirmed: post-merge, verify fr run check and fr run status both report evidence debt for an unevidenced flat agent step such as spec-review or deliver.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-24T22:56:17 state=fixed review_scope=in -->
### s1 · finding [fixed] (reviewer: in scope) · Full-suite verification must use foreground chunks

The Test Plan must specify the full-suite foreground-chunk requirement recorded by #607.

<!-- fr:journal kind=review scope=spec id=153d5a20c4d6 created=2026-09-24T22:56:22 -->
### 153d5a20c4d6 · review · Spec review

In-scope findings: s1, fixed by specifying the full suite must run in foreground chunks per #607. No other findings.

<!-- fr:journal kind=decision scope=spec id=skeleton-override-2026-09-25-flat-agent-step-evidence-debt created=2026-09-24T22:57:50 -->
### skeleton-override-2026-09-25-flat-agent-step-evidence-debt · decision · Single-phase skeleton override

This is a narrow single-file state-source fix with one focused unit test module. Its agentic phase itself is the smallest meaningful walking skeleton and CI exercises the runtime through tests; adding another phase would only add dispatch/handoff overhead, so the one phase is marked as the skeleton.
