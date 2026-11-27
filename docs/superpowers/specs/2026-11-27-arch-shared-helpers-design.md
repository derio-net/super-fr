# Shared helpers from the #1318 review: strict YAML loader, record placement, hermetic git, timestamp readers

Issues: derio-net/super-fr#1512, derio-net/super-fr#1513, derio-net/super-fr#1514,
derio-net/super-fr#1523.

## Background

The architecture review for #1318 (`docs/superpowers/audits/2026-11-16-architecture-review.md`,
section 3) found code that is copied instead of shared. Four of its slices are small and touch
no giant module. Every location below was checked on `main` at `da66accc5`. No behaviour
changes. Each slice moves a copy to one owner and adds a guard so that no new copy appears.

- **Duplicate-key YAML detector (#1512).** Two `SafeLoader` subclasses hold the same
  `construct_mapping` detector: `packages/fr/src/fr/artifacts/structure.py:46` raises a
  `ConstructorError` with marks, and `packages/fr/src/fr/harness/model.py:153` raises
  `HarnessError(f"duplicate key {key!r} in parity data")`. Harness keeps its own copy because
  `fr.artifacts.structure` imports the plan parser and pydantic models
  (`harness/model.py:160-163`). `fr/lenses/model.py:18` and `fr/isolation/scaffold.py:911`
  import the artifact module's private `_StrictLoader`. So does `tests/unit/test_init_scaffold.py:1255`.
  `fr/yamlio.py` imports only `yaml`. Open issue #1286 will switch fr's YAML reading to libyaml
  through `fr.yamlio`. That switch stays #1286's job: the shared loader is still based on the
  pure-Python `yaml.SafeLoader`.
- **Record-file placement (#1513).** `_record_file` writes
  `docs/superpowers/runs/r1.records/<stem>.yaml` under a tmp root. It is defined eleven times
  in `tests/unit/`: `test_migration_record_contract.py:63`, `_delegated.py:30`,
  `_exit_gates.py:31`, `_input_unconfirmed.py:29`, `_questions.py:36`, `_shape.py:35`,
  `_status_split.py:43`, `_visual.py:30`, `test_record_acceptance_v8.py:138`,
  `test_record_amendments.py:41` and `test_record_lens.py:171`. Some copies take a `stem`,
  some hard-code `implement-phase__phase-1`, and most default `text` to the module's
  historical record.
- **Hermetic git fixture (#1514).** The same function-scoped autouse fixture sets
  `GIT_CONFIG_GLOBAL` to the null device and `GIT_CONFIG_NOSYSTEM=1` in
  `tests/unit/test_gatebackfill_candidates.py:28`, `test_gatebackfill_delivery.py:31`,
  `test_gatebackfill_discharged.py:31`, `test_gatebackfill_render.py:19` and
  `test_merge_evidence.py:31`. `test_status_owed.py:73` sets the same two variables and also
  stubs `fr.archive._fetch`. Out of scope, because their policies differ: the fixtures that set
  `HOME` or a per-test config directory (`test_isolation_branch_classify.py`,
  `test_isolation_preserve.py`, `test_gatebackfill_closes.py`, `test_release_status.py`), and
  `test_archive_cmd._hermetic`.
- **Small duplicate readers (#1523).**
  1. The `--gate` help of `fr journal add` (`commands/journal_cmd.py:222`) spells the six
     members of `fr.gates.Gate` by hand.
  2. `_created_since` (`triage/collect.py:1345`) repeats `fr.triage.timestamps.parse_aware`'s
     rule inline: missing, unparseable or naive is unknown, and unknown counts as yes.
  3. `_pr_time` (`commands/triage_batch_cmd.py:2423`) has `parse_aware`'s contract on its
     value. That module already imports `parse_aware` (`:369`).
  4. `_instant` (`usage/compare.py:173`), `_parse` (`debt/engine.py:309`) and an inline block
     in `usage/backfill.py:165-169` each read a stamp with a naive time taken as UTC and a bad
     value as `None`. That is a different contract from `parse_aware`'s, and
     `fr/triage/timestamps.py`'s docstring keeps it out of that module.
     `tests/unit/test_triage_timestamps.py` already fails when a second function has
     `parse_aware`'s body. The review found two more readers with the same contract that the
     issue did not list: `_parse_instant` (`run/liveness.py:307`, where a non-string gives
     `None` through `TypeError`) and `_created` (`triage/claims.py:174`, where a non-string
     gives `None`). Both are folded in too, so the one-owner claim is true.
- **A second hermetic-git copy.** `test_merge_evidence.stub_fetch` (`tests/unit/test_merge_evidence.py:36-48`)
  sets the same two variables before it stubs `fr.archive._fetch`. Six other modules import it
  (`test_archive_all_debug.py`, `test_archive_branch.py`, `test_archive_cmd.py`,
  `test_status_cmd.py`, `test_status_sweep.py`, `test_archive_nudge_landed.py`).

## Requirements

R1. One duplicate-key detector exists: `fr.yamlio.StrictLoader`, a `yaml.SafeLoader` subclass. The artifact validator, the lens reader, the profile scaffold and the harness parity reader all load through it or through a subclass of it.
R2. Each reader keeps its own error translation. The artifact validator, lenses and scaffold see the same `ConstructorError` message and marks as today. The harness reader raises the same `HarnessError` text. An unhashable key is still skipped by the duplicate check. Callers of plain `safe_load` do not become strict.
R3. `fr/yamlio.py` imports nothing from `fr`, and no module under `packages/*/src` other than `fr/yamlio.py` defines a `construct_mapping` method. A test guards both.
R4. One test helper, `tests.unit.record_helpers.write_record(root, text, *, stem="implement-phase__phase-1") -> Path`, writes a record to `root/docs/superpowers/runs/r1.records/<stem>.yaml` with the exact bytes it is given. Each of the eleven modules calls it and passes its own historical payload explicitly. None keeps a placement function of its own. A test guards this, and one test checks the helper's path and bytes.
R5. One fixture-only test module, `tests/unit/hermetic_git.py`, defines the function-scoped, non-autouse fixture `hermetic_git`, which sets `GIT_CONFIG_GLOBAL=os.devnull` and `GIT_CONFIG_NOSYSTEM=1` through a `MonkeyPatch`. The six modules activate it explicitly. None of them keeps its own `setenv` of those two variables. `test_status_owed.py` keeps its `fr.archive._fetch` stub in a fixture of its own. `test_merge_evidence.stub_fetch` sets the variables by calling the shared `apply_hermetic_git(monkeypatch)`, so its importers keep the same environment. A test guards the six modules, and a test shows the variables are restored after use.
R6. The `--gate` option's help string for `fr journal add` is built from `get_args(fr.gates.Gate)` and stays byte-identical. A test reads that string from the click parameter (not the rendered `--help`, which rich wraps) and checks that it names every member of `GATES`.
R7. `_created_since` and `_pr_time` read their stamps through `parse_aware`. An unknown or naive creation time still counts as yes in `_created_since`, and `_pr_time` still returns `None` for one.
R8. One reader, `fr.utc_time.parse_as_utc(value: object) -> datetime | None`, holds the naive-as-UTC contract: a value that is missing, empty, not a string or unparseable gives `None`, `Z` gives UTC, and a naive time is read as UTC. `usage/compare.py`, `debt/engine.py`, `usage/backfill.py`, `run/liveness.py` and `triage/claims.py` use it. Each keeps its own handling of `None` (backfill still treats an unreadable `captured_at` as worth reading). The body scan in `tests/unit/test_triage_timestamps.py` also fails when a second function has `parse_as_utc`'s body.
R9. Prose that names the old owner names the new one: `.claude/rules/artifact-versioning.md` (and its generated OpenCode mirror) and the two comments in `scripts/sync-opencode.py` and `tests/unit/test_opencode_agent_mirror.py`.

## Design

### Strict loader (R1–R3)

`fr/yamlio.py` gains `StrictLoader(yaml.SafeLoader)`. Its `construct_mapping` holds the detector
from `artifacts/structure.py:61-78` unchanged. On a repeat it calls a hook,
`duplicate_key(node, key_node, key) -> NoReturn`, which by default raises the `ConstructorError`
the artifact validator raises today. Its docstring keeps the reason (the matrix row that lost a
`levels:` ref).

- `artifacts/structure.py`: drop `_StrictLoader`, and `_load_mapping` loads with
  `fr.yamlio.StrictLoader`.
- `harness/model.py`: `_StrictLoader(StrictLoader)` overrides only `duplicate_key` to raise the
  existing `HarnessError`. The import-cost reason for a local copy goes away, because
  `fr.yamlio` imports only `yaml`.
- `lenses/model.py`, `isolation/scaffold.py` and `tests/unit/test_init_scaffold.py` import
  `fr.yamlio.StrictLoader`.
- A new guard test, `tests/unit/test_yamlio_strict.py`, does three things: an AST scan that no
  `packages/*/src/**/*.py` file other than `fr/yamlio.py` defines `construct_mapping`; an AST
  check that `fr/yamlio.py` imports only the standard library and `yaml`; and direct tests of
  the default error (message and marks) and of the unhashable-key skip. The existing
  duplicate-key tests in `test_harness_matrix.py` and `test_validate_artifacts.py` stay as they
  are.

### Record placement (R4)

`tests/unit/record_helpers.py` defines `write_record`, following the pattern of
`tests/unit/acceptance_helpers.py`. Each module's `_record_file(...)` call becomes
`write_record(tmp_path, <payload>[, stem=...])`, with the payload the old default supplied
spelled out at the call site. The guard (`tests/unit/test_record_helpers.py`) parses the eleven
modules and fails when any of them defines a function whose body holds both the string
`r1.records` and a `write_text` call. It also checks the helper's path and bytes in a tmp root.

### Hermetic git (R5)

`tests/unit/hermetic_git.py` defines `apply_hermetic_git(mp: pytest.MonkeyPatch) -> None` and
the fixture `hermetic_git(monkeypatch)` that calls it. Each of the six modules imports the
fixture (`# noqa: F401`) and declares `pytestmark = pytest.mark.usefixtures("hermetic_git")`,
merged with any `pytestmark` it already has. `test_status_owed.py` keeps an autouse
`_stub_archive_fetch` fixture for its `fr.archive._fetch` stub. `test_merge_evidence.stub_fetch`
replaces its two `setenv` calls with `apply_hermetic_git(monkeypatch)` and keeps its signature, so
the six modules that import it do not change. The guard
(`tests/unit/test_hermetic_git.py`) uses an AST check that each of the six modules names
`hermetic_git` in a `usefixtures` mark and calls `setenv` with neither variable name. A
restoration test calls `apply_hermetic_git` on a fresh `MonkeyPatch`, calls `undo()`, and
checks that the previous values are back.

### Readers (R6–R8)

- `journal_cmd.py`: `help=f"--kind decision only: the gate role that owns it ({'|'.join(get_args(Gate))})."`.
  The test (`tests/unit/test_journal_gate_help.py`) finds the `--gate` parameter of `journal add`
  in `typer.main.get_command(app)` and compares its `.help` to today's literal string, then checks
  every `GATES` member.
- `collect.py`: `created = parse_aware(pr.created_at)`; `return created is None or created >= at`.
- `triage_batch_cmd.py`: `_pr_time` becomes `return parse_aware(str(stamp) if stamp else None)`.
  Its callers do not change.
- `fr/utc_time.py` (new, standard library only): `parse_as_utc` as R8 states. Its docstring
  points at `parse_aware` as the other contract. `compare._instant` and `engine._parse` are
  removed, and their callers call `parse_as_utc`. `backfill._worth_reading` becomes
  `at = parse_as_utc(mine.captured_at); if at is None: return True`. Python ≥3.14 already
  accepts `Z` in `fromisoformat`, so backfill's old lack of a `Z` replacement changes nothing.
  `liveness._parse_instant` and `claims._created` are removed: `stalled_attempts` calls
  `parse_as_utc(attempt.dispatched)`, and `claims` calls `parse_as_utc(comment.get("created_at"))`.
  The non-string check in `parse_as_utc` covers liveness's old `TypeError` catch and claims's
  old `isinstance` check.
- `tests/unit/test_utc_time.py` tests `parse_as_utc` directly: `None`, `""`, a non-string,
  garbage, `Z`, naive and an offset.
- `test_triage_timestamps.py`'s scan gains `parse_as_utc` as a second owner: a function with
  either reader's body outside its owning module fails.

### Docs and release

The change touches `packages/*/src`, so it adds the patch fragment
`.changes/feat-batch-arch-shared-helpers.yaml`. No page describes these helpers. The pages whose
`covers:` match a touched path (usage, journal, triage, the triage batch command) get a
`reviewed` stamp, "still true; shared-helper refactor, no behaviour change". `fr docs check`
decides which pages those are.

## Design shape

```
packages/fr/src/fr/
  yamlio.py                 + StrictLoader (detector; duplicate_key hook → ConstructorError)
  utc_time.py               + parse_as_utc (naive → UTC)              [new]
  artifacts/structure.py    - _StrictLoader            → yamlio.StrictLoader
  harness/model.py          ~ _StrictLoader(StrictLoader): duplicate_key → HarnessError
  lenses/model.py           ~ import yamlio.StrictLoader
  isolation/scaffold.py     ~ import yamlio.StrictLoader
  commands/journal_cmd.py   ~ --gate help from get_args(Gate)
  triage/collect.py         ~ _created_since via parse_aware
  commands/triage_batch_cmd.py ~ _pr_time via parse_aware
  usage/compare.py          - _instant                 → parse_as_utc
  usage/backfill.py         ~ inline parse             → parse_as_utc
  debt/engine.py            - _parse                   → parse_as_utc
  run/liveness.py           - _parse_instant           → parse_as_utc
  triage/claims.py          - _created                 → parse_as_utc
tests/unit/
  record_helpers.py         + write_record             ← 11 modules drop _record_file
  hermetic_git.py           + apply_hermetic_git, fixture ← 6 modules drop setenv copies;
                                                           test_merge_evidence.stub_fetch calls it
  test_yamlio_strict.py     + single owner, import purity, default error
  test_record_helpers.py    + no placement copies, helper bytes/path
  test_hermetic_git.py      + activation, no setenv copies, restoration
  test_journal_gate_help.py + --gate help string from Gate
  test_utc_time.py          + parse_as_utc contract
  test_triage_timestamps.py ~ scan also guards parse_as_utc
  test_init_scaffold.py     ~ import yamlio.StrictLoader
  test_opencode_agent_mirror.py ~ comment names the new owner
.claude/rules/artifact-versioning.md  ~ detector is fr.yamlio.StrictLoader
.opencode/instructions/artifact-versioning.md  ~ regenerated mirror
scripts/sync-opencode.py              ~ comment names the new owner
.changes/feat-batch-arch-shared-helpers.yaml  + patch fragment
docs/** pages fr docs check names     ~ reviewed stamp only
```

## Verification

strategy: none
gate: developer

This is a refactor with no behaviour change. The unit suite in this PR's CI proves it: the
existing duplicate-key, timestamp and migration tests, plus the new guards. It adds no
acceptance rows (operator decision): no product behaviour changes, and the guards are tests,
not business claims.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-27-arch-shared-helpers | `derio-net/super-fr` | `2026-11-27-arch-shared-helpers` | — |
