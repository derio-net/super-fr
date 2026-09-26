# herdr CLI fixtures

- `tab-list.json` — captured live 2026-09-25 from `herdr tab list --workspace w2`
  (herdr's JSON envelope and tab objects as printed); the operator's tab labels
  are replaced with invented ones, the shape is unchanged.
- `tab-create.json` — NOT a live capture: creating a tab would have opened one
  in the operator's session. It is assembled from herdr's own documentation
  (`herdr --skill`: "`tab create` returns `.result.tab` and `.result.root_pane`")
  with a `tab` object shaped as captured by `herdr tab get` and a `root_pane`
  object shaped as captured by `herdr pane list`. `fr_herdr` reads only
  `.result.root_pane.pane_id` from it. Replace it with a real capture when one is
  taken (plan phase 4's live walk).
