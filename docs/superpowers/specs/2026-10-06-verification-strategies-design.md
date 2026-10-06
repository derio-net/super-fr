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
pre-merge | post-merge` and `driver: agent | operator`; and gives the argv templates
that install the candidate and run one scenario. fr resolves a strategy name in this
order: the repo's `docs/superpowers/verifications/<name>.yaml`, then
`$FR_SHIPPED_VERIFICATIONS_DIR`, then the `fr` wheel's copy, then the marketplace
clone. A repo file wins wholesale.

R2. `fr verification list` shows every strategy that resolves and where it came
from. `fr verification check [<name> | --all]` refuses a malformed manifest: an
unknown key, a bad `when` or `driver`, or an unknown placeholder. A tripwire runs
the check over every shipped strategy.

R3. fr ships four strategies. `candidate` is pre-merge and agent-driven: it installs
the PR's build into a throwaway prefix and runs scripted scenarios against a fresh
fixture repo. `client-live` is pre-merge and operator-driven: it uses the same
install, and the operator drives the scenario inside a real client repo. Neither
needs a release. `prerelease` is pre-merge and operator-driven: it installs from an
on-demand pre-release of the PR branch. `live` is post-merge and operator-driven: it
is today's walk.

R4. A repo can add its own strategy, such as a staging deploy of a release
candidate, as a manifest under `docs/superpowers/verifications/`. fr documents one
such example and ships none of that kind.

R5. A workflow shape may declare a default strategy (`verification: <name>`).
`fr workflow check` refuses a name that does not resolve. The shipped `fr-goal` and
`fr-goal-light` shapes declare `candidate`.

R6. A spec may carry a `## Verification` section. It names the run's strategy, which
defaults from the shape, and may override the strategy for individual rows, using a
strategy name or the reserved word `none`. A row of the run whose effective strategy
is post-merge or `none` needs a one-line reason in that section. For post-merge, the
reason says why no pre-merge strategy applies. For `none`, it says what verifies the
row instead. fr-brainstorming asks for the strategy as a standing question,
spec-review reads the reasons, and `fr plan self-review` refuses a missing reason.

R7. An acceptance row's `verify:` field names a strategy or `none`. On migration, an
existing `verify: post-merge` becomes `verify: live`. A row's effective strategy is
the first of these that is set: its own `verify:`, the spec's override line for that
row, the spec's `strategy:`, the shape's default. A row whose run has no
`## Verification` section and which has no `verify:` has no strategy. That is how
every row behaves today.

R8. A candidate install never touches the operator's install. It goes into a fresh
temporary prefix through the repo's install contract: an executable
`.fr/candidate-install <prefix> <source>`, where `<source>` is a worktree path or a
git `URL@ref`. A repo without the contract cannot use `candidate`, `client-live` or
`prerelease`, and fr says so by name.

R9. `fr verification walk --run <run-id> --model <m>` runs the run's pre-merge
strategy. It always runs a baseline smoke: install, the installed tool's version, and
one command in a fresh fixture repo. It then runs the scenario of each row the run's
spec cites whose effective strategy is that one. The log it writes outside the repo
records the code tree, the strategy, the harness, the model, and each step's exit
status. The command exits non-zero when any step fails. `--client <path>` runs the
scenarios with that client repo as their working directory, for `client-live`.

R10. A row may name its scenario (`scenario: <repo-relative path>`). A row whose
effective strategy is agent-driven and pre-merge, and that has no scenario, is
refused at deliver by name.

R11. `deliver` owes a `walk` evidence, verified the way `tests` is. It must be a log
written by `fr verification walk`, covering HEAD's code tree, with every step passing,
the smoke included, and every agent-driven pre-merge row of the run covered. The
evidence is owed only when the run's spec gives the run, or any of its rows, an
agent-driven pre-merge strategy. When it is not owed, omitting it or saying
`walk: none` is accepted. A run with no `## Verification` section behaves as it does
today, and so does an in-flight run.

