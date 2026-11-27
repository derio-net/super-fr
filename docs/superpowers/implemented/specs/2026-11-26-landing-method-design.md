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
R2. Under `queue.land: push`, a chosen method of `squash` or `rebase`, whatever its source, holds the repo's queue: the queue builds and lands nothing for that repo, and the held reason names the method, where it came from, that GitHub closes such a PR unmerged, and a fix that works for the repo: `merge_method: merge` in `.fr/triage.yaml` when the repo allows merge commits, else allowing merge commits in the repo's settings; `queue.land: merge` either way. `fr triage batch merge --method squash|rebase` under `land: push` is held the same way. The rule holds the queue's planned builds and landings only: the resume pass, which records a landing an earlier driver already pushed and makes none, still runs for the repo. A method that cannot be chosen (a `ConfigError`) holds the queue with that error's text; a failed merge-methods read holds it for the pass with the read's error, and the next pass reads again; neither raises out of a dry run or the snapshot reads.
R3. `land_push` pushes nothing, and returns `held` with the R2 reason, unless the method is `merge` and every landing's combination commit is a merge whose second parent is that PR's head. So a combination built in `squash` or `rebase` before the method changed is never landed by push.
R4. Under `queue.land: merge`, a chosen method of `rebase` lands, and the driver prints one warning per repo per driver process: a rebase landing puts the branch's commit subjects on the default branch's first-parent line, so a release that attributes PRs by first-parent `(#N)` or `Merge pull request #N` (as this repo's `release.py` does) cannot see the PR; use `merge` or `squash`.
R5. `fr cloud doctor`'s `merge_method` check reports the R2 refusal as a failure for a repo whose `.fr/triage.yaml` has a `queue:` block with `land: push` (or no `land`, whose default is `push`) and whose chosen method is `squash` or `rebase`. A repo with no `queue:` block keeps today's check.
R6. This repo's `.fr/triage.yaml` sets `merge_method: merge`, with its comment saying why.
R7. In `release.py`, a PR that the first-parent log names and the merged-PR read misses is read by number. When the forge reports it `CLOSED` with no `mergedAt`, it counts as landed: it joins the release facts with its labels and with `mergedAt` set to the committer date of the first-parent commit that names it, so its gate labels still decide whether it waits. A PR the read cannot fetch, or that is `OPEN`, keeps the gate state unknown, as today.
R8. The text that describes the method choice, push landing or release gating says R1's order, R2's rule and R7's reading: the fr-triage skill's "The driver" paragraph, `docs/explainers/fr-wave-driver.md`, `docs/cloud-setup.md`, `docs/merge-protection.md`'s `queue.land: push` paragraph and AGENTS.md's "Release gating" paragraph. Every other page whose `covers:` this change touches has its `reviewed:` stamp moved, or its text fixed where it is now false.
R9. This change amends spec `2026-11-19-wave-merge-queue` R10: under `queue.land: push` only merge commits land. The merged acceptance row `wave-queue-land-methods` is amended to say so (squash and rebase land only through `queue.land: merge`), and every merged row citing a land test this change rewrites or renames has its level re-pointed by amendment. The fixtures that land squash or rebase by push move to `merge`, keeping each R10 proof they make (the atomic push, the leases, the protection refusals, resume).

## Design

### Method choice (R1)

`choose_method(explicit, methods, *, configured=None)` keeps its signature and its refusals; only
the order changes: explicit, configured, default, single. Its docstring says the configured
method is a repo decision and the viewer default only a fallback. A sibling
`choose_method_source(...) -> tuple[str, str]` returns the method and where it came from
(`"--method"`, `"merge_method in .fr/triage.yaml"`, `"the forge's default"`, `"the one allowed
method"`); `choose_method` returns its first element, so every caller
(`triage_batch_cmd.py:4424`, `:4446`, `cloud.py:260`) is unchanged. The existing test case
"the forge's own default still wins where it names one" (`tests/unit/test_triage_batch_merge.py:346`)
encodes the old order and is rewritten.

### The landing rule (R2, R3, R5)

A pure function in `queue_exec.py` beside `queue_refusal`:

```python
def landing_refusal(land: str, method: str, *, source: str, allowed: Collection[str]) -> str | None:
    """R2: under `land: push` only a merge commit lands a GitHub PR by push."""
```

It returns None unless `land == "push"` and `method != "merge"`. Its fix names
`merge_method: merge` when `"merge" in allowed`, else "allow merge commits in the repo's
settings", and `queue.land: merge` in both cases.

**Where the driver checks it.** Not in `_queue_refusal` (`triage_batch_cmd.py:7053`): its
callers include `_queue_resume` (`:7082`, which runs before the pass reads anything and must
still record a landing already pushed) and `_wave_queue_reads` (`:7116`), and building a merge
context there would add a fetch and a forge read to paths that make none today. The check goes
in `_queue_gate` (`:7313`), after `_queue_refusal` and before the needs: a new
`_landing_hold(facts, repo) -> str | None` calls `merge_ctx`, catching what it raises
(`classify`'d `ConfigError` → its text; `ForgeReadError` → "the merge methods could not be read:
<error>; read again next pass"; `DefaultBranchUnknown` → its existing hold text), and otherwise
returns `landing_refusal(block.land, ctx.method, source=…, allowed=self._allowed[repo])`. A
non-None result becomes `held_plan(qplan, reason)`, so the pass's `queue` line, the board and
Needs you now show it with no new plumbing. `merge_ctx` caches the context per repo per process,
so the forge read happens once, where the `--yes` path already reads it; under a dry run it is
one new read per repo per process. The source is stored beside the context
(`self._method_source[repo]`, refreshed where `ctx.method` is). `batch merge` runs the same
driver (`_Driver.queue_only`, `:3271`), so R2 covers `--method`.

**`land_push`'s own guard (R3).** Before anything else it returns `LandResult("held", …)` with
no push when `method != "merge"`, or when any landing's commit has parents other than
`(<its parent>, x.head)`, read through the checkout's parents seam (`gitseam.py:1092`,
`parents(sha)`; the `Checkout` protocol of `queue_exec.py` gains it if missing). The head-ref
refspec becomes `(x.head, ref)` alone. Building combinations in `squash` and `rebase` stays:
`land: merge` (`land_merge`, `queue_exec.py:656`) still compares the forge's result tree with them.

**Fixtures (R9).** The shared fakes and fixtures that land squash or rebase by push move to
`merge`: `tests/unit/fakes.py:499` (default squash), the drive tests' World
(`tests/unit/test_triage_batch_drive_cmd.py:212`, squash only, with the autouse `_queue_stub`
giving `land: push`), `tests/integration/test_queue_land.py`, `test_queue_errors.py`,
`test_queue_resume.py` and `test_queue_drive_cmd.py`. Each keeps its R10 proof. The parametrised
`test_one_atomic_push_moves_main_to_the_tip_and_each_head_to_its_commit` (squash, rebase) is
rewritten: squash and rebase by push are held and push nothing; the head-moves-to-its-commit
assertion goes away with R3.

**`fr cloud doctor` (R5).** `cloud.py` reads the `queue:` block from the same
`.fr/triage.yaml` it reads `merge_method` from (`cloud.py:266`); when the block exists, it fails
the `merge_method` check with `landing_refusal`'s text.

### The rebase warning (R4)

In `_landing_hold`, when the landing is allowed, `land == "merge"` and the method is `rebase`,
the driver says the R4 warning through `_report_once` (`:5451`, key
`rebase-first-parent\0<repo>`), so it prints once per process.

### This repo (R6)

`.fr/triage.yaml`: `merge_method: merge`, the comment replaced: under `queue.land: push` only
a merge commit makes GitHub mark the PR merged (#1705), a configured method wins over the
viewer default (#1702), and this repo's release reads first-parent `Merge pull request #N`
subjects, which a rebase breaks (#1603).

### release.py (R7)

In `waiting_prs`, before raising on `missing`: for each missing number, `cmds.gh_read(["pr",
"view", str(n), "--json", MERGED_PR_FIELDS + ",state"])`. A `CLOSED` PR with no `mergedAt` is
added to `prs` with `mergedAt` replaced by the committer date (`%cI`) of the first-parent
commit that named it. For that, `logged_prs` gains a sibling `logged_pr_dates(repo, tag) ->
dict[int, str]` that keeps the first (newest) commit's date per number, and `logged_prs`
returns its keys. Anything else (a failed read, `OPEN`, `MERGED` that the list missed for
index lag) keeps today's `GateStateUnknownError` naming the PR. The `state` key is dropped
before the facts are written; `fr release status --from-json` (`commands/release_cmd.py:53`)
reads the same shape it reads today.

### Docs and amendments (R8, R9)

The fr-triage skill sentence "The merge method is the forge's default, else `merge_method` …"
becomes R1's order plus R2's rule; `fr-wave-driver.md:305`, `cloud-setup.md:30` and
`merge-protection.md:215` say the same, and AGENTS.md's release-gating sentence ("a PR the read
misses … makes the gate state unknown") gains R7's exception. Pages covering the changed paths
(`docs/explainers/fr-triage.md`, `fr-exit-gates.md`, `index.md`, `docs/exit-gates-release-walk.md`)
get their text checked and their `reviewed:` stamps moved; `fr docs check` names the full set.
The skill's OpenCode and Hermes mirrors are regenerated. The `wave-queue-land-methods` row is
amended with `fr acceptance amend --op reword` and its levels re-pointed with
`add-level`/`drop-level` for every rewritten test; any other merged row citing a renamed test
(`wave-queue-*` rows citing `test_queue_land.py`) gets the same level amendment.

## Design shape

```
packages/fr/src/fr/
  triage/batch_merge.py     ~ choose_method: explicit > configured > default > single
                            + choose_method_source: (method, where it came from)
  triage/queue_exec.py      + landing_refusal(land, method, source, allowed)   R2
                            ~ land_push: held unless merge AND each commit's
                              2nd parent is the PR head; no head-ref rewrite  R3
  commands/triage_batch_cmd.py
                            + _landing_hold (called from _queue_gate only;
                              catches ConfigError/ForgeReadError) + rebase warning  R2 R4
                            (_queue_refusal and the resume path unchanged)
  cloud.py                  ~ merge_method check reads queue.land          R5
scripts/release.py          ~ waiting_prs: closed-unmerged landing counts   R7
                            + logged_pr_dates
.fr/triage.yaml             ~ merge_method: merge                           R6
plugins/super-fr/skills/fr-triage/SKILL.md, docs/explainers/fr-wave-driver.md,
docs/cloud-setup.md, docs/merge-protection.md, AGENTS.md
                            ~ method order, the push rule, R7's reading     R8
tests/unit/fakes.py, tests/unit/test_triage_batch_drive_cmd.py,
tests/integration/test_queue_{land,errors,resume,drive_cmd}.py
                            ~ squash/rebase-by-push fixtures → merge        R9
docs/acceptance/features/2026-11-26-landing-method.yaml
                            ~ amendments of wave-queue-land-methods (+ levels)   R9
```

```
method = explicit ?? configured ?? forge default ?? only allowed
land: push  + method ∈ {squash, rebase}  →  queue-held (names fix)    ← #1705, #1603
land_push: commit not a merge of (parent, PR head) → held, no push   ← stale squash build
land: push  + merge                       →  lands; GitHub reads MERGED
land: merge + rebase                      →  lands + one warning      ← #1603
release: first-parent (#N) ∉ merged list → pr view N
    CLOSED, mergedAt null → counted, mergedAt = commit date            ← #1704
    else                  → unknown (RC only), as today
```

## Verification

strategy: none
- landing-method-order: none — unit tests drive `choose_method` and `choose_method_source` over every source combination in this PR's CI
- landing-method-push-merge-only: none — unit and integration tests drive `landing_refusal`, `land_push`'s guard over real bare git, the driver's held plan and `fr cloud doctor`'s check in this PR's CI
- landing-method-rebase-warning: none — a unit test drives the driver's once-per-process warning in this PR's CI
- release-closed-unmerged-landing: none — unit tests drive `waiting_prs` with a fake `gh_read` and a git fixture in this PR's CI
gate: developer

## Test Plan

- pre-merge — CI: `choose_method` returns the configured method over a forge default, the default when nothing is configured, the single allowed method last, and refuses a disallowed explicit or configured method (row `landing-method-order`).
- pre-merge — CI: under `land: push` a `squash` or `rebase` method from each source holds the queue with a reason naming the method, its source and the fix (`merge_method: merge` when merge is allowed, allowing merge commits when it is not); `merge` does not; an unchoosable method or a failed merge-methods read holds the queue for the pass without raising, also under a dry run; the resume pass still records a landing already pushed; `land_push` with a non-merge method, or with a merge-method call whose combination commit is not a merge of its parent and the PR's head, pushes nothing; `fr cloud doctor` fails the check when a `queue:` block lands by push and passes when there is no `queue:` block (row `landing-method-push-merge-only`).
- pre-merge — CI: under `land: merge` a `rebase` method prints the warning once per repo per process (row `landing-method-rebase-warning`).
- pre-merge — CI: `waiting_prs` counts a first-parent PR the forge reports `CLOSED` and unmerged with the commit's date and its labels, and stays unknown for an `OPEN` PR or a failed read (row `release-closed-unmerged-landing`).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-26-landing-method | `derio-net/super-fr` | `2026-11-26-landing-method` | — |
