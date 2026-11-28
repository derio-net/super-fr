// The edit gate past S1's transition (spec 2026-11-28-s1-followups R7, R8, R10), the
// marker.ts side of tests/unit/test_isolation_decision_transition.py. marker.ts reads its
// release from `VERSION` beside itself (the delivered plugin), else from this package's
// own package.json one directory up (the source tree); neither readable is ended, and
// `FR_OLD_PATHS=refuse` ends it whatever the version. Each test points marker.ts at a
// fixture directory and puts the preload's 9.1.0 back afterwards.
import { afterEach, describe, expect, test } from "bun:test";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";

import {
  matchesAllowlist,
  placementEnabled,
  placementWriteTarget,
  REFUSE_FROM,
  resetFrPaths,
  setVersionDir,
  switchDifferNote,
  transitionEnded,
} from "../src/marker";
import { OPEN_VERSION_DIR } from "./setup";

const made: string[] = [];
function scratch(prefix: string): string {
  const dir = realpathSync(mkdtempSync(join(tmpdir(), prefix)));
  made.push(dir);
  return dir;
}

afterEach(() => {
  setVersionDir(OPEN_VERSION_DIR);
  delete process.env.FR_OLD_PATHS;
  for (const dir of made.splice(0)) rmSync(dir, { recursive: true, force: true });
});

/** A plugin directory whose VERSION says *version* (none when undefined). */
function versionDir(version: string | undefined): string {
  const dir = scratch("fr-version-");
  if (version !== undefined) writeFileSync(join(dir, "VERSION"), `${version}\n`);
  return dir;
}

function sh(cwd: string, args: string[], input?: string): string {
  return execFileSync("git", ["-c", "user.email=t@t", "-c", "user.name=t", ...args], { cwd, input, stdio: "pipe" })
    .toString()
    .trim();
}

function withoutFr<T>(run: () => T): T {
  const saved = process.env.PATH;
  const bin = scratch("fr-transition-nofr-");
  const gitBin = execFileSync("sh", ["-c", "command -v git"]).toString().trim();
  execFileSync("ln", ["-s", gitBin, join(bin, "git")]);
  process.env.PATH = bin;
  resetFrPaths();
  try {
    return run();
  } finally {
    process.env.PATH = saved;
    resetFrPaths();
  }
}

describe("the end is read from the plugin's own version source", () => {
  test("REFUSE_FROM is 9.2", () => expect([...REFUSE_FROM]).toEqual([9, 2]));

  for (const [version, ended] of [
    ["9.1.0", false],
    ["9.1.0-rc.10", false],
    ["8.12.0", false],
    ["9.2.0", true],
    ["9.2.0-rc.1", true],
    ["9.2.0rc1", true],
    ["10.0.0", true],
    ["not-a-version", true],
    [undefined, true],
  ] as const) {
    test(`VERSION ${version ?? "(absent)"} -> ${ended ? "ended" : "open"}`, () => {
      setVersionDir(versionDir(version));
      expect(transitionEnded()).toBe(ended);
    });
  }

  test("in the source tree, this package's package.json is the fallback", () => {
    const pkg = scratch("fr-pkg-");
    mkdirSync(join(pkg, "src"));
    writeFileSync(join(pkg, "package.json"), JSON.stringify({ name: "@derio-net/fr-opencode-plugin", version: "9.1.0" }));
    setVersionDir(join(pkg, "src"));
    expect(transitionEnded()).toBe(false);
    writeFileSync(join(pkg, "package.json"), JSON.stringify({ name: "@derio-net/fr-opencode-plugin", version: "9.2.0" }));
    expect(transitionEnded()).toBe(true);
  });

  test("another package's package.json is no version source", () => {
    const pkg = scratch("fr-pkg-");
    mkdirSync(join(pkg, "plugins"));
    writeFileSync(join(pkg, "package.json"), JSON.stringify({ name: "opencode-config", version: "1.0.0" }));
    setVersionDir(join(pkg, "plugins"));
    expect(transitionEnded()).toBe(true);
  });

  test("the real module reads the source tree's package.json", () => {
    setVersionDir(undefined);
    const pkg = JSON.parse(execFileSync("cat", [join(import.meta.dir, "..", "package.json")]).toString());
    const [major, minor] = String(pkg.version).split(".").map(Number);
    expect(transitionEnded()).toBe(major > 9 || (major === 9 && minor >= 2));
  });

  test("FR_OLD_PATHS=refuse ends it on a 9.1 plugin, and only `refuse` means anything", () => {
    setVersionDir(versionDir("9.1.0"));
    process.env.FR_OLD_PATHS = "keep";
    expect(transitionEnded()).toBe(false);
    process.env.FR_OLD_PATHS = "refuse";
    expect(transitionEnded()).toBe(true);
  });
});

