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
`standalone_style: broadsheet`, `covers` and `reviewed`. The index lists every other page
at the `<!-- site:pages -->` marker, from their `title` and the first sentence of `tldr`.
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
- `tests/unit/test_build_site.py` — routes, link rewriting and the index list; this repo's
  `/`, `/01-fr-goal.html` and `/fr-isolation.html` stay published.
- `tests/unit/test_pages_workflow.py` — the deploy's triggers, the build step and the pin.
- `tests/unit/test_tripwire_fr_goal_question_rounds.py` — the question-round wording on
  `01-fr-goal.md` and `index.md`.
