# Journal: 2026-09-25-writes-dot-dir-prefix-design

<!-- fr:journal kind=decision scope=spec id=d1 created=2026-09-25T00:44:21 -->
### d1 · decision · Segment-wise strip for relative redirect targets

Operator chose the segment-wise strip (drop '.' and leading '..' segments, then trailing-segment match). This keeps the existing ../x.log leniency on purpose.

<!-- fr:journal kind=decision scope=spec id=d2 created=2026-09-25T00:44:21 -->
### d2 · decision · Model tiers left unbound

Operator: inherit the session model, and dispatch untiered agents.

<!-- fr:journal kind=decision scope=spec id=d3 created=2026-09-25T00:44:22 -->
### d3 · decision · No post-merge Test Plan; dogfood at this deliver

This run's deliver names .fr-deliver/tests.log through uv run fr, which is the live proof.