describe("past the end the old forms are not read", () => {
  function repo(): string {
    const dir = scratch("fr-transition-repo-");
    sh(dir, ["init", "-q", "-b", "main"]);
    writeFileSync(join(dir, "README.md"), "x\n");
    sh(dir, ["add", "."]);
    sh(dir, ["commit", "-qm", "init"]);
    sh(dir, ["remote", "add", "origin", "https://example.com/org/repo.git"]);
    return dir;
  }

  function switchRef(dir: string, ref: string, path: string[], settings: string): void {
    const blob = sh(dir, ["hash-object", "-w", "--stdin"], settings);
    let tree = sh(dir, ["mktree"], `100644 blob ${blob}\t${path[path.length - 1]}\n`);
    for (const name of path.slice(0, -1).reverse()) tree = sh(dir, ["mktree"], `040000 tree ${tree}\t${name}\n`);
    sh(dir, ["update-ref", ref, sh(dir, ["commit-tree", tree, "-m", "switch"])]);
  }

  for (const [side, version, allows] of [
    ["open", "9.1.0", true],
    ["ended", "9.2.0", false],
  ] as const) {
    test(`the old allowlist (${side})`, () => {
      setVersionDir(versionDir(version));
      const top = repo();
      writeFileSync(join(top, ".fr-isolation-allow"), "projects/**\n");
      expect(matchesAllowlist(top, join(top, "projects", "x.md"))).toBe(allows);
      mkdirSync(join(top, ".fr"));
      writeFileSync(join(top, ".fr", "isolation-allow"), "data/**\n*\n");
      expect(matchesAllowlist(top, join(top, "data", "x.md"))).toBe(true);
      expect(matchesAllowlist(top, join(top, ".fr-isolation-allow"))).toBe(false);
    });

    test(`an old-only quiet switch is gated, its fr worktree a write target only before the end (${side})`, () => {
      setVersionDir(versionDir(version));
      const home = scratch("fr-transition-home-");
      const saved = process.env.HOME;
      process.env.HOME = home;
      try {
        const parent = scratch("fr-transition-q-");
        const prod = join(parent, "prod");
        mkdirSync(prod);
        sh(prod, ["init", "-q", "-b", "main"]);
        writeFileSync(join(prod, "README.md"), "x\n");
        sh(prod, ["add", "."]);
        sh(prod, ["commit", "-qm", "init"]);
        sh(prod, ["remote", "add", "origin", "https://example.com/org/repo.git"]);
        switchRef(prod, "refs/remotes/origin/fr", ["settings.yaml"], "placement: quiet\n");
        const at = join(home, ".cache", "fr", "worktrees", "prod", "fr");
        mkdirSync(dirname(at), { recursive: true });
        sh(prod, ["worktree", "add", "-q", "-b", "fr", at, "refs/remotes/origin/fr"]);
        withoutFr(() => {
          expect(placementEnabled(prod)).toBe(true);
          expect(placementWriteTarget(realpathSync(at))).toBe(allows);
        });
      } finally {
        if (saved === undefined) delete process.env.HOME;
        else process.env.HOME = saved;
      }
    });

    test(`differing switches add a note only before the end (${side})`, () => {
      setVersionDir(versionDir(version));
      const top = repo();
      switchRef(top, "refs/remotes/origin/fr", ["settings.yaml"], "placement: quiet\n");
      switchRef(top, "refs/remotes/origin/fr-config", [".fr", "settings.yaml"], "placement: quiet\n\n");
      withoutFr(() => expect(switchDifferNote(top).includes("fr settings sync")).toBe(allows));
    });
  }
});
