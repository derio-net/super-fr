# Docs, help and skill wording sweep (batch docs-wording)

## 1. Goal

Thirteen issues (derio-net/super-fr#1265, #1441, #1445, #1440, #1447, #1446, #1450,
#1443, #1442, #1421, #1449, #1444, #1448) report places where fr's help text, a shipped
skill or a published page says something the code does not do, or where the published
site renders a page wrongly. This batch makes each one true and, where the operator
asked for it, adds a guard so the same class of defect fails a test or the build instead
of shipping silently. One pull request delivers all thirteen.

## 2. Background (checked against the code at the branch base, 66e02916d)

- **#1265.** `packages/fr/src/fr/commands/ops_gate_cmd.py:207` prints
  `` `fr init scaffold --ops`, then re-run ``; `plugins/super-fr/skills/fr-devops-gate/SKILL.md:35`
  says the same. `fr init scaffold` requires `--profile` and `--purpose`
  (`packages/fr/src/fr/commands/init_cmd.py:29-30`), so the printed command fails, and
  neither text says where to scaffold.
- **#1441.** `ops_cmd.py:536` (`seal --encrypt` help) says `{target}` is "the target's
  name"; `packages/fr/src/fr/ops/helpers.py:164` substitutes `shlex.quote(str(target))`,
  the full path, and the docstring at `helpers.py:141` says "path as a name".
- **#1445.** `plan_cmd.py:365` says the parent plan is "(Complete + archived)";
  `rework_create` (`plan_ops.py:866-884`) accepts a parent under `plans/`,
  `implemented/plans/` or `archived-plans/` and never checks completeness; its docstring
  says "Parent stays Complete".
- **#1447.** `init_cmd.py:33` help reads `<tool>[@<version>]`; Rich reads `[@<version>]`
  as markup and `fr init scaffold --help` prints `<tool>;`.
- **#1440.** `docs/reference/cli.md` carries `writing_standard: none` because its
  generated tree (from fr's help first lines, `scripts/sync-readme.py`) is not STE. Run
  under STE with the pinned checker it has 14 FAILs, all `sentence_length`; the rest are
  warnings, which do not fail the check.
- **#1444.** `plugins/super-fr/skills/fr-acceptance/SKILL.md:116` says a `--verify live`
  row "keeps nagging in `fr acceptance status` whatever its status". `open_rows`
  (`packages/fr/src/fr/acceptance/check.py:113`) lists only debt rows (`is_debt`: a
  `DEBT_STATUSES` status, contested, or a stale `local`).
- **#1448.** `plugins/super-fr/skills/fr-progress/SKILL.md:29` says
  `fr status`/`fr repair`/`fr migrate v1-to-v2` "preview by default, no `--yes`".
  `fr repair` and `fr migrate` take `--yes` (`repair_cmd.py:54`, `migrate_cmd.py:27-138`);
  `fr status` has none (`status_cmd.py`).
- **#1449.** Already fixed at the base: `fr-triage/SKILL.md` says `schema: 12` in both
  places, matching `JUDGEMENTS_SCHEMA` (`packages/fr/src/fr/triage/model.py:98`).
  Nothing pins the two together.
- **#1446, #1450, #1443.** A local build at the base (`scripts/build-site.py` with the
  pinned blog-craft) and a scan of every built page for a fence rendered as
  `<p><code>lang …` found exactly four: `docs/explainers/fr-acceptance.md` (backfill
  step 3's example, under a 3-space list indent, renders inline, and steps 4–5 fold into
  step 3's paragraph), `docs/explainers/fr-exit-gates.md:86-88` (the Tester bullet's
  2-space fence), and two 2-space fences in `docs/docs-currency.md` (the CI YAML under
  "Where it runs" and the preview `bash` block). `docs/merge-protection.md` already
  renders correctly (fixed in f52f33659). docs-currency.md's other broken list is #1442.
- **#1442.** `fill_pages` (`scripts/build-site.py:267-280`) does
  `text.replace(MARKER, …)`, so docs-currency.md:175, which names the marker in inline
  code, gets the whole page list spliced into item 5 of its numbered list.
- **#1421.** `scripts/site/bar.css` has one phone rule (`max-width:480px`, shrinks gap
  and font) and `flex-wrap:wrap`, so at 320 px the links wrap raggedly. Article pages
  pull the bar out with `margin:-3rem -1.25rem` and pad it `1.25rem`. On the landing,
  `body.landing .site-bar` (`scripts/site/landing.css:53`) already pads the bar with
  `max(1.5rem, calc((100% - 1120px)/2 + 1.5rem))`, the gutter of the content's `.wrap`
  (`:45`), so on desktop the two share a left edge. At ≤720 px `.wrap` drops to `1.15rem`
  (`:199`) while the bar keeps its `1.5rem` minimum, so at 320 and 390 px the bar's text
  sits about 0.35rem right of the content. `body.landing` rules outrank `bar.css`, so on
  the landing `.site-name`'s size is landing.css:55's, not the bar's phone rule's. The
  article column's own padding comes from blog-craft's broadsheet style, which this repo
  does not hold; whether the bar lines up there at phone widths is for the screenshots to
  show.

