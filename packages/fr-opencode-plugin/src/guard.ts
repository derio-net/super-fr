// The shell gate — the OpenCode 2 port of plugins/super-fr/hooks/fr-isolation-guard.sh
// (spec 2026-10-20-opencode-2-support R3, §B).
//
// While a pipeline sentinel exists for this session, a shell command whose cwd
// resolves inside the pipeline's base repo is refused, except: a leading `cd`
// into a valid isolation workspace or an allowed prefix, the `fr isolation …`
// lifecycle, `fr run start`, and the bootstrap/info `fr` verbs. The decision is
// made on the WHOLE command line (`execute.before` for `tool === "shell"`), never
// per scanner resource: `cd <worktree> && git status` judged piecewise would be
// a bare `git status` in the base repo.
//
// PARITY, NOT IMPROVEMENT. Two engines now decide this, and the contract between
// them is tests/fixtures/hooks/guard-verdicts.yaml — CAPTURED from the bash
// script and run against both (test/guard-verdicts.test.ts here,
// tests/unit/test_hooks_guard.py there). Every quirk below is the bash guard's,
// kept on purpose; read that script for the history behind each one. Two are
// worth naming because they look like bugs:
//   * the allowances are START-anchored but not END-anchored, so
//     `fr isolation status && make` is allowed as a unit — deliberate there
//     (rejecting it would reject `fr isolation exec -- 'a && b'`), so here too;
//   * only the LEADING `cd` is evaluated, so `cd <tmp> && cd <base> && …` rides
//     the first segment's allowance — blessed in #421, so here too.
// A rule that looks wrong is a finding against BOTH engines, not an edit here.
//
// Only the FIRST LINE of a command is evaluated, as in bash.
//
// Returns the refusal text, or undefined to allow. Never throws: the handler in
// index.ts throws the text, and an internal failure here allows (the bash hook,
// under `set -e`, also lets the command through when it fails).
import { existsSync, readdirSync, readFileSync, realpathSync, rmSync, statSync, utimesSync } from "node:fs";
import { isAbsolute, join, resolve } from "node:path";
import {
  readRepoRoot,
  readWorkspaces,
  sentinelLock,
  sentinelOwns,
  sentinelPath,
  sentinelUnlock,
} from "./sentinel";
import { runSync } from "./spawn";

const GIT_TIMEOUT_MS = 5_000;
/** POSIX [[:space:]] — not JS `\s`, which also matches Unicode spaces. */
const S = "[ \\t\\n\\v\\f\\r]";
const NS = "[^ \\t\\n\\v\\f\\r]";
const CD_TARGET = new RegExp(`^${S}*cd${S}+("([^"]+)"|'([^']+)'|([^ \\t\\n\\v\\f\\r;&|]+))`);
const CD_STRIP = new RegExp(`^${S}*cd${S}+("[^"]+"|'[^']+'|[^ \\t\\n\\v\\f\\r;&|]+)${S}*(&&|;)${S}*`);
const ENV_PREFIX = new RegExp(`^${S}*(env${S}+)?([A-Za-z_][A-Za-z0-9_]*=${NS}*${S}+)+`);
const UV_RUN = new RegExp(`^${S}*uv${S}+run${S}+`);
const FR_INFO = new RegExp(`^${S}*fr${S}+(init(${S}|$)|skills(${S}|$)|--version(${S}|$))`);
const FR_RUN_START = new RegExp(`^${S}*fr${S}+run${S}+start(${S}|$)`);
const FR_ISOLATION = new RegExp(`^${S}*fr${S}+isolation(${S}|$)`);

function realDir(path: string): string | undefined {
  try {
    if (!statSync(path).isDirectory()) return undefined;
    return realpathSync(path);
  } catch {
    return undefined;
  }
}

function under(path: string, root: string): boolean {
  return `${path}/`.startsWith(`${root}/`);
}

