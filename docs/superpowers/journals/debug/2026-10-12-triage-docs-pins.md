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

<!-- fr:journal kind=finding scope=debug id=fix-closed-pins created=2026-10-11T23:39:23+00:00 state=fixed -->
### fix-closed-pins · finding [fixed] · Closed pins drop off visibly; history fragments build even if the diagram fails

dac3f687: pipeline.py filters pins to open issues, names the dropped ones under the diagram and on stderr; build.py runs pipeline.py guarded, writes history/ regardless, exits non-zero on a diagram failure. Pinned by tests/unit/test_triage_docs_authored_src.py (both red before the fix, green after). Live: the scratch repro with the scope's real facts.json and real gh now exits 0, drops 30 pins, writes all three history fragments. Not done here: re-judging which of today's open issues pin to which step (issue item 1, an operator judgement).

<!-- fr:journal kind=review scope=debug id=14133a5cd277 created=2026-10-11T23:39:31+00:00 -->
### 14133a5cd277 · review · Self-review of the fix diff: no findings

Reviewed by the debugging session itself, not an independent reviewer (docs-tree scripts + one test file). Checked: defect count and placed set are computed after filtering; an all-empty pin column still renders 'no open pins'; the 'other' sentence no longer claims unpinned issues act on no step, since new issues are unpinned until re-judged; committed fragments were deliberately not regenerated (the state export flow owns them). No change fragment: docs/ and tests/ only.
