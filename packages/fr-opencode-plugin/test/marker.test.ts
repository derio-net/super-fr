// Unit tests for the extracted marker-resolution logic (src/marker.ts),
// isolated from the tool.execute.before wiring in index.test.ts.
import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { resolveMarker } from "../src/marker";

function sh(cmd: string, args: string[], cwd: string): void {
  execFileSync(cmd, args, { cwd, stdio: "pipe" });
}

let repo: string;
let savedK8s: string | undefined;

beforeEach(() => {
  // The `external` branch keys off live container evidence; on the host test
  // runner /.dockerenv and /run/.containerenv are absent, so
  // KUBERNETES_SERVICE_HOST is the controllable evidence. Isolate it per test.
  savedK8s = process.env.KUBERNETES_SERVICE_HOST;
  delete process.env.KUBERNETES_SERVICE_HOST;
  repo = mkdtempSync(join(tmpdir(), "fr-opencode-marker-test-"));
  sh("git", ["init", "--quiet"], repo);
  sh("git", ["config", "user.email", "test@example.com"], repo);
  sh("git", ["config", "user.name", "Test"], repo);
  writeFileSync(join(repo, "README.md"), "placeholder\n");
  sh("git", ["add", "."], repo);
  sh("git", ["commit", "--quiet", "-m", "init"], repo);
});

afterEach(() => {
  if (savedK8s === undefined) delete process.env.KUBERNETES_SERVICE_HOST;
  else process.env.KUBERNETES_SERVICE_HOST = savedK8s;
  rmSync(repo, { recursive: true, force: true });
});

