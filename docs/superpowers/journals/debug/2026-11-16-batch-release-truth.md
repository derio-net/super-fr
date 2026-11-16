<!-- fr:journal-schema=4 -->
# Journal: 2026-11-16-batch-release-truth

<!-- fr:journal kind=repro scope=debug id=cb1563c4510f created=2026-11-16T18:18:25+00:00 -->
### cb1563c4510f · repro · Five release-robustness defects, each reproducible from the code

Batch release-truth (#1201 #1290 #1393 #1291 #1202). Each was confirmed against the code on origin/main 4eb40198d; per-defect failing tests follow.

<!-- fr:journal kind=root-cause scope=debug id=a3bf8f63c6c5 created=2026-11-16T18:18:27+00:00 -->
### a3bf8f63c6c5 · root-cause · #1201: _version_tuple returns None for X.Y.ZrcN, and _check_fr reads None as ok

packages/fr/src/fr/cloud.py: int('0rc7') raises ValueError -> None; `ok = have is None or ...` makes every RC install pass the fr-version check. Fix: parse with packaging.version (fr already depends on it); an unparseable installed version is not ok.

<!-- fr:journal kind=root-cause scope=debug id=7e2f56ea7143 created=2026-11-16T18:18:29+00:00 -->
### 7e2f56ea7143 · root-cause · #1290: finish() reads 'tag exists' as 'released'

scripts/release.py tag_and_release pushes the tag before gh release create; finish returns 'already tagged; nothing to do' whenever the tag exists, so a failed create is never retried. Fix: when the tag exists, ask gh release view; create the Release when it is missing (no retag), refuse when the read fails for another reason.

<!-- fr:journal kind=root-cause scope=debug id=54006a2d9216 created=2026-11-16T18:18:30+00:00 -->
### 54006a2d9216 · root-cause · #1393: _rcs_above lists RC tags HEAD does not contain

scripts/release.py _rcs_above reads every RC tag; `since = rcs[-1][1]` can be a sibling commit's tag whose tree always differs, so every run cuts another RC. Fix: 'since' comes from RC tags merged into HEAD; RC numbering still counts every tag so a sibling RC number is never reused.

<!-- fr:journal kind=root-cause scope=debug id=d9d5e306aba5 created=2026-11-16T18:18:32+00:00 -->
### d9d5e306aba5 · root-cause · #1291: one concurrency group drops a pending workflow_dispatch run

.github/workflows/release.yml: group: release, cancel-in-progress false. GitHub keeps one pending run per group, so a later push run replaces a pending dispatch --version run. Fix: dispatch runs get a group of their own, keyed by run id.

<!-- fr:journal kind=root-cause scope=debug id=1773ac64f6c1 created=2026-11-16T18:18:33+00:00 -->
### 1773ac64f6c1 · root-cause · #1202: a channel switch keeps untracked files in the managed cache

scripts/bootstrap.sh switches with checkout -f and no clean; install.sh's preflight then refuses 'untracked files'. Fix: git clean -fdx after the switch (the cache is bootstrap-managed, no operator work lives there).

<!-- fr:journal kind=finding scope=debug id=f-1201 created=2026-11-16T18:36:57+00:00 state=fixed -->
### f-1201 · finding [fixed] · #1201 fixed: the cloud doctor compares RC installs

fr.cloud._parse_version uses packaging.version (both RC spellings); an unparseable installed version is not ok, an unparseable latest stays unknown. Pinned by tests/unit/test_cloud_remedy.py::test_an_rc_install_is_compared_not_waved_through and ::test_an_unparseable_installed_version_is_not_ok.

<!-- fr:journal kind=finding scope=debug id=f-1290 created=2026-11-16T18:36:59+00:00 state=fixed -->
### f-1290 · finding [fixed] · #1290 fixed: a tag with no GitHub Release gets one on the next run

finish() asks release_exists (gh release view); 'not found' -> create_release on the existing tag (no retag), any other failed read refuses. Pinned by test_release_script.py::test_gh1290_a_failed_release_create_is_retried_on_the_next_run, ::test_gh1290_a_tag_with_its_release_is_left_alone, ::test_gh1290_an_unreadable_release_refuses_rather_than_guessing.

<!-- fr:journal kind=finding scope=debug id=f-1393 created=2026-11-16T18:37:01+00:00 state=fixed -->
### f-1393 · finding [fixed] · #1393 fixed: the RC since-tag is one HEAD contains

_rcs_above(merged=True) picks 'since'; RC numbering still counts every tag. Pinned by test_gh1393_an_rc_tag_head_does_not_contain_is_not_the_since_tag and test_gh1393_the_next_rc_still_numbers_past_a_sibling_rc_tag.

<!-- fr:journal kind=finding scope=debug id=f-1291 created=2026-11-16T18:37:03+00:00 state=fixed -->
### f-1291 · finding [fixed] · #1291 fixed: a dispatch run has its own concurrency group

release.yml group: release-dispatch-<run_id> for workflow_dispatch, 'release' otherwise. A dispatch beside a push run is superseded loudly by publish's base check. Pinned by test_release_workflow.py::test_a_dispatch_run_has_a_group_of_its_own.

<!-- fr:journal kind=finding scope=debug id=f-1202 created=2026-11-16T18:37:05+00:00 state=fixed -->
### f-1202 · finding [fixed] · #1202 fixed: a channel switch cleans the managed cache

bootstrap.sh runs git clean -q -f -d after the checkout (no -x: ignored files, which the preflight does not count, stay). Pinned by test_install_channels.py::test_a_channel_switch_removes_untracked_files_from_the_managed_cache and ::test_a_channel_switch_keeps_ignored_files_in_the_managed_cache.
