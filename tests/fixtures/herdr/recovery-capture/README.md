# Captured recovery observations

Read-only host herdr captures taken 2026-10-14 by the parent OpenCode session
while implementing closed-session recovery. No panes were created/closed, no
clients launched, and no process input was sent to obtain these observations.

- `pane-list.json`: `herdr pane list` without workspace filtering; all 16 entries
  preserved, projected to pane/tab/workspace/agent/status fields. Personal cwd,
  titles, terminal ids, scroll/revision details and harness session ids omitted.
- `tab-list.json`: `herdr tab list` without workspace filtering; all 14 tabs and
  exact pane counts preserved. Human labels replaced with stable fixture labels.
- `tab-get-shell.json`: `herdr tab get w1T:t1`; label masked. This response does
  not expose pane ids. Pane discovery is the join of pane-list tab_id and tab-list
  tab_id, not an invented field on tab-get.
- `shell-process-info.json`: `herdr pane process-info --pane w1T:p1`; cwd and pid
  masked, preserving the process-group/shell-pid equality and exact key/argv shape.
  The driver had already stopped; the actual observation was a lone foreground zsh.

Pane/tab/workspace ids preserve observed joins. These files are captured projections,
not proof of a closed-session recovery walk or a complete runtime capture of every
optional field. Tests may derive hypothetical failure/state variants from this
documented wire shape, but must not claim those variants were captured live.
The host control CLI exists; it is intentionally absent from the test container.
Use fakes/captured fixtures inside isolation, not real herdr operations in tests.
