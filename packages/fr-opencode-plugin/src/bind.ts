// Session bind/unbind — the OpenCode 2 port of plugins/super-fr/hooks/fr-session-bind.sh
// and fr-session-unbind.sh (spec 2026-10-20-opencode-2-support R11).
//
// super-fr-parity: fr-session-bind.sh
// super-fr-parity: fr-session-unbind.sh
//
// A completed `shell` call whose first line is `fr isolation up|exec|down` or
// `fr run start` (after an optional leading `cd <dir> &&|;`, env assignments
// and `uv run`) binds or unbinds this session through `fr isolation
// attach|detach`. A `session.deleted` event detaches. Transport only — the
// engine is `fr isolation attach/detach` — and best-effort: bounded, never
// throws, never blocks the call it follows. A child session never rebinds its
// parent (the bash hook's `agent_id` rule).
import { realpathSync, statSync } from "node:fs";
import { isAbsolute, resolve } from "node:path";
import { stripCommandPrefix } from "./guard";
import { runFr } from "./fr";
import { sessionDirectory, type SessionInfo } from "./session";
import type { RunAnswer } from "./spawn";

const DEFAULT_TIMEOUT_MS = 20_000;
const S = "[ \\t\\n\\v\\f\\r]";
const CD = new RegExp(`^${S}*cd${S}+("([^"]+)"|'([^']+)'|([^ \\t\\n\\v\\f\\r;&|]+))${S}*(&&|;)${S}*(.*)$`);
const ISOLATION_VERB = new RegExp(`^${S}*fr${S}+isolation${S}+(up|exec|down)(${S}|$)`);
const RUN_START = new RegExp(`^${S}*fr${S}+run${S}+start(${S}|$)`);
// Greedy `.*` first, as sed's is: the LAST `--branch` on the line wins.
const BRANCH = new RegExp(`.*--branch(=|${S}+)("([^"]+)"|'([^']+)'|([^ \\t\\n\\v\\f\\r]+))`);

export type FrRunner = (args: string[], cwd: string) => Promise<RunAnswer>;

export type BindOptions = {
  /** `ctx.session` — `get({sessionID})`, to skip child sessions. */
  session: unknown;
  directory: string;
  /** Test seam. Default: `fr <args>`, bounded. */
  runFr?: FrRunner;
  timeoutMs?: number;
};

type AfterEvent = { tool?: unknown; sessionID?: unknown; status?: unknown; input?: unknown };

function realDir(path: string): string | undefined {
  try {
    return statSync(path).isDirectory() ? realpathSync(path) : undefined;
  } catch {
    return undefined;
  }
}

/** Whether a shell command's first line could bind at all: pure command text
 * (an optional leading `cd`, then `fr isolation up|exec|down` / `fr run start`),
 * no filesystem and no session. The cheap check before any session lookup. */
export function canBind(command: string): boolean {
  let first = command.split("\n")[0] ?? "";
  const cd = CD.exec(first);
  if (cd) first = cd[6] ?? "";
  first = stripCommandPrefix(first);
  return ISOLATION_VERB.test(first) || RUN_START.test(first);
}

/** The argv `fr` gets for one completed shell command, or undefined. Pure. */
export function bindArgs(command: string, cwd: string, sessionID: string, home = process.env.HOME ?? ""): string[] | undefined {
  let first = command.split("\n")[0] ?? "";
  let repo = cwd;
  const cd = CD.exec(first);
  if (cd) {
    let target = (cd[2] ?? "") + (cd[3] ?? "") + (cd[4] ?? "");
    if (target.startsWith("~")) target = home + target.slice(1);
    const landed = realDir(isAbsolute(target) ? target : resolve(cwd, target));
    if (!landed || realDir(cwd) === undefined) return undefined;
    repo = landed;
    first = cd[6] ?? "";
  }
  first = stripCommandPrefix(first);
  let verb = ISOLATION_VERB.exec(first)?.[1];
  if (!verb && RUN_START.test(first)) verb = "up";
  if (!verb) return undefined;
  if (verb === "down") return ["isolation", "detach", "--session", sessionID];
  const b = BRANCH.exec(first);
  const branch = b ? (b[3] ?? "") + (b[4] ?? "") + (b[5] ?? "") : "";
  return [
    "isolation",
    "attach",
    "--session",
    sessionID,
    "--repo",
    repo,
    ...(branch ? ["--branch", branch] : []),
    "--harness",
    "opencode",
  ];
}

