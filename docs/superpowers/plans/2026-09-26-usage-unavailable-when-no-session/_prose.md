# Plan — explicit unavailable capture when no session is found

Single phase, debugging-first (spec `2026-09-26-usage-unavailable-when-no-session-design.md`,
fixes #636's cheapest cut). Red tests reproduce `sessions: []` on a no-session capture and pin the
merge/placeholder rules; the fix is a small `_merge` change plus a placeholder built after the merge
in `usage/capture.py`, and one new closed-vocabulary reason. No schema change, no migration;
`run/telemetry.py` is deliberately untouched.
