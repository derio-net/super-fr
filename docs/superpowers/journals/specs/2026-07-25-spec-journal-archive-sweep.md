# Journal: 2026-07-25-spec-journal-archive-sweep

<!-- fr:journal kind=decision scope=spec id=d1 created=2026-07-25T05:43:28 -->
### d1 · decision · Fix root cause: -design suffix slug mismatch

spec_archive_sweep passed spec_path.stem (<slug>-design) but the spec journal is keyed by the bare slug. Add spec_journal_slug() to strip -design in one place.

<!-- fr:journal kind=decision scope=spec id=d2 created=2026-07-25T05:43:28 -->
### d2 · decision · Read resolver falls back to archived path

render/check gain resolve_journal_read_path (active else archived); closes the same gap for plan reads. add keeps writing the active path.

<!-- fr:journal kind=decision scope=spec id=d3 created=2026-07-25T05:43:28 -->
### d3 · decision · Backfill 3 stragglers in this PR, no orphan scanner

Their specs already left specs/, so the sweep can't revisit them. git mv the three; no standalone repair scanner (matches plan-journal posture).
