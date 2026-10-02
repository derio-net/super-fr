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
  /**
   * Set when a worktree-mode marker records a branch and HEAD is a different
   * branch (gh#553) — the marker is then invalid, and the deny names both.
   */
  drift?: BranchDrift;
}

export interface BranchDrift {
  marker: string;
  head: string;
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

/**
 * The marker's `branch` vs. the branch HEAD has checked out (gh#553). fr's
 * state is keyed on the marker's branch, so a `git checkout -b` inside the
 * workspace silently decouples the two. A detached HEAD (mid-rebase, bisect)
 * is not another branch, and a marker with no `branch` has nothing to compare:
 * neither is drift. Mirrors the shell hook's `_fr_branch_drift`.
 */
function branchDrift(toplevel: string, markerBranch: string | undefined): BranchDrift | undefined {
  if (!markerBranch) return undefined;
  let head: string;
  try {
    head = execFileSync("git", ["-C", toplevel, "symbolic-ref", "--quiet", "--short", "HEAD"], {
      stdio: ["ignore", "pipe", "ignore"],
    })
      .toString()
      .trim();
  } catch {
    return undefined;
  }
  return head && head !== markerBranch ? { marker: markerBranch, head } : undefined;
}

function readMarker(toplevel: string): { toplevel?: string; mode?: string; branch?: string } | null {
  try {
    return JSON.parse(readFileSync(`${toplevel}/.fr-isolation`, "utf-8"));
  } catch {
    return null;
  }
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
        // into the primary tree), on the branch the marker records.
        return gitDirsDiffer(toplevel) && !branchDrift(toplevel, (marker as { branch?: string }).branch);
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

  const hasValidMarker = hasValidIsolationMarker(toplevel);
  if (hasValidMarker) return { toplevel, frEnabled: true, hasValidMarker };
  const marker = existsSync(`${toplevel}/.fr-isolation`) ? readMarker(toplevel) : null;
  const drift =
    marker && (marker.mode ?? "worktree") === "worktree" ? branchDrift(toplevel, marker.branch) : undefined;
  return { toplevel, frEnabled: true, hasValidMarker, drift };
}

export { matchesAllowlist };
