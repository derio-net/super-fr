// The `fr` binary this plugin spawns, resolved at CALL time (not at process start: a
// bare-name spawn can answer from the PATH the server started with) to one absolute
// file, the way ./git.ts resolves git. `null` when none is executable. The bash hooks
// resolve it the same way (lib/fr-isolation-decision.sh `fr_fr_resolve`, review p6-r2).
import { accessSync, constants, realpathSync, statSync } from "node:fs";
import { delimiter, isAbsolute, join } from "node:path";

import { run, type RunAnswer, type RunOptions } from "./spawn";

function executableFile(path: string): string | null {
  try {
    if (!statSync(path).isFile()) return null;
    accessSync(path, constants.X_OK);
    return realpathSync(path); // spawn exactly the file that was checked
  } catch {
    return null;
  }
}

export function resolveFr(
  // A string record, not `{ PATH?; FR_HARNESS_FR? }`: an all-optional object type is a
  // TypeScript "weak type", which `process.env` (index signature only) does not satisfy.
  env: Readonly<Record<string, string | undefined>> = process.env
): string | null {
  // A pin that is an absolute path to an executable file wins. The identity string
  // fr-binary-pin.sh and ./pin.ts export (`<version> <package dir>`) is not a path and
  // falls through to PATH.
  const pin = env.FR_HARNESS_FR;
  if (pin && isAbsolute(pin)) {
    const pinned = executableFile(pin);
    if (pinned !== null) return pinned;
  }
  for (const dir of (env.PATH ?? "").split(delimiter)) {
    // A relative or empty entry is checked against THIS process's cwd but would be
    // executed from the repo toplevel: a different file, possibly one planted in the
    // repo being edited. Only absolute entries are trusted.
    if (!dir || !isAbsolute(dir)) continue;
    const found = executableFile(join(dir, "fr"));
    if (found !== null) return found;
  }
  return null;
}

/** The missing-fr answer: nothing ran, so there is no exit status and no output. */
export const NO_FR: RunAnswer = { code: null, stdout: "" };

/**
 * `fr <args…>` through the file `resolveFr()` names at CALL time, never a bare `fr` that a
 * relative PATH entry could answer from the repo's own directory. No trusted fr: `NO_FR`,
 * with nothing spawned. Bounded and never throwing, like `run`.
 */
export async function runFr(args: string[], options: RunOptions): Promise<RunAnswer> {
  const fr = resolveFr();
  return fr === null ? NO_FR : run(fr, args, options);
}
