# Journal: 2026-10-12-triage-docs-pins

<!-- fr:journal kind=repro scope=debug id=d67997855a39 created=2026-10-11T23:36:57+00:00 -->
### d67997855a39 · repro · build.py aborts: 30 of 39 pinned issues are now closed

Copied docs/triage/derio-net--super-fr plus the live scope's facts.json into a scratch state dir and ran `python3 authored-src/build.py` from /. pipeline.py:63 raises `AssertionError: pinned issues no longer open: [458, 528, ... 1015]` (30 numbers). build.py runs pipeline.py first via runpy, so none of the three history/ fragments are written either.

<!-- fr:journal kind=root-cause scope=debug id=9aa21bf93b8b created=2026-10-11T23:37:00+00:00 -->
### 9aa21bf93b8b · root-cause · The pin table is a dated hand snapshot, and closing a pinned issue is a fatal error for the whole build

pipeline.py's DRIVER/PIPE/STRIPS tables pin the issues open on 2026-10-05. Issues closing is the normal lifecycle, yet pipeline.py treats any closed pin as a hard assert (#969's guard, meant to stop a pin silently pointing at a closed issue), and build.py calls pipeline.py unguarded before writing the independent history fragments. So the table goes stale by design, and staleness blocks every authored fragment. Refreshing the table by hand only resets the clock.

<!-- fr:journal kind=hypothesis scope=debug id=714ab0c4c387 created=2026-10-11T23:37:04+00:00 -->
### 714ab0c4c387 · hypothesis · Fix: drop closed pins visibly instead of aborting; build history even if the diagram fails

pipeline.py keeps pins whose issue is open, and lists the dropped (closed or no longer collected) ones in the fragment and on stderr, so the guard's intent (no pin pointing at a closed issue) holds without a fatal build. build.py runs pipeline.py in a try, writes the history fragments regardless, and exits non-zero naming the failure. Re-pinning today's open issues stays an operator judgement (issue item 1), not part of this fix.
