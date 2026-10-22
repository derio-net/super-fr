// The pipeline sentinel writer (spec 2026-10-20-opencode-2-support R10): the
// OpenCode 2 port of plugins/super-fr/hooks/fr-pipeline-sentinel.sh, run from
// `execute.after` on a completed `skill` call.
import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { writePipelineSentinel } from "../src/sentinel";

let root: string;
let base: string;
let saved: Record<string, string | undefined>;

function git(cwd: string, ...args: string[]): void {
  execFileSync("git", ["-c", "user.email=t@example.com", "-c", "user.name=t", ...args], { cwd, stdio: "pipe" });
}

beforeEach(() => {
  root = realpathSync(mkdtempSync(join(tmpdir(), "fr-sentinel-")));
  base = join(root, "base");
  mkdirSync(base);
  git(base, "init", "-q");
  writeFileSync(join(base, "f"), "x\n");
  git(base, "add", "f");
  git(base, "commit", "-q", "-m", "init");
  mkdirSync(join(root, "home", ".cache", "fr"), { recursive: true });
  saved = { HOME: process.env.HOME, FR_SENTINEL_DIR: process.env.FR_SENTINEL_DIR };
  process.env.HOME = join(root, "home");
  process.env.FR_SENTINEL_DIR = join(root, "sentinels");
});

afterEach(() => {
  for (const [k, v] of Object.entries(saved)) {
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
  rmSync(root, { recursive: true, force: true });
});

const sentinelOf = (session: string) => join(root, "sentinels", `${session}.json`);

function skillEvent(id: string, sessionID = "ses_1", status = "completed") {
  return { tool: "skill", sessionID, status, input: { id } };
}

describe("writePipelineSentinel", () => {
  test("a pipeline skill in a base repo writes the bash writer's keys", () => {
    writePipelineSentinel(skillEvent("fr-goal"), base);
    const data = JSON.parse(readFileSync(sentinelOf("ses_1"), "utf-8"));
    // fr-pipeline-sentinel.sh writes exactly these, and `workspaces` only when
    // it carries a live entry.
    expect(Object.keys(data).sort()).toEqual(["repo_root", "skill", "started_at"]);
    expect(realpathSync(data.repo_root)).toBe(base);
    expect(data.skill).toBe("fr-goal");
    expect(data.started_at).toMatch(/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/);
  });

  test.each(["fr-brainstorming", "fr-execute", "super-fr:fr-goal"])("%s arms the pipeline", (id) => {
    writePipelineSentinel(skillEvent(id), base);
    expect(existsSync(sentinelOf("ses_1"))).toBe(true);
  });

  test("a non-pipeline skill writes nothing", () => {
    writePipelineSentinel(skillEvent("fr-plan"), base);
    expect(existsSync(sentinelOf("ses_1"))).toBe(false);
  });

  test("a failed skill call, or another tool, writes nothing", () => {
    writePipelineSentinel(skillEvent("fr-goal", "ses_1", "error"), base);
    writePipelineSentinel({ ...skillEvent("fr-goal"), tool: "shell" }, base);
    expect(existsSync(sentinelOf("ses_1"))).toBe(false);
  });

  test("a linked worktree (the isolation workspace) writes nothing", () => {
    const wt = join(root, "wt");
    git(base, "worktree", "add", "-q", "-b", "feat", wt);
    writeFileSync(join(wt, ".fr-isolation"), JSON.stringify({ toplevel: wt, mode: "worktree", branch: "feat" }));
    writePipelineSentinel(skillEvent("fr-goal"), wt);
    expect(existsSync(sentinelOf("ses_1"))).toBe(false);
  });

  test("a non-git directory writes nothing", () => {
    const plain = join(root, "plain");
    mkdirSync(plain);
    writePipelineSentinel(skillEvent("fr-goal"), plain);
    expect(existsSync(sentinelOf("ses_1"))).toBe(false);
  });

  test("a sentinel older than 48h is collected, and this session's is written afresh", () => {
    mkdirSync(join(root, "sentinels"));
    const old = sentinelOf("ses_old");
    const mine = sentinelOf("ses_1");
    writeFileSync(old, JSON.stringify({ repo_root: base, workspaces: ["worktrees/gone"] }));
    writeFileSync(mine, JSON.stringify({ repo_root: base, skill: "stale", workspaces: ["worktrees/gone"] }));
    const past = new Date(Date.now() - 49 * 3600 * 1000);
    utimesSync(old, past, past);
    utimesSync(mine, past, past);
    writePipelineSentinel(skillEvent("fr-goal"), base);
    expect(existsSync(old)).toBe(false);
    const data = JSON.parse(readFileSync(mine, "utf-8"));
    expect(data.skill).toBe("fr-goal");
    expect(data.workspaces).toBeUndefined();
  });

  test("an old sentinel whose workspace still exists is a parked pipeline, and is kept", () => {
    mkdirSync(join(root, "sentinels"));
    mkdirSync(join(root, "home", ".cache", "fr", "worktrees", "live"), { recursive: true });
    const parked = sentinelOf("ses_parked");
    writeFileSync(parked, JSON.stringify({ repo_root: base, workspaces: ["worktrees/live"] }));
    const past = new Date(Date.now() - 49 * 3600 * 1000);
    utimesSync(parked, past, past);
    writePipelineSentinel(skillEvent("fr-goal"), base);
    expect(existsSync(parked)).toBe(true);
  });

  test("a reload carries only the live workspaces of the same repo", () => {
    mkdirSync(join(root, "sentinels"));
    mkdirSync(join(root, "home", ".cache", "fr", "worktrees", "live"), { recursive: true });
    const repoRoot = execFileSync("git", ["-C", base, "rev-parse", "--show-toplevel"]).toString().trim();
    writeFileSync(
      sentinelOf("ses_1"),
      JSON.stringify({ repo_root: repoRoot, skill: "fr-goal", workspaces: ["worktrees/live", "worktrees/gone"] })
    );
    writePipelineSentinel(skillEvent("fr-brainstorming"), base);
    const data = JSON.parse(readFileSync(sentinelOf("ses_1"), "utf-8"));
    expect(data.workspaces).toEqual(["worktrees/live"]);
    expect(data.skill).toBe("fr-brainstorming");
  });

  test("the write leaves no temp file and releases the lock", () => {
    writePipelineSentinel(skillEvent("fr-goal"), base);
    const left = execFileSync("ls", ["-a", join(root, "sentinels")]).toString().split("\n").filter(Boolean);
    expect(left.sort()).toEqual([".", "..", "ses_1.json"]);
  });

  test("never throws, even with an unwritable sentinel dir", () => {
    process.env.FR_SENTINEL_DIR = "/dev/null/sentinels";
    expect(() => writePipelineSentinel(skillEvent("fr-goal"), base)).not.toThrow();
    expect(() => writePipelineSentinel(null as never, base)).not.toThrow();
  });
});
