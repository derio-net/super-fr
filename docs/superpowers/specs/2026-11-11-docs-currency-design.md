# Docs currency: generated pages, a shipped `fr docs check`, and a rewritten front door

## 1. Goal

super-fr's documentation is a 552-line README and three published pages. Both lag the code,
and nothing but a prose rule keeps them current. This change makes the published site a build
product of Markdown sources, ships a gate (`fr docs check`) that any repo using super-fr can
run on every PR, and rewrites the content: a short README, the reference material and the
existing operator guides published as pages, and a page for every shipped skill.

### Non-goals

- Changing the blog-craft renderer, or the look of the `broadsheet` style.
- A renderer inside `fr`. `fr docs` checks coverage; how a repo turns Markdown into a site
  stays that repo's business.
- Proving a page's prose is true. The gate proves a page was looked at when its sources
  changed, which is the most a diff can show.
- Editing anything under `docs/superpowers/implemented/`.
- Publishing `docs/acceptance/`, `docs/triage/`, `docs/audits/` or `docs/goals/` as pages (the
  acceptance report keeps its own `/acceptance/` route).

## 2. Background (read from the code)

- `.github/workflows/pages.yml` copies `docs/explainers/` to Pages verbatim on a push to
  `main` that touches `docs/explainers/**`, `docs/acceptance/**` or
  `packages/fr/src/fr/acceptance/**`, then renders the acceptance report into
  `_site/acceptance/`. It renders no explainer.
- `docs/explainers/` holds `01-fr-goal.md` with a committed `01-fr-goal.html` (1.07 MB,
  fonts embedded), and two pages with no source: `index.html` and `fr-isolation.html`,
  hand-authored with a bespoke shell (`.claude/rules/explainers-currency.md`, known gap 1).
