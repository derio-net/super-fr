<!-- fr:journal-schema=3 -->
# Journal: 2026-11-11-docs-currency

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-11T12:17:36+00:00 input=true -->
### operator-brief · discovery · The operator's brief, as typed

there is documentation for this project, in Readme and in https://derio-net.github.io/super-fr/. I want to substantially improve both the repo documentation and the published pages. I think one of the published pages is raw html, these pages should be generated and stay up to date with all PRs (I think this is already the case, via an installed skill or a fr verb - which? are there blind spots e.g. only via fr-goal but not fr-debugging, what about future flows?).

<!-- fr:journal kind=decision scope=spec id=d-generator created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-generator · decision · Pages are rendered at deploy from Markdown with pinned blog-craft

Operator chose 'Render at deploy' (asked before the gate opened, restated in the spec): committed .html deleted; the two hand-authored pages become Markdown and lose their bespoke layout. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d-enforcement created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-enforcement · decision · Currency is enforced by a shipped fr verb for all repos

Operator chose 'Shipped fr verb for all repos' over a repo-local CI gate. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d-scope created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-scope · decision · Pipeline, gate, README and every new page in one PR

Operator chose 'Everything in one PR'. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d-verification created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-verification · decision · Verification strategy is candidate

Round 1 question 1: 'candidate'. The published site is a post-merge Test Plan row gated tester. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d-waiver created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-waiver · decision · A PR waives a page with a reviewed stamp in its front matter

Round 1 question 2: 'Reviewed stamp in the page'. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d-readme created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-readme · decision · The README becomes a short front door

Round 1 question 3: 'Short front door'; reference sections move to published pages. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d-depth created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-depth · decision · New explainers are concise

Round 1 question 4: 150 to 300 lines each. decider: operator.

<!-- fr:journal kind=decision scope=spec id=d-model-mechanical created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-model-mechanical · decision · mechanical tier runs on haiku

Round 1 question 5. old: unbound, new: haiku, reason: unbound tier, decider: operator, rule: brief unbound_tiers. Applied with fr models set.

<!-- fr:journal kind=decision scope=spec id=d-model-standard created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-model-standard · decision · standard tier runs on sonnet

Round 1 question 6. old: unbound, new: sonnet, reason: unbound tier, decider: operator, rule: brief unbound_tiers. Applied with fr models set.

<!-- fr:journal kind=decision scope=spec id=d-model-hard created=2026-11-11T12:17:36+00:00 decided_by=operator -->
### d-model-hard · decision · hard tier runs on opus

Round 1 question 7. old: unbound, new: opus, reason: unbound tier, decider: operator, rule: brief unbound_tiers. Applied with fr models set.
