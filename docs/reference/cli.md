---
title: "The fr command line"
tldr: |
  Every fr command and subcommand with its one-line purpose, generated from the CLI itself, plus the handful you will actually type.
standalone_style: broadsheet
covers:
  - packages/fr/src/fr/cli.py
reviewed: 2026-11-11 docs-currency phase 5
---

# The fr command line

`fr` is the engine behind the skills: plans, isolation, the run cursor, the acceptance
matrix, triage and the rest. You rarely type it for a normal feature, because the skills
call it for you, but every step they take is a plain command you can run yourself. Add
`--help` to any command for its flags.

Inside a clone of this repo, run `uv run fr ...` so you get the CLI of the code you are
reading rather than whatever was installed globally.

## The ones you will meet first

| Command | What it does |
|---|---|
| `fr isolation up --branch <b>` | Create the isolated workspace for a branch. See [fr-isolation](../explainers/fr-isolation.md). |
| `fr isolation exec -- <cmd>` | Run a build, test or lint command inside that workspace's container. |
| `fr status` | Read-only report on every plan: phases, steps, tracking issues. Never writes. |
| `fr apply <plan>` | Mirror a plan to tracking issues. Dry run unless you add `--yes`; `--to <runner>` also queues its phases. See [dispatch](../explainers/fr-dispatch.md). |
| `fr acceptance status` | The open acceptance debt in one screen. See [the acceptance matrix](acceptance-matrix.md). |
| `fr run status <run-id>` | Where a workflow run's cursor is. See [workflow shapes](workflow-shapes.md). |
| `fr docs check` | Fail when code a page covers changed and the page did not. See [docs currency](../docs-currency.md). |
| `fr archive` | Move finished plans and their specs under `implemented/`. |

Commands that change files are dry runs by default and say what they would do; add `--yes`
to apply. `fr skills` prints a short map of the skills and the commands each one drives.

## Every command

<!-- generated:cli-tree -->
- `fr apply`: Render + observe + diff + apply for a plan.
- `fr status`: Read-only plan report (allowlist-safe; never mutates).
- `fr archive`: Move finished plans (and specs) to implemented/.
- `fr undispatch`: Close a plan's tracking Issues and null the fields.
- `fr pickup`: Output phase scope (markdown) for an agent.
- `fr repair`: Normalize stale plan/spec refs + strip dead plan-config keys (dry-run; --yes to write).
- `fr skills`: Show the v2 CLI surface + skill summaries.
- `fr services`: Read-only: the resolved forge / ci / tracking services.
- `fr acceptance`: Acceptance matrix: business-level acceptance tests × verification levels.
  - `fr acceptance check`: The gate: refs resolve, staleness, exit 2 on failing rows.
  - `fr acceptance report`: Render the report set (or, with --check, verify it is in sync).
  - `fr acceptance status`: Terminal nag: counts by status + the open acceptance debt rows.
  - `fr acceptance summary`: GitHub Actions-friendly Markdown summary: compact counts + collapsible debt.
  - `fr acceptance set-status`: Move an existing row's status, in place, with a reason (spec §3.G.2).
  - `fr acceptance add`: Insert a schema-validated row after its capability's last row (agents never hand-edit YAML shapes); a new capability appends at the end.
  - `fr acceptance init`: Scaffold matrix + CI workflow + backfill rule + gitignore (idempotent).
  - `fr acceptance backfill`: Emit the agent backfill protocol + deterministic inventory (markdown).
  - `fr acceptance digest`: Markdown for the upserted "Acceptance debt" issue (idempotence marker included; zero debt prints a closable body).
- `fr plan`: v2 plan editing commands.
  - `fr plan create`: Scaffold a new v2 plan folder + append spec row.
  - `fr plan edit`: Mutate plan state — tick a step OR complete a phase.
  - `fr plan rework`: Scaffold a sibling rework plan + append spec row.
  - `fr plan rework-add`: Append an origin item to a rework plan's _meta.origin_items.
  - `fr plan rework-list`: List rework plans in the current repo.
  - `fr plan self-review`: Soft lints beyond schema validation.
  - `fr plan proportionality`: Compare the branch's diff with the plan: unreferenced new files, out-of-plan touches, size vs estimate.
- `fr spec`: v2 spec status commands.
  - `fr spec status`: Compute and print spec status (markdown).
- `fr migrate`: v2 migration tools.
  - `fr migrate v1-to-v2`: Convert every v1 .md plan in this repo to a v2 folder + rewrite spec tables.
  - `fr migrate dirs`: Migrate the legacy archived-plans/ layout to implemented/{plans,specs}/.
  - `fr migrate artifacts`: Bring every live artifact up to the version this fr writes.
