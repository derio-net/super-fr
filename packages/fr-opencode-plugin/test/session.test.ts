// The session-directory resolver the gates judge in (spec 2026-11-19-consumer-followups R4).
import { describe, expect, test } from "bun:test";
import { createSessionDirectoryResolver, sharedSessionDirectories } from "../src/session";

const FALLBACK = "/plugin/dir";

function counting(answer: (request: { sessionID: string }) => unknown) {
  const calls: string[] = [];
  const session = {
    get(request: { sessionID: string }) {
      calls.push(request.sessionID);
      return answer(request);
    },
  };
  return { session, calls };
}

describe("createSessionDirectoryResolver", () => {
  test("returns the session's own directory and caches it", async () => {
    const { session, calls } = counting(({ sessionID }) => Promise.resolve({ id: sessionID, location: { directory: "/repo/b" } }));
    const resolveDir = createSessionDirectoryResolver({ session, fallback: FALLBACK, cache: new Map() });
    expect(await resolveDir("ses_1")).toBe("/repo/b");
    expect(await resolveDir("ses_1")).toBe("/repo/b");
    expect(calls).toEqual(["ses_1"]);
  });

  const failures: Array<[string, (request: { sessionID: string }) => unknown]> = [
    ["a throwing get", () => {
      throw new Error("boom");
    }],
    ["a rejecting get", () => Promise.reject(new Error("boom"))],
    ["an answer about another session", () => Promise.resolve({ id: "ses_other", location: { directory: "/repo/b" } })],
    ["an answer with no location", ({ sessionID }) => Promise.resolve({ id: sessionID })],
    ["an answer with an empty directory", ({ sessionID }) => Promise.resolve({ id: sessionID, location: { directory: "" } })],
    ["a null answer", () => Promise.resolve(null)],
    ["a get that never answers", () => new Promise(() => undefined)],
  ];
  for (const [name, answer] of failures) {
    test(`${name} returns the fallback, uncached`, async () => {
      const { session, calls } = counting(answer);
      const resolveDir = createSessionDirectoryResolver({ session, fallback: FALLBACK, timeoutMs: 20, cache: new Map() });
      expect(await resolveDir("ses_1")).toBe(FALLBACK);
      expect(await resolveDir("ses_1")).toBe(FALLBACK);
      expect(calls).toEqual(["ses_1", "ses_1"]);
    });
  }

  test("a child session gets its own directory, never its parent's", async () => {
    const { session } = counting(({ sessionID }) =>
      Promise.resolve({ id: sessionID, parentID: "ses_parent", location: { directory: "/repo/child" } })
    );
    const resolveDir = createSessionDirectoryResolver({ session, fallback: FALLBACK, cache: new Map() });
    expect(await resolveDir("ses_child")).toBe("/repo/child");
  });

  test("a session with no get, or a missing session id, is the fallback with no lookup", async () => {
    expect(await createSessionDirectoryResolver({ session: {}, fallback: FALLBACK, cache: new Map() })("ses_1")).toBe(FALLBACK);
    const { session, calls } = counting(() => Promise.resolve({ id: "x", location: { directory: "/x" } }));
    const resolveDir = createSessionDirectoryResolver({ session, fallback: FALLBACK, cache: new Map() });
    expect(await resolveDir(undefined)).toBe(FALLBACK);
    expect(await resolveDir("")).toBe(FALLBACK);
    expect(calls).toEqual([]);
  });

  test("never rejects, whatever the session object does", async () => {
    const hostile = new Proxy({}, { get() { throw new Error("hostile"); } });
    const resolveDir = createSessionDirectoryResolver({ session: hostile, fallback: FALLBACK, cache: new Map() });
    expect(await resolveDir("ses_1")).toBe(FALLBACK);
  });

  test("the shared cache is process-wide, so a reloaded copy reads the same map", () => {
    expect(sharedSessionDirectories()).toBe(sharedSessionDirectories());
  });
});
