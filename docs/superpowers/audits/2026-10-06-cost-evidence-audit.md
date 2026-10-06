# Cost-evidence audit (2026-10-06)

Spec: `docs/superpowers/specs/2026-10-06-cost-evidence-design.md` (R11).
Everything below is super-fr's own runs (the archived cursors, usage files and
plan journals in this repo); no foreign host, org or repo appears in any of it.
Commands were run from the workspace on 2026-10-06 with `uv run fr`, the `fr`
built from this branch. A selector may be an ISO timestamp, so a merge hour
can cut a day: runs are placed by the `started` stamp in their cursor.

How to read the tables: **phases** counts the cursor's `phase/<n>/...` units
(`items` in cursors before 2026-09-20); **turns** and **cost** come from the
run's usage file; **main cr/out** and **subagent cr/out** are cache-read and
output tokens from the v2 `steps_by_role` split and are `—` for every run
captured before that split existed (see Data limits); **priced** says whether
any harness dollar figure exists; **findings/phase** is journal `finding`
entries per phase; **re-opened** is findings a later record moved from closed
back to open. `—` is "nobody measured this", never zero.

## 1. #627 — did the bounded executor handoff (#514) improve handoff quality?

Cutoff: #514's merge, 2026-09-20T16:47Z.

```
$ uv run fr usage compare --before 2026-09-20T16:47:00Z --after 2026-09-20T16:47:00Z
Per run
run                                                           phases  turns  main cr/out  subagent cr/out     cost  priced  findings/phase  re-opened
------------------------------------------------------------  ------  -----  -----------  ---------------  -------  ------  --------------  ---------
[before] 2026-09-09-feat-issue-464                                 0      —            —                —        —      no               —          0
[before] 2026-09-14-feat-statusline-session-branch                 5      —            —                —        —      no            2.60          0
[before] 2026-09-18-feat-harness-parity-matrix                     7      —            —                —        —      no            6.71          0
[before] 2026-09-19-feat-gh-429-followup                           1      —            —                —        —      no               0          0
[before] 2026-09-19-feat-opencode-subagent-dispatch                6      —            —                —        —      no               2          0
[before] 2026-09-19-fix-gh-486-gitlab-contents-ref                 7      —            —                —        —      no            3.29          0
[before] 2026-09-20-feat-bounded-executor-handoff                  5      —            —                —        —      no            4.20          0
[before] 2026-09-20-feat-phase-holder-identity                     6      —            —                —        —      no            2.50          0
[before] 2026-09-20-feat-plan-self-review-dispatch-verb-lint       1      —            —                —        —      no              23          0
[before] 2026-09-20-fix-434-phases-file-tier                       5      —            —                —        —      no            1.20          0
[before] 2026-09-20-fix-fr-run-cursor-cluster                      6      —            —                —        —      no            1.33          0
[before] 2026-09-20-fix-isolation-reap-data-loss                   1      —            —                —        —      no               8          0
[before] 2026-09-20-fix-opencode-tier-model-reaches-dispatch       4      —            —                —        —      no            1.50          0
[after] 2026-09-20-journal-require-reviews-v2                      6      —            —                —        —      no               4          0
[after] 2026-09-20-unit-record-unification-r2                      7  2,175            —                —  $398.94     yes            1.43          0
[after] 2026-09-21-feat-fr-triage                                  4    851            —                —  $208.56     yes               9          0
[after] 2026-09-21-fix-497-agent-tool-neutrality                   1    892            —                —  $200.72     yes               1          0
[after] 2026-09-21-fix-isolation-guard-sentinel-states             4    644            —                —  $120.11     yes            4.25          0
[after] 2026-09-22-feat-gh-558-triage-prs                          4      —            —                —        —      no            0.75          0
[after] 2026-09-22-fix-532-repair-harness-neutrality               5    892            —                —  $200.72     yes            4.60          0
[after] 2026-09-23-feat-triage-batches                             3    995            —                —   $97.14     yes              13          0
[after] 2026-09-23-fix-457-uninstall-rules                         2      —            —                —        —      no               2          0
[after] 2026-09-23-fix-526-status-archivable-merged                3    333            —                —   $24.81     yes               1          0
[after] 2026-09-23-fix-lifecycle-container-vs-worktree             6    827            —                —   $86.02     yes           13.17          0
[after] 2026-09-23-fix-scaffold-batch-574-576-569                  6    620            —                —   $47.19     yes            4.50          0
[after] 2026-09-24-feat-597-593                                    4    827            —                —   $62.06     yes               4          0
[after] 2026-09-25-feat-lean-cost-aware-process                    3  1,372            —                —  $128.38     yes           13.67          0
[after] 2026-09-25-fix-605-agent-step-evidence-debt                1     32            —                —    $0.05     yes               0          0
[after] 2026-09-25-fix-606-writes-dot-dir-prefix                   1    120            —                —    $7.22     yes               0          0
[after] 2026-09-25-fix-610-closeout-defects                        5  1,938            —                —  $105.36     yes            5.20          0
[after] 2026-09-26-feat-batch-archive-repair-scope                 1    227            —                —   $14.91     yes              13          0
[after] 2026-09-26-feat-batch-container-git-ownership              1    145            —                —    $6.59     yes               5          0
[after] 2026-09-26-feat-batch-isolation-timeouts                   2    151            —                —    $6.28     yes            0.50          0
[after] 2026-09-26-feat-batch-one-phase-plans                      1    117            —                —    $5.19     yes               2          0
[after] 2026-09-26-feat-batch-plan-table-header                    3    152            —                —    $6.47     yes               2          0
[after] 2026-09-26-feat-batch-release-scripts                      1  1,889            —                —  $158.17     yes               4          0
[after] 2026-09-26-feat-batch-tests-window                         1    286            —                —   $18.11     yes              14          0
[after] 2026-09-26-feat-batch-usage-opencode-empty                 1    285            —                —   $20.09     yes               7          0
[after] 2026-09-26-feat-batch-verify-merge-rewrites                1    576            —                —   $40.83     yes              15          0
[after] 2026-09-26-feat-ci-time-budget                             2    476            —                —   $29.31     yes               5          0
[after] 2026-09-26-feat-dynamic-brainstorm-questions               3    584            —                —   $32.90     yes            8.33          0
[after] 2026-09-26-feat-version-bump-churn                         5    492            —                —   $33.37     yes            2.20          0
[after] 2026-09-26-fix-624-set-status-drop-level                   3    211            —                —   $17.06     yes            3.67          0
[after] 2026-09-26-fix-659-isolation-gc-fetch                      1    246            —                —    $0.78     yes               0          0
[after] 2026-09-26-fix-models-opencode-noop-505                    2      —            —                —        —      no            0.50          0
[after] 2026-09-27-feat-batch-batch-launch                         2    464            —                —   $22.34     yes               2          0
[after] 2026-09-27-feat-batch-ci-hardening                         1    164            —                —   $10.21     yes               5          0
[after] 2026-09-27-feat-batch-spec-ref-writers                     1    230            —                —   $11.57     yes               3          0
[after] 2026-09-28-feat-batch-closeout-always-2                    6    887            —                —   $52.70     yes            2.67          0
[after] 2026-09-28-feat-batch-phase-sizing-2                       1    312            —                —   $23.90     yes               8          0
[after] 2026-09-28-feat-batch-raw-input-relay-2                    1    185            —                —   $12.04     yes               3          0
[after] 2026-09-28-feat-batch-service-split-2                      6    705            —                —   $46.64     yes            6.17          0
[after] 2026-09-28-feat-batch-ui-evidence-2                        3    748            —                —   $46.62     yes            5.67          0
[after] 2026-09-28-feat-gh-759                                     4    433            —                —    $6.09     yes            3.75          0
[after] 2026-09-29-feat-batch-light-path                           3    591            —                —   $45.75     yes            4.67          0
[after] 2026-09-29-feat-batch-spec-fidelity                        2    318            —                —   $22.94     yes            5.50          0
[after] 2026-10-02-feat-batch-opencode-observe-2                   3    693            —                —        —      no            4.33          0
[after] 2026-10-02-feat-wave-driver                                6  1,773            —                —  $154.67     yes            8.33          0
[after] 2026-10-03-feat-acceptance-report-deployment               1    119            —                —    $9.44     yes               3          0
[after] 2026-10-04-feat-batch-drive-merge-train                    1    165            —                —        —      no               4          0
[after] 2026-10-04-feat-batch-drive-scoped-collect                 1    143            —                —        —      no               4          0
[after] 2026-10-05-feat-batch-drive-close-tabs                     2    260            —                —        —      no            1.50          0
[after] 2026-10-05-feat-batch-run-upgrade-midflight                3    389            —                —        —      no            3.33          0
[after] 2026-10-05-feat-batch-triage-pages-goal                    5    987            —                —        —      no            9.20          0
[after] 2026-10-05-feat-triage-kanban-board                        3    368            —                —   $27.56     yes               6          0
[after] 2026-10-06-feat-batch-cost-evidence                        3     32            —                —        —      no               3          0
[after] 2026-10-06-feat-batch-forge-remainder                      2    303            —                —        —      no            5.50          0
[after] 2026-10-06-feat-batch-triage-dedupe                        1    369            —                —        —      no              11          0
[after] 2026-10-06-feat-batch-verification-kinds                   7  1,128            —                —        —      no            4.57          0

Per set
run                   phases  turns  main cr/out  subagent cr/out    cost  priced  findings/phase  re-opened
--------------------  ------  -----  -----------  ---------------  ------  ------  --------------  ---------
before median (n=13)       5      —        — / —            — / —       —    0/13            2.55          0
after median (n=56)        3    411        — / —            — / —  $28.43   42/56            4.12          0
```

