# Cost-evidence audit (2026-10-06)

Spec: `docs/superpowers/specs/2026-10-06-cost-evidence-design.md` (R11).
Everything below is super-fr's own runs (the archived cursors, usage files and
plan journals in this repo); no foreign host, org or repo appears in any of it.
Commands were run from the workspace on 2026-10-06 with `uv run fr`, the `fr`
built from this branch. A selector may be an ISO timestamp, so a merge hour
can cut a day: runs are placed by the `started` stamp in their cursor.

How to read the tables: **phases** is the plan folder's phase count (the
cursor's `phase/<n>` keys only when the plan is missing: pre-v5 cursors list
just the phases fr dispatched); **turns** and **cost** come from the run's
usage file and include time outside the run's steps (`(outside run)`);
**main cr/out** and **subagent cr/out** are cache-read and output tokens from
the v2 `steps_by_role` split and are `—` for every run captured before that
split existed (see Data limits); **priced** says whether any harness dollar
figure exists; **findings/phase** is journal findings filed against a phase,
per phase; **unphased** counts findings with no phase, never divided in;
**re-opened** is findings the journal fold moved from closed back to open;
**shared** is how many of a run's sessions another run of the same set also
holds. `—` is "nobody measured this", never zero.

## 1. #627 — did the bounded executor handoff (#514) improve handoff quality?

Cutoff: #514's merge, 2026-09-20T16:47Z.

