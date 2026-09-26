# Journal: 2026-09-26-plan-table-header

<!-- fr:journal kind=discovery scope=plan id=p1-separator-unused created=2026-09-26T07:40:08 phase=1 -->
### p1-separator-unused · discovery · _CANONICAL_HEADER_SEPARATOR has no consumer yet (phase 1)

Added and derived from the header line per the plan, but nothing reads it until the phase that creates the section (_ensure_section_text) lands.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-26T07:40:08 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

the header literal now lives once (_CANONICAL_HEADER_LINE) with cells and separator derived from it; grep 'Depends on' in plan_ops.py shows a single literal, nothing further to clean
