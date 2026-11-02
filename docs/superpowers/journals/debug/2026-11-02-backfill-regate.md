<!-- fr:journal-schema=3 -->
# Journal: 2026-11-02-backfill-regate

<!-- fr:journal kind=repro scope=debug id=repro created=2026-11-02T19:00:24+00:00 -->
### repro · repro · dry run lists passed-gate PRs as owed; --yes files no tracker for them

On super-fr (v6.1.0-rc.11), `fr gate backfill --plan <scratch>` lists row:release-superseded-not-retried and spec:2026-11-01-ci-speed#step1/2 (PR #1276) and spec:2026-10-22-fr-ops#step1 (PR #1228) as `gate=tester ... -> owed`. Both PRs carry gate:tester-passed. Nothing in the summary says so. In apply.py, an already-passed PR returns at step 1 with a discharge line, so the owed item gets no tracker. gh#1322.