```
$ uv run fr usage compare --before 2026-09-20T16:47:00Z --after 2026-09-20T16:47:00Z
Per run
run                                                           phases  turns  main cr/out  subagent cr/out     cost  priced  findings/phase  unphased  re-opened  shared
------------------------------------------------------------  ------  -----  -----------  ---------------  -------  ------  --------------  --------  ---------  ------
[before] 2026-09-09-feat-issue-464                                 5      —            —                —        —      no            0.80         0          0       —
[before] 2026-09-14-feat-statusline-session-branch                 5      —            —                —        —      no            2.60         0          0      10
[before] 2026-09-18-feat-harness-parity-matrix                     7      —            —                —        —      no            6.57         1          0      13
[before] 2026-09-19-feat-gh-429-followup                           1      —            —                —        —      no               0         0          0       1
[before] 2026-09-19-feat-opencode-subagent-dispatch                6      —            —                —        —      no               2         0          0      12
[before] 2026-09-19-fix-gh-486-gitlab-contents-ref                 7      —            —                —        —      no            3.29         0          0       8
[before] 2026-09-20-feat-bounded-executor-handoff                  5      —            —                —        —      no            4.20         0          0       9
[before] 2026-09-20-feat-phase-holder-identity                     6      —            —                —        —      no            2.50         0          0       8
[before] 2026-09-20-feat-plan-self-review-dispatch-verb-lint       4      —            —                —        —      no            5.50         1          0       1
[before] 2026-09-20-fix-434-phases-file-tier                       5      —            —                —        —      no            1.20         0          0      10
[before] 2026-09-20-fix-fr-run-cursor-cluster                      7      —            —                —        —      no            1.14         0          0       6
[before] 2026-09-20-fix-isolation-reap-data-loss                   4      —            —                —        —      no               2         0          0       1
[before] 2026-09-20-fix-opencode-tier-model-reaches-dispatch       4      —            —                —        —      no            1.50         0          0       7
[after] 2026-09-20-journal-require-reviews-v2                      6      —            —                —        —      no               4         0          0       4
[after] 2026-09-20-unit-record-unification-r2                      7  2,175            —                —  $398.94     yes            0.86         4          0       —
[after] 2026-09-21-feat-fr-triage                                  5    851            —                —  $208.56     yes            7.20         0          0       —
[after] 2026-09-21-fix-497-agent-tool-neutrality                   1    892            —                —  $200.72     yes               1         0          0       1
[after] 2026-09-21-fix-isolation-guard-sentinel-states             4    644            —                —  $120.11     yes               4         1          0       —
[after] 2026-09-22-feat-gh-558-triage-prs                          5      —            —                —        —      no            0.60         0          0       4
[after] 2026-09-22-fix-532-repair-harness-neutrality               5    892            —                —  $200.72     yes            4.60         0          0       1
[after] 2026-09-23-feat-triage-batches                             4    995            —                —   $97.14     yes            9.50         1          0       1
[after] 2026-09-23-fix-457-uninstall-rules                         2      —            —                —        —      no               2         0          0       2
[after] 2026-09-23-fix-526-status-archivable-merged                4    333            —                —   $24.81     yes            0.75         0          0       —
[after] 2026-09-23-fix-lifecycle-container-vs-worktree             6    827            —                —   $86.02     yes           13.17         0          0       —
[after] 2026-09-23-fix-scaffold-batch-574-576-569                  6    620            —                —   $47.19     yes            4.50         0          0       —
[after] 2026-09-24-feat-597-593                                    5    827            —                —   $62.06     yes            2.80         2          0       1
[after] 2026-09-25-feat-lean-cost-aware-process                    4  1,372            —                —  $128.38     yes            9.50         3          0       1
[after] 2026-09-25-fix-605-agent-step-evidence-debt                1     32            —                —    $0.05     yes               0         0          0       2
[after] 2026-09-25-fix-606-writes-dot-dir-prefix                   1    120            —                —    $7.22     yes               0         0          0       —
[after] 2026-09-25-fix-610-closeout-defects                        5  1,938            —                —  $105.36     yes               5         1          0       —
[after] 2026-09-26-feat-batch-archive-repair-scope                 1    227            —                —   $14.91     yes              13         0          0       —
[after] 2026-09-26-feat-batch-container-git-ownership              1    145            —                —    $6.59     yes               5         0          0       —
[after] 2026-09-26-feat-batch-isolation-timeouts                   2    151            —                —    $6.28     yes            0.50         0          0       1
[after] 2026-09-26-feat-batch-one-phase-plans                      1    117            —                —    $5.19     yes               2         0          0       —
[after] 2026-09-26-feat-batch-plan-table-header                    3    152            —                —    $6.47     yes               2         0          0       1
[after] 2026-09-26-feat-batch-release-scripts                      1  1,889            —                —  $158.17     yes               4         0          0       1
[after] 2026-09-26-feat-batch-tests-window                         1    286            —                —   $18.11     yes              14         0          0       1
[after] 2026-09-26-feat-batch-usage-opencode-empty                 1    285            —                —   $20.09     yes               7         0          0       —
[after] 2026-09-26-feat-batch-verify-merge-rewrites                1    576            —                —   $40.83     yes              15         0          0       1
[after] 2026-09-26-feat-ci-time-budget                             2    476            —                —   $29.31     yes               5         0          0       —
[after] 2026-09-26-feat-dynamic-brainstorm-questions               3    584            —                —   $32.90     yes            8.33         0          0       —
[after] 2026-09-26-feat-version-bump-churn                         6    492            —                —   $33.37     yes            1.83         0          0       —
[after] 2026-09-26-fix-624-set-status-drop-level                   3    211            —                —   $17.06     yes            3.67         0          0       —
[after] 2026-09-26-fix-659-isolation-gc-fetch                      1    246            —                —    $0.78     yes               0         0          0       —
[after] 2026-09-26-fix-models-opencode-noop-505                    2      —            —                —        —      no            0.50         0          0       —
[after] 2026-09-27-feat-batch-batch-launch                         2    464            —                —   $22.34     yes               2         0          0       —
[after] 2026-09-27-feat-batch-ci-hardening                         1    164            —                —   $10.21     yes               5         0          0       —
[after] 2026-09-27-feat-batch-spec-ref-writers                     1    230            —                —   $11.57     yes               3         0          0       —
[after] 2026-09-28-feat-batch-closeout-always-2                    6    887            —                —   $52.70     yes            2.67         0          0       —
[after] 2026-09-28-feat-batch-phase-sizing-2                       1    312            —                —   $23.90     yes               8         0          0       —
[after] 2026-09-28-feat-batch-raw-input-relay-2                    1    185            —                —   $12.04     yes               3         0          0       —
[after] 2026-09-28-feat-batch-service-split-2                      6    705            —                —   $46.64     yes            6.17         0          0       —
[after] 2026-09-28-feat-batch-ui-evidence-2                        3    748            —                —   $46.62     yes            5.67         0          0       —
[after] 2026-09-28-feat-gh-759                                     4    433            —                —    $6.09     yes            3.50         1          0       —
[after] 2026-09-29-feat-batch-light-path                           3    591            —                —   $45.75     yes            4.67         0          0       —
[after] 2026-09-29-feat-batch-spec-fidelity                        2    318            —                —   $22.94     yes            5.50         0          0       —
[after] 2026-10-02-feat-batch-opencode-observe-2                   3    693            —                —        —      no            4.33         0          0       —
[after] 2026-10-02-feat-wave-driver                                6  1,773            —                —  $154.67     yes            8.33         0          0       1
[after] 2026-10-03-feat-acceptance-report-deployment               1    119            —                —    $9.44     yes               3         0          0       —
[after] 2026-10-04-feat-batch-drive-merge-train                    1    165            —                —        —      no               4         0          0       —
[after] 2026-10-04-feat-batch-drive-scoped-collect                 1    143            —                —        —      no               4         0          0       —
[after] 2026-10-05-feat-batch-drive-close-tabs                     2    260            —                —        —      no            1.50         0          0       —
[after] 2026-10-05-feat-batch-run-upgrade-midflight                3    389            —                —        —      no            3.33         0          0       —
[after] 2026-10-05-feat-batch-triage-pages-goal                    5    987            —                —        —      no            9.20         0          0       —
[after] 2026-10-05-feat-triage-kanban-board                        3    368            —                —   $27.56     yes               6         0          0       —
[after] 2026-10-06-feat-batch-cost-evidence                        3     32            —                —        —      no               3         0          0       —
[after] 2026-10-06-feat-batch-forge-remainder                      2    303            —                —        —      no            5.50         0          0       —
[after] 2026-10-06-feat-batch-triage-dedupe                        1    369            —                —        —      no              11         0          0       —
[after] 2026-10-06-feat-batch-verification-kinds                   7  1,128            —                —        —      no            4.57         0          0       —

Per set
run                   phases  turns  main cr/out  subagent cr/out    cost  priced  findings/phase  unphased  re-opened     shared
--------------------  ------  -----  -----------  ---------------  ------  ------  --------------  --------  ---------  ---------
before median (n=13)       5      —        — / —            — / —       —    0/13               2         0          0  12 run(s)
after median (n=56)        3    411        — / —            — / —  $28.43   42/56               4         0          0  15 run(s)

* before: 12 of 13 runs share a session with another run of the set; that session's turns and cost count in full under each.
* after: 15 of 56 runs share a session with another run of the set; that session's turns and cost count in full under each.
```

