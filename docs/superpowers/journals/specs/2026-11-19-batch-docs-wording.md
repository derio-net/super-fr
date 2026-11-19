<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-batch-docs-wording

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-19T09:35:05+00:00 input=true -->
### brief · discovery · Operator brief: batch docs-wording (13 issues)

Batch `docs-wording` of derio-net/super-fr: 13 issues, delivered as ONE pull request (branch feat/batch-docs-wording). Batch title: Docs, help and skill wording sweep. Members:
- #1265 docs: `fr init scaffold --ops` hint (fr ops gate + fr-devops-gate SKILL) is incomplete — missing required --profile/--purpose, and doesn't say where to scaffold
- #1441 ops_cmd.py `fr ops seal --encrypt` help says {target} is the target's name; it is the shell-quoted full path
- #1445 fr plan rework help says the parent is "(Complete + archived)"; rework_create accepts a live or incomplete parent
- #1440 fr's CLI help lines are too long for STE, so docs/reference/cli.md's generated tree cannot meet the guides' standard
- #1447 fr init scaffold --help prints `<tool>;` - Rich markup eats `[@<version>]`
- #1446 fr-acceptance.md backfill list already renders broken at the merge base: step 4 merges into step 3's paragraph
- #1450 fr-exit-gates.md tester bullet's fenced example renders as inline code, at the merge base too
- #1443 docs-currency.md and merge-protection.md lists already rendered broken at the merge base
- #1442 scripts/build-site.py fill_pages replaces <!-- site:pages --> even inside inline code
- #1421 shared top bar is cramped at 390 and wraps at 320, and its left edge differs between article pages and the landing
- #1449 fr-triage SKILL.md says a first run creates judgements with schema: 11; the engine writes 12
- #1444 fr-acceptance SKILL.md:116 says a --verify row keeps nagging in fr acceptance status whatever its status, under Post-merge owed
- #1448 fr-progress SKILL.md lists fr status among the commands that preview until --yes
Why together: regenerates all three mirror sets (sync-opencode, sync-hermes, sync-readme). Delivery: draft PR with one `Closes derio-net/super-fr#N` line per member; no member issue as a phase tracking_issue; never add approved-fr.

<!-- fr:journal kind=decision scope=spec id=d1-rework-help created=2026-11-19T09:35:05+00:00 decided_by=operator -->
### d1-rework-help · decision · #1445: the code is right; fix help and docstring

Operator chose "Fix help to match code" over tightening rework_create. Behaviour unchanged.

<!-- fr:journal kind=decision scope=spec id=d2-cli-ste created=2026-11-19T09:35:05+00:00 decided_by=operator -->
### d2-cli-ste · decision · #1440: rewrite failing help lines and drop cli.md exemption

Operator chose to shorten the ~14 failing help first lines, regenerate, remove writing_standard: none from cli.md, and update the pinned exception list and the explainers-currency rule.

<!-- fr:journal kind=decision scope=spec id=d3-bar-two-rows created=2026-11-19T09:35:05+00:00 decided_by=operator -->
### d3-bar-two-rows · decision · #1421: two-row bar on phones

Operator chose: at <=480 px the site name on row 1, the four links on row 2; no ragged wrap, no horizontal scroll.

<!-- fr:journal kind=decision scope=spec id=d4-bar-edge created=2026-11-19T09:35:05+00:00 decided_by=operator -->
### d4-bar-edge · decision · #1421: bar text aligns with each page's content

Operator chose to match each page's own content column rather than one fixed gutter.

<!-- fr:journal kind=decision scope=spec id=d5-guards created=2026-11-19T09:35:05+00:00 decided_by=operator -->
### d5-guards · decision · Add three guards

Operator selected all three: build refuses a fence rendered inline; unit test pins fr-triage SKILL schema to JUDGEMENTS_SCHEMA; unit test fails when Rich markup eats bracketed help text.

<!-- fr:journal kind=decision scope=spec id=d6-verification created=2026-11-19T09:35:05+00:00 decided_by=operator -->
### d6-verification · decision · Verification: strategy none, CI plus screenshots

Operator chose no candidate walk: CI unit tests, site-build and writing-standards check, and browser screenshots of the built site for the bar.

<!-- fr:journal kind=decision scope=spec id=d7-no-hold created=2026-11-19T09:35:05+00:00 decided_by=operator -->
### d7-no-hold · decision · No post-merge hold, no Test Plan

