// Test for the OpenCode plugin's tool.execute.before hook: it must deny
// Edit/Write-class tool calls targeting tracked source in an fr-enabled repo
// unless a valid .fr-isolation marker is present. Ports the decision logic
// of plugins/super-fr/hooks/fr-isolation-required.sh (Claude Code PreToolUse
// hook) to OpenCode's plugin API.
import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";

import { FrIsolationRequired } from "../src/index";

function sh(cmd: string, args: string[], cwd: string): void {
  execFileSync(cmd, args, { cwd, stdio: "pipe" });
}

function initFrEnabledRepo(): string {
  const dir = mkdtempSync(join(tmpdir(), "fr-opencode-test-"));
  sh("git", ["init", "--quiet"], dir);
  sh("git", ["config", "user.email", "test@example.com"], dir);
  sh("git", ["config", "user.name", "Test"], dir);
  // fr-enabled marker: a devcontainer profile.
  mkdirSync(join(dir, ".devcontainer", "dev"), { recursive: true });
  writeFileSync(join(dir, ".devcontainer", "dev", "devcontainer.json"), "{}\n");
  writeFileSync(join(dir, "README.md"), "placeholder\n");
  sh("git", ["add", "."], dir);
  sh("git", ["commit", "--quiet", "-m", "init"], dir);
  return dir;
}

let repo: string;

beforeEach(() => {
  repo = initFrEnabledRepo();
  delete process.env.FR_BASE_OK;
});

afterEach(() => {
  rmSync(repo, { recursive: true, force: true });
});

async function makeHook(directory: string) {
  const plugin = await FrIsolationRequired({
    project: undefined as never,
    client: undefined as never,
    $: undefined as never,
    directory,
    worktree: directory,
  });
  return plugin["tool.execute.before"]!;
}

describe("fr-isolation-required (OpenCode plugin)", () => {
  test("denies an edit with no .fr-isolation marker present", async () => {
    const hook = await makeHook(repo);
    const target = join(repo, "README.md");
    await expect(
      hook({ tool: "edit" } as never, { args: { filePath: target } } as never)
    ).rejects.toThrow(/fr-isolation/);
  });

  test("allows the edit when FR_BASE_OK=1 is set", async () => {
    process.env.FR_BASE_OK = "1";
    const hook = await makeHook(repo);
    const target = join(repo, "README.md");
    await expect(
      hook({ tool: "edit" } as never, { args: { filePath: target } } as never)
    ).resolves.toBeUndefined();
  });

  test("allows the edit when the path matches .fr-isolation-allow", async () => {
    writeFileSync(join(repo, ".fr-isolation-allow"), "README.md\n");
    const hook = await makeHook(repo);
    const target = join(repo, "README.md");
    await expect(
      hook({ tool: "edit" } as never, { args: { filePath: target } } as never)
    ).resolves.toBeUndefined();
  });

  test("still denies a non-matching path even with .fr-isolation-allow present", async () => {
    writeFileSync(join(repo, ".fr-isolation-allow"), "docs/**\n");
    const hook = await makeHook(repo);
    const target = join(repo, "README.md");
    await expect(
      hook({ tool: "edit" } as never, { args: { filePath: target } } as never)
    ).rejects.toThrow(/fr-isolation/);
  });

  test("ignores non-edit tools entirely", async () => {
    const hook = await makeHook(repo);
    const target = join(repo, "README.md");
    await expect(
      hook({ tool: "bash" } as never, { args: { filePath: target } } as never)
    ).resolves.toBeUndefined();
  });

  test("allows edits inside a real linked worktree with a valid marker", async () => {
    const worktreeDir = mkdtempSync(join(tmpdir(), "fr-opencode-wt-"));
    rmSync(worktreeDir, { recursive: true, force: true }); // git worktree add wants it absent
    sh("git", ["worktree", "add", "-b", "feat/test", worktreeDir], repo);
    try {
      const resolvedTop = execFileSync("bash", ["-c", `cd "${worktreeDir}" && pwd -P`])
        .toString()
        .trim();
      writeFileSync(
        join(worktreeDir, ".fr-isolation"),
        JSON.stringify({ toplevel: resolvedTop, mode: "worktree" })
      );
      const hook = await makeHook(worktreeDir);
      const target = join(worktreeDir, "README.md");
      await expect(
        hook({ tool: "edit" } as never, { args: { filePath: target } } as never)
      ).resolves.toBeUndefined();
    } finally {
      sh("git", ["worktree", "remove", "--force", worktreeDir], repo);
    }
  });
});
