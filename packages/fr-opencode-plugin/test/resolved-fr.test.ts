// guard-trust R4: every module that starts `fr` spawns `resolveFr()`'s absolute file, resolved
// at call time. A `fr` planted in the working directory and reached only through a relative or
// empty PATH entry is never spawned, and the module gives its missing-fr answer.
import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { createBindHandler, createUnbindHandler } from "../src/bind";
import { createClaimHandler } from "../src/claim";
import { createIdleHandler } from "../src/idle";
import { createNagHandler } from "../src/nag";
import { createPinHandler } from "../src/pin";

let saved: { PATH?: string; HARNESS?: string; cwd: string };
let scratch: string;
let mark: string;

function plant(dir: string): void {
  mkdirSync(dir, { recursive: true });
  const file = join(dir, "fr");
  writeFileSync(file, `#!/bin/sh\nprintf "%s\\n" "$*" >> "${mark}"\n[ "$1" = --identity ] && echo "9.9.9 /x"\nexit 0\n`);
  chmodSync(file, 0o755);
}

beforeEach(() => {
  saved = { PATH: process.env.PATH, HARNESS: process.env.FR_HARNESS_FR, cwd: process.cwd() };
  scratch = mkdtempSync(join(tmpdir(), "fr-opencode-resolved-fr-"));
  mark = join(scratch, "mark");
  delete process.env.FR_HARNESS_FR;
  plant(join(scratch, "work", "bin")); // reachable only as the relative entry `bin`
  process.chdir(join(scratch, "work"));
});

afterEach(() => {
  process.chdir(saved.cwd);
  process.env.PATH = saved.PATH;
  if (saved.HARNESS === undefined) delete process.env.FR_HARNESS_FR;
  else process.env.FR_HARNESS_FR = saved.HARNESS;
  rmSync(scratch, { recursive: true, force: true });
});

const settle = () => new Promise((r) => setTimeout(r, 400));
const planted = () => "bin:./bin::/usr/bin:/bin";
function absolute(): void {
  plant(join(scratch, "abs"));
  process.env.PATH = `bin:${join(scratch, "abs")}:/usr/bin:/bin`;
}

const session = { get: async (r: { sessionID: string }) => ({ id: r.sessionID }), prompt: async () => undefined };
const childSession = {
  get: async (r: { sessionID: string }) => ({ id: r.sessionID, parentID: "root", agent: "fr-phase-executor" }),
};
const bindEvent = {
  tool: "shell",
  status: "completed",
  sessionID: "ses_1",
  input: { command: "fr isolation up --branch b" },
};

describe("pin", () => {
  test("a planted relative fr pins nothing and is never spawned", async () => {
    process.env.PATH = planted();
    const event: { env?: Record<string, string | undefined> } = {};
    await createPinHandler()(event);
    expect(event.env?.FR_HARNESS_FR).toBeUndefined();
    expect(existsSync(mark)).toBe(false);
  });
  test("an absolute fr is the one asked", async () => {
    absolute();
    const event: { env?: Record<string, string | undefined> } = {};
    await createPinHandler()(event);
    expect(event.env?.FR_HARNESS_FR).toBe("9.9.9 /x");
  });
});

describe("claim", () => {
  test("a planted relative fr is never spawned", async () => {
    process.env.PATH = planted();
    await createClaimHandler({ session: childSession, directory: process.cwd() })({ sessionID: "ses_c" });
    expect(existsSync(mark)).toBe(false);
  });
  test("an absolute fr is the one asked", async () => {
    absolute();
    await createClaimHandler({ session: childSession, directory: process.cwd() })({ sessionID: "ses_c" });
    expect(readFileSync(mark, "utf8")).toContain("run claim --open-unit");
  });
});

describe("bind and unbind", () => {
  test("a planted relative fr is never spawned", async () => {
    process.env.PATH = planted();
    await createBindHandler({ session, directory: process.cwd() })(bindEvent);
    await createUnbindHandler({ directory: process.cwd() })({
      type: "session.deleted",
      data: { sessionID: "ses_1" },
    });
    await settle();
    expect(existsSync(mark)).toBe(false);
  });
  test("an absolute fr is the one asked", async () => {
    absolute();
    await createBindHandler({ session, directory: process.cwd() })(bindEvent);
    expect(readFileSync(mark, "utf8")).toContain("isolation attach");
    await createUnbindHandler({ directory: process.cwd() })({
      type: "session.deleted",
      data: { sessionID: "ses_1" },
    });
    await settle();
    expect(readFileSync(mark, "utf8")).toContain("isolation detach");
  });
});

describe("idle", () => {
  const event = { type: "session.idle", data: { sessionID: "ses_1" } };
  test("a planted relative fr is never spawned and no verdict is read", async () => {
    process.env.PATH = planted();
    const prompts: unknown[] = [];
    const api = { ...session, prompt: async (r: unknown) => void prompts.push(r) };
    await createIdleHandler({ session: api, directory: process.cwd() })(event);
    expect(existsSync(mark)).toBe(false);
    expect(prompts).toEqual([]);
  });
  test("an absolute fr is the one asked", async () => {
    absolute();
    await createIdleHandler({ session, directory: process.cwd() })(event);
    expect(readFileSync(mark, "utf8")).toContain("run check --idle");
  });
});

describe("nag", () => {
  // review l-tests-r2: the real default runFr, never a stub.
  function nagRepo(): string {
    const repo = join(scratch, "work");
    mkdirSync(join(repo, ".git"), { recursive: true });
    mkdirSync(join(repo, "docs", "acceptance", "features"), { recursive: true });
    writeFileSync(join(repo, "docs", "acceptance", "features", "f.yaml"), "rows: []\n");
    return repo;
  }
  const ctx = () => ({ sessionID: "ses_n", system: [] as { type: "text"; text: string }[] });
  test("a planted relative fr is never spawned and nothing is said", async () => {
    process.env.PATH = planted();
    const event = ctx();
    await createNagHandler({ session, directory: nagRepo() })(event);
    expect(existsSync(mark)).toBe(false);
    expect(event.system).toEqual([]);
  });
  test("an absolute fr is the one asked", async () => {
    absolute();
    await createNagHandler({ session, directory: nagRepo() })(ctx());
    expect(readFileSync(mark, "utf8")).toContain("acceptance status --brief");
  });
});
