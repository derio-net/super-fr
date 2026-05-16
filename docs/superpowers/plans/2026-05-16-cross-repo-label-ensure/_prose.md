# Cross-repo `RepoLabelEnsure` fix

Closes issue [#132](https://github.com/derio-net/superpowers-for-vk/issues/132).
`diff()` emits exactly one `RepoLabelEnsure` for `plan.meta.target_repo`,
even when phases' tracking Issues live on a different repo. The labels get
created on the wrong repo and the subsequent `IssueLabelChange` fails with
`label not found`. The fix groups labels by destination repo and emits one
`RepoLabelEnsure` per distinct repo.

See the design spec at
`docs/superpowers/specs/2026-05-16-cross-repo-label-ensure-design.md`
for the full rationale — options considered, behavior shifts per plan
shape, malformed-URL error path, and why the issue comment's wider-scope
claim (that `IssueStateChange` and `IssueBodyChange` are also broken)
turns out to be a misdiagnosis the new regression tests refute.

## Shape

One phase, four tasks. Reproduction-first throughout: the cross-repo
fixture and tests land first, with one predicted-red test that documents
the bug; the fix flips that test green; downstream regression tests
prove the bridge tick path is also safe.

- **T1** adds `tests/unit/fixtures/v2_plan_cross_repo/` (two phases,
  one dispatched on `repo-b`, one undispatched on `target_repo`), then
  writes two new tests in `test_v2_diff.py`: one predicted-red
  (documents the `RepoLabelEnsure` bug), one predicted-green (locks
  down the already-correct per-issue routing).
- **T2** tightens `FakeGhClient.edit_issue_labels` and
  `FakeGhClient.create_issue` to raise on labels not yet ensured on
  the destination repo — making the bug catchable in future unit
  tests rather than silently passing. Fixes any unrelated test fallout.
- **T3** lands the `diff()` change per spec § Decision (group by
  destination repo, union of managed labels, sorted iteration for
  deterministic mutation order). Adds an `apply()`-level end-to-end
  test and a `bridge.tick()` regression test to cover the post-MCP
  `vk-synced` add at `bridge/__init__.py:181`.
- **T4** bumps `2.1.4 → 2.1.5` across the three version files,
  refreshes `uv.lock`, runs the full lint/format/type/test pass, and
  does a CLI-level sanity check against the new fixture.

## Why this is one phase, not several

~80 LOC of source change (just the diff() block) plus ~150 LOC of
tests and fixture. Tightly coupled: T1's failing test is meaningless
without T3's fix, T2's fake-tightening would silently regress without
T1's tests exercising it, T4's version bump must ship in the same
commit train as the behavior change to be visible to consumers. The
"one phase = one PR" convention from the prior writeback plan
(2026-05-13) applies cleanly.

## Out of scope

- Refactoring `IssueLabelChange` / `IssueStateChange` / `IssueBodyChange`
  routing — the T1 regression-guard test confirms it's already correct.
- Changes to the `GhClient` Protocol, `real_ghclient.py`, or any bridge
  code.
- Data migration for `willikins#162` / `#164` — operator already closed
  them manually.
- A CI guard enforcing "every plan must exercise the cross-repo
  fixture" — the new tests are the guard.
- Re-titling or splitting issue #132 — the spec's *Scope clarification*
  addresses the comment-thread framing.
