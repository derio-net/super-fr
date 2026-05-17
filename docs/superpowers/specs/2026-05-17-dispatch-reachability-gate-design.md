# Dispatch-reachability gate for `vk apply --yes` — Design

## Problem

`vk apply --yes` creates a GitHub Issue with `vk-ready` (and other
dispatchable content in the Issue body) without verifying that the
referenced plan and spec files are reachable to downstream consumers.
When the operator dispatches from a local-only branch:

1. The bridge's v2 path (`vk.bridge.discover_plans`) silently skips
   the plan because the plan dir isn't on the bridge's local checkout
   at `~/repos/<name>/`.
2. The bridge's **legacy per-Issue loop**
   (`agent-images/kali/scripts/vk-issue-bridge.py:990+`) parses the
   Issue body's `## Instruction` / `## Workspace` blocks and
   dispatches the implementing agent based on that alone — it does
   NOT require the plan to exist anywhere.
3. The implementing agent branches from `origin/<default-branch>`
   (which doesn't have the plan), reads the Issue body's
   "Goal (from plan):" paragraph, and improvises a PR.

Concrete incident: PR #135 shipped a functionally-correct cross-repo
fix but omitted the cross-repo fixture, the `FakeGhClient`
tightening, the `apply()` end-to-end test, and the `bridge.tick()`
regression test that the underlying plan designed. Reverted via #138.
Full forensics in #139.

## Why the v2 contract requires "plan reachable on `origin/<default-branch>`"

Both downstream consumers — bridge and implementing agent — depend
on the plan being visible on the branch their checkout follows
(typically the remote default branch):

1. `vk.bridge.discover_plans` walks the local filesystem at
   `~/repos/<name>/docs/superpowers/plans/`. Plans not on the
   bridge's checked-out branch are invisible.
2. The live bridge script uses the same library path (line 904 of
   `vk-issue-bridge.py`).
3. The `vk-dispatch` skill, step 5: *"Commit and push the staged
   writeback so the bridge's checkout can see the URLs on its next
   tick."* — the spec acknowledges that "bridge-sees-default-branch"
   is the steady state.
4. Implementing agents branch from `origin/<default-branch>`. Without
   the plan there, they improvise.

The gap is purely **the contract is unenforced in code.**

## Options considered

1. **Pre-flight gate at `origin/HEAD` (Accepted).** For each file
   under `<plan-dir>/` (recursive) AND the spec file referenced in
   `_meta.yaml`, check `git ls-tree origin/HEAD -- <relpath>`
   returns non-empty stdout. If any file is missing, abort `--yes`
   with a structured error listing the missing paths. Dry-run
   unaffected.

2. **Plan reachable on any pushed branch.** *Rejected.* The bridge's
   checkout follows the remote default branch; plans on a pushed
   feature branch are not visible to it. This rule passes cases that
   still race.

3. **Just check "no unpushed commits touching plan dir".** *Rejected.*
   Allows dispatch from a feature branch that's pushed but never
   merged — same race.

4. **Add a `--force` flag or `VK_DISPATCH_ALLOW_LOCAL=1` env var
   escape hatch.** *Rejected.* The autonomous flow we hit had no
   operator in the loop. An env var on the Kali container or a
   `--force` an agent learned to add would defeat the gate entirely.
   Testing the gate itself uses monkeypatch / tmp_path; no runtime
   escape is needed.

## Decision

Adopt option 1.

### Rule

`vk apply --yes` refuses to dispatch unless **every plan file AND
the spec file referenced in `_meta.yaml`** is present at
`origin/HEAD`. No flag/env-var escape hatch. Dry-run preview
(`vk apply <plan-dir>` without `--yes`) is unchanged — operators
can still preview locally without push.

### Why `origin/HEAD` (not `origin/main`)

`origin/HEAD` is a local symref set automatically on clone, pointing
at the remote's current default branch. Using it means:

- No hardcoded branch name (works for repos that use `master`,
  `trunk`, etc.).
- No extra network call to query the remote.
- The check tracks whatever the remote considers default at the time
  the operator's local refs were last updated.

If `origin/HEAD` is unset locally (rare; only happens for repos
cloned with `--no-checkout` or similar), the error message tells the
operator how to fix it (`git remote set-head origin --auto`).

### Architecture

Two functions:

```python
# src/vk/git.py — generic git primitive (new)
def file_on_ref(ref: str, path: str, cwd: Path | None = None) -> bool:
    """True if `git ls-tree <ref> -- <path>` has output."""

# src/vk/commands/apply_cmd.py — application logic (new private)
def _check_plan_reachable_on_origin_head(
    plan: Plan, repo_root: Path
) -> list[Path]:
    """Return paths NOT present on origin/HEAD. Empty list = gate passes."""
```

Why split: `file_on_ref` is a one-liner generic git primitive
testable in isolation against any tmp_path repo;
`_check_plan_reachable_on_origin_head` is application logic that
knows about `Plan` structure and the spec field in `_meta.yaml`.

Call site: at the top of the `if yes:` branch of `_apply_one(...)`,
after the dry-run path but before `apply(d, gh)`. On non-empty
result, return `(2, error_text, json_with_unreachable_paths)`.

### Failure shape

Text output (example):

```
plan: <some-plan-slug>
refuse to dispatch: 4 file(s) not at origin/HEAD:
  docs/superpowers/plans/<some-plan-slug>/_meta.yaml
  docs/superpowers/plans/<some-plan-slug>/_prose.md
  docs/superpowers/plans/<some-plan-slug>/01.yaml
  docs/superpowers/specs/<spec-file>.md

Merge the plan + spec to the default branch first, then re-run
`vk apply --yes`.
(If origin/HEAD isn't set locally: `git remote set-head origin --auto`.)
```

Exit code 2 (matches the existing "usage / refusal" code in
`apply_command`'s docstring). JSON output gains an
`unreachable_paths: [...]` field — empty list when the gate passes.

### Edge cases

- **`origin/HEAD` not set locally:** `_run_git(["ls-tree",
  "origin/HEAD", ...])` raises. The gate function catches and
  re-raises with the helpful "git remote set-head origin --auto"
  hint.
- **No `origin` remote:** the git call fails with a clear "no such
  remote" error. `vk apply --yes` is only meaningful in a clone; if
  there's no remote, dispatching to GitHub doesn't make sense.
- **Symlinks inside plan dir:** unlikely (plans are yaml/md); if
  present, `git ls-tree` treats them as blobs — no special handling.
- **`vk apply --all`:** gate runs per-plan inside `_apply_one`;
  failures accumulate into `overall_rc` the same way parse errors do
  today.
- **Spec field absent in `_meta.yaml`:** the field is optional per
  `vk plan create --help`. If `meta.spec is None`, skip the spec
  check; only gate the plan files.
- **Rework plans** (`_meta.parent_plan`, `_meta.prior_rework`): no
  special handling — the rework plan's own files are checked.
  parent/prior references aren't pre-flighted (they should already
  be on default branch since rework PRs follow the same gated
  workflow).

### Testing approach

- **Unit tests** for `file_on_ref` (new `tests/unit/test_git.py` or
  extend an existing module): `tmp_path` + `git init` + commit;
  assert true/false for present/missing paths against `HEAD` and
  `origin/HEAD` (after setting up a fake remote).
- **Unit tests** for `_check_plan_reachable_on_origin_head` in
  `tests/unit/test_v2_apply.py`: copy a fixture plan into a
  `tmp_path` git repo, commit some files but not others, set up an
  `origin` remote with a matching/mismatching `HEAD`, assert the
  returned missing-paths list matches.
- **Integration test** for `_apply_one` end-to-end with the gate:
  monkeypatch `_check_plan_reachable_on_origin_head` to return
  `[<paths>]`; assert `(rc=2, message contains unreachable paths,
  no gh mutations attempted)`. One sibling test asserts that a
  passing gate proceeds to the existing apply flow.

## Workflow impact

The implicit "merge plan before dispatch" convention becomes
mandatory. Operationally that's the same **2-PR pattern** this repo
already uses (PRs #121 / #122 for the writeback feature):

1. PR #1: spec + plan → review → merge to default branch.
2. `vk apply --yes` from any branch (gate passes).
3. PR #2: the staged `tracking_issue` writeback → review → merge.

The `vk-dispatch` skill needs one paragraph added before its current
step 1:

> **Pre-flight (mandatory after gate fix):** the plan and its
> referenced spec MUST be merged to the default branch first.
> `vk apply --yes` will refuse otherwise. If you've just written
> the plan, open a PR for spec+plan and merge it before running
> this workflow.

`CLAUDE.md` gains a one-line cross-reference under "PR workflow
expectations" pointing at the gate.

### Concrete: resolving the in-flight cross-repo bug after gate ships

> **Updated 2026-05-17:** This section originally described how to resume the cross-repo bug fix after the gate landed. That plan was subsequently folded into the v2 bridge rebuild (#147 + spec at `docs/superpowers/specs/2026-05-17-v2-bridge-rebuild-design.md`'s "Multi-repo concerns" section + acceptance-tests Group H). The walkthrough below is preserved as historical context only.
>
> #134 was retired in the rebuild's cleanup. #132 closes when Phase 1 of the rebuild ships.

The cross-repo bug (#132) is still open. Its plan + spec live on
local branch `2026-05-16-cross-repo-label-ensure`; #134 is the
dispatched-but-defused tracking issue (vk-ready label removed
during the PR #135 cleanup).

Path through the new gated workflow:

1. Push `2026-05-16-cross-repo-label-ensure`; open PR for the spec
   + plan + the already-staged tracking_issue writeback for #134.
2. Merge that PR to the default branch. Now plan, spec, and
   tracking_issue are all reachable to the bridge.
3. Re-add `vk-ready` label to #134 (one-line `gh issue edit`
   command). The bridge's next tick discovers the now-reachable
   plan and dispatches the implementing agent against the
   already-existing #134.
4. Implementing agent reads the plan, follows it through TDD, opens
   a PR with the full designed test coverage.
5. PR review → merge. Cross-repo bug actually fixed, with the
   regression-prevention scaffolding intact this time.

## Release mechanics

Per `CLAUDE.md` § Release / version bumping:

| File | Field | Change |
|---|---|---|
| `pyproject.toml` | `[project].version` | `2.1.5` → `2.1.6` |
| `.claude-plugin/plugin.json` | `.version` | `2.1.5` → `2.1.6` |
| `.claude-plugin/marketplace.json` | `.plugins[0].version` | `2.1.5` → `2.1.6` |

Then `uv sync` and `uv run vk --version` to verify the CLI reports
`2.1.6`. Patch bump: this is a new guard in existing behavior, no
new user-facing workflow verb. (User-facing impact is the workflow
change to mandatory pre-merge — documented as a skill update, not a
new command.)

## Out of scope

- **No bridge-side defence-in-depth.** The bridge's legacy loop
  COULD also verify plan-locally before dispatching the implementing
  agent. With the operator-side gate enforced, that becomes
  belt-and-suspenders. Leave for a follow-up if the operator-side
  gate proves insufficient.
- **No kali-bridge venv architecture changes.** The kali bridge's
  `vk` venv is currently Dockerfile-pinned
  (`agent-images/kali/Dockerfile:59-61`), which creates a separate
  drift class: image rebuilds out of sync with plugin updates. A
  runtime version-check guard was briefly folded into this spec then
  removed. A skeleton spec for "make the kali venv hot-swappable"
  was filed then archived 2026-05-17 — the 2026-05-17 bridge audit
  found the right fix is the v2 bridge rebuild ([#147](https://github.com/derio-net/superpowers-for-vk/issues/147)),
  which makes the venv-pinning problem moot (once the bridge is the
  ~7-line thin wrapper v2 originally specced, hot-swap is trivial at
  the consumer-image level).
- **No redesign of the writeback flow.** The "derive `tracking_issue`
  from gh labels (e.g., `plan:<slug>` + `phase:N`)" v3 idea that
  would eliminate the writeback entirely stays out — file separately
  as a v3 design.
- **No automatic merge / push automation.** The gate refuses; the
  operator does the merge. We don't add `--auto-merge-plan` or
  similar.
- **No retroactive cleanup of dispatched-but-unreachable Issues.**
  #134 stays as-is (re-used manually when cross-repo work resumes).

## Verification checklist (apply during execution, not now)

- [ ] `file_on_ref` works correctly for present and missing paths
      against arbitrary refs (unit test against `tmp_path` git repo).
- [ ] `_check_plan_reachable_on_origin_head` returns the right
      missing-paths list for a fixture plan with mixed
      committed/uncommitted state.
- [ ] `vk apply --yes` rejects with exit 2 + structured error when
      any plan file or spec is missing from `origin/HEAD`.
- [ ] `vk apply --yes` proceeds normally when all files are present
      at `origin/HEAD`.
- [ ] `vk apply <plan-dir>` (dry-run) is unaffected by the gate.
- [ ] `vk apply --all` accumulates per-plan gate failures into
      `overall_rc`.
- [ ] Helpful error message when `origin/HEAD` symref is unset
      locally (includes the `git remote set-head origin --auto`
      hint).
- [ ] `vk-dispatch` skill markdown updated with the pre-flight
      paragraph.
- [ ] `CLAUDE.md` cross-reference added under "PR workflow
      expectations".
- [ ] Version bump applied to all three files; `uv.lock` updated via
      `uv sync`.
- [ ] `uv run ruff format src/ tests/`, `uv run ruff check
      src/ tests/`, `uv run mypy src/`, `uv run pytest -q --no-cov`
      all clean.

## Why this matters

The bug we hit (PR #135 incident) cost: ~1 hour of operator
attention, a revert PR, two duplicate bug filings consolidated,
real review confusion. The gate is ~30 LOC of source change + ~100
LOC of tests. Strict cost/benefit: the gate prevents a recurring
silent-failure mode for ~130 LOC of effort.

It also pairs naturally with the sibling kali-bridge venv shared-PV
redesign spec — both target silent-drift failure modes at different
layers of the dispatch pipeline. The gate prevents Issues being
created with unreachable plans; the venv redesign prevents the kali
container from running a vk version different from the plugin
manifest. Together they harden the dispatch pipeline against the
class of failures where "everything looks fine" but downstream
consumers act on stale or partial information.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-05-17-dispatch-reachability-gate | `derio-net/superpowers-for-vk` | `docs/superpowers/archived-plans/2026-05-17-dispatch-reachability-gate/` (shipped via PR #146, archived 2026-05-17) | — |
