// The OpenCode half of the idle guard (spec 2026-09-20-unit-record-unification
// §4.G; gh#518). OpenCode CANNOT refuse a stop. It can CONTINUE a session: on
// `session.idle` the plugin asks fr whether the run is idle and, if it is,
// sends the next command back in (`/session/{id}/prompt_async`).
//
// Same contract as the Claude Code hook (plugins/super-fr/hooks/
// fr-run-idle-guard.sh): the verdict is `fr run check --idle`'s and nobody
// else's; silent on anything but a clean parsed "idle"; at most once per run
// position; and it NEVER throws — an exception out of an `event` hook is the
// plugin breaking the session it was meant to help.
//
// WHICH event ends a turn moved (gh#1231): 2.0.32 shipped `session.idle`,
// 2.1.x removed it for `session.execution.succeeded`. Both are covered here,
// because a handler that knows only one is inert and silent on the other.
//
// WHAT THIS FILE DOES NOT PROVE: that a prompt a plugin sends when a turn ends
// actually EXECUTES in a live OpenCode session. Everything here drives the
// handler with a fake client. That needs a live run (the gh#494 standard), and
// until one exists the parity row for this surface stays `partial`.
import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { chmodSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";

import { createIdleHandler, SHARED_ACTED_ON, type FrAnswer } from "../src/idle";
import { load } from "./fake";

const IDLE = {
  idle: true,
  reason: "idle",
  detail: "implement is advanceable and nobody is working on it",
  run: "r1",
  cursor: "implement",
  position: "0123456789abcdef",
  next_command: "fr run advance r1",
  stalled: [],
};

type Sent = { sessionID: string; text: string };

function fakeClient(
  opts: { parentID?: string; getThrows?: boolean; promptThrows?: boolean; getReturns?: unknown } = {}
) {
  const sent: Sent[] = [];
  const attempted: string[] = [];
  // OpenCode 2's `ctx.session`: `get({sessionID})` resolves to the info itself
  // (throwing on a failed lookup); `prompt({sessionID, text})` sends.
  const client = {
    get: async (req: { sessionID: string }) => {
      if (opts.getThrows) throw new Error("boom");
      if ("getReturns" in opts) return opts.getReturns;
      return { id: req.sessionID, parentID: opts.parentID };
    },
    prompt: async (req: Sent) => {
      attempted.push(req.sessionID);
      if (opts.promptThrows) throw new Error("boom");
      sent.push(req);
      return {};
    },
  };
  return { client, sent, attempted };
}

function answers(...queue: (FrAnswer | Error)[]) {
  const calls: string[] = [];
  const runFr = async (cwd: string): Promise<FrAnswer> => {
    calls.push(cwd);
    const next = queue.length > 1 ? queue.shift()! : queue[0]!;
    if (next instanceof Error) throw next;
    return next;
  };
  return { runFr, calls };
}

const idleEvent = (sessionID: unknown = "ses_1") =>
  ({ type: "session.idle", data: { sessionID } }) as never;

/** 2.1.x's turn-end event, same `data.sessionID` and `durable: true`. */
const succeededEvent = (sessionID: unknown = "ses_1") =>
  ({ type: "session.execution.succeeded", data: { sessionID } }) as never;

const ok = (body: unknown, code: number | null = 3): FrAnswer => ({
  code,
  stdout: typeof body === "string" ? body : JSON.stringify(body),
});

describe("idle guard (OpenCode): continues an idle run", () => {
  test("on session.idle it asks fr in the session's directory and sends the next command back in", async () => {
    const { client, sent } = fakeClient();
    const { runFr, calls } = answers(ok(IDLE));
    const handler = createIdleHandler({ session: client, directory: "/work/tree", runFr });

    await handler(idleEvent());

    expect(calls).toEqual(["/work/tree"]);
    expect(sent).toHaveLength(1);
    // V2's prompt takes the session and the text; the directory is the
    // plugin's location, so there is no per-call directory to assert.
    expect(sent[0]!.sessionID).toBe("ses_1");
    expect(typeof sent[0]!.text).toBe("string");
    expect(sent[0]!.text).toContain("fr run advance r1");
    // fr's own words, not the plugin's: the plugin holds no opinion about runs.
    expect(sent[0]!.text).toContain(IDLE.detail);
  });

  test("on session.execution.succeeded (2.1.x) it does exactly what session.idle did", async () => {
    const { client, sent } = fakeClient();
    const { runFr, calls } = answers(ok(IDLE));
    const handler = createIdleHandler({ session: client, directory: "/work/tree", runFr });

    await handler(succeededEvent());

    expect(calls).toEqual(["/work/tree"]);
    expect(sent).toHaveLength(1);
    expect(sent[0]!.sessionID).toBe("ses_1");
    expect(sent[0]!.text).toContain("fr run advance r1");
  });

  test("a replayed session.execution.succeeded at the same position does not nudge twice", async () => {
    const { client, sent } = fakeClient();
    const { runFr, calls } = answers(ok(IDLE));
    const handler = createIdleHandler({ session: client, directory: "/w", runFr });

    await handler(succeededEvent());
    await handler(succeededEvent()); // durable: a reconnect can replay it
    await handler(idleEvent()); // and the old name on the same position

    expect(calls).toHaveLength(3); // fr is asked every time — the MEMORY is the brake
    expect(sent).toHaveLength(1);
  });

  test("ignores every other event", async () => {
    const { client, sent } = fakeClient();
    const { runFr, calls } = answers(ok(IDLE));
    const handler = createIdleHandler({ session: client, directory: "/w", runFr });

    for (const type of [
      "session.updated",
      "message.updated",
      "session.execution.started", // the same family as success — but not an end
      "session.execution.failed", // a failure is the model's to report, not a nudge
      "session.status", // 2.0.x's status carrier, whose idle arrives as session.idle
      "session.text.ended",
    ]) {
      await handler({ type, data: { sessionID: "ses_1" } } as never);
    }

    expect(calls).toEqual([]);
    expect(sent).toEqual([]);
  });
});

describe("idle guard (OpenCode): silent otherwise", () => {
  const SILENT: [string, FrAnswer][] = [
    ["a legitimate stop (exit 0, idle: false)", ok({ ...IDLE, idle: false, reason: "held", next_command: null }, 0)],
    ["no run at all", ok({ idle: false, reason: "no-run", runs: [] }, 0)],
    ["fr errors", ok("", 1)],
    ["fr refuses (the migration gate; an fr too old for --idle)", ok("", 2)],
    ["fr was killed or timed out", ok("", null)],
    ["exit 3 with no output", ok("", 3)],
    ["exit 3 with garbage", ok("not json {", 3)],
    ["exit 3 with JSON that is not an object", ok([1, 2], 3)],
    ["exit 3 with a complete answer that says NOT idle", ok({ ...IDLE, idle: false }, 3)],
    ["exit 3 with an idle that is the STRING true", ok({ ...IDLE, idle: "true" }, 3)],
    ["an idle answer under exit 0", ok(IDLE, 0)],
    ["an idle answer with no next command", ok({ ...IDLE, next_command: null }, 3)],
    ["an idle answer with no position", ok({ ...IDLE, position: undefined }, 3)],
    ["an idle answer whose position is not a string", ok({ ...IDLE, position: 7 }, 3)],
  ];
  for (const [label, answer] of SILENT) {
    test(`silent: ${label}`, async () => {
      const { client, sent } = fakeClient();
      const { runFr, calls } = answers(answer);
      const handler = createIdleHandler({ session: client, directory: "/w", runFr });

      await expect(handler(idleEvent())).resolves.toBeUndefined();

      expect(calls).toHaveLength(1); // fr WAS asked — this is not silence by never looking
      expect(sent).toEqual([]);
    });
  }

  test("silent for a CHILD session: a subagent going idle is not the run's owner stalling", async () => {
    const { client, sent } = fakeClient({ parentID: "ses_parent" });
    const { runFr, calls } = answers(ok(IDLE));
    const handler = createIdleHandler({ session: client, directory: "/w", runFr });

    await handler(idleEvent());

    expect(calls).toEqual([]);
    expect(sent).toEqual([]);
  });

  test("silent when the session cannot be looked up — unknown is not 'top-level'", async () => {
    const { client, sent } = fakeClient({ getThrows: true });
    const { runFr } = answers(ok(IDLE));
    const handler = createIdleHandler({ session: client, directory: "/w", runFr });

    await expect(handler(idleEvent())).resolves.toBeUndefined();

    expect(sent).toEqual([]);
  });

  // OpenCode 2's session.get throws on a failed lookup, but anything that is not
  // the session asked for is still unknown, never top-level. Found by mutation
  // (1.x) — the throwing case alone left "unknown means top-level" unkilled,
  // because the catch-all silenced it.
  for (const [label, getReturns] of [
    ["an { error } response", { error: { name: "NotFoundError" } }],
    ["a response with no data", {}],
    ["a different session", { id: "ses_other" }],
    ["null", null],
  ] as const) {
    test(`silent when the session lookup comes back as ${label}`, async () => {
      const { client, sent } = fakeClient({ getReturns });
      const { runFr, calls } = answers(ok(IDLE));
      const handler = createIdleHandler({ session: client, directory: "/w", runFr });

      await expect(handler(idleEvent())).resolves.toBeUndefined();

      expect(calls).toEqual([]);
      expect(sent).toEqual([]);
    });
  }

  test("silent on an event with no usable session id", async () => {
    const { client, sent } = fakeClient();
    const { runFr, calls } = answers(ok(IDLE));
    const handler = createIdleHandler({ session: client, directory: "/w", runFr });

    // (not `idleEvent(undefined)` — a default parameter turns that back into "ses_1")
    await handler({ type: "session.idle", data: {} } as never);
    await handler(idleEvent(null));
    await handler(idleEvent(7));
    await handler(idleEvent(""));
    await handler({ type: "session.idle" } as never);
    await handler({} as never);
    await handler(undefined as never);

    expect(calls).toEqual([]);
    expect(sent).toEqual([]);
  });
});

describe("idle guard (OpenCode): never throws", () => {
  test("when running fr throws", async () => {
    const { client, sent } = fakeClient();
    const { runFr } = answers(new Error("spawn fr ENOENT"));
    const handler = createIdleHandler({ session: client, directory: "/w", runFr });

    await expect(handler(idleEvent())).resolves.toBeUndefined();
    expect(sent).toEqual([]);
  });

  test("when sending the prompt throws", async () => {
    const { client } = fakeClient({ promptThrows: true });
    const { runFr } = answers(ok(IDLE));
    const handler = createIdleHandler({ session: client, directory: "/w", runFr });

    await expect(handler(idleEvent())).resolves.toBeUndefined();
  });

  test("when the client is not what it should be", async () => {
    const { runFr } = answers(ok(IDLE));
    for (const client of [undefined, null, {}, { get: 1, prompt: 2 }, { get: async () => ({}) }]) {
      const handler = createIdleHandler({ session: client, directory: "/w", runFr });
      await expect(handler(idleEvent())).resolves.toBeUndefined();
    }
  });
});

describe("idle guard (OpenCode): at most once per run position", () => {
  test("a second idle at the same position is let through", async () => {
    const { client, sent } = fakeClient();
    const { runFr, calls } = answers(ok(IDLE));
    const handler = createIdleHandler({ session: client, directory: "/w", runFr });

    await handler(idleEvent());
    await handler(idleEvent());
    await handler(idleEvent());

    expect(calls).toHaveLength(3);
    expect(sent).toHaveLength(1);
  });

  test("it acts again once the position has moved", async () => {
    const { client, sent } = fakeClient();
    const { runFr } = answers(ok(IDLE), ok(IDLE), ok({ ...IDLE, position: "fedcba9876543210" }));
    const handler = createIdleHandler({ session: client, directory: "/w", runFr });

    await handler(idleEvent());
    await handler(idleEvent());
    await handler(idleEvent());

    expect(sent).toHaveLength(2);
  });

  test("one session's memory is not another's", async () => {
    const { client, sent } = fakeClient();
    const { runFr } = answers(ok(IDLE));
    const handler = createIdleHandler({ session: client, directory: "/w", runFr });

    await handler(idleEvent("ses_1"));
    await handler(idleEvent("ses_2"));
    await handler(idleEvent("ses_1"));

    expect(sent.map((s) => s.sessionID)).toEqual(["ses_1", "ses_2"]);
  });

  test("a prompt that failed to send is still remembered — a broken endpoint must not become a retry loop", async () => {
    const { client, attempted } = fakeClient({ promptThrows: true });
    const { runFr, calls } = answers(ok(IDLE));
    const handler = createIdleHandler({ session: client, directory: "/w", runFr });

    await handler(idleEvent());
    await handler(idleEvent());

    expect(calls).toHaveLength(2);
    expect(attempted).toEqual(["ses_1"]);
  });
});

// The default runner and the plugin wiring, against a REAL process: a stub
// `fr` on PATH. (Not the real fr — `uv run pytest` owns that, in
// tests/unit/test_run_idle.py; this package must test without Python.)
describe("idle guard (OpenCode): wired into the plugin, running a real process", () => {
  let dir: string;
  let savedPath: string | undefined;

  function stubFr(body: string): void {
    const stub = join(dir, "fr");
    writeFileSync(stub, `#!/bin/bash\nprintf '%s|%s\\n' "$PWD" "$*" >> "${join(dir, "fr.log")}"\n${body}\n`);
    chmodSync(stub, 0o755);
  }

  beforeEach(() => {
    dir = realpathSync(mkdtempSync(join(tmpdir(), "fr-opencode-idle-")));
    savedPath = process.env.PATH;
    process.env.PATH = `${dir}${delimiter}${savedPath ?? ""}`;
    // The plugin's once-per-position memory is process-wide on purpose (see
    // the double-load test below); each test starts from a clean process.
    delete (globalThis as Record<symbol, unknown>)[SHARED_ACTED_ON];
  });

  afterEach(() => {
    process.env.PATH = savedPath;
    rmSync(dir, { recursive: true, force: true });
  });

  // Loads the plugin on a fake context whose event stream yields `events`, and
  // waits until every one of them has been handled.
  async function plugin(client: unknown, events: unknown[] = []) {
    const loaded = await load({ session: client, directory: dir, events });
    await loaded.drained;
    return loaded;
  }

  // gh#563: install.sh delivers a GLOBAL copy of this plugin, and a repo that
  // also loads it project-locally (super-fr itself, via .opencode/plugins/,
  // or a consumer's opencode.json) gets two instances in one OpenCode
  // process. The edit gate doubling is harmless; the idle nudge doubling is
  // not — each instance would send its own "run is idle" prompt.
  test("two loaded copies send ONE nudge per run position, not two", async () => {
    stubFr(`printf '%s\\n' '${JSON.stringify(IDLE)}'\nexit 3`);
    const { client, sent } = fakeClient();
    await plugin(client, [idleEvent()]);
    await plugin(client, [idleEvent()]);

    expect(sent).toHaveLength(1);
  });

  test("the plugin subscribes to events beside its execute.before hook", async () => {
    const hooks = await plugin(fakeClient().client);
    expect(hooks.subscribed).toHaveLength(1);
    expect(typeof hooks.executeBefore).toBe("function");
  });

  test("exit 3 + idle JSON from the process → the next command is sent", async () => {
    stubFr(`printf '%s\\n' '${JSON.stringify(IDLE)}'\nexit 3`);
    const { client, sent } = fakeClient();
    await plugin(client, [idleEvent()]);

    expect(readFileSync(join(dir, "fr.log"), "utf8")).toBe(`${dir}|run check --idle --format json\n`);
    expect(sent).toHaveLength(1);
    expect(sent[0]!.text).toContain("fr run advance r1");
  });

  test("exit 2 from the process → silent", async () => {
    stubFr(`echo 'fr: artifacts must be migrated' >&2\nexit 2`);
    const { client, sent } = fakeClient();
    await expect(plugin(client, [idleEvent()])).resolves.toBeDefined();
    expect(sent).toEqual([]);
  });

  test("no fr on PATH at all → silent", async () => {
    process.env.PATH = dir; // nothing in it
    const { client, sent } = fakeClient();
    await expect(plugin(client, [idleEvent()])).resolves.toBeDefined();
    expect(sent).toEqual([]);
  });

  test("a hung fr is abandoned, not waited on", async () => {
    stubFr("exec sleep 30");
    const { client, sent } = fakeClient();
    const handler = createIdleHandler({ session: client, directory: dir, timeoutMs: 500 });

    const began = Date.now();
    await expect(handler(idleEvent())).resolves.toBeUndefined();

    expect(Date.now() - began).toBeLessThan(8000);
    expect(sent).toEqual([]);
  });
});

describe("idle guard (OpenCode): the adapter holds no opinion about runs", () => {
  test("idle.ts never names a step or unit state — the predicate is fr's", () => {
    const code = readFileSync(join(import.meta.dir, "..", "src", "idle.ts"), "utf8")
      .split("\n")
      .filter((line) => !line.trim().startsWith("//"))
      .join("\n");
    for (const word of ["pending", "running", "blocked", "attempts", "units", "cursor", "gate"]) {
      expect(code).not.toContain(word);
    }
  });
});
