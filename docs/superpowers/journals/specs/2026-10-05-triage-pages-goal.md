# Journal: 2026-10-05-triage-pages-goal

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-05T21:01:46+00:00 input=true -->
### operator-brief · discovery · Operator brief (batch triage-pages-goal), verbatim

/fr-goal Triage pages: one goal per page, one home per fact, authored sections everywhere, driver exports the state

Batch `triage-pages-goal` of derio-net/super-fr: 3 issues, delivered as ONE pull request.

## super-fr#970: Triage pages: one goal per page, partition and de-duplicate their data, and export the state from the driver (fr-brainstorming)
Brainstorm first: one goal per page, one home per fact, summary before detail, driver export of the triage state. Folds in super-fr#968 and super-fr#887.
Note: Operator priority 2026-10-05: artifact issues first (wave 4).

## super-fr#968: Triage pages: the board and origins page have no home for authored sections, so hand-written analysis is lost on re-render
Board and origins page have no fragment mechanism; architecture's `load_manifest`/`validate_fragment` is the one to share.
Note: Folded into super-fr#970, whose design covers it. Close when #970 lands: `gh issue close 968 -R derio-net/super-fr --reason "not planned" --comment "Folded into #970."`

## super-fr#887: Board's wave 'Closing order' table has no per-batch tier column
Wave tables omit each batch's tier, on purpose per spec design D.
Note: Folded into super-fr#970 (board layout).

## Why these belong together
Wave 4: the artifact UX brainstorm. fr-goal starts with fr-brainstorming and will stop at its question round for the operator.

## Delivery rules
- Work on branch `feat/batch-triage-pages-goal`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#970
  Closes derio-net/super-fr#968
  Closes derio-net/super-fr#887
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

(Issue bodies of #970, #968 and #887 as read 2026-10-05 via `gh issue view`; their
asks are restated in the spec's Background and Requirements.)

<!-- fr:journal kind=decision scope=spec id=q1-board-backlog-collapsed created=2026-10-05T21:01:46+00:00 -->
### q1-board-backlog-collapsed · decision · Board keeps the backlog, collapsed per sub-section; batch cards collapsed and stage-filterable

Q: where do backlog by tier, patterns, features, parked, PRs and batch cards go?
A (operator, verbatim): "Batch cards should be a. collapsed and b. filterable by state
(merged, cancelled, etc in multi-select). Since last report should be a nice table showing
the transitions. Clicking on a batch should jump to the batches section for more details.
Regarding q1, 2. collapsed on the board and each sub category (Patterns, Parked etc..) also
collapsed.." -> spec R2, R3, R5.

<!-- fr:journal kind=decision scope=spec id=q2-architecture-summary created=2026-10-05T21:01:46+00:00 -->
### q2-architecture-summary · decision · Architecture summary strip becomes the page's own answer

Operator chose: replace the strip with lines then/now and the top 3 subsystems by open defects (R6).

<!-- fr:journal kind=decision scope=spec id=q3-history-page created=2026-10-05T21:01:46+00:00 -->
### q3-history-page · decision · History gets its own page

Operator chose a separate history.html: snapshot timeline, finished waves, dated fragments (R8).

<!-- fr:journal kind=decision scope=spec id=q4-data-scope created=2026-10-05T21:01:46+00:00 -->
### q4-data-scope · decision · Data in scope - origins schema 2, severity on judgements, duplicate_of on judgements; per-wave cost out

Operator selected origins.yaml schema 2, severity on every open issue, structured duplicates in judgements (R10, R11). Per-wave cost not selected (non-goal).

<!-- fr:journal kind=decision scope=spec id=q5-driver-opens-export-pr created=2026-10-05T21:01:46+00:00 -->
### q5-driver-opens-export-pr · decision · The driver itself opens and merges the export PR

Operator chose: driver commits in a worktree, pushes chore/triage-state-wave-<N>, opens the PR via a new GhClient.pr_create, merges it when green like an archive PR; one export per wave, recorded (R13).

<!-- fr:journal kind=decision scope=spec id=q6-fr-verbs-replace-sync created=2026-10-05T21:01:46+00:00 -->
### q6-fr-verbs-replace-sync · decision · fr triage state export|import replace docs/triage/sync.sh

Operator chose fr verbs owning the file list; the driver calls the same function; opt-in export: {path: docs/triage} in .fr/triage.yaml (R12, R15).
