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
let savedK8s: string | undefined;

beforeEach(() => {
  // The `external` branch keys off live container evidence; on the host test
  // runner /.dockerenv and /run/.containerenv are absent, so
  // KUBERNETES_SERVICE_HOST is the controllable evidence. Isolate it per test.
  savedK8s = process.env.KUBERNETES_SERVICE_HOST;
  delete process.env.KUBERNETES_SERVICE_HOST;
  repo = mkdtempSync(join(tmpdir(), "fr-opencode-marker-test-"));
  sh("git", ["init", "--quiet"], repo);
  sh("git", ["config", "user.email", "test@example.com"], repo);
  sh("git", ["config", "user.name", "Test"], repo);
  writeFileSync(join(repo, "README.md"), "placeholder\n");
  sh("git", ["add", "."], repo);
  sh("git", ["commit", "--quiet", "-m", "init"], repo);
});

afterEach(() => {
  if (savedK8s === undefined) delete process.env.KUBERNETES_SERVICE_HOST;
  else process.env.KUBERNETES_SERVICE_HOST = savedK8s;
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

  test("an external marker with container evidence (KUBERNETES_SERVICE_HOST) is valid", () => {
    mkdirSync(join(repo, "docs", "superpowers", "plans"), { recursive: true });
    // external mode needs no linked-worktree; the primary clone is fine so long
    // as the toplevel matches AND live container evidence is present.
    writeFileSync(
      join(repo, ".fr-isolation"),
      JSON.stringify({ toplevel: repo, mode: "external" })
    );
    process.env.KUBERNETES_SERVICE_HOST = "10.0.0.1";
    const result = resolveMarker(join(repo, "README.md"));
    expect(result.hasValidMarker).toBe(true);
  });

  test("an external marker with no container evidence is never valid", () => {
    mkdirSync(join(repo, "docs", "superpowers", "plans"), { recursive: true });
    // No KUBERNETES_SERVICE_HOST, and /.dockerenv and /run/.containerenv are
    // absent on the host runner — a marker forged on a bare host fails closed.
    writeFileSync(
      join(repo, ".fr-isolation"),
      JSON.stringify({ toplevel: repo, mode: "external" })
    );
    const result = resolveMarker(join(repo, "README.md"));
    expect(result.hasValidMarker).toBe(false);
  });

  test("an external marker recorded for a different toplevel is never valid even with evidence", () => {
    mkdirSync(join(repo, "docs", "superpowers", "plans"), { recursive: true });
    writeFileSync(
      join(repo, ".fr-isolation"),
      JSON.stringify({ toplevel: "/some/other/path", mode: "external" })
    );
    process.env.KUBERNETES_SERVICE_HOST = "10.0.0.1";
    const result = resolveMarker(join(repo, "README.md"));
    expect(result.hasValidMarker).toBe(false);
  });
});
