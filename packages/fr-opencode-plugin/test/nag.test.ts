// The acceptance nag (spec 2026-10-20-opencode-2-support R9).
import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { mkdirSync, mkdtempSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { createNagHandler } from "../src/nag";
import type { RunAnswer } from "../src/spawn";

let repo: string;

beforeEach(() => {
  repo = realpathSync(mkdtempSync(join(tmpdir(), "fr-nag-")));
  mkdirSync(join(repo, ".git"));
  mkdirSync(join(repo, "docs", "acceptance"), { recursive: true });
  writeFileSync(join(repo, "docs", "acceptance", "matrix.yaml"), "rows: []\n");
});

afterEach(() => rmSync(repo, { recursive: true, force: true }));

const topLevel = { get: async ({ sessionID }: { sessionID: string }) => ({ id: sessionID }) };

function stub(answer: RunAnswer) {
  const calls: { cwd: string; args: string[] }[] = [];
  const runFr = async (cwd: string, args: string[]) => {
    calls.push({ cwd, args });
    return answer;
  };
  return { calls, runFr };
}

const ctxEvent = (sessionID = "ses_1") => ({ sessionID, system: [] as { type: "text"; text: string }[] });

describe("acceptance nag", () => {
  test("serves one system part per top-level session, never rewriting the prompt", async () => {
    const { calls, runFr } = stub({ code: 0, stdout: "3 rows owe a walk\n" });
    const nag = createNagHandler({ session: topLevel, directory: join(repo, "docs"), runFr });
    const first = ctxEvent();
    await nag(first);
    expect(first.system).toEqual([
      {
        type: "text",
        text: "Acceptance debt in this repo (backfill owed — details: fr acceptance status):\n3 rows owe a walk\n",
      },
    ]);
    expect(calls).toEqual([{ cwd: repo, args: ["acceptance", "status", "--brief"] }]);
    const second = ctxEvent();
    await nag(second);
    expect(second.system).toEqual([]);
    expect(calls.length).toBe(1);
  });

  test("a child session is skipped", async () => {
    const { calls, runFr } = stub({ code: 0, stdout: "debt\n" });
    const session = { get: async ({ sessionID }: { sessionID: string }) => ({ id: sessionID, parentID: "ses_p" }) };
    const event = ctxEvent();
    await createNagHandler({ session, directory: repo, runFr })(event);
    expect(event.system).toEqual([]);
    expect(calls.length).toBe(0);
  });

  test("no matrix: returns before spawning anything", async () => {
    rmSync(join(repo, "docs", "acceptance", "matrix.yaml"));
    const { calls, runFr } = stub({ code: 0, stdout: "debt\n" });
    const event = ctxEvent();
    await createNagHandler({ session: topLevel, directory: repo, runFr })(event);
    expect(calls.length).toBe(0);
    expect(event.system).toEqual([]);
  });

  test("no debt, empty output, failure and a timeout are all silent", async () => {
    for (const answer of [
      { code: 0, stdout: "no acceptance debt\n" },
      { code: 0, stdout: "" },
      { code: 1, stdout: "", stderr: "boom" },
      { code: null, stdout: "" },
    ]) {
      const { runFr } = stub(answer);
      const event = ctxEvent();
      await createNagHandler({ session: topLevel, directory: repo, runFr })(event);
      expect(event.system).toEqual([]);
    }
  });

  test("a stale-artifact refusal says why the nag is missing", async () => {
    const { runFr } = stub({ code: 2, stdout: "", stderr: "fr: artifacts … must be migrated" });
    const event = ctxEvent();
    await createNagHandler({ session: topLevel, directory: repo, runFr })(event);
    expect(event.system).toEqual([
      { type: "text", text: "acceptance nag skipped: artifacts stale — run `fr migrate artifacts --yes`\n" },
    ]);
  });

  test("never throws", async () => {
    const session = {
      get: async () => {
        throw new Error("lookup");
      },
    };
    const nag = createNagHandler({ session, directory: repo, runFr: stub({ code: 0, stdout: "x" }).runFr });
    await expect(nag(ctxEvent())).resolves.toBeUndefined();
    await expect(nag(null as never)).resolves.toBeUndefined();
    const throwing = createNagHandler({
      session: topLevel,
      directory: repo,
      runFr: async () => {
        throw new Error("spawn");
      },
    });
    await expect(throwing(ctxEvent())).resolves.toBeUndefined();
  });
});