describe("resolveMarker", () => {
  test("frEnabled is false with no devcontainer profile or plans dir", () => {
    const result = resolveMarker(join(repo, "README.md"));
    expect(result.frEnabled).toBe(false);
  });

  test("frEnabled is true when a devcontainer profile exists", () => {
    mkdirSync(join(repo, ".devcontainer", "dev"), { recursive: true });
    writeFileSync(join(repo, ".devcontainer", "dev", "devcontainer.json"), "{}\n");
    const result = resolveMarker(join(repo, "README.md"));
    expect(result.frEnabled).toBe(true);
    expect(result.hasValidMarker).toBe(false);
  });

  test("frEnabled is true when a docs/superpowers/plans dir exists", () => {
    mkdirSync(join(repo, "docs", "superpowers", "plans"), { recursive: true });
    const result = resolveMarker(join(repo, "README.md"));
    expect(result.frEnabled).toBe(true);
  });

  test("a marker with mode != worktree is never valid", () => {
    mkdirSync(join(repo, "docs", "superpowers", "plans"), { recursive: true });
    writeFileSync(
      join(repo, ".fr-isolation"),
      JSON.stringify({ toplevel: repo, mode: "devcontainer" })
    );
    const result = resolveMarker(join(repo, "README.md"));
    expect(result.hasValidMarker).toBe(false);
  });

  test("a linked-worktree marker carrying fr's `target` key stays valid (p2-r20)", () => {
    const wt = mkdtempSync(join(tmpdir(), "fr-opencode-marker-wt-"));
    rmSync(wt, { recursive: true, force: true });
    sh("git", ["worktree", "add", "--quiet", "-b", "feat/target", wt], repo);
    try {
      mkdirSync(join(wt, "docs", "superpowers", "plans"), { recursive: true });
      const top = execFileSync("git", ["rev-parse", "--show-toplevel"], { cwd: wt })
        .toString()
        .trim();
      writeFileSync(
        join(wt, ".fr-isolation"),
        JSON.stringify({ toplevel: top, branch: "feat/target", mode: "worktree", target: "worktree" })
      );
      expect(resolveMarker(join(wt, "README.md")).hasValidMarker).toBe(true);
    } finally {
      rmSync(wt, { recursive: true, force: true });
    }
  });

  test("a marker recorded for a different toplevel is never valid", () => {
    mkdirSync(join(repo, "docs", "superpowers", "plans"), { recursive: true });
    writeFileSync(
      join(repo, ".fr-isolation"),
      JSON.stringify({ toplevel: "/some/other/path", mode: "worktree" })
    );
    const result = resolveMarker(join(repo, "README.md"));
    expect(result.hasValidMarker).toBe(false);
  });

  test("a marker in the primary working tree (not a linked worktree) is never valid", () => {
    mkdirSync(join(repo, "docs", "superpowers", "plans"), { recursive: true });
    // Recorded toplevel matches, mode is "worktree", but this IS the primary
    // clone — git-common-dir == git-dir, so it must still fail closed.
    writeFileSync(
      join(repo, ".fr-isolation"),
      JSON.stringify({ toplevel: repo, mode: "worktree" })
    );
    const result = resolveMarker(join(repo, "README.md"));
    expect(result.hasValidMarker).toBe(false);
  });

  test("an external marker with container evidence (KUBERNETES_SERVICE_HOST) is valid", () => {
    mkdirSync(join(repo, "docs", "superpowers", "plans"), { recursive: true });
    // external mode needs no linked-worktree; the primary clone is fine so long
    // as the toplevel matches AND live container evidence is present.
    writeFileSync(
      join(repo, ".fr-isolation"),
      JSON.stringify({ toplevel: repo, mode: "external" })
    );
    process.env.KUBERNETES_SERVICE_HOST = "10.0.0.1";
    const result = resolveMarker(join(repo, "README.md"));
    expect(result.hasValidMarker).toBe(true);
  });

  test("an external marker with no container evidence is never valid", () => {
    mkdirSync(join(repo, "docs", "superpowers", "plans"), { recursive: true });
    // No KUBERNETES_SERVICE_HOST, and /.dockerenv and /run/.containerenv are
    // absent on the host runner — a marker forged on a bare host fails closed.
    writeFileSync(
      join(repo, ".fr-isolation"),
      JSON.stringify({ toplevel: repo, mode: "external" })
    );
    const result = resolveMarker(join(repo, "README.md"));
    expect(result.hasValidMarker).toBe(false);
  });

  test("an external marker recorded for a different toplevel is never valid even with evidence", () => {
    mkdirSync(join(repo, "docs", "superpowers", "plans"), { recursive: true });
    writeFileSync(
      join(repo, ".fr-isolation"),
      JSON.stringify({ toplevel: "/some/other/path", mode: "external" })
    );
    process.env.KUBERNETES_SERVICE_HOST = "10.0.0.1";
    const result = resolveMarker(join(repo, "README.md"));
    expect(result.hasValidMarker).toBe(false);
  });

  test("a worktree marker whose HEAD drifted to another branch is invalid and names both (gh#553)", () => {
    const wt = mkdtempSync(join(tmpdir(), "fr-opencode-marker-wt-"));
    rmSync(wt, { recursive: true, force: true });
    sh("git", ["worktree", "add", "--quiet", "-b", "feat/target", wt], repo);
    try {
      mkdirSync(join(wt, "docs", "superpowers", "plans"), { recursive: true });
      const top = execFileSync("git", ["rev-parse", "--show-toplevel"], { cwd: wt })
        .toString()
        .trim();
      writeFileSync(
        join(wt, ".fr-isolation"),
        JSON.stringify({ toplevel: top, branch: "feat/target", mode: "worktree" })
      );
      sh("git", ["checkout", "--quiet", "-b", "chore/elsewhere"], wt);
      const result = resolveMarker(join(wt, "README.md"));
      expect(result.hasValidMarker).toBe(false);
      expect(result.drift).toEqual({ marker: "feat/target", head: "chore/elsewhere" });

      sh("git", ["checkout", "--quiet", "--detach"], wt); // mid-rebase shape: not drift
      expect(resolveMarker(join(wt, "README.md")).hasValidMarker).toBe(true);
    } finally {
      rmSync(wt, { recursive: true, force: true });
    }
  });
});