- The renderer is `tools/render_explainer.py` in `derio-net/blog-craft` (public). Run as
  `uv run --isolated --no-project --with markdown --with pyyaml python <renderer>
  <page>.md --style broadsheet --embed-fonts -o <page>.html` from `/`, at blog-craft
  `cdff7a66b4dc`, it reproduces the committed `01-fr-goal.html` byte for byte (checked
  2026-11-11 in this run's workspace). It reads front matter keys `title`, `date`,
  `archetype`, `tldr`, `standalone_style`; a file with no front matter renders with the
  title `Explainer`. Its fonts are in the same repository
  (`templates/content-type-explainers/shared/fonts/broadsheet/`).
- Currency is enforced by `.claude/rules/explainers-currency.md` (repo-local; mirrored to
  OpenCode by `scripts/sync-opencode.py`'s `REPO_LOCAL_ONLY_RULES`; not mirrored to Hermes,
  because `scripts/sync-hermes.py` mirrors only the plugin rules named in its
  `SHIPPED_RULE_NAMES`) and by
  `tests/unit/test_tripwire_explainers_fresh.py`, which compares title and headings only.
  No skill, workflow manifest or `fr` command names an explainer.
- `tests/unit/test_tripwire_fr_goal_question_rounds.py` reads `01-fr-goal.html` and
  `index.html`; `tests/unit/test_pages_workflow.py` pins the workflow's triggers and steps.
- `README.md` says the plugins ship eleven skills; `plugins/super-fr/skills/` has thirteen
  and `plugins/super-fr-dispatch/skills/` two. Its CLI tables omit `triage`, `usage`,
  `debt`, `ops`, `gate`, `release`, `journal`, `models`, `verification`, `cloud`, `harness`,
  `services`, `hermes` and `closeout`, all registered in `packages/fr/src/fr/cli.py`.
- Seven operator guides sit in `docs/*.md` (`cloud-setup`, `exit-gates-release-walk`,
  `gate-backfill`, `herdr-control-sessions`, `merge-protection`, `ops`,
  `verification-strategies`), named by AGENTS.md and by messages `fr` prints. None is
  published and none has front matter.
- `fr` reads per-repo settings from `.fr/` (`ci.yaml`, `debt.yaml`, `triage.yaml`); none is a
  registered artifact kind. `fr.artifacts.trigger.READ_ONLY_COMMANDS` lists the commands that
  never write a registered artifact, pinned literally by
  `tests/unit/test_migration_trigger.py`.
- `deliver` already derives evidence by running an `fr` check itself: `proportionality`
  (`commands/run_cmd.py`, `_proportionality_witness`).
- `scripts/check-change-fragment.py` is the precedent for a PR gate over the diff
  `<merge-base>...HEAD`.
- `.github/workflows/ci.yml` aggregates its jobs in `ci-ok`. A new workflow file must be
  listed in `ci-budget.yml` or excluded (`tests/unit/test_ci_budget.py`).

## Requirements

R1. `fr docs check` reads `.fr/docs.yaml` and exits 0, saying there is nothing to check, in a repo that has none. A config whose `pages` globs select no tracked file is a usage error (exit 2), never a clean pass.
R2. A page is a Markdown file matched by the config's `pages` globs; its front matter declares `covers` (a list of path globs) and `reviewed` (a date and a one-line note).
R3. `fr docs check --base <ref>` fails, exit 1, when the diff from the merge base to HEAD changes a path a page covers and does not change that page, naming the page, the changed paths and the two ways to satisfy it (edit the page, or update its `reviewed` stamp).
R4. `fr docs check` fails a page whose front matter is missing or unreadable, lacks `covers` or `reviewed`, or has a `covers` glob that matches no tracked file.
R5. The config's `must_cover` globs name files that some page must cover; `fr docs check` fails naming every such file that no page covers.
R6. `fr docs check` with no `--base` uses the repository's default branch on the remote, and on that default branch itself (pushed or not) runs only the structural checks (R4, R5).
R7. `fr docs status` lists every page with its covered globs and its `reviewed` stamp; `--json` gives the same as data.
R8. `fr docs` writes nothing, and runs on a repository whose artifacts are stale.
R9. `deliver` refuses to resolve `done` while `fr docs check` fails for the run's branch, printing the check's own output; a repo with no `.fr/docs.yaml` is unaffected.
R10. The fr-goal and fr-debugging skills tell the agent to run `fr docs check` before the PR is delivered, and a shipped rule states the obligation for every harness, Hermes included.
R11. This repo's CI runs `fr docs check` on every pull request as part of `ci-ok`.
R12. Every published page of this repo is rendered from a Markdown source when the site is deployed; no rendered explainer HTML is committed.
R13. The renderer is `derio-net/blog-craft` at one pinned commit, named in one file that every workflow reads; a test fails a workflow that names a blog-craft commit itself.
R14. The site build renders every page the config names, rewrites links between pages from `.md` to `.html`, and fills the index page's list of pages from their front matter.
R15. CI builds the site on every pull request, so a page that does not render fails before merge.
R16. The existing published URLs keep working: `/`, `/01-fr-goal.html`, `/fr-isolation.html` and `/acceptance/`.
R17. `index` and `fr-isolation` have Markdown sources that carry the content of today's hand-authored pages; the index keeps its link to `./acceptance/`.
R18. The seven operator guides in `docs/` are published pages, each with `covers` and `reviewed`.
R19. Every shipped skill is covered by a published page, enforced by `must_cover`.
R20. The README is a front door of at most 200 lines: the badges it carries today (the Acceptance badge among them), what super-fr is, install, a first goal, the skills table, the CLI table and links to the pages; a test fails a longer README.
R21. The README's skills table and CLI table are generated from the skills' front matter and the `fr` command tree, and a test fails when either is stale.
R22. The reference material removed from the README (plan model, workflow shapes, label lifecycle, per-repo profile, acceptance matrix, Hermes, components, isolation, requirements) is published as pages.
R23. The pages deploy runs when a page source, the docs config, the site build, the renderer pin or the acceptance report's inputs change, and not on other changes under `docs/`.
R24. `.claude/rules/explainers-currency.md` and its mirrors describe the new model, and the tripwires that read rendered HTML read the Markdown sources.

## 3. Design

### A. `fr docs` (R1-R8)

A new package `packages/fr/src/fr/docs/` and `commands/docs_cmd.py`, registered as `fr docs`.

`.fr/docs.yaml`, strict (`extra="forbid"`):

```yaml
pages:            # globs, relative to the repo root; each match is a page
  - docs/explainers/*.md
  - docs/*.md
  - docs/reference/*.md
must_cover:       # optional; every tracked file matching must be covered by a page
  - plugins/*/skills/*/SKILL.md
```

A page's front matter (other keys are ignored, so the renderer's keys coexist):

```yaml
covers:
  - plugins/super-fr/skills/fr-triage/SKILL.md
  - packages/fr/src/fr/commands/triage_cmd.py
reviewed: 2026-11-11 written with the page
```

