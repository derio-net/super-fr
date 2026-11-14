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
4. **Accuracy, now and later.** Asked whether the rewrite works from the code or the
   prose, the operator chose: "I want the documents to be (and stay) accurate". So every
   page is first checked against the code it covers and corrected, as its own visible
   step, before its language is rewritten; and a repo review lens keeps later changes to
   a page honest against the code.

## Requirements

R1. Guides (`docs/*.md`) and reference pages (`docs/reference/*.md`) follow `ste`, explainers (`docs/explainers/*.md`) follow `plain-language`, `docs/explainers/why-fr.md` follows `elements-of-style`, and two pages follow no standard: the landing page `docs/explainers/index.md`, and `docs/reference/cli.md`, whose command tree is generated from `fr`'s help text.
R2. One script, `scripts/check-writing-standards.sh <blog-craft-dir>`, holds the page-group mapping and runs blog-craft's `tools/validate_writing_standard.py`, with PyYAML provided by `uv run --isolated --no-project --with pyyaml`, over every page `.fr/docs.yaml` names, from the repository root whatever the caller's directory; it exits with the highest code any group returned, so a FAIL fails it and warnings do not.
R3. A page that departs from its group's standard says so in its own front matter (`writing_standard: <name>` or `none`), and only `why-fr.md`, `index.md` and `cli.md` do.
R4. Product terms the docs legitimately use (for example `worktree`, `devcontainer`, `fr`, `PR`, `CI`) are listed once in `.writing-standard-terms` at the repo root, which the checker reads; a term is listed only when the standard would otherwise flag a word the page cannot avoid.
R5. `.github/blog-craft.ref` points at a blog-craft commit that ships the checker and the three standards, and every page still renders: CI's `site-build` job passes.
R6. CI's `site-build` job runs `scripts/check-writing-standards.sh` against the pinned blog-craft checkout and fails on any FAIL.
R7. Every page with a standard is rewritten to it, language only: front matter keys (apart from R3's added key) and their values (apart from `title` and `tldr` prose), section order, fenced code, inline code, link targets, numerals and HTML comment markers stay, and the page passes `validate_writing_standard.py --preserve-from <page baseline>` with no FAIL and no `preserve` hit. A page's baseline is its accuracy commit (R14), or, when R13 found nothing to correct, the merge base of the branch and `origin/main` recorded once in the plan journal.
R8. Every rewritten page gets a fact-keeper review, a read-only agent given only the page at its baseline and the rewrite, and no fact it reports `lost`, `changed` or `added` stays unresolved: each is fixed, or the journal records why the rewrite is right; the result is recorded in the plan journal per page.
R9. After the rewrite, no page FAILs its standard, and a page keeps a warning only when the plan journal names the warning and the reason it stays; this holds for every standard, the `ste` and `elements-of-style` pages included.
R10. `.claude/rules/explainers-currency.md` says which standard each page group follows, how to run the check locally, and replaces its "second person, concrete, unhurried" voice line with the standards (the explainers keep explaining why a mechanism exists); its Enforcement list names the new check, and its generated mirror `.opencode/instructions/explainers-currency.md` is regenerated.
R11. A unit test pins the `site-build` step, the script's page-group mapping, and the three front-matter exceptions.
R12. The rewrite keeps every test that pins page wording or markers green, among them `tests/unit/test_tripwire_fr_goal_question_rounds.py`, `tests/unit/test_hermes_docs.py` and `tests/unit/test_build_site.py`; the full unit suite passes in CI after every batch.
R13. Before a page's language is rewritten, an accuracy review reads it against the code its front matter `covers:` and every file, command, option, default or behaviour it names, and lists each claim that is wrong or stale, with file:line evidence for each.
R14. Each confirmed inaccuracy is corrected in one content commit per page, made before that page's language rewrite, and the plan journal records each claim, its evidence and the correction; a flagged claim the code turns out to support is recorded as refuted with its evidence.
R15. A repo review lens `docs-accuracy`, defined in `.fr/lenses.yaml`, asks its reviewer to check every claim a change adds to, changes on or leaves on a published page against the code, and a path rule there requires it for any change to a page `.fr/docs.yaml` names.
R16. `.claude/rules/explainers-currency.md` tells authors that a page must stay true to the code it covers, that fr-goal runs review page changes under the `docs-accuracy` lens, and that a page edited outside a run is checked against its `covers:` code by hand.

## Design

### 1. The script — `scripts/check-writing-standards.sh` (R1–R4)

```bash
scripts/check-writing-standards.sh <blog-craft-dir>
```

It runs the checker once per group, with the group's standard as `--default`, so a
page's own front matter still wins (R3):

```bash
cd "$(git rev-parse --show-toplevel)"
checker="$(realpath "$1")/tools/validate_writing_standard.py"
run() { uv run --isolated --no-project --with pyyaml python "$checker" "$@"; }
run --default ste docs/*.md docs/reference/*.md
run --default plain-language docs/explainers/*.md
```

The globs are the three `pages:` globs of `.fr/docs.yaml`. A page added to one of
those directories is checked with no edit to the script. The script runs every group
before it exits, then exits with the highest code any group returned, so one run shows
every failure. `site-build` only gives PyYAML to its build step's isolated environment
(`.github/workflows/ci.yml`), so the script brings its own through `uv run --isolated
--no-project --with pyyaml`, as the build step does. `uv` is already set up in that
job.

`why-fr.md` carries `writing_standard: elements-of-style`; `index.md` and `cli.md`
carry `writing_standard: none`. `cli.md` is mostly the `<!-- generated:cli-tree -->`
block that `scripts/sync-readme.py` writes from `fr`'s help lines, and
`test_tripwire_readme_sync.py` pins it. Under `ste` it fails, because one help line can
run to 40 words. The only fix is to rewrite `fr`'s help text, which is a code change
outside this feature. So `cli.md` opts out; its hand-written paragraphs are still
rewritten to `ste` language, without the gate. Rewriting the help lines is filed as a
follow-up. `fr.docs.model.parse_page` and `scripts/build-site.py`
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

0. Record the baseline once: `git merge-base HEAD origin/main`, in the plan journal.
   If `main` is merged into the branch later, the pages `main` changed meanwhile are
   checked and reviewed again against the new merge base.
1. Rewrite a batch of 3 to 5 pages in place, language only.
2. Run the checker on the batch with `--preserve-from <baseline> --stats`. Fix every
   FAIL and every `preserve` hit. No check is waived to pass.
3. Review each page with a fact-keeper: a dispatched read-only agent whose instructions
   are blog-craft's `agents/fact-keeper.md`, given the page at the baseline (written
   outside the repository) and the rewrite. Fix every `lost`, `changed` or `added`
   fact, or record why the rewrite is right.
