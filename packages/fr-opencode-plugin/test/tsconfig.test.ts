// p3-r9: exactly ONE file escapes `tsc` (the TUI entry, whose JSX types live
// in packages the opencode binary bundles). A second excluded file has to be
// argued for in a diff to this test, never slip in through a glob.
import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

test("tsconfig excludes exactly src/tui/index.tsx", () => {
  const config = JSON.parse(readFileSync(join(import.meta.dir, "..", "tsconfig.json"), "utf8"));
  expect(config.exclude).toEqual(["src/tui/index.tsx"]);
});
