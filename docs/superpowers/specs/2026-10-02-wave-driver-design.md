# Wave driver: batches run in waves, and the pages are generated, not hand-patched — design

**Date:** 2026-10-02 · **Branch:** `feat/wave-driver` · **Release:** minor (new verbs and skills)
**Origin:** operator brief on 2026-10-02, after the post-talk closing order was run by a scratchpad script and three hand-patched pages (journal `wave-driver-brief`).

## Requirements

R1. A triage batch can declare a `wave` (an integer) and `after` (batch ids that must be merged first). Both are set through `fr triage batch create` and `edit`, stored in `judgements.yaml`, and refused when invalid: an unknown id, the batch's own id, or a cycle.
R2. `fr triage batch drive` runs a set of batches to completion. One pass merges what is ready, closes out what merged, and dispatches what may start. `--once` makes one pass and exits; without it the verb sleeps between passes until nothing is left. It acts only with `--yes`; without it, it prints what the pass would do.
R3. A pass never lets more than `--max-inflight` batches be dispatched and unmerged (default 4). It dispatches in wave order, then merge order, then id, and skips a batch whose `after` batches are not all merged. A batch whose dependency was cancelled or abandoned is reported as blocked and is never dispatched.
R4. A pass merges a batch's PR only when the PR is not a draft and every check is green at that moment. It never readies, approves or un-drafts a PR, never waits for checks, and reports a failing CI once per head commit. The ready-for-review transition stays the operator's.
R5. After a batch merges, the driver starts its close-out session through the batch's runner: a work item whose brief is the `fr pickup` instruction for the batch (`--run <id>` for a goal batch, `--branch <name>` for a debug batch). A close-out is started at most once per batch, and the driver then merges the close-out's archive PR when it is not a draft and its checks are green.
R6. The driver keeps no state of its own. What was dispatched, merged or closed out is read from `judgements.yaml` events and the forge, so a stopped driver resumes where it left off, and a second driver on the same state directory refuses to start.
R7. `--once` exits 0 when it acted or everything is done, 3 when it did nothing and work remains (waiting on a draft PR, CI or a dependency), and 2 on a refusal. A loop or a harness's scheduler can drive it without parsing text.
R8. The driver is harness-neutral: it reaches a runner only through the runner registry and the forge only through the forge client, as the other batch verbs do. fr names no harness tool.
R9. Each issue judgement can carry `kind` (`defect`, `feature` or `parked`), and `judgements.yaml` can carry ranked `features` groups (`rank`, `title`, `ids`, `why`, `start`). `fr triage render` draws a "Closing order" section from them and from the batches' waves and dependencies. `fr triage check` reports open issues that sit in no batch and no feature group.
R10. `fr triage origins collect|check|render` classifies the issues filed in a window by origin. Judgements live in `origins.yaml` in the triage state directory: per issue a `category` (latent, regression, new-feature, leftover, gap, duplicate), a `source` (pipeline, recording, hand), the PR it relates to, a severity and a one-line reason. `render` writes the defect-origins page (counts, filings per day, time to fix by category, per-PR leaderboards, the issue table). A new skill, `fr-origins`, holds the classification discipline.
R11. `fr triage architecture render` writes the architecture page. The measured sections are generated: the summary strip, the waves and batch order, subsystem cards (open issues placed on a subsystem, source lines then and now), the size table, and filings per day. Authored sections (diagrams, narrative) are fragments the agent writes into the state directory and the verb splices in, in the order of a manifest. The `fr-audit` skill's architecture-page section is rewritten around this verb.
R12. Every page the engine writes carries a real `<title>`, defines its colours as tokens with light, dark and explicit-theme variants, and keeps a 16px side gutter at phone width. No page needs a hand patch after rendering. Publishing a page stays outside fr; the skills say how.
R13. A pass reports one line per action, in the same words in `--once` and loop mode, and ends with a one-line summary (`in flight`, `merged`, `pending`, `closing`).

## Design

### Background

The closing order of 2026-10-02 ran from `waves-watch.py`, a scratchpad script: it capped the runs in flight at four, held a dependency table, merged ready PRs and started close-outs. Three of its parts exist in fr only as prose or not at all: the dependencies and waves (no field), the in-flight limit (no check in `batch dispatch`), and the close-out session (`fr pickup` only prints a brief; fr-goal and fr-debugging tell the operator to open a session by hand). `fr triage batch merge` merges pr-open batches in order but blocks on required checks and does not wait for a draft to become ready. The three pages were a patched `fr triage render` output and two hand-built HTML files; `fr-audit` describes an architecture page as prose-guided and hand-authored, and nothing produces a defect-origins page.

