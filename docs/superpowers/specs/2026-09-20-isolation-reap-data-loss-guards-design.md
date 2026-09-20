# A merged PR is not permission to delete a working tree

- **Issues:** [#435](https://github.com/derio-net/super-fr/issues/435) (dirty worktree
  destroyed) · [#467](https://github.com/derio-net/super-fr/issues/467) (unpushed commit
  destroyed)
- **Date:** 2026-09-20
- **Status:** designed

## 1. Problem

`fr`'s isolation gc reaps a workspace the moment its PR reads `MERGED`, and the teardown
path it calls guards exactly one thing: an **open** PR. Everything else about the
workspace — uncommitted edits, a commit that never left the machine — is deleted without a
prompt, a warning, a stash, or a salvage copy.

Verified live on `main` at `a5cd114`:

| | |
|---|---|
| `isolation/local.py:696` | `pr_state == "MERGED"` → `down(state, force=False)` — no precheck of any kind |
| `isolation/local.py:564` | `_down_worktree_tail`: OPEN-PR guard, then `git worktree remove --force`, unconditionally |
| `isolation/local.py:810` | `_merged_by_content`: **does** check `git status --porcelain` before it will classify |

The last row is the shape of the defect. The **speculative** path — "I think this
PR-less branch may have been squash-merged" — refuses to act on a dirty tree. The
**authoritative** path — "GitHub says this PR merged" — does not check at all. Confidence
in the *classification* was silently read as confidence about the *working tree*, and
those are unrelated pieces of state.

### 1.1 The two reported losses

**#435 — uncommitted work.** A workspace on `derio-homelab/homelab` held a series of
uncommitted edits: spec changes, two diagrams, an acceptance-row deletion, a plan phase
renumber, and a newly authored phase file. The operator merged the PR from GitHub. The
next `fr` command — something innocuous, in a different session — reconciled the
workspace as merged and deleted the directory. Nothing had ever been committed, so there
was no object to `reflog` back to. Unrecoverable.

**#467 — an unpushed commit.** `fr isolation up --branch <new>` fired its opportunistic
sweep, which reaped the merged `feat/issue-464` workspace while it held a local-only
commit. The objects likely survive in the shared store, but nothing in `fr` points back
at them, which is the same thing as gone for anyone who is not already a git plumber.

### 1.2 Why this is a bug and not user error

The person who loses the work is not the person whose action destroys it, and neither is
told:

- the merge happens on GitHub, in a different context to the session holding the work;
- that session gets no signal a merge occurred;
- the reap fires on the *next* `fr` command — plausibly `fr isolation up` for something
  else entirely, or a `status` in a third repo, because the sweep is host-wide;
- there is no dirty-tree check anywhere on that path.

So the failure is structurally easy to lose and impossible to see coming. It is also this
repo's recurring failure class inverted: usually an operation reports success while doing
nothing; here one reports success while destroying something.

### 1.3 What #435 asked for, and what it got wrong

#435 proposed a `git status --porcelain` check and suggested "untracked files are
arguably fine to ignore". Its own narrative refutes that: the lost work included a *newly
authored phase file*, which is untracked by definition. The tentative carve-out would not
have saved the work the issue was filed about.

#467 asked to "refuse or warn when the workspace branch is ahead of its remote". Read
literally, that check goes silent in precisely the situation that fired it — see §3.3.

## 2. Goal

A workspace is never destroyed while it holds work that exists nowhere else.

**In scope**

1. A **dirty-worktree** guard and an **unlanded-content** guard, evaluated *before* any
   destructive step, on every path that reaps: `fr isolation down`, `down --all`,
   `down --worktree`, and both of gc's reap branches (`merged`, `merged-by-content`).
2. Refusal messages that name the branch and what would be lost, and say what to do.
3. `--force` preserved as the single deliberate escape, with its scope and its cost
   stated where an operator and an agent will each read it.
4. `gc --dry-run` reporting the refusal honestly, as a skip rather than a would-reap.

**Out of scope**

- Salvage refs (`refs/fr-salvage/<branch>`) — decision `d3`. #435 offered these only as a
  *weaker fallback* for the case where reaping must stay unconditional, which this change
  ends. A recovery ref nobody knows to look for is its own trap.
- `external` mode. `ExternalContainerTarget.gc` reports and never reaps
  (`isolation/external.py:241`), and its `down` removes no worktree — there is nothing
  here to guard.
- #432's post-reap guard-denial message. Different failure ("the message after the reap
  is confusing"); this spec is "the reap should not have happened".
- `verify_merge`'s `default_branch: str = "main"` default, which is latently wrong for a
  repo on `master`. Real, adjacent, and not this change — §3.4 passes a resolved branch
  rather than relying on it.

## 3. Design

### 3.1 One hazard check, one enforcement site

The guards live in `_down_worktree_tail`, immediately after the existing OPEN-PR guard
and before `_teardown_container`. That is the single narrow waist every reap already
passes through — it is shared by `LocalWorktreeDevcontainerTarget` and
`HostWorktreeTarget` (the modes differ only in `_teardown_container`), and gc reaches it
by calling `down(state, force=False)` on a sibling Target. Guarding there covers every
caller by construction, including ones not yet written.

