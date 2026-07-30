# Changelog

All notable user-observable changes to the `vk` toolchain. Conventions:
SemVer-ish (see [CLAUDE.md](./CLAUDE.md) for the patch / minor / major
heuristic this project uses), reverse-chronological, breaking changes
flagged with **BREAKING**.

Internal-only changes (test reorganisations, ruff/format passes, doc
typos) are not listed; consult the PR history for those.

## 3.19.0 — isolation GC works in every mode (#423)

- **`fr isolation gc` no longer refuses a mode.** host-worktree runs the same
  reconciler as devcontainer minus the docker-only steps (container discovery,
  container reap, `vsc-*` image sweep); external returns a structured
  `external`/`skipped` verdict naming the preparer as cleanup owner. Both used
  to exit 2 with no output, leaving docker-less pods and prepared containers
  with no reconciler at all. `--format json` is now useful in all three.
- **Discovery proves fr ownership.** A third source — the invoking repo's fr
  state records — finds workspaces created at a custom `--path` (previously
  invisible to gc in every mode) and state records whose worktree was removed
  out of band (now retired as `orphan`/`reaped`, so `status` stops reporting a
  phantom workspace). `git worktree list` is still never consulted: a plain
  `git worktree add` by other automation remains outside gc's reach.
- **`up`/`down` fire the opportunistic sweep in host-worktree mode** too;
  external deliberately does not.
- **`fr isolation gc --repo <path>`** for cron/agent runs, and a deleted cwd now
  exits 2 with guidance instead of raising `FileNotFoundError`.

## 3.7.0 — acceptance matrix: first-class acceptance tests (#352)

- **New `fr acceptance` CLI group.** `check` (the gate: ref resolution with
  archive-twin fallback, staleness guard, plan-linkage, workflow path-filter
  coverage; exit 2 on `failing` rows / 1 on errors / 0 with `::warning::`
  annotations), `report` (HTML, github/local link modes, `--sibling-root`),
  `status [--brief]` (terminal nag), `add` (schema- and ref-grammar-validated
  append that preserves header comments), `init` (idempotent scaffold:
  matrix + CI workflow + backfill rule + gitignore), `backfill` (agent
  work-protocol + deterministic inventory), `digest` (issue-body markdown
  with idempotence marker), and `check --added-since <ref>` (row diff for
  the PR-body "added since brainstorm" section).
- **Plan linkage.** Phase headers gain optional `acceptance: [row-ids]`;
  `fr plan self-review` errors on a Test-Plan spec with zero linked rows
  (matrix present) and on unknown ids; `fr plan edit --complete-phase`
  warns on rows left `not-implemented`; `fr status` appends an acceptance
  summary in matrix-adopting repos.
- **Nag channels.** New SessionStart hook (`fr-acceptance-nag.sh`) injects
  capped open-debt context; the scaffolded workflow upserts a weekly
  "Acceptance debt" issue and closes it at zero.
- **Skills.** New `fr-acceptance` (backfill driver, honest-status
  calibration); fr-brainstorming / fr-plan / fr-execute / fr-goal /
  fr-progress carry their pipeline duties (rows born at brainstorm with
  defenses, linked at planning, flipped at execution, debt surfaced at
  delivery).
- **Dog food.** super-fr's own matrix ships with 15 backfilled rows
  (11 ci, 4 skipped) covering every spec with a Test Plan; the
  acceptance-report workflow gates this repo's PRs.

## 3.1.0 — isolation guard hooks + fr-spelling dual-read (#265, #272)

