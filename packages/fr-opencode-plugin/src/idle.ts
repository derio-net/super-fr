// The OpenCode half of the idle guard — spec 2026-09-20-unit-record-unification
// §4.G, the artifact half of gh#518: an fr run that is ADVANCEABLE WITH NOBODY
// WORKING ON IT should not just sit there because a turn ended on a report.
//
// OpenCode cannot refuse a stop (Claude Code can: see
// plugins/super-fr/hooks/fr-run-idle-guard.sh, whose contract this mirrors).
// It can CONTINUE a session. So on `session.idle` this asks fr whether the run
// is idle and, if it is, sends fr's next command back into the session.
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
//   - CHILD SESSIONS are left alone. A subagent's session goes idle when it
//     finishes; it does not own the run. A session that cannot be looked up is
//     not assumed to be top-level.
//
// NOT PROVEN: that a prompt sent from a plugin on `session.idle` actually
// EXECUTES in a live OpenCode session. `session.idle` and
// `/session/{id}/prompt_async` were read from the installed SDK's types; the
// tests drive this with a fake client. Until a live run shows it (the gh#494
// standard), `parity.yaml` declares this surface `partial` on OpenCode.
import { execFile } from "node:child_process";

export type FrAnswer = { code: number | null; stdout: string };

export type IdleHandlerOptions = {
  client: unknown;
  directory: string;
  /** Test seam. Default: `fr run check --idle --format json` in `cwd`. */
  runFr?: (cwd: string) => Promise<FrAnswer>;
  timeoutMs?: number;
};

const DEFAULT_TIMEOUT_MS = 20_000;

function defaultRunFr(timeoutMs: number): (cwd: string) => Promise<FrAnswer> {
  return (cwd) =>
    new Promise((resolve) => {
      execFile(
        "fr",
        ["run", "check", "--idle", "--format", "json"],
        { cwd, timeout: timeoutMs, killSignal: "SIGKILL", windowsHide: true },
        (error, stdout) => {
          // `error.code` is the exit status for a process that ran and exited
          // non-zero, a STRING ("ENOENT") when it never ran, and absent when it
          // was killed. Only a number is an exit status.
          const raw = error ? (error as { code?: unknown }).code : 0;
          resolve({ code: typeof raw === "number" ? raw : null, stdout: String(stdout ?? "") });
        }
      );
    });
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
  get: (req: { path: { id: string }; query?: { directory?: string } }) => Promise<unknown>;
  promptAsync: (req: {
    path: { id: string };
    body: { parts: { type: "text"; text: string }[] };
    query?: { directory?: string };
  }) => Promise<unknown>;
};

function sessionApi(client: unknown): SessionApi | undefined {
  const session = (client as { session?: Partial<SessionApi> } | null | undefined)?.session;
  if (!session || typeof session.get !== "function" || typeof session.promptAsync !== "function") {
    return undefined;
  }
  return session as SessionApi;
}

/** True only when the lookup SUCCEEDED and named no parent. */
async function isTopLevel(api: SessionApi, id: string, directory: string): Promise<boolean> {
  const response = (await api.get({ path: { id }, query: { directory } })) as
    | { data?: { parentID?: unknown } | null; error?: unknown }
    | null
    | undefined;
  if (!response || response.error || !response.data) return false;
  return response.data.parentID === undefined || response.data.parentID === null;
}

export function createIdleHandler(options: IdleHandlerOptions) {
  const runFr = options.runFr ?? defaultRunFr(options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const actedOn = new Map<string, string>();

  return async (input: { event?: { type?: unknown; properties?: unknown } }): Promise<void> => {
    try {
      const event = input?.event;
      if (!event || event.type !== "session.idle") return;
      const sessionID = (event.properties as { sessionID?: unknown } | undefined)?.sessionID;
      if (typeof sessionID !== "string" || sessionID === "") return;

      const api = sessionApi(options.client);
      if (!api) return;
      if (!(await isTopLevel(api, sessionID, options.directory))) return;

      const verdict = parseVerdict(await runFr(options.directory));
      if (!verdict) return;

      if (actedOn.get(sessionID) === verdict.position) return;
      actedOn.set(sessionID, verdict.position);

      await api.promptAsync({
        path: { id: sessionID },
        query: { directory: options.directory },
        body: {
          parts: [
            {
              type: "text",
              text:
                `fr run ${verdict.run} is idle — ${verdict.detail} (gh#518). Nothing is ` +
                `blocking it: run \`${verdict.nextCommand}\` now and act on what it prints — ` +
                "a dispatch brief means dispatch that unit, then report. If you stopped on " +
                "purpose (the operator asked, or you are waiting on something fr cannot " +
                "see), say so and stop: this nudge is sent once per run position.",
            },
          ],
        },
      });
    } catch {
      // Fail open, always. See the header.
    }
  };
}
