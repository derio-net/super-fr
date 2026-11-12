# A front page that draws readers — design

Date: 2026-11-12
Repo: `derio-net/super-fr`

## Background

The published site (https://derio-net.github.io/super-fr) is built from Markdown
sources by `scripts/build-site.py`, which hands every page `.fr/docs.yaml` names to
the pinned blog-craft renderer (`.github/blog-craft.ref`, `--style broadsheet`). That
renderer produces one layout: a single-column article (`<article class="explainer">`
with a title, a date, a `tldr` block and the body). The front page,
`docs/explainers/index.md`, is therefore a long essay ("fr: The Trustworthy Agent")
followed by a list of every page. It reads as a wiki's home page: accurate, and
nothing in it tells a newcomer in ten seconds what fr is or why to read on.

The operator wants a front page that draws readers in, inspired by (not copied from)
a product page built as a hero with a call to action followed by numbered sections
that each go: a problem the reader recognises, a headline, what the reader gains,
briefly how, and a link to the detail.

Facts checked in the code:

- `scripts/build-site.py` `build()` renders each page through `render_page()` and
  checks it with `check_rendered()` (an embedded `@font-face` data URI is required).
- The renderer uses python-markdown with `fenced_code`, `codehilite`, `tables` and
  `sane_lists`; the broadsheet style is dark only and defines its palette as CSS
  custom properties on `:root` (`--ink`, `--paper`, `--brass`, `--display`
  "Fraunces", `--serif` "Newsreader", …), with the fonts embedded as data URIs.
- Every rendered page has exactly one `<body>` open tag followed by
  `<article class="explainer">`.
- `docs/explainers/index.md` is named by tests: `tests/unit/test_build_site.py`
  (route `index.html`), `tests/unit/test_pages_workflow.py` (it links
  `](./acceptance/)`), `tests/unit/test_tripwire_explainers_fresh.py` (it parses with
  `fr.docs`) and `tests/unit/test_tripwire_fr_goal_question_rounds.py` (question-round
  wording).
- The deploy (`.github/workflows/pages.yml`) and the `site-build` CI job run the same
  build command; `pages.yml` triggers on a fixed list of paths.
- `/acceptance/` is rendered by `fr acceptance report`, not by the site build.

## Decisions (operator, 2026-11-12)

1. The front page is rendered by `scripts/build-site.py` itself from a template kept
   in this repo; all other pages keep the blog-craft renderer.
2. The current essay is kept as its own explainer page, linked from the front page.
3. The front page addresses evaluators (people deciding whether an agent's work can
   be trusted). Primary call to action: see how a run works (the fr-goal explainer).
   Install and GitHub are secondary.
4. Structure: hero and call to action, a short "how a run goes" strip, then six to
   eight numbered sections in the rhythm problem → headline → gain → how → link,
   then every page and a closing call to action.
5. Look: the broadsheet identity (its fonts, palette and brass accent) at landing
   scale, following the reader's light or dark setting.
6. Scope: the front page plus one shared top bar on every built page. The other
   pages' own text is not rewritten.
7. Verification: unit tests, the CI site build and screenshots before merge; one
   post-merge Test Plan row for the published site; gate `developer` (holds nothing).
8. Models: mechanical → haiku, standard → sonnet, hard → opus (Claude Code).

## Requirements

R1. The site's front page (`index.html`) is a landing page that `scripts/build-site.py` renders itself from `docs/explainers/index.md` and a template kept in this repo; it is not passed to the blog-craft renderer.
R2. The front page opens with a hero: a short eyebrow, a headline, a subline, an example `/fr-goal` command, a primary button to the fr-goal explainer and secondary links to the install guide and the GitHub repository, followed by a strip of short facts (a figure and a caption each).
R3. The front page shows how a run goes as a strip of ordered steps, and marks the steps that are the operator's.
R4. The front page has six to eight numbered sections; each has a problem the reader recognises, a headline, what the reader gains, how fr does it, and one link to the page that explains it. The build assigns the numbers ("01 / 07").
R5. The front page lists every other page, grouped as Explainers, Guides and Reference under the anchors `#explainers`, `#guides` and `#reference`, links the acceptance report (`./acceptance/`), and ends with a closing call to action.
R6. The front page uses the broadsheet identity: the embedded fonts and the dark palette are taken from a page the renderer produced in the same build, so they cannot differ from the other pages; it has a light palette under `prefers-color-scheme: light`, no horizontal scrolling at a 390 px wide viewport, no JavaScript and no request to another host.
R7. The current essay is kept, with its content, as the explainer `docs/explainers/why-fr.md`; the front page links to it, and it no longer carries the list of every page.
R8. Every page the build writes, the front page included, has the same top bar: the site name linking to the front page, links to the front page's Explainers, Guides and Reference anchors, and a link to the GitHub repository; its links are correct from every route (`x.html`, `guides/x.html`, `reference/x.html`).
R9. The build fails (exit 1, naming the page and the defect) and writes no degraded page when: the front page's front matter lacks a required hero key; `layout: landing` is set on a page that is not routed to `index.html`; a section names an unknown kind; a numbered section lacks its problem, or its link; there are fewer than six or more than eight numbered sections; the run strip is not exactly one ordered list; the page-list section lacks its marker; the top bar cannot be inserted at exactly one place in a rendered page; or the front page has no embedded font.
R10. Every relative link on the front page, in its body and in its front matter, goes through the build's one link rule (another page's source becomes its route, another tracked file a GitHub link at the built commit, an untracked path fails the build).
R11. A change to the front-page template deploys the site: `pages.yml` triggers on the template's directory, and the `site-build` CI job builds the front page on every pull request.
R12. The repo's guidance for page authors (`.claude/rules/explainers-currency.md` and its generated mirror, `docs/docs-currency.md` where it describes the index) says how the front page is authored, and every claim on the front page is one an explainer or guide it links to already makes.

