// Unit tests for the extracted marker-resolution logic (src/marker.ts),
// isolated from the tool.execute.before wiring in index.test.ts.
import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { resolveMarker } from "../src/marker";

function sh(cmd: string, args: string[], cwd: string): void {
  execFileSync(cmd, args, { cwd, stdio: "pipe" });
}

let repo: string;

beforeEach(() => {
  repo = mkdtempSync(join(tmpdir(), "fr-opencode-marker-test-"));
  sh("git", ["init", "--quiet"], repo);
  sh("git", ["config", "user.email", "test@example.com"], repo);
  sh("git", ["config", "user.name", "Test"], repo);
  writeFileSync(join(repo, "README.md"), "placeholder\n");
  sh("git", ["add", "."], repo);
  sh("git", ["commit", "--quiet", "-m", "init"], repo);
});

afterEach(() => {
  rmSync(repo, { recursive: true, force: true });
});

describe("resolveMarker", () => {
  test("frEnabled is false with no devcontainer profile or plans dir", () => {
    const result = resolveMarker(join(repo, "README.md"));
    expect(result.frEnabled).toBe(false);
  });

  test("frEnabled is true when a devcontainer profile exists", () => {
    mkdirSync(join(repo, ".devcontainer", "dev"), { recursive: true });
    writeFileSync(join(repo, ".devcontainer", "dev", "devcontainer.json"), "{}\n");
    const result = resolveMarker(join(repo, "README.md"));
    expect(result.frEnabled).toBe(true);
    expect(result.hasValidMarker).toBe(false);
  });

  test("frEnabled is true when a docs/superpowers/plans dir exists", () => {
    mkdirSync(join(repo, "docs", "superpowers", "plans"), { recursive: true });
    const result = resolveMarker(join(repo, "README.md"));
    expect(result.frEnabled).toBe(true);
  });

  test("a marker with mode != worktree is never valid", () => {
    mkdirSync(join(repo, "docs", "superpowers", "plans"), { recursive: true });
    writeFileSync(
      join(repo, ".fr-isolation"),
      JSON.stringify({ toplevel: repo, mode: "devcontainer" })
    );
    const result = resolveMarker(join(repo, "README.md"));
    expect(result.hasValidMarker).toBe(false);
  });

  test("a marker recorded for a different toplevel is never valid", () => {
    mkdirSync(join(repo, "docs", "superpowers", "plans"), { recursive: true });
    writeFileSync(
      join(repo, ".fr-isolation"),
      JSON.stringify({ toplevel: "/some/other/path", mode: "worktree" })
    );
    const result = resolveMarker(join(repo, "README.md"));
    expect(result.hasValidMarker).toBe(false);
  });

  test("a marker in the primary working tree (not a linked worktree) is never valid", () => {
    mkdirSync(join(repo, "docs", "superpowers", "plans"), { recursive: true });
    // Recorded toplevel matches, mode is "worktree", but this IS the primary
    // clone — git-common-dir == git-dir, so it must still fail closed.
    writeFileSync(
      join(repo, ".fr-isolation"),
      JSON.stringify({ toplevel: repo, mode: "worktree" })
    );
    const result = resolveMarker(join(repo, "README.md"));
    expect(result.hasValidMarker).toBe(false);
  });
});
