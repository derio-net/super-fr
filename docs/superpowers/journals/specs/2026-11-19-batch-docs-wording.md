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
