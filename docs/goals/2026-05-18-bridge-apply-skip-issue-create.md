# Goal — Ship the bridge's apply-without-`IssueCreate` fix (test-first)

**Created:** 2026-05-18
**Triggered by:** Bridge mass-dispatch incident on 2026-05-18 (waves at 18:30 UTC and 18:48 UTC)
**Intended consumer:** Agent invoked via `/goal` in the secure pod

---

## Mission

Stop the bridge from emitting `IssueCreate` mutations during its
tick. `IssueCreate` is operator-only (via `vk apply --yes` from a
human's terminal). The bridge should call a stripped-down apply that
handles label/state/body sync but never creates issues.

Ship the fix with BDD-style integration tests that pin the right
shape **first**, then the code change, then merge. Verify in the pod
before re-enabling cron.

---

## Critical context — what happened on 2026-05-18

A two-wave production incident:

- **Wave 1 (18:30-18:32 UTC).** PR #194 (`fix(bridge): discover_plans
  uses yaml-only incomplete check`) shipped a too-permissive
  `discover_plans` filter. Bridge picked up every plan with any
  incomplete phase across all configured repos. Auto-created 19
  spurious GH issues (sfv#196-#214) — one per phase per dormant plan.

- **Wave 2 (18:48-18:49 UTC).** PR #215 reverted #194's filter. The
  revert was deployed. Bridge then ran again and created **another**
  19 spurious issues (sfv#216-#234) — same plans, same shapes.

### Why the revert didn't help

The actual mechanism isn't in `discover_plans`. It's in
`vk.bridge.__init__.py::tick()` at line ~151 calling
`apply(d, gh, plan=plan)`. `apply()` emits `IssueCreate` for any
mutation diff entry where the renderer projected `vk-ready` for a
phase with `tracking_issue=null`. That projection fires whenever
`not complete + deps satisfied + obs is None`.

Restoring the discovery gate didn't stop `apply` from creating
issues for **all partially-dispatched plans** that the gate still
admitted (e.g., a plan where Phase 1 has `vk-ready` + tracking,
but Phases 2-N have `tracking_issue: null`).

All 38 spurious issues are closed with explanatory comments.

---

## What's already in main (do NOT re-do)

| PR | Effect | Status |
|---|---|---|
| #190 | Phase 8 prompt change | merged |
| #192 | install.sh wrapper-path default to `$HOME` | merged |
| #193 | cross-repo reachability gate fix | merged |
| #194 | discover_plans yaml-only | merged then REVERTED via #215 |
| #195 | bridge per-plan logging | merged — keep all its log lines |
| #215 | revert of #194 | merged; sfv at v2.2.4 |

`main` HEAD: `aa1cb86 Revert "fix(bridge): discover_plans..."` (or
later). Current version: 2.2.4.

---

## What's already DONE — do NOT re-do

- 38 spurious issues closed with explanatory comments: sfv#196-#214
  and sfv#216-#234
- Bridge cron stopped (operator action)
- Bridge container's `~/repos/*` local checkouts have been reset to
  `origin/main` at least once today, but the bridge likely re-dirtied
  them via writebacks before being stopped. **Confirm state** with
  `git -C ~/repos/<r> status` before running any tests. Reset again
  if dirty:

  ```bash
  for r in agent-images frank willikins vibe-kanban superpowers-for-vk; do
    git -C ~/repos/$r status -s | head -3
    git -C ~/repos/$r reset --hard origin/main
  done
  ```

---

## The fix design (high level)

Two changes in `src/vk/`:

1. **`src/vk/apply.py`** — add a parameter to `apply()`:
   `skip_issue_create: bool = False`. When `True`, filter out
   `IssueCreate` mutations from the diff before applying. Log a
   `WARNING` for each skipped `IssueCreate` so the operator knows
   there's pending dispatch work that needs `vk apply --yes`. The
   default `False` keeps operator-side `vk apply --yes` behavior
   unchanged.

2. **`src/vk/bridge/__init__.py`** at the `tick()` callsite (~line
   151), change:
   ```python
   apply(d, gh, plan=plan)
   ```
   to:
   ```python
   apply(d, gh, plan=plan, skip_issue_create=True)
   ```

This is **~30 lines of source code**. The tests are the bulk of the
work.

---

## TDD discipline — failing tests FIRST

**DO NOT touch `src/vk/apply.py` or `src/vk/bridge/__init__.py`
until the failing tests are written and they fail for the RIGHT
reason** (the missing parameter / unfiltered IssueCreate — not a
typo or import error).

Verify locally:

```bash
cd <worktree>
uv run pytest tests/integration/test_bridge_no_issue_create.py -v --no-cov
```

Then make the code changes. Then re-run and confirm green. Then full
suite:

```bash
uv run pytest tests/ -q --no-cov
```

---

## BDD test scenarios to cover

Create `tests/integration/test_bridge_no_issue_create.py` with these
scenarios. Use `GIVEN`/`WHEN`/`THEN` structure in docstrings (matches
the repo's existing style — see `tests/integration/test_v2_full_lifecycle.py`
for the pattern). Use `tests.unit.fakes.FakeGhClient` for the gh
double; use a minimal MCP stub class (no real MCP needed for these
tests).

### Scenario 1 — the headline fix

```
GIVEN  a plan with Phase 1 vk-ready + tracking_issue set AND
       Phases 2..N with tracking_issue=null
WHEN   bridge tick runs
THEN   the gh client receives ZERO IssueCreate calls
AND    each null-tracking-issue phase logs a WARNING saying
       "phase N: would have created Issue; skipping (operator-only
       via `vk apply --yes`)"
```

### Scenario 2 — operator path still works

```
GIVEN  the same plan
WHEN   operator runs `vk apply --yes <plan>` (default
       skip_issue_create=False)
THEN   the gh client receives N-1 IssueCreate calls (Phases 2..N)
AND    plan yaml writebacks set tracking_issue on Phases 2..N
```

### Scenario 3 — mixed-state plan, label sync still happens

```
GIVEN  a plan where:
         Phase 1 = vk-ready + tracking_issue set
         Phase 2 = vk-blocked + tracking_issue set
         Phase 3 = tracking_issue=null
WHEN   bridge tick runs
THEN   Phase 1's labels are sync'd (IssueLabelChange OK)
AND    Phase 2's state is sync'd (IssueStateChange OK if needed)
AND    Phase 3 produces ZERO IssueCreate
AND    Phase 3 logs the WARNING about pending dispatch
```

### Scenario 4 — fully-dispatched plan, no IssueCreates ever

```
GIVEN  a plan where every phase has tracking_issue set
WHEN   bridge tick runs
THEN   ZERO IssueCreate calls (no nulls to create)
AND    ZERO warnings (nothing to skip)
```

### Scenario 5 — regression guard for today's incident

```
GIVEN  the stoa-company-creation plan shape (one phase with
       vk-ready + tracking_issue set, 8 phases with
       tracking_issue=null)
WHEN   bridge tick runs ON THIS PLAN
THEN   ZERO IssueCreate calls
AND    8 WARNING log messages, one per undispatched phase
```

Each scenario = separate test function. Don't share fixture state
between scenarios; clean setup each time.

---

## Code pointers

| Path | Role |
|---|---|
| `src/vk/apply.py` | `IssueCreate` handling, `gh.create_issue` call site |
| `src/vk/bridge/__init__.py:tick()` | The line to change (~151) |
| `src/vk/diff.py` | Emits `IssueCreate` mutations |
| `src/vk/render.py::_lifecycle_label()` | Projects `vk-ready` |
| `tests/integration/test_v2_full_lifecycle.py` | BDD pattern reference |
| `tests/integration/test_bridge_cli.py` | Bridge cli test patterns (uses real bare git repos for E4 auto-pull testing) |
| `tests/unit/fakes.py::FakeGhClient` | gh double; track `.calls` for IssueCreate-call assertions |
| `src/vk/diff.py::IssueCreate` | The dataclass to filter on |

---

## Verification approach

After tests pass locally + lint clean + version bump:

1. **Open PR.** CI must show `lint` + `test` + `typecheck` +
   `version-sync` all green.
2. **Merge.**
3. **In the bridge pod:** re-run `install.sh` to upgrade vk to
   v2.2.5 (assuming this is the next patch — confirm by checking
   main's `pyproject.toml` AFTER your PR merges).
4. **Re-enable bridge cron.**
5. **Watch the next 2-3 ticks.** Expected behavior:
   - Discover plans still finds the same set (no change to discover).
   - For each plan, tick should NOT spawn new issues.
   - Look for `WARNING` lines like `would have created Issue;
     skipping` for plans with null-tracking-issue phases.
   - For `agent-images` cutover (#82): it has all phases already with
     `tracking_issue` + #82 has `vk-ready` → bridge should dispatch
     the **workspace** for it. The dispatch path (`dispatch_phase`)
     is separate from `IssueCreate` and is fine.
6. **If anything looks wrong, STOP THE CRON IMMEDIATELY.** Don't
   iterate live in production.

---

## Worktree convention

Per the org rule, use git worktrees for isolation:

```bash
cd /home/claude/repos/superpowers-for-vk
git fetch origin
git worktree add -b fix/apply-skip-issue-create-for-bridge \
  ../sfv-wt-apply-fix origin/main
cd ../sfv-wt-apply-fix
```

After PR merges, clean up:

```bash
cd /home/claude/repos/superpowers-for-vk
git worktree remove ../sfv-wt-apply-fix
git branch -D fix/apply-skip-issue-create-for-bridge
```

---

## Version + PR conventions

- Bump 2.2.4 → 2.2.5 via `scripts/bump-version.py patch`.
- PR title shape: `fix(apply+bridge): skip IssueCreate in bridge tick`
- PR body must reference this incident: closed sfv#196-#214 +
  sfv#216-#234, PR #194 reverted via #215. Describe the design choice
  (the `skip_issue_create=True` param at the bridge callsite).
  Summarize test coverage with the 5 BDD scenarios above.
- Pre-push (per `CLAUDE.md`):
  ```bash
  uv run ruff format src/ tests/
  uv run ruff check src/ tests/
  uv run pytest tests/ -q --no-cov
  ```

---

## Open questions to resolve while implementing

1. **Should the WARNING include the phase title?** Probably yes —
   operators see this and need to know which work is pending.

2. **Should there be a metric for "skipped IssueCreate"?** The bridge
   already has `_metrics.push_failure_total(reason=...)`. Consider
   adding `push_skipped_create_total` or reusing the existing one
   with a clear reason label.

3. **Are there other call sites of `apply()` from non-operator
   contexts?** `grep -rn "from vk.apply import apply" src/` to verify.
   The bridge `tick()` and the operator `vk apply --yes` should be
   the only two. If there are others, evaluate whether they should
   also pass `skip_issue_create=True`.

---

## When done — reporting

Comment on the originating chat thread with:
1. **PR URL**
2. **Test count summary** — e.g., "5 integration scenarios + N unit
   tests, all green"
3. **Post-deployment verification** — e.g., "bridge ran 3 ticks at
   v2.2.5 with no spurious issues; `agent-images` cutover dispatched
   the workspace for #82"

---

## References

- Incident closed-issue ranges: sfv#196-#214, sfv#216-#234 (all
  CLOSED with explanatory comments on 2026-05-18)
- PRs referenced: #190, #192, #193, #194, #195, #215
- This brief: `docs/goals/2026-05-18-bridge-apply-skip-issue-create.md`
