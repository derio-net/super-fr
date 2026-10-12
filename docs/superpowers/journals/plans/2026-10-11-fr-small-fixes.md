# Journal: 2026-10-11-fr-small-fixes

<!-- fr:journal kind=discovery scope=plan id=p1-d-fake-state-case created=2026-10-12T15:43:37+00:00 phase=1 -->
### p1-d-fake-state-case · discovery · FakeGhClient stores the state string as given (phase 1)

The fake keeps whatever state edit_issue_state received, and GithubTracker previously passed lowercase closed. It now passes CLOSED and the fake refuses anything but OPEN or CLOSED; the existing done test asserts CLOSED.

<!-- fr:journal kind=discovery scope=plan id=p1-d-models-handler created=2026-10-12T15:43:37+00:00 phase=1 -->
### p1-d-models-handler · discovery · ModelsError handled by one decorator, with resolve --record handled inside the advance (phase 1)

fr.commands.common.models_errors_exit wraps advance and the five fr models commands. run start warns in place. resolve --record catches inside _advance_after_record, so the applied record is reported. No harness means no models.yaml read, as before.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-12T15:43:37+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

release fragment, acceptance rows and quality gate; no code to refactor

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-12T15:52:37+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · load_models' YAML error takes PyYAML's context line, not the problem or its line/column (phase 1)

models.py:62-64: str(exc)'s first line for a MarkedYAMLError is the context (`while parsing a flow sequence`); the problem (`expected ',' or ']'…`) and the position were lost.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-12T15:52:37+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · Tripwire could false-pass: titles matched as substrings anywhere on a 3,090-char line, no order, COUNT_PHRASE missed 'seven board columns'/'six-column' (phase 1)

test_tripwire_triage_board_columns.py:21,37-39. The board line also carries the runner and cloud-driver paragraphs; #1107's 'Needs you · start/review' show the substring risk. The docstring test checked only the count, not titles.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-12T15:52:37+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · probe rstrip(')] ') also ate a provider message's own trailing ')' (phase 1)

probe.py:113: `…p/m (preview)` with no wrapper became `…(preview`. The spec's 'inner parens survive' held only away from the end.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-12T15:52:37+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · Corrupt-config CLI tests skipped fr models set/get/apply, advance --redispatch, a cli step after the resolved one, and the OpenCode start path (phase 1)

test_models_corrupt_config.py:94-103. Behaviour was correct (shared decorator / chain-start read), but nothing pinned those entry points.

<!-- fr:journal kind=discovery scope=plan id=p1-circular-import-triage-kanban created=2026-10-12T15:52:37+00:00 phase=1 -->
### p1-circular-import-triage-kanban · discovery · Importing fr.commands.triage_kanban_cmd alone fails with a circular import (pre-existing) (phase 1)

`python -c 'import fr.commands.triage_kanban_cmd'` raises ImportError: cannot import name '_fail' from partially initialized module (on this branch, which adds no import to it; the cycle predates this change). It surfaced when the new tripwire's docstring test ran alone; the test now reads the docstring via ast. Not caused by this change: out of scope, noted for triage.

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-10-12T15:52:37+00:00 phase=1 -->
### p1-review-1 · review · phase 1 review: 4 findings (p1-r1..p1-r4 in scope, all fixed), none out of scope (phase 1)

An independent read-only reviewer checked R1–R7 and §A–§D against the diff d5c38cdc..58372ca3, every load_models site (all reached through the decorated entry or the chain-start read; no harness → no read; triage left alone per Non-goals), the strict fake's callers, the probe fixture, the mirrors and the fragment, and ran the targeted tests (67 passed). The orchestrator verified each finding against the code and fixed all four test-first in 3e215f57 and the follow-up: problem+position YAML message, a balance-aware wrapper trim, an exact ordered column-list tripwire with a wider count regex and a docstring title check, and new CLI tests for the uncovered entry points. Targeted suites: 81 passed, then 8 passed for the tripwire alone; ruff and mypy clean.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-12T15:52:37+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: load_models' YAML error takes PyYAML's context line, not the problem or its line/column (phase 1)

models._yaml_problem uses exc.problem + problem_mark (line/column, 1-based), falling back to the first line; test_load_models_reports_the_problem_and_its_position covers three error kinds.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-12T15:52:37+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: Tripwire could false-pass: titles matched as substrings anywhere on a 3,090-char line, no order, COUNT_PHRASE missed 'seven board columns'/'six-column' (phase 1)

The tripwire extracts the `across its columns (…)` list and compares it to list(COLUMN_TITLES.values()) exactly and in order. COUNT_PHRASE now catches `seven board columns`, `six-column` and `9 columns` (parametrized test), and the docstring test also refuses a column list and titles.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-12T15:52:37+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: probe rstrip(')] ') also ate a provider message's own trailing ')' (phase 1)

probe._trim_wrapper drops a trailing ) or ] only while it is unbalanced; test_a_providers_own_trailing_parenthesis_survives_the_trim covers bare and wrapped messages.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-12T15:52:37+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: Corrupt-config CLI tests skipped fr models set/get/apply, advance --redispatch, a cli step after the resolved one, and the OpenCode start path (phase 1)

Added CLI tests: fr models get/set/apply exit 2, advance --redispatch exit 2, start on OpenCode warns once, and a record resolve whose next step is kind: cli reports 'record applied…' with the cli step still pending.
