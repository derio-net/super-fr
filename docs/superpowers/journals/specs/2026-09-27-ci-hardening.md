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
