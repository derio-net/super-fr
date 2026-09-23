# fr status and fr archive: check the default branch before saying "merged"

- **Date:** 2026-09-23
- **Status:** designed
- **Origin:** gh#526 (canonical for #439), gh#544
- **Goal:** `fr status` calls a plan merged, and `fr archive` archives it, only
  when the plan's agentic phases are complete on `origin/<default>`. A plan that
  is only complete locally is reported as waiting for merge. Nothing suggests
  archiving it, and `fr archive` refuses it.

## 1. Problem

`fr status` with no argument sweeps `docs/superpowers/plans/` and prints:

```
archivable — merged but not archived (1):
  2026-09-20-agentic-dispatch-verb-lint

run `fr archive --all` to move 1 plan(s) to implemented/.
```

The list comes from `fr.archive.completed_unarchived_plans`. That function is
gh-free by design (#334): it counts a plan when every phase is locally complete
(`render.plan_locally_complete`). It never checks merge state. Its docstring
puts "merged-but-unarchived" in quotes because it knows the label is a guess.
`status_cmd._sweep_text` (`status_cmd.py:150`) prints that guess as fact and
then suggests acting on it.

**Every fr-goal run reaches this state before its PR exists.** fr-goal finishes
every phase and only then delivers. So the suggestion fires exactly when
following it would be wrong. #439 recorded a live case on 2026-08-15:
`2026-07-26-fr-goal-isolation-deadlocks` was reported merged while PR #422 was
still open.

#439 argued this was only a wording bug, because `archive_gate` would refuse
the real move. For fr-goal plans it does not refuse (#544). `archive_gate`'s
undispatched arm (`render.py:276`) passes any phase that is locally complete
and has no tracking issue. fr-goal plans never get a tracking issue. So
`fr archive --all` archives the unmerged plan the sweep just called merged.

Archiving is hard to undo. `docs/superpowers/implemented/` is frozen: no
locator reaches it, no migration rewrites it, and `fr validate artifacts` does
not check it (`.claude/rules/artifact-versioning.md`).

The correct version of this signal already exists, in a test.
`tests/unit/test_tripwire_unarchived_plans.py` computes *complete on
`origin/main`* ∩ *still in the working tree*. It materialises `origin/main`'s
`plans/` subtree with `git archive` and runs the same predicate on it. That is
why the tripwire did not fire on the branch that led to #526.

## 2. Goal and non-goals

**Goal.**

1. "Merged" has one definition, built from one materialisation of
   `origin/<default>` and shared by `fr status`, `fr archive`, and the CI
   tripwire: **every agentic phase of the plan is locally complete as the plan
   exists on the ref.** Manual phases do not count toward it (see 3.A). They
   record operator work done after merge, not merged code.
2. The sweep shows four buckets: merged and ready to archive, merged with
   manual phases still open, complete locally but waiting for merge, and in
   progress. It suggests `fr archive <dir>` only for the first bucket, one
   command per plan, and never `--all` (decision `d2-suggestion`).
3. `fr archive` refuses a plan whose undispatched agentic phases have not
   landed on `origin/<default>` (#544, decision `d1-scope`). `--force` on a
   single plan still overrides.

**Non-goals.**

- The dispatched arm of `archive_gate` stays as it is. A dispatched phase
  already needs gh to show a merged PR (`_phase_complete`).
- No gh or PR lookups in the sweep. The sweep stays gh-free, so its limit for
  dispatched plans is stated rather than fixed (3.B).
- `completed_unarchived_plans` keeps its meaning (locally complete, every
  phase). Its docstring claim "never flags a plan the mover would refuse" is
  already false for dispatched plans. It gets corrected, not relied on.

## 3. Design

### A. One merge-evidence helper in `fr.archive`

`fr/archive.py` gains the single definition of "merged":

```python
@dataclass(frozen=True)
class DefaultRef:
    ref: str            # e.g. "origin/main": a remote-tracking ref, never a local branch
    sha: str            # short SHA read, so a stale ref is visible in output

@dataclass(frozen=True)
class MergeEvidence:
    ref: DefaultRef | None           # None = no remote-tracking default ref resolvable
    ref_error: str | None            # why ref is None (no remote; ambiguous remotes; …)
    fetched: bool                    # a fetch was attempted and succeeded
    fetch_error: str | None          # attempted and failed (offline, auth, timeout): evidence is the stale local ref
    landed_phases: Mapping[str, frozenset[int]]  # plan name → phase numbers locally complete on ref
    agentic_landed: frozenset[str]   # plans whose every agentic phase is in landed_phases
    complete_on_ref: frozenset[str]  # plans with EVERY phase complete on ref (the tripwire's set)
    unparsed_on_ref: tuple[str, ...] # ref-side plan dirs the current fr could not parse

def merge_evidence(repo_root: Path, *, fetch: bool) -> MergeEvidence: ...
```

**Why manual phases are excluded.** fr-goal ships the trailing `[manual]`
phase unticked. The operator ticks it after merge while driving the Test Plan,
then archives (`fr-goal` post-merge close-out). If merge evidence required
every phase to be complete on the ref, a plan would never look merged on
`main`, and `fr archive` would refuse every fr-goal plan forever. The merged
code is the agentic phases, so they are the evidence. The manual phases must
still be complete in the **working tree** before archiving (the existing
`plan_locally_complete` arm), so the operator's attestation still gates the
move. It just does not have to reach `main` first. A plan with no agentic
phases counts as landed as soon as its directory exists on the ref.

**How the default ref is found.** Only remote-tracking refs count, because a
local `main` does not show that anything merged. The remote-tracking half of
`fr.artifacts.commit._default_branch` (steps 1–2, `commit.py:258-270`) moves
into one public helper, `fr.git.remote_default_ref(root) -> str | GitRefusal |
None`, which `_default_branch` then calls. The steps:

1. `refs/remotes/<remote>/HEAD`, if its target exists.
2. `refs/remotes/<remote>/{main,master,trunk,develop}`, the first that exists.

The remote name comes from `_remote_name`, made public as `remote_name` and
moved alongside it. That makes three copies of the lookup one (the third, in
`isolation/local.py`, stays: it uses a different seam on purpose). A
`GitRefusal` (for example, two remotes and no `checkout.defaultRemote`) or no
remote gives `ref=None`, with the reason in `ref_error`. Nothing counts as
merged; the answer is "unknown", never "merged".

**Fetch (decision `d3-evidence`).** With `fetch=True`, the helper first calls a
module-level `_fetch(repo_root, remote)`. That function is a monkeypatchable
seam (the `_make_gh_client` pattern), so tests never hit a network. It runs
`git fetch --quiet --no-tags <remote>` with `GIT_TERMINAL_PROMPT=0` and a
30-second timeout. A failure or timeout is not fatal. It sets `fetch_error`,
the evidence falls back to the local remote-tracking ref, and every surface
prints that fact. A fetch changes only remote-tracking refs, so `status` stays
in `READ_ONLY_COMMANDS`.

**Materialising the ref's plans.** The helper runs
`git archive <ref> docs/superpowers/plans` and extracts the result into a temp
dir. It then parses each plan there **per phase**. `completed_unarchived_plans`
only returns fully complete names, so it cannot give `landed_phases` for a
partly landed plan. Phases are matched by number. A plan the current fr cannot
parse on the ref (for example, an older schema on `main`) goes into
`unparsed_on_ref` and is reported, not silently treated as unmerged. If the ref
has no `plans/` tree, the sets are empty.

The tripwire imports this helper with `fetch=False` and uses `complete_on_ref`.
Its question is "merged, fully done, still not archived". It keeps an explicit
`pytest.skip` when `ref is None`, so a checkout without the ref still skips
instead of passing silently.

### B. `fr status` sweep: four buckets

`_sweep_lists` becomes a sweep over `merge_evidence(repo_root, fetch=True)`.
For each plan still in the working-tree `plans/`:

- **archivable**: in `agentic_landed` and locally complete (every phase,
  manual included) → `fr archive docs/superpowers/plans/<name>`
- **merged_manual_open**: in `agentic_landed` but not locally complete. Name
  the open manual phase numbers; no archive command.
- **complete_unmerged**: locally complete but not in `agentic_landed`. No
  command.
- **in_progress**: everything else.

Text output:

```
merged but not archived: agentic phases on origin/main @ f6a2603 (1):
  2026-09-20-foo
    fr archive docs/superpowers/plans/2026-09-20-foo

merged, manual phases still open (1):
  2026-09-21-baz  (phase 5)

complete locally, not yet on origin/main (waiting for merge) (1):
  2026-09-23-bar

in progress (2):
  ...
```

- A fetch failure adds `(fetch failed: <reason>; using the local origin/main
  ref)`.
- `ref=None` replaces the merged headings with `merge state unknown
  (<ref_error>; try git fetch / git remote set-head origin -a)`, and every
  locally complete plan is listed there.
- `unparsed_on_ref` entries are listed with a one-line note.
- A dispatched plan is labelled by the same offline rule. The gh gate in
  `fr archive` may still refuse it; the sweep's help text says so.

JSON (decision `d4-json`):
`{"archivable": [...], "merged_manual_open": [...], "complete_unmerged": [...],
"in_progress": [...], "default_ref": {"ref", "sha", "fetched", "fetch_error"} |
null}`. `archivable` narrows: it can only get shorter, never longer.

### C. `archive_gate` requires landed evidence (#544)

`render.archive_gate(plan, observed, *, landed: frozenset[int] | None)`. The
new keyword is **required, with no default**, so no caller can skip the
question. `landed` is the set of phase numbers locally complete on
`origin/<default>`. `None` means the merge state is unknown.

- **Dispatched arm:** unchanged.
- **Undispatched agentic phase:** passes only if it is locally complete
  **and** its number is in `landed`. Otherwise the blocker reads `Phase N:
  complete locally, not on origin/main; merge the PR first`. With
  `landed=None` it reads `… merge state unknown (<reason>); add a remote or
  use --force`.
- **Manual phase:** unchanged. Locally complete is enough (see 3.A).

All three callers use `fetch=True` (decision `d3-evidence` covers `status`;
`archive` and `apply` already use the network):

- `fr archive`: one `merge_evidence` call per invocation (not per plan under
  `--all`), and `landed = evidence.landed_phases.get(name, frozenset())`.
  `--force` on a single plan overrides every blocker. `--force --all` stays
  refused.
- `fr status <plan>`: the "plan complete — run fr archive" nudge **and** the
  JSON `archive_ready` field, from the same `landed`.
- `fr apply`'s matching nudge.

### D. Prose

`plugins/super-fr/skills/fr-progress/SKILL.md` prescribes `fr archive --all`
in two places: the preflight block ("only now, for plans the sweep marked
archivable") and the "When a plan is finished" block. Both change to the
per-plan command the sweep prints and to the four buckets. Then regenerate both
mirror sets (`sync-opencode.py`, `sync-hermes.py`). The fr-goal close-out ticks
the manual phase and then runs `fr archive <plan-dir>`. It works unchanged
because manual phases are judged locally (3.A). A patch release does not
trigger explainer updates.

### E. Housekeeping

Patch bump (bug fix; the gate gets stricter in the direction #544 asks for).
Acceptance rows `status-sweep-merge-evidence` and
`archive-refuses-unmerged-plan` move to `ci` as their unit tests land. The live
walk is the trailing manual phase.

## 4. Risks

- **A slow or hanging fetch** would stall `fr status`. The 30-second timeout
  and `GIT_TERMINAL_PROMPT=0` bound it, and failure degrades instead of
  aborting.
- **A repo with no remote** (a scratch repo, some pods). `fr archive --all`
  archives nothing, and a single plan needs `--force`. The refusal text says
  this. That is the fail-closed direction #544 asks for.
- **Archive tests build repos with no remote.** About 20 tests in
  `test_archive_cmd.py` must now commit the plan and add a file-path remote,
  with `_fetch` monkeypatched. A shared test helper keeps this in one place.
- **Squash merges.** The evidence is the plan's *content* on the ref, not
  commit ancestry, so a squash merge counts as merged.
- **Phase renumbering.** Phases are matched by number. A phase renumbered on
  the branch after an earlier merge could false-pass. Renumbering landed phases
  is not a supported operation.
- **Sweep vs. gh gate for dispatched plans.** See 3.B. A dispatched plan
  ticked on `main` may be listed as archivable and then refused by the gh
  gate, which is the safe direction.

## 5. Test Plan

**In this PR:**

1. Unit `merge_evidence`:
   - `origin/HEAD` resolution; fallback to a remote well-known branch.
   - A local-only `main` never counts; no remote → `ref=None` with
     `ref_error`; two remotes and no default → `ref=None`.
   - `landed_phases` per phase for a partly landed plan (a phase added and
     ticked locally is not landed).
   - `agentic_landed` ignores an unticked trailing manual phase on the ref;
     `complete_on_ref` does not.
   - A plan that cannot be parsed on the ref goes to `unparsed_on_ref`.
   - Fetch success via a file remote; fetch failure and timeout (through the
     `_fetch` seam) degrade with `fetch_error` set.
2. `remote_default_ref` extraction: `_default_branch`'s existing tests stay
   green.
3. The tripwire uses the shared helper, skips explicitly when `ref is None`,
   and its fixture tests still pass.
4. Unit sweep:
   - Four buckets, with a per-plan `fr archive <dir>` line only under
     archivable, and `--all` never printed.
   - Open manual phases named; ref-unknown wording; fetch-failed note;
     unparsed note.
   - JSON keys and `default_ref`.
5. Unit gate:
   - Undispatched agentic phase complete locally but not landed → blocked;
     not on the ref → blocked; `landed=None` → blocked with unknown wording.
   - A landed phase passes; a manual phase is judged locally only; the
     dispatched arm is unchanged.
   - Calling without `landed` raises `TypeError`.
6. `fr archive`:
   - An unmerged plan is refused (single, exit 2) and skipped (`--all`).
   - A merged plan with its manual phase ticked only locally is archived (the
     close-out case).
   - `--force` on a single plan still overrides; one `merge_evidence` per
     invocation.
7. The `fr status <plan>` nudge, the `archive_ready` field, and `fr apply`'s
   nudge do not fire for an unmerged plan, and do fire once it has landed.
8. Skill validation, neutrality, and all three mirror tripwires green; version
   lockstep green; acceptance rows at `ci`; `fr acceptance check` and
   `fr validate artifacts` green.

**Pre-merge and post-merge, operator-driven (trailing `[manual]` phase):**

9. On this run's own branch, after implement, before merge: `fr status` does
   not call this plan merged and prints no archive command for it. It is under
   in progress while phase 4 is open, and under "complete locally, not yet on
   origin/main" once phase 4 is ticked. `fr archive <this plan>` refuses.
10. After the PR merges, on `main`: `fr status` lists this plan as merged,
    under "merged, manual phases still open" while phase 4 is unticked there.
    Once the close-out ticks it, the plan moves to "merged but not archived"
    with its `fr archive <dir>` line, and that command archives it.

## 6. Evidence hygiene

All fixtures are built in temp git repos with fictional plan names. Live
evidence comes from `derio-net/super-fr` (public, owned by `derio-net`). No
third-party hosts.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-23-archive-merge-evidence | `derio-net/super-fr` | `2026-09-23-archive-merge-evidence` | — |