```python
@dataclass
class ReapHazard:
    """Work that a reap would destroy, and how to keep it."""
    kind: str      # "dirty-worktree" | "unlanded-content" | "unverifiable"
    detail: str    # names the branch and what would be lost


class ReapRefused(IsolationError):
    """Raised INSTEAD of tearing down. Carries the hazard so gc can classify
    a refusal as a deliberate skip rather than a failure."""
    def __init__(self, hazard: ReapHazard) -> None: ...
```

`Target._reap_hazard(state) -> ReapHazard | None` is a **pure query** — it runs no
destructive command — which is what lets `gc --dry-run` ask the same question the live
path enforces, instead of predicting a different answer (§3.5).

### 3.2 Guard one — the worktree is dirty (#435)

`git status --porcelain` in `state.worktree`. Non-empty output is a hazard; so is a
**non-zero return code**, which is the #354 invariant applied here: a failed query is not
evidence of a clean tree. Decision `d1`: tracked and untracked alike, no
`--untracked-files=no`. Ignored paths (`.venv/`, `.fr-isolation`, `__pycache__/`) never
appear in `--porcelain`, so routine workspace clutter cannot wedge the sweep.

This is deliberately the identical predicate `_merged_by_content` already applies at
`local.py:810`. The asymmetry that caused #435 is closed by making the authoritative path
ask what the speculative path always asked.

### 3.3 Guard two — the branch holds content that never landed (#467)

Spelled **content-based against `origin/<default>`**, not `@{upstream}..HEAD` — decision
`d2`.

The literal reading of #467 fails on its own scenario. GitHub's auto-delete-branch is the
norm here, so after a squash-merge the remote branch is *gone*: `@{upstream}` does not
resolve, the check finds nothing to compare, and it goes quiet in exactly the shape that
fired the issue. Worse, it would answer the wrong question even when it worked — the
operator does not care whether commits were *pushed*, they care whether the work
*survives the deletion*.

The repo already owns the right primitive. `branch_changes_present` (`local.py:178`)
compares final file **content** against a base ref, with per-line containment as a
fallback, and is documented as squash/rebase/merge-commit safe precisely because an
ancestry check false-negatives on a squash. `verify_merge` (`local.py:498`) already wraps
it with the fetch that keeps a stale local ref from producing a wrong answer.

So: `missing` non-empty ⇒ hazard, naming the paths. This catches both #467's local-only
commit and, for free, a commit **pushed** to the branch after the merge — the #320 orphan,
which is equally unmerged work and equally destroyed today.

### 3.4 Fetching, and the cost of being conservative

The content guard must fetch first, or it inverts into a false-refusal machine: a local
`origin/main` that predates the merge does not contain the branch's own merged content,
so every genuinely-merged workspace would read as unlanded. `verify_merge` already does
`git fetch <remote> <default>`; `_reap_hazard` reuses it, passing the **resolved** default
branch (`_resolve_default_branch()`) rather than the `"main"` literal default.

Two consequences, both accepted:

- **One fetch per about-to-be-reaped workspace, per sweep.** Only workspaces that would
  otherwise be destroyed pay it; `open` and `no-pr` verdicts return before the guard runs.
  Ordering matters: the cheap local dirty check runs first and short-circuits.
- **A failed fetch is a hazard** (`kind="unverifiable"`), not a pass. Offline, gc warns
  instead of reaping. This matches `_merged_by_content`'s documented stance that a stale
  ref "only DEFERS a reap to a later sweep, never causes a wrong one", and it is the
  correct direction: a deferred reap costs disk, a wrong one costs work.

### 3.5 What gc reports

`_gc_one` changes in two places, both reap branches:

- **live** — catch `ReapRefused` *specifically*, before the existing broad `except
  Exception`, and emit `GcAction(wt, branch, verdict, "skipped", hazard.detail)`. A
  refusal is a decision, not a failure; classifying it as `reap-failed` would read as
  breakage and train the operator to ignore it. The broad handler stays exactly as it is
  for genuine teardown errors.
- **dry-run** — call `_reap_hazard` and report `("would-skip", hazard.detail)` instead of
  `"would-reap"`. A dry run that promises an action the live run will refuse is not a
  preview.

`GcAction`'s `verdict` stays the classification (`merged`, `merged-by-content`) and
`action` carries the outcome, so no new verdict vocabulary is needed. `"would-skip"` joins
the documented action list.

### 3.6 `--force`, and who is allowed to type it

`--force` becomes the escape for **all three** guards. Its current docstring claim —
"`--force` bypasses the open-PR guard ONLY" (`local.py:552`) — stops being true and is
rewritten in the same change, as is its `--help` string, which must now say what is
destroyed rather than only what is bypassed.

Decision `d3` attaches an obligation the code cannot enforce: **an agent may not reach for
`--force` on its own initiative.** It requires that the operator asked for it *and* was
told what would be destroyed. This lands as prose in
`plugins/super-fr/skills/fr-isolation/SKILL.md` (canonical) plus its generated
`.opencode/skills/` mirror via `scripts/sync-opencode.py`. It is stated as prose, and
stated as *knowingly* prose: there is no tripwire for "an agent decided by itself", and
pretending otherwise is the fixture-composition defect this repo already has a scar from.

