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

<!-- fr:journal kind=finding scope=debug id=review-api-response-envelope-resolved created=2026-10-24T12:25:13+00:00 state=refuted resolves=review-api-response-envelope -->
### review-api-response-envelope-resolved · finding [refuted] · resolves review-api-response-envelope: Review questioned session-create response envelope

Verified against official v2.1.4 tagged source: packages/protocol/src/groups/session.ts declares success Schema.Struct({ data: PublicSessionInfo }), and packages/server/src/handlers/session.ts returns { data: yield* session.create(...) }. The api command writes that JSON response text unchanged, so reading response.data is correct. No live session or service was used.

<!-- fr:journal kind=discovery scope=debug id=verification-after-docker-recovery created=2026-10-24T17:43:40+00:00 -->
### verification-after-docker-recovery · discovery · Bounded verification passes; full suite run exposed compatibility follow-ups

After Docker recovery, the preserved branch/worktree was verified at HEAD 947b8920. Focused mypy and 254 Herdr tests passed. A conservative full-suite run with pytest -n 2 completed with 13,463 passed, 136 skipped, 10 failed; it was NOT green. Failures exposed legacy descriptors lacking session IDs, replacement not carrying the source descriptor session, and synthetic installed scenarios not stubbing the new OpenCode API. Fixed those paths/tests. The affected unit tests now pass (277 tests), and the four related installed scenarios passed in a separate focused rerun (27 combined unit/scenario tests). Mypy, Ruff, format, diff check, acceptance check (561 rows), and change-fragment gate pass on the updated tree. No full-suite rerun was performed after these fixes; full suite remains unverified, not green. No real API session, fixture session, shared-service restart, or A/B fixture was used.

<!-- fr:journal kind=discovery scope=debug id=final-followup-review-no-findings created=2026-10-24T17:56:07+00:00 -->
### final-followup-review-no-findings · discovery · Independent review found no follow-up compatibility issues

Reviewer session ses_e90fefc9cffeDA9HQnDaUuksz9 reviewed the final code/test diff after the 10-failure bounded full-suite run and after the compatibility follow-ups: strict exact session-ID identity for pinned descriptors, legacy argument matching when session is absent, source-session propagation during replacement, and synthetic API stubs/session launch assertions. The reviewer checked the v2.1.4 protocol/server contract and returned no findings. This is a read-only review result, not an approval or CI/full-suite pass. The review covered commit 559fa99c and the final source/test diff; the later local commit only adds 1217/result-summary.md.

<!-- fr:journal kind=review scope=debug id=final-independent-review created=2026-10-24T18:06:19+00:00 -->
### final-independent-review · review · Independent final compatibility review found no findings

Reviewer session ses_e90fefc9cffeDA9HQnDaUuksz9 rechecked the post-full-suite-failure compatibility fixes: strict selected-session identity, legacy descriptor matching, replacement source-session propagation, and synthetic API scenarios against tagged OpenCode 2.1.4. No findings were returned. This records independent code review, not operator approval or a live recovery pass. Final focused verification: 277 unit tests and four related installed scenarios passed; full suite had 13463 passed,136 skipped,10 failures before those fixes and was not rerun locally on the corrected tree. Draft PR1245 CI is the current whole-tree check. Detailed result summary is retained in the durable coordination artifact bundle at release-control-2026-10-24/1217/result-summary.md, not a new top-level repository folder. No gate, merge or release is authorized by this record.

<!-- fr:journal kind=repro scope=debug id=rc10-default-variant-create-session-false-negative created=2026-10-24T21:16:14+00:00 -->
### rc10-default-variant-create-session-false-negative · repro · RC10 rejected a correctly selected OpenCode session default variant

The published RC10 fixture dispatch failed in create_session with “OpenCode did not confirm the requested session model.” Its request selected provider openai and model gpt-6.1-sol explicitly and supplied the fixture location. A read-only GET of the newly persisted session, whose creation timestamp matches the failure, showed the same provider and model with variant default. The POST response body was not captured. No prompt was submitted; no batch dispatch event or run cursor was written. Herdr automatically closed the runner-created w24:p2 tab on this failure path. That closure was an unauthorized runner side effect, not a manual cleanup or a successful launch. The prepared descriptor remains untouched in the coordinator bundle.

<!-- fr:journal kind=root-cause scope=debug id=rc10-default-variant-response-normalization created=2026-10-24T21:16:28+00:00 -->
### rc10-default-variant-response-normalization · root-cause · Variant equality compared a server default to an unrequested absence

RC10 create_session builds the correct POST /api/session model reference: {providerID: openai, id: gpt-6.1-sol}, with no variant because the requested model has no #variant suffix. OpenCode v2.1.4 accepts Model.Ref.variant as optional and returns a valid persisted session model with variant default. The helper then compared selected.variant to None and falsely refused an otherwise exact provider/model match. The official v2.1.4 protocol tag confirms the POST payload and data-wrapped PublicSessionInfo response; the live persisted record confirms the server selection. This is not provider/model rejection, a response-envelope mismatch, or fallback to root --model. The manual C fixture used the same provider/model selection with no explicit variant. The session POST response bytes themselves were not retained, so the GET record is the live evidence.

<!-- fr:journal kind=finding scope=debug id=rc10-default-variant-response-fixed created=2026-10-24T21:16:39+00:00 state=fixed -->
### rc10-default-variant-response-fixed · finding [fixed] · Accept valid API-selected variants without weakening model identity

Changed create_session to require the exact requested provider and model ID, require exact variant equality when a #variant was explicitly requested, and accept an omitted or valid string variant when the API resolves an unqualified model. Malformed variant types, wrong provider/model, missing session identity, malformed envelopes, and explicit variant mismatch remain refusals. OpenCode still launches attached to the returned session with --auto; no root --model fallback was added. Added a sanitized 2.1.4 response fixture and positive/negative tests. The Herdr launch acceptance row remains walk-owed: the actual RC10 failure and automatic pane closure do not prove a live managed launch.

<!-- fr:journal kind=review scope=debug id=independent-review-default-variant-fix created=2026-10-24T21:18:42+00:00 -->
### independent-review-default-variant-fix · review · Independent code review found no findings

An independent read-only review examined the model-confirmation fix, negative tests, acceptance row, patch fragment, and journal. No findings. Reviewer confirmed provider/model identity and explicit variants remain strict; the user-unspecified API default is accepted without a root --model fallback, and --session --auto is unchanged. This review is not a live managed-runner pass; herdr-opencode-launch remains walk-owed.

<!-- fr:journal kind=review scope=debug id=pr-1249-independent-review created=2026-10-24T21:21:03+00:00 -->
### pr-1249-independent-review · review · PR 1249 independent review found no findings

Draft PR #1249 is open. An independent read-only final review of the exact proposed code and tests found no findings. The reviewer confirmed exact provider/model checks, strict explicit-variant matching, refusal of malformed confirmations, and unchanged --session --auto behavior. The Herdr OpenCode launch acceptance remains walk-owed; no Ready, merge, release, or live retry is authorized.
