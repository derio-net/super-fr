// The `fr` binary this plugin asks about artifact paths, resolved from PATH at CALL time
// (not at process start: a bare-name spawn can answer from the PATH the server started
// with) to one absolute file, the way ./git.ts resolves git. `null` when none is executable.
import { accessSync, constants } from "node:fs";
import { delimiter, join } from "node:path";

export function resolveFr(env: { PATH?: string } = process.env): string | null {
  for (const dir of (env.PATH ?? "").split(delimiter)) {
    if (!dir) continue;
    const full = join(dir, "fr");
    try {
      accessSync(full, constants.X_OK);
      return full;
    } catch {
      // not here
    }
  }
  return null;
}
