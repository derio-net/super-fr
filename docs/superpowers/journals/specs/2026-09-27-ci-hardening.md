# Journal: 2026-09-27-ci-hardening

<!-- fr:journal kind=decision scope=spec id=pin-scope-all-remote created=2026-09-27T14:27:59+00:00 -->
### pin-scope-all-remote · decision · Pin every remote action, actions/* included; only ./ local refs exempt

Operator, round 1: a tag on actions/* is as mutable as any other.

<!-- fr:journal kind=decision scope=spec id=aggregate-ci-ok created=2026-09-27T14:27:59+00:00 -->
### aggregate-ci-ok · decision · Aggregating job gates every ci.yml job and is named ci-ok

Operator, round 1: needs lists every other ci.yml job (pinned as an equality by a test); if: always(); fails on failure/cancelled. Supersedes #706's suggested name test-all.

<!-- fr:journal kind=decision scope=spec id=dependabot-weekly-grouped created=2026-09-27T14:27:59+00:00 -->
### dependabot-weekly-grouped · decision · Dependabot github-actions: weekly, one grouped PR

Operator, round 1.

<!-- fr:journal kind=decision scope=spec id=tripwire-sha-plus-comment created=2026-09-27T14:27:59+00:00 -->
### tripwire-sha-plus-comment · decision · Tripwire requires 40-hex SHA + '# vX.Y.Z' comment; pin today's commit of each current tag, no upgrades

Operator, round 1. SHAs resolved via the GitHub API with annotated tags dereferenced; table in spec 3.A.

<!-- fr:journal kind=discovery scope=spec id=scaffold-tag-pins created=2026-09-27T14:27:59+00:00 -->
### scaffold-tag-pins · discovery · fr acceptance scaffold emits tag-pinned actions into consumer repos

packages/fr/src/fr/acceptance/scaffold.py:133-147,236-250. packages/ source is owned by other batches; out of scope, follow-up issue at deliver.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-27T14:37:03+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Tripwire's text-scan/yaml-parse equality misses a job-level uses (reusable workflow call)

_pr_spec_status.yml:21 is jobs.status.uses with no steps; a steps-only walker drops it and the equality fails on this repo's own workflows. Spec 3.C must name both shapes.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-27T14:37:03+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · Version-comment regex looser than the decided vX.Y.Z

3.C said v<digits>(.<digits>)*, accepting '# v4'; decision 4 says vX.Y.Z.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-27T14:37:03+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · Problem section miscounts remote uses (27 claimed, 34 actual)

35 uses lines, 34 remote; the pin table's 12 unique pairs are complete.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-27T14:37:03+00:00 -->
### spec-review · review · independent spec review: 3 findings

fr-spec-reviewer (standard tier): 3 in-scope findings (s1-s3), all fixed in the spec. Verified: ci-ok needs matches ci.yml's 8 jobs; pin table exhaustive; ci-budget needs no change; existing tests match on startswith, not tags; matrix rows present; packages/ and ruleset untouched.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-27T14:37:03+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Tripwire's text-scan/yaml-parse equality misses a job-level uses (reusable workflow call)

3.C now collects jobs.<id>.uses and jobs.<id>.steps[].uses and names _pr_spec_status.yml:21 as the real case; compares multisets.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-27T14:37:03+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: Version-comment regex looser than the decided vX.Y.Z

3.C now requires v\d+\.\d+\.\d+ exactly.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-27T14:37:03+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: Problem section miscounts remote uses (27 claimed, 34 actual)

1 now says 34 remote (35 in all, one local).
