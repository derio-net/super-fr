# Dispatch-walk toy plan

Fixture for the post-4.0.0 live bridge walk (spec
`docs/superpowers/specs/2026-09-05-dispatch-walk-toy-design.md`). One agentic
phase, one step, no code change: the runner's agent appends a line to the
spec's walk log. Observed outcome that matters lives in the bridge log — one
card on the first tick, none on the second — not in the diff.