Operator chose no tester/devops gate (gate: developer) and no Test Plan.

<!-- fr:journal kind=discovery scope=spec id=gh1449-already-fixed created=2026-11-19T09:35:05+00:00 -->
### gh1449-already-fixed · discovery · #1449 is already fixed at the base; only the pin (R9) is new

fr-triage SKILL.md says schema: 12 in both places at 66e02916d, matching JUDGEMENTS_SCHEMA (triage/model.py:98). merge-protection.md (#1443) already renders correctly (f52f33659).

<!-- fr:journal kind=finding scope=spec id=sr-r1 created=2026-11-19T09:42:10+00:00 state=open review_scope=in -->
### sr-r1 · finding [open] (reviewer: in scope) · R5's guard will flag other existing help strings that R4 does not fix

Raised by the independent fr-spec-reviewer (see spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-r2 created=2026-11-19T09:42:10+00:00 state=open review_scope=in -->
### sr-r2 · finding [open] (reviewer: in scope) · R5's substring check will break on Rich panel wrapping unless the test sets the width and normalises output

Raised by the independent fr-spec-reviewer (see spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-r3 created=2026-11-19T09:42:10+00:00 state=open review_scope=in -->
### sr-r3 · finding [open] (reviewer: in scope) · R12's fence-to-output matching is unspecified, misses bare fences, and contradicts the build's all-or-nothing write rule

Raised by the independent fr-spec-reviewer (see spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-r4 created=2026-11-19T09:42:10+00:00 state=open review_scope=in -->
### sr-r4 · finding [open] (reviewer: in scope) · R15's landing diagnosis and fix are wrong; the landing already uses that gutter expression, and the real gap is at <=720 px

Raised by the independent fr-spec-reviewer (see spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-r5 created=2026-11-19T09:42:10+00:00 state=open review_scope=in -->
### sr-r5 · finding [open] (reviewer: in scope) · R1 misses the published page that repeats the incomplete scaffold command

Raised by the independent fr-spec-reviewer (see spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-r6 created=2026-11-19T09:42:10+00:00 state=open review_scope=in -->
### sr-r6 · finding [open] (reviewer: in scope) · The docs-currency gate will require page edits or stamps that the spec never mentions

Raised by the independent fr-spec-reviewer (see spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-r7 created=2026-11-19T09:42:10+00:00 state=open review_scope=in -->
### sr-r7 · finding [open] (reviewer: in scope) · R10 omits the OpenCode mirror of the explainers-currency rule that R6 edits

Raised by the independent fr-spec-reviewer (see spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-r8 created=2026-11-19T09:42:10+00:00 state=open review_scope=in -->
### sr-r8 · finding [open] (reviewer: in scope) · R6's README.md clause cannot be checked as written

Raised by the independent fr-spec-reviewer (see spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-r9 created=2026-11-19T09:42:10+00:00 state=open review_scope=in -->
### sr-r9 · finding [open] (reviewer: in scope) · R13 names a section heading that does not exist

Raised by the independent fr-spec-reviewer (see spec-review-1).

<!-- fr:journal kind=finding scope=spec id=sr-r10 created=2026-11-19T09:42:10+00:00 state=open review_scope=in -->
### sr-r10 · finding [open] (reviewer: in scope) · R7's definition of debt leaves out the stale local reason

Raised by the independent fr-spec-reviewer (see spec-review-1).

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-19T09:42:10+00:00 -->
### spec-review-1 · review · independent spec review: 10 findings

fr-spec-reviewer (separate context, read-only) raised sr-r1..sr-r10, all in scope; decisions d1-d7 honoured. Every finding fixed in the spec. Suggested lenses: tests (R5/R12 guards), docs-accuracy (already required by .fr/lenses.yaml for page edits).

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-19T09:42:10+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · R5 and R12 add new test/build guard machinery whose false-pass and false-fail behaviour needs its own check

<!-- fr:journal kind=finding scope=spec id=sr-r1-resolved created=2026-11-19T09:42:10+00:00 state=fixed resolves=sr-r1 -->
### sr-r1-resolved · finding [fixed] · resolves sr-r1: R5's guard will flag other existing help strings that R4 does not fix

R4 extended to every string R5 flags, known ones listed (acceptance_cmd.py:755,1137,1141; triage_batch_cmd.py:773); Design: write R5 first, its set is R4's set.

<!-- fr:journal kind=finding scope=spec id=sr-r2-resolved created=2026-11-19T09:42:10+00:00 state=fixed resolves=sr-r2 -->
### sr-r2-resolved · finding [fixed] · resolves sr-r2: R5's substring check will break on Rich panel wrapping unless the test sets the width and normalises output

Design: wide terminal (COLUMNS/TERMINAL_WIDTH), normalise box glyphs and whitespace on both sides, \[ read as [, plus a self-test.

<!-- fr:journal kind=finding scope=spec id=sr-r3-resolved created=2026-11-19T09:42:10+00:00 state=fixed resolves=sr-r3 -->
### sr-r3-resolved · finding [fixed] · resolves sr-r3: R12's fence-to-output matching is unspecified, misses bare fences, and contradicts the build's all-or-nothing write rule

R12 reworded (with or without info word; line in the source file; writes no page at all). Design gives one counting rule over source fences vs article <pre>, excluding figure/raw/chrome <pre>, line taken before splices, raised in the refusal pass.

<!-- fr:journal kind=finding scope=spec id=sr-r4-resolved created=2026-11-19T09:42:10+00:00 state=fixed resolves=sr-r4 -->
### sr-r4-resolved · finding [fixed] · resolves sr-r4: R15's landing diagnosis and fix are wrong; the landing already uses that gutter expression, and the real gap is at <=720 px

Background corrected (landing.css:53 already aligned on desktop; :199 1.15rem gap at <=720px; body.landing outranks bar.css). R15 design: a max-width:720px rule matching .wrap; article alignment stated as what screenshots decide.

<!-- fr:journal kind=finding scope=spec id=sr-r5-resolved created=2026-11-19T09:42:10+00:00 state=fixed resolves=sr-r5 -->
### sr-r5-resolved · finding [fixed] · resolves sr-r5: R1 misses the published page that repeats the incomplete scaffold command

R1 now names docs/explainers/fr-devops-gate.md:63-64.

<!-- fr:journal kind=finding scope=spec id=sr-r6-resolved created=2026-11-19T09:42:10+00:00 state=fixed resolves=sr-r6 -->
### sr-r6-resolved · finding [fixed] · resolves sr-r6: The docs-currency gate will require page edits or stamps that the spec never mentions

New Design section lists the pages to edit or stamp, says each phase ends with fr docs check, and where the R12 refusal is documented.

<!-- fr:journal kind=finding scope=spec id=sr-r7-resolved created=2026-11-19T09:42:10+00:00 state=fixed resolves=sr-r7 -->
### sr-r7-resolved · finding [fixed] · resolves sr-r7: R10 omits the OpenCode mirror of the explainers-currency rule that R6 edits

R10 names .opencode/instructions/explainers-currency.md.

<!-- fr:journal kind=finding scope=spec id=sr-r8-resolved created=2026-11-19T09:42:10+00:00 state=fixed resolves=sr-r8 -->
### sr-r8-resolved · finding [fixed] · resolves sr-r8: R6's README.md clause cannot be checked as written

README dropped from R6's checked surface; a note says README is derived and not a checked page.

<!-- fr:journal kind=finding scope=spec id=sr-r9-resolved created=2026-11-19T09:42:10+00:00 state=fixed resolves=sr-r9 -->
### sr-r9-resolved · finding [fixed] · resolves sr-r9: R13 names a section heading that does not exist

R13 uses "How this repo builds its site" (:157-178).

<!-- fr:journal kind=finding scope=spec id=sr-r10-resolved created=2026-11-19T09:42:10+00:00 state=fixed resolves=sr-r10 -->
### sr-r10-resolved · finding [fixed] · resolves sr-r10: R7's definition of debt leaves out the stale local reason

R7 now defers to is_debt: debt status, contested, or an unstamped or stale local.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-19T09:42:14+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  cli-help-matches-code: none
  cli-help-rich-markup-safe: none
  cli-reference-ste: none
  site-code-blocks-render: none
  site-pages-marker-own-line: none
  site-top-bar-phone-layout: none
  skill-prose-matches-engine: none
row_kinds:
  cli-help-matches-code: none
  cli-help-rich-markup-safe: none
  cli-reference-ste: none
  site-code-blocks-render: none
  site-pages-marker-own-line: none
  site-top-bar-phone-layout: none
  skill-prose-matches-engine: none
run_gate: developer
run_kind: none
```
