# OpenCode 1.18.35 input observations

Captured live 2026-10-09 in an operator-authorized disposable herdr workspace
(herdr 0.9.0, protocol 22, OpenCode --model openai/gpt-6.1-sol). The workspace
was closed after plain `exit` returned to the original shell. No production
pane was mutated. User/project paths and pane/session ids are redacted.

These are **excerpts/projections of those captures**, not synthetic screens:
blank rows/trailing padding and non-border SGR are removed for readability;
the final border retains its original ANSI, including the dimmed overlay colour.
`placeholder-line.json` retains the original home placeholder's full ANSI from
the SAME idle-ready capture; tests restore that line to the readability projection.
Its muted ghost-text colour distinguishes it from a literal unsent draft.
The final input rows and footer are retained; final-idle also retains the
completed task echo. Metadata/sidebar paths use generic projects/super-fr.
Unknown layouts/themes are unsupported. Blank startup is not ready input.
Draft and Commands overlay still reported done/interactive_ready=true.
The active subagent had working status, a spinner and esc interrupt.

No permission/question dialog or detached child was live-proven; synthetic
negative tests are labelled as such. This is grounding, **not** the operator's
full client-live Ready walk. Source corroboration: OpenCode v1.18.35 commit
53d1eabb61e21162157817bf677da0a4ad3332e3,
packages/tui/src/component/prompt/index.tsx: dialog.stack blurs the prompt,
and submitInner handles exact trimmed exit/quit/:q before model submission.
# Wide session captures (2026-10-10)

`wide-idle.json`, `wide-draft.json` and `wide-palette.json` are **real** Herdr
0.9.0/OpenCode 1.18.35 captures from user-authorized disposable sessions, after a
read-only sleep/HOLD turn. The wide default layout puts sidebar cwd text beside
the focused closing border and uses a `• OpenCode 1.18.35` footer. Runtime path
identifiers were masked at capture with same-width replacements, preserving
columns and every ANSI sequence. The full viewport is losslessly gzip/base64
encoded; the loader checks its decompressed SHA-256. These are captures, not
layouts constructed alongside the parser. Deliberate draft/palette inputs were
refused by the real replacement CLI before being manually cleaned up as fixture
inputs. They do not discharge the complete client-live walk.

# OpenCode 2.1.4 prompt capture (2026-10-24)

`v2-2.1.4-idle.json` is a lossless gzip/base64 viewport captured from the
disposable fixture-C OpenCode 2.1.4 session. The user's home path was masked at
capture with a same-width replacement; the SHA-256 covers the decoded,
redacted bytes. It shows a focused blank prompt with `Build auto`, the selected
model, and the V2 footer (`shift+tab agents`, `ctrl+p commands`, workspace and
branch state). It has no visible dialog or overlay. RC9's previous observer
rejected it because the V2 footer does not contain the legacy `1.18.35` marker.

The fixture is a readiness-observer regression, not proof of the failed
`herdr-agent-state.js` plugin's lifecycle hooks. That plugin warning is
separate; the actor and action that dismissed its earlier overlay on fixture C
are unknown. Overlay refusal tests are synthetic and explicitly exercise
permission, search-provider setup, and plugin-error indicators. This capture
does not discharge the operator-owned client-live/managed-runner walk.
