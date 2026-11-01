// The acceptance nag (spec 2026-10-20-opencode-2-support R9).
import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { mkdirSync, mkdtempSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { createNagHandler, sharedServed } from "../src/nag";
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

const STALE_SKIPPED =
  "acceptance nag skipped: artifacts stale — in an fr-isolation workspace (`fr isolation up --branch <branch>`) " +
  "the next fr command migrates and commits them; elsewhere run `fr migrate artifacts --yes` on a branch\n";

const ctxEvent = (sessionID = "ses_1") => ({ sessionID, system: [] as { type: "text"; text: string }[] });

describe("acceptance nag", () => {
  test("shares its once-per-session memory between loaded copies of the plugin", async () => {
    // OpenCode 2 scans the plugins directory for DIRECTORIES too, so the delivered
    // plugin can load twice (phase-1 finding p1-v2-loads-sources-dir-as-plugin);
    // each copy registers its own context hook. Module state is per copy, so only
    // a process-wide memory keeps R9's "one system part" true.
    const { calls, runFr } = stub({ code: 0, stdout: "rows\n" });
    const served = sharedServed();
    served.clear();
    const first = createNagHandler({ session: topLevel, directory: repo, runFr, served });
    const second = createNagHandler({ session: topLevel, directory: repo, runFr, served });

    const a = ctxEvent("ses_shared");
    await first(a);
    const b = ctxEvent("ses_shared");
    await second(b);

    expect(calls).toHaveLength(1);
    expect(a.system).toHaveLength(1);
    expect(b.system).toEqual([]);
  });

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
      { type: "text", text: STALE_SKIPPED },
    ]);
  });

  test("a stale refusal names the fr-isolation workspace and the manual migration", async () => {
    const { runFr } = stub({ code: 2, stdout: "", stderr: "fr: artifacts in . … must be migrated" });
    const event = ctxEvent();
    await createNagHandler({ session: topLevel, directory: repo, runFr })(event);
    const text = event.system[0]?.text ?? "";
    expect(text).toContain("fr-isolation workspace");
    expect(text).toContain("fr isolation up --branch");
    expect(text).toContain("fr migrate artifacts --yes");
  });

  test("the gate's commit notice is relayed first (R11)", async () => {
    const notice = "fr: migrated and committed 2 artifact(s): chore(fr): migrate 2 plans to fr 9.9.9 (abc1234)";
    const { runFr } = stub({
      code: 0,
      stdout: "1 row owes a walk: debt-0\n",
      stderr: `fr: artifacts in . are out of date — migrating before running the command.\n${notice}\n`,
    });
    const event = ctxEvent();
    await createNagHandler({ session: topLevel, directory: repo, runFr })(event);
    expect(event.system.length).toBe(1);
    expect(event.system[0].text.startsWith(`${notice}\n`)).toBe(true);
    expect(event.system[0].text).toContain("debt-0");

    const quiet = stub({ code: 0, stdout: "no acceptance debt\n", stderr: `${notice}\n` });
    const second = ctxEvent("ses_2");
    await createNagHandler({ session: topLevel, directory: repo, runFr: quiet.runFr })(second);
    expect(second.system).toEqual([{ type: "text", text: `${notice}\n` }]);
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
