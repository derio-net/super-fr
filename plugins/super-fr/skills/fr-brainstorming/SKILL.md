---
name: fr-brainstorming
description: >
  Brainstorm a feature INSIDE an isolated workspace: invokes fr-isolation
  first, then runs superpowers brainstorming in the worktree/devcontainer —
  the base repo is never touched from the first command on. Use for any
  feature brainstorm in an fr-enabled repo (fr plans or devcontainer profiles
  present), when fr-goal starts its pipeline, or when the operator says
  "brainstorm this feature", "let's design X", or starts creative work that
  will become a spec. devcontainer mode hard-stops without a profile;
  docker-less host/external modes isolate via the worktree instead.
---

# fr-brainstorming

`superpowers:brainstorming`, wrapped in isolation. Exploration commands,
spec drafts, and everything downstream happen in the isolation workspace,
so a brainstorm that becomes a build never has to relocate, and a brainstorm
that dies leaves the base repo pristine.

**Announce at start:** "I'm using fr-brainstorming to design this in isolation."

## 0. Isolation first — hard gate

Before ANY command — exploration, measurement, cluster reads included; an
operator "start with X" never reorders this:

```bash
fr isolation up --branch <feature-branch> [--profile <name>]
```

- Name the branch for the feature now (`feat/<slug>`); the worktree, the
  eventual PR, and cleanup all key off it. The new `feat/<slug>` is cut from
  freshly-fetched `origin/<default>` (#322) — pass `--base <ref>` only to
  stack on something else.
- **No devcontainer profile → HARD STOP — but only in devcontainer mode.**
  Offer to run the fr-init interview immediately; if the operator declines,
  the brainstorm does not proceed. (Under fr-goal, treat it as a blocker:
  pause, fr-init, resume.) On a docker-less host that declares
  `FR_ISOLATION_TARGET=worktree` (or in a prepared external container), `up`
  succeeds without a profile — no stop, the worktree is the isolation.
- From here on, follow the fr-isolation skill's exec-bridge discipline:
  read/edit files in the worktree, run every command through
  `fr isolation exec -- ...`.
- **Standalone invocation only:** also start the run cursor now —
  `fr run start fr-goal --branch <feature-branch> --driver standalone`, or
  `fr run adopt <plan-dir|spec>` when work already exists on disk — so
  `implement`'s `needs: [spec, plan]` later refuses to advance past a plan
  that was never written (#436 instance 1). Then, **before the first
  question**, run `fr run advance <run-id>`: the `brainstorm` gate opens only
  then, and `resolve` counts only answers given after it (#761). Never ask
  while the gate is closed. `--driver standalone` lifts fr-goal's two-round
  cap (you ask one question per turn); one answered question is still owed.
  **Under fr-goal, skip this entirely** — that
  pipeline already started the run, and a second `fr run start` exits 2. It
  also exits 2 (naming the run) if this branch already has one: resume with
  `fr run advance <id>`. Refused over stale artifacts? Run
  `fr migrate artifacts --yes` and retry — `fr run start` is not exempt.

## 1. Brainstorm

Run `superpowers:brainstorming` as usual — understand the context and goal, explore the codebase (in the worktree), propose approaches, refine into a design.

Before exploring, record the operator's brief **verbatim** as a spec-journal entry, for
the record: the goal text as typed, or the issue's title and body plus any
comments pointed at. Redact per `.claude/rules/third-party-privacy.md` first —
a third-party host, org, repo or person becomes an RFC 2606 name
(`example.com`, `.invalid`, …) keeping the shape. Standalone: `fr journal add
--scope spec --kind discovery --input …`; under fr-goal: `journal: [{kind:
discovery, input: true, id, title, body}]` on the brainstorm record. Nothing
after brainstorm reads it: the spec is the contract.

- **Standalone invocation:** fully interactive — ask questions as they
  arise, section-by-section validation, the normal brainstorming flow.
- **Under fr-goal:** the sized-round contract applies instead — collect every
  operator-owned decision into one round, rarely two (fr-goal's rules win
  while it drives).

**The standing verification question.** Every brainstorm asks it once: *how will this be verified before it merges?* Run `fr verification list` (repo-authored strategies first, then the shipped `candidate`, `client-live`, `prerelease`, `live`), recommend one, and record the answer in the spec's `## Verification` section: an optional `strategy: <name>` line (default: the workflow shape's, unless the repo cannot run its install program, e.g. no executable `.fr/candidate-install`; an explicit unrunnable one fails `fr plan self-review`), then one `- <row-id>: <strategy|none> — <reason>` line per overridden row. The reason is required when a line's strategy is post-merge (`live`) or `none` (post-merge: why no pre-merge strategy applies; `none`: what verifies the row instead) and optional otherwise; prose alone counts as no section. A row on an agent-driven pre-merge strategy needs a `scenario:` (`fr acceptance set-status --scenario`), and any strategy that installs a build needs the repo's executable `.fr/candidate-install` — if it has none, say so rather than choosing `candidate`. Only behaviour a released build alone can show goes to the Test Plan as a post-merge row. The same question settles the gate: who must act once it merges (`tester` or `devops` hold the close-out; `developer`, `reviewer`, `owner`, `security` hold nothing). A `live` strategy defaults to `tester`; set the run's with a `gate: <gate>` line and one row's with `gate: <row-id>=<gate>`, then check it with `fr verification exit --spec <path>`. Authoring a strategy: `docs/verification-strategies.md`. **Read the repo's settings first.** Run `fr settings show --json` and write the spec to match what the repo turned off (`artifacts.*`, read from the default branch): under `acceptance: off` present no rows (§3 does not apply) and write no row-level `gate: <row>=<gate>` line; under `test_plan: off` write no `## Test Plan`; under `gates: off` write no `gate:` line. `fr run resolve` refuses a spec that breaks one, naming the setting.

## 2. Hand off

The brainstorm's design document becomes the spec
(`docs/superpowers/specs/<YYYY-MM-DD-slug>-design.md`, committed in the worktree;
under quiet or stealth `$FR_SPECS_DIR/<YYYY-MM-DD-slug>-design.md`, see below), with a `## Requirements` section before `## Design`: a plain
numbered list, one requirement per line — `R1. <text>`, `R2. <text>` — in the
spec author's own words, with no quote, no source and no gate on its content.
It is what the questions settled: a requirement the spec does not state is not
built, and a spec defect is fixed in the spec. The Test Plan heading is exactly `## Test Plan` — unnumbered, no suffix, even when every other section is numbered: fr reads that line alone, and refuses a near-miss such as `## 6. Test Plan (post-merge)` (`fr validate artifacts`, `fr plan self-review`, archive, close-out). **Standalone:** resolve the cursor §0 started with its step **Where the files go (quiet and stealth).** Under the default `repo` placement fr's artifacts live in the checkout, at the `docs/superpowers/…` paths named here. Under quiet or stealth they do not: run `fr settings paths --shell` in the workspace and use its answers — `FR_SPECS_DIR`, `FR_PLANS_DIR`, `FR_PLAN_JOURNALS_DIR`, `FR_DEBUG_JOURNALS_DIR` and the rest — for every path a skill names below `docs/superpowers/`. They point into the repo's `fr` worktree (quiet) or the tracking clone (stealth), the two places outside the workspace where the edit gate lets you write. A file you write by hand there (the spec) is committed in that checkout, never in the product worktree, where `fr push` refuses it. fr's own commands (`fr plan create`, `fr journal add`, `fr run …`) already follow the placement.
record — `emitted: {spec: <path>}`, each answer a `decision` in `journal:`,
the brief from §1, each §3 row in `acceptance:` — in ONE `fr run
resolve <run-id> --step brainstorm --record <file>`, then `fr run advance
<run-id>` for everything after (the cursor is a gate, not a file on disk:
`implement`'s `needs: [spec, plan]` refuses work that never wrote one). Hand
off to `fr-plan` (fr-plan-override routes `writing-plans` there); the
isolation workspace stays up — cleanup belongs to whoever finishes the run
(`fr isolation down` after the PR merges).

## 3. Acceptance rows — born with the spec, presented at the close

One acceptance row per requirement, or per closely related group of
requirements — an `acceptance:` entry of the brainstorm record (`status:
not-implemented`, `origin: [<repo>:<new-spec-path>#R<n>]`, `verify:
live` when only a live run can prove it, or any strategy the §1 question settled), or with no run
`fr acceptance add --origin <repo>:<spec>#R<n> …` (run `fr acceptance init`
first if the repo has no matrix; it commits what it writes). A requirement that changes a row an earlier feature merged is an amendment of that row, never a new row or an in-place edit: an `acceptance:` entry `{row, op, why, …}` (or `fr acceptance amend`, see `fr-acceptance`). A row states what the product does, never how the pipeline runs ("delivered in one phase", "a browser check was done"): a process directive is not a row, and a level ref into `docs/superpowers/` is refused. A UI row also carries `visual`: states and interactions, limits included (ask about any the design leaves unstated). **The brainstorm ENDS by presenting the
rows to the operator with a one-line defense each** — the business claim,
the target verification level, why it is business-level not implementation
detail. Silent row creation is not acceptance-of-scope; the presentation is.
Under fr-goal the presentation rides spec-review. Hand-off checklist: rows
added AND presented, each citing its requirement id.

## Scope notes

- This skill owns WHERE brainstorming happens, not HOW — brainstorming's
  own craft (questions, alternatives, YAGNI) is unchanged.
- Multi-repo features: brainstorm in the repo that owns the spec; other
  repos get their own isolation workspaces when their plans dispatch
  (one workspace, one branch, one PR per repo).
- **Lenses.** When the work gives you a reason to want the whole feature examined under a concern (shipped: `security`, `tests`, `errors`, `simplicity`; `fr lenses list` shows the repo's set), add one in your step record: `journal: [{kind: lens, lens: <id>, title: "<why, one line>"}]`. A lens is never removed, and the lens review before `deliver` examines the whole diff under each one.
