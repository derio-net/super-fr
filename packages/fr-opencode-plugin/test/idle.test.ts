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
// WHAT THIS FILE DOES NOT PROVE: that a prompt a plugin sends on `session.idle`
// actually executes in a live OpenCode session. Everything here drives the
// handler with a fake client. That needs a live run (the gh#494 standard), and
// until one exists the parity row for this surface stays `partial`.
import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { chmodSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";

import { createIdleHandler, SHARED_ACTED_ON, type FrAnswer } from "../src/idle";
import { FrIsolationRequired } from "../src/index";

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

type Sent = { path: { id: string }; body: { parts: { type: string; text: string }[] }; query?: { directory?: string } };

function fakeClient(
  opts: { parentID?: string; getThrows?: boolean; promptThrows?: boolean; getReturns?: unknown } = {}
) {
  const sent: Sent[] = [];
  const attempted: string[] = [];
  const client = {
    session: {
      get: async (_: unknown) => {
        if (opts.getThrows) throw new Error("boom");
        if ("getReturns" in opts) return opts.getReturns;
        return { data: { id: "ses_1", parentID: opts.parentID } };
      },
      promptAsync: async (req: Sent) => {
        attempted.push(req.path.id);
        if (opts.promptThrows) throw new Error("boom");
        sent.push(req);
        return { data: undefined };
      },
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
  ({ event: { type: "session.idle", properties: { sessionID } } }) as never;

const ok = (body: unknown, code: number | null = 3): FrAnswer => ({
  code,
  stdout: typeof body === "string" ? body : JSON.stringify(body),
});

describe("idle guard (OpenCode): continues an idle run", () => {
  test("on session.idle it asks fr in the session's directory and sends the next command back in", async () => {
    const { client, sent } = fakeClient();
    const { runFr, calls } = answers(ok(IDLE));
    const handler = createIdleHandler({ client, directory: "/work/tree", runFr });

    await handler(idleEvent());

    expect(calls).toEqual(["/work/tree"]);
    expect(sent).toHaveLength(1);
    expect(sent[0]!.path).toEqual({ id: "ses_1" });
    expect(sent[0]!.query).toEqual({ directory: "/work/tree" });
    expect(sent[0]!.body.parts).toHaveLength(1);
    expect(sent[0]!.body.parts[0]!.type).toBe("text");
    expect(sent[0]!.body.parts[0]!.text).toContain("fr run advance r1");
    // fr's own words, not the plugin's: the plugin holds no opinion about runs.
    expect(sent[0]!.body.parts[0]!.text).toContain(IDLE.detail);
  });

  test("ignores every other event", async () => {
    const { client, sent } = fakeClient();
    const { runFr, calls } = answers(ok(IDLE));
    const handler = createIdleHandler({ client, directory: "/w", runFr });

    await handler({ event: { type: "session.updated", properties: { sessionID: "ses_1" } } } as never);
    await handler({ event: { type: "message.updated", properties: {} } } as never);

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
      const handler = createIdleHandler({ client, directory: "/w", runFr });

      await expect(handler(idleEvent())).resolves.toBeUndefined();

      expect(calls).toHaveLength(1); // fr WAS asked — this is not silence by never looking
      expect(sent).toEqual([]);
    });
  }

  test("silent for a CHILD session: a subagent going idle is not the run's owner stalling", async () => {
    const { client, sent } = fakeClient({ parentID: "ses_parent" });
    const { runFr, calls } = answers(ok(IDLE));
    const handler = createIdleHandler({ client, directory: "/w", runFr });

    await handler(idleEvent());

    expect(calls).toEqual([]);
    expect(sent).toEqual([]);
  });

  test("silent when the session cannot be looked up — unknown is not 'top-level'", async () => {
    const { client, sent } = fakeClient({ getThrows: true });
    const { runFr } = answers(ok(IDLE));
    const handler = createIdleHandler({ client, directory: "/w", runFr });

    await expect(handler(idleEvent())).resolves.toBeUndefined();

    expect(sent).toEqual([]);
  });

  // The SDK client does not throw by default: a failed lookup comes back as
  // `{ error }` with no `data`. Found by mutation — the throwing case alone left
  // "unknown means top-level" unkilled, because the catch-all silenced it.
  for (const [label, getReturns] of [
    ["an { error } response", { error: { name: "NotFoundError" } }],
    ["a response with no data", {}],
    ["null", null],
  ] as const) {
    test(`silent when the session lookup comes back as ${label}`, async () => {
      const { client, sent } = fakeClient({ getReturns });
      const { runFr, calls } = answers(ok(IDLE));
      const handler = createIdleHandler({ client, directory: "/w", runFr });

      await expect(handler(idleEvent())).resolves.toBeUndefined();

      expect(calls).toEqual([]);
      expect(sent).toEqual([]);
    });
  }

  test("silent on an event with no usable session id", async () => {
    const { client, sent } = fakeClient();
    const { runFr, calls } = answers(ok(IDLE));
    const handler = createIdleHandler({ client, directory: "/w", runFr });

    // (not `idleEvent(undefined)` — a default parameter turns that back into "ses_1")
    await handler({ event: { type: "session.idle", properties: {} } } as never);
    await handler(idleEvent(null));
    await handler(idleEvent(7));
    await handler(idleEvent(""));
    await handler({ event: { type: "session.idle" } } as never);
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
    const handler = createIdleHandler({ client, directory: "/w", runFr });

    await expect(handler(idleEvent())).resolves.toBeUndefined();
    expect(sent).toEqual([]);
  });

  test("when sending the prompt throws", async () => {
    const { client } = fakeClient({ promptThrows: true });
    const { runFr } = answers(ok(IDLE));
    const handler = createIdleHandler({ client, directory: "/w", runFr });

    await expect(handler(idleEvent())).resolves.toBeUndefined();
  });

  test("when the client is not what it should be", async () => {
    const { runFr } = answers(ok(IDLE));
    for (const client of [undefined, null, {}, { session: {} }, { session: { get: 1, promptAsync: 2 } }]) {
      const handler = createIdleHandler({ client, directory: "/w", runFr });
      await expect(handler(idleEvent())).resolves.toBeUndefined();
    }
  });
});

describe("idle guard (OpenCode): at most once per run position", () => {
  test("a second idle at the same position is let through", async () => {
    const { client, sent } = fakeClient();
    const { runFr, calls } = answers(ok(IDLE));
    const handler = createIdleHandler({ client, directory: "/w", runFr });

    await handler(idleEvent());
    await handler(idleEvent());
    await handler(idleEvent());

    expect(calls).toHaveLength(3);
    expect(sent).toHaveLength(1);
  });

  test("it acts again once the position has moved", async () => {
    const { client, sent } = fakeClient();
    const { runFr } = answers(ok(IDLE), ok(IDLE), ok({ ...IDLE, position: "fedcba9876543210" }));
    const handler = createIdleHandler({ client, directory: "/w", runFr });

    await handler(idleEvent());
    await handler(idleEvent());
    await handler(idleEvent());

    expect(sent).toHaveLength(2);
  });

  test("one session's memory is not another's", async () => {
    const { client, sent } = fakeClient();
    const { runFr } = answers(ok(IDLE));
    const handler = createIdleHandler({ client, directory: "/w", runFr });

    await handler(idleEvent("ses_1"));
    await handler(idleEvent("ses_2"));
    await handler(idleEvent("ses_1"));

    expect(sent.map((s) => s.path.id)).toEqual(["ses_1", "ses_2"]);
  });

  test("a prompt that failed to send is still remembered — a broken endpoint must not become a retry loop", async () => {
    const { client, attempted } = fakeClient({ promptThrows: true });
    const { runFr, calls } = answers(ok(IDLE));
    const handler = createIdleHandler({ client, directory: "/w", runFr });

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

  async function plugin(client: unknown) {
    return FrIsolationRequired({
      project: undefined as never,
      client: client as never,
      $: undefined as never,
      directory: dir,
      worktree: dir,
    });
  }

  // gh#563: install.sh delivers a GLOBAL copy of this plugin, and a repo that
  // also loads it project-locally (super-fr itself, via .opencode/plugins/,
  // or a consumer's opencode.json) gets two instances in one OpenCode
  // process. The edit gate doubling is harmless; the idle nudge doubling is
  // not — each instance would send its own "run is idle" prompt.
  test("two loaded copies send ONE nudge per run position, not two", async () => {
    stubFr(`printf '%s\\n' '${JSON.stringify(IDLE)}'\nexit 3`);
    const { client, sent } = fakeClient();
    const project = await plugin(client);
    const global = await plugin(client);

    await project.event!(idleEvent());
    await global.event!(idleEvent());

    expect(sent).toHaveLength(1);
  });

  test("the plugin exposes an `event` hook beside tool.execute.before", async () => {
    const hooks = await plugin(fakeClient().client);
    expect(typeof hooks.event).toBe("function");
    expect(typeof hooks["tool.execute.before"]).toBe("function");
  });

  test("exit 3 + idle JSON from the process → the next command is sent", async () => {
    stubFr(`printf '%s\\n' '${JSON.stringify(IDLE)}'\nexit 3`);
    const { client, sent } = fakeClient();
    const hooks = await plugin(client);

    await hooks.event!(idleEvent());

    expect(readFileSync(join(dir, "fr.log"), "utf8")).toBe(`${dir}|run check --idle --format json\n`);
    expect(sent).toHaveLength(1);
    expect(sent[0]!.body.parts[0]!.text).toContain("fr run advance r1");
  });

  test("exit 2 from the process → silent", async () => {
    stubFr(`echo 'fr: artifacts must be migrated' >&2\nexit 2`);
    const { client, sent } = fakeClient();
    const hooks = await plugin(client);

    await expect(hooks.event!(idleEvent())).resolves.toBeUndefined();
    expect(sent).toEqual([]);
  });

  test("no fr on PATH at all → silent", async () => {
    process.env.PATH = dir; // nothing in it
    const { client, sent } = fakeClient();
    const hooks = await plugin(client);

    await expect(hooks.event!(idleEvent())).resolves.toBeUndefined();
    expect(sent).toEqual([]);
  });

  test("a hung fr is abandoned, not waited on", async () => {
    stubFr("exec sleep 30");
    const { client, sent } = fakeClient();
    const handler = createIdleHandler({ client, directory: dir, timeoutMs: 500 });

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
