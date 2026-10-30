<!-- fr:journal-schema=3 -->
# Journal: 2026-10-30-opencode-readiness-refusal-evidence

<!-- fr:journal kind=repro scope=debug id=e2468d67c085 created=2026-10-30T18:35:19+00:00 -->
### e2468d67c085 · repro · Offline RED: refusal predicate and conservative projection absent

Fresh fetched origin/main be4f159e9b1f; host isolation profile host. RC14 venv chosen with genuine RC7 harness pin unchanged. GC dry-run only proposed completed clean startup workspace for reaping; all others skipped/warned. Current source collapses text-dialog and braille Task branches into unknown-dialog-or-background. Actual RC14 triggering predicate remains unknown; no root-cause claim. RED command through isolation exec: python -m unittest tests.unit.test_opencode_refusal_evidence -q. Ran 2 tests, 11 AttributeError errors because refusal_evidence is absent. Tests load only candidate opencode.py explicitly using importlib; runtime venv has no pytest. No installation, PYTHONPATH override or runtime mutation. Candidate diagnostic method is local-only and not live-authorized.

<!-- fr:journal kind=hypothesis scope=debug id=d0dc29ce9a4d created=2026-10-30T18:35:59+00:00 -->
### d0dc29ce9a4d · hypothesis · First projection GREEN; capture integration remains unimplemented

Same isolation exec unittest command now passes 2 tests including 10 category subcases. Intermediate run exposed an invalid focused-border fixture (colour applied before spaces rather than directly before glyph); corrected fixture to existing parser contract, not parser behavior. Shared named-group regex retains original refusal alternatives and order. Pure projection masks every character except space and explicit border glyphs, max 64 rows x160 character offsets; strips supported CSI and masks all remaining controls. No writer or wait_ready hook exists yet, no safety/completion claim for capture. Next tests must cover braille branch, draft/metadata, same observation, native cleanup, unsafe paths, exclusive bounded writer and finite deadline. Independent review not performed.
