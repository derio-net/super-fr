// The status line's data (src/tui/segment.ts), against a stubbed spawn: the
// segment text, the em-dash for what is missing, nothing outside a repo, and
// refreshes that coalesce instead of spawning per request.
import { describe, expect, test } from "bun:test";

import { createRefresher, formatSegment, inGitRepo, MISSING, readSegment } from "../src/tui/segment";

const repo = (p: string) => p === "/w/repo/.git";

function stub(stdout: string, code: number | null = 0) {
  const calls: Array<{ cmd: string; args: string[] }> = [];
  const run = async (cmd: string, args: string[]) => {
    calls.push({ cmd, args });
    return { code, stdout };
  };
  return { calls, run };
}

describe("formatSegment", () => {
  test("an fr workspace names its branch", () => {
    expect(formatSegment("fr\nbranch: feat/x\nworktree: /w/wt\n")).toBe("fr \u2387 feat/x");
  });
  test("outside isolation says so", () => {
    expect(formatSegment("none\nbranch: main\nno fr-isolation\n")).toBe("main \u00b7 no fr-isolation");
  });
  test("a detached HEAD is an em-dash, not an empty string", () => {
    expect(formatSegment("none\nno branch\nno fr-isolation\n")).toBe(`${MISSING} \u00b7 no fr-isolation`);
  });
  test("unreadable output is all em-dashes", () => {
    expect(formatSegment("")).toBe(`${MISSING} \u00b7 ${MISSING}`);
    expect(formatSegment("garbage")).toBe(`${MISSING} \u00b7 ${MISSING}`);
  });
});

describe("readSegment", () => {
  test("renders nothing outside a git repo, and never spawns", async () => {
    const s = stub("fr\nbranch: x\nworktree: /x\n");
    expect(await readSegment("/elsewhere", "/s.sh", { run: s.run, exists: repo })).toBe("");
    expect(s.calls).toEqual([]);
  });
  test("inside a repo runs the shared segment script with --cwd", async () => {
    const s = stub("none\nbranch: main\nno fr-isolation\n");
    expect(await readSegment("/w/repo/sub", "/s.sh", { run: s.run, exists: repo })).toBe(
      "main \u00b7 no fr-isolation"
    );
    expect(s.calls).toEqual([
      { cmd: "bash", args: ["/s.sh", "--format", "plain", "--cwd", "/w/repo/sub"] },
    ]);
  });
  test("a failed or timed-out script is em-dashes, never a throw", async () => {
    const s = stub("", null);
    expect(await readSegment("/w/repo", "/s.sh", { run: s.run, exists: repo })).toBe(
      `${MISSING} \u00b7 ${MISSING}`
    );
  });
  test("inGitRepo walks up to the root and stops", () => {
    expect(inGitRepo("/w/repo/a/b", repo)).toBe(true);
    expect(inGitRepo("/w", repo)).toBe(false);
    expect(inGitRepo("", repo)).toBe(false);
  });
});

describe("createRefresher", () => {
  test("a burst of events is one read, not one per event", async () => {
    let reads = 0;
    const r = createRefresher(async () => {
      reads++;
    }, 10);
    for (let i = 0; i < 50; i++) r.schedule();
    await new Promise((res) => setTimeout(res, 40));
    expect(reads).toBe(1);
    r.cancel();
  });
  test("a request during a read queues exactly one more", async () => {
    let reads = 0;
    let release: () => void = () => {};
    const r = createRefresher(
      () =>
        new Promise<void>((res) => {
          reads++;
          release = res;
        }),
      1
    );
    const first = r.now();
    r.schedule();
    r.schedule();
    await new Promise((res) => setTimeout(res, 10));
    release();
    await first;
    await new Promise((res) => setTimeout(res, 20));
    release();
    expect(reads).toBe(2);
    r.cancel();
  });
  test("cancel stops a pending read", async () => {
    let reads = 0;
    const r = createRefresher(async () => {
      reads++;
    }, 5);
    r.schedule();
    r.cancel();
    await new Promise((res) => setTimeout(res, 20));
    expect(reads).toBe(0);
  });
});