// gh#1221: with git unreachable there is no toplevel, so there is no verdict
// at all — `toplevel: null`, `frEnabled: false`. The caller allows; that is the
// bash guard's documented posture, and the plugin says so at load (setup's one
// warning) rather than letting an allow read as a decision.
describe("fail-open when git is unreachable (gh#1221)", () => {
  test("no toplevel, no fr-enabled answer, no marker", () => {
    mkdirSync(join(repo, ".devcontainer", "dev"), { recursive: true });
    writeFileSync(join(repo, ".devcontainer", "dev", "devcontainer.json"), "{}\n");
    const savedPath = process.env.PATH;
    const savedCandidates = process.env.FR_GIT_CANDIDATES;
    const empty = mkdtempSync(join(tmpdir(), "fr-opencode-nogit-"));
    try {
      process.env.PATH = empty;
      process.env.FR_GIT_CANDIDATES = join(empty, "no-such-git");
      expect(resolveMarker(join(repo, "README.md"))).toEqual({
        toplevel: null,
        frEnabled: false,
        hasValidMarker: false,
      });
    } finally {
      process.env.PATH = savedPath;
      if (savedCandidates === undefined) delete process.env.FR_GIT_CANDIDATES;
      else process.env.FR_GIT_CANDIDATES = savedCandidates;
      rmSync(empty, { recursive: true, force: true });
    }
  });
});

// R26 (spec 2026-11-04-repo-feature-settings): quiet and stealth are fr-enabled, and the
// plugin has one definition of that, which asks `fr settings paths --json`.
import { frEnabled as guardFrEnabled } from "../src/guard";
import { frEnabled, frPaths, placementEnabled, resetFrPaths, warnIfFrUnresolved } from "../src/marker";

function quietSwitch(dir: string, settings = "placement: quiet\n"): void {
  sh("git", ["remote", "add", "origin", "https://example.com/org/repo.git"], dir);
  const blob = execFileSync("git", ["hash-object", "-w", "--stdin"], { cwd: dir, input: settings }).toString().trim();
  const tree = execFileSync("git", ["mktree"], { cwd: dir, input: `100644 blob ${blob}\tsettings.yaml\n` })
    .toString()
    .trim();
  const commit = execFileSync("git", ["commit-tree", tree, "-m", "switch"], { cwd: dir }).toString().trim();
  sh("git", ["update-ref", "refs/remotes/origin/fr", commit], dir);
}

/** A stub `fr` first on PATH answering `settings paths --json` with *json* (exit *code*). */
function withFr<T>(body: string, run: () => T): T {
  const bin = mkdtempSync(join(tmpdir(), "fr-opencode-frbin-"));
  writeFileSync(join(bin, "fr"), `#!/bin/sh\n${body}\n`, { mode: 0o755 });
  const saved = process.env.PATH;
  process.env.PATH = `${bin}:${saved}`;
  resetFrPaths();
  try {
    return run();
  } finally {
    process.env.PATH = saved;
    resetFrPaths();
    rmSync(bin, { recursive: true, force: true });
  }
}

function withoutFr<T>(run: () => T): T {
  const saved = process.env.PATH;
  // keep git, drop any `fr`: a directory holding only a `git` symlink
  const bin = mkdtempSync(join(tmpdir(), "fr-opencode-nofr-"));
  const gitBin = execFileSync("sh", ["-c", "command -v git"]).toString().trim();
  execFileSync("ln", ["-s", gitBin, join(bin, "git")]);
  process.env.PATH = bin;
  resetFrPaths();
  try {
    return run();
  } finally {
    process.env.PATH = saved;
    resetFrPaths();
    rmSync(bin, { recursive: true, force: true });
  }
}

