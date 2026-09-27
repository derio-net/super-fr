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