function git(dir: string, ...args: string[]): string | undefined {
  const out = runSync("git", ["-C", dir, ...args], { timeoutMs: GIT_TIMEOUT_MS });
  if (out.code !== 0) return undefined;
  const text = out.stdout.trim();
  return text === "" ? undefined : text;
}

function toplevelOf(dir: string): string | undefined {
  const top = git(dir, "rev-parse", "--show-toplevel");
  return top === undefined ? undefined : realDir(top);
}

/** `cd <base> && cd <rel>` then `pwd -P`, falling back to the raw value. */
function resolveFrom(base: string, path: string): string {
  return realDir(isAbsolute(path) ? path : join(base, path)) ?? path;
}

/** bash `_fr_is_enabled`: a devcontainer profile, or an fr plans dir. */
export function frEnabled(toplevel: string): boolean {
  try {
    const profiles = join(toplevel, ".devcontainer");
    for (const name of readdirSafe(profiles)) {
      try {
        if (statSync(join(profiles, name, "devcontainer.json")).isFile()) return true;
      } catch {
        // not a profile
      }
    }
  } catch {
    // no profiles
  }
  return realDir(join(toplevel, "docs", "superpowers", "plans")) !== undefined;
}

function readdirSafe(dir: string): string[] {
  try {
    return readdirSync(dir);
  } catch {
    return [];
  }
}

/** bash `fr_isolation_marker_valid`: dir's toplevel carries a VALID marker.
 * Branch drift is deliberately NOT part of validity here (the shell must stay
 * open so `git switch` can recover a drifted workspace) — which is why this is
 * not marker.ts's edit-gate check. */
export function markerValid(dir: string): boolean {
  if (realDir(dir) === undefined) return false;
  const top = toplevelOf(dir);
  if (!top) return false;
  const markerPath = join(top, ".fr-isolation");
  if (!existsSync(markerPath)) return false;
  let marker: unknown;
  try {
    marker = JSON.parse(readFileSync(markerPath, "utf-8"));
  } catch {
    return false;
  }
  if (!marker || typeof marker !== "object" || Array.isArray(marker)) return false;
  const fields = marker as Record<string, unknown>;
  const recorded = typeof fields.toplevel === "string" ? fields.toplevel : "";
  const mode = typeof fields.mode === "string" && fields.mode !== "" ? fields.mode : "worktree";
  const rrecorded = recorded === "" ? "" : (realDir(recorded) ?? recorded);
  if (rrecorded !== top) return false;
  if (mode === "worktree") {
    const common = git(top, "rev-parse", "--git-common-dir") ?? "";
    const gitdir = git(top, "rev-parse", "--git-dir") ?? "";
    return resolveFrom(top, common) !== resolveFrom(top, gitdir);
  }
  if (mode === "external") {
    return existsSync("/.dockerenv") || existsSync("/run/.containerenv") || !!process.env.KUBERNETES_SERVICE_HOST;
  }
  return false;
}

/** bash `fr_strip_command_prefix`: env assignments (optionally after `env`),
 * then a leading `uv run`. */
export function stripCommandPrefix(line: string): string {
  return line.replace(ENV_PREFIX, "").replace(UV_RUN, "");
}

/** The heal (#472/#529): true when THIS sentinel is orphaned and was retired. */
function healOrphaned(sentinel: string, rroot: string): boolean {
  if (readWorkspaces(sentinel).length === 0) return false; // fresh: never healed
  if (!sentinelLock(sentinel, 20)) return false; // no heal this call: stays armed
  try {
    const workspaces = readWorkspaces(sentinel);
    let live = true; // unknown (non-git repo, emptied while we waited): no heal
    const listing = workspaces.length > 0 ? runSync("git", ["-C", rroot, "worktree", "list", "--porcelain"], { timeoutMs: GIT_TIMEOUT_MS }) : undefined;
    if (listing && listing.code === 0) {
      const listed = new Set<string>();
      for (const line of listing.stdout.split("\n")) {
        if (!line.startsWith("worktree ")) continue;
        const real = realDir(line.slice("worktree ".length));
        if (real) listed.add(real);
      }
      live = false;
      for (const ws of workspaces) {
        const real = realDir(join(process.env.HOME ?? "", ".cache", "fr", ws));
        if (real && listed.has(real)) {
          live = true;
          break;
        }
      }
    }
    if (!live && sentinelOwns(sentinel)) {
      rmSync(sentinel, { force: true });
      return true;
    }
    return false;
  } finally {
    sentinelUnlock(sentinel);
  }
}