describe("quiet and stealth are fr-enabled (R26)", () => {
  test("guard.ts and marker.ts share one frEnabled", () => {
    expect(guardFrEnabled).toBe(frEnabled);
  });

  test("the quiet switch makes a profile-less, plans-less repo fr-enabled, with or without fr", () => {
    quietSwitch(repo);
    withoutFr(() => {
      expect(placementEnabled(repo)).toBe(true);
      expect(resolveMarker(join(repo, "README.md")).frEnabled).toBe(true);
    });
    withFr("exit 3", () => expect(resolveMarker(join(repo, "README.md")).frEnabled).toBe(true));
  });

  test("an fr branch without the switch is not fr-enabled", () => {
    quietSwitch(repo, "placement: repo\n");
    withoutFr(() => expect(resolveMarker(join(repo, "README.md")).frEnabled).toBe(false));
  });

  test("a stealth marker makes the workspace fr-enabled", () => {
    writeFileSync(
      join(repo, ".fr-isolation"),
      JSON.stringify({ toplevel: repo, branch: "main", mode: "worktree", placement: "stealth" }),
    );
    withoutFr(() => {
      const result = resolveMarker(join(repo, "README.md"));
      expect(result.frEnabled).toBe(true);
      expect(result.hasValidMarker).toBe(false); // the primary tree: a copied marker never validates
    });
  });

  test("fr settings paths --json names the placement", () => {
    quietSwitch(repo, "placement: repo\n"); // the cheap precondition: an origin/fr ref
    withFr(`echo '{"FR_PLACEMENT": "quiet", "FR_PLANS_DIR": "/nowhere/plans"}'`, () => {
      expect(frPaths(repo)?.placement).toBe("quiet");
      expect(frEnabled(repo)).toBe(true);
    });
  });

  test("fr settings paths --json naming an existing plans dir makes the repo fr-enabled", () => {
    const plans = mkdtempSync(join(tmpdir(), "fr-opencode-plans-"));
    quietSwitch(repo, "placement: repo\n");
    try {
      withFr(`echo '{"FR_PLACEMENT": "repo", "FR_PLANS_DIR": "${plans}"}'`, () => expect(frEnabled(repo)).toBe(true));
    } finally {
      rmSync(plans, { recursive: true, force: true });
    }
  });

  test("a failing or garbled fr falls back to the direct checks, never to no", () => {
    quietSwitch(repo);
    withFr(`echo 'not json {'; exit 0`, () => {
      expect(frPaths(repo)).toBeNull();
      expect(frEnabled(repo)).toBe(true);
    });
    withFr(`echo '[1,2]'`, () => expect(frPaths(repo)).toBeNull());
    withFr(`echo '{"FR_PLACEMENT": "repo"}'; exit 4`, () => expect(frPaths(repo)).toBeNull());
  });

  test("frPaths caches its answer per toplevel", () => {
    const counter = join(repo, "..", `count-${process.pid}`);
    withFr(`echo x >> ${counter}; echo '{"FR_PLACEMENT": "repo"}'`, () => {
      frPaths(repo);
      frPaths(repo);
      expect(readFileSync(counter, "utf-8").trim().split("\n")).toHaveLength(1);
    });
    rmSync(counter, { force: true });
  });

  test("with no fr the plugin says so once, and still falls back to the plans test", () => {
    mkdirSync(join(repo, "docs", "superpowers", "plans"), { recursive: true });
    const lines: string[] = [];
    const real = console.error;
    console.error = (m: string) => void lines.push(String(m));
    try {
      withoutFr(() => {
        expect(warnIfFrUnresolved()).toBe(true);
        expect(warnIfFrUnresolved()).toBe(false);
        expect(frEnabled(repo)).toBe(true);
      });
    } finally {
      console.error = real;
    }
    expect(lines).toHaveLength(1);
    expect(lines[0]).toContain("no `fr` found");
  });
});

