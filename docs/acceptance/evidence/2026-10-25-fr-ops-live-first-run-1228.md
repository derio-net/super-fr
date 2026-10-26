# Live fr-ops acceptance evidence — original run #1228

Walk date: 2026-10-25 (UTC), based on the retained successful fresh-main status log.
Scope: disposable fixture only; this records evidence for `fr-ops-live-first-run` and the original run's Test Plan step 1. It does not pass original PR #1228's gate.

## Walk result

- Fixture PR [#1](https://github.com/derio-net/super-fr-release-fixtures-20261024/pull/1) merged at `2026-10-24T20:15:43Z`, merge commit `134287446e2301501269ac74a6d1b5dd84157094`. Its current forge state carries `gate:devops-passed`.
- The captured eight-stage fixture transcript records pre-merge `fixture-pre-merge` applied and `DONE (checked)`, the real merge, post-merge readiness, post-merge `fixture-post-merge` applied and `DONE (checked)`, a `ran` Test Plan outcome, fixture gate pass, tester handoff, and housekeeping PR creation. The fixture's ops-profile install pin is published `v6.0.0-rc.7`; the retained stage transcript does not independently establish a host-side `fr --identity` for every stage, so this note does not claim every stage invocation was verified to that binary identity.
- Housekeeping fixture PR [#4](https://github.com/derio-net/super-fr-release-fixtures-20261024/pull/4) merged at `2026-10-24T20:25:37Z`, merge commit `8a15e2daaa9a536bc4f5899acd72eeeddaa31cf7`. Its source head is `250e8f57f0b89da53dcb8d9384120b62bb04975c`. The source-head tree and clean fresh-main checkout tree both equal `a770ac57fca1aa79656ef09cafae59d1be94e386`.
- A captured no-op rerun left all eight stages complete and preserved the gate-state digest, marker inventory, ops-branch PR list, and clean worktree/head. The rerun comparison predates PR #4's merge; the subsequent forge read confirms that same single PR merged.
- On the clean fresh-main checkout at `8a15e2daaa9a536bc4f5899acd72eeeddaa31cf7`, published `fr 6.0.0rc11` from source commit `cc133a53b3ed6dcaa8f6e6d64e2bb8b04c6c53b8` ran `fr ops status --plan docs/superpowers/implemented/plans/2026-10-24-fr-ops-live-1228`. It returned exit 0 and reported both `fixture-pre-merge` and `fixture-post-merge` as `DONE (checked)`. Before/after marker hashes were identical: pre-merge `ba459c67ab5c44adb0ff6fad7b3407dcd957d30d41b03a7930e7020dfc6c4693`; post-merge `a6ca63f65063cbb3bfd30e49d06f96deb3a8204451b46c941e0a6ef3e11d3e11`.

## Evidence types and limits

`fr ops status` is live check evidence: it ran the two checks against the unchanged fixture markers. Archived `op-trust-2` and other journal entries are separate recorded audit evidence; this note does not claim `fr ops status` reads or folds the journal.

The fixture identity `fr-ops-1228-fixture-only` is literal local test data, not a credential and not evidence of production credentials or service authorization. The fixture acceptance row `fixture-devops-live` is outside the requested scope and remains unchanged. Original PR #1228 remains labeled `gate:devops`; its no-`--yes` RC11 preview was held by its recorded owed Test Plan step 1, without probes or writes. No original gate pass is claimed.

The fixture run's archived usage identifies harness `opencode` and model `gpt-6-luna-fast`; dollars are unavailable (`usd: null`, `usd_source: none`). This model attribution is taken from the retained run usage record, not inferred from the status command's output. Adoption-inferred earlier run stages are not review evidence. The evidence packet and its manifests remain in the coordinator's private audit bundle; hashes in the adjacent manifest identify those retained materials without copying private grants, source caches, raw host paths, or secrets into this repository.

## Audit packet

The adjacent `2026-10-25-fr-ops-live-first-run-1228.manifest.json` records SHA-256 hashes for this note and the retained private packet anchors. The private coordinator packet's 79-file manifest and the three-member eight-stage capture were independently verified; its current-forge GETs record PRs #1/#4 merged and original PR #1228 still held. Full local artifact paths are intentionally omitted here.
