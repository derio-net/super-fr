# Journal: 2026-09-27-tests-var-binding

<!-- fr:journal kind=repro scope=debug id=9c63095f91e5 created=2026-09-27T09:31:03+00:00 -->
### 9c63095f91e5 · repro · deliver tests= gate binds $L from assignments the shell never makes at top level

Probed `fr.run.telemetry._writes(cmd, Path("/w/t.log"))` on origin/main (baff515e). Each of these returns True although `$L` is unset (or holds another value) where `pytest > $L` runs:
- subshell: `(cd x; L=/w/t.log;); pytest > $L`, and the newline / `&&` forms
- command substitution: `x=$(cd y; L=/w/t.log;); pytest > $L`
- backslash-newline continuation: `echo \<NL>L=/w/t.log; pytest > $L` (L=… is an argument of echo)
- comment: `true # note; L=/w/t.log<NL>pytest > $L`
- backgrounded: `L=/w/t.log & pytest > $L` (the `&` list runs in a subshell)
- pipeline member: `L=/w/t.log | cat; pytest > $L`
Already fail closed today: `echo L=…` on one line, `(L=…)` with no inner separator, prefix assignments, `if …; then L=…`.

<!-- fr:journal kind=hypothesis scope=debug id=1c20d9f3fa1f created=2026-09-27T09:31:13+00:00 -->
### 1c20d9f3fa1f · hypothesis · Single cause: _ASSIGNMENT judges command position by its adjacent separators only

The regex accepts a NAME=value when it is preceded by start/`;`/newline/`&&`/`||` and followed by a separator or the end. It has no notion of nesting (`( )`, `$( )`, backticks, `{ }` and compound commands), of comments, of line continuation, or of the lone `&` / `|` that runs the assignment in a subshell. Every false binding above is one of those. Verdict: confirmed by the probe table; one cause, not several.

<!-- fr:journal kind=root-cause scope=debug id=caa6a2d4ef42 created=2026-09-27T09:31:18+00:00 -->
### caa6a2d4ef42 · root-cause · _assignments masks only quotes and here-docs, so any separator-adjacent NAME=value binds regardless of shell structure

`packages/fr/src/fr/run/telemetry.py` `_ASSIGNMENT` + `_assignments`: masking covered quotes and here-doc bodies (review F3) but not comments or continuations, and nothing tracked nesting depth or the terminator after the assignment. Fix direction (the issue's own): bind only an assignment at nesting depth 0, terminated by `;`, newline, `&&`, `||` or the end, on a mask that also blanks comments and joins continuations; fail closed on everything else.

<!-- fr:journal kind=finding scope=debug id=ce59d41b60a2 created=2026-09-27T09:40:18+00:00 state=fixed -->
### ce59d41b60a2 · finding [fixed] · Assignments bind only at top level (depth 0, ended by ; NL && || or end)

Source: `packages/fr/src/fr/run/telemetry.py` — new `_code` mask (quotes/here-doc bodies filled with `_`, comments blanked, `\<NL>` joined), `_NESTING` + `_top_level` depth scan over `( )`, backticks, `{ }`, `if/fi`, `case/esac`, `do/done`; `_ASSIGNMENT` terminator no longer accepts a lone `&` or `|`. Pinned red-first by `test_only_a_top_level_assignment_binds_a_variable` (12 shapes, `_writes` and `_names`) and `test_a_top_level_assignment_still_binds` (5 shapes). Deliberate tightening: an assignment inside a `{ …; }` group or an unpiped loop body is in the current shell but now fails closed too — the depth scan cannot see whether the group is later piped or backgrounded. Side effect: a trailing comment (`L=x # c`) now binds, as it does in the shell. Full suite 6571 passed.

<!-- fr:journal kind=finding scope=debug id=review-case-paren created=2026-09-27T10:16:51+00:00 state=fixed review_scope=in -->
### review-case-paren · finding [fixed] (reviewer: in scope) · Review: a depth COUNT lets a stray closer cancel a real grouping

Independent review (separate context) traced `case $x in a) true;; esac<NL>(cd /x; L=/x/t.log;); pytest > $L`: the case arm `)` drove depth to -1 so the later `(` read as 0, binding a subshell assignment. Extending the trace: `(echo done; L=…;)` and `do echo done; L=…; done | cat` do the same through an argument keyword. Fixed with a typed stack in `_top_level` (closer must meet its own opener, mismatch → fail closed; `)` directly under `case` ends a pattern) and reserved words counted only in command position. 4 new red-first negatives + 2 positives; full suite 6577 passed.
