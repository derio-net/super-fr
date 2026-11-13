# Writing standards for super-fr's published docs

- **Branch:** `feat/writing-standards-docs`
- **Date:** 2026-11-13
- **Type:** docs + CI (no `fr` code change)
- **Depends on:** derio-net/blog-craft v0.23.0 (derio-net/blog-craft#105, archived in
  derio-net/blog-craft#108): `tools/validate_writing_standard.py`, the `ste`,
  `elements-of-style` and `plain-language` standards, the `apply-writing-standard`
  procedure and the `fact-keeper` agent.

## Problem

super-fr publishes 32 Markdown pages to https://derio-net.github.io/super-fr: the
explainers, the guides in `docs/*.md` and the reference pages. The only language
guidance they follow is one line in `.claude/rules/explainers-currency.md`: "second
person, concrete, unhurried". Nothing checks it. Sentences are long and uneven.
Measured on 2026-11-13 with blog-craft's checker:

| Group | Pages | `ste` | `plain-language` | `elements-of-style` |
|---|---|---|---|---|
| explainers (`docs/explainers/*.md`) | 15 | 397 FAIL | 1 FAIL, 607 WARN | 0 FAIL, 402 WARN |
| guides (`docs/*.md`) | 9 | 137 FAIL | 1 FAIL, 229 WARN | 0 FAIL, 131 WARN |
| reference (`docs/reference/*.md`) | 8 | 39 FAIL | 0 FAIL, 78 WARN | 0 FAIL, 47 WARN |

The plain-language failures are `docs/explainers/01-fr-goal.md` (23.4 words per
sentence on average) and `docs/cloud-setup.md` (25.7).

blog-craft now ships the tools to fix this: a checker that runs on any Markdown file
with no blog config, three standards, and a rewrite procedure that changes only the
language and proves no fact was lost. super-fr already pins blog-craft for its site
build (`.github/blog-craft.ref`), and its `site-build` CI job already checks it out.

## Operator decisions (2026-11-13, one question per turn)

1. **Standards per page group.** Guides (`docs/*.md`) and reference pages
   (`docs/reference/*.md`) follow `ste`. Explainers (`docs/explainers/*.md`) follow
   `plain-language`. `docs/explainers/why-fr.md`, the argument essay, follows
   `elements-of-style`. The landing page `docs/explainers/index.md` opts out.
2. **Rewrite every page in this feature.** All 31 pages that have a standard are
   rewritten, and explainers get the full plain-language treatment: the warnings are
   addressed, not only the one failure. CI then fails on any FAIL.
3. **Verification: CI plus per-page fact checks.** The checker runs in CI and fails the
   PR on any FAIL. Each rewritten page passes `--preserve-from` against `origin/main` and
   a fact-keeper review. No live walk and no post-merge gate.

## Requirements

R1. Guides (`docs/*.md`) and reference pages (`docs/reference/*.md`) follow `ste`, explainers (`docs/explainers/*.md`) follow `plain-language`, `docs/explainers/why-fr.md` follows `elements-of-style`, and the landing page `docs/explainers/index.md` follows no standard.
R2. One script, `scripts/check-writing-standards.sh <blog-craft-dir>`, holds the page-group mapping and runs blog-craft's `tools/validate_writing_standard.py` over every page `.fr/docs.yaml` names; it exits with the checker's code, so a FAIL fails it and warnings do not.
R3. A page that departs from its group's standard says so in its own front matter (`writing_standard: <name>` or `none`), and only `why-fr.md` and `index.md` do.
R4. Product terms the docs legitimately use (for example `worktree`, `devcontainer`, `fr`, `PR`, `CI`) are listed once in `.writing-standard-terms` at the repo root, which the checker reads; a term is listed only when the standard would otherwise flag a word the page cannot avoid.
R5. `.github/blog-craft.ref` points at a blog-craft commit that ships the checker and the three standards, and every page still renders: CI's `site-build` job passes.
R6. CI's `site-build` job runs `scripts/check-writing-standards.sh` against the pinned blog-craft checkout and fails on any FAIL.
R7. Every page with a standard is rewritten to it, language only: front matter keys, section order, fenced code, inline code, link targets and numerals stay, and the page passes `validate_writing_standard.py --preserve-from origin/main` with no hit.
R8. Every rewritten page gets a fact-keeper review, a read-only agent given only the page as it is on `origin/main` and the rewrite, and no fact it reports `lost` or `changed` stays unresolved; the result is recorded in the plan journal per page.
R9. After the rewrite, no page FAILs its standard, and an explainer keeps a plain-language warning only when the plan journal names the warning and the reason it stays.
R10. `.claude/rules/explainers-currency.md` says which standard each page group follows, how to run the check locally, and replaces its "second person, concrete, unhurried" voice line with the standards; the explainers keep explaining why a mechanism exists.
R11. A unit test pins the `site-build` step, the script's page-group mapping, and the two front-matter exceptions.

## Design

### 1. The script — `scripts/check-writing-standards.sh` (R1–R4)

```bash
scripts/check-writing-standards.sh <blog-craft-dir>
```

It runs the checker once per group, with the group's standard as `--default`, so a
page's own front matter still wins (R3):

```bash
checker="$1/tools/validate_writing_standard.py"
python3 "$checker" --default ste docs/*.md docs/reference/*.md
python3 "$checker" --default plain-language docs/explainers/*.md
```

The globs are the three `pages:` globs of `.fr/docs.yaml`. A page added to one of
those directories is checked with no edit to the script. The script runs every group
before it exits, then exits with the highest code any group returned, so one run shows
every failure. It needs only Python 3 and PyYAML, which the `site-build` job already
installs.

`why-fr.md` carries `writing_standard: elements-of-style` and `index.md` carries
`writing_standard: none`. `fr.docs.model.parse_page` and `scripts/build-site.py`
ignore front matter keys they do not read, so the extra key changes neither the docs
gate nor the landing page.

`.writing-standard-terms` (R4) sits at the repo root. The checker reads it from each
page's git toplevel. One term per line, `#` comments, grouped by why each term is
there.

### 2. The pin and CI (R5, R6)

- `.github/blog-craft.ref` moves from `cdff7a66b4dc383b66aa8e5465d0d978117dd3c0` to `3b0c7d0851f3512bc6bc413af5b5652cf79bd502`, blog-craft `main` after
  v0.23.0. No blog-craft change touched `tools/render_explainer.py` between the two, so
  rendering is unchanged. `site-build` proves it.
- `.github/workflows/ci.yml`'s `site-build` job gains one step after the build:
  `bash scripts/check-writing-standards.sh .blog-craft`. `test_pages_workflow.py`
  already forbids a workflow from naming the SHA; the step reads the checkout the job
  already makes.
- `pages.yml` is unchanged. The deploy builds what the PR already checked.

### 3. The rewrite (R7–R9)

The blog-craft plugin is not installed in the session that runs this feature, so the
rewrite follows blog-craft's `skills/apply-writing-standard/SKILL.md` procedure by hand,
pinned to the same commit as R5:

1. Rewrite a batch of 3 to 5 pages in place, language only.
2. Run the checker on the batch with `--preserve-from origin/main --stats`. Fix every
   FAIL and every `preserve` hit. No check is waived to pass.
3. Review each page with a fact-keeper: a dispatched read-only agent whose instructions
   are blog-craft's `agents/fact-keeper.md`, given the page from `origin/main` (written
   outside the repository) and the rewrite. Fix every `lost` or `changed` fact, or
   record why the change is correct.
