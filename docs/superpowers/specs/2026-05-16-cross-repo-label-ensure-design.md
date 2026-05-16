# Cross-repo `RepoLabelEnsure` fix — Design

## Problem

`diff()` in `src/vk/diff.py:100-113` emits exactly one
`RepoLabelEnsure(repo=plan.meta.target_repo, …)` per plan, regardless of where
each phase's tracking Issue actually lives. When a plan has a `target_repo`
distinct from any phase's `tracking_issue` repo, the managed labels (e.g.
`plan:<slug>`, `spec:<slug>`, `vk-ready`) are created on the wrong repo. The
subsequent `IssueLabelChange` against the foreign repo then fails with:

```
failed to update https://github.com/<owner>/<repo>/issues/<N>:
'plan:<slug>' not found
```

The bug shipped against
`willikins/docs/superpowers/plans/2026-05-03-agent-followup-sweep`:

- `target_repo: derio-net/superpowers-for-vk`
- Phases 1–4, 6 tracked on `derio-net/willikins`

The bridge daemon accumulated 5 failures per tick for `willikins#160`–`#164`
until labels were created manually on `willikins` via `gh label create`. See
issue [#132](https://github.com/derio-net/superpowers-for-vk/issues/132).

### Scope clarification

The issue comment thread proposed widening the fix to
`IssueLabelChange` / `IssueStateChange` / `IssueBodyChange`, on the premise
that those mutations also assume `target_repo`. **A direct read of the code
shows they already pass `parse_issue_url(tracking_issue).repo` through to
`apply()`, which honors it (`src/vk/diff.py:134-171`,
`src/vk/apply.py:64-87`).** The reproduction tests below confirm this — the
broader claim does not survive contact with the source. The fix is scoped to
`RepoLabelEnsure` only; the per-issue routing gets regression coverage rather
than a code change.

## Options considered

1. **Group `RepoLabelEnsure` by destination repo; union all managed labels per
   repo.** For each distinct destination repo across phases (dispatched:
   `parse_issue_url(tracking).repo`; undispatched: `plan.meta.target_repo`),
   collect the union of every managed label projected by the renderer and
   emit one `RepoLabelEnsure` per repo. *Accepted.* Smallest diff, idempotent,
   already-deterministic with a sorted iteration order. Slight over-ensure
   (every destination repo receives every managed label, including ones for
   phases that don't live there) — acceptable since vk owns the prefixed
   namespace and an unused phase label on a foreign repo is harmless.

2. **Slice managed labels by which phases actually live on each repo.**
   Precise per-repo label sets, no over-ensure. *Rejected.* Adds a per-phase
   label-to-repo bookkeeping pass; phases that move repos would need
   re-ensure logic. Marginal benefit without a label-count constraint.

3. **One `RepoLabelEnsure` per (repo, label) pair.** *Rejected.* Mutation
   count balloons (e.g. 50 labels × 2 repos = 100 mutations); `apply()`
   iterates one at a time, observably slower in real ticks.

## Decision

Adopt option 1.

### Change in `diff()`

Replace the existing single-emission block (`diff.py:108-113`) with a
per-repo grouping:

```python
labels_per_repo: dict[str, set[LabelDef]] = defaultdict(set)
for phase_n, ri in rendered.issue_per_phase.items():
    phase = next(p for p in plan.phases if p.phase.number == phase_n)
    tracking = phase.phase.tracking_issue
    dest = parse_issue_url(tracking)[0] if tracking else plan.meta.target_repo
    labels_per_repo[dest].update(ld for ld in ri.labels if _is_managed(ld.name))

for repo in sorted(labels_per_repo):
    labels = labels_per_repo[repo]
    if labels:
        mutations.append(RepoLabelEnsure(repo=repo, labels=frozenset(labels)))
```

Sorted iteration keeps mutation ordering deterministic — existing tests in
`test_v2_diff.py` and `test_v2_apply.py` assert on mutation order.

### No other code changes

- `apply.py`, `real_ghclient.py`, `bridge/__init__.py`, and the `GhClient`
  Protocol are unchanged. Per-issue mutations already carry `issue_repo`.
- The bridge's post-MCP `gh.edit_issue_labels(issue_repo, …, add={"vk-synced"})`
  at `bridge/__init__.py:181` will succeed on cross-repo plans after the fix,
  because `apply()` will have ensured `vk-synced` on every destination repo
  before the bridge's add-call runs.

## Reproduction-first testing

The work order is: write tests that exercise the cross-repo case **before**
landing the code change. The label test will fail (documenting the bug); the
per-issue routing tests will pass (locking down the correct existing
behavior).

### New fixture

`tests/unit/fixtures/v2_plan_cross_repo/`:

- `_meta.yaml`: `target_repo: derio-net/repo-a`, two phases.
- `01.yaml`: dispatched phase with
  `tracking_issue: https://github.com/derio-net/repo-b/issues/100`.
- `02.yaml`: undispatched phase (no `tracking_issue`).

### New tests in `tests/unit/test_v2_diff.py`

- `test_diff_emits_ensure_per_destination_repo` — asserts two
  `RepoLabelEnsure` mutations: one for `derio-net/repo-a` (covers phase 2's
  projected `IssueCreate`), one for `derio-net/repo-b` (covers phase 1's
  existing tracking issue). **Fails before the fix.**
- `test_diff_routes_per_issue_mutations_to_tracking_repo` — locks down that
  `IssueLabelChange` / `IssueStateChange` / `IssueBodyChange` emitted for
  phase 1 carry `repo == "derio-net/repo-b"`, never `"derio-net/repo-a"`.
  **Passes before the fix** — regression guard against the broader claim.

### New test in `tests/unit/test_v2_apply.py`

- `test_apply_executes_cross_repo_mutations_through_correct_repo` —
  end-to-end with `FakeGhClient`: preload `repo-b#100` as `OPEN` with
  `vk-ready`. Run `diff()` + `apply()`. Assert
  `fake.issues[("derio-net/repo-b", 100)].state == "CLOSED"` and that the
  recorded `fake.calls` carry the right `(repo, number)` pairs. **Passes
  before the fix** (state/body routing is already correct); becomes a guard.

### New test in `tests/unit/test_vk_bridge_tick.py`

- A cross-repo variant that exercises `bridge.tick()` with the new fixture.
  Asserts (a) `apply()` succeeds on both repos, and (b) the post-MCP
  `gh.edit_issue_labels(issue_repo, add={"vk-synced"})` call lands on
  `derio-net/repo-b`, not `derio-net/repo-a`.

### `FakeGhClient` tightening

`tests/unit/fakes.py` does not currently model real `gh`'s "label must exist
on repo before it can be applied to an issue" rule. Even with the cross-repo
fixture, an `edit_issue_labels(repo="derio-net/repo-b", add={"vk-ready"})`
call would silently succeed today — masking exactly the production failure
this fix targets.

Tighten the fake:

- `edit_issue_labels(repo, number, *, add, remove)` raises `FakeGhError`
  if any name in `add` is not in `self.repo_labels.get(repo, set())`.
- `create_issue(repo, *, title, body, labels)` raises `FakeGhError` if any
  name in `labels` is not in `self.repo_labels.get(repo, set())`.

The standard apply flow already emits `RepoLabelEnsure` before any
label-using mutation, so existing tests should keep passing. Run the full
suite after the fake change; for any test that breaks, decide between (a)
fixing the test (it was masking a missing precondition) or (b) preloading
`repo_labels` in the fixture setup. Expected breakage surface: minimal.

## Out of scope

- No refactor of `IssueLabelChange` / `IssueStateChange` / `IssueBodyChange`
  routing — reproduction tests confirm those paths are already correct.
- No change to the `GhClient` Protocol or `real_ghclient.py`.
- No data migration for `willikins#162` and `willikins#164` — the user
  already closed them manually.
- No CI guard for "plans must have a cross-repo fixture exercised" beyond the
  new tests themselves.
- No re-titling or splitting of issue #132 — the body remains accurate as a
  bug report; the comment's broader framing is addressed in this design's
  *Scope clarification* section.

## Release mechanics

Per `CLAUDE.md` (Release / version bumping):

| File | Field | Change |
|---|---|---|
| `pyproject.toml` | `[project].version` | `2.1.4` → `2.1.5` |
| `.claude-plugin/plugin.json` | `.version` | `2.1.4` → `2.1.5` |
| `.claude-plugin/marketplace.json` | `.plugins[0].version` | `2.1.4` → `2.1.5` |

Then `uv sync` and `uv run vk --version` to verify the CLI reports `2.1.5`.
Patch bump: this is a bug fix to existing behavior, no new user-facing
workflow.

## Verification checklist (apply during execution, not now)

- [ ] New cross-repo fixture parses cleanly (`uv run vk apply --dry-run`
      against the fixture path).
- [ ] `test_diff_emits_ensure_per_destination_repo` fails on `main`, passes
      after the `diff()` change.
- [ ] `test_diff_routes_per_issue_mutations_to_tracking_repo` passes both
      before and after the change.
- [ ] `test_apply_executes_cross_repo_mutations_through_correct_repo` passes
      both before and after the change.
- [ ] `FakeGhClient` tightening: full suite still green after the fake learns
      the label-existence rule.
- [ ] `uv run ruff format src/ tests/`, `uv run ruff check src/ tests/`,
      `uv run mypy src/`, `uv run pytest -q --no-cov` all clean locally
      before push (CI is slow to fail-loud per `CLAUDE.md`).
- [ ] Version bump applied to all three files; `uv.lock` updated via
      `uv sync`.

## Why this matters

The bridge daemon polls every plan with a `vk-ready` phase on every tick. A
cross-repo plan accumulates failures per tick indefinitely until someone
manually creates labels. With the fix, the bridge becomes self-healing for
cross-repo dispatch — a property the codebase otherwise claims (idempotent,
deterministic, no manual intervention needed).
