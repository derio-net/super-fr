<!-- fr:journal-schema=4 -->
# Journal: 2026-11-25-wave-plan-file-overlap

<!-- fr:journal kind=decision scope=plan id=plan-overlap-one-paragraph created=2026-11-25T15:44:18+00:00 phase=1 -->
### plan-overlap-one-paragraph · decision · A card's overlap sentences render as one paragraph (phase 1)

The spec asks for one `<p class="overlap">` per card detail, so a card in several overlaps joins its sentences with spaces inside that one paragraph, instead of one paragraph per overlap.

<!-- fr:journal kind=discovery scope=plan id=plan-overlap-checkout-paths-optional created=2026-11-25T15:44:18+00:00 phase=1 -->
### plan-overlap-checkout-paths-optional · discovery · The driver's checkout map holds optional paths (phase 1)

`checkout_paths` is `dict[str, Path | None]`, so `write_board` and `source_for_clones` take `Mapping[str, Path | None]`; a None value reads as no clone of the repo.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-25T15:44:18+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the check command change is one call and one print block; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-25T15:44:18+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

docs, fragment and acceptance moves only; no code to refactor

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-25T15:50:06+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · A branch YAML with a bad-date scalar raises ValueError and crashes fr triage check (phase 1)

plan_overlap._load caught only TriageError/YAMLError; yaml.safe_load('a: 2020-13-45') raises ValueError (reproduced), and check_command had no guard, so check exited non-zero against R6.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-25T15:50:06+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · _is_glob treats `[` as a glob, so identical bracketed literal paths never overlap (phase 1)

A literal such as app/[id]/page.tsx was moved to the glob set and never compared literal-to-literal: a false negative.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-25T15:50:06+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · fr-triage.md does not say check reads only the cwd clone's repo (phase 1)

R9: a reader running check from another repo sees every batch not compared; the page did not say so.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-25T15:50:06+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · The board re-reads every batch's plan with git subprocesses on every driver pass (phase 1)

About 3 + phases git calls per dispatched batch per pass, with no cache.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-25T15:50:06+00:00 phase=1 state=open review_scope=out -->
### p1-r5 · finding [open] (reviewer: out of scope) · overlaps() compares repo names case-sensitively (phase 1)

Relies on batch_repo's single spelling; the casing rule predates this change.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-25T15:50:06+00:00 phase=1 -->
### review-p1 · review · phase 1 code review: 5 findings (phase 1)

Dispatched reviewer read the diff 238e6c66..68f7df2f against spec R1-R9 and plan phase 1; ran 135 targeted tests green. Findings p1-r1..p1-r5 (4 in scope, 1 out). Verdict: with fixes. Fixes landed in one commit with new tests (bad-date YAML unreadable; bracketed literal path; check exits 0 when the read raises).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-25T15:50:06+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: A branch YAML with a bad-date scalar raises ValueError and crashes fr triage check (phase 1)

_load also catches ValueError and RecursionError; check_command uses the new checked_report, which turns any unexpected exception into one not-compared line. Tests: test_a_yaml_scalar_that_is_not_a_real_date_is_unreadable_never_raised, test_check_exits_zero_when_the_overlap_read_raises.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-25T15:50:06+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: _is_glob treats `[` as a glob, so identical bracketed literal paths never overlap (phase 1)

_is_glob counts only `*` and `?`; test_a_bracketed_literal_path_is_a_literal_not_a_glob pins both the literal-literal and the glob-literal case.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-25T15:50:06+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: fr-triage.md does not say check reads only the cwd clone's repo (phase 1)

fr-triage.md's plan overlap bullet now says check reads only the clone it runs in (its repo's batches), the driver's page reads every clone it was given, and an empty set means nothing overlaps, not nothing read.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-25T15:50:06+00:00 phase=1 state=refuted resolves=p1-r4 -->
### p1-r4-resolved · finding [refuted] · resolves p1-r4: The board re-reads every batch's plan with git subprocesses on every driver pass (phase 1)

The cost is bounded by the in-flight batches (the driver's max_inflight cap) at a few local git plumbing calls each (cat-file, ls-tree, show on refs the pass already fetched), beside the much larger per-pass work the driver already does (fetches, trial merges, cursor reads). A cross-pass cache would add process-global state keyed on ref commits for no measured cost; the board is a view the driver renders once per pass.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-25T15:50:06+00:00 phase=1 state=open resolves=p1-r5 out_of_scope=true -->
### p1-r5-resolved · finding [out-of-scope] · resolves p1-r5: overlaps() compares repo names case-sensitively (phase 1)

batch_repo and Facts.config_for already decide the repo spelling for every triage reader; this change adds no new casing rule, and source_for_clones lowercases where it matches a clone.
