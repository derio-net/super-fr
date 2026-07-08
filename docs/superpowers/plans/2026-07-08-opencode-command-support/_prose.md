# opencode-command-support

Adds a third generated OpenCode mirror — `.opencode/commands/<name>.md` —
so the 9 already-mirrored `fr-*` skills also work as real, registered
OpenCode slash commands (`/fr-goal`, `/fr-plan`, ...), not just literal-text
pattern matching against the skill's own description. Follows the exact
canonical-source → generated-mirror → CI-tripwire → installer-delivery
pattern the sibling `opencode-adaptation` plan established for skills and
instructions earlier the same day.

See `docs/superpowers/specs/2026-07-08-opencode-command-support-design.md`
for the full design, decisions, and Test Plan.