- `fr isolation`: Isolated workspaces: git worktree + devcontainer.
  - `fr isolation up`: Create worktree + start the profile's devcontainer against it.
  - `fr isolation exec`: Run a command inside the isolation container (exit code passthrough).
  - `fr isolation restart`: Bounce a resource-wedged devcontainer, keeping the worktree intact.
  - `fr isolation rebuild`: Recreate the devcontainer against the existing worktree.
  - `fr isolation stop`: Stop a workspace's devcontainer to free its resources, keeping the rest.
  - `fr isolation status`: Show worktree, container, PR, and bound-session state for isolation workspaces.
  - `fr isolation down`: Stop the container, remove the worktree, drop the state.
  - `fr isolation attach`: Bind a session to a workspace (traceability; idempotent).
  - `fr isolation detach`: Unbind a session (idempotent; exit 0 when nothing was bound).
  - `fr isolation verify-merge`: Verify a merged branch's changes actually reached the base branch.
  - `fr isolation gc`: Reconcile isolation workspaces host-wide (#354).
- `fr init`: Repo initialization: devcontainer profile scaffolding (driven by fr-init).
  - `fr init scaffold`: Write + commit .devcontainer/<profile>/ and the fr-profiles.yaml entry, plus host secrets placeholders.
  - `fr init migrate`: Rewrite this repo's vk spellings to fr (#272): profiles yaml, devcontainer mounts/customizations, isolation state dir.
  - `fr init agents`: Render fr's two dispatched agents into .claude/agents/ and commit them, so a Claude Code cloud session can dispatch fr-spec-reviewer and….
  - `fr init validator-wrapper`: Write scripts/validate-plans.sh (0755) and stage it — the harness-neutral remedy every isolation guard names when a plan repo is missing the wrapper.
- `fr cloud`: Claude Code cloud sessions: check the environment, print its setup script.
  - `fr cloud doctor`: Every cloud prerequisite and its state; exits 1 when any fails.
  - `fr cloud setup-script`: Print the cloud environment setup script (paste it into the environment's Setup script; new sessions run it).
- `fr repos`: Instrument locally-checked-out repos (driven by the operator's collection).
  - `fr repos sync`: Write docs/superpowers/plan-config.yaml into each checked-out repo.
- `fr journal`: Scope-keyed durable run-state (spec\|plan\|debug): add / render / check.
  - `fr journal add`: Append one entry to ``docs/superpowers/journals/<slug>.md``.
  - `fr journal resolve`: Append a resolution record closing one finding (spec §3.G.1).
  - `fr journal file`: File leftovers as issues before `deliver` (spec 2026-10-14 exit-gates R10).
  - `fr journal render`: Emit journal entries as Markdown (fail-open: missing/bad file → nothing).
  - `fr journal check`: Freshness gate.
  - `fr journal handoff`: Compose the curated executor handoff for one phase (fail-closed).
- `fr models`: Tier→model bindings for fr-goal subagent dispatch (harness-keyed).
  - `fr models set`: Persist a binding to ~/.config/fr/models.yaml, then materialize it into any on-disk OpenCode agent files it affects.
  - `fr models check`: Report every binding's live state, with a replacement for each dead one and any upgrade offer.
  - `fr models get`: Print the user model config (optionally one harness).
  - `fr models resolve`: Print the bound model, or nothing (exit 0) when unbound.
  - `fr models apply`: Re-run the materialiser for one harness over the current resolved config.
- `fr harness`: Declared harness-parity matrix: which surfaces are wired on which harness.
  - `fr harness parity`: Render the declared harness-parity matrix (`fr.harness.parity.yaml`).
- `fr hermes`: Install/uninstall super-fr into a Hermes Agent home.
  - `fr hermes install`: Merge super-fr's hooks, allowlist them, and apply the SOUL.md block.
  - `fr hermes uninstall`: Reverse install: strip super-fr's hooks, allowlist, SOUL block, hook tree.
- `fr workflow`: Workflow shape manifests: resolve (repo > shipped) and validate.
  - `fr workflow check`: Validate one shape by name, or every discoverable shape with --all.
- `fr verification`: Verification strategies: resolve (repo > shipped) and validate.
  - `fr verification list`: Every strategy that resolves, and where it came from.
  - `fr verification check`: Validate one strategy by name, or every discoverable one with --all.
  - `fr verification exit`: Print a run's (or spec's) exit: its kinds, its gates and the gated rows (spec 2026-10-14 exit-gates R1).
  - `fr verification set`: Insert or rewrite one `strategy:`, row bullet or `gate:` line of the spec's `## Verification`, journal why, commit and re-sync the PR labels.
  - `fr verification walk`: Install the candidate into a throwaway prefix, smoke it, run each row's scenario, and write the log `deliver` verifies (spec §C).
  - `fr verification prerelease`: Cut an on-demand pre-release of BRANCH: dispatch the `prerelease.yml` workflow….
- `fr run`: Durable workflow-run cursor: start / status / advance / resolve / check.
  - `fr run start`: Start a run: resolve the shape, ensure isolation, write run state in it.
  - `fr run reshape`: Move a drifted cursor onto the shape's current step list.
  - `fr run adopt`: Give in-flight work a run cursor, inferred from artifacts that exist.
  - `fr run status`: Print the cursor, every step's state, who is holding each dispatched unit, since when, and whether it has returned (spec §4.C).
  - `fr run cost`: Print what a run cost, per step and per model, from its usage file — spec `2026-09-25-lean-cost-aware-process-design.md` §5.B.4.
  - `fr run advance`: Advance the cursor by one step.
  - `fr run resolve`: Record the outcome of an `agent` step, or answer a step's operator gate.
  - `fr run claim`: Put the orchestrator's reported identity onto the dispatch `fr run advance` already opened for a unit — the `agent`/ `harness` half of `Attempt` that….
  - `fr run check`: Freshness gate: non-zero when the cursor sits on a failed step.
  - `fr run gates`: Every `gate: operator` step this run's manifest declares, and who cleared it — the source `fr-goal`'s `deliver` step reads for the PR body's….
- `fr validate`: Structural validation of generated artifacts.
  - `fr validate artifacts`: Structurally validate every live artifact against the version this fr writes.
  - `fr validate plans`: Run the plan-file validator bundled with this fr: `[--profile <yaml>] [FILE]...`.
- `fr triage`: Backlog triage: collect forge facts, check judgements, render a board.
  - `fr triage collect`: Read the forge and write facts.json for the scope.
  - `fr triage check`: Report unranked issues and PRs, settled, orphaned, unreachable, stale, unplaced, duplicate candidates, duplicates, awaiting live and more.
  - `fr triage clean-labels`: Remove `fr:in-progress` and `fr:claimed` from closed issues that still carry them (board-truth R3; post-merge truth R2).
  - `fr triage render`: Write triage.html from facts.json and judgements.yaml.
  - `fr triage board`: Write board.html: one card per batch in its lifecycle column (`fr.triage.kanban.COLUMN_TITLES`), with live session status and a jump command.
  - `fr triage batch`: Batches: groups of judged issues delivered as one run.
    - `fr triage batch focus`: Switch the terminal to a batch's live session, through the runner that dispatched it.
    - `fr triage batch list`: Print one line per batch in judgements.yaml, or "no batches".
    - `fr triage batch create`: Add a proposed batch of judged issues.
    - `fr triage batch edit`: Change a proposed batch; past `proposed`, only --order (and, until it merges, --wave and --after) may change.
    - `fr triage batch cancel`: Withdraw a batch: unlabel and comment on each member, append a cancel event.
    - `fr triage batch suggest`: Print candidate groupings (shared file, theme, pattern).
    - `fr triage batch replace`: Replace a managed batch harness/model in place, or reconcile without replay.
    - `fr triage batch dispatch`: Hand a batch to a runner as one fr-goal run, and mark its issues taken.
    - `fr triage batch adopt`: Put a running session under the wave driver as an existing batch; launches nothing.
    - `fr triage batch merge`: Merge pr-open batch PRs in the computed order, re-slotting versions (§3.F).
    - `fr triage batch closeout`: Close out every landed, ungated batch in ONE housekeeping PR (exit-gates R15).
    - `fr triage batch drive`: Drive batches to completion: merge what is ready, close out what merged, dispatch what may start (wave order, then merge order, then id).
  - `fr triage architecture`: The architecture page: measured sections plus authored fragments.
    - `fr triage architecture render`: Write architecture.html: the summary, subsystem cards and size table, with the authored fragments `architecture/manifest.yaml` places among them.
  - `fr triage scope`: This triage scope's identity and config.
    - `fr triage scope show`: Print the scope's name, id, state directory and scope config.
    - `fr triage scope retire`: Release every claim another scope holds in this scope's facts, in one pass (gh#1123): the operator's way to retire a scope that stopped.
  - `fr triage claim`: Claims: which scope may act on an issue (fr:claimed plus a marker comment).
    - `fr triage claim list`: This scope's held-elsewhere, expired and owed claims, from facts.
    - `fr triage claim sync`: Write every owed claim, due refresh and owed release (R3, R8, R10, R11).
    - `fr triage claim take`: Replace another scope's EXPIRED claim with this scope's, for *batch* (R9); with --stale, a live one whose holder stopped refreshing (gh#1123).
    - `fr triage claim release`: Withdraw this scope's claim on *key* at any time, or another scope's once expired (R9); with --stale, once its heartbeat is stale (gh#1123).
  - `fr triage lease`: The drive lease: which driver runs this scope (one per scope).
    - `fr triage lease show`: Who holds the scope's drive lease, since when and until when; or `free`.
    - `fr triage lease take`: Take the scope's drive lease for this machine's driver, from whoever holds it (R9): the operator's take-over of a lease another driver left.
  - `fr triage drive`: The cloud driver's one pass per wake, and the record of its session results.
    - `fr triage drive pass`: One pass of the cloud driver: restore the state from its ref when it is missing or older, renew the drive lease, collect….
    - `fr triage drive record`: Apply every result the agent recorded for the outbox's requests to the scope's state, empty the outbox, and push the state ref.
  - `fr triage history`: The history page: the snapshot timeline and the finished waves.
    - `fr triage history render`: Write history.html: the snapshot timeline, the finished waves as tabs, then the authored fragments `history/manifest.yaml` places among them.
  - `fr triage origins`: Defect origins: collect issues filed since a date, classify them, render the page.
    - `fr triage origins collect`: Read the issues created since a date and write origins-facts.json.
    - `fr triage origins check`: List issues with no classification, and classifications for issues not in the facts.
    - `fr triage origins render`: Write origins.html from origins-facts.json, origins.yaml and judgements.yaml, with the fragments `origins/manifest.yaml` places among the sections.
  - `fr triage state`: Copy a scope's durable state (judgements, origins, manifests, fragments, snapshots) to a repo directory and back, or push and fetch its state ref.
    - `fr triage state export`: Copy the scope's durable state to <dir>/<scope>/.
    - `fr triage state push`: Push the scope's state to its ref, the branch refs/heads/fr-triage/<scope-id>….
    - `fr triage state fetch`: Restore the scope's state from its ref, refs/heads/fr-triage/<scope-id>: the state directory's ref files become exactly the ref's….
    - `fr triage state import`: Copy <dir>/<scope>/ back into the state directory.
- `fr usage`: What harness sessions and runs cost, split by activity and step (read-only).
  - `fr usage collect`: Normalize sessions into the usage cache (`$HOME/.cache/fr/usage/`).
  - `fr usage report`: Render collected usage (reading live for any session not yet collected).
  - `fr usage backfill`: Write `implemented/usage/<run>.yaml` for every archived run that has none, and price an archived file's sessions that were still open when it was….
  - `fr usage compare`: Compare two sets of runs: phases, turns, main/subagent tokens, cost, review findings per phase and re-opened findings (read-only, deterministic).
- `fr debt`: What this repo owes: acceptance, plans and owed actions (read-only).
  - `fr debt issue`: Keep the one open `<repo>: Technical debt` issue current (R9-R11).
  - `fr debt archive-pr`: Open or refresh the one draft PR archiving long-merged plans (R12).
- `fr docs`: Docs currency: pages must keep up with the code they cover (read-only).
  - `fr docs check`: Fail when a covered path changed and its page did not (exit 1).
  - `fr docs status`: List every page with its covered globs and its `reviewed` stamp.
- `fr gate`: Post-merge gates: record that a gate passed on its PR (the gate ledger).
  - `fr gate pass`: Comment why PR <n>'s gate <g> passed, then swap gate:<g> for gate:<g>-passed (R14).
  - `fr gate backfill`: Bring pre-v6 owed work into the gate lanes.
- `fr ops`: Manual operations: check, apply, attest (spec 2026-10-22-fr-ops).
  - `fr ops status`: Report each selected op's state, running its probes.
  - `fr ops apply`: Apply one op, or a whole phase, in `needs` order; stop at the first failure.
  - `fr ops attest`: Close an UNVERIFIABLE op as DONE (attested), at a terminal, in an ops profile.
  - `fr ops trust`: Show every probe and command of the selected ops and, confirmed at a terminal….
  - `fr ops seal`: Encrypt stdin into --target without ever leaving plaintext behind.
  - `fr ops secret`: Read a value live and pass it to COMMAND on stdin; never to stdout.
  - `fr ops clip`: Put a value on the clipboard.
  - `fr ops scratch`: Run COMMAND, then --cleanup on success, failure, Ctrl-C or SIGTERM.
  - `fr ops stub`: Propose an op stub per devops command step of the plan's spec (R11).
  - `fr ops gate`: The DevOps stage: pre-merge ops, the merge, post-merge ops, the devops Test Plan steps, the gate pass, the tester hand-off and the archive….
- `fr release`: Release gating: what still waits on a post-merge gate since the last final.
  - `fr release status`: List every PR merged since the last final tag that still waits on a post-merge gate.
- `fr closeout`: Close-out records: one outcome per spec Test Plan step.
  - `fr closeout outcome`: Record one outcome for each Test Plan step in --step (R18).
<!-- /generated:cli-tree -->

The list above is generated from the command tree by `scripts/sync-readme.py`; a test fails
when it is stale, so it cannot drift from the code.
