// One resolved `git`, and one bounded way to call it.
//
// git is this plugin's other load-bearing dependency (the bash guard's words),
// and it fails in the same silent way: with git unreachable every toplevel and
// common-dir probe is undefined, so the edit and shell gates degrade to "allow"
// — the bash guard's documented fail-open posture. gh#1221 is that this plugin
// reached it by accident, with a bare `git` from a PATH it does not control,
// while `plugins/super-fr/hooks/lib/fr-isolation-decision.sh` resolves one
// absolute binary through `FR_GIT_CANDIDATES` for exactly the reason gh#746
// pinned `fr`: hooks and this plugin spawn with no shell, so PATH is whatever
// the server inherited.
//
// So: resolve ONCE (cached by the environment that produced the answer), from
// the same candidate list and order as the bash guard, and run every call
// through `spawn.runSync` — bounded (SIGKILL on expiry) and never throwing.
// `setup` calls `resolveGit` eagerly and says so when it comes back empty; the
// gates themselves stay fail-open, deliberately, matching the bash guard.
import { accessSync, constants } from "node:fs";
import { delimiter, isAbsolute, join } from "node:path";

import { runSync } from "./spawn";

export const GIT_TIMEOUT_MS = 5_000;

/** The bash guard's default list, in its order: a bare name (PATH lookup) first,
 * then absolute locations, so a PATH that dropped `/usr/bin` still finds git. */
export const DEFAULT_GIT_CANDIDATES = [
  "git",
  "/usr/bin/git",
  "/usr/local/bin/git",
  "/bin/git",
  "/opt/homebrew/bin/git",
] as const;

/** The two keys this module reads. The index signature is what lets a real
 * `process.env` be passed directly — a weak type of only-optional keys is not
 * assignable from `ProcessEnv` (TS2559). */
export type GitEnv = { PATH?: string; FR_GIT_CANDIDATES?: string; [key: string]: string | undefined };

function candidates(env: GitEnv): string[] {
  const raw = env.FR_GIT_CANDIDATES;
  const words = raw ? raw.trim().split(/\s+/).filter(Boolean) : [];
  return words.length > 0 ? words : [...DEFAULT_GIT_CANDIDATES];
}

function executable(path: string): boolean {
  try {
    accessSync(path, constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

function onPath(name: string, env: GitEnv): string | undefined {
  for (const dir of (env.PATH ?? "").split(delimiter)) {
    if (!dir) continue;
    const full = join(dir, name);
    if (executable(full)) return full;
  }
  return undefined;
}

let cached: { key: string; bin: string | null } | undefined;

/**
 * The `git` this process will run, or `null` when none of the candidates is
 * executable. Cached per `(FR_GIT_CANDIDATES, PATH)` pair, so a caller that
 * changes either — a test, or the plugin reloaded in a session whose PATH it
 * inherited differently — gets a fresh answer without a reset hook.
 */
export function resolveGit(env: GitEnv = process.env): string | null {
  const key = `${env.FR_GIT_CANDIDATES ?? ""}\u0000${env.PATH ?? ""}`;
  if (cached?.key === key) return cached.bin;
  let bin: string | null = null;
  for (const candidate of candidates(env)) {
    if (isAbsolute(candidate)) {
      if (executable(candidate)) {
        bin = candidate;
        break;
      }
      continue;
    }
    const found = onPath(candidate, env);
    if (found !== undefined) {
      bin = found;
      break;
    }
  }
  cached = { key, bin };
  return bin;
}

/**
 * `git -C <dir> <args…>` as trimmed stdout, or `undefined` when git is
 * unresolvable, the call times out, or git exits non-zero (a non-repository, a
 * missing ref — all one "no answer"). Never throws.
 */
export function git(dir: string, ...args: string[]): string | undefined {
  const bin = resolveGit();
  if (bin === null) return undefined;
  const out = runSync(bin, ["-C", dir, ...args], { timeoutMs: GIT_TIMEOUT_MS });
  if (out.code !== 0) return undefined;
  const text = out.stdout.trim();
  return text === "" ? undefined : text;
}
