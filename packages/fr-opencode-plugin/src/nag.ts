// The acceptance nag — the OpenCode 2 port of plugins/super-fr/hooks/fr-acceptance-nag.sh
// (spec 2026-10-20-opencode-2-support R9).
//
// super-fr-parity: fr-acceptance-nag.sh
//
// At a top-level session's FIRST model request, `ctx.session.hook("context")`
// appends one system part carrying `fr acceptance status --brief` — the open
// acceptance debt. It never rewrites the operator's prompt text.
//
// Rules, as in the bash hook:
//   - at most ONCE per top-level session (remembered before the spawn, so a
//     failing `fr` is not retried on every request);
//   - child sessions are skipped, and a session that cannot be looked up is not
//     assumed to be top-level;
//   - a repo with no docs/acceptance/matrix.yaml returns BEFORE any process
//     spawn (the repo root is found on the filesystem, not via git);
//   - bounded (a short timeout), silent on every failure — except the stale
//     artifact refusal, which says why the nag is missing;
//   - NEVER THROWS.
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { run, type RunAnswer } from "./spawn";

const DEFAULT_TIMEOUT_MS = 10_000;

/** The artifact gate's commit notice (`fr.artifacts.trigger.COMMIT_NOTICE_PREFIX`). */
const COMMIT_NOTICE = "fr: migrated and committed";

const STALE_SKIPPED =
  "acceptance nag skipped: artifacts stale — in an fr-isolation workspace (`fr isolation up --branch <branch>`) " +
  "the next fr command migrates and commits them; elsewhere run `fr migrate artifacts --yes` on a branch\n";

/** `globalThis` key for the nag's process-wide once-per-session memory. */
export const SHARED_SERVED = Symbol.for("super-fr.fr-opencode-plugin.nag.served");

export function sharedServed(): Set<string> {
  const slot = globalThis as Record<symbol, Set<string> | undefined>;
  return (slot[SHARED_SERVED] ??= new Set<string>());
}

export type NagHandlerOptions = {
  /** `ctx.session` — `get({sessionID})`. */
  session: unknown;
  directory: string;
  /** Test seam. Default: `fr <args>` in `cwd`, bounded. */
  runFr?: (cwd: string, args: string[]) => Promise<RunAnswer>;
  timeoutMs?: number;
  /** Once-per-session memory. The plugin passes `sharedServed()`, because
   * OpenCode 2 can load the delivered plugin twice (phase-1 finding
   * p1-v2-loads-sources-dir-as-plugin): module state is per copy, globalThis is
   * not, so each copy would otherwise nag every top-level session again. */
  served?: Set<string>;
};

type ContextEvent = { sessionID?: unknown; system?: unknown };

/** The nearest ancestor holding `.git` (file or dir) — no spawn. */
function repoRootOf(directory: string): string | undefined {
  let dir = resolve(directory);
  for (;;) {
    if (existsSync(join(dir, ".git"))) return dir;
    const parent = dirname(dir);
    if (parent === dir) return undefined;
    dir = parent;
  }
}

async function isTopLevel(session: unknown, id: string): Promise<boolean> {
  const get = (session as { get?: unknown } | null | undefined)?.get;
  if (typeof get !== "function") return false;
  const info = (await (get as (r: { sessionID: string }) => Promise<unknown>).call(session, { sessionID: id })) as
    | { id?: unknown; parentID?: unknown }
    | null
    | undefined;
  if (!info || typeof info !== "object" || info.id !== id) return false;
  return info.parentID === undefined || info.parentID === null;
}

export function createNagHandler(options: NagHandlerOptions) {
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const runFr = options.runFr ?? ((cwd: string, args: string[]) => run("fr", args, { cwd, timeoutMs }));
  const served = options.served ?? new Set<string>();

  return async (event: ContextEvent | null | undefined): Promise<void> => {
    try {
      if (!event || !Array.isArray(event.system)) return;
      const sessionID = event.sessionID;
      if (typeof sessionID !== "string" || sessionID === "" || served.has(sessionID)) return;

      const root = repoRootOf(options.directory);
      if (!root || !existsSync(join(root, "docs", "acceptance", "matrix.yaml"))) return;

      served.add(sessionID); // before any await: one attempt per session
      if (!(await isTopLevel(options.session, sessionID))) return;

      const answer = await runFr(root, ["acceptance", "status", "--brief"]);
      let text: string | undefined;
      const err = answer.stderr ?? "";
      if (answer.code !== 0) {
        if (err.includes("must be migrated") || err.includes("migrate artifacts")) {
          text = STALE_SKIPPED;
        }
      } else {
        const out = answer.stdout.replace(/\n+$/, "");
        if (out !== "" && !out.includes("no acceptance debt")) {
          text = `Acceptance debt in this repo (backfill owed — details: fr acceptance status):\n${out}\n`;
        }
      }
      // The gate may have migrated and committed on the way in (spec
      // 2026-11-01-auto-migrate-own-commit R11): relay its one-line notice first,
      // on a refusal too: a partial migration commits, then exits 2 (review p1-r4).
      const notice = err.split("\n").find((line) => line.startsWith(COMMIT_NOTICE));
      if (notice) text = `${notice}\n${text ?? ""}`;
      if (text) (event.system as { type: "text"; text: string }[]).push({ type: "text", text });
    } catch {
      // Fail open, always. See the header.
    }
  };
}
