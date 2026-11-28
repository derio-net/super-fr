// Preloaded before every test file (bunfig.toml): pin the pre-9.2 side of S1's transition
// (spec 2026-11-28-s1-followups R10). marker.ts reads its release from `VERSION` beside
// itself; in the source tree that falls back to this package's package.json, whose version
// moves with every release. So the suite reads a fixture VERSION of 9.1.0 instead, and a
// test of the ended side points marker.ts at its own fixture (test/transition.test.ts).
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { setVersionDir } from "../src/marker";

const open = mkdtempSync(join(tmpdir(), "fr-open-version-"));
writeFileSync(join(open, "VERSION"), "9.1.0\n");
setVersionDir(open);
delete process.env.FR_OLD_PATHS;

export const OPEN_VERSION_DIR = open;