/** The session's info, unless it is a child (undefined for a child). A failed
 * lookup, or an answer whose `id` is not this session's, is not a child: the bash
 * hook skips only on agent_id, so the caller falls back to the plugin directory. */
async function parentInfo(session: unknown, id: string): Promise<{ child: boolean; info?: SessionInfo }> {
  try {
    const get = (session as { get?: unknown } | null | undefined)?.get;
    if (typeof get !== "function") return { child: false };
    const info = (await (get as (r: { sessionID: string }) => Promise<unknown>).call(session, { sessionID: id })) as
      | SessionInfo
      | null
      | undefined;
    if (!info || typeof info !== "object") return { child: false };
    // An answer about another session (nag's check): not this one's directory, and no
    // evidence it is a child. Bind from the plugin directory.
    if (info.id !== id) return { child: false };
    if (typeof info.parentID === "string" && info.parentID !== "") return { child: true };
    return { child: false, info };
  } catch {
    return { child: false };
  }
}

function defaultRunner(timeoutMs: number): FrRunner {
  return (args, cwd) => runFr(args, { cwd, timeoutMs });
}

/** `execute.after`: bind on a completed `fr isolation up|exec|down` / `fr run start`. */
export function createBindHandler(options: BindOptions) {
  const runFr = options.runFr ?? defaultRunner(options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  return async (event: AfterEvent | null | undefined): Promise<void> => {
    try {
      if (!event || event.tool !== "shell" || event.status !== "completed") return;
      const sessionID = event.sessionID;
      if (typeof sessionID !== "string" || sessionID === "") return;
      const input = (event.input ?? {}) as { command?: unknown; workdir?: unknown };
      if (typeof input.command !== "string" || input.command === "") return;
      if (!canBind(input.command)) return; // before any lookup
      // One lookup: the child check and the session's own directory.
      const { child, info } = await parentInfo(options.session, sessionID);
      if (child) return;
      const sessionDir = info ? sessionDirectory(info, options.directory) : options.directory;
      const cwd = shellCwd(sessionDir, input.workdir);
      const args = bindArgs(input.command, cwd, sessionID);
      if (!args) return;
      await runFr(args, cwd);
    } catch {
      // Best-effort. See the header.
    }
  };
}

/** `session.deleted` from the event subscription: detach, fire-and-forget. */
export function createUnbindHandler(options: { directory: string; runFr?: FrRunner; timeoutMs?: number }) {
  const runFr = options.runFr ?? defaultRunner(options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  return async (event: { type?: unknown; data?: unknown } | null | undefined): Promise<void> => {
    try {
      if (!event || event.type !== "session.deleted") return;
      const sessionID = (event.data as { sessionID?: unknown } | undefined)?.sessionID;
      if (typeof sessionID !== "string" || sessionID === "") return;
      // Runs in the plugin's directory on purpose: `fr isolation detach --session`
      // acts on the session's bindings wherever they are (isolation_cmd.py detach),
      // so its cwd chooses nothing.
      // Not awaited: the subscription loop must not wait ~2s of Python start
      // per deleted session. `run` is bounded and never rejects.
      void runFr(["isolation", "detach", "--session", sessionID], options.directory).catch(() => undefined);
    } catch {
      // Best-effort.
    }
  };
}

/** Where a V2 `shell` call runs: its optional `workdir` (measured on 2.0.32:
 * the input is `{command, workdir?}`), relative to the session directory. */
export function shellCwd(directory: string, workdir: unknown): string {
  return typeof workdir === "string" && workdir !== "" ? resolve(directory, workdir) : directory;
}
