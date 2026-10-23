// The pipeline sentinel: "an fr pipeline is active for this session in this
// repo" — the OpenCode 2 port of plugins/super-fr/hooks/fr-pipeline-sentinel.sh
// (spec 2026-10-20-opencode-2-support R10), plus the lock every sentinel writer
// shares (lib/fr-isolation-decision.sh `fr_sentinel_lock`; in Python
// `fr.isolation.types._sentinel_lock`).
//
// super-fr-parity: fr-pipeline-sentinel.sh
//
// The FILE is a contract with three other readers — the bash guard, `fr
// isolation attach` (stamp_sentinel_workspace) and `fr isolation down`
// (clear_*_sentinels) — so it is written in exactly the bash writer's shape:
// `{repo_root, skill, started_at}` plus `workspaces` only when a live entry is
// carried. tests/unit/test_sentinel_lifecycle.py asserts the key set against
// the Python reader so the two cannot drift.
//
// NEVER THROWS. This runs after a skill call completed; an exception out of it
// would be this plugin breaking the session it protects.
import { existsSync, mkdirSync, readdirSync, readFileSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { git } from "./git";

const PIPELINE_SKILLS = new Set(["fr-goal", "fr-brainstorming", "fr-execute"]);
const GC_AGE_MS = 48 * 3600 * 1000;
/** A lock with no readable owner is abandoned only once clearly stale. */
const OWNERLESS_LOCK_AGE_MS = 60 * 1000;

export function frHome(): string {
  return process.env.HOME || homedir();
}

export function sentinelDir(): string {
  return process.env.FR_SENTINEL_DIR || join(frHome(), ".cache", "fr", "sentinels");
}

export function sentinelPath(sessionID: string): string {
  return join(sentinelDir(), `${sessionID}.json`);
}

/** The cache-relative workspace entries a sentinel records — strings only. */
export function readWorkspaces(sentinel: string): string[] {
  try {
    const data = JSON.parse(readFileSync(sentinel, "utf-8")) as { workspaces?: unknown };
    if (!Array.isArray(data.workspaces)) return [];
    return data.workspaces.filter((w): w is string => typeof w === "string" && w !== "");
  } catch {
    return [];
  }
}

export function readRepoRoot(sentinel: string): string {
  try {
    const data = JSON.parse(readFileSync(sentinel, "utf-8")) as { repo_root?: unknown };
    return typeof data.repo_root === "string" ? data.repo_root : "";
  } catch {
    return "";
  }
}

// --- the shared lock -------------------------------------------------------
//
// `<sentinel>.lock/` (mkdir is atomic) holding `owner` = the holder's PID.
// Broken only when the holder is dead, or ownerless and older than 60s. A live
// holder is never broken. Release is owner-checked.
//
// The owner here is the OpenCode server's PID, shared by every handler in this
// process. That is sound only because every lock/act/unlock below is
// SYNCHRONOUS — no `await` between take and release — so two handlers in this
// process can never interleave inside one.

function sleepSync(ms: number): void {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function pidAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return (error as NodeJS.ErrnoException).code === "EPERM";
  }
}

function lockAbandoned(lock: string): boolean {
  let owner = "";
  try {
    owner = readFileSync(join(lock, "owner"), "utf-8").trim();
  } catch {
    owner = "";
  }
  if (/^[0-9]+$/.test(owner)) return !pidAlive(Number(owner));
  try {
    return Date.now() - statSync(lock).mtimeMs > OWNERLESS_LOCK_AGE_MS;
  } catch {
    return false;
  }
}

/** Take the lock; `maxAttempts` steps of 50ms. True when held. */
export function sentinelLock(sentinel: string, maxAttempts: number): boolean {
  const lock = `${sentinel}.lock`;
  for (let tries = 0; ; ) {
    try {
      mkdirSync(lock);
      try {
        writeFileSync(join(lock, "owner"), `${process.pid}\n`);
      } catch {
        // an ownerless lock ages out after 60s, as in the bash protocol
      }
      return true;
    } catch {
      // fall through
    }
    if (!existsSync(lock)) return false; // mkdir failed, and not because it exists
    if (lockAbandoned(lock)) {
      rmSync(join(lock, "owner"), { force: true });
      try {
        rmSync(lock, { recursive: false, force: true });
      } catch {
        // someone else broke it first
      }
      continue;
    }
    tries += 1;
    if (tries >= maxAttempts) return false;
    sleepSync(50);
  }
}

