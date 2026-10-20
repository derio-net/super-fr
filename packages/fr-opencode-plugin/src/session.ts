// The run-session export — spec 2026-10-02-opencode-observe-2 §B (R1), ported
// to OpenCode 2 by spec 2026-10-20-opencode-2-support (R7).
//
// fr could not tell which OpenCode session is the run: nothing OpenCode sets
// in a command's environment names the session that issued it. Claude Code
// exports its own key (CLAUDE_CODE_SESSION_ID); this is OpenCode's counterpart.
//
// OpenCode 1.x handed the session id straight to `shell.env`. OpenCode 2's
// `shell` hook `create.before` carries `{command, cwd, timeout, shell, env}` and
// NO session id. The session is known one step earlier, at the tool layer:
// `tool` hook `execute.before` fires with `{tool: "shell", sessionID, input}`.
// So this keeps a short-lived PENDING list of `(sessionID, command)` from
// `execute.before`, and `create.before` exports FR_OPENCODE_SESSION_ID only when
// EXACTLY ONE pending entry, from exactly one session, matches its command.
// Ambiguity, no match, or an expired entry export nothing: an unattributed
// command is honest; a misattributed one is a lie fr would build on. There is
// deliberately no "most recent session" fallback.
//
// Transport only, and NEVER THROWS.
export const SESSION_ENV_KEY = "FR_OPENCODE_SESSION_ID";

/** The tool name of OpenCode 2's shell tool (`bash` in 1.x). */
export const SHELL_TOOLS = new Set(["shell", "bash"]);

export type ShellCreateEvent = {
  command?: string;
  cwd?: string;
  env?: Record<string, string | undefined>;
};

export type ToolBeforeEvent = { tool?: unknown; sessionID?: unknown; input?: unknown };

type Pending = { sessionID: string; command: string; at: number };

export type SessionExportOptions = {
  /** How long a recorded tool call may wait for its shell. Default 30 s. */
  ttlMs?: number;
  now?: () => number;
};

const DEFAULT_TTL_MS = 30_000;

function commandOf(input: unknown): string | undefined {
  const command = (input as { command?: unknown } | null | undefined)?.command;
  return typeof command === "string" && command !== "" ? command : undefined;
}

export function createSessionExport(options: SessionExportOptions = {}) {
  const ttl = options.ttlMs ?? DEFAULT_TTL_MS;
  const now = options.now ?? Date.now;
  let pending: Pending[] = [];

  const prune = (at: number) => {
    pending = pending.filter((entry) => at - entry.at <= ttl);
  };

  return {
    /** `tool` `execute.before`: remember a shell call's session and command. */
    record(event: ToolBeforeEvent): void {
      try {
        if (typeof event?.tool !== "string" || !SHELL_TOOLS.has(event.tool)) return;
        const sessionID = event.sessionID;
        if (typeof sessionID !== "string" || sessionID === "") return;
        const command = commandOf(event.input);
        if (!command) return;
        const at = now();
        prune(at);
        pending.push({ sessionID, command, at });
      } catch {
        // Attribution, not a gate.
      }
    },
    /** `shell` `create.before`: export the session only on one unambiguous match. */
    async apply(event: ShellCreateEvent): Promise<void> {
      try {
        if (!event || typeof event.command !== "string") return;
        prune(now());
        const matches = pending.filter((entry) => entry.command === event.command);
        if (matches.length === 0) return;
        // Consumed whatever the verdict: a matched command is not reused later.
        pending = pending.filter((entry) => entry.command !== event.command);
        if (matches.length !== 1) return;
        event.env ??= {};
        event.env[SESSION_ENV_KEY] = matches[0]!.sessionID;
      } catch {
        // Attribution, not a gate: a failure here must never fail the command.
      }
    },
    /** Test seam: how many calls are waiting. */
    size(): number {
      return pending.length;
    },
  };
}
