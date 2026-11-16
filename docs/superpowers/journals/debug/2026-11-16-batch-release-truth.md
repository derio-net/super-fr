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