`reviewed` is a string: an ISO date, a space, a non-empty note. A page whose `covers` is the
empty list is legal (an index page), and R4's "matches no tracked file" applies per glob.
Every glob in the config and in `covers` is segment-aware and matched against
`git ls-files`: `*` and `?` stay inside one path segment, and `**` spans segments. So
`docs/*.md` is the seven guides and the new `docs-currency.md` only, never
`docs/superpowers/**`. (`fnmatch`, where `*` crosses `/`, is not used.) The matcher is one
small function, `fr.docs.globs.match`, and `scripts/build-site.py` carries a copy of it
because it runs without `fr`; a test asserts the build's page set equals
`fr docs status --json`'s on this repo, so the gate and the site cannot disagree about what
a page is.

Modules: `model.py` (config and page front matter), `load.py` (config, pages, tracked
files; a git seam the tests replace), `check.py` (pure: pages, tracked files and changed
paths in, findings out) and `render.py` (text and JSON). The changed paths are
`git diff --name-only <merge-base>...HEAD`, with both sides of a rename counted. A page
"changed" when its own path is in that list, so an edit to the body and an edit to `reviewed`
both count, and the gate never reads the stamp's date.

`--base` resolution (R6): the given ref; else `fr.git.remote_default_ref`, which only
reads (`origin/HEAD`, then `origin/{main,master,trunk,develop}`) and makes no network call.
When HEAD is that branch or the merge base equals HEAD, the diff is empty and only R4 and
R5 run. An unresolvable base is exit 2, never a pass. `fr docs` runs no git command that
writes, `set-head` included (R8).

Exit codes: 0 clean, 1 findings, 2 usage or environment error (bad config, no git, no base).

`docs` joins `READ_ONLY_COMMANDS`: it reads `.fr/docs.yaml`, page files and git, none of
them a registered artifact, and must be able to run in CI on a tree the gate would refuse.
`.fr/docs.yaml` is not an artifact kind, like `.fr/debt.yaml`.

### B. Every flow (R9-R11)

- **CI** is the gate that no flow can skip: a human PR, a triage batch, fr-debugging and any
  future flow all end in a PR. This repo adds a `docs-check` job to `ci.yml`, inside
  `ci-ok`: `actions/checkout` with `fetch-depth: 0`, then `uv run fr docs check --base
  "origin/${{ github.base_ref }}"` on `pull_request`, and `uv run fr docs check` with no
  base on `push` to `main` and on `merge_group` (structural checks only on `main`; on a
  merge group the diff against the default branch). A consumer repo adds the one command to its own CI; `docs/docs-currency.md` (a
  new guide, itself a page) says how.
- **`deliver`** gains a derived evidence key, `docs`, beside `proportionality`: on `done`
  fr runs the check in process against the default branch and refuses on findings. With no
  `.fr/docs.yaml` the witness is `none`. The base is `_proportionality_base`'s,
  so both derived witnesses diff against the same commit, the isolation start commit
  included. Both shipped shapes (`fr-goal`, `fr-goal-light`) list `docs` in
  `deliver.evidence`, in both copies (`plugins/super-fr/workflows/` and
  `packages/fr/src/fr/workflows/`). `_check_step_drift` compares step and member ids only,
  so this drifts no run: an in-flight run gains the obligation at its next `deliver`, and
  only in a repo with `.fr/docs.yaml`. The edits: `docs` in `DERIVED_EVIDENCE`
  (`fr/workflow/artifacts.py`), in `_VERIFIABLE_EVIDENCE` and `_DERIVED_FROM`
  (`commands/run_cmd.py`), a `derive("docs", ...)` beside proportionality's, and the pinned
  evidence tuples in `tests/unit/test_tripwire_shipped_workflows.py`.
- **Skills**: fr-goal §8 and fr-debugging's delivery paragraph each gain one sentence.
- **Rule**: `plugins/super-fr/rules/docs-currency.md`, under 25 lines, added to
  `install.sh`'s `CLAUDE_RULES` and to `sync-hermes.py`'s `SHIPPED_RULE_NAMES` (Hermes
  mirrors only the names on that list), and mirrored by running both sync scripts. It states: in a
  repo with `.fr/docs.yaml`, a PR that changes covered behaviour updates the page or its
  `reviewed` stamp, and `fr docs check` is how to know.

### C. The site build (R12-R17, R23)