R12. The rendered PR body gains a `## Pre-merge verification owed` section. It lists
each operator-driven pre-merge row of the run with the exact `fr verification walk`
command, and a Ready-checklist line that the operator ticks after the walk. `deliver`
does not wait for that walk. `## Post-merge verification owed` lists each
post-merge row with its reason, or `no reason recorded (legacy)` for a row whose
reason no spec states.

R13. An acceptance row may cite the issues whose promise it carries:
`issues: [<owner>/<repo>#<n>]`. `fr acceptance add` and `set-status` accept
`--issue`.

R14. A row records its walks: `walks: [{strategy, harness, model, outcome: pass |
fail, at, evidence}]`. It may also name the harnesses its promise covers:
`harnesses: [...]`. `fr acceptance set-status --walk` appends a walk and requires
`--harness`, `--model` and `--strategy`. A row is walk-verified once it has a passing
walk on every harness it names, or on any one harness if it names none.

R15. `deliver` refuses a live PR body that closes, fixes or resolves an issue cited
by a row whose effective strategy is post-merge and that is not yet walk-verified.
The refusal names the line and prints the fix, `Refs <ref>`. This check reads only
the body `deliver` already fetches and makes no other forge call.

R16. Once a recorded walk makes a row walk-verified, `set-status` finds each issue
that row cites which no other row still holds open, meaning no other row citing it
is post-merge and not yet walk-verified. For each such issue it prints the
forge-specific commands to close it and remove `fr:awaiting-live`, or the manual
steps where a forge's command line lacks one. Under `tracking: none` it prints
nothing. fr never closes the issue itself.

R17. `fr:awaiting-live` joins fr's label registry. The post-merge close-out brief
prints the command to add that label for each issue the run's PR references with
`Refs` whose row is still waiting for a walk.

R18. `fr triage check` lists an `awaiting-live` set: the open issues carrying the
label. These issues are not ranked or proposed as work. The board shows them
separately, and triage never reports them as unplaced.

R19. A real merge conflict in drive is structured: it carries the conflicted batch,
its head, and the paths merge refused to resolve.

R20. When drive hits a real conflict, it records a `conflict` event on the batch and
hands the conflict back. If the batch's session is idle, drive sends it the brief.
If no session is live, drive starts a fresh session on the batch's existing branch
through the batch's runner. If the session is working or blocked, drive sends
nothing and records nothing, and retries on a later pass. The brief tells the
session to merge `origin/main` without rebasing or force-pushing, resolve the named
paths, regenerate generated mirrors instead of hand-resolving them, run the suite,
and push.

R21. Drive hands back at most once per batch head, and this survives driver
restarts because the persisted events decide it. Within one pass, a conflicted batch
that shares a refused path with an earlier conflicted batch in merge order waits
behind it and is not handed back.

R22. A batch gets at most 2 hand-backs per dispatch. The next conflict, at a new
head, is not handed back. Drive records it as held, and the batch appears under
"needs you" as a merge conflict until its PR merges or the batch is dispatched or
cancelled again.

R23. A runner may implement an optional session-messaging protocol to send text to a
session it dispatched. herdr implements it. A runner without it always takes the
fresh-session path.

R24. A pre-release of a branch can be cut on demand with
`fr verification prerelease --branch <b>` or a hand dispatch of the workflow. It tags
the branch head `rc/<branch-slug>/<sha12>` and publishes a GitHub pre-release. It
edits no version surface and pushes nothing to `main`. On a non-GitHub forge the
command refuses with `UnsupportedForgeOperation`.

R25. super-fr itself carries the install contract and scenario scripts for this PR's
candidate rows. This PR is verified by its own `candidate` walk before merge. Only
behaviour that cannot run before merge stays post-merge `live`, each with its reason:
the live herdr hand-back, and the first real dispatch of the pre-release workflow.

## Design

### A. The strategy vocabulary (R1–R5)

