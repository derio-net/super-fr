// Shared marker-resolution logic: given a file path, walk up to the nearest
// existing ancestor directory, resolve the git toplevel, decide whether the
// repo is "fr-enabled", and check for a valid .fr-isolation marker or
// .fr-isolation-allow escape. Extracted so both the deny path and any future
// caller (e.g. a status/debug tool) share one source of truth — mirrors
// fr-isolation-required.sh's own separation between marker lookup and the
// PreToolUse deny decision.
//
// Every probe here is BOUNDED and resolved, never a bare spawn on the edit
// path (gh#1221): git comes from ./git (one explicit binary, SIGKILL on
// timeout), and the directory/name checks are Node syscalls rather than `pwd`/
// `bash` subprocesses that could stall the server for the whole session.
//
// FAIL-OPEN, DELIBERATELY. When git cannot be resolved or times out, this
// resolution has no verdict — `toplevel` is null and the caller allows the
// edit. That is exactly what the bash guard does when git is unreachable (its
// `_fr_toplevel_of` returns non-zero and the edit decision allows), so the two
// engines agree. It is a recorded choice, not the accident it was: an edit gate
// that guessed "deny" on unknown filesystem state would block work in repos it
// knows nothing about, and it is a discipline backstop, not a security
// boundary. `setup` warns once at load when git is missing, so the fail-open
// state is visible rather than silent.
import { existsSync, readFileSync, readdirSync, realpathSync, statSync } from "node:fs";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";

import { resolveFr } from "./fr";
import { git } from "./git";
import { runSync } from "./spawn";

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
    return realpathSync(path);
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
  const out = git(dir, "rev-parse", "--show-toplevel");
  return out ? realpath(out) : null;
}

/** Bound for the one `fr settings paths --json --no-create` per toplevel. */
const FR_PATHS_TIMEOUT_MS = 5_000;

/** The keys of `fr settings paths --json` this plugin reads (spec 2026-11-04
 * repo-feature-settings R1: one resolver names every artifact directory). */
export interface FrPaths {
  placement?: string;
  plansDir?: string;
  acceptanceDir?: string;
}

const pathsCache = new Map<string, FrPaths | null>();

/** Test seam: forget what `fr` answered. */
export function resetFrPaths(): void {
  pathsCache.clear();
  announcedMissingFr = false;
}

function stringKey(doc: Record<string, unknown>, key: string): string | undefined {
  const value = doc[key];
  return typeof value === "string" && value !== "" ? value : undefined;
}

/**
 * What `fr settings paths --json --no-create` says about this toplevel, cached per
 * toplevel (a failure is cached too: a hung or missing `fr` must not cost every edit its
 * timeout). `--no-create` keeps it read-only: a hook never creates the quiet `fr` branch
 * or worktree (review p6-r4). It runs with FR_REPO_ROOT set to *toplevel*, never an
 * inherited one naming another repo (review p6-r9). `null` when `fr` is absent, fails,
 * or answers something that is not a JSON object: the caller then falls back to the
 * direct checks, never to "no".
 */
export function frPaths(toplevel: string): FrPaths | null {
  if (pathsCache.has(toplevel)) return pathsCache.get(toplevel) ?? null;
  let result: FrPaths | null = null;
  const fr = resolveFr();
  const out =
    fr === null
      ? { code: null, stdout: "" }
      : runSync(fr, ["settings", "paths", "--json", "--no-create"], {
          cwd: toplevel,
          timeoutMs: FR_PATHS_TIMEOUT_MS,
          env: { ...process.env, FR_REPO_ROOT: toplevel },
        });
  if (out.code === 0) {
    try {
      const doc = JSON.parse(out.stdout) as unknown;
      if (doc !== null && typeof doc === "object" && !Array.isArray(doc)) {
        const d = doc as Record<string, unknown>;
        result = {
          placement: stringKey(d, "FR_PLACEMENT"),
          plansDir: stringKey(d, "FR_PLANS_DIR"),
          acceptanceDir: stringKey(d, "FR_ACCEPTANCE_DIR"),
        };
      }
    } catch {
      result = null;
    }
  }
  pathsCache.set(toplevel, result);
  return result;
}

