# fr triage batches: create, dispatch and merge groups of issues

- **Date:** 2026-09-25
- **Status:** designed
- **Origin:** operator request, triage session 2026-09-23 (batches of gh#574/#576/#569 and gh#577/#575/#471/#438); follow-up gh#611
- **Goal:** a batch of judged issues becomes first-class triage state that fr can
  dispatch to any run-capable runner as one fr-goal run, show on the forge, and
  merge in a computed order, with version bumps reserved up front.

## 1. Problem

On 2026-09-23 a triage of super-fr grouped seven issues into two batches by
shared subsystem, launched each batch as a `/fr-goal` run in a herdr tab on a
chosen model, and flagged that both batches would touch
`isolation/local.py` and `isolation_cmd.py`. Every step of that was done by hand:

1. **The grouping lived in free text.** `judgements.yaml` has no batch field,
   so the batch was a sentence in three `note`s plus a `patterns` entry. Nothing
   checks that a member is judged, open, or in only one batch.
2. **The launch brief was hand-typed.** The rules the run depended on (one PR,
   `Closes #n` for every member, the model for every subagent) existed only in
   the prompt the agent wrote. Forget `Closes`, and triage never sees the batch
   merge, because stages come from `closingIssuesReferences` alone.
3. **Nothing on the forge said the issues were taken.** Another machine, or the
   next triage, saw them as `backlog`.
4. **Merge order was a remark in chat.** Nothing predicted which batch PRs
   would conflict, and every batch PR bumps the version, so the second PR to
   merge always conflicts in ten version-bearing files.

## 2. Decisions (operator, 2026-09-23 → 25)

| # | Decision |
|---|---|
| d1 | `dispatch`, `merge` and `cancel` act only with `--yes`; without it they print the plan. This reverses two fr-triage non-goals (writing to the forge; knowing about fr runs), explicitly, in §7. |
| d2 | Dispatch goes through the `fr_dispatch` runner protocol. A new `fr-herdr` package is the first runner that accepts run-unit work; batching supports **any** runner that does. |
| d3 | On a behind or conflicting PR: update from main, wait for CI, merge; stop on a real conflict and name it. Never resolve a conflict, **except** one confined to the repo's declared version files (d4). |
| d4 | Version bumps are reserved per batch at dispatch time, in merge order, so each run bumps to its final number early and CI builds it early. |
| d5 | `batch merge --yes` blocks in the foreground while CI runs; Ctrl-C and re-run resumes. |
| d6 | Forge writes go through `GhClient` where it already covers the operation; merge-only operations are GitHub-only with a declared refusal elsewhere. A forge parity matrix is its own spec (gh#611). |

## 3. Design

### 3.A Batch state: `judgements.yaml` schema 2

`fr/triage/model.py`'s `Judgements` gains `batches: list[Batch]` and moves to
`schema: 2`. Schema 1 files still load (as zero batches); the first engine
write of a batch upgrades the file to 2. Triage state is not a registered
artifact kind (`fr.artifacts.registry`), so this needs no migration-framework
entry. Every model stays `_Strict` (`extra="forbid", frozen=True`).

```yaml
schema: 2
batches:
  - id: lifecycle                    # slug: [a-z][a-z0-9-]{0,25} (herdr agent names cap at 32 chars incl. `batch-`)
    title: "Separate container lifecycle from worktree lifecycle"
    ids: ["super-fr#577", "super-fr#575", "super-fr#471", "super-fr#438"]
    rationale: "Rebuild, stop and re-up all route through `down` today."
    order: 1                         # optional; a hard constraint on merge order
    bump: minor                      # patch | minor | major
    launch: {runner: herdr, harness: claude, model: claude-opus-5-5}
    dispatch:                        # written by the engine only
      - at: 2026-09-25T10:12:00Z
        runner: herdr
        handle: "w2:p1K"             # opaque to triage; never posted to the forge
        branch: feat/batch-lifecycle
        reserved_version: 4.21.0
```

Validated at load (structural, so a bad file fails when it is written, not at
dispatch):

- every id in `ids` is a key in `issues` (judged);
- no key is in two batches whose derived stage is not `merged`/`cancelled`;
- `ids` is non-empty; batch `id`s are unique case-insensitively;
- `launch.runner` names a registered `fr.runners` entry point (checked at
  dispatch, not at load, because the dispatch package may not be installed
  where the board renders).

**Derived batch stage** (never stored), from member stages and `dispatch`:
`proposed` (no dispatch record) → `dispatched` (record, no linked PR) →
`pr-open` (the batch PR, found by `head_ref == branch`, is open) → `merged`
(PR merged, every member closed) or `partial` (PR merged, a member still open:
a `Closes` line was missing) → `cancelled` (a `cancel` record is present, §3.E).

### 3.B `batch create`, `edit`, `cancel`, `suggest`

```
fr triage batch create <id> --title T --issue KEY... --rationale R
    [--order N] [--bump patch|minor|major]
    [--runner R --harness H --model M]
fr triage batch edit <id> [same options; --add-issue/--remove-issue]
fr triage batch cancel <id> [--yes]
fr triage batch suggest
```

`create` and `edit` write only the `batches:` section of the agent-owned file,
through the same model the loader uses, so every §3.A rule is enforced on
write. Launch settings resolve from the batch's `launch`, then
`.fr/triage.yaml` `defaults.launch`, then refuse. fr never picks a model.

`suggest` prints candidate groupings and writes nothing. It makes no model
call. Signals, in order: open judged issues whose `detail` cites the same file
path; the same `theme`; the same `patterns` entry. The agent accepts one with
`create` or ignores it.

### 3.C `batch dispatch`

```
fr triage batch dispatch <id> [--to RUNNER] [--yes]
```

1. **Resolve** the runner (`--to`, else `launch.runner`) via
   `fr_dispatch.registry` (`fr.runners`). Missing package: exit 2 naming it.
2. **Reserve a version** (§3.D) if the repo declares version files.
3. **Render the brief** deterministically from the judgements. The brief is
   engine-owned text; the same judgements always produce the same brief:
   - `/fr-goal <title>`
   - for each member: key, title, `detail`, `note`; then `rationale`
   - branch `feat/batch-<id>`
   - "Open a draft PR as soon as the spec is committed. Its body contains
     `Closes <owner>/<repo>#<n>` for every member."
   - "Bump the version to `<reserved>`" (when reserved)
   - "Use `<model>` for every subagent and every model tier"
4. **Build the WorkItem.** `unit: run`, id `<repo>/run/batch-<id>`
   (`fr_dispatch.work_item.run_item_id`), `payload = {brief, harness, model,
   branch, reserved_version}`, `tracking = {issues: [...]}`.
5. **Without `--yes`:** print the brief, runner, harness, model, branch and
   reserved version. Stop.
6. **With `--yes`:** `runner.preflight([item])` → refuse if
   `item.id in runner.existing_dispatches([item])` → refuse if
   `not runner.can_dispatch(item)` with "runner `<name>` does not take
   run-unit work" → `runner.dispatch(item)` → append the `dispatch` record →
   forge writes (§3.E).

**Run-unit payload contract.** The payload shape above is pinned in
`fr_dispatch` (documented beside `WorkItem`) and covered by a contract test that
any runner whose `can_dispatch` accepts `unit == "run"` must pass. `vk` and
`cncd` accept `unit == "phase"` only (`fr_vk/runner.py`, `fr_cncd/runner.py`
`can_dispatch`) and are refused cleanly; teaching VK to take run-unit work is
out of scope (§6).

A runner may impose its own limits on the payload; `fr-herdr`'s is the agent
name, which is why §3.A caps batch ids at 26 characters.

**`fr-herdr` runner** (new package `packages/fr-herdr`, entry point
`herdr = "fr_herdr.runner:HerdrRunner"` in group `fr.runners`):

- `capabilities = {"git", "tests", "scm", "devcontainer"}` (the closed set in
  `fr/capabilities.py`; unit support is `can_dispatch`'s job, not a capability).
- `preflight`: `herdr` on PATH and `HERDR_ENV=1`, else refuse. Herdr's own rule
  is never to drive a session from outside it.
- `can_dispatch(item)`: `item.unit == "run"` and `item.payload["harness"]` is
  in the runner's harness table.
- `dispatch(item)`: `herdr tab create --workspace $HERDR_WORKSPACE_ID --cwd
  <repo> --label <id> --no-focus` → `herdr agent start batch-<id> --kind
  <harness> --pane <root pane> -- <model flag>` → `herdr agent prompt
  batch-<id> <brief>`. The harness table maps harness to the agent kind and
  the model flag (`claude` → `--model <m>`; others added as verified).
  Returns the pane id as the handle.
- `existing_dispatches(items)`: the ids whose agent name `batch-<id>` is live
  in `herdr agent list`.
- `fr-herdr` never imports `fr.triage`; `fr` never imports `fr_herdr`.

fr makes no model call and does not wait on the run: dispatch returns once the
prompt is submitted (`no-claude-p-batch` holds: the runner starts an
interactive session).

### 3.D Version reservations

A repo opts in through `.fr/triage.yaml`:

```yaml
version:
  files: [pyproject.toml, packages/fr/pyproject.toml, ..., uv.lock]
  current: "uv version --short"
  set: "uv run --no-project python scripts/bump-version.py {version}"
  relock: "uv lock"          # optional; run after `set`
```

fr parses no manifest itself. For super-fr, `files` is exactly
`bump-version.py`'s surface list (`bump-version.py` takes one argument, a
version or `--check`, and already re-syncs `uv.lock`, so its `relock` is a
belt-and-braces no-op there). A repo with no `version` block gets no
reservations and no version resolver (d3's exception simply never applies).

- **Reserve (dispatch):** the next version after the highest of (main's current
  version, every live reservation), bumped by the batch's `bump`, in planned
  merge order. Stored in the `dispatch` record and put in the brief.
- **Reconcile (merge):** before merging, fr re-derives the reservation sequence
  from the plan order (§3.F). A PR whose version is not its slot's number is
  re-set in its branch (the §3.F update path). fr never merges a PR whose
  version is lower than or equal to main's.

Why reserve rather than bump at merge time: a batch's CI then builds and tests
the number it will ship, early, and the only conflict left after an earlier
batch merges is in files whose correct resolution is already known.

### 3.E Forge visibility

After `runner.dispatch` succeeds, the **engine** (not the runner, so the signal
is the same for every runner) writes to each member issue through `GhClient`
(`edit_issue_labels`, `comment_issue`, present on github, gitlab and gitea):

1. label **`fr:in-progress`**, the existing `fr/labels.py` `LabelDef`
   (created with `ensure_labels`);
2. one comment: "Dispatched as batch `<id>` (<title>), with <other members>.
   Branch `feat/batch-<id>`." No pane id, host, or other local detail.

The brief's early draft PR does the rest: GitHub links it in each issue's
Development panel, and triage's existing stage derivation moves the member to
`pr-draft`.

`fr/triage/stage.py` gains one stage, `in-progress`, derived from the
`fr:in-progress` label in `facts.json`, which `collect` already fetches.
`STAGES` becomes closed > merged > pr-ready > pr-draft > in-progress > blocked >
backlog: a linked PR outranks the label, and a held issue outranks a `blocked`
label (someone is working on it). Stages still come from forge facts alone, so another machine's
board sees a dispatch.

`batch cancel <id> --yes` removes the label, posts "batch `<id>` withdrawn",
and appends a `cancel` record. `check` gains a sixth set, **stale dispatch**:
labelled `fr:in-progress` for more than 3 days (`.fr/triage.yaml`
`stale_dispatch_days`) with no linked PR. Reported, never acted on.

**To verify in the plan:** the bridge's apply cycle rewrites `fr:*` lifecycle
labels only on the Issues it renders from plans, not on ordinary backlog
issues. If that is false, it would strip this label, and §3.E must use a
triage-owned label instead.

### 3.F `batch merge`

```
fr triage batch merge [<id>...] [--yes]
```

No ids: every batch at stage `pr-open`.

**Facts.** `facts.json` moves to schema 3: `PullRequest` keeps `files` (already
fetched by `gh pr list` for anchoring, then discarded) and the head commit
oid. Collect adds no call.

**Order.** Explicit `order` values are hard constraints. The rest are ordered
so that batches sharing files are not adjacent where avoidable, then by fewest
overlaps, then by lowest member tier. The printed plan lists, per step, the
PR, its reserved version, and the files it shares with later steps: that is the
conflict prediction, shown before anything merges.

**Per step, with `--yes`:**

1. Re-read the PR from the forge. Refuse the step, and stop, if it is a draft,
   has failing required checks, or its head moved since the plan was printed.
2. Up to date and green → `gh pr merge <n> --<repo default method>
   --match-head-commit <sha>`. Never `--admin`. A protection refusal (e.g. a
   required review) stops the queue and is reported verbatim.
3. Behind main → create a scratch worktree of the PR branch under
   `~/.cache/fr/triage/<scope>/merge/<branch>/` and `git merge
   origin/<default>`:
   - no conflict → push;
   - every conflicted path is in `version.files` → run `set <reserved>`, then
     `relock`, commit "chore: take reserved version <v> after batch <prev>",
     push;
   - any other conflicted path → abort the merge, stop, print the PR and the
     paths, and keep the scratch worktree for inspection.
   After a push, wait for required checks (foreground, d5), then go to step 1.
4. Remove the scratch worktree after a successful merge.

**Resume.** Queue progress is never stored: every step re-derives from the
forge, so re-running after a stop starts at the first unmerged batch.

The scratch worktree sits outside every repo on purpose: merge edits branches
that other runs own, which fr-isolation forbids in the base clone, and a
batch's own workspace may have a live session in it.

**Forges.** Merge needs operations `GhClient` lacks (PR files, required-check
state, merge with head match, check wait). They are added for GitHub only. On
gitlab/gitea `batch merge` exits 2 with "batch merge is not supported on
<backend> (gh#611)". Never a silent no-op.

### 3.G Board

`render` adds a **Batches** section above the tiers: one card per batch with
members, derived stage, reserved version, PR, and, for `pr-open` batches, the
planned merge order with shared files. Members still render in their tiers,
with a batch chip.

### 3.H fr-triage skill

- The loop gains step 5, **batch**: after judging, propose batches (use
  `batch suggest` as input, never as the answer) and create the ones the
  operator accepts.
- "Forge actions are unrun commands" gains: `batch dispatch|merge|cancel` act
  only with `--yes`, and the agent passes `--yes` only when the operator asked
  for that action in this session.
- The `judgements.yaml` section documents `batches:` and schema 2.
- Regenerate both mirrors (`sync-opencode.py`, `sync-hermes.py`). The engine
  ships in the wheel, so every harness gets the same verbs.

## 4. Error handling

| Situation | Behaviour |
|---|---|
| Runner package not installed | exit 2, names the package |
| Runner refuses the unit | exit 2, "runner `<name>` does not take run-unit work" |
| Batch already dispatched and live | exit 2, names the handle; nothing written |
| `runner.dispatch` fails | no record, no forge write; exit 1 with the runner's error |
| Forge write fails after a successful dispatch | the dispatch record is kept; exit 1 listing the issues not labelled; re-running `dispatch` retries only the forge writes |
| Reservation without a `version` block | skipped silently (not an error); brief omits the bump line |
| Merge conflict outside version files | stop, name PR and paths, keep scratch worktree, exit 1 |
| Required checks fail after an update push | stop, name the check, exit 1 |
| Non-GitHub backend on `merge` | exit 2, declared refusal (gh#611) |

## 5. Migration gate

`triage` stays in `fr.artifacts.trigger.READ_ONLY_COMMANDS`. The tuple's
criterion is "never mutates a registered artifact". The batch verbs write the
forge, `~/.cache/fr/triage/`, and scratch worktrees under that directory, never
an fr artifact in the invoking checkout. A `git merge` in a scratch worktree
moves whatever artifacts main carries, which is ordinary git and not an fr
rewrite. The pinned exemption test does not change.

## 6. Non-goals

- Run-unit support in `vk` or `cncd` (a follow-up issue is filed at delivery).
- Forges other than GitHub for `merge`; a forge parity matrix (gh#611).
- GitHub auto-merge or a dispatched merge queue (d5).
- Resolving any conflict outside the declared version files.
- Cross-repo batches: a batch's members are in one repo. An `--org` triage may
  hold batches in several repos.
- Watching a run's progress: after dispatch, fr learns about the run only
  through the forge (draft PR, merge).

## 7. Reversed fr-triage non-goals

The fr-triage spec (`implemented/specs/2026-09-21-fr-triage-design.md`) listed:

- **"Writing to the forge."** Reversed for `batch dispatch|merge|cancel`
  only, behind `--yes` (d1). `collect`, `check`, `render` and `suggest`
  still never write.
- **"Knowing about fr runs."** Kept in its original sense: stages still come
  from forge facts alone. A dispatch becomes a forge fact (§3.E label and
  draft PR), which is why the board can show it without reading any run cursor.

## 8. Test Plan

1. **Schema 2 model** (unit): a batch naming an unjudged key, a key in two open
   batches, an empty `ids`, and case-colliding batch ids are each refused at
   load; schema 1 loads as zero batches; a write upgrades it to 2.
2. **Derived batch stage** (unit): each of proposed, dispatched, pr-open,
   merged, partial, cancelled from constructed facts.
3. **Brief rendering** (unit): identical judgements render byte-identical
   briefs; the brief contains `Closes` for every member, the branch, the
   reserved version when present and not when absent, and the model line.
4. **Run-unit runner contract** (unit): a reusable contract test; `fr-herdr`
   passes it; `vk` and `cncd` are refused by `can_dispatch` with the documented
   message.
5. **fr-herdr** (unit, `herdr` faked): preflight refuses without `HERDR_ENV`;
   dispatch issues tab create, agent start with the model flag, and prompt, in
   order; a live agent name is reported by `existing_dispatches`.
6. **Dispatch forge writes** (unit, `GhClient` faked): label and comment on
   every member only after `runner.dispatch` succeeds; a failed dispatch writes
   nothing; the comment carries no handle.
7. **`in-progress` stage and stale dispatch** (unit): derived from the label;
   outranked by a linked PR; stale after the configured days with no PR.
8. **Version reservation** (unit): sequence follows merge order and bump levels;
   reconcile re-assigns after a reorder; never lower than main.
9. **Merge order** (unit): hard `order` respected; overlapping batches not
   adjacent when avoidable; tie-breaks deterministic.
10. **Merge execution** (integration, local bare origin): two branches both
    bumping the version merge in sequence with the second auto-resolved; a
    third conflicting in a non-version file stops the queue with the path named
    and the scratch worktree kept; a re-run resumes at the first unmerged PR;
    a moved head is refused.
11. **Migration exemption** (unit): the pinned exemption test still passes.
12. **Live walk** (manual, post-implementation): create, dispatch through
    `fr-herdr`, and merge two real super-fr batches with overlapping files.