A new package, `packages/fr/src/fr/verification/`, mirrors `fr/workflow/`:

- `model.py`: `StrategyManifest` (`extra="forbid"`) with the fields
  `verification: <name>`, `schema: 1`, `description`, `when: pre-merge|post-merge`,
  `driver: agent|operator`, `install: <argv template> | null`,
  `scenario: <argv template> | null`, `source: worktree | prerelease | none`, and
  `notes`. Placeholders are a closed set: `{repo}`, `{worktree}`, `{prefix}`, `{bin}`,
  `{fixture}`, `{client}`, `{scenario}`, `{source}`. `parse_strategy` refuses any
  other placeholder. `none` is reserved: no manifest may take that name.
- `resolve.py`: the same four-step order as `workflow/resolve.py`. The shared
  directory walk is factored out, not copied. The four places are
  `docs/superpowers/verifications/`, `$FR_SHIPPED_VERIFICATIONS_DIR`, the wheel's
  `fr/verifications/`, and `plugins/super-fr/verifications/`. The direction follows
  workflows (`packages/fr/src/fr/workflows/README.md`): the plugin directory is
  canonical, and the wheel copy is generated and guarded by a byte-identity
  tripwire.
- `check.py` and the CLI `commands/verification_cmd.py`: `list`, `check`, `walk`,
  `prerelease`. The group stays **under** the migration gate as a whole.
  `fr.artifacts.trigger` exempts top-level command names only (`trigger.py:82-92`,
  `:223`), and `walk` reads the matrix with the live parser, so it must not run over
  a stale one.
- The four shipped manifests:

  | name | when | driver | install | scenario cwd |
  |---|---|---|---|---|
  | `candidate` | pre-merge | agent | `.fr/candidate-install {prefix} {worktree}` | `{fixture}` |
  | `client-live` | pre-merge | operator | same | `{client}` |
  | `prerelease` | pre-merge | operator | `.fr/candidate-install {prefix} {source}` (source = the rc tag) | `{client}` or `{fixture}` |
  | `live` | post-merge | operator | none | none (the operator runs the released build) |

- `WorkflowManifest` gains `verification: str | None = None`. Both shipped shapes set
  `candidate`. A repo override that predates this key still parses, because the key
  is optional. A repo override that *carries* the key is unreadable by an older `fr`.
  That is acceptable: shapes are not a registered artifact kind
  (`registry.py:345-481`), and a shape ships with its `fr`.
- Author docs, including the repo-authored `staging` example (R4), live in
  `docs/verification-strategies.md` and the fr-acceptance skill. They stay outside
  both manifest directories, so the mirror tripwire never treats them as generated.

### B. Spec `## Verification`, the effective strategy, and the shape changes (R6, R7, R10, R13, R14)

`fr/verification/spec_section.py` parses one section in this fixed grammar:

```
## Verification

strategy: candidate
- <row-id>: <strategy|none> — <reason>
```

The `strategy:` line is optional and defaults to the shape's `verification`. The
reason after `—` is required when the line's strategy is post-merge or `none`, and
optional otherwise. A line may also name a row whose matrix `verify:` already says
post-merge, only to give it a reason. The effective strategy is resolved by
`fr/verification/effective.py` (`effective_strategy(row, section, shape)` and
`is_post_merge(...)`), in the precedence R7 states. Every consumer listed below calls
those two functions, and none compares strings itself.

`fr plan self-review` (which already reads the spec) refuses three things, each by
name: a malformed section, a post-merge or `none` row of the run with no reason, and
an agent pre-merge row with no `scenario`.

Consumers of the old `verify == "post-merge"` test that switch to `is_post_merge`:

- `pr_body._post_merge_owed` (`pr_body.py:166-184`);
- `run/visual.py:67`, so rows migrated to `live` do not start owing visual evidence;
- `acceptance_cmd.py:430-432` (`--verify` accepts any resolving strategy name or
  `none`);
