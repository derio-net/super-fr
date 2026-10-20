// The merged-PR push guard (spec 2026-10-20-opencode-2-support R4). Each
// command's verdict is compared against the REAL bash hook
// (plugins/super-fr/hooks/fr-merged-pr-push-guard.sh) run with a stub `gh` on
// PATH, so the port's push matcher cannot drift from the script's.
import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { chmodSync, mkdirSync, mkdtempSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

import { decidePush, isGitPush } from "../src/push";

const HOOK = resolve(import.meta.dir, "../../../plugins/super-fr/hooks/fr-merged-pr-push-guard.sh");
let root = "";
let saved: string | undefined;

beforeAll(() => {
  root = realpathSync(mkdtempSync(join(tmpdir(), "fr-push-")));
  mkdirSync(join(root, "bin"));
  mkdirSync(join(root, "sentinels"));
  writeFileSync(join(root, "sentinels", "ses_1.json"), JSON.stringify({ repo_root: root }));
  saved = process.env.FR_SENTINEL_DIR;
  process.env.FR_SENTINEL_DIR = join(root, "sentinels");
});

afterAll(() => {
  if (saved === undefined) delete process.env.FR_SENTINEL_DIR;
  else process.env.FR_SENTINEL_DIR = saved;
  rmSync(root, { recursive: true, force: true });
});

function stubGh(state: string): void {
  const gh = join(root, "bin", "gh");
  writeFileSync(gh, `#!/bin/sh\nprintf '{"state":"${state}"}\\n'\n`);
  chmodSync(gh, 0o755);
}

function bashDenies(command: string, session = "ses_1"): boolean {
  const out = spawnSync("bash", [HOOK], {
    input: JSON.stringify({ session_id: session, cwd: root, tool_name: "Bash", tool_input: { command } }),
    env: { ...process.env, PATH: `${join(root, "bin")}:${process.env.PATH}` },
    encoding: "utf-8",
  });
  expect(out.status).toBe(0);
  return out.stdout.includes('"deny"');
}

const merged = async () => ({ code: 0, stdout: '{"state":"MERGED"}\n' });

const COMMANDS = [
  "git push",
  "git push origin feat",
  "git -C /x push",
  "git -c k=v push --force-with-lease",
  "git push;",
  "git push|tee log",
  "cd /x && git push",
  "echo hi\ngit push",
  "git pushy",
  "git push-foo",
  "mygit push",
  "git log --grep=push",
  "git commit -m 'git push later'",
  "gh pr merge 12",
  "ls",
];

describe("push guard", () => {
  test.each(COMMANDS)("matches the bash hook on %p", async (command) => {
    stubGh("MERGED");
    const ts = (await decidePush(command, root, "ses_1", merged)) !== undefined;
    expect(ts).toBe(bashDenies(command));
  });

  test("CLOSED is refused with the hook's text", async () => {
    const reason = await decidePush("git push", root, "ses_1", async () => ({ code: 0, stdout: '{"state":"CLOSED"}' }));
    expect(reason).toBe(
      "Pre-push guard: this branch's PR is CLOSED. Pushing here orphans the commit from `main` (#320 merge-race). " +
        "Stop — cherry-pick the commit onto `main` (or open a fresh branch/PR) instead. See " +
        "plugins/super-fr/skills/fr-isolation (pre-push guard)."
    );
  });

  test("OPEN, no PR, gh failing, garbage and no sentinel all allow", async () => {
    expect(await decidePush("git push", root, "ses_1", async () => ({ code: 0, stdout: '{"state":"OPEN"}' }))).toBeUndefined();
    expect(await decidePush("git push", root, "ses_1", async () => ({ code: 1, stdout: "" }))).toBeUndefined();
    expect(await decidePush("git push", root, "ses_1", async () => ({ code: null, stdout: "" }))).toBeUndefined();
    expect(await decidePush("git push", root, "ses_1", async () => ({ code: 0, stdout: "nope" }))).toBeUndefined();
    expect(await decidePush("git push", root, "ses_none", merged)).toBeUndefined();
    stubGh("MERGED");
    expect(bashDenies("git push", "ses_none")).toBe(false);
  });

  test("a reader that throws still allows", async () => {
    expect(
      await decidePush("git push", root, "ses_1", async () => {
        throw new Error("boom");
      })
    ).toBeUndefined();
  });

  test("the comparison is not vacuous: the bash hook does refuse a push here", () => {
    stubGh("MERGED");
    expect(bashDenies("git push")).toBe(true);
    expect(bashDenies("git pushy")).toBe(false);
  });

  test("isGitPush is per line", () => {
    expect(isGitPush("echo\ngit push")).toBe(true);
    expect(isGitPush("git status")).toBe(false);
  });
});
