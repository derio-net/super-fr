// OpenCode 2 loads a plugin only as a definition — `export default { id, setup }`
// (spec 2026-10-20-opencode-2-support R1). The 1.x hook-object export was
// refused at load and left every gate inert.
import { describe, expect, test } from "bun:test";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import * as mod from "../src/index";
import { fakeCtx, load } from "./fake";

describe("V2 plugin definition", () => {
  test("the default export is a definition with an id and a setup function", () => {
    const plugin = mod.default as { id?: unknown; setup?: unknown };
    expect(typeof plugin.id).toBe("string");
    expect(typeof plugin.setup).toBe("function");
  });

  test("the module exports nothing but the definition", () => {
    expect(Object.keys(mod)).toEqual(["default"]);
  });

  test("setup returns a cleanup that aborts the event subscription", async () => {
    const { cleanup, subscribed } = await load();
    expect(typeof cleanup).toBe("function");
    expect(subscribed).toHaveLength(1);
    expect(subscribed[0]!.aborted).toBe(false);
    await (cleanup as () => void)();
    expect(subscribed[0]!.aborted).toBe(true);
  });

  test("setup registers exactly one of each hook it uses", async () => {
    const { hooks } = await load();
    expect([...hooks.keys()].sort()).toEqual([
      "session:context",
      "shell:create.before",
      "tool:execute.after",
      "tool:execute.before",
    ]);
  });

  test("setup survives a context with no event domain", async () => {
    const { ctx } = fakeCtx();
    const bare = { ...ctx, event: undefined };
    await expect(mod.default.setup(bare as never)).resolves.toBeFunction();
  });
});

// gh#1221: fail-open silently was the defect — with git unreachable the gates
// allow everything, and nothing said so. setup resolves git eagerly and warns
// ONCE per process (a reload runs setup again).
describe("setup's git warning (gh#1221)", () => {
  test("warns once at load when no candidate is executable, and stays quiet on reload", async () => {
    const savedPath = process.env.PATH;
    const savedCandidates = process.env.FR_GIT_CANDIDATES;
    const empty = mkdtempSync(join(tmpdir(), "fr-opencode-nogit-warn-"));
    const errors: string[] = [];
    const realError = console.error;
    console.error = (...args: unknown[]) => void errors.push(args.map(String).join(" "));
    try {
      process.env.PATH = empty;
      process.env.FR_GIT_CANDIDATES = join(empty, "no-such-git");
      const first = await load();
      await (first.cleanup as () => void)();
      const second = await load();
      await (second.cleanup as () => void)();
    } finally {
      console.error = realError;
      process.env.PATH = savedPath;
      if (savedCandidates === undefined) delete process.env.FR_GIT_CANDIDATES;
      else process.env.FR_GIT_CANDIDATES = savedCandidates;
      rmSync(empty, { recursive: true, force: true });
    }
    const warnings = errors.filter((line) => line.includes("no executable git found"));
    expect(warnings).toHaveLength(1);
    expect(warnings[0]).toContain("FAIL OPEN");
  });
});