Reading it. The handoff-quality signals the compare can see for both sets are
review findings per phase and re-opened findings. Findings per phase went from
a median of 2 (n=13 runs before) to 4 (n=56 after); re-opened is 0 in both.
That is not evidence the handoff got worse: review practice and the size of
changes moved at the same time, and a reviewer that looks harder files more
findings. **Zero re-opens is not a measurement**: no resolution record in any
archived or live plan journal moves a finding from closed back to open, so the
column cannot separate the two sets. The cost columns cannot be compared:
none of the 13 runs before the cutoff has a dollar figure (0/13 priced, turns
`—`), as usage capture arrived later and backfill found no readable session or
kept figure for those runs. And the sessions overlap: 12 of the 13 before runs
and 15 of the 56 after runs share a session with another run of their set (the
footnote under the table), whose turns and cost then count in full under each.

**Conclusion: inconclusive.** The data that would answer #627 (rework caused by
a thin handoff: re-opened findings, executor turns spent re-discovering
context) does not exist for the before set, and the one signal that does,
findings per phase, is confounded by review practice. Nothing here argues the
bounded handoff failed; nothing here shows it helped.

The binding limits for this section (full list at the end): the sample (n=13
against 56, the after set including runs still open and unpriced), the missing
before-set usage, shared sessions, and the model change straddling the after
set (Opus 5 appears in runs up to 2026-09-22, Opus 5.5 from 2026-09-23).

