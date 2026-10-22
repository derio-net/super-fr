// OpenCode 2 loads a plugin only as a definition — `export default { id, setup }`
// (spec 2026-10-20-opencode-2-support R1). The 1.x hook-object export was
// refused at load and left every gate inert.
import { describe, expect, test } from "bun:test";

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
