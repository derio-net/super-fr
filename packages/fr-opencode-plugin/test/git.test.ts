// gh#1221: one resolved `git`, called in one bounded way, never throwing.
//
// These tests drive the REAL `process.env` rather than a tidy mock object,
// because the module exists for exactly one situation — a PATH this plugin does
// not control, inherited by the OpenCode server with no shell in between — and a
// fake env would prove nothing about it.
import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, realpathSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { DEFAULT_GIT_CANDIDATES, git, resolveGit } from "../src/git";

const realGit = Bun.which("git");
if (!realGit) throw new Error("these tests need a git on PATH to seed their sandbox");

let saved: { PATH?: string; FR_GIT_CANDIDATES?: string };
let scratch: string;

beforeEach(() => {
  saved = { PATH: process.env.PATH, FR_GIT_CANDIDATES: process.env.FR_GIT_CANDIDATES };
  scratch = mkdtempSync(join(tmpdir(), "fr-opencode-git-test-"));
});

afterEach(() => {
  process.env.PATH = saved.PATH;
  if (saved.FR_GIT_CANDIDATES === undefined) delete process.env.FR_GIT_CANDIDATES;
  else process.env.FR_GIT_CANDIDATES = saved.FR_GIT_CANDIDATES;
  rmSync(scratch, { recursive: true, force: true });
});

/** A throwaway repo whose toplevel is `realpath(<scratch>/repo)`. */
function newRepo(): { dir: string; top: string } {
  const dir = join(scratch, "repo");
  mkdirSync(dir);
  execFileSync(realGit!, ["init", "--quiet"], { cwd: dir, stdio: "pipe" });
  // macOS tmpdirs live behind /var -> /private/var; git answers with the real one.
  return { dir, top: realpathSync(dir) };
}

/** The candidates in the bash guard's order, which this list must keep. */
test("DEFAULT_GIT_CANDIDATES is the bash guard's list, bare name first", () => {
  expect(DEFAULT_GIT_CANDIDATES[0]).toBe("git");
  expect([...DEFAULT_GIT_CANDIDATES]).toEqual([
    "git",
    "/usr/bin/git",
    "/usr/local/bin/git",
    "/bin/git",
    "/opt/homebrew/bin/git",
  ]);
});

describe("resolveGit", () => {
  test("resolves the git on PATH when nothing is overridden", () => {
    delete process.env.FR_GIT_CANDIDATES;
    expect(resolveGit()).toBe(realGit!);
  });

  test("returns null when no candidate is executable — never a bare name", () => {
    process.env.PATH = scratch; // an empty directory: nothing on it
    process.env.FR_GIT_CANDIDATES = join(scratch, "no-such-git");
    expect(resolveGit()).toBeNull();
  });

  test("an ABSOLUTE candidate survives a PATH that lost /usr/bin (gh#746 shape)", () => {
    const { dir, top } = newRepo();
    process.env.PATH = scratch;
    process.env.FR_GIT_CANDIDATES = realGit;
    expect(resolveGit()).toBe(realGit!);
    expect(git(dir, "rev-parse", "--show-toplevel")).toBe(top);
  });

  test("an empty FR_GIT_CANDIDATES falls back to the defaults, not to nothing", () => {
    delete process.env.FR_GIT_CANDIDATES;
    process.env.FR_GIT_CANDIDATES = "   ";
    expect(resolveGit()).toBe(realGit!);
  });

  test("the answer is cached per overridden env, with no reset hook to forget", () => {
    process.env.PATH = scratch;
    process.env.FR_GIT_CANDIDATES = join(scratch, "no-such-git");
    expect(resolveGit()).toBeNull();

    // Same process, different env: a session whose PATH was repaired gets git
    // back without anything having to clear module state.
    process.env.FR_GIT_CANDIDATES = realGit;
    expect(resolveGit()).toBe(realGit!);
  });
});

describe("git", () => {
  test("answers trimmed stdout for a repo", () => {
    const { dir, top } = newRepo();
    delete process.env.FR_GIT_CANDIDATES;
    expect(git(dir, "rev-parse", "--show-toplevel")).toBe(top);
  });

  test("a non-repository is undefined, not an exception", () => {
    delete process.env.FR_GIT_CANDIDATES;
    expect(git(scratch, "rev-parse", "--show-toplevel")).toBeUndefined();
  });

  test("unresolvable git is undefined — the fail-open the gates rely on", () => {
    const { dir } = newRepo();
    process.env.PATH = scratch;
    process.env.FR_GIT_CANDIDATES = join(scratch, "no-such-git");
    expect(git(dir, "rev-parse", "--show-toplevel")).toBeUndefined();
  });

  test("an empty answer is undefined, so callers never see \"\" as a toplevel", () => {
    const { dir } = newRepo();
    delete process.env.FR_GIT_CANDIDATES;
    // `git <dir> rev-parse --quiet --verify` of a missing ref prints nothing.
    expect(git(dir, "rev-parse", "--quiet", "--verify", "refs/heads/nope")).toBeUndefined();
  });
});
