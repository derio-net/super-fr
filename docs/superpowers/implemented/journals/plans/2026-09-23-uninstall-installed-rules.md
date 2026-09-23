# Journal: 2026-09-23-uninstall-installed-rules

<!-- fr:journal kind=finding scope=plan id=e52755b61b87 created=2026-09-23T14:48:34 phase=1 state=open -->
### e52755b61b87 · finding [open] · Uninstall incomplete for two rule files (phase 1)

scripts/install.sh (lines 523-530) installs four rule files: fr-plan-override.md, fr-isolation-required.md, no-claude-p-batch.md, fr-worktree-override.md. But uninstall (lines 96-97) only removes fr-plan-override.md, vk-plan-override.md (retired), and fr-worktree-override.md. Missing: fr-isolation-required.md and no-claude-p-batch.md.

<!-- fr:journal kind=finding scope=plan id=uninstall-rule-derivation created=2026-09-23T14:51:14 phase=1 state=fixed -->
### uninstall-rule-derivation · finding [fixed] · Derive rule regression from install-side declaration (phase 1)

Phase review found the regex over literal cp lines would break when implementation centralizes filenames. Updated the helper to read CLAUDE_RULES when present, with legacy cp parsing only for the initial red test.

<!-- fr:journal kind=finding scope=plan id=uninstall-rule-derivation-review created=2026-09-23T14:51:21 phase=1 state=open -->
### uninstall-rule-derivation-review · finding [open] · Literal cp parsing would break after installer refactor (phase 1)

Review identified that deriving expected rule names only from literal cp lines would leave the regression test with no names once install.sh used a shared rule array.

<!-- fr:journal kind=finding scope=plan id=uninstall-rule-derivation-review-resolved created=2026-09-23T14:51:21 state=fixed resolves=uninstall-rule-derivation-review -->
### uninstall-rule-derivation-review-resolved · finding [fixed] · resolves uninstall-rule-derivation-review: Literal cp parsing would break after installer refactor

The helper now reads the authoritative CLAUDE_RULES array, with cp parsing only as a temporary red-test fallback.

<!-- fr:journal kind=review scope=plan id=e8d9d299f484 created=2026-09-23T14:51:32 phase=1 -->
### e8d9d299f484 · review · Phase 1 review: test is durable across implementation refactor (phase 1)

Reviewed red integration coverage against the spec. Review found the install-rule extractor must survive centralizing the install commands; fixed by preferring the CLAUDE_RULES array, retaining literal cp extraction only while the implementation is still red. Focused test reports expected failure for fr-isolation-required.md and passes retired-rule cleanup; ruff passes.

<!-- fr:journal kind=finding scope=plan id=e52755b61b87-resolved created=2026-09-23T14:51:48 state=fixed resolves=e52755b61b87 -->
### e52755b61b87-resolved · finding [fixed] · resolves e52755b61b87: Uninstall incomplete for two rule files

Will be resolved in phase 2 by using one Claude rule filename array for uninstall removal and install copying, covered by the failing all-installed-rules integration test.

<!-- fr:journal kind=discovery scope=plan id=refactored-to-single-list created=2026-09-23T14:56:48 phase=2 -->
### refactored-to-single-list · discovery · Refactored install.sh to use single authoritative CLAUDE_RULES array (phase 2)

Both install copy and --uninstall removal now derive from one central CLAUDE_RULES array definition, making the relationship durable and test-following. Retired rules are kept in a separate RETIRED_CLAUDE_RULES array.

<!-- fr:journal kind=discovery scope=plan id=test-now-reads-array created=2026-09-23T14:56:52 phase=2 -->
### test-now-reads-array · discovery · Updated test_install_copies_rules to read CLAUDE_RULES array (phase 2)

The unit test now extracts the CLAUDE_RULES array via regex instead of searching for literal 'rules/' strings in the script. This allows it to remain coupled to the authoritative array even as install.sh's implementation changes.

<!-- fr:journal kind=finding scope=plan id=acceptance-note-context created=2026-09-23T15:01:30 phase=2 state=open -->
### acceptance-note-context · finding [open] · Preserve existing acceptance note (phase 2)

Review found replacing the invariants-tripwires notes dropped existing acceptance context. Restored the prior explanation and appended the uninstall regression evidence.

<!-- fr:journal kind=finding scope=plan id=acceptance-note-context-resolved created=2026-09-23T15:01:30 state=fixed resolves=acceptance-note-context -->
### acceptance-note-context-resolved · finding [fixed] · resolves acceptance-note-context: Preserve existing acceptance note

Restored the prior acceptance note and appended uninstall test evidence; reports regenerated deterministically.

<!-- fr:journal kind=review scope=plan id=5078d42d2bf9 created=2026-09-23T15:01:35 phase=2 -->
### 5078d42d2bf9 · review · Phase 2 review: shared rule list and acceptance context (phase 2)

Reviewed install/uninstall loops, installer source list guard, fake-home integration coverage, and acceptance updates. No remaining findings. The shared CLAUDE_RULES list drives both copies and uninstall; retired vk-plan-override remains explicitly removed. Preserved existing acceptance context and appended the regression evidence.