## 3. Operator decisions (question round 1)

- d1 (#1445): the code is right. Fix the help and the docstring; behaviour unchanged.
- d2 (#1440): rewrite the failing help lines, regenerate, and drop cli.md's
  `writing_standard: none`, so CI's site-build keeps new help lines within STE.
- d3 (#1421): on a phone the bar is two rows by design: the name, then the links.
- d4 (#1421): the bar's text lines up with the content of the page it sits on.
- d5: add three guards: the build refuses a fence rendered inline; a test pins the
  fr-triage skill's judgements schema number to the engine's; a test fails when Rich
  markup eats bracketed help text.
- d6: verification is CI plus browser screenshots of the built site; no candidate walk.
- d7: no post-merge hold and no Test Plan.

## Requirements

R1. When `fr ops gate` finds no ops profile, its hint names a complete command, `fr init scaffold --ops --profile <name> --purpose "<one line>"`, and says to run it on a new branch cut from the default branch and land the profile by its own pull request; `fr-devops-gate` SKILL.md and the explainer `docs/explainers/fr-devops-gate.md` (which gives the same command at :63-64) say the same.
R2. `fr ops seal --encrypt`'s help says `{target}` is the target's path, shell-quoted, and the docstring of `fr.ops.helpers.seal` says the same.
R3. `fr plan rework`'s argument help and `rework_create`'s docstring say the parent plan may be live (`plans/`) or archived (`implemented/plans/`, `archived-plans/`), complete or not; what `rework_create` accepts and does is unchanged.
R4. Every fr help string that holds bracketed text renders it as written in `--help`: `fr init scaffold --help` shows `<tool>[@<version>]`, and the other strings R5's test flags do too (known at the base: `acceptance_cmd.py:755,1137,1141` `[#test_name]`/`[#R<n>]`/`[#anchor]`, `triage_batch_cmd.py:773` `[a-z][a-z0-9-]{0,39}`).
R5. A unit test renders the `--help` of every fr command and fails, naming the command, when bracketed text (`[...]`) in one of its help strings (option help, argument help or the command's docstring) is missing from the rendered output.
R6. Every help first line that the generated command tree in `docs/reference/cli.md` carries passes the pinned STE checker with no FAIL; `docs/reference/cli.md` no longer carries `writing_standard: none` and is checked as a reference page; the pinned exception list (`tests/unit/test_writing_standards_docs.py`) and `.claude/rules/explainers-currency.md` name two exceptions, `why-fr.md` and `index.md`. (README's table is derived from the same lines, shortened by `sync-readme.py`, and is not a checked page.)
R7. `fr-acceptance` SKILL.md says that `fr acceptance status` lists a `--verify live` row only while the row is debt (as `is_debt` defines it: a debt status, contested, or an unstamped or stale `local`), not whatever its status.
R8. `fr-progress` SKILL.md says `fr repair` and `fr migrate v1-to-v2` preview by default and apply only with `--yes`, and that `fr status` only reads and has no `--yes`.
R9. A unit test fails when a judgements `schema: <n>` that `fr-triage` SKILL.md states differs from `JUDGEMENTS_SCHEMA`.
R10. The OpenCode and Hermes mirrors of every edited skill, the OpenCode instructions mirror of every edited rule (`.opencode/instructions/explainers-currency.md`), and the generated README and cli.md tables are regenerated in the same change.
R11. In the built site every fenced code block of a page renders as a code block, never as inline code: `fr-acceptance.md`'s backfill steps 1–5 render as one numbered list with step 3's example a code block inside it; the Tester example of `fr-exit-gates.md` and both indented examples of `docs-currency.md` render as code blocks inside their list items.
R12. The site build fails, naming the page and the fence's line in the page's own source file, when a fenced code block of that page does not render as a code block (`<pre>`), with or without an info word; like every other refusal, it writes no page at all.
R13. `fill_pages` replaces `<!-- site:pages -->` only on a line that holds the marker alone (surrounding whitespace allowed); the marker inside inline code or running text is left as written. The numbered list under `docs-currency.md`'s "How this repo builds its site" (:157-178) renders as one list, items 1–6, showing the marker as code.
R14. At widths up to 480 px the top bar lays out as two rows: the site name alone on the first, its four links on the second; at 320 px no row wraps and the page has no horizontal scroll. Above 480 px the bar stays one row.
R15. The bar's text starts at the left edge of the content below it, on article pages and on the landing, at 320 px, 390 px and desktop widths.

## Design

### Help text and skill prose (R1–R10)

- R1: one string in `ops_gate_cmd.py` and the matching SKILL sentence. `<name>` and the
  purpose stay placeholders: fr cannot know the operator's profile name. The "new branch"
  clause names why: a profile committed on the feature branch would ride the feature PR.
- R2, R3: string-only edits in `ops_cmd.py`, `ops/helpers.py`, `plan_cmd.py`,
  `plan_ops.py`.
- R4/R5: write R5's test first and run it: the set it flags is the set R4 escapes
  (`\[` in the source, so Rich prints the bracket). The test walks the Typer app's Click
  command tree (`typer.main.get_command(fr.cli.app)`), renders each command's help with
  `CliRunner` under a very wide terminal (`COLUMNS`/`TERMINAL_WIDTH` set, e.g. 1000) so
  Rich does not wrap, then normalises the output (drop box glyphs `│╭╮╰╯─`, collapse
  whitespace) and the expected text alike. The expected spans are every `[...]` in the
  params' `help` and the docstring, with `\[` read as `[`. Help with no bracket passes
  trivially. A self-test feeds it one unescaped `[@x]` string and asserts it fails.
- R6: shorten the help first lines that fail (under 25 words, one claim per sentence),
  run `scripts/sync-readme.py`, drop the key from cli.md, update
  `test_only_the_three_exceptions_carry_a_writing_standard_key` (renamed for two) and the
  rule's paragraph. The executor runs `scripts/check-writing-standards.sh` against the
  pinned blog-craft to prove no FAIL. Warnings are not addressed.
- R7, R8: sentence edits. R9: a unit test reads the SKILL, finds every
  `schema: <n>` that names the judgements file, and compares with
  `fr.triage.model.JUDGEMENTS_SCHEMA`.
- R10: `scripts/sync-opencode.py`, `scripts/sync-hermes.py`, `scripts/sync-readme.py`.
  Skill and `packages/*/src` edits need a change fragment (`.changes/feat-batch-docs-wording.yaml`,
  `bump: patch`).

### Site build and pages (R11–R13)

- R11: Python-Markdown never reads a fence inside a list item, at any indent (checked at
  2, 3 and 4 spaces with markdown 3.11 and the pinned renderer; journal
  `p2-fence-in-list-not-read`). So each of the four examples becomes an indented code block
  (8 spaces, no fence) inside its list item, and step 4 of the backfill list gets a blank
  line before it. The examples' text does not change.
- R12: one matching rule. Each fence of the page's own source file (opening lines of
  three backticks or tildes at any indent, paired by `_FENCE`; a `mermaid` fence is the
  renderer's to place and is skipped) must have its body as the whole text of a `<pre>` of
  the rendered page (whitespace-normalised), so a `<pre>` that merely contains the body,
  or also shows the fence's own lines (a fence rendered as literal text), does not count. Matching by body means a `<pre>` from a figure, raw HTML or the
  renderer's chrome cannot satisfy a fence. The first fence that fails raises
  `BuildError` naming the page path and the fence's line in the source file as read from
  disk (front matter included). The check runs on each page's render, before `build()`
  writes any page, so no page is written when it fires.
- R13: `fill_pages` matches the marker with a multiline regex anchored to a whole line
  (`^[ \t]*<!-- site:pages -->[ \t]*$`). The landing's own marker is on its own line,
  so the front page is unchanged.

### Top bar (R14–R15)

- R14: in the `max-width:480px` rule the bar wraps on purpose: `.site-name` takes
  `flex-basis:100%` (alone on row 1) and the links share row 2 with even gaps, sized so
  the four fit at 320 px without wrapping, under bar.css's sizes on article pages and
  under landing.css's `body.landing` sizes (`:53,55`) on the landing. No JavaScript, no
  new markup if CSS suffices.
- R15: the bar's horizontal padding follows the gutter of the page it sits on. On the
  landing, add a `max-width:720px` rule beside landing.css:199 so the bar's padding
  matches `.wrap`'s `1.15rem` there (desktop is already aligned). On article pages, the
  screenshots at 320, 390 and 1280 px decide whether the pull-out lines up with the
  broadsheet column; if not, bar.css's phone rule corrects the margin and padding.
- Evidence is browser screenshots of the built site (article, guide, reference and
  landing at 320 px, 390 px and 1280 px), opened and compared at implement and review.

### Pages the docs-currency gate owes (all requirements)

`fr docs check` refuses `deliver` while a page whose `covers:` matches an edited path is
unchanged. Each phase edits or re-stamps the pages its paths make stale, and ends with
`fr docs check`. Known at the base: `docs/ops.md` (ops/**, ops_cmd.py),
`docs/explainers/fr-init.md` (init_cmd.py), `docs/explainers/fr-brainstorming-and-plan.md`
and `docs/reference/plan-model.md` (plan_cmd.py), `docs/explainers/fr-progress.md`
(fr-progress SKILL), `docs/explainers/fr-devops-gate.md` (edited per R1),
`docs/explainers/fr-acceptance.md` and `docs/explainers/fr-triage.md` (their skills),
`docs/reference/cli.md` (commands/*.py), and `docs/docs-currency.md` (build-site.py,
scripts/site/**, the explainers-currency rule). The R6 help rewrites touch further
`commands/*.py` modules; the check names their pages. The new R12 refusal is described
where the build's rules live: docs-currency.md's "Write a page that builds" list (a fence
inside a list item is an 8-space indented code block, never a fence) and the build-failure list in
`.claude/rules/explainers-currency.md`.

## Verification

strategy: none
gate: developer

- cli-help-matches-code: none — verified by CI unit tests asserting the rendered help and hint text
- cli-help-rich-markup-safe: none — verified by the CI unit test over every fr command's help
- cli-reference-ste: none — verified by CI's site-build writing-standards check and the exceptions unit test
- skill-prose-matches-engine: none — verified by CI unit tests over the skill text and the schema pin
- site-code-blocks-render: none — verified by CI unit tests of the build's fence refusal and CI's site-build over every page
- site-pages-marker-own-line: none — verified by CI unit tests of fill_pages and the built docs-currency page
- site-top-bar-phone-layout: none — verified by CI unit tests on bar.css and browser screenshots of the built site at 320, 390 and 1280 px

There is no `## Test Plan` (d7): nothing here needs a released build or the live Pages
site to show it. R10 is how the change is delivered, not a business claim, so it has no row.

## Acceptance rows

| Row | Requirements |
|---|---|
| cli-help-matches-code | R1–R4 |
| cli-help-rich-markup-safe | R5 |
| cli-reference-ste | R6 |
| skill-prose-matches-engine | R7–R9 |
| site-code-blocks-render | R11–R12 |
| site-pages-marker-own-line | R13 |
| site-top-bar-phone-layout | R14–R15 |

`writing-standards-docs-groups` (spec `2026-11-13-writing-standards-docs`) already says
reference pages are held to STE; when R6 renames its pinned test, its level ref is
re-pointed by amendment (`add-level`/`drop-level`), not edited in place.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-19-batch-docs-wording | `derio-net/super-fr` | `2026-11-19-batch-docs-wording` | — |