`scripts/build-site.py <out-dir>`, stdlib plus the renderer's two libraries, run with
`uv run --isolated --no-project --with markdown --with pyyaml`:

1. reads `.fr/docs.yaml` (it shares no code with `fr`, so the deploy needs no `fr` to build
   pages; the acceptance report step keeps its own install);
2. renders each page with the blog-craft renderer found at `$BLOG_CRAFT_DIR`
   (`--style broadsheet --embed-fonts`) to `<out>/<route>.html`. Routes: a page under
   `docs/explainers/` keeps its basename at the site root (so `01-fr-goal.html`,
   `fr-isolation.html` and `index.html` are unchanged); any other page goes to
   `guides/<basename>.html` or `reference/<basename>.html` by its directory;
3. rewrites relative `href`s by one rule: a link to another page's source becomes that
   page's route, relative to the linking page; a link to any other tracked file or
   directory becomes a `github.com` blob (or tree) URL at the commit being built
   (`--ref`, default `HEAD`'s SHA); a relative link to a path git does not track fails the
   build. Absolute URLs, fragments and links that already point at a site route such as
   `./acceptance/` are left alone;
4. replaces the marker `<!-- site:pages -->` in the index source with a list of every
   page, grouped by section, each with its title and the first sentence of its `tldr`;
5. passes `--fonts-dir` explicitly, after checking the directory exists in the blog-craft
   checkout, and exits non-zero when the renderer exits non-zero or a rendered page carries
   no embedded `@font-face` data URI (the renderer continues without fonts, exit 0, when it
   cannot find them).

The pinned commit lives in `.github/blog-craft.ref` (one line, a full SHA). `pages.yml`
and the new CI job both check blog-craft out at that ref with `actions/checkout`
(`repository: derio-net/blog-craft`, `path: .blog-craft`). `pages.yml` replaces
`cp -R docs/explainers/. _site/` with the build, keeps the acceptance steps, and its
`paths` become `docs/explainers/**`, `docs/*.md`, `docs/reference/**`, `docs/acceptance/**`,
`.fr/docs.yaml`, `scripts/build-site.py`, `.github/blog-craft.ref` and
`packages/fr/src/fr/acceptance/**`. Both workflows read the SHA from the file
(`ref: ${{ steps.pin.outputs.sha }}` after a step that cats it); neither names it. CI gains a `site-build` job in `ci.yml`, inside
`ci-ok`.

`docs/explainers/*.html` are deleted and ignored. `index.md` and `fr-isolation.md` are
written from the hand-authored pages' text; the bespoke hero and schematic become prose,
tables and Mermaid diagrams, which the renderer supports.

### D. Content (R17-R22)

- `docs/explainers/`: `index.md`, `01-fr-goal.md` (kept; gains `covers`, `reviewed`),
  `fr-isolation.md`, and new concise pages (150 to 300 lines each, same voice as the
  fr-goal page): `fr-brainstorming-and-plan.md` (fr-brainstorming, fr-plan, fr-execute),
  `fr-debugging.md`, `fr-triage.md` (with fr-origins), `fr-acceptance.md`,
  `fr-dispatch.md` (fr-dispatch, fr-runner), `fr-devops-gate.md`, `fr-audit.md`,
  `fr-init.md`, `fr-progress.md`. Together their `covers` name all fifteen `SKILL.md` files.
- `docs/*.md` guides gain front matter (`title`, `tldr`, `covers`, `reviewed`,
  `standalone_style: broadsheet`) and stay where they are, since code and AGENTS.md name
  those paths. `docs/docs-currency.md` is new.
- `docs/reference/`: `cli.md` (the full command tree, in a generated block), `plan-model.md`,
  `workflow-shapes.md`, `dispatch-lifecycle.md` (label lifecycle, per-repo profile),
  `acceptance-matrix.md`, `hermes.md`, `components.md` (components, requirements). The text
  comes from today's README, corrected against the code.
- `README.md`: the front door of R20.
- `scripts/sync-readme.py` (`--check` verifies, no flag writes) fills
  `<!-- generated:skills -->` and `<!-- generated:cli -->` blocks in `README.md` and a
  `<!-- generated:cli-tree -->` block in `docs/reference/cli.md`. It writes only between
  the markers, so `cli.md`'s front matter (its `reviewed` stamp, and `covers:
  [packages/fr/src/fr/cli.py]`) stays hand-owned. The skills table is name, plugin and the first sentence
  of the `description` front matter; the CLI table is each top-level command and its help
  line, read from the typer app. Guard: `tests/unit/test_tripwire_readme_sync.py`, which also fails a README over 200 lines.

### E. Rules and tripwires (R24)

- `.claude/rules/explainers-currency.md` is rewritten: sources only, how to preview a page
  locally, the pinned renderer, `fr docs check`. `REPO_LOCAL_ONLY_RULES` keeps it.
- `tests/unit/test_tripwire_explainers_fresh.py` becomes: no `.html` is tracked under
  `docs/explainers/`; every page parses.
- `tests/unit/test_tripwire_fr_goal_question_rounds.py` reads `01-fr-goal.md` and
  `index.md` and drops both rendered pages.
- `tests/unit/test_pages_workflow.py` pins the new triggers and the build step in place of
  the `cp`; reads `docs/explainers/index.md` for the `./acceptance/` link; keeps the README
  Acceptance-badge pin; and asserts no workflow contains a 40-hex blog-craft SHA while both
  read `.github/blog-craft.ref`.
- `tests/unit/test_build_site.py` runs the build's pure parts (page set, routes, link
  rewrite, index list) over a fixture and asserts this repo's routes include `index.html`,
  `01-fr-goal.html` and `fr-isolation.html` at the root (R16).
- AGENTS.md gains the `fr/docs` entry, the `sync-readme.py` generator and the new rule.

### F. Release and matrix

A `minor` change fragment (`.changes/claude-tender-darwin-bj3d7j.yaml`): a new command
group and a new shipped rule. No artifact kind changes shape, so no migration.

## 4. Decisions

Recorded in the spec journal, each the operator's answer:

- generator: render at deploy from Markdown with pinned blog-craft; the two hand-authored
  pages become Markdown and lose their bespoke layout;
- enforcement: a shipped `fr` verb for all repos;
- scope: pipeline, gate, README and every new page in one PR;
- waiver: a `reviewed` stamp in the page's front matter;
- README: a short front door, reference moved to pages;
- new explainers: concise, 150 to 300 lines;
- verification: `candidate`; models: haiku, sonnet, opus for mechanical, standard, hard.

## 5. Risks

- **Stamp conflicts.** Two open PRs that both stamp one page conflict on its `reviewed`
  line. `covers` is kept narrow (a skill's `SKILL.md` and its command module, never
  `packages/**`) so this happens only when both PRs change the same surface.
- **A stamp is cheap.** An agent can stamp without reading. The stamp's note is in the
  diff a reviewer reads, which is more than today's silence.
- **Deploy depends on another repo.** A pinned SHA makes it reproducible; the CI
  `site-build` job fails first if the checkout or the renderer breaks.
- **The two rewritten pages look plainer.** Accepted by the operator.
- **Prose accuracy at this volume.** Around a dozen new pages; each is written from the
  skill and command source it covers, and review-phase checks claims against that source.

## Verification

strategy: candidate
gate: site-published-from-sources=tester
- docs-check-flags-uncovered-change: candidate — scenario drives the installed `fr docs check` over a fixture repo: a covered change with and without the page touched
- docs-check-structure: candidate — scenario: a dead glob, a missing stamp, an uncovered `must_cover` file, and a repo with no config
- docs-check-default-base-readonly: candidate — scenario: no `--base` on a feature branch and on the default branch, over a tree holding a stale artifact, with `git status` unchanged afterwards
- docs-deliver-refuses-stale-docs: none — unit tests drive `deliver`'s resolve over a fixture run in CI
- docs-currency-every-flow: none — the CI job, the shipped rule and its three mirrors are pinned by tripwires in CI
- site-builds-from-sources: none — the `site-build` CI job renders every page on each PR
- site-published-from-sources: live — only a Pages deploy from `main` shows the published URLs serving rendered sources
- docs-every-skill-has-page: none — `fr docs check` over this repo runs in CI with `must_cover`
- readme-generated-tables: none — the sync tripwire runs in CI

## Test Plan

1. [tester] After merge, wait for the "Deploy explainers to Pages" run on `main`. Open `https://derio-net.github.io/super-fr/`, `/01-fr-goal.html`, `/fr-isolation.html`, one guide and one reference page from the index, and `/acceptance/`: each loads, links between pages resolve, and the index lists every page.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-11-docs-currency | `derio-net/super-fr` | `2026-11-11-docs-currency` | — |
