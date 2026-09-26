# Journal: 2026-09-26-ci-time-budget

<!-- fr:journal kind=decision scope=plan id=plan-two-phases created=2026-09-26T15:14:33 -->
### plan-two-phases · decision · Two agentic phases, sharding (skeleton, proven live on the branch CI run) then the watcher

The watcher is inert until merge, so only the sharding can be proven live pre-merge; making it the skeleton puts the riskiest claim (under 240s) first. There is no manual phase, because the post-merge Test Plan is operator-driven.
