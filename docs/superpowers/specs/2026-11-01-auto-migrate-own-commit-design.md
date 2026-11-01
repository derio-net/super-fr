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

R2. A fr-isolation workspace is valid only when its `.fr-isolation` marker passes the same checks the edit gate makes: the marker parses, and its recorded `toplevel` equals the repository's actual toplevel. For `mode: worktree`, the toplevel must also be a linked worktree (`--git-common-dir` ≠ `--git-dir`) and HEAD must be on the marker's `branch`. For `mode: external`, there must be container evidence. Any other mode, or any failed check, means "not a workspace".

R3. A non-interactive context that is neither CI nor a valid workspace (a bridge/daemon checkout, a base clone driven by an agent) still refuses and writes nothing. Its refusal adds one line naming the way to get the migration carried: enter isolation (`fr isolation up --branch <branch>`), where the next fr command migrates and commits it.

R4. `FR_NON_INTERACTIVE` stays an explicit "do not write to git" opt-out. When it is truthy, a workspace context refuses as in R3 rather than committing.

R5. In **CI** (any truthy marker in `CI_ENV_VARS`), the gate migrates the checkout's working tree **in place, never commits**, and emits a warning naming how many artifacts were migrated and that the repo should carry the migration on a branch. Under GitHub Actions this is also a `::warning::` annotation. Then it runs the command. This holds on the default branch too, because nothing is committed. A tree that cannot be migrated (an unreadable artifact, a failed migration, a partial migration) still fails, with the existing messages.

R6. The default-branch, detached-HEAD, wrong-root, lock-held and uncommitted-file refusals keep their current behaviour in every committing context (interactive and workspace). Nothing ever auto-commits on the default branch.

R7. When work commits already exist on the branch (an fr upgrade mid-run), the migration commit lands on top of them as its own commit. History is never rewritten and nothing is force-pushed.

R8. A plan whose `fr_version` ceiling excludes the installed major (e.g. `<6.0.0` under fr 6.x) is widened inside that same migration commit, in a workspace exactly as interactively.

R9. `.claude/rules/artifact-versioning.md` is amended in this PR. It records the 2026-10-31 decision, replaces the "do not make non-interactive contexts migrate" paragraph with the context table below, and keeps the two invariants that still hold: no automatic commit on the default branch, and the migration is always its own visible commit. `trigger.py`'s module docstring says the same.

R10. Nothing new opens a migration-only PR for a repo with no work in flight. Its CI stays green through R5, and its next work branch carries the migration through R1.

## Design

### A. The context table

`ensure_artifacts_current` replaces its single `interactive` test with one classification,
`migration_context(env, stdin, stdout, root) -> "interactive" | "workspace" | "ci" | "refuse"`,
in this precedence:

| Context | Test | Migrates | Commits |
|---|---|---|---|
| ci | any truthy `CI_ENV_VARS` marker | working tree, in place | **never** |
| refuse (opt-out) | `FR_NON_INTERACTIVE` truthy | no | no |
| interactive | TTY on stdin and stdout | yes | yes (git-state guards apply) |
| workspace | valid fr-isolation workspace (R2) | yes | yes (git-state guards apply) |
| refuse | anything else (bridge/daemon checkout, agent in a base clone) | no | no |

CI comes first because a CI runner may allocate a pty, and a CI checkout must never be
committed to, whatever else is true. `FR_NON_INTERACTIVE` comes before interactive because it
is a TTY-bearing wrapper's explicit opt-out (`trigger.py:202`). `is_interactive` keeps its
current signature and meaning (its tests stay). It is one input to the classification, not
replaced by it.

### B. Workspace validation (R2)

New function `fr.isolation.marker.valid_workspace(root: Path) -> WorkspaceVerdict` (a small
new module, imported lazily by the gate so the not-stale path stays free). It is the Python
counterpart of steps 3a/3b of `plugins/super-fr/hooks/fr-isolation-required.sh`:

- read `<toplevel>/.fr-isolation` as JSON (absent, unreadable or not a dict → not a workspace);
- `marker["toplevel"]` resolved must equal the git toplevel the gate already holds
  (`GitContext.toplevel`);
- `mode == "worktree"`: `git rev-parse --git-common-dir` ≠ `--git-dir` (resolved), and the
  current branch equals `marker["branch"]` (a different branch is drift → not a workspace).
  A detached HEAD is not drift for the edit gate, but here the detached-HEAD refusal (R6) fires
  first anyway;
- `mode == "external"`: `fr.isolation.where.container_evidence()`;
- any other mode → not a workspace.

The verdict carries a one-line `reason` for the not-a-workspace cases. R3's refusal prints it,
so a drifted or copied marker says why it did not count. `where.py`'s private `_marker`
reader moves into this module and `where.py` imports it (one reader of the marker).

