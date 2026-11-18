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
    await createRulesHandler({ rulesDir: dir, readFile })(e3);
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
    })(ev());
  });
});
