# Run cursors — captured, never constructed

Every file under `v1/` … `v6/` is a run cursor `fr` really wrote while driving a
real `/fr-goal` run in this repository, copied **byte for byte** with
`git show <rev>:<path> > <fixture>`. None was typed, trimmed, reformatted or
"tidied". They exist so the `run` 4 → 5 rewrite (spec
`2026-09-20-unit-record-unification-design.md` §4.F), its frozen legacy reader
and the whole chain `[2, 3, 4, 5]` are tested against files fr produced rather
than against a guess written alongside the parser.

**Do not edit these files, and do not "fix" them.** A captured fixture that has
been refactored is a constructed one. If a fixture stops being useful, capture
another and add a row; if the shape a test needs does not exist in any real
cursor, that is a finding about the test, not a reason to author YAML here.
`tests/unit/test_run_cursor_fixtures.py` pins each file's SHA-256 to the table
below, so an edit fails CI and has to be argued for in a diff to this file.

## What "version" means here

`vN/` is the `schema_version` the file DECLARES, which is what a migration
dispatches on. `v1/` files carry no stamp at all — the stamp did not exist.
`run` 2 → 3 (gh#514 telemetry) and 3 → 4 (gh#508 dispatch holder) are both
**stamp-only** migrations, so a cursor that was migrated up to a version is
byte-identical in body to what it was before; where a fixture reached its
version that way rather than being written natively, the table says so. That is
a property of the real population, not a defect of the capture — most live v4
cursors in any repository will be exactly that.

Archived cursors (`docs/superpowers/implemented/runs/`) are frozen: no locator
reaches them and no migration rewrites them, which is why real v1–v3 files still
exist to capture.

## Provenance

Captured 2026-09-20 in phase 1 of plan `2026-09-20-unit-record-unification`.
`rev` is what the bytes were read from; `last touched` is the last commit that
changed the source file; `blob` is the git blob id (so `git cat-file -p <blob>`
reproduces the fixture exactly, from any clone that has the commit).

| fixture | source path | rev | last touched | blob | sha256 | carries |
|---|---|---|---|---|---|---|
| `v1/2026-09-09-feat-issue-464.yaml` | `docs/superpowers/implemented/runs/2026-09-09-feat-issue-464.yaml` | `da2af6e74867` | `00984690b028` | `dd5f1e02726d` | `f61dc0bdcaa86bbd8b343880e8d9a1645e1472d307fc70e8e2d35452b60a179a` | smallest real cursor: no stamp, one grouped step, no accounting |
| `v1/2026-09-14-feat-statusline-session-branch.yaml` | `docs/superpowers/implemented/runs/2026-09-14-feat-statusline-session-branch.yaml` | `da2af6e74867` | `9bb2248a5090` | `bcafc1c4f366` | `fa9962ee1c8b9b75677253fdbe96f5966887a8e3153e5f5816b4b659989b336f` | no stamp; grouped `items`, top-level `accounting`, `emitted.pr` |
| `v2/2026-09-18-feat-harness-parity-matrix.yaml` | `docs/superpowers/implemented/runs/2026-09-18-feat-harness-parity-matrix.yaml` | `da2af6e74867` | `ea0b521b8ce1` | `8dd4264fdd28` | `701708d089c861549f29c17eff7b883d2f6a6e73bd8162d6e8f2df3537aaf4b6` | first stamped shape; finished run, grouped `items` + `accounting` |
| `v2/2026-09-20-journal-require-reviews-v2.yaml` | `docs/superpowers/runs/2026-09-20-journal-require-reviews-v2.yaml` | `9fab01427637` (`origin/feat/journal-require-reviews`, gh#517, before it was folded in and migrated) | `9fab01427637` | `317df0f62c87` | `1d7b17c5f175ac4dc4522a3141d5ae1011f3a0429ff4b8b9f797094aa145235d` | IN-FLIGHT: flat `deliver: running` with NO dispatch record (the u1 fallback shape); a `cli` step with `exit`/`stdout` |
| `v3/2026-09-20-feat-bounded-executor-handoff.yaml` | `docs/superpowers/implemented/runs/2026-09-20-feat-bounded-executor-handoff.yaml` | `da2af6e74867` | `8aa6d1c1e51c` | `1c543599225f` | `279e7448246d5bfd05e500a682f622304d059fcd1357c3ea003777adc78e2f12` | gh#514 telemetry era: `accounting` with measured figures |
| `v3/2026-09-20-fix-434-phases-file-tier.yaml` | `docs/superpowers/implemented/runs/2026-09-20-fix-434-phases-file-tier.yaml` | `da2af6e74867` | `33e31dd09724` | `bbca669fbd16` | `df4e82dd9bfb94aec276c5622880c6fa6d8cba4a1e55948f7c5178aea1cde6f6` | second v3: `accounting` with sizes only, NO measured token figures (the unmeasured case) |
| `v4/2026-09-20-feat-phase-holder-identity.yaml` | `docs/superpowers/runs/2026-09-20-feat-phase-holder-identity.yaml` | `da2af6e74867` | `a880434b6ec5` | `4a8417423c7c` | `ccbcbc6a5671812b04e5b54fe232f570e1edf15738e50ad53d034fc7138f2da1` | all three maps at once: `items`, `dispatch` (several attempts per unit, claimed and abandoned), `accounting` |
| `v4/2026-09-20-fix-fr-run-cursor-cluster.yaml` | `docs/superpowers/runs/2026-09-20-fix-fr-run-cursor-cluster.yaml` | `da2af6e74867` | `bd96bebc0263` | `f6cd3dbd0b64` | `f87a94d7f098d70a973721bb42875691d6a7df68af67a9956a21367f66aad0ec` | gh#496's `phase/<n>: manual` marker; no `dispatch` (stamp-migrated 2 -> 4, body untouched) |
| `v4/2026-09-20-unit-record-unification-r2.yaml` | `docs/superpowers/runs/2026-09-20-unit-record-unification-r2.yaml` | `b7fd771b7141` | `b7fd771b7141` | `a8d7daf57a37` | `2ae23637b2a1ebb91ef280a43ec0234c5777d398c048141ad476b21ef3f6dabd` | IN-FLIGHT WITH A HELD UNIT: `phase/3/implement-phase` carries a claimed, OPEN attempt (`returned` absent) beside closed ones, a real measurement on `phase/2/implement-phase`, and two attempts with no `agent_type` (orchestrator-run reviews). Captured in phase 3, moments before the 4 -> 5 migration rewrote the source |
| `v5/2026-09-23-fix-457-uninstall-rules.yaml` | `docs/superpowers/implemented/runs/2026-09-23-fix-457-uninstall-rules.yaml` | `7dbdc35b73a5` | `f6a26033add4` | `9c7feb6c087b` | `3aa0949f6150a38a358ce8acc8169a6bdbe14c1bacd96e33b7a878aad5c7a00b` | natively-written v5 (`units`, flat `step/*` attempts on an OpenCode run, a `cli` step with `exit`/`stdout`). Captured in phase 1 of plan `2026-09-24-fr-goal-scope-proportion-cost` as the input of the stamp-only 5 -> 6 hop |
| `v6/2026-09-24-feat-597-593.yaml` | `docs/superpowers/runs/2026-09-24-feat-597-593.yaml` | `6d8200df` | `6d8200df` | `5a13a47e4d56` | `d9ce0a0953caa81bbd39831ad1203afbbd26f13b63c6e9ee4660c7991dac7e2b` | natively-written v6: `main_session` on three steps, `estimate` + `measured` on grouped phase attempts. Captured in phase 2 of plan `2026-09-25-lean-cost-aware-process` as the input of the 6 -> 7 hop, which moves those figures into `usage/` |

## Not captured, and why

- (Resolved in phase 3.) This plan's own cursor — the only one carrying a claimed OPEN
  hold — was untracked when phase 1 ran, so there were no committed bytes to point at.
  Phase 3 committed it (`b7fd771b7141`) and captured it from `git show` as
  `v4/2026-09-20-unit-record-unification-r2.yaml`, immediately before migrating the
  source file to version 5. The `-r2` run superseded the original run id after a
  manifest-drift recovery (journal `x-p1-lost-dispatch-history`).
- A natively-written v2 → v3 cursor pair for the same run. None exists: each
  run lived at one version.
