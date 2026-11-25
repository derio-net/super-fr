// The shared behavioural table of the edit gate (review p2-r6): the cases in
// tests/fixtures/isolation-decision-cases.json, which tests/unit/test_isolation_decision_cases.py
// drives through the bash library. A logic edit to one engine alone fails one of the two suites.
import { describe, expect, test } from "bun:test";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import {
  allowlistProtected,
  configTreeOk,
  placementEnabled,
  readSwitch,
  resetFrPaths,
  stealthHeadMatches,
  switchIsQuiet,
} from "../src/marker";

type Side = null | { settings: string | null };
const CASES = JSON.parse(
  readFileSync(join(import.meta.dir, "..", "..", "..", "tests", "fixtures", "isolation-decision-cases.json"), "utf-8")
);

function git(cwd: string, args: string[], input?: string): string {
  return execFileSync("git", ["-c", "user.email=t@t", "-c", "user.name=t", ...args], { cwd, input })
    .toString()
    .trim();
}

function switchRef(repo: string, ref: string, path: string[], settings: string | null): void {
  let tree: string;
  if (settings === null) {
    const blob = git(repo, ["hash-object", "-w", "--stdin"], "other\n");
    tree = git(repo, ["mktree"], `100644 blob ${blob}\tnotes.md\n`);
  } else {
    const blob = git(repo, ["hash-object", "-w", "--stdin"], settings);
    tree = git(repo, ["mktree"], `100644 blob ${blob}\t${path[path.length - 1]}\n`);
    for (const name of path.slice(0, -1).reverse()) tree = git(repo, ["mktree"], `040000 tree ${tree}\t${name}\n`);
  }
  const commit = git(repo, ["commit-tree", tree, "-m", "switch"]);
  git(repo, ["update-ref", ref, commit]);
}

function withoutFr<T>(run: () => T): T {
  const saved = process.env.PATH;
  const bin = mkdtempSync(join(tmpdir(), "fr-cases-nofr-"));
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

describe("shared cases: switch", () => {
  for (const c of CASES.switch as { id: string; new: Side; old: Side; read: boolean; enabled: boolean; quiet: boolean }[]) {
    test(c.id, () => {
      const root = realpathSync(mkdtempSync(join(tmpdir(), "fr-cases-")));
      try {
        const repo = join(root, "r");
        mkdirSync(repo);
        git(repo, ["init", "-q", "-b", "main"]);
        git(repo, ["remote", "add", "origin", "https://example.com/org/repo.git"]);
        if (c.new !== null) switchRef(repo, "refs/remotes/origin/fr-config", [".fr", "settings.yaml"], c.new.settings);
        if (c.old !== null) switchRef(repo, "refs/remotes/origin/fr", ["settings.yaml"], c.old.settings);
        withoutFr(() => {
          const text = readSwitch(repo);
          expect([text !== undefined, placementEnabled(repo), text !== undefined && switchIsQuiet(text)]).toEqual([
            c.read,
            c.enabled,
            c.quiet,
          ]);
        });
      } finally {
        rmSync(root, { recursive: true, force: true });
      }
    });
  }
});

describe("shared cases: allowlist self-protection", () => {
  for (const c of CASES.allowlist as { id: string; rel: string; protected: boolean }[]) {
    test(c.id, () => {
      const top = realpathSync(mkdtempSync(join(tmpdir(), "fr-cases-")));
      try {
        expect(allowlistProtected(top, `${top}/${c.rel}`, c.rel)).toBe(c.protected);
      } finally {
        rmSync(top, { recursive: true, force: true });
      }
    });
  }
});

describe("shared cases: configuration tree", () => {
  for (const c of CASES.config_tree as { id: string; depth: 0 | 1; names: string[]; ok: boolean }[]) {
    test(c.id, () => expect(configTreeOk(c.depth, c.names)).toBe(c.ok));
  }
});

describe("shared cases: stealth clone naming", () => {
  for (const c of CASES.stealth_head as { id: string; clone: string; branch: string; head: string; ok: boolean }[]) {
    test(c.id, () => expect(stealthHeadMatches(c.clone, c.branch, c.head)).toBe(c.ok));
  }
});