- the hint in `record/template.py:109`.

**Matrix kind 3 → 4.** `Row` widens `verify` to a `StrictStr`. It gains
`scenario: StrictStr | None`, `issues: tuple[StrictStr, ...] = ()`,
`harnesses: tuple[StrictStr, ...] = ()`, and `walks: tuple[Walk, ...] = ()`. `Walk` is
frozen and holds strategy, harness, model, outcome, at and evidence. The registered
`SchemaMigration` (`fr/artifacts/matrix_strategies.py`) rewrites `verify: post-merge`
to `verify: live`. That is a body rewrite, so the full artifact-versioning rule
applies:

- A frozen `MatrixV3` reader (`fr/acceptance/legacy.py`, vocabularies inlined,
  source pinned) is a superset of matrix versions 1–3. **Every** matrix hop reads
  through it, which means `guard_matrix` (`matrix_verify.py:36-49`, shared by the
  2 → 3 hop in `matrix_visual.py:22-28`) is re-pointed at it. Otherwise a v2 matrix
  would be refused at its first hop by the live model, whose `verify` now has to
  resolve.
- The migration builds the new body in memory and writes it once through
  `write_text_atomic`. A file it cannot convert is left byte-identical and reported.
- It recognises a body that is already wholly v4 (the crash window).
- A test asserts the hop chain `[2, 3, 4]`.

`fr validate artifacts` checks that each `verify` resolves or is `none`, that each
`issues` entry matches `owner/repo#n`, and that each walk's outcome is in its
vocabulary. `fr migrate artifacts --yes` runs over this repo's own matrix in the
same PR.

**Record kind 7 → 8.** `AcceptanceItem` (`record/model.py:157-175`) is how
`fr acceptance add/set-status` and every step's `acceptance:` section reach the
matrix. It widens `verify` the same way and gains `scenario`, `issues`, `harnesses`
and `walk` (one walk to append). It is `_Strict`, so this is a record shape change:
the stamp moves to 8. A `RecordV7` frozen reader is added beside the existing record
legacy model (`record/legacy.py`). A registered migration stamps live records, which
are transient and rewritten only by stamp, since every v7 record is a valid v8
record once read through the frozen model. The record validator covers the new
fields.

### C. The walk and the `walk` evidence (R8, R9, R11)

`fr verification walk --run <id> --model <m> [--harness <h>] [--strategy <s>]
[--client <path>] [--row <id>…]`:

1. It resolves the run's spec, the effective strategy of each row the spec cites,
   and the strategy manifest. It refuses when the repo has no `.fr/candidate-install`
   and the strategy needs one (R8).
