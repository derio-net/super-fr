---
title: "Docs currency: keep pages true to the code"
tldr: |
  A page names the paths it describes, and a check fails any pull request that changes
  one of those paths without touching the page. This guide covers the config, the
  front matter, the stamp, wiring the check into CI, and how this repo turns its pages
  into a website.
standalone_style: broadsheet
covers:
  - packages/fr/src/fr/docs/**
  - packages/fr/src/fr/commands/docs_cmd.py
  - plugins/super-fr/rules/docs-currency.md
  - .claude/rules/explainers-currency.md
  - scripts/build-site.py
  - scripts/site/**
  - .fr/docs.yaml
  - .github/workflows/pages.yml
reviewed: 2026-11-13 writing-standards-docs phase 1, explainers-currency now names each page group's writing standard; this page still defers authoring detail to that rule
---

# Docs currency: keep pages true to the code

Documentation goes stale in one specific way. Someone changes behaviour, and the page that
described it is not in the diff. Nobody sees this, and the page quietly starts to lie. A
reviewer cannot find this in the diff, because the page is not in it.

`fr docs check` closes that gap mechanically. Each page declares the paths it describes. When a
pull request changes one of those paths and does not change the page, the check fails and names
both. You then either update the page, or, when it is still true, update its `reviewed` stamp
to say you looked. Either way the page appears in the diff, so a reviewer sees it.

A repo with no `.fr/docs.yaml` owes nothing, and `fr docs check` says so and exits 0.

## Adopt it in your repo

1. Make `.fr/docs.yaml` with a `pages` list (next section).
2. Give one page front matter with `covers` and `reviewed` (the section after).
3. `git add` both. The check reads tracked files only.
   For the check, a new page or a new covered file does not exist until you add it.
4. Run `fr docs check`. On a feature branch it compares with the default branch; fix what it
   names.
5. Add the CI job from "Where it runs", so the check runs on every pull request.

## The config

`.fr/docs.yaml` takes two keys, both lists of path globs relative to the repo root:

```yaml
pages:
  - docs/explainers/*.md
  - docs/*.md
  - docs/reference/*.md
must_cover:
  - plugins/*/skills/*/SKILL.md
```

- **`pages`** selects the Markdown files that are pages. A config whose globs select no tracked
  file is a usage error (exit 2), never a clean pass: a typo would otherwise disable the gate.
- **`must_cover`** names files that some page must cover. The check lists each file that matches
  and that no page covers. So a new skill without a page fails. It is optional.

Globs are segment-aware: `*` and `?` stay inside one path segment, and `**` spans segments. So
`docs/*.md` does not reach `docs/superpowers/x.md`, and `packages/fr/src/fr/docs/**` reaches
everything below that directory.

## The front matter

A page opens with a YAML block. The check reads two keys; the rest is for the site build:

```yaml
---
title: "fr-isolation: the sandbox an agent can't walk out of"
tldr: |
  One or two sentences. The index page shows the first.
standalone_style: broadsheet
covers:
  - plugins/super-fr/skills/fr-isolation/SKILL.md
  - packages/fr/src/fr/isolation/**
reviewed: 2026-11-11 checked against the rule after the HEAD-drift change
---
```

- **`covers`** is a list of globs that name the skill and the code the page describes. Choose them as
  a reader would: if a change here could make the page wrong, it belongs. A glob that matches no
  tracked file fails the check (a `dead-glob`), which is how a renamed directory gets noticed.
- **`reviewed`** is an ISO date and a one-line note. It is your stamp.

A page with no front matter, unreadable YAML, or no `covers` or `reviewed` is a `bad-page` finding.

## What the check reports

```bash
fr docs check                              # against the remote's default branch
fr docs check --base origin/main           # against a ref you name
fr docs status [--json]                    # every page, what it covers, its stamp
```

Exit 0 is clean, 1 is findings, 2 is a usage or environment error. It never writes. The findings:

| Finding | Meaning |
|---|---|
| `stale` | a covered path changed in the diff and the page did not |
| `dead-glob` | a `covers` glob matches no tracked file |
| `bad-page` | the front matter is missing or unusable |
| `uncovered` | a `must_cover` file that no page covers |

The diff is from the merge base to HEAD. With no `--base`, the base is the remote's default
branch. fr reads it locally, without a network call. It reads `origin/HEAD`, or else the first
of `origin/main`, `master`, `trunk` or `develop` that exists. Sometimes there is no diff to
judge: with no `--base` on the default branch itself, or when HEAD is the merge base. Then
only the structural checks (`bad-page`, `dead-glob`, `uncovered`) run.

## The stamp: when the page is still true

Say you refactor a module a page covers and nothing the page says has changed. Do not invent an edit.
Update the stamp:

```yaml
reviewed: 2026-11-12 module split into two files; the page's description still holds
```

Any change to the page file satisfies the check, so the note is the part that matters. The next
person reads it to know that someone checked. A stamp written by someone who did not read the page
is the one way to defeat this gate, and no tool can stop it.

## Where it runs

- **fr-goal's `deliver`** derives a `docs` witness itself (it is never passed). It does not
  finish while `fr docs check` fails, and it prints the check's own output.
- **fr-debugging** runs it before it opens the fix PR.
- **A shipped rule**, `docs-currency`, states the obligation for every harness.
- **CI is the gate no flow can skip.** In a GitHub Actions job:

  ```yaml
  docs-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0          # the diff needs the merge base
      # install fr however your repo does, then:
      - name: Pages covering a changed path changed too
        if: github.event_name == 'pull_request'
        run: fr docs check --base "origin/${{ github.base_ref }}"
      - name: Pages are well formed and cover what they claim
        if: github.event_name != 'pull_request'
        run: fr docs check
  ```

  Fetch the checkout's full history (`fetch-depth: 0`). A shallow clone cannot compute the merge
  base, and the check then says so; it does not pass. Add the job to any aggregate check that your
  repo needs.

`fr docs` never writes and runs even when the repo's artifacts are stale, so it works as the very
first step of a job.

## How this repo builds its site

The pages you read are Markdown sources only. No rendered HTML is committed. A push to the
default branch can touch a page, the config, the build script or the renderer pin. On each such
push, `.github/workflows/pages.yml` runs `scripts/build-site.py`, which:

1. reads `.fr/docs.yaml` (it shares no code with `fr`, so the deploy needs no `fr` to build pages);
2. renders each page with the `blog-craft` renderer, in the broadsheet style with embedded fonts.
   The build uses the renderer at the one commit named in `.github/blog-craft.ref`.
   The front page is the one exception: `docs/explainers/index.md` carries `layout: landing`.
   The build renders that page itself from `scripts/site/`, with its own dark and light look and no embedded font.
   Acts, a card grid and a terminal of `hero.terminal` lines are kinds of that source.
   The explainers-currency rule gives the rules to write it;
3. writes each page to its route: `docs/explainers/x.md` at the site root, `docs/x.md` under
   `guides/`, `docs/reference/x.md` under `reference/`;
4. rewrites relative links. A link to another page's source becomes that page's route.
   A link to any other tracked file becomes a GitHub link at the built commit.
   A link to a path that git does not track **fails the build**;
5. fills a `<!-- site:pages -->` marker with a list of every page, grouped by section.
   Each entry comes from the page's `title` and the first sentence of its `tldr`.
   On the front page, these are the Explainers, Guides and Reference lists that the top bar links to;
6. places each figure (below), then gives every page the same top bar.
   The bar has a link home, links to the three lists and a link to GitHub.
   The build does not write a page that it cannot put the bar on.

CI runs the same build on every pull request (the `site-build` job). So a page that does not
render, or that links to nothing, fails before merge.

### Figures

A diagram is an SVG file in `scripts/site/figures/`. A line of its own in a page's Markdown,
`<!-- site:figure <name> -->`, places it. This also works in the front page's sections.
`<name>` is `[a-z0-9-]+`, and the build leaves a marker inside a fenced block alone.

The build inlines the file as a `<figure class="site-figure">` before the renderer runs. It
fails the page if the renderer changes the SVG, or if the file is not there. Each file:

- carries `role="img"` and a non-empty `<title>` as its first child;
- runs no script, and refers to nothing outside the page;
- takes every colour from a class in `scripts/site/figures.css`, never a literal colour.

The classes are `fig-ink`, `fig-muted`, `fig-line`, `fig-panel`, `fig-panel-fill`, `fig-accent`,
`fig-accent-line`, `fig-you`, `fig-you-line`, `fig-ok`, `fig-ok-line`, `fig-flow`, `fig-text`,
`fig-small` and `fig-big`. Every `id` starts with the file's name and two hyphens
(`gate-ledger--arrow`).

The text of a figure can fall below about 11 px on a phone. Such a figure has a second file,
`<name>.narrow.svg`, whose ids start with `<name>-narrow--`. The stylesheet shows the narrow file
up to 860 px wide, or up to 1079 px inside an article page. Only a page with a figure gets
`figures.css`.

### Write a page that builds

- Use inline Markdown links. A relative image, a reference-style link definition and a raw HTML
  `href` fail the build. Absolute URLs are fine.
- Fence all code, and name the language. Link to sibling pages with relative `.md` paths.
- The build drops a `# H1` that opens the body of an article page, because the renderer prints the title
  itself. Keep it in the source, so that the file reads well on GitHub.
- To preview, build into a directory outside the repo:

  ```bash
  uv run --isolated --no-project --with markdown --with pyyaml python \
    scripts/build-site.py /tmp/site --blog-craft /path/to/blog-craft-checkout
  ```

  `--isolated` matters: without it a pygments install elsewhere on the machine changes how code
  blocks render.

## Limits

- The check proves that a page was *touched*, not that it is *right*. It makes a stale page visible
  in the diff. A human must still judge the prose.
- Coverage is only as good as the `covers` globs. A page that covers too little goes stale quietly;
  one that covers too much trains people to stamp a page that they did not read.
- Cover the code and the schema a page describes, never a data file that changes in routine work
  (a registry, a ledger, a lockfile). Such a file makes the page stale in every pull request that
  touches it, whatever the page says.
- When you rename or move a covered file, every page that covered it gets a `stale` finding. If the
  glob named the old path, the page also gets a `dead-glob`. That is the point.

## Where to go next

- [The front page](explainers/index.md) shows a finished front-page source; [why fr](explainers/why-fr.md) is the long essay it links to.
- [fr-isolation](explainers/fr-isolation.md) is a good example of a page with a long `covers` list.
- [fr-debugging](explainers/fr-debugging.md) shows where the check runs before a fix is delivered.
