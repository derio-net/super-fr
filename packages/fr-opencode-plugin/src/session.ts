// What the handlers read off a session's info — shared, so nag, bind, claim and
// idle all ask the same question the same way (consumer-delivery R4-R7).

export type SessionInfo = { id?: unknown; parentID?: unknown; location?: { directory?: unknown } | null };

/** Where fr is asked: the session's own `location.directory` (gh#1371 — a
 * session can live in another checkout than the plugin), else `fallback`. */
export function sessionDirectory(info: SessionInfo, fallback: string): string {
  const directory = info.location?.directory;
  return typeof directory === "string" && directory !== "" ? directory : fallback;
}

// The gates follow the session (gh#1371, #1552): the shell gate, the edit gate
// and the pipeline sentinel judge in the `location.directory` of the session an
// event names, as Claude Code's hooks judge in the hook input's `cwd`. One
// OpenCode server can hold sessions in another checkout than the plugin's; judged
// in the plugin's directory, a base-clone command there could pass and a
// workspace command be refused. Spec 2026-11-19-consumer-followups R4.

/** `globalThis` key for the process-wide session-id → directory cache. */
export const SHARED_SESSION_DIRECTORIES = Symbol.for("super-fr.fr-opencode-plugin.session.directories");

/** Shared across plugin reloads (OpenCode 2 can load the delivered plugin twice),
 * as `sharedClaimed()` and `sharedServed()` are. */
export function sharedSessionDirectories(): Map<string, string> {
  const slot = globalThis as Record<symbol, Map<string, string> | undefined>;
  return (slot[SHARED_SESSION_DIRECTORIES] ??= new Map<string, string>());
}

export type SessionDirectoryResolverOptions = {
  /** `ctx.session` — only its `get({sessionID})` is used. */
  session: unknown;
  /** The plugin's directory: the answer whenever the lookup fails. */
  fallback: string;
  /** A lookup slower than this counts as failed. Default 2000 (R4). */
  timeoutMs?: number;
  /** Found directories by session id. The plugin passes `sharedSessionDirectories()`. */
  cache?: Map<string, string>;
};

const DEFAULT_LOOKUP_TIMEOUT_MS = 2000;

/** The session's own directory — top-level or child, never its parent's — or
 * `fallback` when the lookup fails, times out, answers about another session or
 * names no directory. Only a found directory is cached, so a failure is asked
 * again next call. Never rejects. */
export function createSessionDirectoryResolver(
  options: SessionDirectoryResolverOptions
): (sessionID: unknown) => Promise<string> {
  const { session, fallback } = options;
  const timeoutMs = options.timeoutMs ?? DEFAULT_LOOKUP_TIMEOUT_MS;
  const cache = options.cache ?? new Map<string, string>();
  return async (sessionID) => {
    if (typeof sessionID !== "string" || sessionID === "") return fallback;
    const known = cache.get(sessionID);
    if (known !== undefined) return known;
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const get = (session as { get?: unknown } | null | undefined)?.get;
      if (typeof get !== "function") return fallback;
      const timeout = new Promise<undefined>((resolve) => {
        timer = setTimeout(() => resolve(undefined), timeoutMs);
      });
      const lookup = Promise.resolve().then(() => get.call(session, { sessionID }));
      // A lookup that rejects after the timer won must not surface as an
      // unhandled rejection.
      lookup.catch(() => undefined);
      const info = (await Promise.race([lookup, timeout])) as SessionInfo | null | undefined;
      if (!info || typeof info !== "object" || info.id !== sessionID) return fallback;
      const directory = sessionDirectory(info, "");
      if (directory === "") return fallback;
      cache.set(sessionID, directory);
      return directory;
    } catch {
      return fallback;
    } finally {
      if (timer !== undefined) clearTimeout(timer);
    }
  };
}
