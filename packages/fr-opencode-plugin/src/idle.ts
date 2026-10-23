// The OpenCode half of the idle guard — spec 2026-09-20-unit-record-unification
// §4.G, the artifact half of gh#518: an fr run that is ADVANCEABLE WITH NOBODY
// WORKING ON IT should not just sit there because a turn ended on a report.
//
// OpenCode cannot refuse a stop (Claude Code can: see
// plugins/super-fr/hooks/fr-run-idle-guard.sh, whose contract this mirrors).
// It can CONTINUE a session. So when a turn ENDS this asks fr whether the run
// is idle and, if it is, sends fr's next command back into the session.
//
// WHICH event "a turn ended" is moved under us (gh#1231). 2.0.32 shipped
// `session.idle` (ephemeral, `data.sessionID`); 2.1.x removed it and ends an
// execution with `session.execution.succeeded` (durable, the same
// `data.sessionID`). A handler matching only the first is inert on every 2.1
// server, and it fails SILENTLY — the event is simply never seen, so nothing
// errors and the run sits there. Both names are accepted; that is a two-string
// set, not an abstraction, because those are the two shapes that exist.
//
// Transport only. WHETHER a run is idle is `fr run check --idle`'s verdict
// (`fr.run.liveness.is_idle`, Python) and nobody else's. This file knows a
// session id, a directory and an opaque position token; it holds no opinion
// about a run, and a test greps it to keep it that way.
//
// The rules, in the order they bite:
//   - SILENT on anything but a clean, parsed "idle": exit code 3 AND a JSON
//     object with `idle === true` AND string `position` + `next_command`.
//     fr missing, erroring, refusing (exit 2: the migration refusal, or an fr
//     too old to know `--idle`), hanging, or printing garbage — all silence.
//   - NEVER THROWS. An exception out of an `event` hook is this plugin breaking
//     the session it meant to help. The whole handler is one try/catch.
//   - AT MOST ONCE PER RUN POSITION per session — the loop breaker. If
//     `advance` keeps failing, or the model keeps stopping, a nudge that
//     repeats is a trap. Remembered BEFORE sending, so a broken endpoint cannot
//     become a retry loop either. In memory: it lives as long as the OpenCode
//     server that loaded the plugin, and forgetting costs one extra nudge.
//     Shared by every copy loaded into that process (`sharedActedOn`): the
//     global install plus a project-local one must still nudge once (gh#563).
//     The check-and-set has no `await` between them, so two copies racing on
//     the same idle event cannot both pass it.
//   - CHILD SESSIONS are left alone. A subagent's session goes idle when it
//     finishes; it does not own the run. A session that cannot be looked up is
//     not assumed to be top-level.
//
// OpenCode 2 (V2 plugin API): events arrive from `ctx.event.subscribe({signal})`,
// an async iterable (`runIdleLoop`), each `{type, data}`; both turn-end events
// name their session as `data.sessionID` (checked against
// `@opencode/schema` 2.0.32 and 2.1.x). The lookup is
// `ctx.session.get({sessionID})` (the info itself, throwing on failure) and the
// nudge `ctx.session.prompt`.
//
// `session.execution.succeeded` is DURABLE, so a reconnecting stream can replay
// it. The once-per-position memory below is what makes a replay free, and the
// same memory is why accepting an event that fires more often than "the session
// went quiet" is safe: a burst of successes at one position buys one nudge.
//
// PROVEN LIVE 2026-10-23 (gh#1231): OpenCode 2.1.3, isolated HOME/XDG and a
// logging `fr` shim, an advanceable run in a disposable clone — the model
// replied, the nudge arrived as a plugin-authored session message, and the model
// ran `fr run advance <run>`. That is the gh#494 standard for this surface, so
// `parity.yaml`'s `fr-run-idle-guard` OpenCode cell is `enforced`.
//
// The server hands one terminal event to every subscribed listener (three, in
// that walk), so the once-per-position memory is also what keeps the nudge
// single when the same turn end arrives several times.
import { run } from "./spawn";

export type FrAnswer = { code: number | null; stdout: string };

/** The events that mean "this session's turn ended": 2.0.32's name, then
 * 2.1.x's. See the header for why both are kept. */
const TURN_END_EVENTS = new Set(["session.idle", "session.execution.succeeded"]);

/** `globalThis` key for the plugin's process-wide once-per-position memory. */
export const SHARED_ACTED_ON = Symbol.for("super-fr.fr-opencode-plugin.idle.actedOn");

export type IdleHandlerOptions = {
  /** `ctx.session` — `get({sessionID})` and `prompt({sessionID, text})`. */
  session: unknown;
  directory: string;
  /** Test seam. Default: `fr run check --idle --format json` in `cwd`. */
  runFr?: (cwd: string) => Promise<FrAnswer>;
  timeoutMs?: number;
  /** Once-per-position memory. Default: this handler's own. The plugin passes
   * `sharedActedOn()` so every loaded copy shares one (gh#563). */
  actedOn?: Map<string, string>;
};

