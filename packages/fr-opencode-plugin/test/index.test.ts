// Test for the OpenCode plugin's tool.execute.before hook: it must deny
// Edit/Write-class tool calls targeting tracked source in an fr-enabled repo
// unless a valid .fr-isolation marker is present. Ports the decision logic
// of plugins/super-fr/hooks/fr-isolation-required.sh (Claude Code PreToolUse
// hook) to OpenCode's plugin API.
import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { mkdtempSync, mkdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";
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

async function makeHook(directory: string, worktree = directory) {
  const plugin = await FrIsolationRequired({
    project: undefined as never,
    client: undefined as never,
    $: undefined as never,
    directory,
    worktree,
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

  test("denies an unlisted patch tool whose target is in patchText", async () => {
    const hook = await makeHook(repo);
    await expect(
      hook(
        { tool: "apply_patch" } as never,
        { args: { patchText: "*** Update File: README.md\n@@\n-placeholder\n+blocked\n" } } as never
      )
    ).rejects.toThrow(/fr-isolation/);
  });

  test("uses OpenCode's no-space patch header grammar", async () => {
    const worktreeDir = mkdtempSync(join(tmpdir(), "fr-opencode-header-wt-"));
    rmSync(worktreeDir, { recursive: true, force: true });
    sh("git", ["worktree", "add", "-b", "feat/header-test", worktreeDir], repo);
    try {
      writeFileSync(
        join(worktreeDir, ".fr-isolation"),
        JSON.stringify({ toplevel: worktreeDir, mode: "worktree" })
      );
      const hook = await makeHook(worktreeDir);
      await expect(
        hook(
          { tool: "apply_patch" } as never,
          { args: { patchText: `*** Add File:${join(repo, "escaped.md")}\n+blocked\n` } } as never
        )
      ).rejects.toThrow(/fr-isolation/);
    } finally {
      sh("git", ["worktree", "remove", "--force", worktreeDir], repo);
    }
  });

  test("denies a headerless patch from a marked worktree", async () => {
    const worktreeDir = mkdtempSync(join(tmpdir(), "fr-opencode-empty-patch-wt-"));
    rmSync(worktreeDir, { recursive: true, force: true });
    sh("git", ["worktree", "add", "-b", "feat/empty-patch-test", worktreeDir], repo);
    try {
      writeFileSync(
        join(worktreeDir, ".fr-isolation"),
        JSON.stringify({ toplevel: worktreeDir, mode: "worktree" })
      );
      const hook = await makeHook(worktreeDir);
      await expect(
        hook({ tool: "apply_patch" } as never, { args: { patchText: "not a patch" } } as never)
      ).rejects.toThrow(/fr-isolation/);
    } finally {
      sh("git", ["worktree", "remove", "--force", worktreeDir], repo);
    }
  });

  test("denies a patch whose Move to destination leaves the worktree", async () => {
    const worktreeDir = mkdtempSync(join(tmpdir(), "fr-opencode-move-wt-"));
    rmSync(worktreeDir, { recursive: true, force: true });
    sh("git", ["worktree", "add", "-b", "feat/move-test", worktreeDir], repo);
    try {
      const resolvedTop = execFileSync("bash", ["-c", `cd "${worktreeDir}" && pwd -P`])
        .toString()
        .trim();
      writeFileSync(
        join(worktreeDir, ".fr-isolation"),
        JSON.stringify({ toplevel: resolvedTop, mode: "worktree" })
      );
      const hook = await makeHook(worktreeDir);
      await expect(
        hook(
          { tool: "apply_patch" } as never,
          {
            args: {
              patchText:
                `*** Update File: ${join(worktreeDir, "README.md")}\n` +
                `*** Move to: ${join(repo, "README.md")}\n` +
                "@@\n-placeholder\n+blocked\n",
            },
          } as never
        )
      ).rejects.toThrow(/fr-isolation/);
    } finally {
      sh("git", ["worktree", "remove", "--force", worktreeDir], repo);
    }
  });

  test("denies a future file-writing tool without a tool-name allowlist", async () => {
    const hook = await makeHook(repo);
    await expect(
      hook({ tool: "future_writer" } as never, { args: { path: "README.md" } } as never)
    ).rejects.toThrow(/fr-isolation/);
  });

  test.each([
    () => ({ edits: [{ filePath: "README.md" }] }),
    () => ({ destination: "README.md" }),
    () => ({ destination_path: "README.md" }),
    () => ({ file_path: "README.md" }),
    () => ({ paths: ["README.md"] }),
    () => ({ path: ["README.md"] }),
    () => ({ metadata: { nested: join(repo, "README.md") } }),
  ])("denies every known or absolute-path argument shape: %#", async (args) => {
    const hook = await makeHook(repo);
    await expect(hook({ tool: "future_writer" } as never, { args: args() } as never)).rejects.toThrow(
      /fr-isolation/
    );
  });

  test.each(["todowrite", "task", "webfetch", "skill"])(
    "allows a pathless %s call",
    async (tool) => {
      const hook = await makeHook(repo);
      await expect(hook({ tool } as never, { args: { prompt: "hello" } } as never)).resolves.toBeUndefined();
    }
  );

  test("denies an unresolvable patch target rather than failing open", async () => {
    const hook = await makeHook(repo);
    await expect(
      hook({ tool: "apply_patch" } as never, { args: { patchText: "not a patch" } } as never)
    ).rejects.toThrow(/fr-isolation/);
  });

  test("allows a tool call with no path arguments", async () => {
    const hook = await makeHook(repo);
    await expect(hook({ tool: "future_writer" } as never, {} as never)).resolves.toBeUndefined();
  });

  test("resolves a relative target against the session worktree", async () => {
    const hook = await makeHook(repo);
    await expect(
      hook({ tool: "edit" } as never, { args: { filePath: "README.md" } } as never)
    ).rejects.toThrow(/fr-isolation/);
  });

  test("resolves relative targets against OpenCode's directory, not worktree", async () => {
    const hook = await makeHook(repo, "/");
    await expect(
      hook({ tool: "edit" } as never, { args: { filePath: "README.md" } } as never)
    ).rejects.toThrow(/fr-isolation/);
  });

  test("normalizes nonexistent path segments before checking the marker", async () => {
    const worktreeDir = mkdtempSync(join(tmpdir(), "fr-opencode-normalize-wt-"));
    rmSync(worktreeDir, { recursive: true, force: true });
    sh("git", ["worktree", "add", "-b", "feat/normalize-test", worktreeDir], repo);
    try {
      writeFileSync(
        join(worktreeDir, ".fr-isolation"),
        JSON.stringify({ toplevel: worktreeDir, mode: "worktree" })
      );
      const hook = await makeHook(worktreeDir);
      const escaped = join(worktreeDir, "nope", "..", relative(worktreeDir, repo), "README.md");
      await expect(
        hook({ tool: "edit" } as never, { args: { filePath: escaped } } as never)
      ).rejects.toThrow(/fr-isolation/);
    } finally {
      sh("git", ["worktree", "remove", "--force", worktreeDir], repo);
    }
  });

  test("resolves an existing worktree symlink before checking the marker", async () => {
    const worktreeDir = mkdtempSync(join(tmpdir(), "fr-opencode-symlink-wt-"));
    rmSync(worktreeDir, { recursive: true, force: true });
    sh("git", ["worktree", "add", "-b", "feat/symlink-test", worktreeDir], repo);
    try {
      writeFileSync(
        join(worktreeDir, ".fr-isolation"),
        JSON.stringify({ toplevel: worktreeDir, mode: "worktree" })
      );
      const escaped = join(worktreeDir, "base-link.md");
      symlinkSync(join(repo, "README.md"), escaped);
      const hook = await makeHook(worktreeDir);
      await expect(
        hook({ tool: "edit" } as never, { args: { filePath: escaped } } as never)
      ).rejects.toThrow(/fr-isolation/);
    } finally {
      sh("git", ["worktree", "remove", "--force", worktreeDir], repo);
    }
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

  test("keeps Bash ungated", async () => {
    const hook = await makeHook(repo);
    const target = join(repo, "README.md");
    await expect(
      hook({ tool: "bash" } as never, { args: { filePath: target } } as never)
    ).resolves.toBeUndefined();
  });

  test("allows the read-only built-ins", async () => {
    const hook = await makeHook(repo);
    for (const tool of ["glob", "grep", "list", "read"]) {
      await expect(
        hook({ tool } as never, { args: { filePath: join(repo, "README.md") } } as never)
      ).resolves.toBeUndefined();
    }
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
