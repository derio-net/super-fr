// The gates judge in the session's own directory (spec 2026-11-19-consumer-followups
// R1-R4, gh#1552): one OpenCode server can hold a session in another checkout than
// the plugin's (gh#1371). Here the plugin sits in repo A and the session lives in
// repo B (or B's workspace); `session.get` names the session's directory.
import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { execFileSync } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { sharedSessionDirectories } from "../src/session";
import { load } from "./fake";

let root: string;
let repoA: string;
let repoB: string;
let wtB: string;
const saved: Record<string, string | undefined> = {};

function git(cwd: string, ...args: string[]): void {
  execFileSync("git", ["-c", "user.email=t@example.com", "-c", "user.name=t", ...args], { cwd, stdio: "pipe" });
}

function frEnabledRepo(dir: string): void {
  mkdirSync(join(dir, "docs", "superpowers", "plans"), { recursive: true });
  mkdirSync(join(dir, "sub"), { recursive: true });
  writeFileSync(join(dir, "README.md"), "x\n");
  writeFileSync(join(dir, "sub", "keep"), "x\n");
  git(dir, "init", "-q");
  git(dir, "add", ".");
  git(dir, "commit", "-q", "-m", "init");
}

beforeEach(() => {
  root = realpathSync(mkdtempSync(join(tmpdir(), "fr-session-gates-")));
  repoA = join(root, "plugin", "a");
  repoB = join(root, "b");
  frEnabledRepo(repoA);
  frEnabledRepo(repoB);
  wtB = join(root, "home", ".cache", "fr", "worktrees", "b", "feat");
  mkdirSync(join(root, "home", ".cache", "fr", "worktrees", "b"), { recursive: true });
  git(repoB, "worktree", "add", "-q", "-b", "feat", wtB);
  writeFileSync(join(wtB, ".fr-isolation"), JSON.stringify({ toplevel: wtB, mode: "worktree", branch: "feat" }));
  // A fake `gh` that reports a MERGED PR only when it runs in B's workspace, so a
  // push refusal proves which directory the push guard was given.
  mkdirSync(join(root, "bin"));
  const gh = join(root, "bin", "gh");
  writeFileSync(gh, `#!/bin/sh\nif [ "$(pwd -P)" = "${wtB}" ]; then echo '{"state":"MERGED"}'; else exit 1; fi\n`);
  chmodSync(gh, 0o755);
  for (const k of ["HOME", "PATH", "FR_SENTINEL_DIR", "FR_CD_ALLOW_PREFIXES", "FR_BASE_OK"]) saved[k] = process.env[k];
  process.env.HOME = join(root, "home");
  process.env.PATH = `${join(root, "bin")}:${process.env.PATH}`;
  process.env.FR_SENTINEL_DIR = join(root, "sentinels");
  process.env.FR_CD_ALLOW_PREFIXES = join(root, "home", ".cache", "fr", "worktrees");
  delete process.env.FR_BASE_OK;
  sharedSessionDirectories().clear();
});

