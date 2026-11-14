<!-- fr:journal-schema=4 -->
# Journal: 2026-11-14-retire-vibekanban

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-14T21:22:30+00:00 input=true -->
### operator-brief · discovery · Operator brief — batch retire-vk (super-fr#1459)

/fr-goal Retire VibeKanban support

Batch `retire-vk` of derio-net/super-fr: 1 issues, delivered as ONE pull request.

## super-fr#1459: Drop VibeKanban support (fr-vk adapter, bridge, VK dispatch conventions)
Decision recorded: drop VibeKanban (its only deployment retired 2026-11-13). Removes `packages/fr-vk/` (16 modules), ~78 test and fixture files (117 `.test_durations` entries), the `super-fr-dispatch` VK wording and the `fr-runner` skill's VK operations.
Note: Touches packaging, install.sh, tests and skill mirrors, so it conflicts with most batches: run it as its own wave. It also shrinks the suite, which helps #1428.

## Why these belong together
Decision recorded in #1459: the only VK deployment was retired 2026-11-13. Removes packages/fr-vk, its tests and fixtures, the VK dispatch wording and the fr-runner skill's VK operations. Runs alone first: it touches packaging, install.sh, tests and mirrors, which most later batches also touch, and it shrinks the suite (#1428).

## Delivery rules
- Work on branch `feat/batch-retire-vk`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1459
- Start the run (`fr run start` with `--issue 1459`) so it records its issue.
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

Never add the `approved-fr` label: it is the operator's approval to merge, and fr voids it on your next push.

Issue #1459 body (scope survey, done-when) is on the issue; its Done-when: no `vibe.?kanban|fr_vk|\bvk\b` outside implemented/ except intentional historical mentions; fr-dispatch, fr-cncd, fr-herdr tests pass unchanged; plugin installs without fr-vk; a version bump and changelog note.

<!-- fr:journal kind=decision scope=spec id=old-scaffolds-break-with-remedy created=2026-11-14T21:22:30+00:00 decided_by=operator -->
### old-scaffolds-break-with-remedy · decision · Scaffolded devcontainers naming fr-vk break, with a clear remedy

Q: devcontainers fr already scaffolded install packages/fr-vk from main; after removal their creation fails. A: break + clear remedy (recommended) — remove the package outright, fix this repo's own profiles, and have `fr isolation up`/`rebuild` refuse such a profile naming the segment to delete; the release note says it too. No tombstone stub, no migration repair. Spec R3, R4, R11.

<!-- fr:journal kind=decision scope=spec id=fr-runner-skill-deleted created=2026-11-14T21:22:30+00:00 decided_by=operator -->
### fr-runner-skill-deleted · decision · Delete the fr-runner skill

Q: the fr-runner skill is VK-only. A: delete it (recommended); its runner-agnostic facts (fr undispatch, unit_mismatch, reachability) move into fr-dispatch. Spec R6.

<!-- fr:journal kind=decision scope=spec id=installer-removes-vk-residue created=2026-11-14T21:22:30+00:00 decided_by=operator -->
### installer-removes-vk-residue · decision · install.sh removes the VK residue it wrote

Q: what install does with the existing vibe_kanban MCP entry and vk-bridge wrapper. A: remove what fr wrote (recommended), print a line per removal; `--install-bridge` refuses naming the removal. Spec R5.

<!-- fr:journal kind=decision scope=spec id=bump-major created=2026-11-14T21:22:30+00:00 decided_by=operator -->
### bump-major · decision · The change fragment is a major bump

Q: bump level. A: major (recommended) — a runner, a daemon and an installer flag are removed and old scaffolds break. Spec R11.

<!-- fr:journal kind=decision scope=spec id=verification-candidate-developer created=2026-11-14T21:22:30+00:00 decided_by=operator -->
### verification-candidate-developer · decision · Verified by the candidate walk, gate developer

Q: pre-merge verification. A: `candidate` strategy, gate developer (recommended): the walk installs the branch into a throwaway prefix and runs the smoke, proving the plugin installs without fr-vk; rows are CI-tested. Spec ## Verification.

<!-- fr:journal kind=decision scope=spec id=captured-fixtures-kept created=2026-11-14T21:22:30+00:00 decided_by=operator -->
### captured-fixtures-kept · decision · Captured forge fixtures that quote VibeKanban stay byte-identical

Decided from the code, not asked: tests/fixtures/github_rest/** and tests/scenarios/fixtures/** mention VibeKanban only inside recorded PR bodies/check names; they are API-shape evidence, not VK behaviour, and rewriting a capture is the fixture-composition defect the repo forbids. Spec R2.
