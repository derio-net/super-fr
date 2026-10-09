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
