<!-- fr:journal-schema=3 -->
# Journal: 2026-10-30-opencode-readiness-refusal-evidence

<!-- fr:journal kind=repro scope=debug id=e2468d67c085 created=2026-10-30T18:35:19+00:00 -->
### e2468d67c085 · repro · Offline RED: refusal predicate and conservative projection absent

Fresh fetched origin/main be4f159e9b1f; host isolation profile host. RC14 venv chosen with genuine RC7 harness pin unchanged. GC dry-run only proposed completed clean startup workspace for reaping; all others skipped/warned. Current source collapses text-dialog and braille Task branches into unknown-dialog-or-background. Actual RC14 triggering predicate remains unknown; no root-cause claim. RED command through isolation exec: python -m unittest tests.unit.test_opencode_refusal_evidence -q. Ran 2 tests, 11 AttributeError errors because refusal_evidence is absent. Tests load only candidate opencode.py explicitly using importlib; runtime venv has no pytest. No installation, PYTHONPATH override or runtime mutation. Candidate diagnostic method is local-only and not live-authorized.