const STANDARD =
  "fr pipeline active — ALL base-repo commands are gated (not just git/gh), so work runs in the isolation worktree. Where is this session's workspace? `fr isolation status`. No workspace yet? `fr isolation up --branch <name>` (prefix `FR_ISOLATION_TARGET=worktree` if this repo has no devcontainer profile). Then run via `fr isolation exec -- …`, or lead with `cd <worktree> && …` to work from the worktree cwd. Working in a DIFFERENT repo? `cd <other-repo> && fr isolation up` is allowed from here — enter that repo's isolation and work from its worktree. LAST RESORT, and rarely right: `fr isolation down --all` acts on EVERY workspace in this repo, including other sessions' — a workspace with no PR yet is torn down with whatever was uncommitted in it. `fr isolation down --all --dry-run` shows its blast radius first (what it would tear down or keep, and whose sessions are bound), and tearing down another session's workspace needs `--yes`. See plugins/super-fr/skills/fr-isolation (exec-bridge discipline, #265/#279/#329/#421/#432).";

function gone(target: string): string {
  return `fr-isolation: \`${target}\` no longer exists, so this \`cd\` cannot succeed — an fr workspace is removed once its branch merges, and unused ones are GC'd after 48h. Where are this session's live workspaces? \`fr isolation status\`. Start a fresh one with \`fr isolation up --branch <name>\` (prefix \`FR_ISOLATION_TARGET=worktree\` if this repo has no devcontainer profile) and work from the path it reports; \`fr isolation exec -- …\` runs a one-off there. A live pipeline still gates base-repo commands — that part is unchanged. See plugins/super-fr/rules/fr-isolation-required.md (#432).`;
}

function sameRepoWorktree(path: string): string {
  return `fr-isolation: \`${path}\` is a linked worktree of THIS repo, but it carries no valid \`.fr-isolation\` marker, so it is not an isolation workspace. Run \`fr isolation up --branch <branch>\` (allowed from here) and work from the workspace it reports, or add this path to FR_CD_ALLOW_PREFIXES if it is a worktree you manage yourself. See plugins/super-fr/rules/fr-isolation-required.md.`;
}

function otherFrRepo(repo: string): string {
  return `fr-isolation: \`${repo}\` is not an fr isolation workspace (no valid \`.fr-isolation\` marker), so a live pipeline elsewhere does not open it for general work — reaching another repo is for entering ITS isolation, not for running anything there. Do: \`cd ${repo} && fr isolation up --branch <branch>\` (allowed from here; prefix \`FR_ISOLATION_TARGET=worktree\` if that repo has no devcontainer profile), then run the command from the worktree it reports. See plugins/super-fr/rules/fr-isolation-required.md (#421).`;
}

function otherPlainRepo(repo: string, rroot: string): string {
  return `fr-isolation: \`${repo}\` is not fr-managed, so there is no isolation to enter and this hook has no opinion about that repo's own tooling — the deny is only about a live pipeline in \`${rroot}\` reaching sideways mid-run. Finish or end this pipeline (\`fr isolation down\`), or run the command from a session that holds no pipeline. FR_BASE_OK=1 also disables the gate, but the hook reads it from its OWN environment: an inline \`FR_BASE_OK=1 <cmd>\` is not parsed, so it has to be set where the harness is launched. See plugins/super-fr/rules/fr-isolation-required.md (#421).`;
}

