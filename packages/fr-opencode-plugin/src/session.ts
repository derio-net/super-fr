// What the handlers read off a session's info — shared, so nag, bind, claim and
// idle all ask the same question the same way (consumer-delivery R4-R7).

export type SessionInfo = { id?: unknown; parentID?: unknown; location?: { directory?: unknown } | null };

/** Where fr is asked: the session's own `location.directory` (gh#1371 — a
 * session can live in another checkout than the plugin), else `fallback`. */
export function sessionDirectory(info: SessionInfo, fallback: string): string {
  const directory = info.location?.directory;
  return typeof directory === "string" && directory !== "" ? directory : fallback;
}
