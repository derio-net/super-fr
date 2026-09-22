# Plan: harness-specific arguments are vocabulary too (#532 repair)

Spec: `docs/superpowers/specs/2026-09-22-harness-argument-neutrality-design.md`.

Five agentic phases. Phase 1 is a trivial walking skeleton (an empty closed vocabulary, CI
green). Phase 2 teaches `scan_prose` arguments, headings and removes `extra_tools`. Phase 3
widens the tripwire to rules and scopes the prose it demands in the same phase, so no phase
hands back a red suite. Phase 4 tightens the #420 check. Phase 5 fixes stale docs and releases.

The OpenCode smoke run is the spec's post-merge Test Plan, not a plan phase: it needs the
released version installed on the OpenCode node.
