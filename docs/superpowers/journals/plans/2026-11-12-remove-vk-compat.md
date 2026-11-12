<!-- fr:journal-schema=3 -->
# Journal: 2026-11-12-remove-vk-compat

<!-- fr:journal kind=discovery scope=plan id=p1-github-rest-capture-keeps-old-env-name created=2026-11-12T16:58:57+00:00 phase=1 -->
### p1-github-rest-capture-keeps-old-env-name · discovery · A recorded GitHub PR capture still names VK_REPO_ROOT (phase 1)

tests/fixtures/github_rest/repo_pulls_1080_files-per_page-100-page-1.json is a capture of a historical PR's file list and contains VK_REPO_ROOT. Captures are never rewritten, so the no-VK-env-names tripwire in tests/unit/test_vk_compat_removed.py skips tests/fixtures/github_rest.

<!-- fr:journal kind=discovery scope=plan id=p1-retired-plugin-seed-counts-as-sibling created=2026-11-12T16:58:57+00:00 phase=1 -->
### p1-retired-plugin-seed-counts-as-sibling · discovery · Replacing the seeded superpowers-for-vk id with retired-plugin made it a sibling (phase 1)

With the installer's sibling grep no longer excluding the vk plugin id, a seeded retired-plugin@derio-net entry reads as a sibling registration and test_no_sibling_note_when_only_our_own_ids_were_purged failed. The seed entry and its assertion were dropped instead of renamed; the bare-org purge is still covered by the super-fr and super-fr-dispatch ids.

<!-- fr:journal kind=discovery scope=plan id=p1-acceptance-rows-owed-phase-2 created=2026-11-12T16:58:57+00:00 phase=1 -->
### p1-acceptance-rows-owed-phase-2 · discovery · Three acceptance rows for this feature are still not-implemented (phase 1)

fr acceptance check lists installer-names-no-vk-residue, init-migrate-removed and isolation-up-requires-branch as not-implemented. Phase 1 added the unit tests that verify them in tests/unit/test_vk_compat_removed.py, but moving them needs fr acceptance set-status; this was not in the phase's steps, so the orchestrator or phase 2 should do it.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-12T16:58:57+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

deletions only

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-12T16:58:57+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

mechanical rename

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-12T16:58:57+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

deletions only