export function sentinelOwns(sentinel: string): boolean {
  try {
    return readFileSync(join(`${sentinel}.lock`, "owner"), "utf-8").trim() === String(process.pid);
  } catch {
    return false;
  }
}

export function sentinelUnlock(sentinel: string): void {
  if (!sentinelOwns(sentinel)) return;
  try {
    rmSync(join(`${sentinel}.lock`, "owner"), { force: true });
    rmSync(`${sentinel}.lock`, { recursive: true, force: true });
  } catch {
    // released enough: an ownerless lock ages out
  }
}

// --- the writer ------------------------------------------------------------

export type SkillCallEvent = {
  tool?: unknown;
  sessionID?: unknown;
  status?: unknown;
  input?: unknown;
};

/** The skill a V2 `skill` call names. Measured on OpenCode 2.0.32: the input is
 * `{id: "fr-goal"}`; the other spellings are kept as the bash hook keeps its. */
function skillName(input: unknown): string {
  if (!input || typeof input !== "object") return "";
  const args = input as Record<string, unknown>;
  for (const key of ["id", "name", "skill", "skill_name"]) {
    if (typeof args[key] === "string") return args[key] as string;
  }
  return "";
}

function isPipelineSkill(skill: string): boolean {
  const bare = skill.includes(":") ? skill.slice(skill.lastIndexOf(":") + 1) : skill;
  return PIPELINE_SKILLS.has(bare);
}

function isDir(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

function gc(dir: string): void {
  const now = Date.now();
  let names: string[] = [];
  try {
    names = readdirSync(dir);
  } catch {
    return;
  }
  for (const name of names) {
    const path = join(dir, name);
    let stat: ReturnType<typeof statSync>;
    try {
      stat = statSync(path);
    } catch {
      continue;
    }
    if (now - stat.mtimeMs <= GC_AGE_MS) continue;
    if (name.endsWith(".json") && stat.isFile()) {
      // A parked pipeline (a workspace it lists still exists) is kept.
      const keep = readWorkspaces(path).some((ws) => isDir(join(frHome(), ".cache", "fr", ws)));
      if (!keep) rmSync(path, { force: true });
    } else if (name.endsWith(".json.lock") && stat.isDirectory()) {
      rmSync(path, { recursive: true, force: true });
    }
  }
}

/** `execute.after` for a completed `skill` call in `cwd`. Never throws. */
export function writePipelineSentinel(event: SkillCallEvent | null | undefined, cwd: string): void {
  try {
    if (!event || event.tool !== "skill" || event.status !== "completed") return;
    const skill = skillName(event.input);
    if (!isPipelineSkill(skill)) return;
    const sessionID = event.sessionID;
    if (typeof sessionID !== "string" || sessionID === "" || !cwd) return;

    // Pipeline skills only matter inside a repo; a non-git cwd is a no-op.
    const repoRoot = git(cwd, "rev-parse", "--show-toplevel") ?? "";
    if (!repoRoot) return;
    // A linked worktree (.git is a file) IS the isolation workspace: only the
    // base repo gets a sentinel.
    if (!isDir(join(repoRoot, ".git"))) return;

    const dir = sentinelDir();
    mkdirSync(dir, { recursive: true });
    gc(dir);

    const sentinel = join(dir, `${sessionID}.json`);
    // The bash writer waits up to ~60s and then writes anyway; this one runs in
    // the OpenCode server and waits ~1s — the outcome (arm the pipeline) is the
    // same, without stalling every session the server holds.
    sentinelLock(sentinel, 20);
    try {
      // Carry the LIVE stamp across a reload (fr-goal → fr-brainstorming): same
      // repo_root, and the entry's directory still exists.
      const carried =
        existsSync(sentinel) && readRepoRoot(sentinel) === repoRoot
          ? readWorkspaces(sentinel).filter((ws) => isDir(join(frHome(), ".cache", "fr", ws)))
          : [];
      const body: Record<string, unknown> = {
        repo_root: repoRoot,
        skill,
        started_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      };
      if (carried.length > 0) body.workspaces = carried;
      // tmp + rename: the guard reads this on every shell call, and a
      // half-written sentinel parses as no repo_root — an unguarded command.
      const tmp = `${sentinel}.tmp.${process.pid}`;
      try {
        writeFileSync(tmp, `${JSON.stringify(body)}\n`);
        renameSync(tmp, sentinel);
      } catch {
        rmSync(tmp, { force: true });
      }
    } finally {
      sentinelUnlock(sentinel);
    }
  } catch {
    // Fail open, always. See the header.
  }
}