## Design

### A. Source: `docs/explainers/index.md` stays the front page's source

Keeping the path keeps the route (`index.html`), `.fr/docs.yaml`, `fr docs check`
(front matter with `title`, `tldr`, `covers`, `reviewed`) and every test that names
the file. Its front matter gains `layout: landing` and the hero data:

```yaml
---
title: "fr: agent work you can merge"
tldr: |
  …
standalone: true
standalone_style: broadsheet
layout: landing
hero:
  eyebrow: "super-fr"
  headline: "…"
  subline: "…"
  command: "/fr-goal add rate limiting to the webhook receiver"
  primary: {label: "See how a run works", href: "01-fr-goal.md"}
  secondary:
    - {label: "Install", href: "../reference/install.md"}
    - {label: "GitHub", href: "https://github.com/derio-net/super-fr"}
facts:
  - {figure: "1", caption: "question round before the build"}
covers: […]
reviewed: 2026-11-12 …
---
```

Required hero keys: `headline`, `subline`, `primary.label`, `primary.href`.
`eyebrow`, `command`, `secondary` and `facts` are optional. `layout` is read by the
build only; a page without it (or with any other value than `landing`) is rendered by
blog-craft as today, and `layout: landing` on any page other than the one routed to
`index.html` fails the build.

The body is Markdown split at its `## ` headings. A line `<!-- landing:<kind> -->`
directly under a heading names the section's kind:

| Kind | Body shape | Rendered as |
|---|---|---|
| `flow` | one ordered list; an item starting with `{you}` is the operator's | the step strip (R3); `{you}` is removed from the text and the step is marked |
| `guarantee` | first blockquote = the problem; last paragraph, holding only one link = the link; the rest = gain and how | a numbered section (R4) |
| `pages` | optional prose, then the `<!-- site:pages -->` marker | the grouped page list with its three anchors (R5) |
| `cta` | paragraphs; a paragraph holding only links is rendered as buttons | the closing call to action |
| none | any Markdown | a plain prose section |

Any other kind fails the build (R9). The section heading is the section's headline.
Markdown is converted with python-markdown and the renderer's extension list
(`fenced_code`, `codehilite`, `tables`, `sane_lists`). `markdown` is present only in
the isolated environment the deploy and the `site-build` job run the build in
(`--with markdown`), not in the test environment, so `build-site.py` imports it
lazily, inside the build, and every landing function takes the converter as an
argument (`to_html`). Unit tests pass a stand-in converter and assert on structure,
never on converted or highlighted markup; the real conversion is exercised by the
`site-build` job.

### B. Rendering: `scripts/site/`

- `scripts/site/landing.html` — the page skeleton with named placeholders.
- `scripts/site/landing.css` — the landing styles: a light set of the broadsheet
  custom properties under `@media (prefers-color-scheme: light)` and a fluid layout
  (single column under ~720 px). It does not define the dark palette.
- `scripts/site/bar.css` — the top bar's styles, used on every page.

`build-site.py` gains pure functions, tested without the renderer: parse the landing
source into sections (raising `BuildError` for each R9 defect), render each kind to
HTML, assemble the page. The page list on the landing is built from the same
`Entry` list as `fill_pages`, as HTML with `id="explainers"`, `id="guides"`,
`id="reference"` on the group headings. `fill_pages` keeps its Markdown behaviour for
any other page that carries the marker.

