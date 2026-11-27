```
packages/fr/src/fr/
  yamlio.py                 + StrictLoader: the one duplicate-key detector;
                              duplicate_key hook → ConstructorError (marks kept)
  utc_time.py               + parse_as_utc(value: object): naive → UTC, bad/non-str → None   [new]
  artifacts/structure.py    - _StrictLoader            → yamlio.StrictLoader
  harness/model.py          ~ _StrictLoader(StrictLoader): duplicate_key → HarnessError (same text)
  lenses/model.py           ~ import yamlio.StrictLoader
  isolation/scaffold.py     ~ import yamlio.StrictLoader
  commands/journal_cmd.py   ~ --gate help built from get_args(Gate), byte-identical
  triage/collect.py         ~ _created_since via parse_aware (unknown still yes)
  commands/triage_batch_cmd.py ~ _pr_time body → parse_aware
  usage/compare.py          - _instant                 → parse_as_utc
  usage/backfill.py         ~ inline parse             → parse_as_utc (None still "worth reading")
  debt/engine.py            - _parse                   → parse_as_utc
  run/liveness.py           - _parse_instant           → parse_as_utc
  triage/claims.py          - _created                 → parse_as_utc
  triage/admit.py           ~ claims._created import   → parse_as_utc   (found while building)
tests/unit/
  record_helpers.py         + write_record             ← 11 record modules drop _record_file
                                                         (test_record_lens imports it as write_record_text)
  hermetic_git.py           + apply_hermetic_git, hermetic_git fixture
                                                       ← 6 modules: usefixtures, no setenv copies;
                                                         test_merge_evidence.stub_fetch calls apply_hermetic_git
  test_yamlio_strict.py     + single construct_mapping owner, yamlio import purity, default error
  test_record_helpers.py    + no placement copies, helper bytes/path
  test_hermetic_git.py      + activation, no setenv copies, restoration
  test_journal_gate_help.py + --gate help string from Gate
  test_utc_time.py          + parse_as_utc contract
  test_triage_timestamps.py ~ body scan also guards parse_as_utc
.claude/rules/artifact-versioning.md (+ .opencode mirror), scripts/sync-opencode.py  ~ new owner named
.changes/feat-batch-arch-shared-helpers.yaml  + patch fragment
docs/** (9 pages)                             ~ reviewed stamp only
```
