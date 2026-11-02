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

<!-- fr:journal kind=finding scope=debug id=fix created=2026-11-02T19:08:20+00:00 state=fixed -->
### fix · finding [fixed] · tracked-only path for an already-passed gate

apply._apply: a passed PR is never relabelled; its tracker is filed, reused or adopted via trackers.passed_tracker_body / adopt_passed_comment, whose markers (fr-gate-passed:, fr-gate-adopt-passed:) fr_gate_marker / fr_adopt_marker read as None, so close_gate_trackers never closes them. Dry run: delivery.mark_gate_passed sets PlanEntry.gate_passed from the cached pr_view, and render prints it. Decision stays 'owed'. Failing-first tests: test_gatebackfill_apply.py::test_gh1322_* (tester+devops, file, rewrite held, adopt, re-run, §H converse), test_gate_cmd.py::test_gh1322_the_dry_run_says_a_passed_gate_is_tracked_only_and_never_re_gated. Converse (§H closes held trackers of still-owed keys on a partial pass) filed as gh#1323.

<!-- fr:journal kind=discovery scope=debug id=pr1228-other-gate created=2026-11-02T19:10:14+00:00 -->
### pr1228-other-gate · discovery · PR #1228 passed devops, backfill computes tester: not a re-gate, a new gate

Live check after the fix: #1228 carries gate:devops-passed (not gate:tester-passed as the brief says). spec:2026-10-22-fr-ops#step1 resolves to gate=tester, so the fix rightly does not flag it, and --yes would ADD gate:tester to #1228, a gate it never had, which would hold the release. That is the backfill's ordinary job, but on a PR already passed under another gate. Left for the operator: set the entry's decision (park/na) or gate: in the plan file, or decide a rule 'any passed post-merge gate counts'. Not changed in this PR.
