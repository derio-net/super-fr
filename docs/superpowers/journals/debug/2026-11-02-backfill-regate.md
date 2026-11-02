<!-- fr:journal-schema=3 -->
# Journal: 2026-11-02-backfill-regate

<!-- fr:journal kind=repro scope=debug id=repro created=2026-11-02T19:00:24+00:00 -->
### repro · repro · dry run lists passed-gate PRs as owed; --yes files no tracker for them

On super-fr (v6.1.0-rc.11), `fr gate backfill --plan <scratch>` lists row:release-superseded-not-retried and spec:2026-11-01-ci-speed#step1/2 (PR #1276) and spec:2026-10-22-fr-ops#step1 (PR #1228) as `gate=tester ... -> owed`. Both PRs carry gate:tester-passed. Nothing in the summary says so. In apply.py, an already-passed PR returns at step 1 with a discharge line, so the owed item gets no tracker. gh#1322.

<!-- fr:journal kind=hypothesis scope=debug id=h1-relabel created=2026-11-02T19:00:34+00:00 -->
### h1-relabel · hypothesis · --yes re-adds gate:tester to a passed PR

Ruled out by reading apply.py:247-253. Both pr_view clients (real_ghclient, real_ghrestclient) flatten labels to names, and gate_label(gate, passed=True) is checked before any add. --yes never relabels. The re-gate fear comes from the dry run reading as 'owed' with the passed state hidden.

<!-- fr:journal kind=root-cause scope=debug id=rc created=2026-11-02T19:00:42+00:00 -->
### rc · root-cause · the plan path has no 'gate already passed' state

The dry run (gate_cmd.backfill_command -> render.summary) never reads the delivering PR's labels, so a passed PR's entry reads 'owed' like any other. Apply's passed branch (spec §G step 1) returns before step 2, so the still-owed item goes untracked. The operator decided against both: the item stays tracked, only the relabel is skipped.
