// super-fr#1481: the plugin spawns no bare name. `bash` (the status line) and `gh`
// (the push guard) are resolved from ABSOLUTE PATH entries, as `git` and `fr`
// already are: a relative or empty entry names a file in whatever directory the
// server runs from, possibly one planted in the repo.
import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { chmodSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import { readPrState } from "../src/push";
import { MISSING, readSegment } from "../src/tui/segment";
import { resolveTool } from "../src/tools";

let scratch = "";
beforeEach(() => {
  scratch = realpathSync(mkdtempSync(join(tmpdir(), "fr-tools-")));
});
afterEach(() => rmSync(scratch, { recursive: true, force: true }));

function exe(path: string): string {
  mkdirSync(resolve(path, ".."), { recursive: true });
  writeFileSync(path, "#!/bin/sh\nexit 0\n");
  chmodSync(path, 0o755);
  return path;
}

describe("resolveTool", () => {
  test("skips relative and empty PATH entries", () => {
    exe(join(scratch, "bin", "gh"));
    const abs = exe(join(scratch, "abs", "gh"));
    const prev = process.cwd();
    process.chdir(scratch);
    try {
      expect(resolveTool("gh", { PATH: ["bin", ".", "", join(scratch, "abs")].join(":") }, [])).toBe(abs);
    } finally {
      process.chdir(prev);
    }
  });
  test("falls back to the absolute default directories", () => {
    const abs = exe(join(scratch, "usr", "bin", "bash"));
    expect(resolveTool("bash", { PATH: "bin" }, [join(scratch, "usr", "bin")])).toBe(abs);
  });
  test("is null when nothing absolute holds it", () => {
    exe(join(scratch, "bin", "gh"));
    expect(resolveTool("gh", { PATH: "bin:." }, [])).toBeNull();
  });
});

describe("spawns use the resolved binary", () => {
  const repo = (p: string) => p === "/w/repo/.git";

  test("the status line runs the resolved bash", async () => {
    const calls: string[] = [];
    const run = async (cmd: string) => {
      calls.push(cmd);
      return { code: 0, stdout: "none\nbranch: main\nno fr-isolation\n" };
    };
    await readSegment("/w/repo", "/s.sh", { run, exists: repo, resolve: () => "/abs/bash" });
    expect(calls).toEqual(["/abs/bash"]);
  });
  test("no bash resolves: em-dashes, and nothing is spawned", async () => {
    const calls: string[] = [];
    const run = async (cmd: string) => {
      calls.push(cmd);
      return { code: 0, stdout: "" };
    };
    expect(await readSegment("/w/repo", "/s.sh", { run, exists: repo, resolve: () => null })).toBe(
      `${MISSING} · ${MISSING}`
    );
    expect(calls).toEqual([]);
  });
  test("the push guard asks the resolved gh", async () => {
    const calls: string[] = [];
    const run = async (cmd: string) => {
      calls.push(cmd);
      return { code: 0, stdout: '{"state":"OPEN"}' };
    };
    await readPrState("/w/repo", () => "/abs/gh", run);
    expect(calls).toEqual(["/abs/gh"]);
  });
  test("no gh resolves: no answer, and nothing is spawned", async () => {
    const calls: string[] = [];
    const run = async (cmd: string) => {
      calls.push(cmd);
      return { code: 0, stdout: "" };
    };
    expect((await readPrState("/w/repo", () => null, run)).code).toBeNull();
    expect(calls).toEqual([]);
  });
});

test("tripwire: no source file spawns a bare command name", () => {
  const src = resolve(import.meta.dir, "../src");
  const files = readdirSync(src, { recursive: true }).map(String).filter((f) => f.endsWith(".ts"));
  const bare = /\b(?:run|runSync|execFile|execFileSync|spawn|spawnSync)\(\s*["'`][^/"'`]/;
  const offenders = files.filter((f) => bare.test(readFileSync(join(src, f), "utf-8")));
  expect(offenders).toEqual([]);
});
