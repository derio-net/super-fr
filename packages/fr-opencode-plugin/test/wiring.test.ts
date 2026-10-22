// The phase-2 handlers wired through the real `setup` (spec 2026-10-20-opencode-2-support
// R3, R10): a `skill` call arms the sentinel through `execute.after`, and the next
// base-repo `shell` call is refused by `execute.before` with the guard's text —
// while `cd <worktree> && …`, judged on the WHOLE line, is not.
import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { load } from "./fake";

let root: string;
let base: string;
let wt: string;
const saved: Record<string, string | undefined> = {};

function git(cwd: string, ...args: string[]): void {
  execFileSync("git", ["-c", "user.email=t@example.com", "-c", "user.name=t", ...args], { cwd, stdio: "pipe" });
}

beforeEach(() => {
  root = realpathSync(mkdtempSync(join(tmpdir(), "fr-wiring-")));
  base = join(root, "base");
  mkdirSync(join(base, "docs", "superpowers", "plans"), { recursive: true });
  git(base, "init", "-q");
  writeFileSync(join(base, "f"), "x\n");
  git(base, "add", "f");
  git(base, "commit", "-q", "-m", "init");
  wt = join(root, "home", ".cache", "fr", "worktrees", "base", "feat");
  mkdirSync(join(root, "home", ".cache", "fr", "worktrees", "base"), { recursive: true });
  git(base, "worktree", "add", "-q", "-b", "feat", wt);
  writeFileSync(join(wt, ".fr-isolation"), JSON.stringify({ toplevel: wt, mode: "worktree", branch: "feat" }));
  for (const k of ["HOME", "FR_SENTINEL_DIR", "FR_CD_ALLOW_PREFIXES", "FR_BASE_OK"]) saved[k] = process.env[k];
  process.env.HOME = join(root, "home");
  process.env.FR_SENTINEL_DIR = join(root, "sentinels");
  process.env.FR_CD_ALLOW_PREFIXES = join(root, "home", ".cache", "fr", "worktrees");
  delete process.env.FR_BASE_OK;
});

afterEach(() => {
  for (const [k, v] of Object.entries(saved)) {
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
  rmSync(root, { recursive: true, force: true });
});

const shell = (command: string, workdir?: string) => ({
  tool: "shell",
  sessionID: "ses_1",
  input: workdir ? { command, workdir } : { command },
});

describe("phase-2 wiring", () => {
  test("no pipeline: a base-repo shell call is allowed", async () => {
    const { executeBefore } = await load({ directory: base });
    await expect(executeBefore(shell("git status"))).resolves.toBeUndefined();
  });

  test("a pipeline skill arms the gate; the whole line decides", async () => {
    const { executeBefore, executeAfter } = await load({ directory: base });
    await executeAfter({ tool: "skill", sessionID: "ses_1", status: "completed", input: { id: "fr-goal" } });
    expect(existsSync(join(root, "sentinels", "ses_1.json"))).toBe(true);
    await expect(executeBefore(shell("git status"))).rejects.toThrow(/^fr pipeline active/);
    await expect(executeBefore(shell(`cd ${wt} && git status`))).resolves.toBeUndefined();
    await expect(executeBefore(shell("fr isolation status && make"))).resolves.toBeUndefined();
    // V2's `workdir` is where the command runs.
    await expect(executeBefore(shell("git status", wt))).resolves.toBeUndefined();
    // Another session holds no pipeline.
    await expect(executeBefore({ ...shell("git status"), sessionID: "ses_2" })).resolves.toBeUndefined();
  });

  test("the context hook leaves the system parts alone in a repo with no matrix", async () => {
    const { context } = await load({ directory: base, session: { get: async () => ({ id: "ses_1" }) } });
    const event = { sessionID: "ses_1", system: [] as unknown[] };
    await context(event);
    expect(event.system).toEqual([]);
  });
});