## 2. #793 item 5 — did phase-per-ask sizing (#792) change what a run costs?

Cutoff: #792's merge, 2026-09-28T21:38Z.

```
$ uv run fr usage compare --before 2026-09-28T21:38:00Z --after 2026-09-28T21:38:00Z
Per run
run                                                           phases  turns  main cr/out  subagent cr/out     cost  priced  findings/phase  unphased  re-opened  shared
------------------------------------------------------------  ------  -----  -----------  ---------------  -------  ------  --------------  --------  ---------  ------
[before] 2026-09-09-feat-issue-464                                 5      —            —                —        —      no            0.80         0          0       —
[before] 2026-09-14-feat-statusline-session-branch                 5      —            —                —        —      no            2.60         0          0      10
[before] 2026-09-18-feat-harness-parity-matrix                     7      —            —                —        —      no            6.57         1          0      13
[before] 2026-09-19-feat-gh-429-followup                           1      —            —                —        —      no               0         0          0       1
[before] 2026-09-19-feat-opencode-subagent-dispatch                6      —            —                —        —      no               2         0          0      12
[before] 2026-09-19-fix-gh-486-gitlab-contents-ref                 7      —            —                —        —      no            3.29         0          0       8
[before] 2026-09-20-feat-bounded-executor-handoff                  5      —            —                —        —      no            4.20         0          0       9
[before] 2026-09-20-feat-phase-holder-identity                     6      —            —                —        —      no            2.50         0          0       8
[before] 2026-09-20-feat-plan-self-review-dispatch-verb-lint       4      —            —                —        —      no            5.50         1          0       1
[before] 2026-09-20-fix-434-phases-file-tier                       5      —            —                —        —      no            1.20         0          0      10
[before] 2026-09-20-fix-fr-run-cursor-cluster                      7      —            —                —        —      no            1.14         0          0       6
[before] 2026-09-20-fix-isolation-reap-data-loss                   4      —            —                —        —      no               2         0          0       1
[before] 2026-09-20-fix-opencode-tier-model-reaches-dispatch       4      —            —                —        —      no            1.50         0          0       7
[before] 2026-09-20-journal-require-reviews-v2                     6      —            —                —        —      no               4         0          0       6
[before] 2026-09-20-unit-record-unification-r2                     7  2,175            —                —  $398.94     yes            0.86         4          0       —
[before] 2026-09-21-feat-fr-triage                                 5    851            —                —  $208.56     yes            7.20         0          0       —
[before] 2026-09-21-fix-497-agent-tool-neutrality                  1    892            —                —  $200.72     yes               1         0          0       1
[before] 2026-09-21-fix-isolation-guard-sentinel-states            4    644            —                —  $120.11     yes               4         1          0       —
[before] 2026-09-22-feat-gh-558-triage-prs                         5      —            —                —        —      no            0.60         0          0       4
[before] 2026-09-22-fix-532-repair-harness-neutrality              5    892            —                —  $200.72     yes            4.60         0          0       1
[before] 2026-09-23-feat-triage-batches                            4    995            —                —   $97.14     yes            9.50         1          0       1
[before] 2026-09-23-fix-457-uninstall-rules                        2      —            —                —        —      no               2         0          0       2
[before] 2026-09-23-fix-526-status-archivable-merged               4    333            —                —   $24.81     yes            0.75         0          0       —
[before] 2026-09-23-fix-lifecycle-container-vs-worktree            6    827            —                —   $86.02     yes           13.17         0          0       —
[before] 2026-09-23-fix-scaffold-batch-574-576-569                 6    620            —                —   $47.19     yes            4.50         0          0       —
[before] 2026-09-24-feat-597-593                                   5    827            —                —   $62.06     yes            2.80         2          0       1
[before] 2026-09-25-feat-lean-cost-aware-process                   4  1,372            —                —  $128.38     yes            9.50         3          0       1
[before] 2026-09-25-fix-605-agent-step-evidence-debt               1     32            —                —    $0.05     yes               0         0          0       2
[before] 2026-09-25-fix-606-writes-dot-dir-prefix                  1    120            —                —    $7.22     yes               0         0          0       —
[before] 2026-09-25-fix-610-closeout-defects                       5  1,938            —                —  $105.36     yes               5         1          0       —
[before] 2026-09-26-feat-batch-archive-repair-scope                1    227            —                —   $14.91     yes              13         0          0       —
[before] 2026-09-26-feat-batch-container-git-ownership             1    145            —                —    $6.59     yes               5         0          0       —
[before] 2026-09-26-feat-batch-isolation-timeouts                  2    151            —                —    $6.28     yes            0.50         0          0       1
[before] 2026-09-26-feat-batch-one-phase-plans                     1    117            —                —    $5.19     yes               2         0          0       —
[before] 2026-09-26-feat-batch-plan-table-header                   3    152            —                —    $6.47     yes               2         0          0       1
[before] 2026-09-26-feat-batch-release-scripts                     1  1,889            —                —  $158.17     yes               4         0          0       —
[before] 2026-09-26-feat-batch-tests-window                        1    286            —                —   $18.11     yes              14         0          0       1
[before] 2026-09-26-feat-batch-usage-opencode-empty                1    285            —                —   $20.09     yes               7         0          0       —
[before] 2026-09-26-feat-batch-verify-merge-rewrites               1    576            —                —   $40.83     yes              15         0          0       1
[before] 2026-09-26-feat-ci-time-budget                            2    476            —                —   $29.31     yes               5         0          0       —
[before] 2026-09-26-feat-dynamic-brainstorm-questions              3    584            —                —   $32.90     yes            8.33         0          0       —
[before] 2026-09-26-feat-version-bump-churn                        6    492            —                —   $33.37     yes            1.83         0          0       —
[before] 2026-09-26-fix-624-set-status-drop-level                  3    211            —                —   $17.06     yes            3.67         0          0       —
[before] 2026-09-26-fix-659-isolation-gc-fetch                     1    246            —                —    $0.78     yes               0         0          0       —
[before] 2026-09-26-fix-models-opencode-noop-505                   2      —            —                —        —      no            0.50         0          0       —
[before] 2026-09-27-feat-batch-batch-launch                        2    464            —                —   $22.34     yes               2         0          0       —
[before] 2026-09-27-feat-batch-ci-hardening                        1    164            —                —   $10.21     yes               5         0          0       —
[before] 2026-09-27-feat-batch-spec-ref-writers                    1    230            —                —   $11.57     yes               3         0          0       —
[before] 2026-09-28-feat-batch-closeout-always-2                   6    887            —                —   $52.70     yes            2.67         0          0       —
[before] 2026-09-28-feat-batch-phase-sizing-2                      1    312            —                —   $23.90     yes               8         0          0       —
[before] 2026-09-28-feat-batch-raw-input-relay-2                   1    185            —                —   $12.04     yes               3         0          0       —
[before] 2026-09-28-feat-batch-service-split-2                     6    705            —                —   $46.64     yes            6.17         0          0       —
[before] 2026-09-28-feat-batch-ui-evidence-2                       3    748            —                —   $46.62     yes            5.67         0          0       —
[before] 2026-09-28-feat-gh-759                                    4    433            —                —    $6.09     yes            3.50         1          0       —
[after] 2026-09-29-feat-batch-light-path                           3    591            —                —   $45.75     yes            4.67         0          0       —
[after] 2026-09-29-feat-batch-spec-fidelity                        2    318            —                —   $22.94     yes            5.50         0          0       —
[after] 2026-10-02-feat-batch-opencode-observe-2                   3    693            —                —        —      no            4.33         0          0       —
[after] 2026-10-02-feat-wave-driver                                6  1,773            —                —  $154.67     yes            8.33         0          0       —
[after] 2026-10-03-feat-acceptance-report-deployment               1    119            —                —    $9.44     yes               3         0          0       —
[after] 2026-10-04-feat-batch-drive-merge-train                    1    165            —                —        —      no               4         0          0       —
[after] 2026-10-04-feat-batch-drive-scoped-collect                 1    143            —                —        —      no               4         0          0       —
[after] 2026-10-05-feat-batch-drive-close-tabs                     2    260            —                —        —      no            1.50         0          0       —
[after] 2026-10-05-feat-batch-run-upgrade-midflight                3    389            —                —        —      no            3.33         0          0       —
[after] 2026-10-05-feat-batch-triage-pages-goal                    5    987            —                —        —      no            9.20         0          0       —
[after] 2026-10-05-feat-triage-kanban-board                        3    368            —                —   $27.56     yes               6         0          0       —
[after] 2026-10-06-feat-batch-cost-evidence                        3     32            —                —        —      no               3         0          0       —
[after] 2026-10-06-feat-batch-forge-remainder                      2    303            —                —        —      no            5.50         0          0       —
[after] 2026-10-06-feat-batch-triage-dedupe                        1    369            —                —        —      no              11         0          0       —
[after] 2026-10-06-feat-batch-verification-kinds                   7  1,128            —                —        —      no            4.57         0          0       —

Per set
run                   phases  turns  main cr/out  subagent cr/out    cost  priced  findings/phase  unphased  re-opened     shared
--------------------  ------  -----  -----------  ---------------  ------  ------  --------------  --------  ---------  ---------
before median (n=54)       4    476        — / —            — / —  $29.31   37/54            3.14         0          0  25 run(s)
after median (n=15)        3    368        — / —            — / —  $27.56    5/15            4.57         0          0          —

* before: 25 of 54 runs share a session with another run of the set; that session's turns and cost count in full under each.
```

