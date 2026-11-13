// The `fr` binary this plugin asks about artifact paths, resolved from PATH at CALL time
// (not at process start: a bare-name spawn can answer from the PATH the server started
// with) to one absolute file, the way ./git.ts resolves git. `null` when none is executable.
import { accessSync, constants, realpathSync } from "node:fs";
import { delimiter, isAbsolute, join } from "node:path";

export function resolveFr(env: { PATH?: string } = process.env): string | null {
  for (const dir of (env.PATH ?? "").split(delimiter)) {
    // A relative or empty entry is checked against THIS process's cwd but would be
    // executed from the repo toplevel: a different file, possibly one planted in the
    // repo being edited. Only absolute entries are trusted.
    if (!dir || !isAbsolute(dir)) continue;
    const full = join(dir, "fr");
    try {
      accessSync(full, constants.X_OK);
      return realpathSync(full); // spawn exactly the file that was checked
    } catch {
      // not here
    }
  }
  return null;
}
