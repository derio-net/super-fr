# Accepted live labels and downgrade-refusal evidence: #1204

Observed 2026-10-30 under OpenCode, configured model `openai/gpt-6.1-sol`.
The operator accepted both observations and authorized this separate evidence
PR. Model/backend identity was not independently attested. References:
[#1204](https://github.com/derio-net/super-fr/issues/1204) and
[#1195](https://github.com/derio-net/super-fr/pull/1195).

## Fixture and runtime identity

- Actual [draft rehearsal PR #2](https://github.com/derio-net/super-fr-release-rehearsal-20261026/pull/2),
  branch `fixture/labels-1204-isolated`, run `2026-10-30-labels-walk-1204`.
- PR head: `c1bdf0b01a65422f7a83ffb0d0ac4bcb65cd920e`.
- Rehearsal main/base: `1325f612635dcbd17c9ccfdd25be721f9be00038`.
- Exact PR diff: 23 files, comprising 14 fixture documents/metadata files and
  nine existing journal schema stamps changed from 2 to 3 by the supported
  migrator. Every migrated journal body is byte-identical; no existing entry
  was removed. No source, workflow, version or security-setting change.
- All 549 pre-existing rehearsal acceptance rows were preserved. The two
  fixture rows remain `walk-owed`; manual phase steps remain unticked and the
  fixture run remains `deliver/running` pending separate bookkeeping.
- Installed runtime: `fr 6.0.0rc11`, product source commit
  `cc133a53b3ed6dcaa8f6e6d64e2bb8b04c6c53b8`; all 336 package files were verified.
  The original RC7 harness identity pin was retained. RC11 was explicitly
  activated through its venv; no identity or migration bypass was used.
- Evidence-PR base: `3b32f792ea2599280c2c56e9de4ff38f033d9372`.
  All 336 runtime files also match this base, including the tested label-sync
  and verification-set code. The synthetic rehearsal tree itself is **not**
  product/release-source-equivalence evidence.

Genuine independent spec review was recorded after the active review unit
opened, followed by a focused acceptance-link/reason review. The replay
preserved all ten non-acceptance fixture content hashes. Actual RC11 plan
self-review passed; the actual exit was `candidate` plus `live`, held by
`tester` (the two live rows contribute that additional verification kind).

## Real label transition

At 04:53:23 UTC the installed, unmodified shipped callable
`fr.verification.labels.sync_exit_labels(repo_root, actual_loaded_run_state,
actual_PR_URL)` ran against the PR above. This is the function called by
delivery, invoked directly with the real forge client and real loaded run.
There was no mock, manual label addition, no-op `verification set`, artificial
gate toggle or claim that CLI delivery had completed. Forge I/O ran on the
host; local CLI checks used the supported isolation exec bridge.

| Observation | Value |
| --- | --- |
| PR labels before | `[]` |
| Shipped result | `synced: true`, `unknown: false`, no warning |
| Added | `gate:tester`, `verification:candidate`, `verification:live` |
| Removed | `[]` |
| GitHub labels after | `gate:tester`, `verification:candidate`, `verification:live` |

This proves initial automatic synchronization to a real PR, not successful
execution of every delivery gate or every possible later spec change.

## One post-review negative attempt

At 04:54:03 UTC the activated RC11 CLI, through isolation exec, ran exactly once:

```sh
fr verification set --run 2026-10-30-labels-walk-1204 --gate none \
  --reason "1204: verify post-review downgrade refusal"
```

No `--answered-by operator` was passed. Actual exit: **2**, with the specific
diagnostic (not a metadata, migration or forge-read failure):

```text
refused: spec-review is done and this makes the exit wait less (the run: the `tester` gate is now `none`): only the operator may lower it — ask them, then pass `--answered-by operator` — nothing changed
```

Before/after comparisons confirmed identical HEAD, every tracked file's bytes
(including spec, journal and run), raw Git index bytes, index entries, clean
working-tree status, PR identity and PR labels. The shipped implementation
temporarily rewrites the spec to compute the proposed exit, then restores its
contents on refusal before journaling, committing or label synchronization.
No agent repair, restoration or second attempt was performed.

## Evidence retention and remaining obligations

Raw command invocations, outputs, snapshots and index bytes remain in the
private evidence store. The coordinator and recording agent independently
verified all 96 entries in its SHA-256 manifest. Manifest SHA-256:
`18f0de1d205bbcf012d5c3cb0c6cda74af524632d7322459f28d134106eb1c85`.
This digest identifies retained private evidence; it does not claim that the
raw bundle is publicly downloadable. Local paths and session identifiers are
omitted from this public summary.

This record discharges only Test Plan step 1's accepted observations. The
`exit-gates-pr-labels` row moves to `walked`; `exit-gates-set-downgrade` keeps
its existing `ci` status. Steps 2–4 (#1205, #1206, #1207), #1217's recovery
walks and the overall #1195 gate remain owed/held. This is not full-suite,
candidate-install, installer/final-release, driver-routing, collected-closeout
or recovery proof.

Rehearsal main, tags and checked Dependabot PR #1 fields were unchanged;
Actions stayed disabled and the nine static workflows stayed disabled.
PR #2 stays draft with `gate:tester`, not a passed-gate label. This evidence
PR is also draft: neither PR is authorized to merge, no release is authorized,
and #1204 stays open until this record is merged under separate approval.

Recording caveat: the shipped `fr journal resolve` appended the requested
resolution but also posted its discharge note and automatically closed #1204.
That premature side effect was immediately corrected by reopening #1204;
the issue timeline is retained. No second resolve was run. This does not grant
permission to close the issue before the evidence PR merges.
