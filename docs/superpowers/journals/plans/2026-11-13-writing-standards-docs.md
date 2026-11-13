<!-- fr:journal-schema=4 -->
# Journal: 2026-11-13-writing-standards-docs

<!-- fr:journal kind=decision scope=plan id=plan-gate-last created=2026-11-13T21:49:14+00:00 -->
### plan-gate-last · decision · The CI gate turns on in the last phase

ci-ok depends on site-build (.fr/ci.yaml gate_checks: [ci-ok]); turning the writing-standard step on before every page passes would make every phase's tests: ci evidence red.

<!-- fr:journal kind=decision scope=plan id=plan-fact-keeper-in-review created=2026-11-13T21:49:14+00:00 -->
### plan-fact-keeper-in-review · decision · Fact-keeper reviews run in each phase's review step

A phase executor cannot dispatch agents; the executor writes each page's baseline outside the repo and the orchestrator dispatches one fact-keeper per page during review-phase, recording the results in that record (R8).

<!-- fr:journal kind=decision scope=plan id=baseline created=2026-11-13T22:11:09+00:00 -->
### baseline · decision · Rewrite baseline: 63764b87921b4f741414cff4def0d5ee205547c9

git merge-base HEAD origin/main at the start of the rewrite (after merging origin/main at 63764b879, #1435, in phase 1); every --preserve-from and fact review in phases 2–6 uses it

<!-- fr:journal kind=discovery scope=plan id=ws-starting-totals created=2026-11-13T22:11:09+00:00 phase=1 -->
### ws-starting-totals · discovery · Starting writing-standard totals (pin 3b0c7d0, before the terms file) (phase 1)

`bash scripts/check-writing-standards.sh /home/user/blog-craft`, exit 1, without `.writing-standard-terms`, re-measured after the merge of origin/main at 63764b879 (identical to the pre-merge run):
- guides (`docs/*.md`, ste): 137 FAIL, 243 WARN
- reference (`docs/reference/*.md`, ste; cli.md opted out): 22 FAIL, 49 WARN
- explainers (`docs/explainers/*.md`, plain-language; why-fr.md elements-of-style, index.md none): 1 FAIL, 585 WARN
FAIL kinds: 159 `sentence_length` (ste), 1 `average_sentence_length` (01-fr-goal.md, 23.4 words/sentence).
The spec's reference figure (39 FAIL) included cli.md, which now carries `writing_standard: none`;
the spec's cloud-setup.md plain-language failure no longer applies, as guides run under ste.

<!-- fr:journal kind=discovery scope=plan id=ws-terms-effect created=2026-11-13T22:11:09+00:00 phase=1 -->
### ws-terms-effect · discovery · .writing-standard-terms removes 65 warnings and no FAIL (phase 1)

With 15 abbreviations (API, CI, CLI, HEAD, HTML, ID, JSON, PATH, PR, README, REST, SSH, UI, URL, YAML)
and 6 -ing fr nouns (debugging, finding, landing, pending, sibling, warning), WARN totals go
877 → 812: guides 243 → 221, reference 49 → 46, explainers 585 → 545. FAIL totals are unchanged
(137 / 22 / 1). Abbreviation warnings left for the rewrite: AI, ISO, OPEN, POM, TDD (spell out
or code-format). Vocabulary words such as `refuse`/`require`/`create` were deliberately not listed:
a page can use the standard's replacement.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-13T22:11:09+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a one-assertion smoke test; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-13T22:11:09+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

a one-line pin and a flat terms list; no code to restructure

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-13T22:11:09+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

a prose rule edit plus its generated mirror; nothing to restructure

<!-- fr:journal kind=discovery scope=plan id=ws-terms-effect-2 created=2026-11-13T22:16:46+00:00 phase=1 -->
### ws-terms-effect-2 · discovery · .writing-standard-terms after review: 19 terms, 63 warnings removed (phase 1)

Supersedes ws-terms-effect's numbers. Review findings p1-r3 and p1-r4: dropped landing (it also exempted the verb at docs/gate-backfill.md:138) and JSON (it removed no warning on any page). 19 terms remain: 14 abbreviations (API, CI, CLI, HEAD, HTML, ID, PATH, PR, README, REST, SSH, UI, URL, YAML) and 5 -ing fr nouns (debugging, finding, pending, sibling, warning). WARN totals with the file: guides 223, reference 46, explainers 545 (814; 877 without it, so 63 removed). FAIL totals are unchanged (137 / 22 / 1). The two landing warnings (gate-backfill.md:138, docs-currency.md:227) are left to their rewrite in phase 3.