- **Plugin-shipped isolation enforcement (#265).** super-fr now ships a
  hook pair: PostToolUse(Skill) writes a session-keyed sentinel when
  fr-goal / fr-brainstorming / fr-execute starts (base repos only — linked
  worktrees never key a sentinel); PreToolUse(Bash) denies base-repo-cwd
  commands other than `fr isolation …` while the sentinel lives, clearing
  it on `fr isolation down` (48 h GC backstop). Skill prose closes the
  read-only gray zone: isolation precedes EVERYTHING; "start with X"
  reorders work items, never the first action.
- **fr-first dual-read for every residual vk spelling (#272).**
  `fr-profiles.yaml`, `~/.config/fr/secrets/`, `.git/fr/isolation/`,
  `~/.cache/fr/worktrees/`, `customizations.fr`, `fr-bridge.lock`,
  `FR_BRIDGE_{REPOS,LOCK_PATH,RECOVER_ORPHAN_CARDS}` — legacy vk
  spellings still read, with a loud `run fr init migrate` warning.
  `fr isolation up` now mount-follows the profile's committed
  `--env-file`. `VK_DERIO_OPS_PROJECT_ID` deliberately keeps its name
  (VibeKanban product domain). Fallbacks removed one minor later.
- **New `fr init migrate`** (dry-run default, `--yes` applies): renames
  the profiles yaml via `git mv`, rewrites devcontainer customizations +
  secrets mounts (JSONC files are skipped with a hand-migrate warning),
  moves the state dir, and prints — never executes — the copy-no-clobber
  host secrets block.

## 2.1.1 — registry label colors land on GitHub again

- **`vk apply` paints labels with their registry color / description.**
  Since the v2 collapse (#101) the render → diff → apply pipeline carried
  label names as plain strings; only the `RealGhClient` boundary wrapped
  them into `LabelDef`, defaulting every name to grey (`ededed`) with
  empty description. Every label `vk apply` created — `spec:<slug>`,
  `plan:<slug>`, `phase:<N>`, `vk-ready`, `manual` — was silently
  stranded grey, regardless of what `vk/labels.py` defined. Fix flows
  `frozenset[LabelDef]` end-to-end: `render._phase_labels` /
  `_lifecycle_label` return registry-resolved `LabelDef`s, `RenderedIssue
  .labels` and `RepoLabelEnsure.labels` carry `LabelDef`, and `IssueCreate
  .labels` / `IssueLabelChange.{add,remove}` project to name strings only
  at the gh-wire boundary.
- **Stranded labels self-heal on next `vk apply --yes`.** `gh label create
  --force` is idempotent and updates color + description on existing
  labels — so previously grey labels get repainted automatically the next
  time their plan is reconciled.

## 2.1.0 — `vk.bridge` library + renderer phase→issue translation

Release marker promoting the patch work in 2.0.5 (renderer fix) and
2.0.6 (`vk.bridge` library) to the stable minor surface. No new code
beyond the version bump and CHANGELOG.

- **`render`: `- Blocked by #N` writes the predecessor's Issue number,
  not its phase number** (shipped 2.0.5). The renderer previously wrote
  phase numbers, which the bridge silently mis-interpreted as Issue
  numbers — any v2 plan with cross-phase deps was wrongly gated. Renderer
  now accepts a `phase_to_issue` map built from each phase's
  `tracking_issue` plus the in-flight `created_issues` of the current
  `apply()` run.

- **`vk.bridge` sub-package** (shipped 2.0.6). Exposes `discover_plans()`
  and `tick()` for cron consumers (the live bridge in agent-images). NOT
  part of the operator CLI. Replaces hand-rolled parsing + dispatch loops
  with the same library projection chain `vk apply` uses. Spec §"Bridge
  integration — `vk.bridge.*`".

## 2.0.6 — `vk.bridge` library

- **New: `vk.bridge` sub-package.** First shipped here as a patch; see
  the 2.1.0 entry above for the full description.

## 2.0.5 — renderer translates phase numbers to tracking-issue numbers

- **`render`: `- Blocked by #N` now uses the predecessor's tracking-Issue
  number, not its phase number.** v2's renderer was writing
  `- Blocked by #{phase_number}` in the `## Dependencies` block, but the
  bridge parses `#N` as a GitHub Issue number — so any v2 plan with
  cross-phase deps was silently mis-gated. Single-phase plans (the bulk of
  what shipped pre-rework) were unaffected, which is why the bug stayed
  invisible. Fix lives in `vk/render.py`: `_render_body` and `render()` now
  accept an explicit `phase_to_issue` map, which `render()` builds from
  each phase's `tracking_issue` URL. The body renderer (formerly
  `_render_body`) is promoted to public `render_body` since `apply()`
  now reuses it for in-flight re-rendering.
- **`apply`: in-flight predecessors are propagated forward.** When two
  dependent phases are created in the same `apply()` run, the second
  phase's `IssueCreate` body is re-rendered after the first phase's Issue
  lands, so `- Blocked by #N` uses the just-assigned Issue number rather
  than the phase-number fallback. Opt in by passing the new `plan=` kwarg
  to `apply()`; callers that omit it get the legacy fallback (the
  operator sees a broken `#<phase-number>` ref and re-dispatches).
- Forward-compat: `_render_body` also accepts a `phase_to_repo` map so
  cross-repo deps render as `owner/repo#N` (the form the bridge already
  parses). v2 is single-target_repo today so the map stays empty in
  practice, but the wiring is in place.

## 2.0.4 — stop silently dropping non-canonical step formats during migration

- **`migrate`: bold-paragraph and bold-prefix step formats now parse.**
  The v1 step regex required `- [x] **Step N: title**` (checkbox + title-inside-bold).
  Plans using bare `**Step N: title**` paragraphs (frank's argocd, openrgb,
  observability) or `- [x] **Step N:** title` (willikins/stoa-goals-entry,
  title-outside-bold) silently parsed as `steps: []` and migration emitted
  empty phase yamls. The regex now accepts all four variants in one shot.
- **`migrate`: raw-body fallback when the parser can't extract structure.**
  When a parsed task ends up with zero steps, the migrator splices the task's
  raw markdown body in as a single synthetic step so content is preserved.
  When a parsed phase ends up with zero tasks (e.g. content-factory's
  `### Step N:` h3 headers instead of `### Task N:`), each sub-section
  becomes a synthetic task with the same body-preservation rule. The bug
  fix in 2.0.4 also covers any other quirks the parser doesn't recognise,
  since the fallback is regex-agnostic.
- **`migrate --force`: re-migrate plans whose v2 folder already exists.**
  Required for repairing plans that were migrated by pre-2.0.4 vk versions
  with the silent-drop bug. Tears down the existing folder, restores the
  paired `.md.v1-archive`, and runs migration fresh.

## 2.0.3 — consistent `|-` for all step text fields in migrated plans

- **`migrate`: step `text:` values now always use YAML literal block scalar.**
  Single-line step titles were emitting as plain or single-quoted scalars
  (e.g. `text: Do the thing` or `text: 'Install: foo'`), while multi-line
  bodies correctly used `|-`. Introduced `LiteralStr` — a `str` subclass
  with its own PyYAML representer that forces `style="|"` unconditionally.
  The migrator wraps all step `text` values in `LiteralStr` so every phase
  YAML is visually uniform: one canonical style, no quoting surprises.

## 2.0.2 — fix flat-plan migration producing empty folders

- **`migrate`: flat-format v1 plans (no `## Phase` headings) produced empty
  folders.** The v1 parser puts tasks into `v1plan.tasks` (not `v1plan.phases`)
  for plans without phase headings. The migrator iterated only over
  `v1plan.phases`, so flat plans got only a `_meta.yaml` with no phase YAML
  files. Fixed by synthesising a single Phase 1 from `v1plan.tasks` when
  `v1plan.phases` is empty — flat plans now produce `01.yaml` with all tasks
  intact.

## 2.0.1 — bugfixes surfaced by self-migration

Three bugs found while running `vk migrate v1-to-v2 --yes` against this
repo's archived plans (Phase 6 of the v2 rebuild):

- **`migrate`: rework-detection was a substring match.** `"-rework-" in
  slug` false-positived on plans whose slug merely *contained* the string
  "rework" — most notably `2026-04-22-vk-plan-rework-command` (which *adds*
  the rework feature but is not itself a rework). Such plans were getting
  a stale `parent_plan` field populated from illustrative markdown in their
  body. Fixed by anchoring the detection to the canonical rework slug
  shape: `<parent-slug>-rework-<N>` (regex `-rework-\d+$`).
- **`real_ghclient`: GraphQL `MERGED` PR state crashed `observe`.** GitHub's
  `PullRequestState` enum has `OPEN`/`CLOSED`/`MERGED`, but the v2 observe
  contract is `OPEN`/`CLOSED` (the `merged` boolean carries the distinction).
  `RealGhClient.list_linked_prs` now coerces `MERGED` → `CLOSED` before
  returning. Crashed `vk apply` on any plan with merged PRs in the wild.
- **`migrate` + `plan_ops`: multi-line `text:` fields were unreadable.**
  Default PyYAML `safe_dump` serialises any string containing a newline as
  a double-quoted scalar with `\n` escapes — borderline impossible to read
  for v2 step bodies (multi-paragraph prose + fenced code blocks). New
  `vk._yaml.dump_plan_yaml` swaps in a representer that emits multi-line
  strings as YAML literal block scalars (`text: |`), preserving newlines
  and code fences verbatim. `allow_unicode=True` keeps `→` / em-dashes
  as-is instead of `→`-escaping them. Both `vk.migrate` and
  `vk.plan_ops` route through this so migrated and hand-edited yaml stays
  visually consistent.

Regression tests added for all three. New files
`tests/unit/test_real_ghclient.py` (GraphQL-shaping seam, monkeypatched
gh subprocess) and `tests/unit/test_yaml_dumper.py` (block scalar +
unicode + key-order assertions).

## 2.0.0 — single state machine

**BREAKING — full rewrite per [the v2 design spec](docs/superpowers/specs/2026-05-06-vk-rebuild-state-machine-design.md).**

The plan format is now folder-based (`docs/superpowers/plans/<slug>/` with
`_meta.yaml`, `_prose.md`, and per-phase `NN.yaml` files). Use `vk migrate
v1-to-v2 --yes` to convert existing v1 `.md` plans; the migration tool
handles rework metadata, conflicting target_repo loud-fails, and updates
spec tables in lockstep.

The CLI surface collapses to:

- `vk apply` — render → observe → diff → mutate (idempotent reconciler).
- `vk plan {create,edit,rework,rework-add,rework-list,self-review}`.
- `vk pickup --phase N` — agent-facing phase scope.
- `vk spec status` — spec rollup, computed on demand.
- `vk migrate v1-to-v2` — the v1 off-ramp.

There are no separate `dispatch` / `progress` / `execute` / `admin` /
`issue` verbs in v2. Every state change is derived from observation of
the plan files plus GitHub state.

The bridge in willikins requires its own migration to call the v2 vk
library directly (Plan 2 of the v2 rebuild spec); until that lands, the
bridge continues to operate on consumer repos that haven't migrated.
Cross-repo plan resolution in `vk spec status` is also Plan-2 work and
currently surfaces cross-repo plans as `Unreachable`.

## 1.5.0 — v1 retirement

**BREAKING.** Every v1 CLI command is removed:

- `vk plan {new,convert,write,validate,rework,spec-index,format,...}`
- `vk dispatch {create,migrate,...}`
- `vk progress {sync,board,audit,transition,create}`
- `vk admin *`
- `vk execute {claim,scope,check-deps,check-step,pr-body,pr-opened}`
- `vk issue *`
- `vk init`

Replaced by the v2 surface (which has been available under `vk v2 ...`
since 1.4.x):

- `vk apply [<plan-dir>|--all] [--yes] [--format text|json]`
- `vk pickup <plan-dir> --phase N`
- `vk plan {create,edit,rework,rework-add,rework-list,self-review}`
- `vk spec status [<spec-path>|--all]`
- `vk migrate v1-to-v2 [--yes] [--include-in-progress]`
- `vk skills`

`vk migrate v1-to-v2` is the supported off-ramp from v1 `.md` plans to v2
plan-as-folder format. Migration is dry-run by default; pass `--yes` to
write. The migration tool itself remains available through 1.x; consumer
repos with v1 plans should run it once and commit the result.

Skill files (`skills/vk-{plan,dispatch,execute,progress}/SKILL.md`)
rewritten to reference only v2 commands.

## Earlier releases

Pre-1.5.0 releases were tracked through PR descriptions and commit
history rather than this file. See git log for details. Notable
milestones:

- **1.4.x** — v2 library + CLI shipped under `vk v2 ...` namespace
  (Phases 1–3 of the v2 rebuild plan).
- **1.0.x — 1.3.x** — v1 plan/dispatch/progress/execute toolchain.