### A. Waves and dependencies (R1)

`Batch` (`fr/triage/model.py`) gains `wave: int | None` and `after: list[str]`. `judgements.yaml` moves to schema 3; schemas 1 and 2 still load, and the first batch write upgrades the file, as the schema 2 upgrade did. The triage state directory is not an artifact kind, so there is no stamp migration. `batch create` and `batch edit` take `--wave N` and `--after ID` (repeatable); like the other fields they change only while the batch is `proposed`, except that `--wave` and `--after` may also change on a dispatched batch that has not merged, because the driver reads them live. Validation lives in `fr/triage/batch.py` with the open-batch rule: ids must exist in the file, a batch cannot name itself, and the `after` graph must be acyclic. `fr triage batch list` shows wave and dependencies. The dependency a batch waits on is satisfied only by stage `merged`; `cancelled` and `abandoned` make it unsatisfiable.

### B. The driver (R2–R8, R13)

A new module `fr/triage/batch_drive.py` holds the pass as a pure function over a snapshot: batches, their derived stages and PR states, the runner's existing dispatches, and the configuration (`max_inflight`). It returns an ordered list of actions (`merge`, `closeout`, `archive`, `dispatch`, `blocked`, `warn`); the command executes them. The pass runs in this order, so a slot freed by a merge is used in the same pass:

1. **Merge.** For each `pr-open` batch in merge order, take the PR from the forge client. Not a draft, every check `SUCCESS`, `SKIPPED` or `NEUTRAL`, and the head unchanged since the snapshot: merge it through the existing `merge_one` path (re-slotting its version as `batch merge` does) without the blocking wait. A failing check yields a `warn` action, recorded per head sha so it is reported once.
2. **Close out.** For each batch that has merged and has no `closeout` event: once the base branch carries the release commit that follows the merge, or ten minutes have passed with none (a PR with no fragment releases nothing), fast-forward the checkout and dispatch the close-out work item. A `CloseoutEvent{kind: closeout, at, runner, handle}` is appended after the dispatch succeeds.
3. **Archive.** Merge the open archive PR of a closed-out batch (a `chore/archive-*` or `chore/closeout-*` head naming the batch) when it is not a draft and green; never otherwise.
4. **Dispatch.** Count batches whose stage is `dispatched` or `pr-open`; while that count is below `max_inflight`, dispatch the next batch by (wave, merge order, id) whose `after` batches are all `merged`, through the existing `batch dispatch` code path (preflight, version reservation, brief, labels).

Stage derivation (`derive_batch_stage`) is unchanged; `closed-out` is derived from the presence of a `closeout` event and a merged archive PR, and is shown by `batch list`. State is the file and the forge, so there is no driver state: restarting re-derives everything. A lock file `drive.lock` in the state directory (pid, start time; stale when the pid is gone) refuses a second driver. The loop sleeps `--interval` seconds (default 120) and ends when no batch is pending, in flight or closing; `--once` runs one pass and exits with R7's codes. Forge writes go only through `GhClient`; other forges raise `UnsupportedForgeOperation`, as the other batch verbs do. The command lives in `triage_batch_cmd.py` (the `fr_dispatch` soft point), and `batch_drive.py` imports nothing from `fr_dispatch`.

### C. Close-out through the runner (R5)

The runner protocol has no close-out, and `fr_herdr` assumes a work item named for a batch. The close-out reuses unit `run` with `payload.kind: closeout` and item id `<repo>/run/closeout-<batch-id>`; `can_dispatch` accepts it, the brief is `fr pickup`'s instruction text, and the model is the harness's orchestrator binding. `fr_herdr.runner.agent_name` derives its name from the item id's last segment instead of requiring a `batch-` prefix. `existing_dispatches` already matches a tab by item id, so a close-out tab is not dispatched twice. Whether the session ends is not visible to the runner; the driver treats a merged archive PR as the end.

### D. The board's closing order (R9)

`judgements.yaml` issues gain optional `kind`; the file gains an optional `features:` list. `fr/triage/render.py` draws, ahead of the tier sections: the counts by kind, one table per wave (batch, skill, issues, why, size, dependencies, derived stage), the ranked features, and the parked issues. `check` adds a sixth set, **unplaced**: open issues with a `kind` that sit in no open batch and no feature group. The tiers below are unchanged. The `fr-triage` skill documents `kind`, `features` and the waves.

### E. Origins (R10)