afterEach(() => {
  for (const [k, v] of Object.entries(saved)) {
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
  sharedSessionDirectories().clear();
  rmSync(root, { recursive: true, force: true });
});

/** A session API whose `get` names `directory` for every session asked about. */
function livesIn(directory: string) {
  return { get: async ({ sessionID }: { sessionID: string }) => ({ id: sessionID, location: { directory } }) };
}

const failing = {
  get: async () => {
    throw new Error("lookup failed");
  },
};

const shell = (command: string, workdir?: string) => ({
  tool: "shell",
  sessionID: "ses_1",
  input: workdir ? { command, workdir } : { command },
});
const edit = (filePath: string) => ({ tool: "write", sessionID: "ses_1", input: { filePath, content: "y\n" } });
const headerlessPatch = { tool: "apply_patch", sessionID: "ses_1", input: { patchText: "*** Begin Patch\n*** End Patch\n" } };
const pipeline = { tool: "skill", sessionID: "ses_1", status: "completed", input: { id: "fr-goal" } };

/** Arm ses_1's pipeline for `repoRoot` directly, whatever directory the plugin is in. */
function armFor(repoRoot: string): void {
  mkdirSync(join(root, "sentinels"), { recursive: true });
  writeFileSync(
    join(root, "sentinels", "ses_1.json"),
    JSON.stringify({ repo_root: repoRoot, skill: "fr-goal", started_at: new Date().toISOString() })
  );
}

function sentinelRepoRoot(): string {
  return (JSON.parse(readFileSync(join(root, "sentinels", "ses_1.json"), "utf8")) as { repo_root: string }).repo_root;
}

describe("the gates judge in the session's directory (#1552)", () => {
  test("the sentinel is armed for the session's repo, not the plugin's (R3)", async () => {
    const { executeAfter } = await load({ directory: repoA, session: livesIn(repoB) });
    await executeAfter(pipeline);
    expect(realpathSync(sentinelRepoRoot())).toBe(repoB);
  });

  test("the shell gate refuses a base-clone command in the session's repo (R1)", async () => {
    const { executeBefore } = await load({ directory: repoA, session: livesIn(repoB) });
    armFor(repoB);
    await expect(executeBefore(shell("git status"))).rejects.toThrow(/^fr pipeline active/);
    // A relative workdir resolves against the session's directory: B/sub is in B.
    await expect(executeBefore(shell("git status", "sub"))).rejects.toThrow(/^fr pipeline active/);
  });

  test("the push guard runs in the session's directory (R1)", async () => {
    const { executeBefore } = await load({ directory: repoA, session: livesIn(wtB) });
    armFor(repoB);
    await expect(executeBefore(shell("git push"))).rejects.toThrow(/^Pre-push guard: this branch's PR is MERGED/);
  });

  test("a relative edit target is judged in the session's repo (R2)", async () => {
    const inBase = await load({ directory: repoA, session: livesIn(repoB) });
    await expect(inBase.executeBefore(edit("README.md"))).rejects.toThrow(/fr-isolation: edit to `README.md` blocked/);
    sharedSessionDirectories().clear();
    // Repo A is fr-enabled with no marker too, so only the session's workspace
    // explains an allow here.
    const inWorkspace = await load({ directory: repoA, session: livesIn(wtB) });
    await expect(inWorkspace.executeBefore(edit("README.md"))).resolves.toBeUndefined();
  });

  test("the unresolvable-patch probe is judged in the session's repo (R2)", async () => {
    const outside = join(root, "plain");
    mkdirSync(outside);
    // From a plain directory the probe finds no fr-enabled repo and allows; in B it refuses.
    const plain = await load({ directory: outside, session: livesIn(outside) });
    await expect(plain.executeBefore(headerlessPatch)).resolves.toBeUndefined();
    sharedSessionDirectories().clear();
    const inB = await load({ directory: outside, session: livesIn(repoB) });
    await expect(inB.executeBefore(headerlessPatch)).rejects.toThrow(/unresolvable patch target blocked/);
  });

  test("a failed lookup judges every case in the plugin's directory, as before (R4)", async () => {
    const { executeBefore, executeAfter } = await load({ directory: repoA, session: failing });
    await executeAfter(pipeline);
    expect(realpathSync(sentinelRepoRoot())).toBe(repoA);
    await expect(executeBefore(shell("git status"))).rejects.toThrow(/^fr pipeline active/);
    await expect(executeBefore(edit("README.md"))).rejects.toThrow(/fr-isolation: edit to `README.md` blocked/);
    expect(sharedSessionDirectories().has("ses_1")).toBe(false);
  });

  test("a failed lookup from a plain plugin directory leaves the session's repo unjudged", async () => {
    const outside = join(root, "plain");
    mkdirSync(outside);
    const { executeBefore } = await load({ directory: outside, session: failing });
    await expect(executeBefore(headerlessPatch)).resolves.toBeUndefined();
    await expect(executeBefore(edit("README.md"))).resolves.toBeUndefined();
  });
});