/** The one once-per-position memory for every copy of this plugin loaded into
 * this process. install.sh delivers a global copy (gh#563), and a repo that
 * also loads it project-locally gets two module instances — module state is
 * per copy, `globalThis` is not, so the memory lives there. */
export function sharedActedOn(): Map<string, string> {
  const slot = globalThis as Record<symbol, Map<string, string> | undefined>;
  return (slot[SHARED_ACTED_ON] ??= new Map<string, string>());
}

const DEFAULT_TIMEOUT_MS = 20_000;

function defaultRunFr(timeoutMs: number): (cwd: string) => Promise<FrAnswer> {
  return async (cwd) => {
    const { code, stdout } = await run("fr", ["run", "check", "--idle", "--format", "json"], { cwd, timeoutMs });
    return { code, stdout };
  };
}

type Verdict = { position: string; nextCommand: string; run: string; detail: string };

function parseVerdict(answer: FrAnswer): Verdict | undefined {
  if (answer.code !== 3) return undefined;
  let body: unknown;
  try {
    body = JSON.parse(answer.stdout);
  } catch {
    return undefined;
  }
  if (typeof body !== "object" || body === null || Array.isArray(body)) return undefined;
  const fields = body as Record<string, unknown>;
  if (fields.idle !== true) return undefined;
  const { position, next_command: nextCommand } = fields;
  if (typeof position !== "string" || position === "") return undefined;
  if (typeof nextCommand !== "string" || nextCommand === "") return undefined;
  return {
    position,
    nextCommand,
    run: typeof fields.run === "string" ? fields.run : "this run",
    detail: typeof fields.detail === "string" ? fields.detail : "",
  };
}

type SessionApi = {
  get: (req: { sessionID: string }) => Promise<unknown>;
  prompt: (req: { sessionID: string; text: string }) => Promise<unknown>;
};

function sessionApi(session: unknown): SessionApi | undefined {
  const api = session as Partial<SessionApi> | null | undefined;
  if (!api || typeof api.get !== "function" || typeof api.prompt !== "function") return undefined;
  return api as SessionApi;
}

/** True only when the lookup SUCCEEDED and named no parent. */
async function isTopLevel(api: SessionApi, id: string): Promise<boolean> {
  const info = (await api.get({ sessionID: id })) as { id?: unknown; parentID?: unknown } | null | undefined;
  // A successful lookup names the session it found; anything else is unknown.
  if (!info || typeof info !== "object" || info.id !== id) return false;
  return info.parentID === undefined || info.parentID === null;
}

export function createIdleHandler(options: IdleHandlerOptions) {
  const runFr = options.runFr ?? defaultRunFr(options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const actedOn = options.actedOn ?? new Map<string, string>();

  return async (event: { type?: unknown; data?: unknown } | null | undefined): Promise<void> => {
    try {
      if (!event || typeof event.type !== "string" || !TURN_END_EVENTS.has(event.type)) return;
      const sessionID = (event.data as { sessionID?: unknown } | undefined)?.sessionID;
      if (typeof sessionID !== "string" || sessionID === "") return;

      const api = sessionApi(options.session);
      if (!api) return;
      if (!(await isTopLevel(api, sessionID))) return;

      const verdict = parseVerdict(await runFr(options.directory));
      if (!verdict) return;

      if (actedOn.get(sessionID) === verdict.position) return;
      actedOn.set(sessionID, verdict.position);

      await api.prompt({
        sessionID,
        text:
          `fr run ${verdict.run} is idle — ${verdict.detail} (gh#518). Nothing is ` +
          `blocking it: run \`${verdict.nextCommand}\` now and act on what it prints — ` +
          "a dispatch brief means dispatch that unit, then report. If you stopped on " +
          "purpose (the operator asked, or you are waiting on something fr cannot " +
          "see), say so and stop: this nudge is sent once per run position.",
      });
    } catch {
      // Fail open, always. See the header.
    }
  };
}

type EventSource = { subscribe?: (options?: { signal?: AbortSignal }) => AsyncIterable<unknown> };

/** Feed `ctx.event.subscribe({signal})` to `handle` until `signal` aborts. Never
 * throws: a stream that fails or ends just stops the guard. */
export async function runIdleLoop(
  events: unknown,
  handle: (event: { type?: unknown; data?: unknown }) => Promise<void>,
  signal: AbortSignal
): Promise<void> {
  try {
    const source = events as EventSource | null | undefined;
    if (!source || typeof source.subscribe !== "function") return;
    for await (const event of source.subscribe({ signal })) {
      if (signal.aborted) return;
      // Awaited, so two idle events never race the once-per-position memory.
      // `handle` never throws.
      await handle(event as { type?: unknown; data?: unknown });
    }
  } catch {
    // Fail open, always. See the header.
  }
}
