# The front page, second pass: two acts, diagrams, a look of its own — design

Date: 2026-11-12
Repo: `derio-net/super-fr`

## Background

The first pass (`docs/superpowers/implemented/specs/2026-11-12-landing-front-page-design.md`,
merged as derio-net/super-fr#1411) replaced the wiki-style index with a landing page that
`scripts/build-site.py` renders itself from `docs/explainers/index.md` and the templates in
`scripts/site/`. The operator read the published page and found three gaps:

- It leaves out newer features: the Tester and DevOps exit gates and the wave driver. The
  word "wave" does not appear on it, and no explainer page exists for the wave driver or
  for exit gates as a whole (`docs/explainers/fr-devops-gate.md` covers the DevOps stage
  only).
- It has no diagrams.
- It looks generic. It reuses the article pages' broadsheet identity (serif type, brass
  accent), which the operator chose in the first pass and now wants replaced, on the
  front page only, by something more modern and eye-catching.

Facts checked in the code:

- `scripts/build-site.py` parses the landing with `parse_landing()`. `SECTION_KINDS` is
  `("prose", "flow", "guarantee", "pages", "cta")`; `GUARANTEES = (6, 8)` bounds the
  numbered sections; a line `<!-- landing:<kind> -->` under a `## ` heading names the kind.
- `render_landing()` fills `scripts/site/landing.html`; `scripts/site/landing.css` lays the
  page out and holds only the light palette. The dark palette and the `@font-face` rules
  are copied from a page the blog-craft renderer produced in the same build
  (`extract_theme_css`, `extract_font_css`); `THEME_PROPERTIES` lists the 13 custom
  properties the copied block must define.
- `insert_bar()` puts `<nav class="site-bar">` and `scripts/site/bar.css` on every page.
- `check_rendered()` requires an embedded `@font-face` data URI on every page.
- Other pages are rendered by the pinned blog-craft renderer with python-markdown
  (`fenced_code`, `codehilite`, `tables`, `sane_lists`); `fill_pages()` already replaces a
  marker (`<!-- site:pages -->`) in a page's Markdown before rendering.
- The first pass's acceptance rows live in
  `docs/acceptance/features/2026-11-12-landing-front-page.yaml`. Row
  `site-front-page-landing` says "six to eight numbered sections … in the broadsheet
  identity in light and dark".
- The wave driver is `fr triage batch drive` (`packages/fr/src/fr/triage/batch_drive.py`,
  `commands/triage_batch_cmd.py`; spec `2026-10-02-wave-driver-design.md`). Exit gates are
  `fr/verification/exit.py`, `fr gate pass`, the `gate:tester` / `gate:devops` PR labels and
  the release gating in `scripts/release.py` (spec `2026-10-14-exit-gates-design.md`).

## Decisions (operator, 2026-11-12)

1. Audience: both, in two acts. Act one sells a single trustworthy run to a developer; act
   two sells running a whole backlog to a lead or operator.
2. First-class sections added: exit gates (Tester and DevOps) and the wave driver.
   Isolation, the question round and spec, and independent review stay.
3. The acceptance matrix and the cost audit leave the numbered sections and move to a
   compact "also included" grid of small cards.
4. Look: dark, technical, glowing — a near-black canvas, one vivid accent gradient, a large
   tight sans-serif headline, monospace details, a terminal-style hero showing a run,
   glass-like cards. A light variant follows the visitor's setting. Article pages keep the
   broadsheet look.
5. Motion: CSS-only animation, switched off for visitors who prefer reduced motion. Still
   no JavaScript.
6. Diagrams, all four: run pipeline, gate ledger, wave of batches, isolation boundary.
   Hand-authored inline SVG kept in this repo.
7. New explainer pages: the wave driver, and exit gates as a whole.
8. The hero headline stays ("Give an agent a goal. Merge a PR you trust."); the rest of
   the copy is rewritten.
9. Verification as in the first pass: unit tests and the site build in CI, screenshots at
   implement, review and deliver; one post-merge row for the published site; gate
   `developer`.

## Requirements