describe("fr resolution trusts only absolute PATH entries", () => {
  test("a relative or empty PATH entry holding an executable fr is never chosen or spawned", async () => {
    const { resolveFr } = await import("../src/fr");
    const marker = join(repo, "planted-ran");
    // a planted `fr` inside the repo being edited, reachable by `.`, `bin` and ``
    mkdirSync(join(repo, "bin"));
    for (const dir of [repo, join(repo, "bin")]) {
      writeFileSync(join(dir, "fr"), `#!/bin/sh\ntouch ${marker}\necho '{"FR_PLACEMENT": "quiet"}'\n`, { mode: 0o755 });
    }
    const savedPath = process.env.PATH;
    const savedCwd = process.cwd();
    try {
      quietSwitch(repo, "placement: repo\n"); // so frEnabled would ask fr
      process.chdir(repo);
      for (const relative of [".", "bin", "", `bin${":"}.`]) {
        expect(resolveFr({ PATH: relative })).toBeNull();
      }
      process.env.PATH = `.:bin::${savedPath}`;
      resetFrPaths();
      expect(frEnabled(repo)).toBe(false); // the planted fr said quiet; it must not be asked
      expect(existsSync(marker)).toBe(false);
    } finally {
      process.chdir(savedCwd);
      process.env.PATH = savedPath;
      resetFrPaths();
    }
  });
});

// Review p6 findings: no fr on a plain repo, a trusted and read-only fr otherwise, a
// fail-closed read of the switch, and FR_REPO_ROOT pinned to the toplevel asked about.
import { switchEnabled, switchRefMaybe } from "../src/marker";

describe("review p6: what the plugin spawns, and when", () => {
  test("a plain repo's decision spawns no fr (p6-r1)", () => {
    const log = join(repo, "..", `calls-${process.pid}-plain`);
    sh("git", ["remote", "add", "origin", "https://example.com/org/repo.git"], repo);
    withFr(`echo "$*" >> ${log}; echo '{"FR_PLACEMENT": "quiet"}'`, () => {
      expect(resolveMarker(join(repo, "README.md")).frEnabled).toBe(false);
    });
    expect(existsSync(log)).toBe(false);
  });

  test("fr is asked read-only, with --no-create (p6-r4)", () => {
    const log = join(repo, "..", `calls-${process.pid}-nocreate`);
    quietSwitch(repo, "placement: repo\n");
    withFr(`echo "$*" >> ${log}; echo '{"FR_PLACEMENT": "repo"}'`, () => frEnabled(repo));
    expect(readFileSync(log, "utf-8").trim()).toBe("settings paths --json --no-create");
    rmSync(log, { force: true });
  });

  test("fr runs with FR_REPO_ROOT set to the toplevel, never an inherited one (p6-r9)", () => {
    const saved = process.env.FR_REPO_ROOT;
    process.env.FR_REPO_ROOT = "/somewhere/else.invalid";
    try {
      withFr(`echo "{\\"FR_PLACEMENT\\": \\"repo\\", \\"FR_PLANS_DIR\\": \\"$FR_REPO_ROOT\\"}"`, () => {
        expect(frPaths(repo)?.plansDir).toBe(repo);
      });
    } finally {
      if (saved === undefined) delete process.env.FR_REPO_ROOT;
      else process.env.FR_REPO_ROOT = saved;
    }
  });

  test("an absolute FR_HARNESS_FR path is preferred; an identity string is not a path (p6-r2)", async () => {
    const { resolveFr } = await import("../src/fr");
    const bin = mkdtempSync(join(tmpdir(), "fr-opencode-pin-"));
    const pinned = join(bin, "fr");
    writeFileSync(pinned, "#!/bin/sh\n", { mode: 0o755 });
    try {
      expect(resolveFr({ PATH: "/usr/bin:/bin", FR_HARNESS_FR: pinned })).toBe(realpathSync(pinned));
      expect(resolveFr({ PATH: bin, FR_HARNESS_FR: `7.0.0 ${bin}` })).toBe(realpathSync(pinned));
      expect(resolveFr({ PATH: "", FR_HARNESS_FR: "fr" })).toBeNull();
    } finally {
      rmSync(bin, { recursive: true, force: true });
    }
  });

  test("the switch ref is found on the filesystem: loose, packed, or not at all (p6-r8)", () => {
    expect(switchRefMaybe(repo)).toBe(false);
    quietSwitch(repo);
    expect(switchRefMaybe(repo)).toBe(true);
    sh("git", ["pack-refs", "--all"], repo);
    expect(existsSync(join(repo, ".git", "refs", "remotes", "origin", "fr"))).toBe(false);
    expect(switchRefMaybe(repo)).toBe(true);
  });
});

