# fr triage batches: create, dispatch and merge groups of issues

- **Date:** 2026-09-25
- **Status:** designed
- **Origin:** operator request, triage session 2026-09-23 (batches of gh#574/#576/#569 and gh#577/#575/#471/#438); follow-up gh#611
- **Journal:** `docs/superpowers/journals/specs/2026-09-25-triage-batches.md`
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
   merge always conflicts in the version-bearing files.

## 2. Decisions (operator, 2026-09-23 → 25)

| # | Decision |
|---|---|
| d1 | `dispatch`, `merge` and `cancel` act only with `--yes`; without it they print the plan. This reverses one fr-triage non-goal (writing to the forge), explicitly, in §7. |
| d2 | Dispatch goes through the `fr_dispatch` runner protocol. A new `fr-herdr` package is the first runner that accepts run-unit work; batching supports **any** runner that meets the run-unit contract (§3.C). |
| d3 | On a behind or conflicting PR: update from main, wait for CI, merge; stop on a real conflict and name it. Never resolve a conflict, **except** one confined to the repo's declared version files (d4). |
| d4 | Version bumps are reserved per batch at dispatch time, so each run bumps to its final number early and CI builds it early. |
| d5 | `batch merge --yes` blocks in the foreground while CI runs; Ctrl-C and re-run resumes. |
| d6 | Every forge operation a batch verb performs goes through fr's forge adapter, `GhClient` via `fr.hostclient.client_for_backend` (§3.J). New operations are implemented for GitHub; the glab/tea adapters declare each one unsupported. `collect` stays on triage's own GitHub-only `Forge`; moving it, and filling the gaps, is gh#611. |
| d7 | A dispatch is made visible on the forge: the existing `fr:in-progress` label, one marker comment, and an early draft PR carrying the `Closes` lines. |

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
  - id: lifecycle                    # slug: [a-z][a-z0-9-]{0,39}
    title: "Separate container lifecycle from worktree lifecycle"
    ids: ["super-fr#577", "super-fr#575", "super-fr#471", "super-fr#438"]
    rationale: "Rebuild, stop and re-up all route through `down` today."
    order: 1                         # optional; a hard constraint on merge order
    bump: minor                      # patch | minor | major
    launch: {runner: herdr, harness: claude, model: claude-opus-5-5}
    events:                          # written by the engine only; append-only
      - kind: dispatch
        at: 2026-09-25T10:12:00Z
        runner: herdr
        handle: "w2:p1K"             # opaque to triage; never posted to the forge
        branch: feat/batch-lifecycle
        reserved_version: 4.21.0     # absent when the repo declares no version block
      - kind: cancel
        at: 2026-09-26T08:00:00Z
        reason: "split into two batches"
```

**Checked at load** (structural, from the file alone):

- every id in `ids` matches `KEY_RE` and is normalised with `normalize_key`
  (as `Pattern.ids` are), then must be a key in `issues` (judged); `ids` is
  non-empty;
- batch `id`s are unique, case-insensitively;
- `events` is time-ordered and every `kind` is `dispatch` or `cancel`.

**Checked by `create`, `edit` and `dispatch`** (they load `facts.json` too):
no issue key belongs to two **open** batches. A batch is open unless its last
event is `cancel`, or its derived stage is `merged`, `partial` or `abandoned`.
`partial` and `abandoned` are terminal: their still-open members are released
and may join a new batch.
`launch.runner` is checked at dispatch, not at load, because the runner package
need not be installed where the board renders.

**Derived batch stage** (never stored), from the last event and facts:

| Stage | Condition |
|---|---|
| `proposed` | no events |
| `cancelled` | last event is `cancel` |
| `dispatched` | last event is `dispatch`, no PR with `head_ref == branch` |
| `pr-open` | that PR is open |
| `merged` | that PR merged, every member closed |
| `partial` | that PR merged, a member still open (a `Closes` line was missing) |
| `abandoned` | that PR closed without merging |

A cancelled or abandoned batch may be dispatched again: the new `dispatch`
event becomes the last one. `abandoned` releases its members, like `partial`.

**Finding the batch PR.** The candidates are every PR with
`head_ref == branch` among the members' `Issue.prs`, `Facts.prs`, and the
branch lookup below; when several match, the highest PR number wins (a
re-dispatch opens a new PR). A merged PR whose body lost every `Closes` line
is linked to no member, so for each batch at `dispatched`, `collect` also runs
one `Forge.list_prs_by_head(repo, branch)` (all states) and stores the result in
`Facts.batch_prs`. `collect` already reads `judgements.yaml` (to view judged
keys that are no longer open), so it knows the branches.

### 3.B `batch create`, `edit`, `cancel`, `suggest`

```
fr triage batch create <id> --title T --issue KEY... --rationale R
    [--order N] [--bump patch|minor|major]
    [--runner R --harness H --model M]
fr triage batch edit <id> [same options; --add-issue/--remove-issue]
fr triage batch cancel <id> [--reason R] [--yes]
fr triage batch suggest
```

`create` and `edit` write only the `batches:` section of the agent-owned file,
through the same model the loader uses, then apply the open-batch rule of §3.A.
They store only the launch values given explicitly. Launch settings are
resolved **at dispatch**: the batch's `launch`, then `defaults.launch` from the
collected config (§3.I), then refuse. fr never picks a model. `edit` refuses
on a batch whose stage is past `proposed`, except to change `order`.

`suggest` prints candidate groupings and writes nothing. It makes no model
call. Signals, in order: open judged issues whose `detail` cites the same file
path; the same `theme`; the same `patterns` entry. The agent accepts one with
`create` or ignores it.

### 3.C `batch dispatch`

```
fr triage batch dispatch <id> [--to RUNNER] [--yes]
```

**Where the code lives.** `fr` may import `fr_dispatch` at exactly one soft
point today, `apply_cmd.py`, behind a `find_spec` guard
(`tests/unit/test_import_direction.py` `_SOFT_POINT`). The dispatch step lives
in a new `fr/commands/triage_batch_cmd.py`, added to that test as a second soft
point with the same guard and the same install message as `apply_cmd.py`.
Nothing else in `fr/triage/` imports `fr_dispatch`.

**Runner construction contract.** `fr_dispatch.registry` lists entry points
but never loads or builds one, and runner constructors differ (`VkRunner`
takes an MCP client). This spec adds `fr_dispatch.registry.load_runner(name)`:
load the entry point and call its `from_env()` classmethod, which builds the
runner from environment and config alone. A runner without `from_env` is
refused: "runner `<name>` cannot be constructed outside its own bridge".
`fr-herdr` implements `from_env`. `vk` and `cncd` do not today, and are
refused by that message.

**Steps:**

1. **Load** the runner (`--to`, else `launch.runner`). Package missing: exit 2
   naming it. No `from_env`: exit 2 as above.
2. **Reserve a version** (§3.D) if the repo declares a version block.
3. **Render the brief** deterministically from the judgements. The brief is
   engine-owned text; the same judgements always produce the same brief:
   - `/fr-goal <title>`
   - for each member: key, title, `detail`, `note`; then `rationale`
   - branch `feat/batch-<id>`
   - "Open a draft PR as soon as the spec is committed. Its body contains
     `<closing ref>` for every member." The reference comes from the adapter
     (`GhClient.closing_ref(repo, number)`, §3.J), `Closes <owner>/<repo>#<n>`
     on GitHub, so the brief never hardcodes one forge's syntax.
   - "Bump the version to `<reserved>`" (only when reserved)
   - "Use `<model>` for every subagent and every model tier"
   - "Do not name any member issue as a phase `tracking_issue` in the plan"
     (§3.E: the bridge would then own that issue's `fr:` labels)
4. **Build the WorkItem:** `unit="run"`, `repo=<owner>/<repo>`,
   `id=run_item_id(<repo>, "batch-<id>")`, `workflow="fr-goal"`,
   `parent=None`, `inputs=()`, `tracking=None`, and
   `payload={brief, harness, model, branch, reserved_version, issues}` where
   `issues` is the list of member keys. `tracking` stays `None` because `tick`
   treats a non-`None` tracking as one tracker Issue to stamp
   (`fr_dispatch/__init__.py`), which a multi-issue batch is not.
5. **Without `--yes`:** print the brief, runner, harness, model, branch and
   reserved version. Write nothing.
6. **With `--yes`**, in this order:
   1. **Stage gate.** Refuse unless the batch's stage is `proposed`,
      `cancelled` or `abandoned`. A batch that is `dispatched` or `pr-open`
      is never started twice, whether or not its runner still holds it (a
      closed herdr tab is the normal end of a run, not a free slot).
   2. **Branch gate.** Refuse if `origin/feat/batch-<id>` already exists and
      the stage is `proposed`: another scope (e.g. an `--org` triage and a
      repo triage of the same repo) already dispatched the same batch (§3.C
      Identity).
   3. `runner.can_dispatch(item)` → refuse with "runner `<name>` does not take
      run-unit work". Before any backend call, because it is the cheap
      routing gate (`protocols.py` `can_dispatch` docstring).
   4. `runner.preflight([item])`; refuse if `item.id in
      runner.existing_dispatches([item])` (a live session, naming its handle).
   5. `runner.dispatch(item)` → append the `dispatch` event.
   6. Forge writes (§3.E).

**Repair.** `batch dispatch <id> --repair [--yes]` redoes only the §3.E forge
writes for a batch whose last event is `dispatch`, using that event's branch
and `reserved_version`. It never calls the runner and never re-reserves. The
writes are idempotent (the marker check in §3.E), so repair adds only what is
missing. This is the path after "forge write fails after a successful
dispatch", whether or not the runner still holds the item.

**Run-unit contract.** A runner takes batches when it implements `from_env`,
its `can_dispatch` accepts `unit == "run"`, and its `dispatch` honours the
payload above. The contract is documented beside `WorkItem` and pinned by a
reusable contract test (Test Plan 4). Teaching `vk` or `cncd` to take run-unit
work is out of scope (§6).

**`fr-herdr` runner** (new package `packages/fr-herdr`, entry point
`herdr = "fr_herdr.runner:HerdrRunner"` in group `fr.runners`):

- `name = "herdr"`; `refresh()` is a no-op (no cache); `slot_budget()`
  returns 1 per call. Batch dispatch dispatches one item per invocation, so it
  does not consult `slot_budget`; the method exists for `tick` compatibility.
- `capabilities = {"git", "tests", "scm", "devcontainer"}` (the closed set in
  `fr/capabilities.py`; unit support is `can_dispatch`'s job, not a capability).
- `from_env()`: no arguments; reads `HERDR_WORKSPACE_ID`.
- `preflight`: `herdr` on PATH and `HERDR_ENV=1`, else refuse. Herdr's own rule
  is never to drive a session from outside it.
- `can_dispatch(item)`: `item.unit == "run"` and `payload["harness"]` is in
  the runner's harness table.
- `dispatch(item)`: `herdr tab create --workspace $HERDR_WORKSPACE_ID --cwd
  <checkout> --label <item.id> --no-focus` → `herdr agent start <name>
  --kind <harness> --pane <root pane> -- <model flag>` → `herdr agent prompt
  <name> <brief>`. The harness table maps harness to agent kind and model flag
  (`claude` → `--model <m>`; others added as verified live). Returns the pane
  id as the handle.
- **Identity.** A batch is identified by repo plus batch id, not by triage
  scope: a repo triage and its owner's `--org` triage that both define batch
  `x` for the same repo describe the **same** batch, share its item id, tab
  label and branch, and the branch gate (step 6.2) refuses the second
  dispatch. The tab label is the full item id (`<repo>/run/batch-<id>`), unique
  across repos; `existing_dispatches` matches live tabs by it. The agent name
  only has to satisfy herdr's `[a-z][a-z0-9_-]{0,31}`:
  `b-<first 20 chars of the batch id>-<4 hex of sha1(item.id)>`.
- The package is added to the `mypy` invocation in `AGENTS.md` and
  `.github/workflows/ci.yml`, and to the uv workspace members.
- `fr-herdr` never imports `fr.triage`; `fr` never imports `fr_herdr`.

fr makes no model call and does not wait on the run: dispatch returns once the
prompt is submitted (`no-claude-p-batch` holds: the runner starts an
interactive session).

### 3.D Version reservations

A repo opts in through the `version` block of `.fr/triage.yaml` (§3.I):

```yaml
version:
  source: {file: pyproject.toml, key: project.version}   # read from origin/<default>
  files: ["pyproject.toml", "packages/*/pyproject.toml", "plugins/*/.claude-plugin/plugin.json",
          ".claude-plugin/marketplace.json", "packages/fr-opencode-plugin/package.json", "uv.lock"]
  set: "uv run --no-project python scripts/bump-version.py {version}"
  relock: "uv lock"            # optional; run after `set`
```

- **`source`** is read with `git show origin/<default>:<file>` in the checkout
  (§3.I), never from a working tree that may be on any branch, and parsed by
  extension (`tomllib` for `.toml`, `json` for `.json`). That is the only
  manifest fr reads, and only at a declared key.
- **`files`** are globs (`fnmatch`, repo-relative). For super-fr they mirror
  `bump-version.py`'s globs. They can drift from the script (this spec's own
  `packages/fr-herdr/pyproject.toml` is matched by `packages/*/pyproject.toml`,
  but a future surface outside the globs would not be). A missed file fails
  safe: its conflict is "outside the version files" and the queue stops.
- **`set`** for super-fr is `bump-version.py`, which takes one argument (an
  explicit version, `patch|minor|major`, or `--check`) and already runs
  `uv sync`, so `relock` is redundant there.

**Reserve (at dispatch).** Dispatch-time order is the batch's explicit `order`,
then dispatch sequence. The reservation is the next version after the highest
of (the `source` version on origin, every live reservation), bumped by the
batch's `bump`. It is stored in the `dispatch` event and written into the brief.

**Reconcile (at merge).** §3.F computes the real order from PR files, which do
not exist at dispatch time. Before merging, fr re-derives the reservation
sequence in §3.F order and reads each PR's version at its head (`git show
<head_oid>:<source.file>`). A PR whose version is not its slot's number is
re-versioned by §3.F step 3b, whether or not it is behind main. fr never merges
a PR whose version is not higher than main's.

Why reserve rather than bump at merge time: in the common case (order
unchanged) a batch's CI builds and tests the number it will ship, early, and the
only conflict left after an earlier batch merges is in files whose correct
resolution is already known.

### 3.E Forge visibility

After `runner.dispatch` succeeds, the **engine** (not the runner, so the signal
is the same for every runner) writes to each member issue through `GhClient`:

1. label **`fr:in-progress`**, the existing `fr/labels.py` `LabelDef`
   (`ensure_labels`, then `edit_issue_labels(add=…)`);
2. one comment, opening with a hidden marker
   `<!-- fr-batch:<repo>/run/batch-<id> -->`, then: "Dispatched as batch
   `<id>` (<title>), with <other members>. Branch `feat/batch-<id>`." No pane
   id, host, or other local detail. Before posting, the engine lists the
   issue's comments (`GhClient.list_issue_comments`, §3.J) and skips the
   post when a
   marker comment for this item id exists, which makes `--repair` idempotent.

The brief's early draft PR does the rest: GitHub links it in each issue's
Development panel, and triage's existing stage derivation moves the member to
`pr-draft`.

**The bridge does not strip this label.** Verified in spec review:
`diff.py` changes labels only on the `tracking_issue` of phases in rendered
plans, removing only managed `fr:` labels the render did not produce;
`observe.py` views only plan-tracked issues; the one other label writer,
`fr_dispatch/__init__.py`, stamps a phase item's own issue; `fr_vk` writes no
`fr:` labels. Caveat: if a batch run's plan named a member issue as a phase
`tracking_issue`, the bridge would own that issue's `fr:` labels. The brief
therefore tells the run not to use member issues as phase tracking issues.

**Triage stage.** `fr/triage/stage.py` gains `in-progress`, derived from the
`fr:in-progress` label, which `collect` already fetches. `STAGES` becomes
closed > merged > pr-ready > pr-draft > in-progress > blocked > backlog: a
linked PR outranks the label, and a held issue outranks a `blocked` label.
`render.py` places `in-progress` in `IN_FLIGHT` with its own pill style.

**Cancel.** `batch cancel <id> --yes` removes the label, posts a marker
comment "batch `<id>` withdrawn", and appends a `cancel` event.

**Stale dispatch.** `check` gains a sixth set: an issue labelled
`fr:in-progress` whose `fr-batch` marker comment is more than 3 days old
(`.fr/triage.yaml` `stale_dispatch_days`) with no linked PR. The age comes from
the forge (the marker comment's `createdAt`, stored as
`Issue.dispatch_marker_at`), so every machine agrees. `collect` calls
`Forge.list_issue_comments` only for issues carrying `fr:in-progress`: one call
each, a small, bounded set. `check` reads the age from facts and the threshold
from the collected config (§3.I). Reported, never acted on.

### 3.F `batch merge`

```
fr triage batch merge [<id>...] [--yes]
```

No ids: every batch at stage `pr-open`.

**Facts.** `facts.json` moves to schema 3 (`FACTS_SCHEMA` 2 → 3):

- `PullRequest` gains `files` and `head_oid` (neither exists today).
  `headRefOid` is added to `OPEN_PR_LIST_FIELDS`, which already carries `files`.
- **The open-PR join.** Today a *linked* PR (one on a member's `Issue.prs`) is
  built from `list_prs(state=all)` with `PR_LIST_FIELDS`, which has neither
  field, and the open-PR list feeds only *unlinked* PRs into `Facts.prs`. A
  batch PR is always linked (it closes every member), so collect joins each
  open-PR record into the linked `PullRequest` with the same (repo, number).
  This also fills `checks`, `mergeable` and `merge_state` on linked open PRs,
  which today stay at their defaults.
- `Issue` gains `dispatch_marker_at` (§3.E); `Facts` gains `batch_prs` (§3.A)
  and `config` (§3.I).
- The `Forge` protocol gains `list_issue_comments(repo, number)` and
  `list_prs_by_head(repo, branch)`. `GhForge` implements both by delegating to
  the new `RealGhClient` methods of the same names (§3.J), so each operation
  has one GitHub implementation, whether collect or a batch verb calls it.

Collect's extra calls are bounded: one per `fr:in-progress` issue, one per
`dispatched` batch, and one config read per repo.

**Order.** Explicit `order` values are hard constraints. The rest are ordered
so that batches sharing files are not adjacent where avoidable, then by fewest
overlaps, then by lowest member tier, then by batch id. The printed plan lists,
per step, the PR, its reserved version, and the files it shares with later
steps: that is the conflict prediction, shown before anything merges.

**Per step, with `--yes`:**

1. Re-read the PR from the forge. Stop the queue if it is a draft, has failing
   required checks, or its head moved since the plan was printed.
2. Up to date, green, and its version is its slot number →
   `GhClient.pr_merge(repo, n, head_sha=<sha>, method=<repo default>)` (on
   GitHub: `gh pr merge <n> --<method> --match-head-commit <sha>`). Never `--admin`. A protection refusal (e.g. a
   required review) stops the queue and is reported verbatim.
3. **Needs a change** (behind main, or 3b: its version is not its slot
   number) → create a scratch worktree of the PR branch under
   `~/.cache/fr/triage/<scope>/merge/<branch>/` (from the checkout, §3.I); if
   behind, `git merge origin/<default>`:
   - (behind only) no conflict → continue;
   - every conflicted path matches `version.files` → `git checkout --theirs --
     <those paths>` (take main's side, so no file holds conflict markers),
     then continue;
   - any other conflicted path → `git merge --abort`, stop, print the PR and
     the paths, keep the scratch worktree for inspection.
   Then, if the version is not the slot number, run `set <slot>` and `relock`
   **with the scratch worktree as cwd** (super-fr's `set` uses the relative
   path `scripts/bump-version.py`). Commit ("chore: take reserved version <v>
   after batch <prev>" when a merge happened, else "chore: re-slot version to
   <v>"), push, wait for required checks (foreground, d5), then go to step 1.
4. Remove the scratch worktree after a successful merge.

**Resume.** Queue progress is never stored: every step re-derives from the
forge, so re-running after a stop starts at the first unmerged batch.

The scratch worktree sits outside every repo on purpose: merge edits branches
that other runs own, which fr-isolation forbids in the base clone, and a
batch's own workspace may have a live session in it.

**Forges.** Merge's forge operations (required checks, merge with head match,
PR re-read) are adapter methods (§3.J). On gitlab/gitea they raise
`UnsupportedForgeOperation`, and `batch merge` exits 2 with its message. Never a
silent no-op. (Today no non-GitHub triage can exist at all, since `collect`'s
only `Forge` is `GhForge`; the refusal is for when that changes.)

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
- The `judgements.yaml` section documents `batches:`, `events` and schema 2.
- Regenerate both mirrors (`sync-opencode.py`, `sync-hermes.py`). The engine
  ships in the wheel, so every harness gets the same verbs.

### 3.I The local checkout and `.fr/triage.yaml`

`fr triage` is forge-scoped and often runs from an unrelated directory. Three
batch steps need a local clone of the batch's repo: herdr's `--cwd`, reading
the version `source`, and merge's scratch worktree. So:

- The batch verbs that need a clone (`dispatch`, `merge`) take
  `--checkout PATH`, defaulting to the current directory's git toplevel. The
  clone's `origin` must resolve to the batch's repo, else exit 2 naming both.
  `create`, `edit`, `cancel` and `suggest` need no clone.
- `.fr/triage.yaml` is a new, optional, committed file in the target repo.
  `collect` reads it through the forge (`Forge.read_file_at_ref` at the
  default branch, which already exists) into `Facts.config`, per repo, so
  every verb, including `create`, `edit` and `check`, sees it without a
  clone. `dispatch` and `merge` use the collected config and refuse if it is
  older than the checkout's `origin/<default>` commit that last touched the
  file (re-collect). Keys: `defaults.launch`, `version`, `stale_dispatch_days`.
  Absent file: no defaults, no reservations, 3 days.
- The version `source` itself is read from the checkout (`git show
  origin/<default>:<file>`) at dispatch and merge, because a reservation must
  use the version at that moment, not at the last collect.
- For an `--org` triage, each batch belongs to one repo; its verbs need a
  checkout of that repo, and `--checkout` is how the operator gives one.

### 3.J The forge adapter

fr's forge adapter is the `GhClient` protocol (`fr/ghclient.py`; the name
predates the other backends), built by `fr.hostclient.client_for_backend`
into `RealGhClient`, `RealGlabClient` or `RealTeaClient`. Every forge operation
a batch verb performs goes through it. No batch module calls `gh`, `glab` or
`tea` directly, and none calls triage's `Forge` (that protocol serves `collect`
only).

Operations batches use that the adapter **already has**, on all three backends:
`edit_issue_labels`, `comment_issue`, `ensure_labels`.

Operations this spec **adds** to the protocol:

| Method | Used by | GitHub | gitlab / gitea |
|---|---|---|---|
| `list_issue_comments(repo, number)` | §3.E marker check, `--repair` | implemented | unsupported |
| `list_prs_by_head(repo, branch)` | §3.A batch PR lookup | implemented | unsupported |
| `pr_view(repo, number)` → state, draft, head oid, mergeable | §3.F step 1 | implemented | unsupported |
| `pr_required_checks(repo, number)` / `wait_required_checks` | §3.F steps 1 and 3 | implemented | unsupported |
| `pr_merge(repo, number, head_sha, method)` | §3.F step 2 | implemented | unsupported |
| `closing_ref(repo, number)` | §3.C brief | implemented | unsupported |

"Unsupported" is a typed `UnsupportedForgeOperation(op, backend, "gh#611")`
raised by the glab/tea adapters, which the batch verbs turn into exit 2 with
its message. It is declared in the adapter, one method at a time, rather than
as a `backend != "github"` check scattered through the verbs. That is the
surface gh#611's parity table is meant to find: each unsupported cell is a
method that raises, readable without running anything.

GitHub gets the attention for now (operator, 2026-09-25). `collect` stays on
triage's own `Forge`; whether it moves onto this adapter is decided in gh#611.

## 4. Error handling

| Situation | Behaviour |
|---|---|
| Runner package not installed | exit 2, names the package (same guard as `apply_cmd.py`) |
| Runner has no `from_env` | exit 2, "cannot be constructed outside its own bridge" |
| Runner refuses the unit | exit 2, "runner `<name>` does not take run-unit work"; nothing written |
| Batch stage `dispatched` or `pr-open` | exit 2; names the stage and, if live, the handle; suggests `--repair` for forge writes |
| Branch `feat/batch-<id>` already on origin for a `proposed` batch | exit 2, "already dispatched from another scope" |
| Runner reports the item live | exit 2, names the handle; nothing written |
| `runner.dispatch` fails | no event, no forge write; exit 1 with the runner's error |
| Forge write fails after a successful dispatch | event kept; exit 1 listing the issues not written; `dispatch --repair` completes them |
| Checkout's origin is not the batch's repo | exit 2, names both |
| No `version` block | no reservation; the brief omits the bump line |
| Merge conflict outside version files | stop, name PR and paths, keep scratch worktree, exit 1 |
| Required checks fail after an update push | stop, name the check, exit 1 |
| Non-GitHub backend on `merge` | exit 2, declared refusal (gh#611) |

## 5. Migration gate

`triage` stays in `fr.artifacts.trigger.READ_ONLY_COMMANDS`. The tuple's
criterion is "never mutates a registered artifact". The batch verbs write the
forge, `~/.cache/fr/triage/`, and scratch worktrees under that directory, never
an fr artifact in the invoking checkout. A `git merge` in a scratch worktree
moves whatever artifacts main carries, which is ordinary git and not an fr
rewrite. The pinned exemption test does not change, but the triage paragraph
of `trigger.py`'s docstring (which says every file triage writes is under its
state directory) is amended to cover forge writes and scratch-worktree pushes.

## 6. Non-goals

- Run-unit support (and `from_env`) in `vk` or `cncd` (a follow-up issue is
  filed at delivery).
- Forges other than GitHub for `merge`; a forge parity matrix (gh#611).
- GitHub auto-merge or a dispatched merge queue (d5).
- Resolving any conflict outside the declared version files.
- Cross-repo batches: a batch's members are in one repo. An `--org` triage may
  hold batches in several repos.
- Watching a run's progress: after dispatch, fr learns about the run only
  through the forge (draft PR, merge).

## 7. Reversed and kept fr-triage non-goals

The fr-triage spec (`implemented/specs/2026-09-21-fr-triage-design.md`) listed:

- **"Writing to the forge."** Reversed for `batch dispatch|merge|cancel`
  only, behind `--yes` (d1). `collect`, `check`, `render` and `suggest`
  still never write.
- **"Knowing about fr runs."** Kept: stages still come from forge facts alone.
  A dispatch becomes a forge fact (§3.E label, marker comment and draft PR),
  which is why the board can show it without reading any run cursor.

## 8. Test Plan

1. **Schema 2 model** (unit): a case-variant member key normalises to the
   judged key; an unjudged member, an empty `ids`,
   case-colliding batch ids and out-of-order events are refused at load;
   schema 1 loads as zero batches; a write upgrades it to 2.
2. **Open-batch rule and stages** (unit, facts constructed): a key in two open
   batches is refused by `create`/`edit`/`dispatch`; members of a `partial` or
   `cancelled` batch may join a new one; each stage in the §3.A table; a
   re-dispatch after `cancel` is `dispatched`; a PR closed unmerged gives
   `abandoned` and releases members; with two PRs on the branch the higher
   number wins; a merged PR with no `Closes` lines is found via `batch_prs`
   and gives `partial`.
3. **create / edit / suggest** (unit): launch resolution batch → defaults →
   refuse; `edit --add-issue/--remove-issue`; `edit` refused past `proposed`
   except `order`; `suggest` groups by shared cited file, theme and pattern and
   writes nothing.
4. **Run-unit runner contract** (unit): a reusable contract test (`from_env`,
   `name`, `refresh`, `slot_budget`, `can_dispatch` on `unit == "run"`,
   payload honoured); `fr-herdr` passes it;
   `vk` and `cncd` are refused by `load_runner`'s `from_env` check, and a stub
   runner that has `from_env` but only takes phases is refused by
   `can_dispatch` before `preflight` runs.
5. **Brief and WorkItem** (unit): identical judgements render byte-identical
   briefs; the brief has `Closes` for every member, the branch, the reserved
   version only when present, the model line, and the no-tracking-issue line;
   the WorkItem has `repo`, `tracking=None`, `workflow="fr-goal"`, issues in
   `payload`.
6. **fr-herdr** (unit, `herdr` faked): preflight refuses without `HERDR_ENV`;
   dispatch issues tab create (label = item id), agent start with the model
   flag, and prompt, in order; the agent name fits herdr's pattern for a
   40-char batch id; the same batch id in two different repos gets different
   tab labels and names; `existing_dispatches` matches by tab label.
7. **Dispatch without `--yes`** (unit): prints the plan, writes nothing to the
   file, the forge or the runner.
8. **Forge writes, gates and repair** (unit, the `GhClient` adapter
   faked): label and marker comment on every member only after
   `runner.dispatch` succeeds; a failed dispatch writes nothing; the comment
   carries no handle; `dispatch` is refused at `dispatched`/`pr-open` whether
   or not the runner reports the item live; a `proposed` batch whose branch
   exists on origin is refused; `--repair` after a partial forge failure calls
   no runner, keeps the stored reserved version, and posts no duplicate
   comment (marker read faked).
9. **Cancel** (unit): removes the label, posts the withdrawn comment, appends
   the event; without `--yes` writes nothing.
10. **`in-progress` stage and stale dispatch** (unit): derived from the label;
    outranked by a linked PR; outranks `blocked`; stale from the marker
    comment's age (`dispatch_marker_at`) with no PR, threshold from
    `Facts.config`; the board places it in-flight with its pill.
11. **Version reservation** (unit): source read from `origin/<default>` by key;
    sequence follows dispatch-time order and bump levels; reconcile re-assigns
    after a reorder; an up-to-date PR holding the wrong slot is re-versioned
    (3b) with `set` run in the scratch worktree; never merges a version not
    above main's; a conflict in a file outside `files` globs stops.
12. **Merge order** (unit): hard `order` respected; overlapping batches not
    adjacent when avoidable; deterministic tie-breaks.
13. **Merge refusals** (unit, forge faked): a draft, a failing required check, a
    moved head, a protection refusal (reported verbatim), and a non-GitHub
    backend each stop the queue with their message.
14. **Merge execution** (integration: git against a local bare origin, forge
    faked): two branches both bumping real multi-file manifests (TOML, JSON,
    a lockfile) merge in sequence, the second resolved via `--theirs` + `set`;
    a third conflicting in a non-version file stops the queue with the path
    named and the scratch worktree kept; a re-run resumes at the first unmerged
    PR.
15. **Facts schema 3** (unit): an open linked PR gets `files`, `head_oid`,
    `checks` and `merge_state` from the open-PR join; `dispatch_marker_at`,
    `batch_prs` and `config` are collected (forge faked); schema 2 facts are
    refused with the existing re-collect message.
16. **Import direction** (unit): `test_import_direction.py` admits
    `triage_batch_cmd.py` as a guarded soft point and still refuses any other
    `fr` → `fr_dispatch` import.
17. **Checkout and config** (unit): a checkout whose origin is another repo is
    refused; `create` resolves no launch defaults and `dispatch` resolves them
    from `Facts.config`; `dispatch` refuses a config older than the checkout's
    last change to `.fr/triage.yaml`; the version source is read from
    `origin/<default>`, not the working tree.
18. **Migration exemption** (unit): the pinned exemption test still passes.
19. **Forge adapter** (unit): each method §3.J adds is implemented by
    `RealGhClient` (subprocess faked) and raises `UnsupportedForgeOperation`
    naming gh#611 on `RealGlabClient` and `RealTeaClient`; `GhForge`'s two new
    methods delegate to `RealGhClient`; a tripwire fails if any batch module
    invokes `gh`, `glab` or `tea` directly or imports triage's `Forge`.
20. **Board** (unit): the Batches section renders each batch's members,
    derived stage, reserved version, PR, and for `pr-open` batches the planned
    merge order with shared files; members carry a batch chip.
21. **Live walk** (manual, post-implementation): create, dispatch through
    `fr-herdr`, and merge two real super-fr batches with overlapping files.
