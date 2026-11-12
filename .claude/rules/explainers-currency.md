# Explainers currency — the published site is built from sources

## Rule

`docs/explainers/`, the guides in `docs/*.md` and `docs/reference/` are published to
**https://derio-net.github.io/super-fr** by `.github/workflows/pages.yml`. They are
**Markdown sources only**: no rendered HTML is committed, and none is hand-authored.
`scripts/build-site.py` renders every page `.fr/docs.yaml` names at deploy time, with
the `derio-net/blog-craft` renderer pinned in `.github/blog-craft.ref`.

**A PR that changes behaviour a page describes updates that page in the same PR**,
or bumps its `reviewed` stamp with a note saying it is still true. The gate is
`fr docs check` (CI job `docs-check`; `fr docs status` shows what is covered): each
page's front matter names the paths it `covers`, and the PR fails when a covered path
changed and the page did not. The shipped rule `docs-currency` lists the triggers; a skill's pipeline, a CLI verb an
explainer names, a shipped default and a minor or major bump are the usual ones.

Internal refactors, test-only changes and anything invisible to a reader who does not
work on this repo are not triggers. The test is whether a newcomer reading the page
would now be misled.

## What there is to edit

Only the `.md`. There is nothing to regenerate and nothing to commit beside it:
`docs/explainers/*.html` is git-ignored and `tests/unit/test_tripwire_explainers_fresh.py`
fails if one is tracked. A page needs front matter with `title`, `tldr`,
`standalone_style: broadsheet`, `covers` and `reviewed`. Every built page, the front page included, carries a top bar
(`scripts/site/bar.css`): the site name, links to the front page's Explainers, Guides and
Reference lists, and GitHub. `why-fr.md` is the long essay on why fr is trustworthy.

**The front page** is `docs/explainers/index.md` with `layout: landing`. It is not rendered by
blog-craft: `scripts/build-site.py` renders it from `scripts/site/landing.html` and
`landing.css`, which define the page's own dark and light look. The landing embeds no font and
takes nothing from a rendered page; article pages keep the broadsheet look. Its front matter
carries `hero` (`headline`, `subline` and `primary: {label, href}` are required; `eyebrow`,
`command` and `secondary` are optional, and `terminal` is an optional list of `{kind, text}`
lines with `kind` one of `prompt` (typed out), `out`, `you` (a point where the operator acts)
and `ok`; with it the terminal panel replaces the single `command` line) and `facts` (`figure`
and `caption`). The body is split at `## ` headings, and a `<!-- landing:<kind> -->` line under
a heading names the section: `flow` (one ordered list, `{you}` marks the operator's steps),
`act` (an act opener: the heading and its introduction; the build labels the acts in order, and
every `guarantee` after one belongs to it until the next), `guarantee` (a blockquote problem,
the gain and how, and a last paragraph holding exactly one link; six to eight of them, numbered
across acts by the build), `grid` (optional prose, then one list of three to eight cards, each
`**Title.** one sentence [label](href)` with exactly one link), `pages` (needs the
`<!-- site:pages -->` marker), `cta`, or none for plain prose. A line `<!-- site:figure <name> -->`
on its own places a diagram from `scripts/site/figures/` on any page, and in a `flow`,
`guarantee` or prose section of the landing (one per section; an `act`, `grid`, `pages` or `cta`
refuses it). A figure file has an accessible name (`role="img"` and a `<title>`), runs no script,
refers to nothing outside the page, takes its colours from the classes of `figures.css` rather
than literal values, prefixes its ids with the file's name and two hyphens, and has a
`<name>.narrow.svg` when its text would fall under about 11 px on a phone. A claim on the front
page must be one the page it links to already makes. The build fails, naming the page, on a
missing hero key, an unknown kind, an unknown terminal kind, an act with no numbered section, a
malformed card or grid, a missing or unsafe figure, a link to an untracked path, `layout:
landing` anywhere but the page routed to `index.html`, a renderer page with no embedded font, or
one that cannot take the top bar. A change under `scripts/site/` deploys the site.
A relative link to another page's `.md` becomes its route; a link to any other tracked file
becomes a GitHub link at the built commit; a link to a path git does not track fails the
build. `./acceptance/` is the one site route a page may name directly.

Match the existing voice: second person, concrete, unhurried, explaining *why* a mechanism
exists rather than only what it does, for a reader who has never seen this repo.

## Previewing a page locally

CI builds the whole site on every pull request (`site-build`), so a page that does not
render fails before merge. To see it first, check the pinned renderer out and build into a
directory outside the repo:

```bash
mkdir -p /tmp/bc && git -C /tmp/bc init -q && git -C /tmp/bc fetch -q --depth 1 \
  https://github.com/derio-net/blog-craft "$(cat .github/blog-craft.ref)" \
  && git -C /tmp/bc checkout -q FETCH_HEAD
uv run --isolated --no-project --with markdown --with pyyaml python \
  scripts/build-site.py /tmp/site --blog-craft /tmp/bc
```

A single page can be rendered with the renderer itself,
`tools/render_explainer.py <page>.md --style broadsheet --embed-fonts -o <out>.html`, but
run it **from a directory outside the repo and with `--isolated`**: inside the repo `uv`
leaks the project venv's `pygments` (and a machine with a global one leaks it too) into the
render, which flips markdown's code highlighting and rewrites every code block. The build
script does not need either precaution; it only runs the renderer.

## Moving the pin

`.github/blog-craft.ref` is one line, a full commit SHA, and both `pages.yml` and the
`site-build` job read it; no workflow may name the SHA itself
(`tests/unit/test_pages_workflow.py`). To move it, change that one line, build locally,
and look at the pages: a renderer change shows up in every page at once.

## Enforcement

- `fr docs check` — the currency gate, in CI and at `deliver`.
- `tests/unit/test_tripwire_explainers_fresh.py` — no rendered explainer is tracked, and
  every configured page parses with `fr.docs`.
- `tests/unit/test_build_site.py` — routes, link rewriting, the landing parser and its refusals,
  the landing and top-bar renderers, and that this repo's own `index.md` is a valid landing;
  `/`, `/01-fr-goal.html` and `/fr-isolation.html` stay published.
- `tests/unit/test_pages_workflow.py` — the deploy's triggers, the build step and the pin.
- `tests/unit/test_tripwire_fr_goal_question_rounds.py` — the question-round wording on
  `01-fr-goal.md` and `index.md`.
