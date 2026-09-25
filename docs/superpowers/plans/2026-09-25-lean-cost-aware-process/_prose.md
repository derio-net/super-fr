# A lean, cost-aware fr pipeline

Implements `docs/superpowers/specs/2026-09-25-lean-cost-aware-process-design.md`.

Four phases, per operator decision d9. Fewer, larger phases keep more decision
context in each executor. Phase 1 opens with the walking skeleton: a real
transcript fixture normalized end to end.

| Phase | Section | Depends on | Needs gh#610 |
|---|---|---|---|
| 1 | A: readers, classifier, `fr usage collect/report`, `fr-audit` | none | no |
| 2 | B: `usage` kind, capture, run 6→7, backfill, host-side `fr run`, parity modes | 1 | **yes** (P2.T1 checks) |
| 3 | C: step records, `resolve --record`, verbs as records, rendered PR body, prose, 4.x minor | 2 | yes |
| 4 | Manual: live `/fr-goal` on Claude Code (devcontainer) and OpenCode | 3 | n/a |

## Invariants every phase keeps

- **Unavailable is never zero.** Any unreadable source is recorded as
  `unavailable: <reason>` and renders `—`. Capture and readers never raise into
  the step that triggered them.
- **Dollars come from the harness.** Only the fixed ratios (1, 1.25, 2, 0.1, 5)
  split a harness figure; no list price appears anywhere in code or tests.
- **Privacy by allowlist.** Usage files serialize an explicit field list. No
  hostname, base URL, path, prompt or message content, ever. Fixtures are
  redacted at capture time (`.claude/rules/third-party-privacy.md`), with
  provenance and sha256 in the fixture's `NOTE.md`.
- **Artifact rule.** `usage` v1 and `record` v1 are new kinds; `run` goes 6→7
  with a frozen `RunStateV6`, every hop naming a frozen reader, and the chain
  test `[2…7]`. `current_version` moves only in `fr.artifacts.registry`. Phase 2
  runs `fr migrate artifacts --yes` and commits the result.
- **History is not edited.** Nothing under `docs/superpowers/implemented/`
  changes except new files in `implemented/usage/` (backfill, archive moves).
- **Where `fr run` executes.** From phase 2 on, `fr run` / `fr usage` run on the
  harness host. This workspace is host-worktree mode, so nothing changes for
  this run's own commands.
- **Both manifests stay identical** (`plugins/super-fr/workflows/fr-goal.yaml`,
  `packages/fr/src/fr/workflows/fr-goal.yaml`).
- **After any skill or agent edit, run BOTH** `scripts/sync-opencode.py` and
  `scripts/sync-hermes.py`.
- **Tests assert outcomes, not cadence**: a clean tree for fr's paths after the
  command returns, one stdout line on success, and nothing changed on refusal.
- **Always `uv run fr …`** inside this worktree (AGENTS.md).

## Deviation from the spec's Test Plan, recorded

Test Plan item 3 (golden audit) is a **local check, skipped in CI**: the nine
sessions' transcripts can't be committed (size and privacy). Its CI-side
coverage is the per-reader fixtures (item 1) and the classifier table (item 2).
The `audit-pages-regenerated` row is flipped on the unit and integration tests
of `fr usage report`, and the golden result is recorded in phase 1's record.
