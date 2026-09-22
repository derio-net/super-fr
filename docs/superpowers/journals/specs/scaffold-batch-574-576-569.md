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