const NON_CANONICAL_QUIET: Record<string, string> = {
  "double-quoted": 'placement: "quiet"\n',
  "single-quoted": "placement: 'quiet'\n",
  "trailing-comment": "placement: quiet # c\n",
  "flow-mapping": "{placement: quiet}\n",
  indented: "  placement: quiet\n",
  "quoted-key": '"placement": quiet\n',
  "crlf-canonical": "placement: quiet\r\n",
  "two-lines": "placement: repo\nplacement: quiet\n",
  "quoted-repo": 'placement: "repo"\n',
};

describe("every spelling of a placement is fr-enabled without fr (p6-r3)", () => {
  for (const [name, text] of Object.entries(NON_CANONICAL_QUIET)) {
    test(name, () => {
      expect(switchEnabled(text)).toBe(true);
      quietSwitch(repo, text);
      withoutFr(() => expect(resolveMarker(join(repo, "README.md")).frEnabled).toBe(true));
    });
  }

  test("the canonical repo line, or no placement at all, is repo", () => {
    expect(switchEnabled("placement: repo\n")).toBe(false);
    expect(switchEnabled("schema: 1\n## placement: quiet is prose\n")).toBe(false);
    expect(switchEnabled("placement: quiet\n")).toBe(true);
  });
});

// Review pr1431-n6: the placement question reads the filesystem first, so a plain repo
// (no `refs/remotes/origin/fr`) spawns no `git config` / `git cat-file` for it.
describe("the placement question spawns no git in a plain repo (pr1431-n6)", () => {
  function withRecordingGit<T>(run: (log: string) => T): T {
    const bin = mkdtempSync(join(tmpdir(), "fr-opencode-gitrec-"));
    const log = join(bin, "calls.log");
    const real = execFileSync("sh", ["-c", "command -v git"]).toString().trim();
    writeFileSync(join(bin, "git"), `#!/bin/sh\nprintf '%s\\n' "$*" >> '${log}'\nexec '${real}' "$@"\n`, {
      mode: 0o755,
    });
    const saved = process.env.FR_GIT_CANDIDATES;
    process.env.FR_GIT_CANDIDATES = join(bin, "git");
    try {
      return run(log);
    } finally {
      if (saved === undefined) delete process.env.FR_GIT_CANDIDATES;
      else process.env.FR_GIT_CANDIDATES = saved;
      rmSync(bin, { recursive: true, force: true });
    }
  }
  const placementCalls = (log: string): string[] =>
    existsSync(log)
      ? readFileSync(log, "utf-8")
          .split("\n")
          .filter((c) => c.includes("config") || c.includes("cat-file"))
      : [];

  test("a plain repo with an origin remote", () => {
    sh("git", ["remote", "add", "origin", "https://example.com/org/repo.git"], repo);
    withRecordingGit((log) => {
      withoutFr(() => {
        expect(placementEnabled(repo)).toBe(false);
        expect(resolveMarker(join(repo, "README.md")).frEnabled).toBe(false);
      });
      expect(placementCalls(log)).toEqual([]);
    });
  });

  test("a quiet repo still reads its switch", () => {
    quietSwitch(repo);
    withRecordingGit((log) => {
      withoutFr(() => expect(placementEnabled(repo)).toBe(true));
      expect(placementCalls(log).some((c) => c.includes("cat-file"))).toBe(true);
    });
  });
});
