<!-- fr:journal-schema=3 -->
# Journal: 2026-11-02-test-plan-heading

<!-- fr:journal kind=repro scope=debug id=f65495f1f836 created=2026-11-02T15:15:38+00:00 -->
### f65495f1f836 · repro · A numbered '## 6. Test Plan (…)' heading is read as no Test Plan

Repro: spec with `## 6. Test Plan (post-merge, operator-driven)` and one list item. `fr.spec.test_plan_steps(text)` returns [] (no section), so `fr closeout outcome --step 1 --owed` refuses 'has no `## Test Plan` section', `fr archive` skips the R19 hold, `fr debt` lists nothing. Separately, acceptance/check.py, acceptance_cmd inventory, run/closeout.py and plan_ops self-review test `'## Test Plan' in text` (substring), which DOES match '## Test Plan (post-merge…)' but not '## 6. Test Plan' — so two readers disagree on the same spec. Live: docs/superpowers/specs/2026-07-23-hermes-agent-compat-design.md:353. Archived: ~55 near-miss headings (frozen, not touched).

<!-- fr:journal kind=root-cause scope=debug id=679804c51cd7 created=2026-11-02T15:15:45+00:00 -->
### 679804c51cd7 · root-cause · The Test Plan heading is a keyword in code with no stated contract and no shared reader

Root cause: `fr/spec.py` _SECTION_RE (^## Test Plan\s*$) is exact while four other modules carry their own literal (acceptance/check.py TEST_PLAN_MARKER, run/closeout.py TEST_PLAN_MARKER, plan_ops.py, acceptance_cmd via check), each a substring test. No skill/agent/rule tells a spec writer the exact spelling, writers number sections, and every reader treats a near-miss as 'absent' — the one answer that makes every downstream gate (R19 hold, closeout outcome, owed/debt) pass silently. Operator's fix: one shared matcher returning exact | near-miss | none; near-miss is an error everywhere, never absent.

<!-- fr:journal kind=ruled-out scope=debug id=61d90c52d637 created=2026-11-02T15:48:23+00:00 -->
### 61d90c52d637 · ruled-out · A tolerant matcher (accept 'N.' prefixes and suffixes) — rejected by the operator

Making _SECTION_RE accept '## 6. Test Plan (…)' would have fixed the 41 existing specs silently, but left the contract unstated and every future variant (### level, 'Test plan', '§6') one more regex edit away from the same silent miss. Operator's decision (brief): keep the heading exact, make near-misses loud.

<!-- fr:journal kind=hypothesis scope=debug id=d70592a8bc18 created=2026-11-02T15:48:26+00:00 -->
### d70592a8bc18 · hypothesis · A ValueError-based near-miss error would recreate the bug inside existing handlers — confirmed, so it is a plain Exception

debt_cmd._held catches (PlanSchemaError, OSError, ValueError, …) and returns []; plan_ops' ops_gap guard catches ValueError and sets gap=[]; ops/gate's ops-gap read says 'not checked'. A near-miss raised as ValueError would be read as 'no hold' / 'no gap' — the original defect, one layer down. TestPlanHeadingError subclasses Exception; tests/unit/test_test_plan_heading.py::test_the_error_is_not_a_value_error pins it, and each handler that should see it names it explicitly.

<!-- fr:journal kind=ruled-out scope=debug id=96037aead0db created=2026-11-02T15:48:28+00:00 -->
### 96037aead0db · ruled-out · Counting archived near-misses as 'has a Test Plan' in the staleness guard

Measured over this repo: 3 archived specs with a numbered heading are uncited, so treating archived near-misses as Test Plans would add 3 new staleness errors on frozen specs. Archived specs now count only an exact heading and are never judged for near-misses; the old substring test and the new exact-only test agree on every archived spec here (no verdict changed).

<!-- fr:journal kind=finding scope=debug id=cac893e4c386 created=2026-11-02T15:48:31+00:00 state=fixed -->
### cac893e4c386 · finding [fixed] · One Test Plan heading matcher; every reader refuses a near-miss

fr.spec.find_test_plan_heading (exact | near-miss | None) replaces _SECTION_RE and the four substring literals (acceptance/check.py, run/closeout.py, plan_ops.py, acceptance_cmd). Near-miss -> validate_spec problem, fr plan self-review error, fr archive hold, fr closeout outcome refusal, acceptance staleness error (live only), fr debt 'specs' source unavailable, pickup brief FIX FIRST line, triage close-out TriageError. Repair test-plan-heading renames a '##' near-miss in live specs (dogfooded on 2026-07-23-hermes-agent-compat). Contract stated in fr-brainstorming + fr-spec-reviewer (agents kind 1->2). Pinned by tests/unit/test_test_plan_heading.py (38 tests, matcher red first: ImportError).
