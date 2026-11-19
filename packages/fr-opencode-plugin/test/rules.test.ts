// The shipped rules, injected once per request (consumer-delivery R2).
import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { createRulesHandler } from "../src/rules";

let dir: string;
beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "fr-rules-"));
});
afterEach(() => rmSync(dir, { recursive: true, force: true }));

const ev = (system: unknown[] = []) => ({ sessionID: "ses_1", system });
const texts = (system: unknown[]) => system.map((p) => (p as { text: string }).text);

describe("createRulesHandler", () => {
  test("appends each rule in name order", async () => {
    writeFileSync(join(dir, "b.md"), "RULE B\n");
    writeFileSync(join(dir, "a.md"), "RULE A\n");
    writeFileSync(join(dir, "skip.txt"), "NOT A RULE");
    const event = ev();
    await createRulesHandler({ rulesDir: dir })(event);
    expect(texts(event.system)).toEqual(["RULE A\n", "RULE B\n"]);
  });

  test("a system that already holds the texts gets nothing (kept between requests)", async () => {
    writeFileSync(join(dir, "a.md"), "RULE A\n");
    const handler = createRulesHandler({ rulesDir: dir });
    const event = ev();
    await handler(event);
    await handler(event);
    expect(event.system).toHaveLength(1);
  });

  test("a second handler instance over the same event appends nothing", async () => {
    writeFileSync(join(dir, "a.md"), "RULE A\n");
    const event = ev();
    await createRulesHandler({ rulesDir: dir })(event);
    await createRulesHandler({ rulesDir: dir })(event);
    expect(event.system).toHaveLength(1);
  });

  test("a rule an instructions loader already wrote inside a longer part is not repeated", async () => {
    writeFileSync(join(dir, "a.md"), "RULE A\n");
    const event = ev([{ type: "text", text: "Instructions from: /x/a.md\nRULE A\n\nmore" }]);
    await createRulesHandler({ rulesDir: dir })(event);
    expect(event.system).toHaveLength(1);
  });

  test("a string part counts too", async () => {
    writeFileSync(join(dir, "a.md"), "RULE A\n");
    const event = ev(["prefix RULE A suffix"]);
    await createRulesHandler({ rulesDir: dir })(event);
    expect(event.system).toHaveLength(1);
  });

  test("a missing dir, an empty dir and an unreadable file add nothing", async () => {
    const e1 = ev();
    await createRulesHandler({ rulesDir: join(dir, "nope") })(e1);
    expect(e1.system).toEqual([]);
    const empty = join(dir, "empty");
    mkdirSync(empty);
    const e2 = ev();
    await createRulesHandler({ rulesDir: empty })(e2);
    expect(e2.system).toEqual([]);
    writeFileSync(join(dir, "ok.md"), "OK");
    writeFileSync(join(dir, "bad.md"), "BAD");
    const readFile = (p: string): string => {
      if (p.endsWith("bad.md")) throw new Error("EACCES");
      return readFileSync(p, "utf8");
    };
    const e3 = ev();
    await createRulesHandler({ rulesDir: dir, readFile, warn: () => {} })(e3);
    expect(texts(e3.system)).toEqual(["OK"]);
  });

  test("an instructions part naming the same rule file counts, even when its text differs (version skew)", async () => {
    writeFileSync(join(dir, "fr-isolation-required.md"), "NEW TEXT\n");
    const event = ev(["Instructions from: /repo/.opencode/instructions/fr-isolation-required.md\nOLD TEXT"]);
    await createRulesHandler({ rulesDir: dir })(event);
    expect(event.system).toHaveLength(1);
  });

  test("a header naming a different file with the same suffix does not count", async () => {
    writeFileSync(join(dir, "required.md"), "ZQX-RULE\n");
    const event = ev(["Instructions from: /repo/x/fr-isolation-required.md\nOTHER"]);
    await createRulesHandler({ rulesDir: dir })(event);
    expect(texts(event.system)).toContain("ZQX-RULE\n");
  });

  test("never throws on a non-array system or a failing fs", async () => {
    writeFileSync(join(dir, "a.md"), "A");
    await createRulesHandler({ rulesDir: dir })({ sessionID: "s", system: "nope" });
    await createRulesHandler({ rulesDir: dir })(null);
    await createRulesHandler({ rulesDir: dir })(undefined);
    await createRulesHandler({
      rulesDir: dir,
      readdir: () => {
        throw new Error("boom");
      },
      warn: () => {},
    })(ev());
  });

  describe("load failures (l-errors-r4)", () => {
    const enoent = () => {
      const e = new Error("ENOENT: no such file or directory") as Error & { code: string };
      e.code = "ENOENT";
      throw e;
    };

    test("a missing rules dir is silent: the in-tree plugin's designed state", async () => {
      const lines: string[] = [];
      await createRulesHandler({ rulesDir: join(dir, "nope"), warn: (l) => lines.push(l) })(ev());
      await createRulesHandler({ rulesDir: dir, readdir: enoent, warn: (l) => lines.push(l) })(ev());
      expect(lines).toEqual([]);
    });

    test("a listing that fails for another reason warns once per request, naming the dir, and is retried", async () => {
      const lines: string[] = [];
      let calls = 0;
      const readdir = (d: string): string[] => {
        calls += 1;
        if (calls === 1) {
          const e = new Error("EACCES: permission denied") as Error & { code: string };
          e.code = "EACCES";
          throw e;
        }
        return ["a.md"];
      };
      writeFileSync(join(dir, "a.md"), "RULE A\n");
      const handler = createRulesHandler({ rulesDir: dir, readdir, warn: (l) => lines.push(l) });
      const e1 = ev();
      await handler(e1);
      expect(e1.system).toEqual([]);
      expect(lines).toHaveLength(1);
      expect(lines[0]).toContain(dir);
      expect(lines[0]).toContain("EACCES");
      const e2 = ev();
      await handler(e2);
      expect(texts(e2.system)).toEqual(["RULE A\n"]);
      expect(lines).toHaveLength(1);
    });

    test("an unreadable rule file warns naming the file, and the load is not cached", async () => {
      writeFileSync(join(dir, "ok.md"), "OK");
      writeFileSync(join(dir, "bad.md"), "BAD");
      const lines: string[] = [];
      let fail = true;
      const readFile = (p: string): string => {
        if (fail && p.endsWith("bad.md")) throw new Error("EIO");
        return readFileSync(p, "utf8");
      };
      const handler = createRulesHandler({ rulesDir: dir, readFile, warn: (l) => lines.push(l) });
      const e1 = ev();
      await handler(e1);
      expect(texts(e1.system)).toEqual(["OK"]);
      expect(lines).toHaveLength(1);
      expect(lines[0]).toContain(join(dir, "bad.md"));
      fail = false;
      const e2 = ev();
      await handler(e2);
      expect(texts(e2.system)).toEqual(["BAD", "OK"]);
    });

    test("the default warning goes to stderr", async () => {
      const seen: unknown[] = [];
      const orig = console.error;
      console.error = (...a: unknown[]) => void seen.push(a.join(" "));
      try {
        await createRulesHandler({
          rulesDir: dir,
          readdir: () => {
            throw new Error("boom");
          },
        })(ev());
      } finally {
        console.error = orig;
      }
      expect(seen).toHaveLength(1);
      expect(String(seen[0])).toContain(dir);
    });
  });

  test("OpenCode's own instructions part (v2.3.0 format, several files in one part) counts", async () => {
    // The exact renderer in the opencode v2.3.0 binary:
    //   `Instructions from: ${path}\n${content}`, joined by "\n\n".
    writeFileSync(join(dir, "fr-plan-override.md"), "NEW PLAN TEXT\n");
    writeFileSync(join(dir, "docs-currency.md"), "DOCS RULE\n");
    const part = [
      "Instructions from: /home/u/repo/AGENTS.md\n# agents",
      "Instructions from: /home/u/repo/.opencode/instructions/fr-plan-override.md\nOLD PLAN TEXT",
    ].join("\n\n");
    const event = ev([{ type: "text", text: part }]);
    await createRulesHandler({ rulesDir: dir })(event);
    expect(texts(event.system)).toEqual([part, "DOCS RULE\n"]);
  });
});