Reading it. The only handoff-quality signals the compare can see for both sets
are review findings per phase and re-opened findings. Findings per phase went
from a median of 2.55 (n=13 runs before) to 4.12 (n=56 after); re-opened is 0
in both. That is not evidence the handoff got worse: review practice and the
size of changes moved at the same time, and a reviewer that looks harder files
more findings. And **zero re-opens is not a measurement**: no resolution record
in any archived or live plan journal (1,111 original findings in the archived
journals alone) moves a finding from closed back to open, so the column cannot
separate the two sets. The cost columns cannot be compared either: none of the
13 runs before the cutoff has a usage file with a dollar figure (0/13 priced,
turns `—`): usage capture arrived later, and backfill found no readable
session or kept figure for those runs.

**Conclusion: inconclusive.** The data that would answer #627 (rework caused by
a thin handoff: re-opened findings, executor turns spent re-discovering context)
does not exist for the before set, and the one signal that does, findings per
phase, is confounded by review practice. Nothing here argues the bounded
handoff failed; nothing here shows it helped.

The binding limits for this section (full list at the end): the sample (n=13
against 56, the after set including runs still open and unpriced), the missing
before-set usage, and the model change straddling the after set (Opus 5 appears
in runs up to 2026-09-22, Opus 5.5 from 2026-09-23).

