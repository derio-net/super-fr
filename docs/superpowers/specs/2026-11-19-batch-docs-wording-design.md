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
  pull the bar out with `margin:-3rem -1.25rem` and pad it `1.25rem`; the landing sets
  `.landing .site-bar{margin:0}` while its content sits at a `1.5rem` gutter inside a
  centred 1120 px column (`scripts/site/landing.css:45,53`), so the bar's text starts at a
  different left edge from the content below it.

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

R1. When `fr ops gate` finds no ops profile, its hint names a complete command, `fr init scaffold --ops --profile <name> --purpose "<one line>"`, and says to run it on a new branch cut from the default branch and land the profile by its own pull request; `fr-devops-gate` SKILL.md says the same.
R2. `fr ops seal --encrypt`'s help says `{target}` is the target's path, shell-quoted, and the docstring of `fr.ops.helpers.seal` says the same.
R3. `fr plan rework`'s argument help and `rework_create`'s docstring say the parent plan may be live (`plans/`) or archived (`implemented/plans/`, `archived-plans/`), complete or not; what `rework_create` accepts and does is unchanged.
R4. `fr init scaffold --help` shows `<tool>[@<version>]` as written.
R5. A unit test renders the `--help` of every fr command and fails, naming the command, when bracketed text (`[...]`) in one of its help strings (option help, argument help or the command's docstring) is missing from the rendered output.
R6. Every help first line that the generated command tree carries (`docs/reference/cli.md`, `README.md`) passes the pinned STE checker with no FAIL; `docs/reference/cli.md` no longer carries `writing_standard: none` and is checked as a reference page; the pinned exception list (`tests/unit/test_writing_standards_docs.py`) and `.claude/rules/explainers-currency.md` name two exceptions, `why-fr.md` and `index.md`.
R7. `fr-acceptance` SKILL.md says that `fr acceptance status` lists a `--verify live` row only while the row is debt (its status is a debt status, or the row is contested), not whatever its status.
R8. `fr-progress` SKILL.md says `fr repair` and `fr migrate v1-to-v2` preview by default and apply only with `--yes`, and that `fr status` only reads and has no `--yes`.
R9. A unit test fails when a judgements `schema: <n>` that `fr-triage` SKILL.md states differs from `JUDGEMENTS_SCHEMA`.
R10. The OpenCode and Hermes mirrors of every edited skill and the generated README and cli.md tables are regenerated in the same change.
R11. In the built site every fenced code block of a page renders as a code block, never as inline code: `fr-acceptance.md`'s backfill steps 1–5 render as one numbered list with step 3's example a code block inside it; the Tester example of `fr-exit-gates.md` and both indented examples of `docs-currency.md` render as code blocks inside their list items.
R12. The site build fails, naming the page, when a fenced code block of a page's source renders as inline code, and writes no output for that page.
R13. `fill_pages` replaces `<!-- site:pages -->` only on a line that holds the marker alone (surrounding whitespace allowed); the marker inside inline code or running text is left as written. `docs-currency.md`'s "How the site is built" list renders as one numbered list, items 1–6, showing the marker as code.
R14. At widths up to 480 px the top bar lays out as two rows: the site name alone on the first, its four links on the second; at 320 px no row wraps and the page has no horizontal scroll. Above 480 px the bar stays one row.
R15. The bar's text starts at the left edge of the content below it, on article pages and on the landing, at 320 px, 390 px and desktop widths.

## Design

### Help text and skill prose (R1–R10)

- R1: one string in `ops_gate_cmd.py` and the matching SKILL sentence. `<name>` and the
  purpose stay placeholders: fr cannot know the operator's profile name. The "new branch"
  clause names why: a profile committed on the feature branch would ride the feature PR.
- R2, R3: string-only edits in `ops_cmd.py`, `ops/helpers.py`, `plan_cmd.py`,
  `plan_ops.py`.
- R4: write the bracket escaped for Rich (`\[@<version>]`) so the rendered help shows
  it. R5's test is the guard: walk the Typer app's Click command tree
  (`typer.main.get_command(fr.cli.app)`), render each command's help with `CliRunner`,
  collect every `[...]` span from its params' `help` and its docstring (unescaping `\[`),
  and assert each appears in the output. Help with no bracket passes trivially.
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

- R11: re-indent each list item's continuation and fence to the 4 spaces Python-Markdown
  needs, and put a blank line before step 4 of the backfill list. Only whitespace changes.
- R12: after markdown rendering, the build compares the page's fenced blocks with the
  rendered HTML. A fence (a line opening with three backticks, at any indent, outside
  another fence) whose rendered form is `<p><code>` followed by its info word, or that
  produced no `<pre>`, fails the build with the page path and the fence's source line.
  The check lives in `scripts/build-site.py` beside the existing refusals and follows
  their "no file for that page" rule.
- R13: `fill_pages` matches the marker with a multiline regex anchored to a whole line
  (`^[ \t]*<!-- site:pages -->[ \t]*$`). The landing's own marker is on its own line,
  so the front page is unchanged.

### Top bar (R14–R15)

- R14: in the `max-width:480px` rule the bar wraps on purpose: `.site-name` takes
  `flex-basis:100%` (alone on row 1) and the links share row 2 with even gaps, sized so
  the four fit at 320 px without wrapping. No JavaScript, no new markup if CSS suffices.
- R15: the bar's horizontal padding follows the gutter of the page it sits on. On the
  landing that is `max(1.5rem, calc((100% - 1120px)/2 + 1.5rem))` (the same expression
  landing.css uses); on article pages the existing pull-out keeps the text on the
  article column, and the phone rule keeps that true at 320 and 390 px.
- Evidence is browser screenshots of the built site (article, guide, reference and
  landing at 320 px, 390 px and 1280 px), opened and compared at implement and review.

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