Reading it. Medians moved little: phases per run 4 before (n=54) against 3
after (n=15), turns 476 against 368, cost $29.31 against $27.56, findings per
phase 3.14 against 4.57, re-opened 0 against 0. The differences sit inside the
per-run spread (per-run costs in the table run from under a dollar to several
hundred), and the after set is small and mostly unpriced: only 5 of its 15 runs
carry a dollar figure (the sessions of the latest runs were still open when
captured and were never re-priced), against 37 of 54 before. The phase median
did fall by one, which is the direction the sizing rule intends, but it cannot
be told from noise at n=15; and 25 of the 54 before runs share a session with
another before run, so their turns and cost are double-counted in the median.

**Conclusion: inconclusive, leaning "no detectable change in cost".** There is
no visible shift in turns, cost or findings per phase; phases per run fell from
4 to 3 but on 15 runs. Re-run `fr usage compare` once a few dozen runs have been
captured after the change. The model change confounds this window too, in the
other direction from what one might assume: the unbounded before set includes the
2026-09-09..22 runs, among them Opus 5 runs and the most expensive priced runs,
so the before median mixes models and its cost is not comparable with the after
set, which ran Opus 5.5 (Sonnet 5.5 from 2026-09-26) throughout. Bounding the
before set is not possible with `compare`'s selectors (they are cutoffs, not
ranges), so the mix is stated, not removed.