R1. The front page tells its story in two acts, each opened by a heading and a short introduction: act one is one goal taken to one trusted pull request; act two is a whole backlog run through waves, gates and releases.
R2. The front page has six numbered sections, numbered continuously across the acts by the build, each keeping the first pass's rhythm (a problem the reader recognises, a headline, what the reader gains, how fr does it, one link). Act one: isolation; one question round and a written spec; a separate reviewer at every stage; one pull request, never self-merged. Act two: exit gates (Tester and DevOps hold the close-out and the final release until a person passes them); the wave driver (a ranked backlog run as waves of batches, each batch ending in one pull request). The build's bound of six to eight numbered sections stays.
R3. The front page has an "also included" grid of three to eight small cards, each a title, one sentence and exactly one link. It carries at least the acceptance matrix, the cost audit, debugging, the triage board and the supported harnesses.
R4. The hero keeps its headline and primary button. Its subline and facts are rewritten for the two acts, and it shows a terminal panel with a short run transcript whose lines are data in the page's front matter, each line marked as a typed command, output, a point where the operator acts, or a success line.
R5. The front page carries four diagrams: the run pipeline (goal to merged pull request, the operator's points marked), the isolation boundary (the reader's clone, the worktree, the container, what the agent can reach), the gate ledger (a merged pull request held by the Tester and DevOps gates, then release candidate to final release) and a wave of batches (backlog ranked into batches, batches into waves, each batch one pull request).
R6. A diagram is an SVG file kept in `scripts/site/figures/`, placed by a marker in a page's Markdown and inlined by the build. Each has an accessible name, takes every colour from the page's custom properties (so it is readable in the landing's dark and light schemes and on the dark article pages), runs no script, references nothing outside the page, and stays legible without horizontal scrolling at a 390 px wide viewport.
R7. The front page has a look of its own, not the broadsheet identity: a near-black canvas, one accent gradient, a large tight sans-serif headline from the system font stack, monospace details from the system monospace stack and glass-like cards, with a light palette under `prefers-color-scheme: light`. Body text and link text meet a contrast ratio of at least 4.5:1 against their background in both schemes. It makes no request to another host and has no horizontal scrolling at a 390 px wide viewport.
R8. Motion on the front page is CSS and SVG only (the terminal's command lines typed out character by character and its output lines appearing in turn, diagram accents moving): the page contains no script. Under `prefers-reduced-motion: reduce` every animation and transition is off, and with animation off or unsupported every piece of content is visible in its final state.
R9. Article pages keep the broadsheet look and their top bar unchanged. The front page keeps the top bar, the grouped list of every page under `#explainers`, `#guides` and `#reference`, the link to the acceptance report and a closing call to action.
R10. The build fails (exit 1, naming the page and the defect) and writes no degraded page when: a figure marker names a file that does not exist; a figure file has no accessible name, contains a script, an external reference, or a literal colour; an act has no numbered section; the grid has fewer than three or more than eight cards, or a card without exactly one link; a terminal line has an unknown kind; a figure marker stands in a section kind that cannot place one, or a section holds more than one; a figure's ids are not prefixed with its file's name; or any first-pass refusal applies, except the one for a front page with no embedded font, which is dropped (the front page embeds none).
R11. Two explainer pages are added, in the explainers' voice and with the front matter `fr docs check` requires: `docs/explainers/fr-wave-driver.md` (what a wave and a batch are, what one driver pass does, what it refuses, how it resumes, where the operator acts) and `docs/explainers/fr-exit-gates.md` (which gate a run gets and why, what each gate holds, how a gate is passed, how gates hold the final release as release candidates, with a link to the DevOps gate page for that stage's detail). Every claim in them is true of the shipped code, skills and guides they name in `covers`. Each carries at least one diagram, and the two act-two sections of the front page link to them.
R12. Every claim on the front page is one that a page it links to makes.
R13. The guidance for page authors (`.claude/rules/explainers-currency.md` and its generated mirrors, `docs/docs-currency.md`) describes acts, the grid, the terminal lines and figures.

## Design

### A. Landing source: new kinds and front matter

`docs/explainers/index.md` stays the source. `SECTION_KINDS` gains two kinds:

| Kind | Body shape | Rendered as |
|---|---|---|
| `act` | paragraphs | an act opener: the heading as the act's title with an act label ("Act one", "Act two", assigned by the build in order), the paragraphs as its introduction. Every `guarantee` section after it, up to the next `act`, belongs to it |
| `grid` | optional prose, then one unordered list; each item is `**Title.** one sentence [label](href)` | the card grid (R3) |

`guarantee`, `flow`, `pages`, `cta` and prose sections keep their first-pass shapes.
Numbering runs across acts ("01 / 06" … "06 / 06"). An `act` with no `guarantee` before the
next `act` or the end is refused; `guarantee` sections before the first `act` are allowed
(a landing with no acts still builds, as the first pass's tests assume).

Front matter: `hero.terminal` is an optional list of `{kind, text}` with `kind` one of
`prompt`, `out`, `you`, `ok`; any other kind is refused. `hero.command` stays accepted;
when `terminal` is present the terminal panel replaces the single command line.

### B. Figures

`<!-- site:figure <name> -->` on a line of its own in any page's Markdown (the landing or
an article) is replaced by the build with
`<figure class="site-figure">` + the contents of `scripts/site/figures/<name>.svg` +
`</figure>`, as one raw HTML block, before the Markdown is converted (the same point at
which `fill_pages` replaces its marker). `<name>` is `[a-z0-9-]+`. On an article page the replacement happens where `fill_pages`
replaces its marker, and the block is padded with a blank line on each side so
python-markdown treats it as a block of its own.

The landing does not go through that path. `parse_landing` lifts a figure marker (a block
holding only the marker) out of a section's body before the kind's shape checks run, and
stores the name on the section; `render_landing` emits the `<figure>` itself, outside the
Markdown conversion. A section holds at most one figure. It is allowed in `flow` (rendered
above the step list), `guarantee` (full width below the section's text, above its link)
and prose sections (below the text); a marker in an `act`, `grid`, `pages` or `cta`
section, or a second marker in one section, is refused.

A figure file is checked when it is read (R10): its root `<svg>` must carry `role="img"`
and a non-empty `<title>` as its first child; it must not contain `<script`, an `on*=`
attribute, `<image`, `<foreignObject`, an `href`/`xlink:href` or `url(` that is not a
same-document `#id`, or a literal colour (a `#hex`, `rgb(`, `hsl(` or a named colour
other than `none`, `currentColor`, `inherit` and `transparent`) as the value of `fill`,
`stroke`, `stop-color`, `flood-color` or `color`. The check reads those values from
attributes, from `style` attributes and from any `<style>` element in the file, and strips
`url(#…)` paint references before looking for a colour, so `fill="url(#run-pipeline--fade)"`
passes. Every `id` in a figure file starts with the file's own name and two hyphens
(`run-pipeline--…`; a narrow file's ids start `run-pipeline-narrow--…`), so two figures, or the two forms of one, inlined in one page
never share an id; an unprefixed id is refused. Colours come from classes:
`scripts/site/figures.css` defines a small class vocabulary (`.fig-ink`, `.fig-muted`,
`.fig-line`, `.fig-panel`, `.fig-accent`, `.fig-you`, `.fig-ok`, text sizes) in terms of
`--fig-*` custom properties with fallbacks to the broadsheet properties, so a figure reads
correctly on an article page with no extra work. `figures.css` also sets `fill`, `stroke`
and `color` on `.site-figure svg` from `--fig-ink`/`none`, so an element with no class
inherits a readable colour, never SVG's default black; `landing.css` sets the `--fig-*`
properties for its own two schemes. The build adds `figures.css` to a page's head only
when the page contains a figure.

Legibility at 390 px: a figure whose wide form would shrink its text below about 11 px
has a second file `<name>.narrow.svg`; when it exists the build inlines both and
`figures.css` shows the narrow one at widths up to 600 px and the wide one above. The four
figures: `run-pipeline`, `isolation-boundary`, `gate-ledger`, `wave-of-batches`.
`fr-wave-driver.md` reuses `wave-of-batches`; `fr-exit-gates.md` reuses `gate-ledger`.

The blog-craft renderer receives the Markdown with the `<figure>` block already in place.
python-markdown passes a block-level raw HTML element through unchanged; the
implementation confirms this against the pinned renderer in the `site-build` job and by a
real build before relying on it, and a figure that does not survive rendering intact fails the build: for every figure a
page was given, the exact `<svg …>…</svg>` text the build inserted must appear verbatim in
the rendered page, on the renderer path and on the landing path alike.

### C. Look and motion

`landing.css` is rewritten and defines every custom property the landing uses, for dark
(default) and light (`prefers-color-scheme: light`), including the ones `bar.css` and
`figures.css` read, so on the landing nothing falls back. The landing no longer takes
anything from a renderer-produced page:

- `extract_theme_css`, `THEME_PROPERTIES` and `_defines` are removed, with
  `render_landing`'s `theme_css` parameter. Article pages never used them: `bar.css`
  there reads the renderer's own `:root` with literal fallbacks.
- `extract_font_css` and the `font_css` parameter are removed too. The landing embeds no
  font: headline and body use the system sans-serif stack
  (`ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`), monospace
  details the system monospace stack (`ui-monospace, SFMono-Regular, Menlo, Consolas,
  monospace`), and `landing.css` sets `--display`, `--serif` and `--mono` to those stacks
  so the bar's site name matches. `check_rendered`'s embedded-font requirement applies to
  renderer-produced pages only, and the landing no longer needs to be rendered last.
- Tests that change in `tests/unit/test_build_site.py`: the assertions that the copied
  theme block is in the landing and precedes the light block, the two theme-property
  tests (`test_a_theme_missing_a_property_the_landing_uses_is_refused`,
  `test_every_property_the_site_stylesheets_use_is_a_required_theme_property`) and the
  missing-font refusal are replaced by: every `var(--x)` used without a fallback in
  `landing.css`, and every `var(--x)` in `bar.css` and `figures.css`, names a property
  `landing.css` defines in both schemes; and the rendered landing contains no
  `@font-face`.

Contrast model (R7): text colour tokens (`--text`, `--text-muted`, `--link`) and surface
tokens (`--canvas`, `--surface` for cards and the terminal panel) are opaque literal hex
values in both schemes. Body and link text sits only on those two surfaces: the glass
effect comes from borders, highlights and a glow drawn behind or around a card, never from
a translucent background under text. A unit test computes, per scheme, each text token
against each surface token and asserts at least 4.5:1. Gradient-filled text is used only
for the headline's accent words and the act labels (large text); the test asserts each
gradient stop token reaches at least 3:1 against `--canvas`.

Elements: a hero with an accent-gradient glow behind a terminal panel (window chrome, the
`hero.terminal` lines, a blinking caret on the last prompt); facts as a row of glass
cards; act openers with a large act label; numbered sections as cards with the problem
set as a quote, the figure full width; the grid; the page list; the closing call to
action. Single column under about 720 px.

Motion (R8): each `prompt` line of the terminal is typed out with a `steps()` animation over its width (the line's character count is set by the build as a custom property), and the `out`, `you` and `ok` lines appear in turn after it with `animation-delay`; diagram
accent strokes use a dash-offset animation; cards lift on hover. Content is never hidden
by default and revealed by animation alone: the base state is the visible final state and
animations run from a `from` keyframe, inside `@media (prefers-reduced-motion:
no-preference)`. A `@media (prefers-reduced-motion: reduce)` block also sets
`animation: none` and `transition: none` on everything. A unit test over `landing.css` and
`figures.css` asserts both: every `animation` declaration sits inside a
`prefers-reduced-motion: no-preference` block, and the `reduce` block exists. No `<script>` anywhere on the
page; a unit test asserts the rendered landing contains none and no `url(` or `src`/`href`
asset reference to another host.

### D. Copy

Hero: headline unchanged; a subline covering both acts; facts that do not go stale; a
terminal transcript of a run (the `/fr-goal` command, the workspace, the question round
marked as the operator's, spec and plan reviewed, phases built and reviewed, the pull
request delivered, the merge marked as the operator's).

Sections and their links:

1. The agent cannot touch what it should not → `fr-isolation.md` (figure `isolation-boundary`)
2. It asks you once, then builds from a written spec → `fr-brainstorming-and-plan.md`
3. A separate reviewer reads the work, at every stage → `01-fr-goal.md`
4. One pull request, never self-merged → `01-fr-goal.md`
5. Merged is not done: the exit gates → `fr-exit-gates.md` (figure `gate-ledger`)
6. A backlog, run in waves → `fr-wave-driver.md` (figure `wave-of-batches`)

The "How a run goes" strip stays, with figure `run-pipeline` above it. The grid links
`fr-acceptance.md`, `fr-audit.md`, `fr-debugging.md`, `fr-triage.md` and, for the
supported harnesses (Claude Code, OpenCode, Hermes), `../reference/install.md`. Claims are limited to what the linked pages say (R12); the two
new pages are written first so the act-two sections have pages to cite.

### E. The two new explainers (R11)

Written from the shipped sources, read end to end before writing: for the wave driver,
`plugins/super-fr/skills/fr-triage/SKILL.md`, `packages/fr/src/fr/triage/batch_drive.py`,
`commands/triage_batch_cmd.py`, `docs/cloud-setup.md` and the wave-driver spec; for exit
gates, `packages/fr/src/fr/verification/exit.py`, `commands/gate_cmd.py`,
`scripts/release.py`, `docs/verification-strategies.md`, `docs/exit-gates-release-walk.md`,
`docs/gate-backfill.md` and the exit-gates spec. Each page has `title`, `date`, `tldr`,
`standalone`, `standalone_style: broadsheet`, `covers` and `reviewed`. They are added to
the set of pages `tests/unit/test_tripwire_explainers_fresh.py` asserts are among the parsed
pages (a subset assertion), and appear in the
landing's page list automatically. `docs/explainers/fr-triage.md` and
`docs/explainers/fr-devops-gate.md` each gain one sentence linking the new page.

### F. Tests, workflow and guidance

- `tests/unit/test_build_site.py`: the `act` and `grid` kinds, continuous numbering, each
  new refusal of R10, terminal lines, figure inlining (wide and narrow), the figure checks
  over fixture files and over every file in `scripts/site/figures/`, `figures.css` added
  only to pages with a figure, the contrast test, no script on the landing, and this
  repo's own `index.md` parsing as a landing with two acts, six numbered sections, a grid
  and four figures, all links resolving.
- R9: a unit test builds an article page with no figure and asserts it carries the bar and
  no `figures.css`, and the existing bar tests stay green unchanged; the screenshot state
  `article-page-unchanged` shows it.
- R12 and R13 are checked by the phase reviewer, who is briefed to read each front-page
  section and card against the page it links and to confirm the guidance files describe
  the new kinds; the mirror tripwires (`test_tripwire_opencode_instructions_sync.py`,
  `test_tripwire_hermes_skills_sync.py`) run in CI.
- `pages.yml` already triggers on `scripts/site/**`, which covers `figures/`.
- `.claude/rules/explainers-currency.md`, its mirrors (`scripts/sync-opencode.py`,
  `scripts/sync-hermes.py` where it applies) and `docs/docs-currency.md` describe the new
  kinds, the terminal lines and figures (R13).
- Acceptance: new rows in this feature's fragment; the first pass's row
  `site-front-page-landing` is reworded by an amendment (it names the broadsheet identity,
  which the front page no longer has).

### Non-goals

- Changing the look of article pages, or the blog-craft renderer or its pin.
- JavaScript, web fonts fetched from another host, analytics, search.
- Rewriting existing explainers beyond the two one-sentence links in E.
- Diagrams on existing pages other than the front page.
- Any change to `/acceptance/`.

## Verification

gate: developer
- site-landing-two-acts: none — unit tests in CI parse this repo's `index.md` (two acts, six numbered sections, grid, links resolve); the phase reviewer checks each front-page claim against its linked page (R12) and the guidance (R13); the `site-build` CI job renders it on every pull request; screenshots are taken and opened at implement, review and deliver
- site-landing-figures: none — unit tests in CI check every figure file and the inlining; the `site-build` CI job fails when a figure does not survive rendering; screenshots at implement, review and deliver
- site-landing-look-and-motion: none — unit tests in CI compute the contrast ratios, assert no script and no external reference, assert every animation sits under `no-preference` with a `reduce` block, and assert an article page is built without the figure stylesheet; screenshots in dark, light, phone width and reduced motion at implement, review and deliver
- site-landing-refuses-malformed-figures-and-acts: none — unit tests in CI drive each refusal over fixture sources
- site-wave-driver-and-exit-gates-pages: none — `fr docs check` and the page-parsing tripwire run in CI; the spec reviewer and the phase reviewer check the pages' claims against the code
- site-front-page-second-pass-published: live — only a Pages deploy from `main` shows the published front page

## Test Plan

1. [developer] After merge, wait for the "Deploy explainers to Pages" run on `main`. Open `https://derio-net.github.io/super-fr/`: the new front page loads with its terminal hero and two acts; the four diagrams are drawn; the exit-gates and wave-driver sections open their new pages, each showing its diagram; the top bar returns to the front page; `#explainers` lists both new pages.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-12-front-page-second-pass | `derio-net/super-fr` | `2026-11-12-front-page-second-pass` | — |
