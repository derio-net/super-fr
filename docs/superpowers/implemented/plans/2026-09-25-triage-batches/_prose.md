# fr triage batches — implementation plan

**Spec:** `docs/superpowers/specs/2026-09-25-triage-batches-design.md` (approved 2026-09-25).
**Journal:** decisions d1–d8 and both spec reviews live in
`docs/superpowers/journals/specs/2026-09-25-triage-batches.md`. Read it before
phase 2: several design choices (the stage gate, `--repair`, the adapter
boundary) exist because a reviewer found the obvious version broken.

## Shape: three layers, serial

The operator chose the fewest phases that still keep an honest walking
skeleton (2026-09-25, option B over a two-phase plan with a skeleton override
and a four-phase declared-parallel plan).

1. **Skeleton.** The one genuinely new delivery surface is a new workspace
   package, `fr-herdr`, which must reach the uv workspace, mypy and CI. Phase 1
   proves that with a stub runner and the smallest real batch verb (`list`),
   so a wiring break shows up in minutes, not halfway through the engine.
2. **Engine.** Everything the verbs stand on, bottom-up: the forge adapter's
   new operations (§3.J), `facts.json` schema 3 and the open-PR join (§3.F
   Facts), the batch model and derived stages (§3.A), the local verbs and the
   board (§3.B, §3.E, §3.G), and the run-unit runner contract with the real
   `HerdrRunner` (§3.C). Nothing here dispatches or merges.
3. **Verbs.** `batch dispatch` and `batch merge`, then the skill, the mirrors,
   the docs and the minor version bump.
4. **Live walk (manual).** Two real batches with a shared file, dispatched
   through herdr and merged. A phase executor cannot drive a live herdr session
   or real PRs, so this is the operator's.

## Things an executor will trip on

- **Always `uv run fr`, never bare `fr`**, inside the workspace (AGENTS.md).
- **Phase 1's new `pyproject.toml` must carry the workspace's current
  version**, or `bump-version.py --check` goes red. The minor bump happens once,
  in phase 3.
- **The import-direction tripwire** (`tests/unit/test_import_direction.py`)
  allows exactly one `fr` → `fr_dispatch` import today. Phase 3 generalises it
  to a tuple; phase 2's runner work lives entirely in `fr-dispatch` and
  `fr-herdr` and needs no exception.
- **No batch module calls `gh`/`glab`/`tea` directly or imports triage's
  `Forge`** (§3.J). Phase 2 adds the adapter methods; phases 2 and 3 use them.
- **Skill edits need BOTH mirror syncs** (`sync-opencode.py` and
  `sync-hermes.py`); three past sessions ran only one.
- **Merge's integration test fakes the forge and uses real git** against a
  local bare origin. A bare repo cannot answer `gh pr merge` or required checks.
- **Acceptance rows move with `fr acceptance set-status`**, never by hand, and
  only when the test that proves them is in CI.

## Out of scope (spec §6)

Run-unit support in `vk`/`cncd`, non-GitHub merge, moving `collect` onto the
adapter (gh#611), auto-merge, cross-repo batches.