## 3. #593 — decision rules for restarting the main session (option 1) or doing nothing (option 4)

#593's rules: adopt option 1 if the main session is more than 60% of cost AND
its per-turn cache read grows more than 2x across steps on the larger tasks.

**Which figures were used.** `fr usage compare --steps` prints, per set, the
main session's per-step turns, tokens, cost and dollars per turn, and says
which source served each run: the v2 split (`steps_by_role.main`) where the
file has one, else the step figures of the session's `role: main` entry. No
archived run carries the split (the only two usage files that do are runs still
in flight, and the sets above hold them only as unpriced rows), so both sets
below read `role: main entry`, whose step figures carry turns and dollars but
no tokens: the cache-read and output columns are `—`. That has consequences:

- Main-session **share of cost** (the first rule) cannot be measured. A v1
  `main` entry holds the main session's whole transcript, and only five
  archived files carry a separate subagent entry, none with a subagent dollar
  figure; whether subagent turns were folded into the main figure depends on
  the capture date (subagents were folded in only after gh#637), so a share
  would be a guess. **Not determined.**
- **Cache read per main-session turn by step** (the second rule) needs tokens
  per step, which v1 files do not carry. The nearest observable proxy is
  **dollars per main-session turn by step**: cache read dominates a long
  session's cost, so it tracks context size, but it carries the model price and
  is not the rule's measure.
- `compare` cannot restrict a set to **larger tasks**, which the rule names;
  the sets are every run on one side of a cutoff.

```
$ uv run fr usage compare --before 2026-09-20T16:47:00Z --after 2026-09-20T16:47:00Z --steps    (the step tables only; the run tables are as in section 1)
Main-session steps (before): medians over the runs that have the step
main = role: main entry in 12 run(s), none in 1 run(s)
step       runs  turns  cache-read  output  cost  $/turn
---------  ----  -----  ----------  ------  ----  ------
implement    12      —           —       —     —       —

Main-session steps (after): medians over the runs that have the step
main = role: main entry in 55 run(s), none in 1 run(s)
step              runs  turns  cache-read  output    cost  $/turn
----------------  ----  -----  ----------  ------  ------  ------
brainstorm          50     23           —       —   $1.59  $0.058
spec-review         48  33.50           —       —   $1.62  $0.045
plan                49      8           —       —   $0.71  $0.083
plan-review          4   0.50           —       —   $0.02  $0.017
implement           54    218           —       —  $13.69  $0.056
journal-check       13      1           —       —   $0.07  $0.074
deliver             49     18           —       —   $1.55  $0.089
(outside run)       51     30           —       —   $4.64  $0.099
spec-plan-review     1     28           —       —       —       —
```

```
$ uv run fr usage compare --before 2026-09-28T21:38:00Z --after 2026-09-28T21:38:00Z --steps    (the step tables only; the run tables are as in section 2)
Main-session steps (before): medians over the runs that have the step
main = role: main entry in 52 run(s), none in 2 run(s)
step           runs  turns  cache-read  output    cost  $/turn
-------------  ----  -----  ----------  ------  ------  ------
brainstorm       35     19           —       —   $1.57  $0.058
spec-review      35     27           —       —   $1.56  $0.045
plan             35      8           —       —   $0.69  $0.081
plan-review       4   0.50           —       —   $0.02  $0.017
implement        52    189           —       —  $11.42  $0.055
journal-check    12      1           —       —   $0.09  $0.086
deliver          35     21           —       —   $1.93  $0.086
(outside run)    36  31.50           —       —   $4.27  $0.091

Main-session steps (after): medians over the runs that have the step
main = role: main entry in 15 run(s)
step              runs  turns  cache-read  output    cost  $/turn
----------------  ----  -----  ----------  ------  ------  ------
brainstorm          15     29           —       —   $1.78  $0.068
spec-review         13     35           —       —   $2.01  $0.060
plan                14      8           —       —   $0.81  $0.101
implement           14    267           —       —  $15.48  $0.064
journal-check        1      3           —       —   $0.06  $0.019
deliver             14     11           —       —   $0.81  $0.116
(outside run)       15     24           —       —   $4.65  $0.129
spec-plan-review     1     28           —       —       —       —
```

Reading it. In the #793 after set (all Opus 5.5, n=15) the proxy grows 1.7x from
brainstorm ($0.068 per turn) to deliver ($0.116); in the larger #627 after set
(n=56) it grows 1.5x ($0.058 to $0.089). Both are below the rule's 2x.
`implement`, the longest step by turns, is where most of the main session's
cost sits (median $13.69 of the steps shown for the #627 after set). The
`(outside run)` row, session time before the first or after the last step
timestamp, is the most expensive step per turn ($0.099 to $0.129): those turns
run in the largest contexts, and they sit outside any step boundary a restart
could reset.

**Conclusion: inconclusive; if a choice must be made today, option 4.** The
first rule (main share above 60%) cannot be evaluated at all, so option 1 cannot
be adopted by #593's own rules. The second rule's proxy gives 1.5x to 1.7x on
the typical run, below 2x, but it is a dollar proxy, not cache read, the sets
are not restricted to larger tasks, and the growth that does show up sits in
`(outside run)`. Option 4 stands by default: it costs nothing and nothing here
contradicts it. Re-run this once runs captured with the v2 split accumulate: the
same `--steps` output then reads `steps_by_role.main` and fills the cache-read
and output columns, making the rule's figures direct readings instead of
proxies.

**Recommendation between #593 options 1 and 4: option 4 (do nothing now)**,
revisited after a few dozen runs have been captured with the split. Option 0
(per-step main-session tokens) is what makes that revisit possible and ships in
this PR's usage v2 format.

## Data limits

Every limit the audit ran into, in one list:

1. **Sample sizes.** n=13 against 56 (#627), 54 against 15 (#793). The most
   recent runs are the least informative: their captures are open or unpriced.
2. **Unpriced captures.** Claude Code writes a session's cost only when the
   session exits, so a capture taken while the session is open carries tokens
   but no dollars. Priced counts: 0/13 and 42/56 for #627; 37/54 and 5/15 for
   #793. Medians are over the runs that have the figure, so a median cost is
   over fewer runs than `n`.
3. **No token split for archived runs.** Main against subagent cache-read and
   output are `—` for every run captured before this branch. The v2 files that
   have the split are two in-flight runs, so the token columns say nothing
   yet. Refreshing an archived file at re-pricing writes no split by design.
4. **The Opus 5 to Opus 5.5 change.** Opus 5 appears in runs up to 2026-09-22,
   Opus 5.5 from 2026-09-23 (Sonnet 5.5 from 2026-09-26). The #627 after set
   straddles it. **The #793 before set also mixes models**: it is an unbounded
   cutoff, so it holds the 2026-09-09..22 runs (Opus 5 among them, and the most
   expensive priced runs) as well as Opus 5.5 ones, while its after set is Opus
   5.5 only. Per-turn dollars and cache behaviour differ by model, so a
   before/after cost reading across either cutoff is confounded.
5. **Attempt `model` before gh#637 holds the binding, not what ran.** For
   subagent attempts recorded before run version 9 the `model` field is the
   tier's configured binding; the observed model is only known where a session
   transcript was read. Per-phase "ran against bound" mismatches cannot be
   computed for the older runs.
6. **Hermes delegates do not attribute.** A Hermes delegate's messages are not
   attributed to a subagent in the harness's records, so a Hermes run's
   subagent column reads `—` or folds into the main figure. No run in these
   windows is known to be a Hermes run, but the limit applies to any future
   Hermes comparison.
7. **Zero re-opens.** No resolution record in the journal corpus re-opens a
   finding, so the re-opened column is 0 everywhere and does not discriminate.
8. **Findings per phase is a confounded proxy** for handoff quality: it moves
   with review thoroughness and change size as much as with the handoff.
9. **Shared sessions and `(outside run)`.** A session shared by two runs of a
   set counts in full under each (12 of 13 and 15 of 56 runs in #627's sets;
   25 of 54 in #793's before set; the footnote under each table), so medians
   of turns and cost over such runs double-count it. A session that outlives a
   run also contributes `(outside run)` spend to the run's cost and turns.
   Dollars per turn by step is a proxy for cache read per turn and carries the
   model price.
10. **Out of scope: the measurement campaign.** #593's three-task by
    two-harness campaign with a plain-agent baseline and a blind review of both
    diffs was not run; this audit is observational over runs that already
    exist.
