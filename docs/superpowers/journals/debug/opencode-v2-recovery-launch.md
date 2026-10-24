<!-- fr:journal-schema=3 -->
# Journal: opencode-v2-recovery-launch

<!-- fr:journal kind=repro scope=debug id=root-model-flag-rejected created=2026-10-24T11:58:46+00:00 -->
### root-model-flag-rejected · repro · OpenCode 2.1.4 rejects the managed recovery launch flags

Host OpenCode v2.1.4 reproduces the recovery-launch failure: `opencode --model openai/gpt-6.1-sol --auto --fr-probe-unsupported-option` exits 1 with `Unrecognized flag: --model in command opencode`. Its `mini --help` exposes --model but not --auto; `mini --model ... --auto` rejects --auto. Pinned fr-herdr launch_args emits [--model, model, --auto] and runner passes that after `herdr agent start ... --`, producing the rejected root command. No prompt/session or auth was used. V2 CLI docs: https://opencode.ai/v2/docs/cli/ and https://opencode.ai/v2/docs/cli/commands/ . Isolated environment initially lacked opencode; installed official pinned 2.1.4 in disposable container to continue.

<!-- fr:journal kind=hypothesis scope=debug id=api-created-model-session-attaches created=2026-10-24T12:07:36+00:00 -->
### api-created-model-session-attaches · hypothesis · API-created sessions may preserve model for interactive attach

Tagged OpenCode v2.1.4 source confirms root opencode supports --auto and --session, while --model is declared only on run/mini; root handler resolves the given session and passes its ID into the interactive TUI. Server session.create forwards ctx.payload.model into Session.create, Session.Info includes optional Model.Ref, and Session.switchModel persists a session.model.selected event. Need verify from source that the full TUI consumes the persisted model and establish a safe supported way for fr-herdr to create the session on the managed server without user config or credentials. If yes, fix likely create-model-session then launch interactive --auto --session ID; no API/session integration has been exercised and no session created.