## 2. #793 item 5 — did phase-per-ask sizing (#792) change what a run costs?

Cutoff: #792's merge, 2026-09-28T21:38Z.

```
$ uv run fr usage compare --before 2026-09-28T21:38:00Z --after 2026-09-28T21:38:00Z
Per run
run                                                           phases  turns  main cr/out  subagent cr/out     cost  priced  findings/phase  re-opened
------------------------------------------------------------  ------  -----  -----------  ---------------  -------  ------  --------------  ---------
[before] 2026-09-09-feat-issue-464                                 0      —            —                —        —      no               —          0
[before] 2026-09-14-feat-statusline-session-branch                 5      —            —                —        —      no            2.60          0
[before] 2026-09-18-feat-harness-parity-matrix                     7      —            —                —        —      no            6.71          0
[before] 2026-09-19-feat-gh-429-followup                           1      —            —                —        —      no               0          0
[before] 2026-09-19-feat-opencode-subagent-dispatch                6      —            —                —        —      no               2          0
[before] 2026-09-19-fix-gh-486-gitlab-contents-ref                 7      —            —                —        —      no            3.29          0
[before] 2026-09-20-feat-bounded-executor-handoff                  5      —            —                —        —      no            4.20          0
[before] 2026-09-20-feat-phase-holder-identity                     6      —            —                —        —      no            2.50          0
[before] 2026-09-20-feat-plan-self-review-dispatch-verb-lint       1      —            —                —        —      no              23          0
[before] 2026-09-20-fix-434-phases-file-tier                       5      —            —                —        —      no            1.20          0
[before] 2026-09-20-fix-fr-run-cursor-cluster                      6      —            —                —        —      no            1.33          0
[before] 2026-09-20-fix-isolation-reap-data-loss                   1      —            —                —        —      no               8          0
[before] 2026-09-20-fix-opencode-tier-model-reaches-dispatch       4      —            —                —        —      no            1.50          0
[before] 2026-09-20-journal-require-reviews-v2                     6      —            —                —        —      no               4          0
[before] 2026-09-20-unit-record-unification-r2                     7  2,175            —                —  $398.94     yes            1.43          0
[before] 2026-09-21-feat-fr-triage                                 4    851            —                —  $208.56     yes               9          0
[before] 2026-09-21-fix-497-agent-tool-neutrality                  1    892            —                —  $200.72     yes               1          0
[before] 2026-09-21-fix-isolation-guard-sentinel-states            4    644            —                —  $120.11     yes            4.25          0
[before] 2026-09-22-feat-gh-558-triage-prs                         4      —            —                —        —      no            0.75          0
[before] 2026-09-22-fix-532-repair-harness-neutrality              5    892            —                —  $200.72     yes            4.60          0
[before] 2026-09-23-feat-triage-batches                            3    995            —                —   $97.14     yes              13          0
[before] 2026-09-23-fix-457-uninstall-rules                        2      —            —                —        —      no               2          0
[before] 2026-09-23-fix-526-status-archivable-merged               3    333            —                —   $24.81     yes               1          0
[before] 2026-09-23-fix-lifecycle-container-vs-worktree            6    827            —                —   $86.02     yes           13.17          0
[before] 2026-09-23-fix-scaffold-batch-574-576-569                 6    620            —                —   $47.19     yes            4.50          0
[before] 2026-09-24-feat-597-593                                   4    827            —                —   $62.06     yes               4          0
[before] 2026-09-25-feat-lean-cost-aware-process                   3  1,372            —                —  $128.38     yes           13.67          0
[before] 2026-09-25-fix-605-agent-step-evidence-debt               1     32            —                —    $0.05     yes               0          0
[before] 2026-09-25-fix-606-writes-dot-dir-prefix                  1    120            —                —    $7.22     yes               0          0
[before] 2026-09-25-fix-610-closeout-defects                       5  1,938            —                —  $105.36     yes            5.20          0
[before] 2026-09-26-feat-batch-archive-repair-scope                1    227            —                —   $14.91     yes              13          0
[before] 2026-09-26-feat-batch-container-git-ownership             1    145            —                —    $6.59     yes               5          0
[before] 2026-09-26-feat-batch-isolation-timeouts                  2    151            —                —    $6.28     yes            0.50          0
[before] 2026-09-26-feat-batch-one-phase-plans                     1    117            —                —    $5.19     yes               2          0
[before] 2026-09-26-feat-batch-plan-table-header                   3    152            —                —    $6.47     yes               2          0
[before] 2026-09-26-feat-batch-release-scripts                     1  1,889            —                —  $158.17     yes               4          0
[before] 2026-09-26-feat-batch-tests-window                        1    286            —                —   $18.11     yes              14          0
[before] 2026-09-26-feat-batch-usage-opencode-empty                1    285            —                —   $20.09     yes               7          0
[before] 2026-09-26-feat-batch-verify-merge-rewrites               1    576            —                —   $40.83     yes              15          0
[before] 2026-09-26-feat-ci-time-budget                            2    476            —                —   $29.31     yes               5          0
[before] 2026-09-26-feat-dynamic-brainstorm-questions              3    584            —                —   $32.90     yes            8.33          0
[before] 2026-09-26-feat-version-bump-churn                        5    492            —                —   $33.37     yes            2.20          0
[before] 2026-09-26-fix-624-set-status-drop-level                  3    211            —                —   $17.06     yes            3.67          0
[before] 2026-09-26-fix-659-isolation-gc-fetch                     1    246            —                —    $0.78     yes               0          0
[before] 2026-09-26-fix-models-opencode-noop-505                   2      —            —                —        —      no            0.50          0
[before] 2026-09-27-feat-batch-batch-launch                        2    464            —                —   $22.34     yes               2          0
[before] 2026-09-27-feat-batch-ci-hardening                        1    164            —                —   $10.21     yes               5          0
[before] 2026-09-27-feat-batch-spec-ref-writers                    1    230            —                —   $11.57     yes               3          0
[before] 2026-09-28-feat-batch-closeout-always-2                   6    887            —                —   $52.70     yes            2.67          0
[before] 2026-09-28-feat-batch-phase-sizing-2                      1    312            —                —   $23.90     yes               8          0
[before] 2026-09-28-feat-batch-raw-input-relay-2                   1    185            —                —   $12.04     yes               3          0
[before] 2026-09-28-feat-batch-service-split-2                     6    705            —                —   $46.64     yes            6.17          0
[before] 2026-09-28-feat-batch-ui-evidence-2                       3    748            —                —   $46.62     yes            5.67          0
[before] 2026-09-28-feat-gh-759                                    4    433            —                —    $6.09     yes            3.75          0
[after] 2026-09-29-feat-batch-light-path                           3    591            —                —   $45.75     yes            4.67          0
[after] 2026-09-29-feat-batch-spec-fidelity                        2    318            —                —   $22.94     yes            5.50          0
[after] 2026-10-02-feat-batch-opencode-observe-2                   3    693            —                —        —      no            4.33          0
[after] 2026-10-02-feat-wave-driver                                6  1,773            —                —  $154.67     yes            8.33          0
[after] 2026-10-03-feat-acceptance-report-deployment               1    119            —                —    $9.44     yes               3          0
[after] 2026-10-04-feat-batch-drive-merge-train                    1    165            —                —        —      no               4          0
[after] 2026-10-04-feat-batch-drive-scoped-collect                 1    143            —                —        —      no               4          0
[after] 2026-10-05-feat-batch-drive-close-tabs                     2    260            —                —        —      no            1.50          0
[after] 2026-10-05-feat-batch-run-upgrade-midflight                3    389            —                —        —      no            3.33          0
[after] 2026-10-05-feat-batch-triage-pages-goal                    5    987            —                —        —      no            9.20          0
[after] 2026-10-05-feat-triage-kanban-board                        3    368            —                —   $27.56     yes               6          0
[after] 2026-10-06-feat-batch-cost-evidence                        3     32            —                —        —      no               3          0
[after] 2026-10-06-feat-batch-forge-remainder                      2    303            —                —        —      no            5.50          0
[after] 2026-10-06-feat-batch-triage-dedupe                        1    369            —                —        —      no              11          0
[after] 2026-10-06-feat-batch-verification-kinds                   7  1,128            —                —        —      no            4.57          0

Per set
run                   phases  turns  main cr/out  subagent cr/out    cost  priced  findings/phase  re-opened
--------------------  ------  -----  -----------  ---------------  ------  ------  --------------  ---------
before median (n=54)       3    476        — / —            — / —  $29.31   37/54            3.75          0
after median (n=15)        3    368        — / —            — / —  $27.56    5/15            4.57          0
```

