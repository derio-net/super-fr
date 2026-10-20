// The status-line segment's data, kept free of JSX so it tests without a TUI
// (spec 2026-10-20-opencode-2-support R12).
//
// The text comes from plugins/super-fr/scripts/fr-statusline-segment.sh — the
// same script Claude Code's status line runs — never from re-deriving branch or
// isolation state here. The delivery copies that script beside this module.
//
// Rules: nothing outside a git repo (a cheap filesystem walk, no spawn), an
// em-dash for any part the script could not answer, and refreshes that are
// event-driven and coalesced — never one spawn per keystroke or per render.
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

import { run, type RunAnswer } from "../spawn";

export const MISSING = "\u2014";
export const SEGMENT_TIMEOUT_MS = 2000;

/** True when `cwd` or an ancestor carries `.git` (a dir, or a worktree's file). */
export function inGitRepo(cwd: string, exists: (p: string) => boolean = existsSync): boolean {
  if (!cwd) return false;
  let dir = resolve(cwd);
  for (;;) {
    if (exists(join(dir, ".git"))) return true;
    const parent = dirname(dir);
    if (parent === dir) return false;
    dir = parent;
  }
}

/** The script's `--format plain` output (three lines) -> the segment text. */
export function formatSegment(plain: string): string {
  const [state, branchRow, worktreeRow] = plain.replace(/\r/g, "").split("\n");
  const branch = branchRow?.startsWith("branch: ") ? branchRow.slice(8).trim() || MISSING : MISSING;
  if (state === "fr" && worktreeRow?.startsWith("worktree: ")) return `fr \u2387 ${branch}`;
  if (state === "none") return `${branch} \u00b7 no fr-isolation`;
  return `${MISSING} \u00b7 ${MISSING}`;
}

export type Runner = (cmd: string, args: string[], options: { cwd?: string; timeoutMs: number }) => Promise<RunAnswer>;

export type SegmentDeps = { run?: Runner; exists?: (p: string) => boolean };

/** The segment for `cwd`: "" outside a repo, the formatted script output inside one. */
export async function readSegment(cwd: string, script: string, deps: SegmentDeps = {}): Promise<string> {
  if (!inGitRepo(cwd, deps.exists)) return "";
  const answer = await (deps.run ?? run)("bash", [script, "--format", "plain", "--cwd", cwd], {
    cwd,
    timeoutMs: SEGMENT_TIMEOUT_MS,
  });
  if (answer.code !== 0) return `${MISSING} \u00b7 ${MISSING}`;
  return formatSegment(answer.stdout);
}

/** Coalesce refresh requests: at most one read in flight, at most one queued. */
export function createRefresher(read: () => Promise<void>, delayMs: number) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let running = false;
  let again = false;
  const fire = async () => {
    timer = undefined;
    if (running) {
      again = true;
      return;
    }
    running = true;
    try {
      await read();
    } catch {
      // A status line never breaks the TUI.
    } finally {
      running = false;
      if (again) {
        again = false;
        schedule();
      }
    }
  };
  const schedule = () => {
    if (timer !== undefined) return;
    timer = setTimeout(fire, delayMs);
  };
  return {
    schedule,
    now: () => fire(),
    cancel: () => {
      if (timer !== undefined) clearTimeout(timer);
      timer = undefined;
      again = false;
    },
  };
}

/** The events that can move branch or isolation state. */
export const REFRESH_EVENTS = [
  "session.execution.started",
  "session.execution.succeeded",
  "session.execution.failed",
  "session.execution.interrupted",
  "session.idle",
] as const;

/** The directory a session lives in, per the TUI's session data; `fallback`
 * (the TUI's launch directory) when there is no session or it is not loaded. */
export function sessionDirectory(
  sessions: { get(sessionID: string): { location?: { directory?: string } } | undefined } | undefined,
  sessionID: string | undefined,
  fallback: string,
): string {
  if (!sessionID || !sessions) return fallback;
  try {
    return sessions.get(sessionID)?.location?.directory || fallback;
  } catch {
    return fallback;
  }
}

/** One segment per session id (the home screen is key ""): each key has its
 * own coalesced refresher, so a render never spawns — it reads the cached
 * text, and the first read of a key or a moved directory schedules one. */
export function createSegmentCache(
  resolveDir: (key: string) => string,
  read: (cwd: string) => Promise<string>,
  onChange: () => void,
  delayMs: number,
) {
  type Entry = { text: string; dir: string; refresher: ReturnType<typeof createRefresher> };
  const entries = new Map<string, Entry>();
  const entry = (key: string): Entry => {
    let e = entries.get(key);
    if (e) return e;
    const created: Entry = {
      text: "",
      dir: resolveDir(key),
      refresher: createRefresher(async () => {
        created.dir = resolveDir(key);
        const next = await read(created.dir);
        if (next !== created.text) {
          created.text = next;
          onChange();
        }
      }, delayMs),
    };
    entries.set(key, created);
    created.refresher.schedule();
    return created;
  };
  return {
    text(key: string): string {
      const e = entry(key);
      if (resolveDir(key) !== e.dir) e.refresher.schedule();
      return e.text;
    },
    refresh(key?: string) {
      if (key !== undefined && entries.has(key)) entries.get(key)!.refresher.schedule();
      else for (const e of entries.values()) e.refresher.schedule();
    },
    cancel() {
      for (const e of entries.values()) e.refresher.cancel();
    },
  };
}