let announcedMissingFr = false;

/**
 * Say once, at load, that `fr` does not resolve: the artifact directories then come
 * from the checkout's own layout (the plans test) plus the direct quiet/stealth
 * detection, so the edit gate is not weakened, but a placement `fr` could name that
 * the direct checks cannot see is not consulted. Returns whether it warned.
 */
export function warnIfFrUnresolved(): boolean {
  if (announcedMissingFr) return false;
  if (resolveFr() !== null) return false;
  announcedMissingFr = true;
  console.error(
    "super-fr: no `fr` found on PATH; fr-enabled detection falls back to the plans dir, a " +
      "devcontainer profile, the quiet switch on origin/fr and the workspace marker's placement. " +
      "Install fr to resolve artifact paths from the placement."
  );
  return true;
}

function isDir(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

/** The repository's common git dir, read from the filesystem (no subprocess): `.git` as
 * a dir, or a `gitdir:` file (a linked worktree), then its `commondir`. */
function commonDirOf(toplevel: string): string | null {
  const dot = join(toplevel, ".git");
  let gitDir: string;
  try {
    if (statSync(dot).isDirectory()) {
      gitDir = dot;
    } else {
      const line = readFileSync(dot, "utf-8").split("\n")[0] ?? "";
      if (!line.startsWith("gitdir: ")) return null;
      gitDir = resolve(toplevel, line.slice("gitdir: ".length).trim());
    }
  } catch {
    return null;
  }
  try {
    return resolve(gitDir, readFileSync(join(gitDir, "commondir"), "utf-8").split("\n")[0]?.trim() ?? "");
  } catch {
    return gitDir;
  }
}

/**
 * Whether `refs/remotes/origin/fr` MAY exist, read from the filesystem with no
 * subprocess (review p6-r8): a loose ref, a `packed-refs` line, a reftable store (not
 * readable without git, so "maybe"), or a git dir that cannot be read. False only when
 * the filesystem says positively that it does not. The precondition that keeps a plain
 * repo's edit decision and nag from spawning git for the switch or `fr` at all (review
 * p6-r1); it never decides fr-enabled by itself. Bash: `fr_switch_ref_maybe`.
 */
export function switchRefMaybe(toplevel: string): boolean {
  const common = commonDirOf(toplevel);
  if (common === null || !isDir(common)) return true;
  if (existsSync(join(common, "refs", "remotes", "origin", "fr"))) return true;
  if (isDir(join(common, "reftable"))) return true;
  try {
    return readFileSync(join(common, "packed-refs"), "utf-8")
      .split("\n")
      .some((line) => line.replace(/\r$/, "").endsWith(" refs/remotes/origin/fr"));
  } catch {
    return false;
  }
}

/**
 * Whether a switch's `settings.yaml` makes the repo fr-enabled (review p6-r3): fr
 * accepts one spelling of `placement` only (`fr.placement.quiet.switch_spelling_problem`),
 * the line `placement: <value>` at column 0, unquoted, no comment, the only live line
 * naming placement. That line saying `quiet` is quiet; it saying `repo`, or no live
 * line naming placement (the default), is repo; ANYTHING else fails closed, as
 * fr-enabled. Bash: `_fr_switch_enabled`, line for line.
 */
export function switchEnabled(text: string): boolean {
  let live = 0;
  let canonical = "";
  for (const raw of text.split("\n")) {
    const line = raw.replace(/\r$/, "");
    if (!line.includes("placement")) continue;
    if (line.replace(/^\s+/, "").startsWith("#")) continue;
    live += 1;
    if (line === "placement: quiet" || line === "placement: repo") canonical = line;
  }
  if (live === 0) return false;
  return !(live === 1 && canonical === "placement: repo");
}

/**
 * Whether the repo is on the quiet or stealth placement, found WITHOUT `fr`: the
 * marker records `placement` quiet or stealth, or the last fetched
 * `refs/remotes/origin/fr:settings.yaml`, with an origin remote (R23), cannot be read
 * positively as `repo` (`switchEnabled`), read only when `switchRefMaybe` says the ref
 * may exist, so a plain repo spawns no git for it. The shell library's
 * `_fr_placement_enabled`, line for line.
 */
export function placementEnabled(toplevel: string): boolean {
  const marker = readMarker(toplevel);
  if (marker && (marker.placement === "quiet" || marker.placement === "stealth")) return true;
  // The filesystem answers first (review pr1431-n6): no `refs/remotes/origin/fr`, no git.
  if (!switchRefMaybe(toplevel)) return false;
  if (git(toplevel, "config", "--get", "remote.origin.url") === undefined) return false;
  const text = git(toplevel, "cat-file", "-p", "refs/remotes/origin/fr:settings.yaml");
  return text !== undefined && switchEnabled(text);
}

/**
 * The one "is this repo fr-enabled" (bash `_fr_is_enabled`, R26): the DIRECT checks, a
 * devcontainer profile, a plans dir in the checkout (run whether or not `fr` resolves,
 * plan-journal decision p6-plans-test-always), or a quiet/stealth placement found
 * directly (the switch read only past `switchRefMaybe`, review pr1431-n6). Only then, and
 * only when `refs/remotes/origin/fr` may exist (a plain repo
 * spawns no `fr`, review p6-r1), `fr settings paths --json --no-create` naming a
 * quiet/stealth placement or an existing plans dir. A missing, failing, slow or garbled
 * `fr` can only fail to ADD a yes.
 */
export function frEnabled(toplevel: string): boolean {
  // The same question the bash guard asks by globbing
  // `.devcontainer/*/devcontainer.json`, without a subprocess on the edit path.
  try {
    for (const entry of readdirSync(`${toplevel}/.devcontainer`)) {
      if (existsSync(`${toplevel}/.devcontainer/${entry}/devcontainer.json`)) return true;
    }
  } catch {
    // no profiles
  }
  if (isDir(`${toplevel}/docs/superpowers/plans`)) return true; // fr-paths-fallback
  if (placementEnabled(toplevel)) return true;
  if (!switchRefMaybe(toplevel)) return false;
  const paths = frPaths(toplevel);
  if (paths === null) return false;
  if (paths.placement === "quiet" || paths.placement === "stealth") return true;
  return paths.plansDir !== undefined && isAbsolute(paths.plansDir) && isDir(paths.plansDir);
}

function gitDirsDiffer(toplevel: string): boolean {
  // A linked worktree has a distinct --git-dir from its --git-common-dir;
  // the primary working tree's git-dir IS its common-dir.
  const common = git(toplevel, "rev-parse", "--git-common-dir");
  const gitdir = git(toplevel, "rev-parse", "--git-dir");
  if (common === undefined || gitdir === undefined) return false;
  const rcommon = realpath(isAbsolute(common) ? common : `${toplevel}/${common}`);
  const rgitdir = realpath(isAbsolute(gitdir) ? gitdir : `${toplevel}/${gitdir}`);
  return rcommon !== rgitdir;
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
  const head = git(toplevel, "symbolic-ref", "--quiet", "--short", "HEAD");
  // A detached HEAD (mid-rebase, bisect) has no symbolic ref — not drift.
  if (head === undefined) return undefined;
  return head !== markerBranch ? { marker: markerBranch, head } : undefined;
}

function readMarker(
  toplevel: string
): { toplevel?: string; mode?: string; branch?: string; placement?: string } | null {
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

  const enabled = frEnabled(toplevel);
  if (!enabled) return { toplevel, frEnabled: false, hasValidMarker: false };

  const hasValidMarker = hasValidIsolationMarker(toplevel);
  if (hasValidMarker) return { toplevel, frEnabled: true, hasValidMarker };
  const marker = existsSync(`${toplevel}/.fr-isolation`) ? readMarker(toplevel) : null;
  const drift =
    marker && (marker.mode ?? "worktree") === "worktree" ? branchDrift(toplevel, marker.branch) : undefined;
  return { toplevel, frEnabled: true, hasValidMarker, drift };
}

export { matchesAllowlist };
