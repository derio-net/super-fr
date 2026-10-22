// The child-session claim — gh#530, closing gh#527's C1 on OpenCode.
//
// OpenCode's task tool BLOCKS: the orchestrator learns a dispatched child's
// session id only when the child has finished, so `fr run claim --agent <id>`
// used to land after the unit was over, and `fr run status` said "HELD BY an
// unclaimed agent" for the whole of it. The child itself knows both facts fr
// is missing — its own session id, and the agent OpenCode actually runs it as
// (`fr-phase-executor-<tier>`: the tier rides in the name, gh#537) — from its
// FIRST tool call. So on that call, this hands them to fr once.
//
// Transport only. WHICH unit the child holds is `fr run claim --open-unit`'s
// verdict: it claims the one open, unclaimed unit dispatched to that agent and
// refuses (exit 2) when zero or several fit — which is also what keeps an
// unrelated subagent (an `explore` child) from claiming a phase. This file
// knows a session id, an agent name and a model; it holds no opinion about a
// run.
//
// The rules, in the order they bite:
//   - TOP-LEVEL SESSIONS are left alone. Only a child is dispatched work; a
//     session that cannot be looked up, or names no agent, is not claimed for.
//   - AT MOST ONCE PER SESSION, remembered BEFORE fr runs, so a broken fr is
//     never retried on every tool call. Shared by every loaded copy of the
//     plugin (`sharedClaimed`), as the idle memory is (gh#563).
//   - NEVER THROWS, and never reports: fr refusing, missing, too old to know
//     `--open-unit`, or hanging are all silence. A claim is attribution; the
//     open record already refuses a second dispatch without it.
//
// OpenCode 2 (V2 plugin API): the hook is `ctx.tool.hook("execute.before")`,
// whose event carries `sessionID`, and the lookup is `ctx.session.get({sessionID})`,
// which resolves to the session info itself (`parentID`, `agent`, `model`) and
// throws on a failed lookup.
//
// NOT PROVEN: that this runs, in a live OpenCode session, before the child's
// first tool executes. The session shape was read off `@opencode/client`
// 2.0.32's `SessionInfo`; the handler itself is driven by a fake session API in
// the tests. Until a live run shows the
// claim landing (the gh#494 standard), `parity.yaml` keeps
// `dispatch-holder-identity` `partial` on OpenCode.
import { run } from "./spawn";

export type ClaimAnswer = { code: number | null };

/** `globalThis` key for the plugin's process-wide once-per-session memory. */
export const SHARED_CLAIMED = Symbol.for("super-fr.fr-opencode-plugin.claim.claimed");

export type ClaimHandlerOptions = {
  /** `ctx.session` — only its `get({sessionID})` is used. */
  session: unknown;
  directory: string;
  /** Test seam. Default: `fr <args>` in `cwd`. */
  runFr?: (cwd: string, args: string[]) => Promise<ClaimAnswer>;
  timeoutMs?: number;
  /** Once-per-session memory. The plugin passes `sharedClaimed()`. */
  claimed?: Set<string>;
};

export function sharedClaimed(): Set<string> {
  const slot = globalThis as Record<symbol, Set<string> | undefined>;
  return (slot[SHARED_CLAIMED] ??= new Set<string>());
}

const DEFAULT_TIMEOUT_MS = 20_000;

function defaultRunFr(timeoutMs: number): (cwd: string, args: string[]) => Promise<ClaimAnswer> {
  return async (cwd, args) => ({ code: (await run("fr", args, { cwd, timeoutMs })).code });
}

type Child = { agent: string; model?: string };

/** The child's agent and model — or undefined for a top-level session, a
 * failed lookup, or one that names no agent. */
async function childOf(session: unknown, id: string): Promise<Child | undefined> {
  const get = (session as { get?: unknown } | null | undefined)?.get;
  if (typeof get !== "function") return undefined;
  const data = (await get.call(session, { sessionID: id })) as Record<string, unknown> | null | undefined;
  if (!data || typeof data !== "object") return undefined;
  if (typeof data.parentID !== "string" || data.parentID === "") return undefined;
  if (typeof data.agent !== "string" || data.agent === "") return undefined;
  const model = data.model as { providerID?: unknown; id?: unknown } | undefined;
  const named =
    model && typeof model.providerID === "string" && typeof model.id === "string"
      ? `${model.providerID}/${model.id}`
      : undefined;
  return { agent: data.agent, model: named };
}

export function createClaimHandler(options: ClaimHandlerOptions) {
  const runFr = options.runFr ?? defaultRunFr(options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const claimed = options.claimed ?? new Set<string>();

  return async (input: { sessionID?: unknown }): Promise<void> => {
    try {
      const sessionID = input?.sessionID;
      if (typeof sessionID !== "string" || sessionID === "") return;
      if (claimed.has(sessionID)) return;
      claimed.add(sessionID);

      const child = await childOf(options.session, sessionID);
      if (!child) return;

      const args = ["run", "claim", "--open-unit", "--agent", sessionID, "--agent-type", child.agent];
      args.push("--harness", "opencode");
      if (child.model) args.push("--model", child.model);
      await runFr(options.directory, args);
    } catch {
      // Fail open, always. See the header.
    }
  };
}