Fonts and dark palette: the landing embeds the `@font-face` rules and the `:root`
custom-property block the blog-craft renderer emitted for another page of the same
build (extracted from that page's HTML; a page with neither fails the build), so the
landing can never use different font files or different dark colours, also after the
renderer pin moves; `check_rendered` then applies to the landing as to
every page. The build renders the landing after the other pages for that reason.

Links (R10): the body goes through `rewrite_markdown` before conversion, and each
front-matter `href` through `rewrite_href`, both with `index.md` as the linking page.

### C. The top bar (R8)

Pages are rendered into a temporary directory, never straight into the output
directory (today `render_page` writes the final file before `check_rendered` runs).
After a page is rendered (by blog-craft or by the landing renderer) and has passed
`check_rendered`, the build inserts the bar's `<style>` before `</head>` and a `<nav class="site-bar">` directly
after the `<body>` open tag. If either anchor is not found exactly once the build
fails (R9): a renderer change must not silently drop the bar. Only then is the page
written to its route, so a refused page leaves no file there. Links are relative to
the page's route: home is `index.html` (or `../index.html`), the groups are
`index.html#explainers` and so on, GitHub is `--repo-url`. The bar uses the page's
own custom properties with fallbacks, so it matches both the dark article pages and
the landing in either scheme. It is not sticky and needs no JavaScript.

`/acceptance/` is rendered by `fr acceptance report` and gets no bar (non-goal).

### D. The essay moves to `why-fr.md`

`git mv docs/explainers/index.md docs/explainers/why-fr.md`, then a new `index.md`.
`why-fr.md` keeps the essay's `tldr`, `covers` and body, is retitled "Why fr: the
trustworthy agent" (the front page takes over the "fr: …" title), drops the "Every
page" section and its marker, and has its `reviewed` stamp bumped. The question-round
wording tripwire covers `why-fr.md` as well as `index.md`. Links that pointed
to the index for the essay's content are re-pointed: `README.md`'s "Start here" link
to the published `index.html` ("the pipeline and why it is trustworthy") goes to
`why-fr.html`. `docs/explainers/fr-isolation.md`'s closing "Back to the fr overview"
link stays on `index.md`: the front page is the overview.

### E. Front-page copy

Written for a reader deciding whether to trust an agent's pull request, in the
explainers' voice (second person, concrete), and limited to claims the linked page
makes (R12). Numbered sections, each linking one page:

1. The agent cannot touch what it should not → `fr-isolation.md`
2. It asks you once, then builds from a written spec → `fr-brainstorming-and-plan.md`
3. A second agent reads the work cold, at every stage → `01-fr-goal.md`
4. Proof that stays honest: the acceptance matrix → `fr-acceptance.md`
5. One pull request, never self-merged; the risky step stays yours → `fr-devops-gate.md`
6. A trail you can read afterwards, with its cost → `fr-audit.md`
7. From one goal to a backlog: triage and dispatch → `fr-triage.md`

The facts strip uses facts that do not go stale with each release (one question
round, one pull request per goal, zero self-merges, three harnesses), not counts read
from the acceptance matrix.

### F. Workflow, tests and guidance

- `pages.yml` `on.push.paths` gains `scripts/site/**`; `tests/unit/test_pages_workflow.py` pins it.
- `tests/unit/test_build_site.py` gains the landing parser, each R9 refusal, the
  section numbering, the page-list anchors, link rewriting of front-matter hrefs and
  bar insertion per route depth; and a test that this repo's own `index.md` parses as
  a valid landing with six to eight numbered sections whose links all resolve.
- `.claude/rules/explainers-currency.md` describes the landing source format; its
  OpenCode mirror is regenerated with `scripts/sync-opencode.py`.
  `docs/docs-currency.md` is updated where it describes the index, and its `covers`
  gains `scripts/site/**`, so a template change flags the guide that describes it.

### Non-goals

- Rewriting the text of the other explainers, guides or reference pages.
- A landing style in `derio-net/blog-craft`, or moving the renderer pin.
- A bar, or any change, on `/acceptance/`.
- Search, analytics, JavaScript, animation.
- A light scheme for the blog-craft-rendered pages.

## Verification

gate: developer
- site-front-page-landing: none — unit tests in CI parse this repo's `index.md` as a landing; the `site-build` CI job renders it on every pull request; screenshots are taken and opened at implement, review and deliver
- site-landing-build-refuses-malformed: none — unit tests in CI drive each refusal over fixture sources
- site-top-bar-every-page: none — unit tests in CI insert the bar at each route depth; the `site-build` CI job fails when a page cannot take it; screenshots at implement, review and deliver
- site-why-fr-essay-kept: none — `fr docs check` and the page-parsing tripwire run in CI
- site-front-page-published: live — only a Pages deploy from `main` shows the published front page

## Test Plan

1. [developer] After merge, wait for the "Deploy explainers to Pages" run on `main`. Open `https://derio-net.github.io/super-fr/`: the landing page loads with its hero; the primary button opens the fr-goal explainer; the top bar on that explainer returns to the front page; `#explainers` lists every page; `/why-fr.html` and `/acceptance/` load.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-12-landing-front-page | `derio-net/super-fr` | `2026-11-12-landing-front-page` | — |