4. Record the batch in the plan journal: per page, the sentence count and average
   before and after, the checker result, the fact-keeper counts, and any warning kept
   with its reason (R9).
5. Run the tests that pin page wording (R12) on the batch before committing it; the
   full unit suite runs in CI on the pushed batch.

The baseline is the merge base, not `HEAD` (the branch accumulates rewrites) and not
`origin/main` (it moves while the feature runs). The skill's per-batch stop for the
operator's approval is replaced by the operator's decisions d-scope and d-verification:
the fact-keeper review and the journal record take its place.

Tripwires the rewrite must keep (R12):
- `test_tripwire_fr_goal_question_rounds.py` forbids phrases such as "one set of
  questions", "one round of questions" and "asks its questions once" on `01-fr-goal.md`
  and `why-fr.md`, and requires the word "round" there.
- `test_hermes_docs.py` pins strings in `docs/reference/hermes.md`.
- `test_build_site.py` pins the `<!-- site:figure … -->` markers in `fr-wave-driver.md`
  and `fr-exit-gates.md`. The checker does not preserve HTML comments, so R7 names them
  and the batch's test run catches a lost one.
Under `ste`, a page's headings may change. A heading that other pages link to keeps
its anchor, or its inbound links are updated in the same batch. The explainers keep
their purpose: they explain why a mechanism exists, in plain language.

### 3a. Accuracy first (R13, R14)

A language-only rewrite keeps whatever the page says, true or not, and `fr docs check`
only asks whether a page was touched when its covered code changed. So each batch starts
with an accuracy pass, kept apart from the rewrite so both stay reviewable:

1. **Review.** A dispatched read-only agent (one per batch; each page reviewed and
   reported on its own) reads the page and the code
   its `covers:` names, plus anything else the page cites: CLI verbs and options
   (`packages/fr/src/fr/commands/`), defaults, file paths, workflow and config names. It
   returns each claim that is wrong or stale, with the page line, the code's file:line,
   and the correct statement. It does not judge style. A phase executor cannot dispatch
   agents, so the orchestrator runs these reviews before dispatching the phase, and the
   executor's brief carries their findings.
2. **Correct.** The executor verifies each finding against the code and fixes the true
   ones in one content commit per page (`docs(<page>): correct …`), before any language
   change. A finding the code does not support is recorded as refuted. Each correction
   goes in the plan journal as a discovery: claim, evidence, correction (R14).
3. **Rewrite.** The language rewrite of §3 then runs with that commit as the page's
   baseline, so `--preserve-from` and the fact-keeper judge only the language step.

