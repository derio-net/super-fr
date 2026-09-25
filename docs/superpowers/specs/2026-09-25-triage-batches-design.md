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
| d6 | Forge writes go through `GhClient` where it already covers the operation; merge-only operations are GitHub-only with a declared refusal elsewhere. A forge parity matrix is its own spec (gh#611). |
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

- every id in `ids` is a key in `issues` (judged); `ids` is non-empty;
- batch `id`s are unique, case-insensitively;
- `events` is time-ordered and every `kind` is `dispatch` or `cancel`.

**Checked by `create`, `edit` and `dispatch`** (they load `facts.json` too):
no issue key belongs to two **open** batches. A batch is open unless its last
event is `cancel`, or its derived stage is `merged` or `partial`. `partial` is
terminal: its still-open members are released and may join a new batch.
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

A cancelled batch may be dispatched again: the new `dispatch` event becomes the
last one.

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
Launch settings resolve from the batch's `launch`, then `.fr/triage.yaml`
`defaults.launch` (§3.I), then refuse. fr never picks a model. `edit` refuses
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
     `Closes <owner>/<repo>#<n>` for every member."
   - "Bump the version to `<reserved>`" (only when reserved)
   - "Use `<model>` for every subagent and every model tier"
4. **Build the WorkItem:** `unit="run"`,
   `id=run_item_id(<repo>, "batch-<id>")`, `workflow="fr-goal"`,
   `parent=None`, `inputs=()`, `tracking=None`, and
   `payload={brief, harness, model, branch, reserved_version, issues}` where
   `issues` is the list of member keys. `tracking` stays `None` because `tick`
   treats a non-`None` tracking as one tracker Issue to stamp
   (`fr_dispatch/__init__.py`), which a multi-issue batch is not.
5. **Without `--yes`:** print the brief, runner, harness, model, branch and
   reserved version. Write nothing.
6. **With `--yes`**, in this order:
   1. `runner.can_dispatch(item)` → refuse with "runner `<name>` does not take
      run-unit work". First, because it is the cheap routing gate
      (`protocols.py` `can_dispatch` docstring) and must not wait behind a
      backend call.
   2. `runner.preflight([item])`.
   3. If `item.id in runner.existing_dispatches([item])`: when the batch's last
      event is a `dispatch` for this runner, skip to step 6.5 (the **retry
      path** for failed forge writes). Otherwise refuse, naming the live
      handle.
   4. `runner.dispatch(item)` → append the `dispatch` event.
   5. Forge writes (§3.E). They are idempotent, so the retry path redoes only
      what is missing.

**Run-unit contract.** A runner takes batches when it implements `from_env`,
its `can_dispatch` accepts `unit == "run"`, and its `dispatch` honours the
payload above. The contract is documented beside `WorkItem` and pinned by a
reusable contract test (Test Plan 4). Teaching `vk` or `cncd` to take run-unit
work is out of scope (§6).

**`fr-herdr` runner** (new package `packages/fr-herdr`, entry point
`herdr = "fr_herdr.runner:HerdrRunner"` in group `fr.runners`):

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
- **Identity.** The tab label is the full item id (`<repo>/run/batch-<id>`),
  which is unique across triage scopes. `existing_dispatches` matches live tabs
  by that label. The agent name only has to satisfy herdr's
  `[a-z][a-z0-9_-]{0,31}`: `b-<first 20 chars of id>-<4 hex of sha1(item.id)>`.
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
sequence in §3.F order. A PR whose version is not its slot's number is re-set
through the §3.F update path. fr never merges a PR whose version is not higher
than main's.

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
   id, host, or other local detail. A comment carrying the marker is never
   posted twice, which makes the retry path (§3.C step 6.3) idempotent.

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
the forge (the marker comment's `createdAt`), so every machine agrees. `collect`
fetches comments only for issues carrying `fr:in-progress`: one
`gh issue view --json comments` each, a small, bounded set. Reported, never
acted on.

### 3.F `batch merge`

```
fr triage batch merge [<id>...] [--yes]
```

No ids: every batch at stage `pr-open`.

**Facts.** `facts.json` moves to schema 3 (`FACTS_SCHEMA` 2 → 3):
`PullRequest` keeps `files` and gains `head_oid`. `files` is already fetched for
open PRs only (`OPEN_PR_LIST_FIELDS`, used for anchoring then discarded);
`headRefOid` is added to `OPEN_PR_LIST_FIELDS`. Collect makes no extra call for
this. Both fields exist on open PRs only, which is all merge needs.

**Order.** Explicit `order` values are hard constraints. The rest are ordered
so that batches sharing files are not adjacent where avoidable, then by fewest
overlaps, then by lowest member tier, then by batch id. The printed plan lists,
per step, the PR, its reserved version, and the files it shares with later
steps: that is the conflict prediction, shown before anything merges.

**Per step, with `--yes`:**

1. Re-read the PR from the forge. Stop the queue if it is a draft, has failing
   required checks, or its head moved since the plan was printed.
2. Up to date and green → `gh pr merge <n> --<repo default method>
   --match-head-commit <sha>`. Never `--admin`. A protection refusal (e.g. a
   required review) stops the queue and is reported verbatim.
3. Behind main → create a scratch worktree of the PR branch under
   `~/.cache/fr/triage/<scope>/merge/<branch>/` (from the checkout, §3.I) and
   `git merge origin/<default>`:
   - no conflict → push;
   - every conflicted path matches `version.files` → `git checkout --theirs --
     <those paths>` (take main's side, so no file holds conflict markers),
     then run `set <reserved>`, then `relock`, commit "chore: take reserved
     version <v> after batch <prev>", push;
   - any other conflicted path → `git merge --abort`, stop, print the PR and
     the paths, keep the scratch worktree for inspection.
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
<backend> (gh#611)". Never a silent no-op. (Today no non-GitHub triage can
exist at all, since `collect`'s only `Forge` is `GhForge`; the refusal is for
when that changes.)

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
- `.fr/triage.yaml` is a new, optional, committed file in the target repo,
  read from `origin/<default>` of the checkout with `git show`, never from the
  working tree. Keys: `defaults.launch`, `version`, `stale_dispatch_days`.
  Absent file: no defaults, no reservations, 3 days.
- For an `--org` triage, each batch belongs to one repo; its verbs need a
  checkout of that repo, and `--checkout` is how the operator gives one.

## 4. Error handling

| Situation | Behaviour |
|---|---|
| Runner package not installed | exit 2, names the package (same guard as `apply_cmd.py`) |
| Runner has no `from_env` | exit 2, "cannot be constructed outside its own bridge" |
| Runner refuses the unit | exit 2, "runner `<name>` does not take run-unit work"; nothing written |
| Batch live and last event is this runner's dispatch | retry path: redo missing forge writes only |
| Batch live otherwise | exit 2, names the handle; nothing written |
| `runner.dispatch` fails | no event, no forge write; exit 1 with the runner's error |
| Forge write fails after a successful dispatch | event kept; exit 1 listing the issues not written; re-run takes the retry path |
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

1. **Schema 2 model** (unit): an unjudged member, an empty `ids`,
   case-colliding batch ids and out-of-order events are refused at load;
   schema 1 loads as zero batches; a write upgrades it to 2.
2. **Open-batch rule and stages** (unit, facts constructed): a key in two open
   batches is refused by `create`/`edit`/`dispatch`; members of a `partial` or
   `cancelled` batch may join a new one; each stage in the §3.A table; a
   re-dispatch after `cancel` is `dispatched`.
3. **create / edit / suggest** (unit): launch resolution batch → defaults →
   refuse; `edit --add-issue/--remove-issue`; `edit` refused past `proposed`
   except `order`; `suggest` groups by shared cited file, theme and pattern and
   writes nothing.
4. **Run-unit runner contract** (unit): a reusable contract test (`from_env`,
   `can_dispatch` on `unit == "run"`, payload honoured); `fr-herdr` passes it;
   `vk` and `cncd` are refused by `load_runner`'s `from_env` check, and a stub
   runner that has `from_env` but only takes phases is refused by
   `can_dispatch` before `preflight` runs.
5. **Brief and WorkItem** (unit): identical judgements render byte-identical
   briefs; the brief has `Closes` for every member, the branch, the reserved
   version only when present, the model line, and the no-tracking-issue line;
   the WorkItem has `tracking=None`, `workflow="fr-goal"`, issues in `payload`.
6. **fr-herdr** (unit, `herdr` faked): preflight refuses without `HERDR_ENV`;
   dispatch issues tab create (label = item id), agent start with the model
   flag, and prompt, in order; the agent name fits herdr's pattern for a
   40-char batch id; two scopes' same batch id get different tab labels and
   names; `existing_dispatches` matches by tab label.
7. **Dispatch without `--yes`** (unit): prints the plan, writes nothing to the
   file, the forge or the runner.
8. **Forge writes and retry** (unit, `GhClient` faked): label and marker
   comment on every member only after `runner.dispatch` succeeds; a failed
   dispatch writes nothing; the comment carries no handle; a re-run after a
   partial forge failure takes the retry path and posts no duplicate comment.
9. **Cancel** (unit): removes the label, posts the withdrawn comment, appends
   the event; without `--yes` writes nothing.
10. **`in-progress` stage and stale dispatch** (unit): derived from the label;
    outranked by a linked PR; outranks `blocked`; stale from the marker
    comment's age with no PR; the board places it in-flight with its pill.
11. **Version reservation** (unit): source read from `origin/<default>` by key;
    sequence follows dispatch-time order and bump levels; reconcile re-assigns
    after a reorder; never merges a version not above main's; a conflict in a
    file outside `files` globs stops.
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
15. **Facts schema 3** (unit): `files` and `head_oid` kept for open PRs;
    schema 2 facts are refused with the existing re-collect message.
16. **Import direction** (unit): `test_import_direction.py` admits
    `triage_batch_cmd.py` as a guarded soft point and still refuses any other
    `fr` → `fr_dispatch` import.
17. **Checkout resolution** (unit): a checkout whose origin is another repo is
    refused; `.fr/triage.yaml` is read from `origin/<default>`, not the
    working tree.
18. **Migration exemption** (unit): the pinned exemption test still passes.
19. **Live walk** (manual, post-implementation): create, dispatch through
    `fr-herdr`, and merge two real super-fr batches with overlapping files.
