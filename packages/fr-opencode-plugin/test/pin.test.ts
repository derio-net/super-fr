// The fr-binary pin (super-fr#746): the plugin exports the fr IT resolves —
// `fr --identity`, spawned from OpenCode's own PATH with no shell — into every
// `bash` command as FR_HARNESS_FR, so fr can refuse when the shell's `zsh -c`
// (which re-reads ~/.zshenv) reached a different one.
//
// WHAT THIS FILE DOES NOT PROVE: that OpenCode merges the env into a live
// `bash` call; the handler is driven directly, so the parity cell is `partial`.
import { describe, expect, test } from "bun:test";

import { createPinHandler, PIN_ENV_KEY } from "../src/pin";

const ID = "5.5.0 /opt/fr/site-packages/fr";

describe("shell.env fr-binary pin", () => {
  test("exports the identity the plugin's fr reports", async () => {
    const handler = createPinHandler({ identify: async () => ID });
    const output = { env: { KEEP: "1" } as Record<string, string> };
    await handler({ cwd: "/w" }, output);
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
    for (let i = 0; i < 3; i += 1) await handler({ cwd: "/w" }, { env: {} });
    expect(calls).toBe(1);
  });

  test("pins nothing when fr is missing, too old, or says nothing", async () => {
    for (const identify of [async () => undefined, async () => "", async () => { throw new Error("x"); }]) {
      const output = { env: { KEEP: "1" } as Record<string, string> };
      await createPinHandler({ identify })({ cwd: "/w" }, output);
      expect(output.env).toEqual({ KEEP: "1" });
    }
  });

  test("keeps only the first line and creates a missing env object", async () => {
    const output = {} as { env?: Record<string, string> };
    await createPinHandler({ identify: async () => `${ID}\nnoise\n` })({ cwd: "/w" }, output as never);
    expect(output.env).toEqual({ [PIN_ENV_KEY]: ID });
  });

  test("never throws", async () => {
    await createPinHandler({ identify: async () => ID })({ cwd: "/w" }, undefined as never);
  });
});
