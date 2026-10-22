// The fr-binary pin (super-fr#746): the plugin exports the fr IT resolves —
// `fr --identity`, spawned from OpenCode's own PATH with no shell — into every
// shell command as FR_HARNESS_FR (OpenCode 2: the shell `create.before` event's `env`), so fr can refuse when the shell's `zsh -c`
// (which re-reads ~/.zshenv) reached a different one.
//
// WHAT THIS FILE DOES NOT PROVE: that OpenCode merges the env into a live
// `bash` call; the handler is driven directly, so the parity cell is `partial`.
import { describe, expect, test } from "bun:test";

import { createPinHandler, PIN_ENV_KEY } from "../src/pin";
import { load } from "./fake";

const ID = "5.5.0 /opt/fr/site-packages/fr";

describe("create.before fr-binary pin", () => {
  test("exports the identity the plugin's fr reports", async () => {
    const handler = createPinHandler({ identify: async () => ID });
    const output = { env: { KEEP: "1" } as Record<string, string> };
    await handler(output);
    expect(output.env).toEqual({ KEEP: "1", [PIN_ENV_KEY]: ID });
  });

  test("asks fr once, however many commands run", async () => {
    let calls = 0;
    const handler = createPinHandler({
      identify: async () => {
        calls += 1;
        return ID;
      },
    });
    for (let i = 0; i < 3; i += 1) await handler({ env: {} });
    expect(calls).toBe(1);
  });

  test("pins nothing when fr is missing, too old, or says nothing", async () => {
    for (const identify of [async () => undefined, async () => "", async () => { throw new Error("x"); }]) {
      const output = { env: { KEEP: "1" } as Record<string, string> };
      await createPinHandler({ identify })(output);
      expect(output.env).toEqual({ KEEP: "1" });
    }
  });

  test("keeps only the first line and creates a missing env object", async () => {
    const output = {} as { env?: Record<string, string> };
    await createPinHandler({ identify: async () => `${ID}\nnoise\n` })(output as never);
    expect(output.env).toEqual({ [PIN_ENV_KEY]: ID });
  });

  test("never throws", async () => {
    await createPinHandler({ identify: async () => ID })(undefined as never);
    const frozen = { env: Object.freeze({}) as Record<string, string> };
    await createPinHandler({ identify: async () => ID })(frozen);
    expect(frozen.env).toEqual({});
  });

  test("is registered on the plugin's shell create.before hook", async () => {
    const { createBefore } = await load();
    const event = { command: "git status", cwd: "/w", timeout: 1, shell: "/bin/zsh", env: {} as Record<string, string> };
    await expect(createBefore(event)).resolves.toBeUndefined();
  });
});
