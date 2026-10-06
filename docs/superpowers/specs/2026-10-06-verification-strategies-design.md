# Verification strategies before merge — design

**Date:** 2026-10-06
**Slug:** `2026-10-06-verification-strategies`
**Status:** design (fr-goal, batch `verification-kinds`)
**Repo:** `derio-net/super-fr` (single-repo change)
**Issues:** super-fr#818, super-fr#822, super-fr#959 — one PR

## 1. Goal

Stop treating "merged and released" as "verified". Three changes, one PR:

1. **Verification strategies (#818).** How a change is verified becomes a named,
   extensible strategy, resolved like a workflow shape. A strategy says *when* it
   runs (before or after merge) and *who* drives it (an agent or the operator). A
   strategy that an agent drives before merge gates `deliver` through witnessed
   evidence. fr ships four strategies: `candidate`, `client-live`, `prerelease` and
   `live`. The post-merge `live` walk is the last resort, and a spec must say why it
   is needed.
2. **Closing on live evidence (#822).** A PR may not say `Closes #n` while an
   acceptance row that cites #n still waits for a post-merge walk. Instead, the
   issue stays open with an `fr:awaiting-live` label and out of the ranked backlog.
   It closes when the walk is recorded. Each walk names its harness and model.
3. **Conflict hand-back (#959).** When `fr triage batch drive` hits a real merge
   conflict, it hands the conflict back to the batch's session, at most twice. It
   then lists the batch under "needs you" instead of logging `stopped again at
   <head>` forever.

### Non-goals

- Forge containers or recorded forge APIs as scenario fixtures, and headless
  harness-driven `/fr-goal` scenarios. A scenario here is an executable script run
  against a fresh local git fixture. Richer fixtures are follow-ups.
- A shipped `staging`/`preview` strategy for services. The mechanism supports a
  repo-authored one, documented as an example and not shipped (R4).
- Any change to how `release.yml` versions `main`.

## 2. Background (verified against the code)

- **Deliver gate.** `_deliver_pr_gate` (`packages/fr/src/fr/commands/run_cmd.py:5445`)
  renders `pr-body.md`. It then reads the live PR body through the forge adapter
  and refuses on `missing_sections` (`packages/fr/src/fr/record/pr_body.py:58`)
  and on `shared_closing_keywords` (`pr_body.py:82`, which is #821, already
  shipped). It never maps a closing reference to an acceptance row.
- **Rows.** `Row` (`packages/fr/src/fr/acceptance/model.py:132`, `extra="forbid"`,
  frozen) has `verify: Literal["post-merge"] | None` (:148) and `visual`. It has no
  issue field. `origin` must be a `repo:path` ref, so it cannot hold `#n`. The
  matrix kind is at `current_version=3` (`packages/fr/src/fr/artifacts/registry.py:417`).
  The `post-merge` rows of a run come from `_post_merge_owed`
  (`pr_body.py:166`) through `rows_citing` (`packages/fr/src/fr/requirements.py:172`).
- **Evidence.** A step names its evidence in the manifest (`Step.evidence`). The
  closed set of verifiable names is `_VERIFIABLE_EVIDENCE` (`run_cmd.py:1548`), and
  `_verified_evidence` (`run_cmd.py:1743`) dispatches each name to a verifier.
  `tests` is the model to follow: a log fr can attribute, newer than the code,
  whose tree is recorded.
- **Shape resolution.** `packages/fr/src/fr/workflow/resolve.py` resolves the repo
  `docs/superpowers/workflows/` first, then `$FR_SHIPPED_WORKFLOWS_DIR`, then the
  wheel's `fr/workflows/`, then the marketplace clone. The repo override wins
  wholesale. `WorkflowManifest` (`packages/fr/src/fr/workflow/model.py:107`) is
  `extra="forbid"`.
- **Side-by-side install.** This already exists in two places:
  `scripts/install.sh:776-800` (a staged `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR`) and
  `tests/integration/test_install_bridge.py`. The autouse guard in
  `tests/conftest.py:148` protects the operator's `fr` (gh#683).
- **Labels and triage.** `packages/fr/src/fr/labels.py:95-107` is the label
  registry. `fr triage check` (`packages/fr/src/fr/triage/check.py`) has its
  unplaced, stale-dispatch and related sets. No awaiting set exists.
- **Drive conflicts.** `_update` (`packages/fr/src/fr/triage/batch_merge.py:436`)
  raises a plain `MergeStopError` whose message names the refused paths. The
  executor catches it (`packages/fr/src/fr/commands/triage_batch_cmd.py:2184-2194`)
  and de-duplicates it in memory only (`self.reported`). The pure pass
  (`packages/fr/src/fr/triage/batch_drive.py`) never sees a conflict. herdr can
  prompt an agent only inside `dispatch` (`packages/fr-herdr/src/fr_herdr/runner.py:215`,
  `herdr agent prompt <agent_name(item.id)> <brief>`). Batch events are
  `DispatchEvent`, `CancelEvent`, `CloseoutEvent` and `PostMergeEvent`
  (`packages/fr/src/fr/triage/model.py:477-523`), under judgements schema 4.

## Requirements

R1. A verification strategy is a YAML manifest. It names itself; declares `when:
pre-merge | post-merge` and `driver: agent | operator`; and gives the argv
templates that install the candidate and run one scenario. fr resolves a strategy
name in this order: the repo's `docs/superpowers/verifications/<name>.yaml`, then
`$FR_SHIPPED_VERIFICATIONS_DIR`, then the `fr` wheel's copy, then the marketplace
clone. A repo file wins wholesale.

R2. `fr verification list` shows every strategy that resolves and where it came
from. `fr verification check [<name> | --all]` refuses a malformed manifest: an
unknown key, a bad `when` or `driver`, or an unknown placeholder. A tripwire runs
the check over every shipped strategy.

R3. fr ships four strategies. `candidate` is pre-merge and agent-driven: it installs
the PR's build into a throwaway prefix and runs scripted scenarios against a fresh
fixture repo. `client-live` is pre-merge and operator-driven: it uses the same
install, but the operator drives the scenario inside a real client repo. Neither
needs a release. `prerelease` is pre-merge and operator-driven: it installs from an
on-demand pre-release of the PR branch. `live` is post-merge and operator-driven,
which is today's walk.

R4. A repo can add its own strategy, such as a staging deploy of a release
candidate, as a manifest under `docs/superpowers/verifications/`. fr documents one
example and ships none of that kind.

R5. A workflow shape may declare a default strategy (`verification: <name>`).
`fr workflow check` refuses a name that does not resolve. The shipped `fr-goal` and
`fr-goal-light` shapes declare `candidate`.

R6. A spec may carry a `## Verification` section. It names the run's strategy,
which defaults from the shape, and may override the strategy for individual rows.
A row whose effective strategy is post-merge must give a one-line reason why no
pre-merge strategy applies. fr-brainstorming asks for the strategy as a standing
question, and spec-review checks the reasons.

R7. An acceptance row's `verify:` field names a strategy. On migration, an existing
`verify: post-merge` becomes `verify: live`. A row's effective strategy is its own
`verify:` if set, otherwise its run spec's `## Verification` strategy. A row with
neither has no strategy, which is how every row behaves today.

R8. A candidate install never touches the operator's install. It goes into a fresh
temporary prefix through the repo's install contract: an executable
`.fr/candidate-install <prefix> <source>`, where `<source>` is a worktree path or a
git `URL@ref`. A repo without the contract cannot use `candidate`, `client-live` or
`prerelease`, and fr says so by name.

R9. `fr verification walk --run <run-id>` runs the run's pre-merge strategy. It
always runs a baseline smoke: install, the installed tool's version, and one command
in a fresh fixture repo. It then runs the scenario of each row the run's spec cites
whose effective strategy is that one. The log it writes outside the repo records
the code tree, the strategy, harness, model, and each scenario's exit status. The
command exits non-zero when any step fails. `--client <path>` runs the scenarios
with that client repo as their working directory, for `client-live`.

R10. A row may name its scenario (`scenario: <repo-relative path>`). A row whose
effective strategy is agent-driven and pre-merge, and that has no scenario, is
refused at deliver by name.

R11. `deliver` owes a `walk` evidence, verified the way `tests` is: a log written by
`fr verification walk`, covering HEAD's code tree, all steps passing, smoke
included, and every agent-driven pre-merge row of the run covered. The evidence is
owed only when the run's spec chooses an agent-driven pre-merge strategy for the run
or any of its rows. Otherwise `walk: none` is accepted, and a run with no
`## Verification` section behaves as it does today.

R12. The rendered PR body gains a `## Pre-merge verification owed` section. It lists
each operator-driven pre-merge row of the run with the exact `fr verification walk`
command, and a Ready-checklist line that the operator ticks after the walk. `deliver`
does not wait for that walk. `## Post-merge verification owed` lists each row
together with its post-merge reason.

R13. An acceptance row may cite the issues whose promise it carries:
`issues: [<owner>/<repo>#<n>]`. `fr acceptance add` and `set-status` accept
`--issue`.

R14. A row records its walks: `walks: [{strategy, harness, model, outcome: pass |
fail, at, evidence}]`. It may also name the harnesses its promise covers:
`harnesses: [...]`. `fr acceptance set-status --walk` appends a walk and requires
`--harness`, `--model` and `--strategy`. A row is walk-verified once it has a
passing walk on every harness it names, or on any one harness if it names none.

R15. `deliver` refuses a live PR body that closes, fixes or resolves an issue cited
by a row whose effective strategy is post-merge and that is not yet walk-verified.
The refusal names the line and prints the fix, `Refs <ref>`. This check reads only
the body `deliver` already fetches and makes no other forge calls.

R16. Once a recorded walk makes a row walk-verified, `set-status` prints each cited
issue that no other unverified row still holds. For each, it prints the forge's
command to close the issue and remove `fr:awaiting-live`. Under `tracking: none` it
prints nothing. fr never closes the issue itself.

R17. `fr:awaiting-live` joins fr's label registry. The post-merge close-out brief
prints, for each issue the run's PR turned into `Refs` because its row awaits a
walk, the command to add that label.

R18. `fr triage check` lists an `awaiting-live` set: open issues carrying the label.
These issues are not ranked or proposed as work. The board shows them separately,
and they are never reported as unplaced.

R19. A real merge conflict in drive is structured: the conflicted batch, its head,
and the paths merge refused to resolve.

R20. When drive hits a real conflict, it records a `conflict` event on the batch and
hands the conflict back. If the batch's session is live, drive sends the brief to
that session. If the session is gone, drive starts a fresh session on the batch's
existing branch through the batch's runner. The brief tells the session to merge
`origin/main` without rebasing or force-pushing, resolve the named paths,
regenerate generated mirrors instead of hand-resolving them, run the suite, and
push.

R21. Drive hands back at most once per batch head, and this holds across driver
restarts, because the persisted events decide it. Within one pass, a conflicted
batch that shares a refused path with an earlier conflicted batch in merge order
waits behind it and is not handed back.

R22. After 2 hand-backs on a batch with no merge between them, drive does not hand
back the next conflict. The batch then appears under "needs you" as a merge
conflict.

R23. A herdr runner can send text to a live session it dispatched, through a new
runner capability. A runner without that capability always takes the fresh-session
path.

R24. A pre-release of a PR branch can be cut on demand, either by
`fr verification prerelease --branch <b>` or by dispatching the workflow by hand. It
tags the branch head as `rc/<branch-slug>/<sha12>` and publishes a GitHub
pre-release. It edits no version surface and pushes nothing to `main`. On a
non-GitHub forge the command refuses with `UnsupportedForgeOperation`.

R25. super-fr itself carries the install contract and scenario scripts for this
PR's rows. This PR is verified by its own `candidate` walk before merge. Only the
live herdr hand-back remains a post-merge `live` row.

## Design

### A. The strategy vocabulary (R1–R5)

A new package, `packages/fr/src/fr/verification/`, mirrors `fr/workflow/`:

- `model.py`: `StrategyManifest` (`extra="forbid"`) with the fields `verification:
  <name>`, `schema: 1`, `description`, `when: pre-merge|post-merge`, `driver:
  agent|operator`, `install: <argv template> | null`, `scenario: <argv template> |
  null`, `source: worktree | prerelease | none`, and `notes`. Placeholders form a
  closed set: `{repo}`, `{worktree}`, `{prefix}`, `{bin}`, `{fixture}`, `{client}`,
  `{scenario}`, `{source}`. `parse_strategy` refuses an unknown one.
- `resolve.py`: the same four-step order as `workflow/resolve.py`. The shared
  directory-walking logic is factored out, not copied. It uses
  `docs/superpowers/verifications/`, `$FR_SHIPPED_VERIFICATIONS_DIR`, the wheel's
  `fr/verifications/` and `plugins/super-fr/verifications/`. Shipped manifests live
  in the wheel (the source of truth), and the plugin directory is a byte-identical
  copy. A tripwire keeps the two identical, as it already does for workflows.
- `check.py` and CLI `commands/verification_cmd.py`: `list`, `check`, `walk`,
  `prerelease`. `verification` joins `fr.artifacts.trigger.READ_ONLY_COMMANDS` only
  for `list` and `check`. `walk` writes nothing in the repo, but `prerelease`
  writes to the forge, so the group is **not** exempt as a whole. The exemption is
  decided per command, the way the gate already distinguishes subcommands.
- The four shipped manifests:

  | name | when | driver | install | scenario cwd |
  |---|---|---|---|---|
  | `candidate` | pre-merge | agent | `.fr/candidate-install {prefix} {worktree}` | `{fixture}` |
  | `client-live` | pre-merge | operator | same | `{client}` |
  | `prerelease` | pre-merge | operator | `.fr/candidate-install {prefix} {source}` (source = the rc tag) | `{client}` or `{fixture}` |
  | `live` | post-merge | operator | none | none (the operator runs the released build) |

- `WorkflowManifest` gains `verification: str | None = None`. Both shipped shapes
  set `candidate`. A repo override that predates this key still parses, because the
  key is optional. A repo override that *carries* the key is unreadable by an older
  `fr`. That is acceptable: shapes are not a registered artifact kind, and the shape
  and its `fr` ship together.
- The docs explainer for authors (`packages/fr/src/fr/verifications/README.md`)
  includes a repo-authored `staging` example (R4).

### B. Spec `## Verification` and the effective strategy (R6, R7, R10)

The parser, `fr/verification/spec_section.py`, reads one section in this fixed
grammar:

```
## Verification

strategy: candidate
- <row-id>: live — <reason>
- <row-id>: client-live
```

The `strategy:` line is optional and defaults to the shape's `verification`. Row
lines are overrides, and a post-merge override must carry the text after `—`. The
effective strategy of a row is `row.verify`, then the spec override, then the spec
strategy, then none. A malformed section is refused at `plan-review`, because
`fr plan self-review` reads the spec. A post-merge row without a reason is a
self-review failure, named.

`Row` widens `verify` to a `StrictStr` strategy name. It gains `scenario: StrictStr
| None`, `issues: tuple[StrictStr, ...] = ()`, `harnesses: tuple[StrictStr, ...] =
()` and `walks: tuple[Walk, ...] = ()`, where `Walk` is frozen with the fields
strategy, harness, model, outcome, at and evidence. This is one shape change, so
the matrix kind moves `3 → 4` with a registered `SchemaMigration`
(`fr/artifacts/matrix_strategies.py`) that rewrites `verify: post-merge` to
`verify: live`. That is a body rewrite, so it follows the artifact-versioning rule
in full:

- It builds the new body in memory and writes once through `write_text_atomic`.
- It recognises a body already wholly in v4.
- It reads the old file only through a frozen `MatrixV3` reader
  (`fr/acceptance/legacy.py`, vocabularies inlined, source pinned), never the live
  `Row`: the live `verify` means "a strategy that resolves", so a v3 `post-merge`
  would read as an unknown strategy instead of the value to rename.

`fr validate artifacts` checks that every `verify` names a strategy that resolves,
and that `issues` entries match `owner/repo#n`. `fr migrate artifacts --yes` runs
over this repo's own matrix in the same PR.

### C. The walk and the `walk` evidence (R8, R9, R11)

`fr verification walk --run <id> [--strategy <s>] [--client <path>] [--row <id>…]`:

1. It resolves the run's spec, the effective strategy per cited row, and the
   strategy manifest. It refuses when the repo has no `.fr/candidate-install` and
   the strategy needs one (R8).
2. It creates `prefix = mkdtemp()`, outside the repo and outside
   `<run>.records/`. It runs the install template, and every child environment
   gets `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` under that prefix. After the install it
   asserts that the operator's resolved `fr`, meaning the `FR_HARNESS_FR` pin or
   PATH's `fr`, is byte-for-byte the same target as before (the gh#683 class).
3. Smoke: `{bin}/<tool> --version`, then a fresh `git init` fixture under the
   prefix and `{bin}/<tool> status` in it. super-fr's contract prints the tool
   name.
4. For each covered row, it runs its `scenario` script with `PATH={bin}:$PATH`,
   cwd `{fixture}` (a fresh copy per row) or `{client}`, and env
   `FR_WALK_PREFIX={prefix}`.
5. It writes `~/.cache/fr/walks/<run-id>/<UTC>.log`. A YAML header holds `fr-walk:
   1`, run, strategy, `code_tree` (from the same helper the `tests` witness uses),
   harness, model (the `fr` harness detection, overridable by flag), and steps
   (name, exit code, seconds). Each step's output follows. Exit status is 0 only if
   every step passed.

`walk` joins `_VERIFIABLE_EVIDENCE`, and both shipped shapes' `deliver` lists it.
Its verifier:

- **Not owed:** the run's spec chooses no agent-driven pre-merge strategy for the
  run or any row. In that case `walk: none` is accepted, and so is omission.
- **Owed:** the log parses as a `fr-walk: 1` header, its `code_tree` equals HEAD's
  code tree (the same tree definition as `tests: reuse`), every step passed, the
  smoke is present, and every owed row id appears. Anything else is refused, naming
  the missing row or the stale tree.

### D. PR body (R12, R15)

`render_pr_body` adds `## Pre-merge verification owed` to `REQUIRED_SECTIONS`, with
one line per operator-driven pre-merge row, including the command, or `None.`.
`## Post-merge verification owed` now selects rows by *effective strategy is
post-merge*, which includes legacy `verify: live`, and appends each row's reason.

`_deliver_pr_gate` gains `premature_closes(live_body, matrix)`. It reuses the
keyword→reference pairing behind `shared_closing_keywords`, factored out as
`closing_refs(body) -> list[(line, keyword, ref)]` with the same code-fence,
inline-code and fr-marker skipping. Each ref is normalised to `owner/repo#n`, where
a bare `#n` takes the run repo's slug from the forge adapter. The function then
looks up matrix rows citing that issue whose effective strategy is post-merge and
that are not walk-verified. Each hit is refused with the line and `Refs <ref>`.

### E. Walk recording and the close command (R13, R14, R16)

`fr acceptance set-status` gains these flags:

- `--issue <ref>`, repeatable, which adds to `issues`.
- `--walk <log-or-note> --harness <h> --model <m> --strategy <s> [--walk-outcome
  pass|fail]`, which appends a `Walk` with `at` set to the current time. `--notes`
  is still required.

`fr acceptance add` takes `--issue`, `--scenario`, `--harness` and `--verify
<strategy>`. After writing, set-status computes the issues that every row citing
them now walk-verifies. For each, it prints the tracker's close command, which
removes `fr:awaiting-live` and adds a comment linking the walk evidence, using the
same forge command renderer `deliver`'s refusals use. Under `tracking: none` it
prints nothing.

### F. Awaiting-live in triage (R17, R18)

`FR_AWAITING_LIVE = LabelDef("fr:awaiting-live", …)` is added to `labels.py`. The
close-out brief (`fr pickup --run`) adds one command per issue in the run's PR body
that is referenced with `Refs` and cited by a not-yet-walk-verified post-merge row.
The brief reads the PR body through the adapter, as `deliver` does.

In triage, `CheckResult.awaiting_live` lists open issues carrying the label.
`views.next_up`/`preselected_wave` and the unranked and unplaced sets exclude them.
The board renders them in their own collapsed group. `collect` already stores
labels, so `facts.json` keeps its schema.

### G. Conflict hand-back (R19–R23)

- `batch_merge.MergeConflictError(MergeStopError)` carries `batch`, `head` and
  `paths` (refused). `_update` raises it, and its message is unchanged.
- `ConflictEvent` (`kind: conflict`; `at`, `head`, `paths`, `delivered: session |
  fresh | held`, `handle`) joins the `BatchEvent` union. Judgements schema `4 → 5`:
  fr reads 1–5 and writes 5. `conflict` is gated to schema ≥5, the way
  `SCHEMA_3_EVENTS` is gated.
- The pure pass does not change its contract: conflicts are still discovered by the
  executor. A new pure helper, `batch_drive.conflict_decision(batch_events, head,
  paths, earlier_conflicts) -> handback | skip-same-head | wait-behind <batch> |
  needs-you`, decides each conflict. The executor calls it with the conflicts it has
  already seen in this pass's train (R21 ordering). Counting rule: the conflict
  events since the batch's last `dispatch` or merge. With a `held` event counted,
  2 → needs-you.
- Delivery: `fr_dispatch.protocols.SessionMessenger` with `message(item, text) ->
  None`. `HerdrRunner` implements it as `herdr agent prompt <agent_name(item.id)>
  <text>`, and uses it only when `session_statuses` says the item is live
  (working, blocked or idle). Otherwise the executor builds a run-unit item
  `<repo>/run/conflict-<id>-<n>` with `payload.kind: conflict`, the batch's branch,
  its harness and model, and checkout set to the batch worktree. It dispatches that
  item through the batch's runner, like a close-out.
- `views.needs_you` gains `merge-conflict` (from the latest `conflict` event with
  `delivered: held`), and `NEED_LABELS` gains its label. The executor's `stopped
  again at` line stays as the log line for skipped repeats.
- The brief (`batch_dispatch.conflict_brief`) names the batch, the PR, the head, the
  refused paths and the five steps of R20, and the repo's mirror-sync commands when
  `.fr/triage.yaml` declares them. A new optional key is added: `mirrors: [argv…]`.

### H. On-demand pre-release (R24)

A new `.github/workflows/prerelease.yml`, triggered by `workflow_dispatch` with an
input `branch`, checks out that branch and tags `rc/<branch-slug>/<sha12>`. It
creates a GitHub pre-release with `gh release create --prerelease --target <sha>`,
with notes naming the PR. It does no version bump and makes no commit. It is added
to `ci-budget.yml`'s watch list.

`fr verification prerelease --branch <b>` triggers it through `GhClient` (new
`dispatch_workflow`). glab and tea raise `UnsupportedForgeOperation`. The command
then prints the tag the `prerelease` strategy installs from (`{source} =
git+<remote>@<tag>`).

### I. Skills, docs, dogfood (R6, R25)

- **fr-brainstorming / fr-goal:** a standing verification question, the spec
  `## Verification` section, and the `deliver` walk step (fr-goal §8). Change "the
  post-merge Test Plan" so that the Test Plan is reserved for post-merge strategies.
- **fr-acceptance:** `--issue`, `--walk`, walk-verified, and the close command.
- **fr-triage:** the awaiting-live set and conflict hand-back in "The driver".
- Regenerate both mirror generators. Update the `01-fr-goal` explainer and re-render
  it per `explainers-currency.md`, because the minor bump and the deliver surface
  both change.
- **super-fr:** `.fr/candidate-install` (`uv tool install --force --from
  <source>/packages/fr fr`, with `<source>` a path or `git+…@ref#subdirectory=`
  handled), and `tests/scenarios/*.sh` for this PR's candidate rows. The scenario
  scripts are also run by a pytest integration test in CI, so they cannot rot.

## Risks

- **Matrix rewrite.** This is the first body-rewriting matrix hop. The mitigation is
  a frozen reader, an atomic write, a test that every hop is asserted, and running
  it on this repo's 386 rows in the PR.
- **`deliver` evidence added to shipped shapes drifts in-flight runs.** Evidence
  lists are part of the manifest, but `_check_step_drift` keys on step ids, so
  in-flight runs see the new evidence without drifting. For a run with no
  `## Verification` section the evidence is "not owed", so nothing strands.
- **The pass-local ordering in R21 is per pass.** Two conflicts discovered in
  different passes on overlapping paths both get handed back. That is accepted,
  because the second sees the first's fix only after it lands.

## Test Plan (pre-merge: this PR's own `candidate` walk)

1. `fr verification walk --run <this run>` on the delivered tree: smoke plus the
   scenarios for rows `verification-strategy-resolution`, `candidate-walk-gates-deliver`,
   `closes-refused-while-awaiting-walk` and `walk-recording-prints-close`. The log
   is cited as `walk` evidence at deliver.
2. Post-merge (`live`, reason: it needs a real conflicted batch in a live herdr
   session): on the next drive wave with a real conflict, the batch session receives
   the brief, resolves it and pushes. A second conflict produces one more hand-back,
   and a third lands under needs-you.

## Verification

strategy: candidate
- triage-drive-conflict-handback-live: live — needs a real conflicted batch in a live herdr session; no fixture reproduces herdr's pane
- prerelease-on-demand: live — GitHub dispatches a `workflow_dispatch` workflow only once its file is on the default branch, so the first real pre-release can only be cut after merge