The gate needs `GitContext` before it can validate, so the order inside
`ensure_artifacts_current` becomes: exempt → stale? → classify CI/opt-out/TTY from env and
streams alone → only when that gives neither ci nor interactive, read `git_context` and
validate the workspace → for the committing contexts, the existing git-state refusals → lock
→ migrate.

### C. CI in place (R5)

A new `_migrate_in_place(root, registry, emit)` runs `run_migrations(root, dry_run=False,
registry=registry)` under the same `migration_lock`. It runs with no veto, because a CI
checkout has no operator edits. It never calls `commit_*`, and it skips `_adoption_offer`,
which is an offer to write run files and makes no sense in CI. On full success it emits:

```
fr: <n> artifact(s) in <root> were written for an older fr; migrated in place for this CI run (not committed).
  Carry the migration on a branch: the next fr command in an fr-isolation workspace commits it.
```

and, when `GITHUB_ACTIONS` is truthy, also prints
`::warning title=fr artifacts stale::<n> artifact(s) migrated in place for this run; carry the migration on a branch.`
on stdout. GitHub reads workflow commands from stdout. This is the one line the gate writes to
stdout, and the spec accepts it because it only happens in CI. Any failure (`report.failed`, a
raised migration, `inspection_failures`) refuses with today's messages (`_refuse`, exit 2).

super-fr's own CI still catches its own staleness. `fr validate artifacts` is exempt from the
gate (`READ_ONLY_COMMANDS`), so the `validate-artifacts` job keeps failing a stale tree, while
`acceptance-report`'s `fr acceptance check` now proceeds over an in-place migration. That
split is deliberate: the validator is the diagnostic, and the acceptance gate is about rows.

### D. Refusal text (R3)

`_will_not_act_here` keeps its six lines. The non-interactive refusal's `because`/`detail`
change to name the actual reason: "not an fr-isolation workspace (<reason>)". It gains one line
before `preview:`:

```
  carry it:  fr isolation up --branch <branch>   # the next fr command there migrates and commits it alone
```

### E. Rule and docs (R9)

- `.claude/rules/artifact-versioning.md`: section "1. Agent sessions, pods and CI always land
  non-interactive — by design" is rewritten as "1. Which contexts migrate". It gets §A's table,
  the 2026-10-31 decision with a link to #1242, and the two invariants that remain (no
  automatic commit on the default branch; a migration is always its own commit). The bridge
  rationale is kept for the refuse row. The "Do not 'fix' it later" paragraph is replaced by:
  never commit in CI, never commit outside a valid workspace or an operator's terminal.
  "What the CLI-entry gate will and will not do" item 1 is updated the same way.
- `trigger.py` module docstring: the tree diagram gains the workspace and CI branches.
- AGENTS.md's paragraph on agents needing `fr migrate artifacts --yes` stays true for refused
  contexts. One clause is added that in an isolation workspace it now happens on its own.
- No explainer mentions the gate (checked: `docs/explainers/`), so the explainers-currency
  rule is not triggered beyond the minor bump. The PR body says so.
- Change fragment `.changes/feat-auto-migrate-own-commit.yaml`, `bump: minor`.

### F. Out of scope

- A migration-only PR opened by the drive loop, the close-out or a schedule (R10, the
  operator's decision: nothing new).
- Rebasing a migration commit beneath existing work (R7).
- Making `fr validate artifacts` tolerate staleness.
- The fr-goal / fr-debugging skill prose ("fr refused … run `fr migrate artifacts --yes`")
  stays accurate for refused contexts. It is not edited (fr-goal sits at its line cap).

## Verification

strategy: candidate
gate: tester
- auto-migrate-refuses-outside-workspace: none — a refusal that writes nothing is pinned by unit tests over the context classification and the trigger in CI; the scenario cannot add evidence beyond them.
- auto-migrate-git-guards-hold: none — the default-branch, detached-HEAD and uncommitted-file guards are existing behaviour, re-pinned per context by unit tests in CI.
- auto-migrate-live-sweep: live — only a released fr, meeting real stale consumer repos in the coming per-repo sweep, shows the migration commit landing alone in a real PR and consumer CI going green over a stale main; walked on first real use.

## Test Plan

- [tester] Post-merge — operator-driven, **walked on first real use**: in the coming per-repo sweep, with the released fr, the first fr command in each stale repo's isolation workspace migrates and commits `chore(fr): migrate … to fr <version>` alone, and the sweep's PR carries it as its own commit. In at least one consumer repo whose main is red only from stale artifacts, the next acceptance-report run on main is green with the in-place warning annotation. Record the walk for `auto-migrate-live-sweep` with `fr acceptance set-status --walk`. **Cost:** none: no rehearsal, no fixture, no disposable repo. It rides the sweep that is already planned, and the gate stays held until that sweep runs.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
