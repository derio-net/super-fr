<!-- fr:journal-schema=3 -->
# Journal: opencode-v2-recovery-launch

<!-- fr:journal kind=repro scope=debug id=root-model-flag-rejected created=2026-10-24T11:58:46+00:00 -->
### root-model-flag-rejected · repro · OpenCode 2.1.4 rejects the managed recovery launch flags

Host OpenCode v2.1.4 reproduces the recovery-launch failure: `opencode --model openai/gpt-6.1-sol --auto --fr-probe-unsupported-option` exits 1 with `Unrecognized flag: --model in command opencode`. Its `mini --help` exposes --model but not --auto; `mini --model ... --auto` rejects --auto. Pinned fr-herdr launch_args emits [--model, model, --auto] and runner passes that after `herdr agent start ... --`, producing the rejected root command. No prompt/session or auth was used. V2 CLI docs: https://opencode.ai/v2/docs/cli/ and https://opencode.ai/v2/docs/cli/commands/ . Isolated environment initially lacked opencode; installed official pinned 2.1.4 in disposable container to continue.

<!-- fr:journal kind=hypothesis scope=debug id=api-created-model-session-attaches created=2026-10-24T12:07:36+00:00 -->
### api-created-model-session-attaches · hypothesis · API-created sessions may preserve model for interactive attach

Tagged OpenCode v2.1.4 source confirms root opencode supports --auto and --session, while --model is declared only on run/mini; root handler resolves the given session and passes its ID into the interactive TUI. Server session.create forwards ctx.payload.model into Session.create, Session.Info includes optional Model.Ref, and Session.switchModel persists a session.model.selected event. Need verify from source that the full TUI consumes the persisted model and establish a safe supported way for fr-herdr to create the session on the managed server without user config or credentials. If yes, fix likely create-model-session then launch interactive --auto --session ID; no API/session integration has been exercised and no session created.

<!-- fr:journal kind=root-cause scope=debug id=root-cli-model-flag-invalid created=2026-10-24T12:12:44+00:00 -->
### root-cli-model-flag-invalid · root-cause · Root CLI has no model flag; selection belongs to session

OpenCode v2.1.4 has a confirmed CLI/API contract mismatch in fr-herdr: launch_args emits root --model MODEL --auto, but the tagged root command schema accepts --auto and --session, not --model; binary v2.1.4 reproduces Unrecognized flag: --model in command opencode. mini accepts --model but not --auto, and run is noninteractive, so neither is a compliant substitution. The exact v2.1.4 source provides a compliant candidate: POST /api/session supports optional Model.Ref and location; Session.Info persists model; the root TUI finds an existing --session and the session UI restores its durable model; root --auto remains supported. Intended minimal direction: create a fresh explicitly model-selected session through OpenCode own API, then launch the interactive root with --session ID --auto. Need adapt initial, replacement, and restart flows and preserve fail-closed identity checks. No session has been created.

<!-- fr:journal kind=finding scope=debug id=review-api-response-envelope created=2026-10-24T12:25:05+00:00 state=open review_scope=in -->
### review-api-response-envelope · finding [open] (reviewer: in scope) · Review questioned session-create response envelope

Independent reviewer asserted v2.1.4 POST /api/session returns the Session object directly and therefore the code incorrectly reads response.data. Tagged v2.1.4 protocol source defines success as Schema.Struct({ data: PublicSessionInfo }); tagged server handler returns { data: yield* session.create(...) }; CLI api writes response.text unchanged. Verify before resolution; if those tagged sources remain authoritative, the review finding is mistaken.