The phase review sees two kinds of change and checks both: the accuracy commits against
the code, and the rewrite against its baseline.

### 3b. Staying accurate (R15, R16)

`.fr/lenses.yaml` gains a repo lens and a path rule:

```yaml
lenses:
  docs-accuracy:
    title: Docs accuracy
    brief: |
      Review every published page this change touches for whether what it says is true
      of the code. Check each claim the change adds or edits, and each claim on a touched
      page whose covered code (`covers:`) the change also touched, against that code:
      commands and options, defaults, file paths, behaviour, order of steps. Report each
      false or stale claim with the page line and the code's file:line.
      A problem you see outside this lens is still reported, as an ordinary finding.
require:
  - paths: ["docs/explainers/*.md", "docs/*.md", "docs/reference/*.md"]
    lenses: [docs-accuracy]
```

With `fr docs check` (a code change must touch its page), this means: a code change that
makes a page stale must edit the page, and every fr-goal change that edits a page gets an
accuracy review of that page against the code. A rule the branch adds is in force for the
branch itself, so this feature's own `lens-review` reviews all 31 pages under it. `fr
lenses check` validates the file. Outside an fr-goal run there is no lens review; the
authoring rule says to check a page against its `covers:` code by hand (R16).

### 4. The authoring rule (R10, R16)

`.claude/rules/explainers-currency.md` gains a short section:
- the group-to-standard mapping, and the two exceptions;
- `bash scripts/check-writing-standards.sh <blog-craft-dir>` to check locally, with the
  same blog-craft checkout recipe the rule already gives for previews;
- a pointer to each standard's reference file in blog-craft for the rules themselves;
- a new Enforcement bullet for `scripts/check-writing-standards.sh` in `site-build` and
  its unit test;
- an accuracy paragraph (R16): a page stays true to the code it covers; fr-goal runs
  review page changes under the `docs-accuracy` lens; a page edited outside a run is
  checked against its `covers:` code by hand.

The rule is listed in `scripts/sync-opencode.py`'s `REPO_LOCAL_ONLY_RULES`, so the edit
is followed by `scripts/sync-opencode.py` and the regenerated
`.opencode/instructions/explainers-currency.md` is committed with it.

The "Match the existing voice: second person, concrete, unhurried" paragraph is
replaced. Its intent stays (explain why, for a newcomer), but the standards replace its
style advice. The shipped `plugins/super-fr/rules/docs-currency.md` is not changed:
consumer repos choose their own standards.

### 5. Tests (R11)

`tests/unit/test_pages_workflow.py` (or a sibling `test_writing_standards_docs.py`) pins:
- the `site-build` step;
- the script's two `--default` groups, which match `.fr/docs.yaml`'s page globs;
- the front matter of `why-fr.md`, `index.md` and `cli.md`;
- that no other page carries a `writing_standard` key.

## Non-goals

- Changing `fr` (its help lines included, see `cli.md` in §1) or the shipped `docs-currency` rule.
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
- writing-standards-docs-accuracy: none — per-page accuracy reviews and corrections recorded in the plan journal, re-checked by each phase review and by this feature's own docs-accuracy lens review
- writing-standards-docs-accuracy-lens: none — `fr lenses check` and `fr lenses status` in CI-run unit test; the lens review of this feature exercises it

## Test Plan

Pre-merge, in CI:

1. `site-build` builds every page with the new pin and runs
   `scripts/check-writing-standards.sh .blog-craft`: no FAIL.
2. The unit test of §5 passes.
3. `fr docs check` passes (every changed page is a covered page that changed).

Per batch, before it is accepted (recorded in the plan journal):

4. `validate_writing_standard.py --preserve-from <baseline> --stats` on the batch: no
   FAIL and no `preserve` hit.
5. A fact-keeper review per page: no unresolved `lost`, `changed` or `added` fact.
6. The plan journal names every warning a page keeps, and why (R9).
7. The wording tripwires of R12 pass on the batch, and CI's full unit suite passes on
   the pushed batch.

At the end, in review:

8. Per page, the plan journal holds the accuracy review's claims and each one's outcome
   (corrected with its commit, or refuted with evidence) (R13, R14).
9. `uv run fr lenses check` passes, and `uv run fr lenses status` on this branch lists
   `docs-accuracy` as required by the path rule; a unit test pins the lens and its rule
   (R15).
10. `.claude/rules/explainers-currency.md` names each group's standard and the three
   exceptions, its local command is the one the CI step runs, and its OpenCode mirror is
   in sync (`test_tripwire_opencode_instructions_sync.py`).

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-11-13-writing-standards-docs | `derio-net/super-fr` | `2026-11-13-writing-standards-docs` | — |
