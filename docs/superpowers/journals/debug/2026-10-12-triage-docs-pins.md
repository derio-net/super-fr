# Journal: 2026-10-12-triage-docs-pins

<!-- fr:journal kind=repro scope=debug id=d67997855a39 created=2026-10-11T23:36:57+00:00 -->
### d67997855a39 · repro · build.py aborts: 30 of 39 pinned issues are now closed

Copied docs/triage/derio-net--super-fr plus the live scope's facts.json into a scratch state dir and ran `python3 authored-src/build.py` from /. pipeline.py:63 raises `AssertionError: pinned issues no longer open: [458, 528, ... 1015]` (30 numbers). build.py runs pipeline.py first via runpy, so none of the three history/ fragments are written either.
