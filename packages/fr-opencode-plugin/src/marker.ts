// Shared marker-resolution logic: given a file path, walk up to the nearest
// existing ancestor directory, resolve the git toplevel, decide whether the
// repo is "fr-enabled", and check for a valid .fr-isolation marker or
// .fr-isolation-allow escape. Extracted so both the deny path and any future
// caller (e.g. a status/debug tool) share one source of truth — mirrors
// fr-isolation-required.sh's own separation between marker lookup and the
// PreToolUse deny decision.
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, isAbsolute, relative } from "node:path";

export interface MarkerResolution {
  /** Absolute, symlink-resolved git toplevel of the target file's repo. */
  toplevel: string | null;
  /** Whether the repo has a devcontainer profile or a plans dir (fr-enabled). */
  frEnabled: boolean;
  /** True if a valid isolation marker allows edits at this toplevel. */
  hasValidMarker: boolean;
}

function realpath(path: string): string {
  try {
    return execFileSync("pwd", { cwd: path, shell: undefined }).toString().trim();
  } catch {
    return path;
  }
}

function nearestExistingAncestor(path: string): string | null {
  let dir = dirname(path);
  while (!existsSync(dir) && dir !== "/" && dir !== ".") {
    dir = dirname(dir);
  }
  return existsSync(dir) ? dir : null;
}

function gitToplevel(dir: string): string | null {
  try {
    const out = execFileSync("git", ["-C", dir, "rev-parse", "--show-toplevel"], {
      stdio: ["ignore", "pipe", "ignore"],
    })
      .toString()
      .trim();
    return out ? realpath(out) : null;
  } catch {
    return null;
  }
}

function isFrEnabled(toplevel: string): boolean {
  if (existsSync(`${toplevel}/docs/superpowers/plans`)) return true;
  try {
    const entries = execFileSync("bash", [
      "-c",
      `for cfg in "${toplevel}"/.devcontainer/*/devcontainer.json; do [ -f "$cfg" ] && echo found && break; done`,
    ])
      .toString()
      .trim();
    return entries === "found";
  } catch {
    return false;
  }
}

function gitDirsDiffer(toplevel: string): boolean {
  // A linked worktree has a distinct --git-dir from its --git-common-dir;
  // the primary working tree's git-dir IS its common-dir.
  try {
    const common = execFileSync("git", ["-C", toplevel, "rev-parse", "--git-common-dir"], {
      stdio: ["ignore", "pipe", "ignore"],
    })
      .toString()
      .trim();
    const gitdir = execFileSync("git", ["-C", toplevel, "rev-parse", "--git-dir"], {
      stdio: ["ignore", "pipe", "ignore"],
    })
      .toString()
      .trim();
    const rcommon = realpath(isAbsolute(common) ? common : `${toplevel}/${common}`);
    const rgitdir = realpath(isAbsolute(gitdir) ? gitdir : `${toplevel}/${gitdir}`);
    return rcommon !== rgitdir;
  } catch {
    return false;
  }
}

function hasContainerEvidence(): boolean {
  // external mode is a preparer's claim over its own checkout: require live
  // container evidence so a marker forged on a bare host never validates.
  // Mirrors the shell hook's `[ -f /.dockerenv ] || [ -f /run/.containerenv ]
  // || [ -n "$KUBERNETES_SERVICE_HOST" ]`.
  return (
    existsSync("/.dockerenv") ||
    existsSync("/run/.containerenv") ||
    !!process.env.KUBERNETES_SERVICE_HOST
  );
}

function hasValidIsolationMarker(toplevel: string): boolean {
  const markerPath = `${toplevel}/.fr-isolation`;
  if (!existsSync(markerPath)) return false;
  try {
    const marker = JSON.parse(readFileSync(markerPath, "utf-8")) as {
      toplevel?: string;
      mode?: string;
    };
    const mode = marker.mode ?? "worktree";
    // Both modes require the recorded toplevel to match (defeats a marker
    // copied elsewhere); then the mode branch decides.
    const recorded = marker.toplevel ? realpath(marker.toplevel) : "";
    if (recorded !== toplevel) return false;
    switch (mode) {
      case "worktree":
        // The toplevel must be a LINKED worktree (defeats a stale marker copied
        // into the primary tree).
        return gitDirsDiffer(toplevel);
      case "external":
        return hasContainerEvidence();
      default:
        // Any other mode fails CLOSED.
        return false;
    }
  } catch {
    return false;
  }
}

/** Simple glob match: `*` spans path segments, mirroring the shell hook's `[[ == ]]`. */
function globMatch(pattern: string, value: string): boolean {
  const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*");
  return new RegExp(`^${escaped}$`).test(value);
}

function matchesAllowlist(toplevel: string, file: string): boolean {
  const allowPath = `${toplevel}/.fr-isolation-allow`;
  if (!existsSync(allowPath)) return false;
  // Symlink-robust: resolve the file's existing-ancestor dir the same way
  // `toplevel` was resolved, so a macOS /tmp -> /private/tmp mismatch doesn't
  // make `relative()` walk outside toplevel and silently drop the escape
  // (mirrors the shell hook's `rdir=$(cd "$dir" && pwd -P)` step).
  const dir = nearestExistingAncestor(file);
  const rdir = dir ? realpath(dir) : dirname(file);
  const tail = dir ? file.slice(dir.length) : "";
  const rfile = `${rdir}${tail}`;
  const rel = relative(toplevel, rfile);
  if (rel.startsWith("..")) return false;
  const lines = readFileSync(allowPath, "utf-8").split("\n");
  for (const raw of lines) {
    const pattern = raw.trim();
    if (!pattern || pattern.startsWith("#")) continue;
    if (globMatch(pattern, rel)) return true;
  }
  return false;
}

/**
 * Resolve whether `file` may be edited: false only means "no verdict" (not
 * our concern — no toplevel, not fr-enabled). Callers combine this with
 * FR_BASE_OK and the allowlist to reach a final decision.
 */
export function resolveMarker(file: string): MarkerResolution {
  const dir = nearestExistingAncestor(file);
  if (!dir) return { toplevel: null, frEnabled: false, hasValidMarker: false };

  const toplevel = gitToplevel(dir);
  if (!toplevel) return { toplevel: null, frEnabled: false, hasValidMarker: false };

  const frEnabled = isFrEnabled(toplevel);
  if (!frEnabled) return { toplevel, frEnabled: false, hasValidMarker: false };

  return { toplevel, frEnabled: true, hasValidMarker: hasValidIsolationMarker(toplevel) };
}

export { matchesAllowlist };
