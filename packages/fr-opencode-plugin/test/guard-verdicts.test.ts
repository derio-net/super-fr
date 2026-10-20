// The shell gate against the CAPTURED verdict table (spec 2026-10-20-opencode-2-support §B).
//
// tests/fixtures/hooks/guard-verdicts.yaml was captured by running the bash
// guard (plugins/super-fr/hooks/fr-isolation-guard.sh) in the sandbox
// guard-world.sh builds; tests/unit/test_hooks_guard.py re-runs every row
// against that script. Here every row runs through the TypeScript port in the
// SAME sandbox (the same builder script), and must reach the same verdict, the
// same refusal text and the same sentinel state. A change to one engine that
// is not a change to both goes red on one side.
import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import { decideShell } from "../src/guard";

const FIXTURES = resolve(import.meta.dir, "../../../tests/fixtures/hooks");

type Row = {
  id: string;
  command: string;
  cwd: string;
  sentinel: Record<string, unknown> | null;
  env?: Record<string, string>;
  expected: "allow" | "deny";
  reason: string | null;
  sentinel_after: "present" | "absent" | null;
};

const table = Bun.YAML.parse(readFileSync(join(FIXTURES, "guard-verdicts.yaml"), "utf-8")) as {
  placeholders: Record<string, string>;
  session: string;
  rows: Row[];
};

let root = "";
const ENV_KEYS = ["HOME", "FR_SENTINEL_DIR", "FR_CD_ALLOW_PREFIXES", "FR_BASE_OK", "KUBERNETES_SERVICE_HOST"];
const saved: Record<string, string | undefined> = {};

function abs(rel: string): string {
  return rel ? `${root}/${rel}` : root;
}

function expand(value: string): string {
  for (const [key, rel] of Object.entries(table.placeholders)) value = value.split(key).join(abs(rel));
  return value;
}

function collapse(value: string): string {
  for (const [key, rel] of Object.entries(table.placeholders)) value = value.split(abs(rel)).join(key);
  return value;
}

beforeAll(() => {
  for (const key of ENV_KEYS) saved[key] = process.env[key];
  const tmp = realpathSync(mkdtempSync(join(tmpdir(), "fr-guard-verdicts-")));
  execFileSync("bash", [join(FIXTURES, "guard-world.sh"), join(tmp, "world")], { stdio: "pipe" });
  root = realpathSync(join(tmp, "world"));
});

afterAll(() => {
  for (const key of ENV_KEYS) {
    if (saved[key] === undefined) delete process.env[key];
    else process.env[key] = saved[key];
  }
  if (root) rmSync(resolve(root, ".."), { recursive: true, force: true });
});

describe("the TypeScript shell gate decides every captured row as the bash guard did", () => {
  test("the table is non-trivial", () => {
    expect(table.rows.length).toBeGreaterThanOrEqual(20);
    expect(table.rows.some((r) => r.expected === "deny")).toBe(true);
    expect(table.rows.some((r) => r.sentinel_after === "absent")).toBe(true);
  });

  for (const row of table.rows) {
    test(row.id, () => {
      for (const key of ["FR_BASE_OK", "KUBERNETES_SERVICE_HOST"]) delete process.env[key];
      process.env.HOME = abs("home");
      process.env.FR_SENTINEL_DIR = abs("sentinels");
      process.env.FR_CD_ALLOW_PREFIXES = `${abs("home/.cache/fr/worktrees")}:${abs("scratch")}`;
      Object.assign(process.env, row.env ?? {});

      const sentinels = abs("sentinels");
      rmSync(sentinels, { recursive: true, force: true });
      mkdirSync(sentinels);
      const sentinel = join(sentinels, `${table.session}.json`);
      if (row.sentinel) {
        const data: Record<string, unknown> = {};
        for (const [k, v] of Object.entries(row.sentinel)) data[k] = typeof v === "string" ? expand(v) : v;
        data.skill = "fr-goal";
        writeFileSync(sentinel, JSON.stringify(data));
      }

      const refusal = decideShell(expand(row.command), expand(row.cwd), table.session);

      expect({
        expected: refusal ? "deny" : "allow",
        reason: refusal ? collapse(refusal) : null,
        sentinel_after: row.sentinel ? (existsSync(sentinel) ? "present" : "absent") : null,
      }).toEqual({ expected: row.expected, reason: row.reason, sentinel_after: row.sentinel_after });
    });
  }
});