`fr/triage/origins.py` (collector over `Forge`, rollups, renderer) and `origins.yaml` follow the engine-and-skill split of `fr triage`: `collect --since DATE` writes `origins-facts.json` (issues created since the date with state, closing PRs, hours to close); `check` lists unclassified issues; `render` writes `origins.html`. The classification is the agent's, from the `fr-origins` skill: a category by what the defect is (latent, regression, new-feature, leftover, gap, duplicate), a source by who found it, evidence read from the issue and the code, never inferred from its title alone. A render shows the share per source and category, filings per day, the median time to fix by category, and, for new-feature and leftover issues, the PRs that produced most of them.

### F. The architecture page (R11)

`fr/triage/architecture.py` reads `facts.json`, `judgements.yaml`, `origins.yaml` (if present), `subsystems.yaml` (subsystem name, path globs, and the ref to measure "then" at) and `architecture/manifest.yaml` (ordered section list: a generated section name or a fragment file). Line counts come from `git ls-tree` and `git show` at the two refs, so a measurement names its commits. Authored fragments are HTML the agent writes into `architecture/`; the verb validates that each is well-formed, inlines it, and applies the shared theme. The `fr-audit` skill keeps its measured-versus-projected rule and now names the verb.

### G. Skills, docs and mirrors

New skill `plugins/super-fr/skills/fr-origins/SKILL.md`; edited `fr-triage`, `fr-audit`, `fr-goal` and `fr-debugging` (the close-out line mentions that a batch's driver starts it); `AGENTS.md` (the triage paragraph, the batch verbs); mirrors regenerated with `scripts/sync-opencode.py` and `scripts/sync-hermes.py`; `READ_ONLY_COMMANDS` and the import-direction allowlist unchanged (the verbs stay under `triage`). A change fragment `.changes/feat-wave-driver.yaml` with `bump: minor`.

### H. Out of scope

A detached daemon; readying or approving a PR; a runner other than through the registry; GitLab and Gitea batch writes; changing `batch merge`'s own ordering; publishing a page (the Artifact tool stays the agent's); a general workflow scheduler.

## Test Plan

Automated (CI, `uv run pytest`), with a fake runner and a fake forge client:

1. **Waves and dependencies (R1).** `wave` and `after` round-trip through schema 3; schemas 1 and 2 load; an unknown id, a self-dependency and a cycle are refused with exit 2 and the file unchanged.
2. **The pass (R2, R3, R13).** With six batches in two waves and `--max-inflight 4`: four dispatch in wave order; a batch whose dependency is unmerged is skipped; a merge in the same pass frees a slot that is used in that pass; a cancelled dependency yields `blocked`.
3. **Merge rule (R4).** A draft PR, a pending check, a failing check and a moved head are never merged; a ready green PR is; a failing check warns once per head sha. No call to ready, approve or update a PR is ever made.
4. **Close-out (R5).** One close-out is dispatched per merged batch with the right `fr pickup` flag for goal and debug batches; none on a second pass; none before the release commit or the ten-minute fallback; the archive PR merges only when ready and green.
5. **Resume and lock (R6, R7).** Killing between any two actions and running again repeats nothing; a second driver refuses; `--once` exit codes are 0, 3 and 2 in their cases.
6. **Harness neutrality (R8).** `batch_drive.py` imports no `fr_dispatch` or harness module (the import-direction tripwire), and the skill-neutrality tripwire passes on the edited and new skills.
7. **Herdr close-out (R5).** `agent_name` for a close-out item is unique per batch and stable; `can_dispatch` accepts `payload.kind: closeout`.
8. **Board section (R9).** A judgements fixture renders the waves, features and parked tables; `check` reports an unplaced issue; a file with no `kind` renders as before.
9. **Origins (R10).** A fixture of fifteen issues classifies into the six categories; the render's counts, per-day buckets and median time to fix match a hand computation; `check` lists an unclassified issue.
10. **Architecture page (R11, R12).** A fixture repo with two refs yields correct line counts per subsystem; a fragment is inlined in manifest order; a malformed fragment is refused; every page has a `<title>` and the three theme blocks.
11. **Mirrors and install.** Both mirror tripwires, the agent-mirror test and the install tests pass with the new skill.

Post-merge, operator-driven:

12. `fr triage batch drive --once` (no `--yes`) on this repo's judgements prints the plan the scratchpad script followed on 2026-10-02.
13. A real wave of two small debug batches is driven from dispatch to archive without a hand step, with the PRs readied by the operator.
14. The three pages render from the triage state and publish without a hand patch.

## Implementation Plans

To be written by `fr-plan` after spec review.
