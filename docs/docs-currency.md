---
title: "Docs currency: keeping pages true to the code"
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
reviewed: 2026-11-12 front page is rendered by the build itself; every page has a top bar; pages.yml's acceptance-fragments visibility gate is still true for this page
---

# Docs currency: keeping pages true to the code

Documentation goes stale in one specific way: someone changes behaviour, the page that
described it is not in the diff, nobody notices, and the page quietly starts to lie. A
reviewer cannot catch this by reading the diff, because the page is not in it.

`fr docs check` closes that gap mechanically. Each page declares the paths it describes. When a
pull request changes one of those paths and does not change the page, the check fails and names
both. You then either update the page, or, when it is still true, update its `reviewed` stamp
to say you looked. Either way the page appears in the diff, so a reviewer sees it.

A repo with no `.fr/docs.yaml` owes nothing, and `fr docs check` says so and exits 0.

## Adopting it in your repo

1. Create `.fr/docs.yaml` with a `pages` list (next section).
2. Give one page front matter with `covers` and `reviewed` (the section after).
3. `git add` both. The check reads tracked files only, so a new page or a new covered file
   does not exist for it until it is added.
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
- **`must_cover`** names files that some page must cover. The check lists every matching file no
  page covers, so adding a skill without a page fails. It is optional.

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

- **`covers`** is a list of globs naming the skill and the code the page describes. Choose them as
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

The diff is from the merge base to HEAD. With no `--base`, the base is the remote's default branch,
read from the local `origin/HEAD` without any network call. With no `--base` on the default branch
itself, or whenever HEAD is the merge base, there is no diff to judge, so only the structural checks (`bad-page`, `dead-glob`,
`uncovered`) run.

## The stamp: when the page is still true

Say you refactor a module a page covers and nothing the page says has changed. Do not invent an edit.
Update the stamp:

```yaml
reviewed: 2026-11-12 module split into two files; the page's description still holds
```

Any change to the page file satisfies the check, so the note is the part that matters: it is what the
next person reads to know someone checked. Writing a stamp without reading the page is the one way to
defeat this gate, and no tool can stop it.

## Where it runs

- **fr-goal's `deliver`** derives a `docs` witness itself (it is never passed) and refuses to finish
  while `fr docs check` fails, printing the check's own output.
- **fr-debugging** runs it before opening the fix PR.
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

  Fetch the checkout's full history (`fetch-depth: 0`): a shallow clone cannot compute the merge base and the check will
  say so rather than pass. Add the job to whatever aggregate check your repo requires.

`fr docs` never writes and runs even when the repo's artifacts are stale, so it works as the very
first step of a job.

## How this repo builds its site

The pages you are reading are Markdown sources only. No rendered HTML is committed. On every push
to the default branch that touches a page, the config, the build script or the renderer pin,
`.github/workflows/pages.yml` runs `scripts/build-site.py`, which:

1. reads `.fr/docs.yaml` (it shares no code with `fr`, so the deploy needs no `fr` to build pages);
2. renders each page with the `blog-craft` renderer, checked out at the one commit named in
   `.github/blog-craft.ref`, using the broadsheet style with embedded fonts. The one exception is
   the front page: `docs/explainers/index.md` carries `layout: landing`, and the build renders it
   itself from `scripts/site/`, copying the fonts and the dark palette from a page the renderer
   produced in the same build;
3. writes each page to its route: `docs/explainers/x.md` at the site root, `docs/x.md` under
   `guides/`, `docs/reference/x.md` under `reference/`;
4. rewrites relative links: a link to another page's source becomes that page's route, a link to
   any other tracked file becomes a GitHub link at the built commit, and a link to a path git does
   not track **fails the build**;
5. fills a `<!-- site:pages -->` marker with a list of every page, grouped by section, from their
   `title` and the first sentence of `tldr` (on the front page, as the Explainers, Guides and
   Reference lists the top bar links to);
6. gives every page the same top bar, a link home, links to the three lists and a link to GitHub,
   and refuses to write a page it cannot put the bar on.

CI runs the same build on every pull request (the `site-build` job), so a page that does not render,
or links to nothing, fails before merge.

### Writing a page that builds

- Use inline Markdown links. A relative image, a reference-style link definition and a raw HTML
  `href` fail the build. Absolute URLs are fine.
- Fence all code, and name the language. Link to sibling pages with relative `.md` paths.
- The build drops a leading `# H1` in a guide because the renderer prints the title itself; keep it
  in the source so the file reads well on GitHub.
- To preview, build into a directory outside the repo:

  ```bash
  uv run --isolated --no-project --with markdown --with pyyaml python \
    scripts/build-site.py /tmp/site --blog-craft /path/to/blog-craft-checkout
  ```

  `--isolated` matters: without it a pygments install elsewhere on the machine changes how code
  blocks render.

## Limits

- The check proves a page was *touched*, not that it is *right*. It makes a stale page visible in the
  diff; judging the prose is still a human's job.
- Coverage is only as good as the `covers` globs. A page that covers too little goes stale quietly;
  one that covers too much trains people to stamp without reading.
- Cover the code and the schema a page describes, never a data file that changes in routine work
  (a registry, a ledger, a lockfile). Such a file makes the page stale in every pull request that
  touches it, whatever the page says.
- Renaming or moving a covered file is a `stale` finding on every page that covered it (and a
  `dead-glob` if the glob named the old path), which is the point.

## Where to go next

- [The front page](explainers/index.md) shows a finished landing source; [why fr](explainers/why-fr.md) is the long essay it links to.
- [fr-isolation](explainers/fr-isolation.md) is a good example of a page with a long `covers` list.
- [fr-debugging](explainers/fr-debugging.md) shows where the check runs before a fix is delivered.
