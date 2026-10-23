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

import { load } from "./fake";

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

// The V2 handler takes one event, `{tool, sessionID, input}`, where `input` is
// the tool's arguments. This adapter keeps every case below in the 1.x
// `(input, {args})` spelling it was written in, so no assertion moved in the port.
async function makeHook(location: string | { directory: string; projectDirectory?: string }) {
  const { executeBefore } = await load(
    typeof location === "string" ? { directory: location } : location
  );
  return (input: { tool: string }, output: { args?: unknown } | undefined) =>
    executeBefore({ tool: input.tool, sessionID: "", input: output?.args });
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

  test("resolves a relative target against the session's directory", async () => {
    const hook = await makeHook(repo);
    await expect(
      hook({ tool: "edit" } as never, { args: { filePath: "README.md" } } as never)
    ).rejects.toThrow(/fr-isolation/);
  });

  test("resolves relative targets against OpenCode's directory, not the project", async () => {
    // The V2 context replaced 1.x's `worktree || directory` with `location`;
    // `location.project.directory` is the PROJECT root, which may sit above the
    // workspace. The base is the session's own directory, so a relative target
    // from elsewhere is outside any fr-enabled repo — while an absolute target
    // in the project is still denied, so the base moved rather than the gate
    // switching off.
    const elsewhere = mkdtempSync(join(tmpdir(), "fr-opencode-elsewhere-"));
    try {
      const hook = await makeHook({ directory: elsewhere, projectDirectory: repo });
      await expect(
        hook({ tool: "edit" } as never, { args: { filePath: "README.md" } } as never)
      ).resolves.toBeUndefined();
      await expect(
        hook({ tool: "edit" } as never, { args: { filePath: join(repo, "README.md") } } as never)
      ).rejects.toThrow(/fr-isolation/);
    } finally {
      rmSync(elsewhere, { recursive: true, force: true });
    }
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

  test("denies worktree symlinks that resolve into the base clone, including dangling links", async () => {
    const worktreeDir = mkdtempSync(join(tmpdir(), "fr-opencode-symlink-wt-"));
    rmSync(worktreeDir, { recursive: true, force: true });
    sh("git", ["worktree", "add", "-b", "feat/symlink-test", worktreeDir], repo);
    try {
      writeFileSync(
        join(worktreeDir, ".fr-isolation"),
        JSON.stringify({ toplevel: worktreeDir, mode: "worktree" })
      );
      const nonDangling = join(worktreeDir, "base-link.md");
      const dangling = join(worktreeDir, "base-link-dangling.md");
      symlinkSync(join(repo, "README.md"), nonDangling);
      symlinkSync(join(repo, "does-not-exist.md"), dangling);
      const hook = await makeHook(worktreeDir);
      await expect(
        hook({ tool: "write" } as never, { args: { filePath: nonDangling } } as never)
      ).rejects.toThrow(/fr-isolation/);
      await expect(
        hook({ tool: "write" } as never, { args: { filePath: dangling } } as never)
      ).rejects.toThrow(/fr-isolation/);
    } finally {
      sh("git", ["worktree", "remove", "--force", worktreeDir], repo);
    }
  });

  test("allows a symlink that remains inside a marked worktree", async () => {
    const worktreeDir = mkdtempSync(join(tmpdir(), "fr-opencode-contained-symlink-wt-"));
    rmSync(worktreeDir, { recursive: true, force: true });
    sh("git", ["worktree", "add", "-b", "feat/contained-symlink-test", worktreeDir], repo);
    try {
      writeFileSync(
        join(worktreeDir, ".fr-isolation"),
        JSON.stringify({ toplevel: worktreeDir, mode: "worktree" })
      );
      const contained = join(worktreeDir, "contained-link.md");
      symlinkSync(join(worktreeDir, "README.md"), contained);
      const hook = await makeHook(worktreeDir);
      await expect(
        hook({ tool: "write" } as never, { args: { filePath: contained } } as never)
      ).resolves.toBeUndefined();
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

  test("keeps OpenCode 2's `shell` tool ungated, as `bash` was", async () => {
    const hook = await makeHook(repo);
    const target = join(repo, "README.md");
    await expect(
      hook({ tool: "shell" } as never, { args: { filePath: target } } as never)
    ).resolves.toBeUndefined();
  });

  test("a call that names no tool is inspected, not waved through", async () => {
    const { executeBefore } = await load({ directory: repo });
    await expect(executeBefore({ input: { filePath: join(repo, "README.md") } })).rejects.toThrow(/fr-isolation/);
  });

  test("lets the host-side `cd <worktree> && fr run …` form through", async () => {
    // spec 2026-09-25-lean-cost-aware-process §5.B.6: in devcontainer mode
    // `fr run` / `fr usage` run on the harness host from the worktree.
    const hook = await makeHook(repo);
    const command = `cd ${join(repo, ".cache/fr/worktrees/x")} && uv run fr run resolve r --step x`;
    await expect(
      hook({ tool: "bash" } as never, { args: { command } } as never)
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

// gh#1221 (found while removing the bare `git` spawn): the gate walks every
// string in the tool input and treats an unkeyed ABSOLUTE one as a possible
// target. `write`'s `content` is an unkeyed string, so a file beginning with
// `//` — a licence header, a commented-out include — was read as an absolute
// path, and the refusal named the CONTENT ("cannot inspect target symlink:
// // …", ENAMETOOLONG on a real file). A multi-line or oversized string is
// prose, never a path, and the verdict must come from the real target.
describe("fr-isolation-required: content is never a target (gh#1221)", () => {
  test("denies a write whose content starts with //, naming the FILE", async () => {
    const hook = await makeHook(repo);
    const target = join(repo, "notes.ts");
    const content = "// a header comment\n// and a second line\nexport const x = 1;\n";
    const failure = await hook({ tool: "write" } as never, { args: { filePath: target, content } } as never)
      .then(() => null)
      .catch((error: Error) => error);
    expect(failure).toBeInstanceOf(Error);
    expect(failure!.message).toContain(target);
    // The content never appears in the refusal, and never becomes a probe path.
    expect(failure!.message).not.toContain("header comment");
    expect(failure!.message).not.toContain("ENAMETOOLONG");
  });

  test("allows the same write inside a valid workspace, content untouched", async () => {
    const worktreeDir = mkdtempSync(join(tmpdir(), "fr-opencode-content-wt-"));
    rmSync(worktreeDir, { recursive: true, force: true });
    sh("git", ["worktree", "add", "-b", "feat/content-test", worktreeDir], repo);
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
          { tool: "write" } as never,
          {
            args: {
              filePath: join(worktreeDir, "notes.ts"),
              content: "// a header comment\n// and a second line\nexport const x = 1;\n",
            },
          } as never
        )
      ).resolves.toBeUndefined();
    } finally {
      sh("git", ["worktree", "remove", "--force", worktreeDir], repo);
    }
  });

  test("a huge single-line absolute string is content too, not a path probe", async () => {
    const hook = await makeHook(repo);
    const target = join(repo, "README.md");
    const content = `/${"a".repeat(5000)}`;
    const failure = await hook({ tool: "write" } as never, { args: { filePath: target, content } } as never)
      .then(() => null)
      .catch((error: Error) => error);
    expect(failure).toBeInstanceOf(Error);
    expect(failure!.message).toContain(target);
    expect(failure!.message).not.toContain("ENAMETOOLONG");
  });
});

// gh#1221: the gate's posture with git unreachable is fail-OPEN (the bash
// guard's), and setup says so once at load. Here the load happens with git
// present; the strip is scoped to the call, so this proves the GATE's answer
// and not setup's warning (which plugin.test.ts owns).
describe("fr-isolation-required: fail-open when git is unreachable (gh#1221)", () => {
  test("allows a base-repo edit rather than guessing a verdict", async () => {
    const hook = await makeHook(repo);
    const savedPath = process.env.PATH;
    const savedCandidates = process.env.FR_GIT_CANDIDATES;
    const empty = mkdtempSync(join(tmpdir(), "fr-opencode-nogit-gate-"));
    try {
      process.env.PATH = empty;
      process.env.FR_GIT_CANDIDATES = join(empty, "no-such-git");
      await expect(
        hook({ tool: "edit" } as never, { args: { filePath: join(repo, "README.md") } } as never)
      ).resolves.toBeUndefined();
    } finally {
      process.env.PATH = savedPath;
      if (savedCandidates === undefined) delete process.env.FR_GIT_CANDIDATES;
      else process.env.FR_GIT_CANDIDATES = savedCandidates;
      rmSync(empty, { recursive: true, force: true });
    }
  });
});