### 3.7 `_down_all` is currently wrong in the same breath

`isolation_cmd.py:478` documents "that open-PR check is the only `IsolationError` `down`
raises, so 'kept' always means an open PR", and its summary hardcodes
`kept (open PR — rerun with --force)`. Both become false the moment a second refusal
exists. `_down_all` collects each refusal's message per branch and reports the reasons it
actually got, rather than asserting one.

### 3.8 The message

Refusals name the branch, the hazard, and the three ways out — the shape #435 asked for:

```
isolation: fix/sitia-site-services is merged but its worktree has 7 uncommitted
changes — refusing to reap (nothing was deleted).
  docs/superpowers/specs/...-design.md, docs/.../phase-04.md, +5 more
Commit or stash them, or destroy them deliberately with
`fr isolation down --branch fix/sitia-site-services --force`.
```

```
isolation: fix/issue-464 is merged but 2 file(s) changed on the branch are not on
origin/main — refusing to reap (nothing was deleted).
  packages/fr/src/fr/isolation/local.py, tests/unit/test_isolation_gc.py
Push the branch, or destroy the work deliberately with
`fr isolation down --branch fix/issue-464 --force`.
```

## 4. Risks

| Risk | Judgement |
|---|---|
| **False refusal turns gc into a permanent warner.** `branch_changes_present` is conservative by design: a branch whose only change is a pure deletion reports `missing`, so it never reaps. | Accepted and named. The failure is a nag, not a loss, and `--force` clears it. It is also the one risk unit tests cannot settle — hence the live sweep in the Test Plan (`d4`). |
| **A fetch per candidate workspace slows the opportunistic sweep**, which fires on every `up`/`down`. | Bounded: only reap candidates fetch, the local dirty check short-circuits first, and the sweep is already detached and best-effort. |
| **Offline hosts stop reaping.** A failed fetch is `unverifiable` ⇒ refuse. | Correct direction, and self-healing on the next online sweep. Disk is cheaper than work. |
| **`--force`'s blast radius grows** — one flag now bypasses three guards. | The alternative (a flag per guard) makes the destructive path harder to reason about, not safer. Mitigated by the help text (§3.6) and the agent obligation (`d3`). |
| **A dirty PR-less workspace reports `no-pr`, not the dirty hazard**, because `_merged_by_content` returns `False` before the guard is ever consulted. Its message ("no PR — `fr isolation down` when done") is then mildly misleading. | Documented residual. That path already refuses to reap, so no work is at risk; sharpening its message is cosmetic and out of scope. |

## 5. Test Plan

### Offline (unit, fake runner)

1. **#435 regression.** A MERGED workspace with dirty `--porcelain` output → `down()`
   raises `ReapRefused(kind="dirty-worktree")`, and `git worktree remove` was **never
   invoked** (assert on the recorded command list, not just the exception).
2. Untracked-only dirt refuses too — the carve-out #435 floated, and `d1` rejected.
3. A failed `git status` (non-zero) refuses, rather than reading as clean.
4. **#467 regression.** A MERGED workspace whose `branch_changes_present` reports
   `missing` → `ReapRefused(kind="unlanded-content")`; no worktree removal.
5. A merged workspace with a commit **pushed** after the merge (#320 orphan) refuses by
   the same guard.
6. A failed fetch → `ReapRefused(kind="unverifiable")`.
7. **Clean + landed still reaps** — the guard does not break the happy path, on both the
   `merged` and `merged-by-content` branches.
8. `--force` tears down through every hazard, and still performs the #354 post-condition
   verification (force bypasses guards, never verification).
9. `gc` live: a refused reap surfaces as `action="skipped"` with the hazard detail, not
   `reap-failed`.
10. `gc --dry-run`: the same workspace reports `would-skip`, not `would-reap`.
11. `down --all`: a hazard-refused workspace is `kept` and the summary states *its*
    reason, not a hardcoded "open PR".
12. Host-worktree mode inherits both guards (shared `_down_worktree_tail`); external mode
    is untouched.
13. Prose tripwire: the shipped and mirrored `fr-isolation` SKILL both carry the `--force`
    obligation, and `scripts/sync-opencode.py --check` is clean.

### Post-merge, operator-driven (`d4`)

14. Stage a merged workspace, dirty it, run `fr isolation gc` — confirm the refusal
    message and that the directory survives.
15. Stage a merged workspace holding a local-only commit — same.
16. `fr isolation gc --dry-run` across the real host — confirm genuinely-merged clean
    workspaces still report `would-reap`. This is the false-refusal check; nothing
    offline can stand in for it.

## 6. Evidence hygiene

#435 originates on `derio-homelab/homelab`, inside the `derio-net` orbit, and #467 on this
repo — no third-party host, org, or repo name enters this spec, its fixtures, or its PR
body. Fixtures use synthetic branch and path names throughout.

## Implementation Plans

_(to be linked by `fr-plan`)_
