> [!WARNING]
> **Not ready to merge until all three hold:** CI green · an explicit review OK from the operator · no commits since that OK (fr's own `chore(fr):` record commits excepted). Draft until then.

## Summary

Closes #624. `fr acceptance set-status` can now **remove** a stale evidence ref:

```bash
fr acceptance set-status --id <row> --status <s> --notes "<why>" \
  --drop-level unit=<repo>:<old-path> --level unit=<repo>:<new-path>
```

- `--drop-level <level>=<ref>` can be repeated. It is applied in the **same single rewrite** as the status/notes change, and all three committed reports are regenerated. `--notes` is still required.
- These are refused with **exit 2**, leaving `matrix.yaml` and every report byte-identical:
  - a ref that is not on the row;
  - the same ref named in both `--level` and `--drop-level`;
  - an unknown level key;
  - a malformed value (the error names `--drop-level`).
- A repeated drop of the same ref is deduplicated.
- Dropping a `ci` row's last ref is allowed. `fr acceptance check` stays the gate.
- **Engine:** drops reach `fr.record.apply` through a verb-only `RecordTarget.acceptance_drops`. The engine refuses misaligned drops on its own, without relying on the CLI to check first:
  - drops passed with a run id;
  - drops for a row that has no item in the record;
  - drops on a row the record creates;
  - drops on a row the record names twice;
  - drop entries that name no ref.
- `fr.acceptance.edit.drop_levels` is the single definition of "on the row", shared by the CLI and the engine.
- **Docs:** `.claude/rules/acceptance-matrix.md` "How" and its OpenCode mirror. Hermes excludes this rule.
- **Matrix:** the new row `lifecycle-acceptance-drop-level` was moved to `ci` **by the new verb itself**.
- **Version:** patch bump to **4.22.1**.

**Spec:** `docs/superpowers/specs/2026-09-26-acceptance-set-status-drop-level-design.md`
**Plan:** `docs/superpowers/plans/2026-09-26-acceptance-set-status-drop-level/`

## Decisions (operator Q&A)

- **Carrier: CLI only.** Step records keep their shape: `AcceptanceItem` is unchanged, so the `record` kind needs no stamp bump or migration, and this stays a patch. Step records still cannot drop refs; a step that needs to runs the verb.
- **Same ref in `--level` and `--drop-level`:** refused, exit 2.
- **Emptying a ci/scheduled row's evidence:** allowed.

## Operator gates

```text
brainstorm: operator gate answered by the operator
```

## Out-of-scope findings: which to file?

These are listed below under fr's marker. None needs filing on its own, since all three are low value. Suggested: skip p1-r4 and p3-r3, and fold p2-r4 into a future "engine refuses contradictions too" hardening if one ever comes up.

**Discovered during delivery (a process defect, worth filing):** `deliver`'s tests-log verifier (`fr.run.telemetry.orchestrator_wrote_since` plus the mtime-in-window check in `run_cmd._verify_tests_log`) accepts only a **foreground** Bash call whose command text names the log **literally**.
- A `run_in_background` suite, which the brief's own `long_commands` rule recommends, "ends" at launch. So its log's mtime always falls outside the window, and fr refuses it with "its bytes were not written by the command of yours that names it".
- A log named through a shell variable (`> $L`) is invisible to the verifier: "no command of YOURS wrote it".
- Here it took three suite runs to satisfy. The refusal messages name neither cause.

## Test Plan

The spec's Test Plan is unit-level and runs in CI: `tests/unit/test_acceptance_set_status.py`, `tests/unit/test_record_apply.py`. **There is no post-merge, operator-driven step**, because nothing deploys.

Verified locally by the delivering session:
- **Full suite:** `uv run pytest -n auto -q` gave 5478 passed, 97 skipped.
- **Lint and types:** `ruff check` and `ruff format --check` are clean, and `mypy` over all four packages is clean.
- **fr checks:** `fr acceptance check` passed, and `bump-version.py --check` shows 4.22.1 everywhere.
- **Flaky test, not caused by this branch:** one full run hit a load-related timeout in `test_suite_isolation_inherited_columns.py`. It is a subprocess probe with a 120s limit, and it took 94s when run alone on this host. The next two full runs were green.

## Acceptance

- **Debt** (`fr acceptance status`): ci 206, not-implemented 9, scheduled 1, skipped 23.
  - This PR moves one row to ci and adds no debt.
  - The 5 archived-spec ref warnings predate this change.
- **Rows added since `origin/main`:** `lifecycle-acceptance-drop-level` (now `ci`, unit).
  - **What it pins:** you can remove a stale evidence ref, in the same rewrite as a status move, with no hand-edited YAML. That closes the one hole in the matrix rule's "never hand-edit" promise.
  - **Why it's business-level:** it is about what the lifecycle guarantees you, not about parser internals.

## Manual phases

None.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<!-- rendered by fr for run 2026-09-26-fix-624-set-status-drop-level; edit above this line only -->

## Findings

- `sr-1` (spec) — §2.C says drops reach the engine via RecordTarget, but _acceptance_writes never receives the target — **fixed**
- `sr-2` (spec) — Engine behaviour is undefined for drops that do not line up with record.acceptance — **fixed**
- `sr-3` (spec) — Test Plan covers only the CLI; the engine-side drop_levels refusal and drop_levels itself go untested — **fixed**
- `sr-4` (spec) — §2.D hedges on the mirrors: OpenCode does carry acceptance-matrix.md, Hermes does not — **fixed**
- `sr-5` (spec) — Reusing _parse_levels for --drop-level prints a wrong flag name on malformed input — **fixed**
- `sr-6` (spec) — Repeated identical --drop-level in one call is unspecified — **fixed**
- `sr-7` (spec) — Spec does not state the same-PR move of the lifecycle-acceptance-drop-level matrix row — **fixed**
- `p1-r1` (plan, phase 1) — drop_levels typed dict[str, list[str]] forces phase 2 to convert Mapping-of-tuples drops — **fixed**
- `p1-r2` (plan, phase 1) — Removing a ref a row carries twice removes every copy, undocumented and untested — **fixed**
- `p1-r3` (plan, phase 1) — No test for dropping from a level the row has no refs in — **fixed**
- `p2-r1` (plan, phase 2) — _check_drops keeps only the last item per id, so the create refusal is decided by position — **fixed**
- `p2-r2` (plan, phase 2) — A drop entry naming no refs passes every check and removes nothing — **fixed**
- `p2-r3` (plan, phase 2) — Refusal tests pinned only docs/acceptance, not HEAD or the tree; the run-id test matched a loose 'run' — **fixed**
- `p3-r1` (plan, phase 3) — Three CLI refusal tests assert only exit 2 and unchanged bytes, which a Typer usage error also satisfies — **fixed**
- `p3-r2` (plan, phase 3) — The drop + add test does not pin the spec's 'one rewrite' — **fixed**

## Out-of-scope findings

- `p1-r4` (plan, phase 1) — No direct test of merge_levels refusing an unknown key — **out-of-scope**
- `p2-r4` (plan, phase 2) — The engine accepts the same ref in the drops and in levels (drop then re-add) — **out-of-scope**
- `p3-r3` (plan, phase 3) — _refuse_unknown_levels' suffix 'a typo would silently drop refs' reads oddly for --drop-level — **out-of-scope**

## Proportionality

```text
proportionality: merge-base 6a7da3568f8c79b44a294f74a9e98ccf4db80155

## Unreferenced new files

none.

## Out-of-plan touches

none.

## Size

578 lines changed (+539 -39; fr artifacts excluded) against an estimate of 410 (1.4×).
```

## Cost

| step | turns | cost |
|---|---:|---:|
| brainstorm | 12 | — |
| spec-review | — | — |
| plan | — | — |
| plan-review | — | — |
| implement | — | — |
| journal-check | — | — |
| deliver | — | — |
| (outside run) | 2 | — |
| **total** | | — |

Sessions: 1 read, 0 unavailable.
