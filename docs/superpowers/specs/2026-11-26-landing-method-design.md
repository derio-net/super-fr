# Landing method: a configured merge_method wins, and `land: push` lands only merge commits

Issues: derio-net/super-fr#1705, derio-net/super-fr#1702, derio-net/super-fr#1603.

## Background

The wave merge queue (spec `2026-11-19-wave-merge-queue`) picks one merge method per repo and
builds every combination in it. Three defects meet in that choice.

- **The viewer default beats the configured method (#1702).** `choose_method`
  (`packages/fr/src/fr/triage/batch_merge.py:92`) returns, in order: an explicit `--method`, the
  forge's default, the configured `merge_method` of `.fr/triage.yaml`, the one allowed method.
  Under `forge.api: graphql` the forge's default is the viewer's own
  `viewerDefaultMergeMethod` (`packages/fr/src/fr/real_ghclient.py:590-606`), a per-user UI
  preference. So a repo's configured `merge_method` is reached only under `rest`
  (`real_ghrestclient.py:1024`, which names no default), and the method the queue lands in
  changes when the operator clicks a different button in the GitHub UI.
- **A squash landed by push closes the PR unmerged (#1705).** Under `queue.land: push`
  (`.fr/triage.yaml`'s default) `land_push` (`packages/fr/src/fr/triage/queue_exec.py:607`)
  moves the default branch by one atomic leased push and, for `squash` and `rebase`,
  force-moves each landed PR's head ref to the PR's own commit in the combination. GitHub marks
  a PR merged by push only when the PR's head commit becomes reachable from the base. A squash
  or rebase commit is a new commit, so GitHub records the PR **closed, not merged**: its
  `Closes` lines never fire. Live 2026-11-25: the viewer default had flipped to `SQUASH`, the
  queue landed #1704 that way, and GitHub reads it `CLOSED` with `mergedAt: null`. Only a merge
  commit (second parent = the PR's head) lands a GitHub PR by push. (`land: merge` goes through
  the forge's merge API, where every method marks the PR merged.)
- **Rebase breaks the release's first-parent cross-check (#1603).** `scripts/release.py`'s
  `logged_prs` (`scripts/release.py:746`) reads `git log --first-parent <last final>..HEAD` and
  takes each subject's `(#N)` or `Merge pull request #N`. A rebase landing puts the branch's own
  commit subjects on that line: they carry no PR number, or an issue's. `waiting_prs`
  (`scripts/release.py:767`) then reports the PR as missed and the gate state as unknown, which
  cuts RCs only. It fails safe, never a wrong final.
- **A closed-unmerged landing also makes the gate state unknown.** #1704's squash commit
  `ff14a97ae` sits on `main`'s first-parent line with subject `… (#1704)`. `waiting_prs` reads
  `gh pr list --state merged`, which does not return #1704, so every release run until the next
  final tag reads "the merged-PR read misses #1704" and cuts RCs only. `fr release status`
  (`packages/fr/src/fr/release_status.py:191`) keeps only PRs whose `mergedAt` is set.

This repo's `.fr/triage.yaml` says `merge_method: squash` and `queue.land: push`: a combination
that only #1702's bug kept from landing as squash.

The queue runs only on GitHub: `forge_refusal` (`queue_exec.py:729`) holds a glab or tea repo.
So "under `land: push`" below always means "on GitHub".

## Requirements

R1. The merge method is, in order: an explicit `--method`; else the `merge_method` configured in the repo's `.fr/triage.yaml`; else the forge's default (the viewer default under `graphql`); else the one method the repo allows; else a refusal that names `merge_method` and `--method`. A configured or explicit method the repo does not allow is refused, as today.
R2. Under `queue.land: push`, a chosen method of `squash` or `rebase`, whatever its source, holds the repo's queue: the queue builds and lands nothing for that repo, and the held reason names the method, where it came from, that GitHub closes such a PR unmerged, and the fix (`merge_method: merge` in `.fr/triage.yaml`, or `queue.land: merge`). `fr triage batch merge --method squash|rebase` under `land: push` is held the same way.
R3. `land_push` itself refuses a method other than `merge` without pushing anything, as a second guard behind R2.
R4. Under `queue.land: merge`, a chosen method of `rebase` lands, and the driver prints one warning per repo per driver process: a rebase landing puts the branch's commit subjects on the default branch's first-parent line, so a release that attributes PRs by first-parent `(#N)` or `Merge pull request #N` (as this repo's `release.py` does) cannot see the PR; use `merge` or `squash`.
R5. `fr cloud doctor`'s `merge_method` check reports the R2 refusal as a failure for a repo whose `.fr/triage.yaml` sets `queue.land: push` (or leaves it at its default) and whose chosen method is `squash` or `rebase`.
R6. This repo's `.fr/triage.yaml` sets `merge_method: merge`, with its comment saying why.
R7. In `release.py`, a PR that the first-parent log names and the merged-PR read misses is read by number. When the forge reports it `CLOSED` with no `mergedAt`, it counts as landed: it joins the release facts with its labels and with `mergedAt` set to the committer date of the first-parent commit that names it, so its gate labels still decide whether it waits. A PR the read cannot fetch, or that is `OPEN`, keeps the gate state unknown, as today.
R8. The pages that describe the method choice say R1's order and R2's rule: the fr-triage skill's "The driver" paragraph, `docs/explainers/fr-wave-driver.md` and `docs/cloud-setup.md`.

## Design

### Method choice (R1)

`choose_method(explicit, methods, *, configured=None)` keeps its signature and its refusals; only
the order changes: explicit, configured, default, single. Its docstring says the configured
method is a repo decision and the viewer default only a fallback. Both call sites
(`triage_batch_cmd.py:4424` and `:4446`, the driver's `merge_ctx`) and `fr cloud doctor`
(`cloud.py:260`) are unchanged.

### The landing rule (R2, R3, R5)

A pure function in `queue_exec.py` beside `queue_refusal`:

```python
def landing_refusal(land: str, method: str, *, source: str) -> str | None:
    """R2: under `land: push` only a merge commit lands a GitHub PR by push."""
```

`source` is `"--method"`, `"merge_method in .fr/triage.yaml"`, `"the forge's default"` or
`"the one allowed method"`. To have it, `choose_method` gains a sibling
`choose_method_source(...) -> tuple[str, str]` that returns the method and its source;
`choose_method` returns its first element, so every existing caller is unchanged.

The driver's `_queue_refusal` (`triage_batch_cmd.py:7053`) calls it last, after
`queue_refusal`, with `self._queue_block(facts, repo).land` and the method of the repo's merge
context (`_ctx_or_hold`, cached per repo, so no new forge read). A context it cannot build
leaves the existing hold reason in place. A refused repo becomes `queue-held` through the
existing `held_plan` path, so the pass's `queue` line, the board and Needs you now show it with
no new plumbing; `batch merge` uses the same driver (`_Driver.queue_only`), so R2 covers it.

`land_push` checks `method != "merge"` first and returns `LandResult("held", …)` with the same
reason and no push. Its squash/rebase head-ref rewrite (`refspecs.append((x.head if method ==
"merge" else x.commit, ref))`) becomes the merge case alone. Building combinations in
`squash` and `rebase` stays: `land: merge` still compares the forge's result tree with them.

`fr cloud doctor` reads `queue.land` from the same `.fr/triage.yaml` it already reads
`merge_method` from (`cloud.py:266`, `_configured_merge_method`) and fails the `merge_method`
check with `landing_refusal`'s text.

### The rebase warning (R4)

Under `land: merge` with `rebase`, `_queue_refusal` returns None and the driver says the R4
warning through `_report_once` (key `rebase-first-parent\0<repo>`), so it prints once per
process.

### This repo (R6)

`.fr/triage.yaml`: `merge_method: merge`, the comment replaced: under `queue.land: push` only
a merge commit makes GitHub mark the PR merged (#1705), and this repo's release reads
first-parent `Merge pull request #N` subjects.

### release.py (R7)

In `waiting_prs`, before raising on `missing`: for each missing number, `cmds.gh_read(["pr",
"view", str(n), "--json", MERGED_PR_FIELDS + ",state"])`. A `CLOSED` PR with no `mergedAt` is
added to `prs` with `mergedAt` replaced by the committer date (`%cI`) of the first-parent
commit that named it. For that, `logged_prs` gains a sibling `logged_pr_dates(repo, tag) ->
dict[int, str]` that keeps the first (newest) commit's date per number, and `logged_prs`
returns its keys. Anything else (a failed read, `OPEN`, `MERGED` that the list missed for
index lag) keeps today's `GateStateUnknownError` naming the PR. The `state` key is dropped
before the facts are written, so `fr release status`'s input shape does not change.

### Docs (R8)

The fr-triage skill sentence "The merge method is the forge's default, else `merge_method` …"
becomes R1's order plus R2's rule; the explainer's paragraph at `fr-wave-driver.md:305` and
`cloud-setup.md`'s merge-method row say the same. The skill's OpenCode and Hermes mirrors are
regenerated.

## Design shape

```
packages/fr/src/fr/
  triage/batch_merge.py     ~ choose_method: explicit > configured > default > single
                            + choose_method_source: (method, where it came from)
  triage/queue_exec.py      + landing_refusal(land, method, source)   R2
                            ~ land_push: refuses non-merge, no head-ref rewrite   R3
  commands/triage_batch_cmd.py
                            ~ _queue_refusal: + landing_refusal, + rebase warning  R2 R4
  cloud.py                  ~ merge_method check reads queue.land          R5
scripts/release.py          ~ waiting_prs: closed-unmerged landing counts   R7
                            + logged_pr_dates
.fr/triage.yaml             ~ merge_method: merge                           R6
plugins/super-fr/skills/fr-triage/SKILL.md, docs/explainers/fr-wave-driver.md,
docs/cloud-setup.md         ~ method order and the push rule                R8
```

```
method = explicit ?? configured ?? forge default ?? only allowed
land: push  + method ∈ {squash, rebase}  →  queue-held (names fix)    ← #1705, #1603
land: push  + merge                       →  lands; GitHub reads MERGED
land: merge + rebase                      →  lands + one warning      ← #1603
release: first-parent (#N) ∉ merged list → pr view N
    CLOSED, mergedAt null → counted, mergedAt = commit date            ← #1704
    else                  → unknown (RC only), as today
```

## Verification

strategy: none
- landing-method-order: none — unit tests drive `choose_method` and `choose_method_source` over every source combination in this PR's CI
- landing-method-push-merge-only: none — unit tests drive `landing_refusal`, `land_push`'s guard, the driver's held plan and `fr cloud doctor`'s check with fakes in this PR's CI
- landing-method-rebase-warning: none — a unit test drives the driver's once-per-process warning in this PR's CI
- release-closed-unmerged-landing: none — unit tests drive `waiting_prs` with a fake `gh_read` and a git fixture in this PR's CI
gate: developer

## Test Plan

- pre-merge — CI: `choose_method` returns the configured method over a forge default, the default when nothing is configured, the single allowed method last, and refuses a disallowed explicit or configured method (row `landing-method-order`).
- pre-merge — CI: under `land: push` a `squash` or `rebase` method from each source holds the queue with a reason naming the method, its source and the fix; `merge` does not; `land_push` with a non-merge method pushes nothing; `fr cloud doctor` fails the check (row `landing-method-push-merge-only`).
- pre-merge — CI: under `land: merge` a `rebase` method prints the warning once per repo per process (row `landing-method-rebase-warning`).
- pre-merge — CI: `waiting_prs` counts a first-parent PR the forge reports `CLOSED` and unmerged with the commit's date and its labels, and stays unknown for an `OPEN` PR or a failed read (row `release-closed-unmerged-landing`).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-26-landing-method | `derio-net/super-fr` | `2026-11-26-landing-method` | — |
