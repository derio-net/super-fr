// The child-session claim (gh#530): on a CHILD session's first tool call the
// plugin hands fr the child's own id and the agent OpenCode runs it as, once,
// through `fr run claim --open-unit`. WHICH unit that is stays fr's verdict.
//
// WHAT THIS FILE DOES NOT PROVE: that the claim lands in a live OpenCode
// session. The session shape was read off a live 1.18 server; everything here
// drives the handler with a fake client, so the parity cell stays `partial`.
import { describe, expect, test } from "bun:test";

import { createClaimHandler, SHARED_CLAIMED, type ClaimAnswer } from "../src/claim";
import { FrIsolationRequired } from "../src/index";

const CHILD = {
  id: "ses_child",
  parentID: "ses_root",
  agent: "fr-phase-executor-mechanical",
  model: { providerID: "github-copilot", id: "gpt-5.6-terra", variant: "max" },
};

function fakeClient(opts: { data?: unknown; getThrows?: boolean; error?: unknown } = {}) {
  const looked: string[] = [];
  const client = {
    session: {
      get: async (req: { path: { id: string } }) => {
        looked.push(req.path.id);
        if (opts.getThrows) throw new Error("boom");
        if (opts.error) return { error: opts.error };
        return { data: "data" in opts ? opts.data : CHILD };
      },
    },
  };
  return { client, looked };
}

function fr(answer: ClaimAnswer | Error = { code: 0 }) {
  const calls: { cwd: string; args: string[] }[] = [];
  const runFr = async (cwd: string, args: string[]): Promise<ClaimAnswer> => {
    calls.push({ cwd, args });
    if (answer instanceof Error) throw answer;
    return answer;
  };
  return { runFr, calls };
}

describe("child claim (OpenCode): names the holder while it holds", () => {
  test("a child's first tool call claims its open unit with its id, agent and model", async () => {
    const { client } = fakeClient();
    const { runFr, calls } = fr();
    const handler = createClaimHandler({ client, directory: "/work/tree", runFr });

    await handler({ sessionID: "ses_child" });

    expect(calls).toEqual([
      {
        cwd: "/work/tree",
        args: [
          "run",
          "claim",
          "--open-unit",
          "--agent",
          "ses_child",
          "--agent-type",
          "fr-phase-executor-mechanical",
          "--harness",
          "opencode",
          "--model",
          "github-copilot/gpt-5.6-terra",
        ],
      },
    ]);
  });

  test("once per session: later tool calls do not look up or claim again", async () => {
    const { client, looked } = fakeClient();
    const { runFr, calls } = fr();
    const handler = createClaimHandler({ client, directory: "/w", runFr });

    await handler({ sessionID: "ses_child" });
    await handler({ sessionID: "ses_child" });

    expect(looked).toEqual(["ses_child"]);
    expect(calls).toHaveLength(1);
  });

  test("a refused claim (exit 2) is not retried", async () => {
    const { client } = fakeClient();
    const { runFr, calls } = fr({ code: 2 });
    const handler = createClaimHandler({ client, directory: "/w", runFr });

    await handler({ sessionID: "ses_child" });
    await handler({ sessionID: "ses_child" });

    expect(calls).toHaveLength(1);
  });

  test("a model the session does not name is left to fr", async () => {
    const { client } = fakeClient({ data: { ...CHILD, model: undefined } });
    const { runFr, calls } = fr();

    await createClaimHandler({ client, directory: "/w", runFr })({ sessionID: "ses_child" });

    expect(calls[0]!.args).not.toContain("--model");
  });

  test("two loaded copies claim ONCE per session, not twice", async () => {
    const slot = globalThis as Record<symbol, unknown>;
    delete slot[SHARED_CLAIMED];
    const { client } = fakeClient();
    const { runFr, calls } = fr();
    const { sharedClaimed } = await import("../src/claim");

    await createClaimHandler({ client, directory: "/w", runFr, claimed: sharedClaimed() })({
      sessionID: "ses_child",
    });
    await createClaimHandler({ client, directory: "/w", runFr, claimed: sharedClaimed() })({
      sessionID: "ses_child",
    });

    expect(calls).toHaveLength(1);
    delete slot[SHARED_CLAIMED];
  });
});

describe("child claim (OpenCode): silent", () => {
  const silentCases: [string, Parameters<typeof fakeClient>[0]][] = [
    ["for a top-level session", { data: { ...CHILD, parentID: undefined } }],
    ["for a child that names no agent", { data: { ...CHILD, agent: "" } }],
    ["when the lookup fails", { error: { name: "NotFound" } }],
    ["when the lookup returns nothing", { data: null }],
  ];
  for (const [name, opts] of silentCases) {
    test(name, async () => {
      const { client } = fakeClient(opts);
      const { runFr, calls } = fr();

      await createClaimHandler({ client, directory: "/w", runFr })({ sessionID: "ses_child" });

      expect(calls).toHaveLength(0);
    });
  }

  test("when there is no session id", async () => {
    const { client, looked } = fakeClient();
    const { runFr, calls } = fr();

    await createClaimHandler({ client, directory: "/w", runFr })({});

    expect(looked).toHaveLength(0);
    expect(calls).toHaveLength(0);
  });

  test("when the lookup throws", async () => {
    const { client } = fakeClient({ getThrows: true });
    const { runFr } = fr();

    await expect(
      createClaimHandler({ client, directory: "/w", runFr })({ sessionID: "ses_child" })
    ).resolves.toBeUndefined();
  });

  test("when running fr throws", async () => {
    const { client } = fakeClient();
    const { runFr } = fr(new Error("ENOENT"));

    await expect(
      createClaimHandler({ client, directory: "/w", runFr })({ sessionID: "ses_child" })
    ).resolves.toBeUndefined();
  });

  test("when the client is not what it should be", async () => {
    const { runFr, calls } = fr();

    await createClaimHandler({ client: null, directory: "/w", runFr })({ sessionID: "ses_child" });

    expect(calls).toHaveLength(0);
  });
});

describe("child claim (OpenCode): wired into the plugin", () => {
  test("tool.execute.before looks the calling session up before the edit gate", async () => {
    const slot = globalThis as Record<symbol, unknown>;
    delete slot[SHARED_CLAIMED];
    const { client, looked } = fakeClient({ data: { ...CHILD, parentID: undefined } });
    const plugin = await FrIsolationRequired({
      project: {},
      client,
      $: {},
      directory: "/nonexistent",
      worktree: "/nonexistent",
    });

    await plugin["tool.execute.before"]({ tool: "read", sessionID: "ses_wired" }, { args: {} });

    expect(looked).toEqual(["ses_wired"]);
    delete slot[SHARED_CLAIMED];
  });

  test("claim.ts never names a step, item or unit state — the verdict is fr's", async () => {
    const source = await Bun.file(new URL("../src/claim.ts", import.meta.url)).text();
    const code = source
      .split("\n")
      .filter((line) => !line.trimStart().startsWith("//"))
      .join("\n");
    for (const word of ["--step", "--item", "phase/", "running", "implement"]) {
      expect(code).not.toContain(word);
    }
  });
});