/** Decide one shell call. `cwd` is where the command will run. */
export function decideShell(command: string, cwd: string, sessionID: string): string | undefined {
  try {
    return decide(command, cwd, sessionID);
  } catch {
    return undefined;
  }
}

function decide(command: string, cwd: string, sessionID: string): string | undefined {
  if (!sessionID) return undefined;
  const sentinel = sentinelPath(sessionID);
  try {
    if (!statSync(sentinel).isFile()) return undefined;
  } catch {
    return undefined; // no active pipeline for this session
  }

  // Liveness: every shell call refreshes the sentinel's mtime (never creates).
  try {
    const now = new Date();
    utimesSync(sentinel, now, now);
  } catch {
    // retired since the test above: stays gone
  }

  const repoRoot = readRepoRoot(sentinel);
  if (!repoRoot || !cwd) return undefined;
  const rcwd = realDir(cwd);
  const rroot = realDir(repoRoot);
  if (!rcwd || !rroot) return undefined;
  if (!under(rcwd, rroot)) return undefined; // worktree, /tmp, elsewhere

  // The pipeline's repo may itself be the workspace (external mode).
  if (markerValid(rroot)) return undefined;

  const first = command.split("\n")[0] ?? "";
  const home = process.env.HOME ?? "";
  let cdTarget = "";
  let cdStrip = false;
  let cdOtherRepo = "";
  let cdSameRepoWorktree = false;
  let rtarget: string | undefined;

  const match = CD_TARGET.exec(first);
  if (match) cdTarget = (match[2] ?? "") + (match[3] ?? "") + (match[4] ?? "");
  if (cdTarget) {
    if (cdTarget.startsWith("~")) cdTarget = home + cdTarget.slice(1);
    if (!cdTarget.startsWith("/")) cdTarget = `${rcwd}/${cdTarget}`;
    rtarget = realDir(cdTarget);
    if (rtarget) {
      if (under(rtarget, rroot)) {
        cdStrip = true;
      } else {
        const rtop = toplevelOf(rtarget);
        if (rtop) {
          if (rtop === rtarget) cdStrip = true;
          const tcommon = git(rtarget, "rev-parse", "--git-common-dir");
          const rcommon = git(rroot, "rev-parse", "--git-common-dir");
          if (tcommon !== undefined && rcommon !== undefined) {
            const t = realDir(isAbsolute(tcommon) ? tcommon : resolve(rtarget, tcommon));
            const r = realDir(isAbsolute(rcommon) ? rcommon : resolve(rroot, rcommon));
            if (t && r && t === r) cdSameRepoWorktree = true;
          }
          if (!under(rtop, rroot)) {
            cdOtherRepo = rtop;
            if (process.env.FR_BASE_OK === "1" || markerValid(rtarget)) return undefined;
          }
        }
        const prefixes =
          process.env.FR_CD_ALLOW_PREFIXES || `${home}/.cache/fr/worktrees:/tmp:${process.env.TMPDIR ?? ""}`;
        for (const prefix of prefixes.split(":")) {
          if (!prefix) continue;
          const rprefix = realDir(prefix);
          if (rprefix && under(rtarget, rprefix)) return undefined;
        }
      }
    }
  }

  let rest = first;
  if (cdStrip) rest = rest.replace(CD_STRIP, "");
  rest = stripCommandPrefix(rest);

  if (FR_INFO.test(rest)) return undefined;
  if (FR_RUN_START.test(rest)) return undefined;
  // Deliberately start-anchored only: `fr isolation status && make` is allowed.
  if (FR_ISOLATION.test(rest)) return undefined;

  if (healOrphaned(sentinel, rroot)) return undefined;

  if (cdTarget && realDir(cdTarget) === undefined) return gone(cdTarget);
  if (cdSameRepoWorktree) return sameRepoWorktree(cdOtherRepo || rtarget || "");
  if (cdOtherRepo) return frEnabled(cdOtherRepo) ? otherFrRepo(cdOtherRepo) : otherPlainRepo(cdOtherRepo, rroot);
  return STANDARD;
}
