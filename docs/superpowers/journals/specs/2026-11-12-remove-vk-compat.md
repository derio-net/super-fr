<!-- fr:journal-schema=3 -->
# Journal: 2026-11-12-remove-vk-compat

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-12T15:43:42+00:00 input=true -->
### operator-brief · discovery · The operator's brief, as typed

"remove the vk compatibility code via /fr-goal."

Earlier in the same session, about the wording cleanup that preceded this
(#1416): "vk references must be removed. There is no vk anymore. Only fr."
and "The vk I was referring to was not the VK runner, but the original vk
command and relevant wording".

<!-- fr:journal kind=decision scope=spec id=d1-vk-version-removed-with-migration created=2026-11-12T15:43:42+00:00 decided_by=operator -->
### d1-vk-version-removed-with-migration · decision · vk_version is removed with a migration that also strips the archive

Asked: keep the inert `vk_version` plan field, stop writing it, or remove
it with a migration. Operator: "3 and the migration also removes the field
from the archives. Do we have other such inert fields?" This overrides the
artifact-versioning rule's "archived artifacts are frozen" for this one
repair. Answer to the side question, from the code: `vk_version` is the
only field in an artifact model marked inert.

<!-- fr:journal kind=decision scope=spec id=d2-env-vars-hard-rename created=2026-11-12T15:43:42+00:00 decided_by=operator -->
### d2-env-vars-hard-rename · decision · VK_REPO_ROOT and VK_INSTALL_SKIP_PREFLIGHT are hard-renamed to FR_*

Operator chose the hard rename with no fallback for the old names.

<!-- fr:journal kind=decision scope=spec id=d3-up-branch-required created=2026-11-12T15:43:42+00:00 decided_by=operator -->
### d3-up-branch-required · decision · fr isolation up requires --branch

Operator chose to make `--branch` required over renaming the `vk-iso/work` default.

<!-- fr:journal kind=decision scope=spec id=d4-old-install-paths-removed created=2026-11-12T15:43:42+00:00 decided_by=operator -->
### d4-old-install-paths-removed · decision · Every old-install path goes, wrapper recognition included

Operator confirmed every machine and consumer repo is past the rename:
the installer purges, `fr init migrate` and the `superpowers-for-vk`
validator-wrapper recognition are all removed.

<!-- fr:journal kind=decision scope=spec id=d5-major-bump created=2026-11-12T15:43:42+00:00 decided_by=operator -->
### d5-major-bump · decision · The change fragment declares a major bump

Operator chose major, following the repo's rule for breaking CLI and plan-schema changes.

<!-- fr:journal kind=decision scope=spec id=d6-verification-ci-tests created=2026-11-12T15:43:42+00:00 decided_by=operator -->
### d6-verification-ci-tests · decision · Verified by unit tests in CI; no walk, no post-merge gate

Operator chose CI tests only. Each row is `none` with its reason; the run's gate is none.