Reading it. Medians barely moved: 3 phases per run on both sides, turns 476
before (n=54) against 368 after (n=15), cost $29.31 against $27.56, findings
per phase 3.75 against 4.57, re-opened 0 against 0. The turns and dollars
differences sit inside the per-run spread (per-run costs in the table run from
under a dollar to well over a hundred), and the after set is small and mostly
unpriced: only 5 of its 15 runs carry a dollar figure (the sessions of the
latest runs were still open when captured and were never re-priced), against 37
of 54 before.

**Conclusion: inconclusive, leaning "no detectable change".** There is no
visible shift in phases per run, turns, cost or findings per phase, but 5
priced runs cannot detect a modest effect, and the median phase count did not
change at all, so the sizing rule had little room to show up in this window.
Re-run `fr usage compare` once a few dozen runs have been captured after the
change. This window is the cleaner of the two for the model change: every run
on both sides ran Opus 5.5 (Sonnet 5.5 from 2026-09-26).

## 3. #593 — decision rules for restarting the main session (option 1) or doing nothing (option 4)

#593's rules: adopt option 1 if the main session is more than 60% of cost AND
its per-turn cache read grows more than 2x across steps on the larger tasks.

**Which figures were used.** The v2 split (`steps_by_role`: main against
subagent tokens per step) exists only for runs captured on this branch, and the
only two usage files that carry it are runs still in flight, both unpriced.
They decide nothing, and the compare output above shows `—` in both token
columns for every archived run. What the archive does have is the v1 per-step
figures (dollars and turns) of the main session. Those are what is used below,
with these consequences:

