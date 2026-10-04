// The run-session export (spec 2026-10-02-opencode-observe-2 §B): before every
// `bash` tool call OpenCode fires `shell.env` with the calling session's id,
// and the plugin hands it to fr as FR_OPENCODE_SESSION_ID.
//
// WHAT THIS FILE DOES NOT PROVE: that the hook fires in a live OpenCode
// session. Its signature was read off the 1.18.33 binary and the
// `@opencode-ai/plugin` 1.17.15 typing; everything here drives the handler
// directly, so the parity cell stays `partial`.
import { describe, expect, test } from "bun:test";

import { FrIsolationRequired } from "../src/index";
import { createShellEnvHandler } from "../src/session";

describe("shell.env session export", () => {
  test("sets FR_OPENCODE_SESSION_ID to the calling session", async () => {
    const output = { env: { KEEP: "1" } as Record<string, string> };
    await createShellEnvHandler()({ cwd: "/work/example", sessionID: "ses_run", callID: "c1" }, output);
    expect(output.env).toEqual({ KEEP: "1", FR_OPENCODE_SESSION_ID: "ses_run" });
  });

  test("leaves env untouched without a session id", async () => {
    for (const input of [{ cwd: "/w" }, { cwd: "/w", sessionID: "" }]) {
      const output = { env: { KEEP: "1" } as Record<string, string> };
      await createShellEnvHandler()(input, output);
      expect(output.env).toEqual({ KEEP: "1" });
    }
  });

  test("creates the env object when the output carries none (review p1-r3)", async () => {
    for (const output of [{} as { env?: Record<string, string> }, { env: undefined }]) {
      await createShellEnvHandler()({ cwd: "/w", sessionID: "ses_run" }, output as never);
      expect(output.env).toEqual({ FR_OPENCODE_SESSION_ID: "ses_run" });
    }
  });

  test("never throws", async () => {
    await createShellEnvHandler()({ cwd: "/w", sessionID: "ses_run" }, undefined as never);
    const frozen = { env: Object.freeze({}) as Record<string, string> };
    await createShellEnvHandler()({ cwd: "/w", sessionID: "ses_run" }, frozen);
    expect(frozen.env).toEqual({});
  });

  test("is registered on the plugin as shell.env", async () => {
    const hooks = (await FrIsolationRequired({
      project: {},
      client: {},
      $: {},
      directory: "/work/example",
      worktree: "/work/example",
    })) as Record<string, unknown>;
    const output = { env: {} as Record<string, string> };
    await (hooks["shell.env"] as (i: unknown, o: unknown) => Promise<void>)(
      { cwd: "/work/example", sessionID: "ses_run" },
      output
    );
    expect(output.env.FR_OPENCODE_SESSION_ID).toBe("ses_run");
  });
});
