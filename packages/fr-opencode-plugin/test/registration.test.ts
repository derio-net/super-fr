// Registration control regression, NOT a real server/loader smoke. Mirrors
// 2.1.4 (68bc26b7) config/plugin/source.ts and plugin/supervisor.ts:
// discover first, explicit config last; filter disabled IDs BEFORE duplicate
// detection and setup. Hook execution below uses the real source definition.
import { expect, test } from "bun:test";
import { execFileSync } from "node:child_process";
import { cpSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import globalPlugin from "../src/index";
import projectPlugin from "../../../.opencode/plugins/fr-isolation-required";
import { fakeCtx } from "./fake";

type Definition = typeof globalPlugin;
const config = JSON.parse(readFileSync(new URL("../../../opencode.json", import.meta.url), "utf8"));

function select(discovered: Definition[], controls: string[]): Definition[] {
  const enabled = new Set(discovered.map((p) => p.id));
  for (const control of controls) {
    if (control.startsWith("-")) enabled.delete(control.slice(1));
    else enabled.add(control);
  }
  const selected = discovered.filter((p) => enabled.has(p.id));
  const ids = new Set<string>();
  for (const p of selected) {
    if (ids.has(p.id)) throw new Error(`Duplicate plugin ID: ${p.id}`);
    ids.add(p.id);
  }
  return selected;
}

test("control catches the original duplicate before setup", () => {
  expect(() => select([globalPlugin, globalPlugin], [])).toThrow("Duplicate plugin ID: super-fr");
});

test("global use outside this repository is unchanged", () => {
  expect(globalPlugin.id).toBe("super-fr");
  expect(select([globalPlugin], [])).toEqual([globalPlugin]);
});

test("the explicit control is necessary: distinct IDs alone leave two guard owners", () => {
  expect(select([globalPlugin, projectPlugin], [])).toHaveLength(2);
  expect(config.plugins).toEqual(["-super-fr"]);
});

for (const order of ["global-first", "project-first", "repo-only"] as const) {
  test(`${order}: selects source guards once, including a separately delivered module`, async () => {
    const root = mkdtempSync(join(tmpdir(), "fr-registration-"));
    try {
      // Separate module paths, as installed copies do not share module identity.
      const delivered = join(root, "installed");
      cpSync(new URL("../src", import.meta.url), delivered, { recursive: true });
      const installed = (await import(join(delivered, "index.ts"))).default as Definition;
      expect(installed).not.toBe(globalPlugin);
      const discovered = order === "repo-only" ? [projectPlugin]
        : order === "global-first" ? [installed, projectPlugin] : [projectPlugin, installed];
      const selected = select(discovered, config.plugins ?? []);
      expect(selected).toEqual([projectPlugin]);
      expect(projectPlugin.id).not.toBe(installed.id);
      expect(projectPlugin.setup).toBe(globalPlugin.setup);

      execFileSync("git", ["init", "--quiet", root]);
      mkdirSync(join(root, "docs/superpowers/plans"), { recursive: true });
      writeFileSync(join(root, "source.ts"), "// protected\n");
      const fake = fakeCtx({ directory: root });
      const cleanup = await selected[0]!.setup(fake.ctx as never);
      try {
        // Exactly one handler for EVERY action, not just deduplicated idle/nag.
        expect(fake.hooks.size).toBe(4);
        for (const handlers of fake.hooks.values()) expect(handlers).toHaveLength(1);
        expect(fake.subscribed).toHaveLength(1);
        const gate = fake.hooks.get("tool:execute.before")![0]!;
        await expect(gate({ tool: "edit", sessionID: "", input: { filePath: join(root, "source.ts") } } as never))
          .rejects.toThrow("fr-isolation");
        await expect(gate({ tool: "read", sessionID: "", input: { path: join(root, "source.ts") } } as never))
          .resolves.toBeUndefined();
      } finally {
        await (cleanup as () => void)();
      }
      expect(fake.subscribed[0]!.aborted).toBe(true);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
}