- Main-session **share of cost** (the first rule) cannot be measured from v1
  files. Their `main` entry holds the main session's whole transcript and only
  five archived files carry a separate subagent entry at all, none with a
  subagent dollar figure.
  Whether subagent turns were folded into the main figure depends on the
  capture date (subagents were folded in only after gh#637), so a share would
  be a guess. It is reported as **not determined**.
- **Cache read per main-session turn by step** (the second rule) needs tokens
  per step, which v1 files do not carry. The nearest observable proxy is
  **dollars per main-session turn by step**: cache read dominates a long
  session's cost, so it tracks context size, but it is a proxy, it carries the
  model price, and it is not the rule's measure.

```
$ uv run python steps.py 0      # script reproduced at the end
priced archived runs from 2026-09-20 with main-session cost >= $0 (n=42); main-session step figures, v1 usage files
step            runs  median share of cost  median $/turn  median turns
(outside run)     40                 17.9%         $0.098            34
brainstorm        39                  5.0%         $0.058            20
spec-review       36                  5.5%         $0.045            31
plan              35                  2.4%         $0.087             8
plan-review        0                  0.4%              —             —
implement         41                 50.5%         $0.056           218
journal-check      0                  0.3%              —             —
deliver           38                  5.9%         $0.095            20
```

```
$ uv run python steps.py 100    # only runs with >= $100 main-session cost
priced archived runs from 2026-09-20 with main-session cost >= $100 (n=9); main-session step figures, v1 usage files
step            runs  median share of cost  median $/turn  median turns
(outside run)      9                 67.8%         $0.200           498
brainstorm         8                  1.5%         $0.044            18
spec-review        5                  0.4%         $0.043            18
plan               7                  0.5%         $0.054             7
plan-review        0                     —              —             —
implement          9                 26.8%         $0.059           517
journal-check      0                  0.1%              —             —
deliver            7                  1.2%         $0.193            18
```

Reading it. Across the 42 priced runs since 2026-09-20 the proxy grows about
1.6x from brainstorm ($0.058 per turn) to deliver ($0.095), below the rule's 2x,
and `implement` (the longest step by turns, with the dispatching and debugging)
is about half of the main session's cost. Among the 9 runs that cost $100 or
more the picture changes: deliver costs $0.193 per turn against $0.044 for
brainstorm, about 4.4x, but 68% of those runs' main-session cost sits in
`(outside run)`: time in the same session before the run cursor's first step
timestamp or after its last. Those long sessions outlive the run (they drive
other runs or pre-date it), so the growth is not inside the steps a restart at
a step boundary would reset, and it cannot be read as the rule intends.

**Conclusion: inconclusive; if a choice must be made today, option 4.** The
first rule (main share above 60%) cannot be evaluated at all, so option 1 cannot
be adopted by #593's own rules. The second rule gives 1.6x on the typical run
(fails) and 4.4x on the largest ones (passes), with the proxy and the
`(outside run)` confound both working against reading that 4.4x as the rule's
cache-read growth. Option 4 therefore stands by default: it costs nothing and
nothing here contradicts it. Re-run this once runs captured with the v2 split
accumulate: the main and subagent token columns of `fr usage compare` and the
per-step columns of `fr run cost` then give the rule's share and cache-read
figures as direct readings instead of proxies.

**Recommendation between #593 options 1 and 4: option 4 (do nothing now)**,
revisited after a few dozen runs have been captured with the split. Option 0
(per-step main-session tokens) is what makes that revisit possible and ships
in this PR's usage v2 format.

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
   have the split are two in-flight runs, so the compare's token columns say
   nothing yet. Refreshing an archived file at re-pricing writes no split by
   design.
4. **The Opus 5 to Opus 5.5 change.** Opus 5 appears in runs up to 2026-09-22,
   Opus 5.5 from 2026-09-23 (Sonnet 5.5 from 2026-09-26). The #627 after set
   straddles it; per-turn dollars and cache behaviour differ by model, so any
   before/after cost reading across it is confounded. #793's window sits after
   it.
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
   finding, so the compare's re-opened column is 0 everywhere and does not
   discriminate.
8. **Findings per phase is a confounded proxy** for handoff quality: it moves
   with review thoroughness and change size as much as with the handoff.
9. **`(outside run)` and shared sessions.** A session that outlives a run
   contributes steps outside the cursor's windows (68% of main-session cost in
   the $100-and-over runs). Dollars per turn by step is a proxy for cache read
   per turn and carries the model price.
