// The run-session export — spec 2026-10-02-opencode-observe-2 §B (R1).
//
// fr could not tell which OpenCode session is the run: nothing OpenCode sets
// in a command's environment names the session that issued it, so `fr run
// advance` recorded no session on an OpenCode attempt, the usage capture found
// nothing, and every transcript gate read "unobserved". Claude Code exports
// its own key (CLAUDE_CODE_SESSION_ID); this is OpenCode's counterpart.
//
// OpenCode fires `shell.env` with `{cwd, sessionID, callID}` before every
// `bash` tool call and merges the returned `env` into the command's
// environment (present in the 1.18.33 binary; typed in `@opencode-ai/plugin`
// 1.17.15's `Hooks`). The id is the CALLING session's — a child's when a
// subagent runs the command; fr walks `parent_id` to the run session itself.
//
// Transport only, and NEVER THROWS: an exception is swallowed, as the idle and
// claim handlers do. A missing or empty session id leaves the env untouched.
export const SESSION_ENV_KEY = "FR_OPENCODE_SESSION_ID";

export type ShellEnvInput = { cwd: string; sessionID?: string; callID?: string };
export type ShellEnvOutput = { env?: Record<string, string> };

export function createShellEnvHandler(): (
  input: ShellEnvInput,
  output: ShellEnvOutput
) => Promise<void> {
  return async (input, output) => {
    try {
      const session = input?.sessionID;
      if (typeof session !== "string" || session === "") return;
      // A binary that hands over no env object would otherwise swallow a
      // TypeError here and R1 would fail invisibly (review p1-r3).
      output.env ??= {};
      output.env[SESSION_ENV_KEY] = session;
    } catch {
      // Attribution, not a gate: a failure here must never fail the command.
    }
  };
}
