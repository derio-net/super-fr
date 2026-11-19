// One way to find a helper binary this plugin spawns: from ABSOLUTE PATH entries,
// then from a few absolute default directories, never by bare name.
//
// The plugin runs inside an OpenCode server it does not control and spawns with no
// shell, so spawning a bare `gh` searches whatever PATH that server inherited,
// relative entries included: a relative or empty entry names a file in whatever
// directory the server runs from, possibly one planted in the repo (super-fr#1481).
// `git` (src/git.ts) and `fr` (src/fr.ts) were already resolved this way; `bash` (the
// status line) and `gh` (the push guard) now are too. The bash hooks do the same in
// `plugins/super-fr/hooks/lib/fr-isolation-decision.sh` (`fr_which`).
import { accessSync, constants, statSync } from "node:fs";
import { delimiter, isAbsolute, join } from "node:path";

/** Where a tool lives when PATH does not name it, in the bash library's order. */
export const DEFAULT_TOOL_DIRS = ["/usr/local/bin", "/usr/bin", "/bin", "/opt/homebrew/bin"] as const;

export type ToolEnv = { PATH?: string; [key: string]: string | undefined };

/** An executable regular file. */
export function executable(path: string): boolean {
  try {
    if (!statSync(path).isFile()) return false;
    accessSync(path, constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

/** The first executable `<dir>/<name>` over PATH's ABSOLUTE entries, or undefined. */
export function onPath(name: string, env: ToolEnv): string | undefined {
  for (const dir of (env.PATH ?? "").split(delimiter)) {
    // Only an absolute entry: a relative or empty one names a file in whatever
    // directory this process happens to run from, possibly one planted in the repo.
    if (!dir || !isAbsolute(dir)) continue;
    const full = join(dir, name);
    if (executable(full)) return full;
  }
  return undefined;
}

/** The absolute path of `name` to spawn, or `null` when none is trusted. */
export function resolveTool(
  name: string,
  env: ToolEnv = process.env,
  fallbacks: readonly string[] = DEFAULT_TOOL_DIRS
): string | null {
  const found = onPath(name, env);
  if (found !== undefined) return found;
  for (const dir of fallbacks) {
    const full = join(dir, name);
    if (executable(full)) return full;
  }
  return null;
}