10. **Out of scope: the measurement campaign.** #593's three-task by
    two-harness campaign with a plain-agent baseline and a blind review of both
    diffs was not run; this audit is observational over runs that already
    exist.

## Reproducing the #593 table

The script is read-only: it sums each priced archived usage file's
main-session step figures through `fr.run.cost.effective_entries` and takes
medians. Run it from the repo root with `uv run python steps.py <min-cost>`.

```python
import glob, statistics
from pathlib import Path
from fr.usage.file import load_usage
from fr.run.cost import effective_entries

import sys
MIN_TOTAL = float(sys.argv[1]) if len(sys.argv) > 1 else 0
STEPS = ["(outside run)", "brainstorm", "spec-review", "plan", "plan-review", "implement", "journal-check", "deliver"]
per = {s: {"share": [], "ppt": [], "turns": []} for s in STEPS}
n = 0
for p in sorted(glob.glob("docs/superpowers/implemented/usage/*.yaml")):
    f = load_usage(Path(p))
    if f is None or f.run < "2026-09-20":
        continue
    ents, _, _ = effective_entries(f)
    usd, turns = {}, {}
    for e in ents:
        if e.unavailable or e.role not in (None, "main"):
            continue
        for s, fig in e.steps.items():
            if fig.usd is not None:
                usd[s] = usd.get(s, 0) + fig.usd
            if fig.turns:
                turns[s] = turns.get(s, 0) + fig.turns
    total = sum(usd.values())
    if not total or total < MIN_TOTAL:
        continue
    n += 1
    for s in STEPS:
        if s in usd:
            per[s]["share"].append(usd[s] / total)
        if s in usd and turns.get(s, 0) >= 5:
            per[s]["ppt"].append(usd[s] / turns[s])
            per[s]["turns"].append(turns[s])
print(f"priced archived runs from 2026-09-20 with main-session cost >= ${MIN_TOTAL:.0f} (n={n}); main-session step figures, v1 usage files")
print(f"{'step':<15}{'runs':>5}{'median share of cost':>22}{'median $/turn':>15}{'median turns':>14}")
for s in STEPS:
    v = per[s]
    m = lambda xs: statistics.median(xs) if xs else None
    sh, pt, tu = m(v["share"]), m(v["ppt"]), m(v["turns"])
    print(f"{s:<15}{len(v['ppt']):>5}{(f'{sh:.1%}' if sh is not None else '—'):>22}{(f'${pt:.3f}' if pt is not None else '—'):>15}{(f'{tu:.0f}' if tu is not None else '—'):>14}")
```