4. Record the batch in the plan journal: per page, the sentence count and average
   before and after, the checker result, the fact-keeper counts, and any warning kept
   with its reason (R9).

The baseline is `origin/main`, not `HEAD`, because the branch accumulates rewrites.
Under `ste`, a page's headings may change. A heading that other pages link to keeps
its anchor, or its inbound links are updated in the same batch. The explainers keep
their purpose: they explain why a mechanism exists, in plain language.

### 4. The authoring rule (R10)

`.claude/rules/explainers-currency.md` gains a short section:
- the group-to-standard mapping, and the two exceptions;
- `bash scripts/check-writing-standards.sh <blog-craft-dir>` to check locally, with the
  same blog-craft checkout recipe the rule already gives for previews;
- a pointer to each standard's reference file in blog-craft for the rules themselves.

The "Match the existing voice: second person, concrete, unhurried" paragraph is
replaced. Its intent stays (explain why, for a newcomer), but the standards replace its
style advice. The shipped `plugins/super-fr/rules/docs-currency.md` is not changed:
consumer repos choose their own standards.

### 5. Tests (R11)

`tests/unit/test_pages_workflow.py` (or a sibling `test_writing_standards_docs.py`) pins:
- the `site-build` step;
- the script's two `--default` groups, which match `.fr/docs.yaml`'s page globs;
- the front matter of `why-fr.md` and `index.md`;
- that no other page carries a `writing_standard` key.

## Non-goals

- Changing `fr` or the shipped `docs-currency` rule.
- Installing blog-craft as a plugin, or vendoring its checker into super-fr.
- Pages outside `.fr/docs.yaml`'s globs (specs, plans, journals, README).
- New standards, or changing blog-craft.

## Verification

strategy: none

- writing-standards-docs-groups: none — unit test pins the mapping and the exceptions; CI site-build runs the check
- writing-standards-docs-ci-gate: none — CI site-build runs the script and fails on FAIL; unit test pins the step
- writing-standards-docs-guides: none — CI site-build check over the rewritten guides and reference pages; per-page preserve and fact-keeper evidence in the plan journal
- writing-standards-docs-explainers: none — CI site-build check over the rewritten explainers; per-page preserve and fact-keeper evidence in the plan journal
- writing-standards-docs-authoring-rule: none — reviewed in the PR; the rule's commands are the ones CI runs

## Test Plan

Pre-merge, in CI:

1. `site-build` builds every page with the new pin and runs
   `scripts/check-writing-standards.sh .blog-craft`: no FAIL.
2. The unit test of §5 passes.
3. `fr docs check` passes (every changed page is a covered page that changed).

Per batch, before it is accepted (recorded in the plan journal):

4. `validate_writing_standard.py --preserve-from origin/main --stats` on the batch: no
   FAIL and no `preserve` hit.
5. A fact-keeper review per page: no unresolved `lost` or `changed` fact.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
