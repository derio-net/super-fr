# Journal: scaffold-batch-574-576-569

<!-- fr:journal kind=decision scope=spec id=d1-feature-escape created=2026-09-23T01:00:05 -->
### d1-feature-escape · decision · #574: unknown --tool refused + --feature <ref> escape

Operator chose to add a raw --feature <ref> escape (repeatable) in addition to refusing unknown tools loudly.

<!-- fr:journal kind=decision scope=spec id=d2-maven-implies-java created=2026-09-23T01:00:06 -->
### d2-maven-implies-java · decision · #574: maven implies java; detect Java version

Operator: maven maps to the java feature with installMaven=true (implies java), AND the required Java version is found from pom and/or project notes. Engine detects from .java-version/.sdkmanrc/.tool-versions/pom.xml; the fr-init skill confirms from project notes and passes java@<major>.

<!-- fr:journal kind=decision scope=spec id=d3-state-field created=2026-09-23T01:00:06 -->
### d3-state-field · decision · #569: explicit target field in IsolationState

Operator chose an explicit optional state field (devcontainer|worktree) with legacy inference from profile==host; scaffold reserves the profile name host.

<!-- fr:journal kind=decision scope=spec id=d4-pin-check-in-scope created=2026-09-23T01:00:07 -->
### d4-pin-check-in-scope · decision · #576: scheduled pinned-asset check included

Operator chose to include a scheduled workflow verifying every pinned glab/tea asset resolves to its checksum, in this PR.

<!-- fr:journal kind=decision scope=spec id=d5-models created=2026-09-23T01:00:07 -->
### d5-models · decision · All fr model tiers bound to claude-opus-5-5

Operator instruction: every subagent and tier runs Opus 5.5; claude-code mechanical/standard/hard/orchestrator bound via fr models set.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-09-23T01:06:02 -->
### spec-review-1 · review · Spec review (independent Opus reviewer): 12 findings, all folded or dispositioned

Folded: (1) gc reap sibling built from type(self) → now routing.target_for_state; background gc spawned with the spawning target's mode (verified local.py:1036, local.py:65-89). (2) down --worktree added to routing (fr-worktree-remove.sh never sets the env). (3) status per-row routing + per-row --stats/--push-check refusal; zero states → no target. (4) existing bogus-env tests + _target stubs listed as rewrites; _target_for is the seam. (5) state lives under <git-common-dir>/fr/isolation, older PATH fr drops 'target' on rewrite → legacy inference permanent, justifies reserved 'host'. (6) 'external' added to the Literal; external without marker fails closed. (7) snippet test under sh + sha256 failure case. (9) code-shape changes listed. (10) fr-isolation skill prose, both mirror syncs, existing matrix rows' notes. (12) pin check via uv run. Refuted: (8) Java 8 risk — feature install.sh:279-287 falls back ms→tem itself. Deferred: (11) failed postCreate debris → gh#578. Refuted-as-redundant: (12b) checksums.txt comparison.
