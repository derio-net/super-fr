// The run-session export (spec 2026-10-02-opencode-observe-2 §B, ported by
// 2026-10-20-opencode-2-support R7). OpenCode 2's shell `create.before` event
// carries no session id, so the plugin correlates it with the `execute.before`
// of a `shell` tool call by command, and exports FR_OPENCODE_SESSION_ID only on
// ONE unambiguous match.
//
// WHAT THIS FILE DOES NOT PROVE: that `execute.before` precedes `create.before`
// with the same command in a live OpenCode session — that premise is measured
// separately (plan P1.T3.S2); everything here drives the handlers directly.
import { describe, expect, test } from "bun:test";

import { createSessionExport, SESSION_ENV_KEY } from "../src/session";
import { load } from "./fake";

const shellCall = (sessionID: string, command: string) => ({ tool: "shell", sessionID, input: { command } });
const shellEvent = (command: string) => ({ command, cwd: "/w", env: { KEEP: "1" } as Record<string, string> });

function clock(start = 1_000) {
  let t = start;
  return { now: () => t, advance: (ms: number) => (t += ms) };
}

describe("create.before session export", () => {
  test("a single pending match exports the calling session", async () => {
    const exp = createSessionExport();
    exp.record(shellCall("ses_run", "git status"));
    const event = shellEvent("git status");
    await exp.apply(event);
    expect(event.env).toEqual({ KEEP: "1", [SESSION_ENV_KEY]: "ses_run" });
    expect(exp.size()).toBe(0);
  });

  test("the 1.x tool name `bash` is recorded too", async () => {
    const exp = createSessionExport();
    exp.record({ tool: "bash", sessionID: "ses_run", input: { command: "ls" } });
    const event = shellEvent("ls");
    await exp.apply(event);
    expect(event.env[SESSION_ENV_KEY]).toBe("ses_run");
  });

  test("two sessions with the same command: nothing is exported", async () => {
    const exp = createSessionExport();
    exp.record(shellCall("ses_a", "git status"));
    exp.record(shellCall("ses_b", "git status"));
    const event = shellEvent("git status");
    await exp.apply(event);
    expect(event.env).toEqual({ KEEP: "1" });
    // The ambiguous entries are consumed, not left to match a later command.
    expect(exp.size()).toBe(0);
  });

  test("one session issuing the same command twice is still ambiguous", async () => {
    const exp = createSessionExport();
    exp.record(shellCall("ses_a", "make"));
    exp.record(shellCall("ses_a", "make"));
    const event = shellEvent("make");
    await exp.apply(event);
    expect(event.env).toEqual({ KEEP: "1" });
  });

  test("an unmatched command exports nothing and keeps the pending call", async () => {
    const exp = createSessionExport();
    exp.record(shellCall("ses_run", "git status"));
    const event = shellEvent("git log");
    await exp.apply(event);
    expect(event.env).toEqual({ KEEP: "1" });
    expect(exp.size()).toBe(1);
  });

  test("an expired pending call exports nothing", async () => {
    const c = clock();
    const exp = createSessionExport({ ttlMs: 1_000, now: c.now });
    exp.record(shellCall("ses_run", "git status"));
    c.advance(1_001);
    const event = shellEvent("git status");
    await exp.apply(event);
    expect(event.env).toEqual({ KEEP: "1" });
    expect(exp.size()).toBe(0);
  });

  test("non-shell tools, missing sessions and missing commands are not recorded", () => {
    const exp = createSessionExport();
    exp.record({ tool: "read", sessionID: "s", input: { command: "x" } });
    exp.record({ tool: "shell", sessionID: "", input: { command: "x" } });
    exp.record({ tool: "shell", input: { command: "x" } });
    exp.record({ tool: "shell", sessionID: "s", input: {} });
    exp.record({ tool: "shell", sessionID: "s" });
    exp.record(undefined as never);
    expect(exp.size()).toBe(0);
  });

  test("creates a missing env object and never throws", async () => {
    const exp = createSessionExport();
    exp.record(shellCall("ses_run", "x"));
    const bare = { command: "x" } as { command: string; env?: Record<string, string> };
    await exp.apply(bare);
    expect(bare.env).toEqual({ [SESSION_ENV_KEY]: "ses_run" });
    await exp.apply(undefined as never);
    exp.record(shellCall("ses_run", "y"));
    const frozen = { command: "y", env: Object.freeze({}) as Record<string, string> };
    await exp.apply(frozen);
    expect(frozen.env).toEqual({});
  });

  test("wired into the plugin: execute.before records, create.before exports", async () => {
    const { executeBefore, createBefore } = await load();
    await executeBefore(shellCall("ses_wired", "echo hi"));
    const event = { ...shellEvent("echo hi"), timeout: 1, shell: "/bin/zsh" };
    await createBefore(event);
    expect(event.env[SESSION_ENV_KEY]).toBe("ses_wired");
  });
});
