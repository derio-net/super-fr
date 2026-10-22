// Session bind/unbind (spec 2026-10-20-opencode-2-support R11). The argv for
// each command is compared against the REAL bash hook
// (plugins/super-fr/hooks/fr-session-bind.sh) run with a stub `fr` that records
// its arguments — only `--harness` differs (claude there, opencode here).
import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { spawnSync } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import { bindArgs, createBindHandler, createUnbindHandler, shellCwd } from "../src/bind";

const HOOK = resolve(import.meta.dir, "../../../plugins/super-fr/hooks/fr-session-bind.sh");
let root = "";

beforeAll(() => {
  root = realpathSync(mkdtempSync(join(tmpdir(), "fr-bind-")));
  mkdirSync(join(root, "bin"));
  mkdirSync(join(root, "repo", "sub"), { recursive: true });
  mkdirSync(join(root, "home", "w"), { recursive: true });
  const fr = join(root, "bin", "fr");
  writeFileSync(fr, `#!/bin/sh\nfor a in "$@"; do printf '%s\\n' "$a"; done > "${root}/argv"\n`);
  chmodSync(fr, 0o755);
});

afterAll(() => rmSync(root, { recursive: true, force: true }));

function bashArgv(command: string, cwd: string): string[] | undefined {
  rmSync(join(root, "argv"), { force: true });
  const out = spawnSync("bash", [HOOK], {
    input: JSON.stringify({ session_id: "ses_1", cwd, tool_name: "Bash", tool_input: { command } }),
    env: { ...process.env, HOME: join(root, "home"), PATH: `${join(root, "bin")}:${process.env.PATH}` },
    encoding: "utf-8",
  });
  expect(out.status).toBe(0);
  if (!existsSync(join(root, "argv"))) return undefined;
  return readFileSync(join(root, "argv"), "utf-8").split("\n").filter((l) => l !== "");
}

const COMMANDS = [
  "fr isolation up --branch feat/x",
  "fr isolation exec -- ls",
  "fr isolation down",
  "fr run start fr-goal --branch feat/y",
  "uv run fr run start fr-goal --branch=feat/z",
  "FR_ISOLATION_TARGET=worktree fr isolation up --branch 'feat/q'",
  "cd sub && fr isolation up --branch a --branch b",
  "cd ~/w; fr isolation exec --branch \"w b\" -- ls",
  "cd missing && fr isolation up",
  "echo fr isolation up",
  "fr run advance",
  "fr isolation status",
  "ls\nfr isolation up",
];

describe("bind", () => {
  test.each(COMMANDS)("matches the bash hook's argv for %p", (command) => {
    const cwd = join(root, "repo");
    const bash = bashArgv(command, cwd);
    const ts = bindArgs(command, cwd, "ses_1", join(root, "home"));
    expect(ts?.map((a) => (a === "opencode" ? "claude" : a))).toEqual(bash);
  });

  test("the comparison is not vacuous", () => {
    expect(bashArgv("fr isolation up --branch x", join(root, "repo"))).toContain("attach");
  });

  test("the handler runs exactly that argv for a completed shell call, in its workdir", async () => {
    const calls: { args: string[]; cwd: string }[] = [];
    const handler = createBindHandler({
      session: { get: async () => ({ id: "ses_1" }) },
      directory: root,
      runFr: async (args, cwd) => {
        calls.push({ args, cwd });
        return { code: 0, stdout: "" };
      },
    });
    await handler({ tool: "shell", sessionID: "ses_1", status: "completed", input: { command: "fr isolation up --branch x", workdir: "repo" } });
    await handler({ tool: "shell", sessionID: "ses_1", status: "error", input: { command: "fr isolation up" } });
    await handler({ tool: "skill", sessionID: "ses_1", status: "completed", input: { command: "fr isolation up" } });
    expect(calls).toEqual([
      {
        args: ["isolation", "attach", "--session", "ses_1", "--repo", join(root, "repo"), "--branch", "x", "--harness", "opencode"],
        cwd: join(root, "repo"),
      },
    ]);
  });

  test("a child session never rebinds", async () => {
    let called = false;
    const handler = createBindHandler({
      session: { get: async () => ({ id: "ses_c", parentID: "ses_p" }) },
      directory: root,
      runFr: async () => {
        called = true;
        return { code: 0, stdout: "" };
      },
    });
    await handler({ tool: "shell", sessionID: "ses_c", status: "completed", input: { command: "fr isolation up" } });
    expect(called).toBe(false);
  });

  test("never throws, even when fr does", async () => {
    const handler = createBindHandler({
      session: {},
      directory: root,
      runFr: async () => {
        throw new Error("spawn");
      },
    });
    await expect(
      handler({ tool: "shell", sessionID: "s", status: "completed", input: { command: "fr isolation up" } })
    ).resolves.toBeUndefined();
    await expect(handler(null)).resolves.toBeUndefined();
  });

  test("shellCwd resolves workdir against the session directory", () => {
    expect(shellCwd("/a", undefined)).toBe("/a");
    expect(shellCwd("/a", "b")).toBe("/a/b");
    expect(shellCwd("/a", "/c")).toBe("/c");
  });
});

describe("unbind", () => {
  test("session.deleted detaches with the exact argv; other events do nothing", async () => {
    const calls: string[][] = [];
    const handler = createUnbindHandler({
      directory: root,
      runFr: async (args) => {
        calls.push(args);
        return { code: 0, stdout: "" };
      },
    });
    await handler({ type: "session.idle", data: { sessionID: "ses_1" } });
    await handler({ type: "session.deleted", data: { sessionID: "ses_1" } });
    await handler({ type: "session.deleted", data: {} });
    await Promise.resolve();
    expect(calls).toEqual([["isolation", "detach", "--session", "ses_1"]]);
  });

  test("never throws", async () => {
    const handler = createUnbindHandler({
      directory: root,
      runFr: () => Promise.reject(new Error("x")),
    });
    await expect(handler({ type: "session.deleted", data: { sessionID: "s" } })).resolves.toBeUndefined();
  });
});