2. It creates `prefix = mkdtemp()` outside the repo and outside `<run>.records/`, and
   runs the install template. Every child process gets `UV_TOOL_DIR` and
   `UV_TOOL_BIN_DIR` under that prefix. After the install, it asserts that the
   operator's resolved `fr` (the `FR_HARNESS_FR` pin, else the `fr` on PATH) points at
   the same target as before (gh#683's class).
3. Smoke: `{bin}/<tool> --version`, then a fresh `git init` fixture under the prefix,
   and `{bin}/<tool> status` inside it. The install contract prints the tool name on
   its last line.
4. It runs each covered row's `scenario` with `PATH={bin}:$PATH`, with a fresh copy
   of `{fixture}` per row (or `{client}`) as the working directory, and
   `FR_WALK_PREFIX={prefix}` in the environment.
5. It writes `~/.cache/fr/walks/<run-id>/<UTC>.log`. The YAML header holds
   `fr-walk: 1`, the run, the strategy, `code_tree` (the helper in
   `fr/run/code_tree.py` that the `tests` witness uses), the harness
   (`fr.harness.detect.detect_harness`, overridable by `--harness`), the model
   (`--model`, required, because fr cannot detect a model), and the steps (name,
   exit code, seconds). Each step's output follows the header. The exit status is 0
   only if every step passed.

`walk` joins `_VERIFIABLE_EVIDENCE` and `_OFFERED_EVIDENCE`, and both shipped
shapes' `deliver` lists it. `_verified_evidence` rule 2 (`run_cmd.py:1773-1776`)
refuses a declared obligation that was not offered. `walk` is the one exception:
the owed predicate below runs **before** that rule, and when it says not owed, an
absent `walk` is satisfied. This is how an in-flight run, or a run with no
`## Verification` section, delivers unchanged.

- **Not owed:** the run's spec gives no row an agent-driven pre-merge strategy, and
  sets none for the run either. `walk: none` is accepted, and so is omitting it.
- **Owed:** the log's header parses as `fr-walk: 1`; its `code_tree` equals HEAD's
  code tree (the same definition `tests: reuse` uses); every step passed; the smoke
  is present; and every owed row id appears. Anything else is refused, and the
  refusal names the missing row or the stale tree.

### D. PR body (R12, R15)

`render_pr_body` adds `## Pre-merge verification owed` to `REQUIRED_SECTIONS`. The
section has one line per operator-driven pre-merge row, each with its `walk` command,
or `None.`. `## Post-merge verification owed` selects rows with `is_post_merge`. It
appends each row's reason from the spec section, or `no reason recorded (legacy)`.

`_deliver_pr_gate` gains `premature_closes(live_body, matrix, identity)`. It factors
the keyword→reference pairing out of `shared_closing_keywords` (`pr_body.py:82`) as
`closing_refs(body) -> list[(line, keyword, ref)]`, keeping the same code-fence,
inline-code and fr-marker skipping. Each reference is normalised to `owner/repo#n`:

- a bare `#n` takes the repo identity from `acceptance/check.py`'s `resolve_identity`
  (matrix `org`/`repo`, then the git remote), so no forge call is made;
- an `owner/repo#n` is kept as written;
- an issue URL `https://<host>/<owner>/<repo>/issues/<n>` (or `/-/issues/<n>`)
  becomes `owner/repo#n`.

Rows citing that issue that are post-merge and not walk-verified are refused, with
the offending line and `Refs <ref>`.

### E. Walk recording and the close command (R13, R14, R16)

`fr acceptance set-status` gains two forms:

- `--issue <ref>` (repeatable) adds to `issues`.
- `--walk <log-or-note> --harness <h> --model <m> --strategy <s>
  [--walk-outcome pass|fail]` appends a `Walk`, with `at` set to the current time.
  `--notes` is still required.

`fr acceptance add` takes `--issue`, `--scenario`, `--harness` and
`--verify <strategy|none>`. After a walk is recorded, set-status computes R16's issue
set and prints, for each issue, the close and unlabel commands from the forge command
table. `hostclient.py`'s `PR_COMMANDS` (`hostclient.py:61-70`) is widened into a
per-backend command table that gains `issue-close` (with a comment linking the walk
evidence) and `issue-unlabel`:

- `gh issue close <n> --comment …` and `gh issue edit <n> --remove-label …`;
- `glab issue close <n>` and `glab issue update <n> --unlabel …`;
- `tea issues close <n>`. tea has no unlabel command, so fr prints a one-line manual
  instruction instead.

Under `tracking: none`, set-status prints nothing.

### F. Awaiting-live in triage (R17, R18)

`labels.py` gains `FR_AWAITING_LIVE = LabelDef("fr:awaiting-live", …)`. The close-out
brief (`fr/run/closeout.py`, printed by `fr pickup --run`) adds one label command per
issue that the run's PR body references with `Refs` and that is cited by a
post-merge row not yet walk-verified. It reads the PR body through the adapter, just
as `deliver` does. The label command comes from the same table (`issue-label`).

In triage, `CheckResult.awaiting_live` lists the open issues carrying the label. The
unranked and unplaced sets, `views.next_up` and `preselected_wave` all exclude them.
The board renders them in a collapsed group of their own. `collect` already stores
labels (`triage/model.py:207`), so `facts.json` keeps its schema.

### G. Conflict hand-back (R19–R23)

- `batch_merge.MergeConflictError(MergeStopError)` carries `batch`, `head` and
  `paths` (the refused ones). `_update` raises it, and its message is unchanged.
- `ConflictEvent` (`kind: conflict`; `at`, `head`, `paths`,
  `delivered: session | fresh | held`, `handle`) joins the `BatchEvent` union.
  Judgements move from schema 4 to 5: fr reads 1–5 and writes 5. `conflict` is gated
  to schema 5 or later, the way `SCHEMA_3_EVENTS` is gated.
- **The decision is pure.** `batch_drive.conflict_decision(events, head, paths,
  earlier_in_pass)` returns one of four outcomes:
  - `skip`: a `conflict` event already exists for this head;
  - `wait-behind <batch>`: a refused path is shared with a conflict met earlier in
    this pass, in train order;
  - `held`: two `session|fresh` hand-backs have already been made since the batch's
    latest `dispatch` event. Held events never count toward the bound;
  - otherwise `handback`.

  The executor collects `earlier_in_pass` while it walks a repo's train.
- **Delivery.** `fr_dispatch.protocols.SessionMessenger` is an optional protocol,
  beside `SessionInspector`. It is not a `Runner.capabilities` entry, so
  `CAPABILITIES` is unchanged. Its single method is `message(item, text) -> None`.
  The target is the latest `fresh` conflict item if one exists, otherwise the batch's
  dispatch item.
  - That target's `session_statuses` is `idle`: drive messages it through
    `herdr agent prompt <agent_name(item.id)> <text>` and records
    `delivered: session`.
  - `working` or `blocked`: drive does nothing this pass and writes no event. A
    blocked session may be showing a permission prompt, which the text would answer.
  - `absent`, `done`, or the runner lacks the protocol: drive dispatches a run-unit
    item `<repo>/run/conflict-<id>-<n>` (`payload.kind: conflict`, the batch's
    branch, harness and model, and the batch worktree as checkout) through the
    batch's runner, the way a close-out is started, and records `delivered: fresh`.
- **Needs you.** `views.needs_you` gains `merge-conflict` whenever the batch's
  latest `conflict` event is `held` and the batch is still open. `NEED_LABELS` gains
  its label. A merge, a cancel or a new `dispatch` clears it, because the batch is no
  longer open or a new dispatch resets the count. The executor keeps its
  `stopped again at` line for skipped repeats.
- **The brief.** `batch_dispatch.conflict_brief` names the batch, the PR, the head,
  the refused paths and the five steps in R20. When `.fr/triage.yaml` declares a new
  optional `mirrors: [argv…]` key, the brief adds the repo's mirror-sync commands
  from it.

### H. On-demand pre-release (R24)

A new workflow, `.github/workflows/prerelease.yml`, runs on `workflow_dispatch` with
an input `branch`. It checks out that branch, tags it `rc/<branch-slug>/<sha12>`, and
creates a GitHub pre-release with `gh release create --prerelease --target <sha>`,
whose notes name the PR. It does not bump a version or commit anything. It is added
to `ci-budget.yml`'s watch list. GitHub dispatches a workflow only once its file is
on the default branch, so the first real dispatch happens after this PR merges.

`fr verification prerelease --branch <b> [--dry-run]` triggers the workflow through
`GhClient`, which gains `dispatch_workflow`. glab and tea raise
`UnsupportedForgeOperation`. The command prints the tag the `prerelease` strategy
installs from (`{source} = git+<remote>@<tag>`). `--dry-run` prints the dispatch
argv without calling it, which is what this PR's own scenario checks before merge.

### I. Skills, docs, dogfood (R6, R25)

- **fr-brainstorming and fr-goal:** add a standing verification question, the spec's
  `## Verification` section, and the `deliver` walk step (fr-goal §8). A spec's
  `## Test Plan` lists every post-merge row with its reason, and pre-merge walks
  live in `## Verification`. "post-merge — operator-driven" now describes the Test
  Plan's post-merge part only.
- **fr-acceptance:** `--issue`, `--walk`, walk-verified, the close command, and the
  staging example pointer.
- **fr-triage:** the awaiting-live set, and conflict hand-back in "The driver".
- Regenerate both mirror generators. Update the `01-fr-goal` explainer and re-render
  it per `explainers-currency.md`, because the minor bump and the deliver surface
  both change.
- **super-fr's own `.fr/candidate-install`:** mirrors `install.sh`'s install,
  `fr` plus the `--with` set of every `fr.runners` package (`install.sh:94-99`,
  `:790-791`), for both a worktree source and a
  `git+<url>@<ref>#subdirectory=packages/fr` source, so the candidate matches what
  operators run.
- **`tests/scenarios/*.sh`:** one script per candidate row below. A pytest
  integration test also runs every script in CI against a throwaway install, so they
  cannot rot.
- **This PR's rows carry no `issues:`.** The operator's delivery rule requires
  `Closes` for #818, #822 and #959. R15 would refuse `Closes #959` if the post-merge
  herdr row cited it. The rule stands, so #822 is not dogfooded on this PR's own
  closing lines, and the PR body says so.

## Risks

- **Matrix rewrite.** This is the first body-rewriting matrix hop. It is mitigated
  by the frozen reader on every hop, an atomic write, the chain assertion, and
  running it on this repo's own rows in the PR.
- **In-flight runs.** `_check_step_drift` diffs step ids only (`run_cmd.py:814-861`),
  so a run that started before this change sees `walk` declared at `deliver`. The
  not-owed exception in §C makes an absent `walk` satisfied for such a run, so it
  does not strand.
- **R21's ordering is per pass.** Two conflicts on overlapping paths that are found
  in different passes are both handed back. This is accepted: the second sees the
  first's fix only after it lands.

## Test Plan

Post-merge rows only. The pre-merge walk is set out in `## Verification`.

1. `triage-drive-conflict-handback-live` (`live`). On the next drive wave with a real
   conflict, the batch session receives the brief, resolves the conflict and pushes.
   A second conflict gets one more hand-back, and a third lands under needs-you.
2. `prerelease-on-demand` (`live`). `fr verification prerelease --branch <b>` cuts an
   `rc/…` tag and a GitHub pre-release, and `main` and the version surfaces are
   untouched.

## Verification

This PR is verified by its own `candidate` walk at `deliver`
(`fr verification walk --run <run-id> --model <m>`). The walk runs the smoke plus one
scenario per candidate row: `verification-strategy-resolution`,
`shipped-verification-strategies`, `spec-verification-section`,
`walk-recording-prints-close`, `awaiting-live-triage` and
`prerelease-command-shape`. Rows that only a forge, a runner or this run itself can
exercise are `none`, and the reason names what verifies each one.

strategy: candidate
- triage-drive-conflict-handback-live: live — needs a real conflicted batch in a live herdr session; no fixture reproduces herdr's pane
- prerelease-on-demand: live — GitHub dispatches a `workflow_dispatch` workflow only once its file is on the default branch, so the first real pre-release can only be cut after merge
- candidate-walk-gates-deliver: none — this run's own deliver is the proof: it resolves only on a passing walk log
- premerge-owed-pr-section: none — needs a live PR body; unit tests over render_pr_body and the gate cover it in CI
- closes-refused-while-awaiting-walk: none — needs a live PR body; unit tests over premature_closes and _deliver_pr_gate with a fake forge cover it in CI
- triage-drive-conflict-handback: none — needs a forge and a runner; executor tests with a fake runner and a git fixture cover it in CI
- super-fr-candidate-contract: none — every walk's smoke runs the contract
