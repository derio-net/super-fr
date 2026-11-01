# Stale artifacts migrate by default, in their own commit — design

**Issue:** derio-net/super-fr#1242 (the operator decision of 2026-10-31 replaces the issue's
"offer a chore PR, then rebase" proposal). Related: #861, #891, #1260 (Test Plan cost lines).

## Context

`fr.cli`'s root callback calls `fr.artifacts.trigger.ensure_artifacts_current` before every
non-exempt command (`packages/fr/src/fr/artifacts/trigger.py:349`). Today the gate acts in
exactly one context. **Interactive** means a TTY on stdin and stdout, no CI marker, and
`FR_NON_INTERACTIVE` unset (`is_interactive`, `trigger.py:298`). Only there does it migrate
and commit. Even then it refuses on the default branch (`trigger.py:467`), on a detached HEAD
(`:455`), when the root is not the repository root (`:443`), and for a file with uncommitted
edits (`uncommitted_veto`, `commit.py:364`). Every **non-interactive** context refuses
outright (`trigger.py:411-423`), and `.claude/rules/artifact-versioning.md` ("Agent sessions,
pods and CI always land non-interactive — by design") forbids loosening that.

Almost all real fr work happens in non-interactive contexts: an agent's Bash tool, a hermes
pod, `fr isolation exec`, CI. So in practice the gate never migrates. It refuses in the middle
of unrelated work: a debug journal never written, a close-out `fr pickup` refused, chore PRs
opened by hand on every fr bump (#1242's frank walkthrough). Consumer CI is worse. The
scaffolded acceptance-report job installs `fr` from `main` (`fr/acceptance/scaffold.py:145`)
and runs `fr acceptance check` with `CI` set. So **a consumer's main goes red on every fr
release** even though nothing in the repo changed (blog-craft since 2026-10-26, and three
consumer repos in another org on 6.0.0 release day).

Two halves of #1242 are already built and stay as they are:

- **The commit is alone.** `commit_migration` → `commit_paths` (`commit.py:466,486`) commits
  exactly the migrated paths under a generated `chore(fr): migrate <n> <noun> to fr <version>`
  message (`migration_commit_message`, `commit.py:432`). Other staged or unstaged work never
  rides along.
- **Ceilings are widened by the same migration.** The `widen-fr-version-ceiling` repair
  (`fr/artifacts/fr_version.py:46,90`) rewrites a plan's `<N.0.0` ceiling to admit the
  installed major. It is part of the same `run_migrations` pass, so its edit lands in the same
  commit.

What is missing is acting in the two non-interactive contexts where acting is safe: an
**fr-isolation workspace** (a real work branch whose commits survive and reach a PR) and
**CI** (an ephemeral checkout, where migrating the working tree is harmless but committing is
pointless). The one context the old rule was really protecting stays refused: a daemon/bridge
checkout that is `reset --hard` every tick (#286), where a commit is silently discarded.

## Requirements

R1. In a non-interactive context inside a **valid fr-isolation workspace** on a non-default, non-detached branch, the gate migrates the stale artifacts, commits that migration **alone** as fr's generated `chore(fr): migrate …` commit, and then runs the command, exactly as it already does for an interactive operator on a work branch.

R2. A fr-isolation workspace is valid only when its `.fr-isolation` marker passes the same checks the edit gate makes (`plugins/super-fr/hooks/lib/fr-isolation-decision.sh`): the marker parses, and its recorded `toplevel` equals the repository's actual toplevel. For `mode: worktree` (or a missing `mode`, which the edit gate reads as worktree), the toplevel must also be a linked worktree (`--git-common-dir` ≠ `--git-dir`), and HEAD must not be on a branch other than the marker's `branch` (a marker with no `branch` is not drift). For `mode: external`, there must be container evidence. Any other mode, or any failed check, means "not a workspace".

R3. A non-interactive context that is neither CI nor a valid workspace (a bridge/daemon checkout, a base clone driven by an agent) still refuses and writes nothing. Its refusal adds one line naming the way to get the migration carried: enter isolation (`fr isolation up --branch <branch>`), where the next fr command migrates and commits it.

R4. `FR_NON_INTERACTIVE` stays an explicit "do not write to git" opt-out. When it is truthy, a workspace context refuses as in R3 rather than committing.

R5. In **CI** (any truthy marker in `CI_ENV_VARS`), the gate migrates the checkout's working tree **in place, never commits**. Files with uncommitted edits are held back, as in every other context. It warns on stderr, naming how many artifacts were migrated, that the repo should carry the migration on a branch, and that these files must not be committed with other work. Under GitHub Actions this is also a `::warning::` annotation. Then it runs the command. This holds on the default branch too, because nothing is committed. A tree that cannot be migrated (an unreadable artifact, a failed migration, a partial migration) still fails, with the existing messages.

R6. The default-branch, detached-HEAD, wrong-root, lock-held and uncommitted-file refusals keep their current behaviour in every committing context (interactive and workspace). Nothing ever auto-commits on the default branch.

R7. When work commits already exist on the branch (an fr upgrade mid-run), the migration commit lands on top of them as its own commit. History is never rewritten and nothing is force-pushed.

R8. A plan whose `fr_version` ceiling excludes the installed major (e.g. `<6.0.0` under fr 6.x) is widened inside that same migration commit, in a workspace exactly as interactively.

R9. `.claude/rules/artifact-versioning.md` is amended in this PR. It records the 2026-10-31 decision, replaces the "do not make non-interactive contexts migrate" paragraph with the context table below, and keeps the two invariants that still hold: no automatic commit on the default branch, and the migration is always its own visible commit. `trigger.py`'s module docstring says the same.

R10. Nothing new opens a migration-only PR for a repo with no work in flight. Its CI stays green through R5, and its next work branch carries the migration through R1.

R11. A session's first gated command is often the SessionStart acceptance nag (`fr-acceptance-nag.sh`, and its OpenCode port `nag.ts`). When that command migrates and commits, the hook surfaces the gate's one-line commit notice to the session. A refused context's nag line names `fr isolation up --branch <branch>` as the way to carry the migration.

## Design

### A. The context table

`ensure_artifacts_current` replaces its single `interactive` test with one classification,
`migration_context(...) -> "ci" | "opt-out" | "interactive" | "workspace" | "refuse"`, in this
precedence:

| Context | Test | Migrates | Commits |
|---|---|---|---|
| ci | any truthy `CI_ENV_VARS` marker | working tree, in place (veto kept) | **never** |
| opt-out | `FR_NON_INTERACTIVE` truthy | no | no |
| interactive | TTY on stdin and stdout | yes | yes (git-state guards apply) |
| workspace | valid fr-isolation workspace (R2) | yes | yes (git-state guards apply) |
| refuse | anything else (bridge/daemon checkout, agent in a base clone) | no | no |

CI comes first because a CI runner may allocate a pty, and a CI checkout must never be
committed to, whatever else is true. `FR_NON_INTERACTIVE` comes before interactive because it
is a TTY-bearing wrapper's explicit opt-out (`trigger.py:202`). `is_interactive` keeps its
signature, its meaning and its tests: its other callers (`models_cmd`, `triage_cmd`,
`archive_cmd`, `ops_cmd`, `ops_gate_cmd`, `fr/ops/apply.py`) are unaffected. It is one input to
the classification, not replaced by it.

**The test seam.** `ensure_artifacts_current`'s `interactive: bool | None` keyword becomes
`context: MigrationContext | None`. Every existing caller and test that passes `interactive=`
or monkeypatches `trigger.is_interactive` moves to `context=` (`interactive=True` →
`"interactive"`, `interactive=False` → `"refuse"`, keeping each test's current meaning). The
two tests that pin "CI never migrates" (`test_non_interactive_refuses_without_migrating_or_committing`,
`test_the_non_interactive_refusal_does_not_reach_the_offer`, both of which pass
`env={"CI": "true"}`) are split. Their refusal half is kept under `context="refuse"`, and a new
test pins the CI in-place behaviour. `tests/conftest.py` gains an autouse fixture that deletes
every `CI_ENV_VARS` marker and `FR_NON_INTERACTIVE`, so a test that wants CI sets it explicitly.
Without it, `GITHUB_ACTIONS=true` on the CI shards and in release.py's staged suite would
silently turn tests that classify from the environment into the ci row, green locally and red
in CI. (`tests/scenarios/_common.sh` exports `CI=true` and `FR_SKIP_MIGRATION=1`; the scenarios
below override both.)

### B. Workspace validation (R2) and its order

`packages/fr/src/fr/run/workspace.py` already validates a marker in Python for `fr run start`
(`_is_linked_worktree` :37, `_container_evidence` :63, `_marker_mode_holds` :73, which fails
closed and returns a reason, and `_marker_at` :113, which checks toplevel identity). Those
helpers **move** into a new `fr.isolation.marker` module, gaining a public
`valid_workspace(root, branch) -> WorkspaceVerdict` (ok, or not-a-workspace with a one-line
`reason`). `fr.run.workspace` imports them from there, and the gate uses the same function.
That gives two Python callers and one implementation. The other marker readers
(`isolation/where.py:111`, `isolation/external.py`, `usage/capture.py`) read the marker for
other purposes and are not touched. `valid_workspace` adds R2's branch-drift rule, which
`_marker_mode_holds` lacks: a current branch that differs from a present `marker["branch"]`
is drift, while a missing `branch` or a detached HEAD is not. It also takes the edit gate's
missing-`mode`-means-worktree reading. The authority it mirrors is
`plugins/super-fr/hooks/lib/fr-isolation-decision.sh` (the toplevel and mode checks,
:214-251), cited in its docstring.

The order inside `ensure_artifacts_current` becomes:

1. exempt? → return. Stale? (`is_stale`) no → return. Neither touches git beyond today.
2. Classify from the environment and streams alone: **ci**, **opt-out** or **interactive**
   return immediately. Otherwise the candidate is workspace-or-refuse.
3. `git_context(root)` once. A `GitRefusal` gets today's "could not establish git state"
   refusal (`trigger.py:432-441`). A `NoRepo` is not a workspace: refuse (R3) with reason "not a
   git repository".
4. For the committing contexts (interactive, workspace candidate): today's **wrong-root** and
   **detached-HEAD** refusals, in today's order (`trigger.py:443-466`). A workspace mid-rebase
   therefore sees "HEAD is detached … finish or abort it first", never "enter isolation".
5. Workspace candidate only: `valid_workspace(state.toplevel, state.branch)`. If it fails,
   refuse with R3's message carrying the verdict's reason.
6. **Default-branch** refusal (`trigger.py:467`), for both committing contexts.
7. Lock, migrate (with `uncommitted_veto`), commit alone. This is the existing
   `_migrate_and_commit`, unchanged, including the partial-failure and adoption-offer
   behaviour. On a successful commit it emits one line that the hooks relay (§D):
   `fr: migrated and committed <n> artifact(s): <commit subject> (<short sha>)`.

For **ci**, step 2 goes straight to §C. It never consults the git-state refusals, because
nothing is committed. It still takes the lock and the veto.

### C. CI in place (R5)

A new `_migrate_in_place(root, registry, emit)` runs `run_migrations(root, dry_run=False,
registry=registry, veto=uncommitted_veto(root))` under the same `migration_lock`. The veto
costs one `git status` and changes nothing on a clean CI checkout, but it protects a local
shell or agent environment that exports `CI=1` while holding uncommitted edits. A veto that
cannot read git state (no repo) is treated as "no edits". The function never calls `commit_*`.
It skips `_adoption_offer`, which offers to write run files and makes no sense in CI. On full
success it writes, **on stderr like everything else the gate says**:

```
fr: <n> artifact(s) in <root> were written for an older fr; migrated in place for this run (NOT committed).
  Do not commit these files with other work. Carry the migration on a branch: the next fr command in an fr-isolation workspace commits it alone.
```

and, when `GITHUB_ACTIONS` is truthy, also
`::warning title=fr artifacts stale::<n> artifact(s) migrated in place for this run; carry the migration on a branch.`
**on stderr too.** The gate's stdout invariant (`trigger.py:336-340`) stays unbroken, so a
`--json` command or a `>> $GITHUB_STEP_SUMMARY` redirect is never contaminated. The Actions
runner is believed to process workflow commands from both streams. That is unverified here, so
the live row checks it on first real use. If the annotation does not render, the stderr warning
still does and nothing fails, and a follow-up moves the annotation to `$GITHUB_STEP_SUMMARY`.
Any failure (`report.failed`, a raised migration, `inspection_failures`) refuses with today's
messages (`_refuse`, exit 2).

A CI-marked environment that later commits with `git add -A` would fold the in-place
migration into its work commit. The warning's second line is the mitigation, and the risk is
stated in the rule (§E). A real CI checkout is discarded, so it never commits.

Matrix migrations re-render the committed reports as companions
(`matrix_status_split.py:177-243`), so after an in-place migration `fr acceptance check`
sees a consistent tree. super-fr's own CI still catches its own staleness: `fr validate
artifacts` is exempt from the gate, so the `validate-artifacts` job (`ci.yml:130`) keeps
failing a stale tree. release.py runs the exempt `fr migrate artifacts --yes` and `fr release
status` (`scripts/release.py:140-158,257`), so it is unaffected.

### D. Refusal text and the hooks (R3, R11)

`_will_not_act_here` keeps its six lines. The non-interactive refusal's `because`/`detail`
name the actual reason: "this context is non-interactive and not an fr-isolation workspace
(<reason>)", keeping the bridge rationale as the detail. It gains one line before `preview:`:

```
  carry it:  fr isolation up --branch <branch>   (the next fr command there migrates and commits it alone)
```

`plugins/super-fr/hooks/fr-acceptance-nag.sh`: on success, if its captured stderr holds a line
starting `fr: migrated and committed`, it prepends that line to the message it emits. On a
refusal, its "acceptance nag skipped: artifacts stale" line becomes "…: artifacts stale — in an
fr-isolation workspace the next fr command migrates and commits them; elsewhere run `fr
migrate artifacts --yes` on a branch". `packages/fr-opencode-plugin/src/nag.ts` gets the same
two changes, keeping its `super-fr-parity:` marker and its `bun test` cases. The migration is a
handful of git calls inside SessionStart, which has no 1500 ms ceiling (unlike SessionEnd).

### E. Rule and docs (R9)

- `.claude/rules/artifact-versioning.md`: section "1. Agent sessions, pods and CI always land
  non-interactive — by design" is rewritten as "1. Which contexts migrate". It gets §A's table,
  the 2026-10-31 decision with a link to #1242, the two invariants that remain (no automatic
  commit on the default branch; a migration is always its own commit), and §C's CI ride-along
  caveat. The bridge rationale is kept for the refuse row. The "Do not 'fix' it later"
  paragraph is replaced by: never commit in CI, and never commit outside a valid workspace or an
  operator's terminal. "What the CLI-entry gate will and will not do" item 1 is updated the same
  way. The rewrite keeps the "Exempt commands" prose that
  `test_the_rule_prose_names_every_read_only_command` (`test_migration_trigger.py:183`) reads.
- Regenerate its OpenCode mirror `.opencode/instructions/artifact-versioning.md` with
  `scripts/sync-opencode.py`, guarded by `test_tripwire_opencode_instructions_sync.py`. Run
  `scripts/sync-hermes.py` as well, in case the SOUL rules bundle carries it.
- `trigger.py` module docstring: the tree diagram gains the workspace and CI branches.
- No explainer mentions the gate (checked: `docs/explainers/`), so the explainers-currency
  rule is not triggered beyond the minor bump. The PR body says so.
- Change fragment `.changes/feat-auto-migrate-own-commit.yaml`, `bump: minor`.

### F. Candidate scenarios

Both are installed-CLI scenarios under `tests/scenarios/`, run in CI by
`tests/integration/test_scenarios.py` and by `fr verification walk`. Each one **unsets every
`CI_ENV_VARS` marker, `FR_NON_INTERACTIVE` and `FR_SKIP_MIGRATION`** after sourcing
`_common.sh`, then sets exactly what it tests:

- `auto-migrate-workspace.sh`: a fresh `git init` repo with a bare local origin and `main` as
  its default branch, holding one plan whose `fr_version` ceiling excludes the installed major.
  It adds a linked worktree on `feat/x` with a hand-written valid marker (`mode: worktree`,
  matching `toplevel` and `branch`) and one work commit. With stdin not a TTY, `fr plan self-review <plan-dir>`
  (a gated, read-only command) run in the worktree exits 0. HEAD's subject is `chore(fr): migrate …`, its parent is the work
  commit (R7), the commit touches only the plan's `_meta.yaml` (R1), and the ceiling is widened
  (R8). Negative leg: the same command in the primary checkout, now on a branch with no marker,
  exits 2 with the `carry it:` line and leaves the tree unchanged (R3).
- `auto-migrate-ci-in-place.sh`: the same stale fixture on `main`, plus a minimal current-schema
  `docs/acceptance/matrix.yaml` with its committed reports, with `CI=true` and
  `GITHUB_ACTIONS=true`. `fr acceptance check` exits 0. The plan is widened in the working tree,
  `git log` gains no commit, stderr carries the warning and the `::warning` line, and stdout
  carries neither (R5).

### G. Out of scope

- A migration-only PR opened by the drive loop, the close-out or a schedule (R10, the
  operator's decision d4: nothing new).
- Rebasing a migration commit beneath existing work (R7, decision d2).
- Making `fr validate artifacts` tolerate staleness.
- The fr-goal / fr-debugging skill prose ("fr refused … run `fr migrate artifacts --yes`")
  stays accurate for refused contexts and is not edited (fr-goal sits at its line cap).

## Verification

strategy: candidate
gate: tester
- auto-migrate-refuses-outside-workspace: none — a refusal that writes nothing is pinned by unit tests over the context classification and the trigger in CI; the workspace scenario's negative leg adds an installed-CLI check of the same path.
- auto-migrate-git-guards-hold: none — the default-branch, detached-HEAD and uncommitted-file guards are existing behaviour, re-pinned per context by unit tests in CI.
- auto-migrate-nag-surfaces-commit: none — the hook and nag.ts are pinned by their own shell and bun tests in CI; a scenario cannot drive a harness SessionStart.
- auto-migrate-live-sweep: live — only a released fr, meeting real stale consumer repos in the coming per-repo sweep, shows the migration commit landing alone in a real PR, consumer CI going green over a stale main, and the GitHub annotation rendering from stderr; walked on first real use.

## Test Plan

- [candidate] Pre-merge — agent-driven: `fr verification walk --run <run-id>` runs `tests/scenarios/auto-migrate-workspace.sh` and `tests/scenarios/auto-migrate-ci-in-place.sh` against the candidate install (§F). **Cost:** fixture (a local `git init` with a bare origin, no network or forge), about a minute per scenario. The same scenarios also run in CI.
- [tester] Post-merge — operator-driven, **walked on first real use**: in the coming per-repo sweep, with the released fr, the first fr command in each stale repo's isolation workspace migrates and commits `chore(fr): migrate … to fr <version>` alone, and the sweep's PR carries it as its own commit. In at least one consumer repo whose main is red only from stale artifacts, the next acceptance-report run on main is green, and its run page shows the in-place warning annotation (or, failing that, the stderr warning in the log; then file the `$GITHUB_STEP_SUMMARY` follow-up). Record the walk for `auto-migrate-live-sweep` with `fr acceptance set-status --walk`. **Cost:** none: no rehearsal, no fixture, no disposable repo. It rides the sweep that is already planned, and the gate stays held until that sweep runs.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
