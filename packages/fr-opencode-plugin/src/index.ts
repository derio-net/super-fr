// OpenCode plugin: deny Edit/Write-class tool calls targeting tracked
// source in an fr-enabled repo unless a valid .fr-isolation marker is
// present. Ports plugins/super-fr/hooks/fr-isolation-required.sh (a Claude
// Code PreToolUse hook) to OpenCode's tool.execute.before hook — see that
// script for the authoritative decision-logic comments; this file mirrors
// its behavior exactly (fail-closed on ambiguity, same two escape hatches).
//
// The `super-fr-parity:` marker below is how `fr harness parity --check`
// observes what this plugin ports: OpenCode has no registration file, only
// source, so the marker IS the declaration (spec §3.B). Add one line per
// shipped hook this plugin ports; `fr.harness.observe` errors if a marker
// names a script absent from plugins/super-fr/hooks/.
// super-fr-parity: fr-isolation-required.sh
//
// The `event` hook below is the OpenCode half of the idle guard (gh#518) — see
// ./idle.ts. It CONTINUES an idle run where Claude Code's Stop hook blocks the
// stop, which is why parity.yaml declares it `partial`, not `enforced`.
// super-fr-parity: fr-run-idle-guard.sh
//
// `tool.execute.before` also carries the child-session claim (gh#530) — see
// ./claim.ts. It ports no hook script (a Claude Code dispatch returns its id at
// once), so it has no marker; parity.yaml's `dispatch-holder-identity` row
// describes it.
//
// `shell.env` carries the run-session export (spec 2026-10-02-opencode-observe-2
// §B) — see ./session.ts. It ports no hook script (Claude Code exports its own
// session key natively), so it has no marker; parity.yaml's
// `run-session-identity` row describes it.
//
// `shell.env` also carries the fr-binary pin (super-fr#746) — see ./pin.ts:
// the fr this plugin spawns, exported for `bash` as FR_HARNESS_FR. It is the
// OpenCode half of Claude Code's SessionStart hook:
// super-fr-parity: fr-binary-pin.sh
//
// EXPORT DISCIPLINE: OpenCode calls every export of a plugin module as a
// plugin. Helpers live in ./marker, ./idle, ./claim, ./session and ./pin; this
// file exports plugins only.
import { lstatSync, readlinkSync } from "node:fs";
import { dirname, isAbsolute, resolve } from "node:path";
import { createClaimHandler, sharedClaimed } from "./claim";
import { createIdleHandler, sharedActedOn } from "./idle";
import { matchesAllowlist, resolveMarker } from "./marker";
import { createPinHandler } from "./pin";
import { createShellEnvHandler, type ShellEnvInput, type ShellEnvOutput } from "./session";

// This is intentionally a short exclusion list, not a writer allowlist: new
// path-carrying tools fail closed. Bash is separately declared as ungated in
// parity.yaml; these built-ins can only read files.
const NON_WRITING_TOOLS = new Set(["bash", "glob", "grep", "list", "read"]);
const PATH_KEYS = new Set([
  "filePath",
  "path",
  "file",
  "filename",
  "file_path",
  "paths",
  "files",
  "source",
  "source_path",
  "destination",
  "destination_path",
  "target",
  "target_path",
  "oldPath",
  "newPath",
  "old_path",
  "new_path",
]);
const PATCH_KEYS = new Set(["patchText", "patch", "diff"]);
const PATCH_PREFIXES = ["*** Add File:", "*** Update File:", "*** Delete File:", "*** Move to:"];

interface Targets {
  paths: string[];
  unresolvablePatch: boolean;
}

function collectPathValues(value: unknown, key: string | undefined, targets: Set<string>): void {
  if (typeof value === "string") {
    if ((key !== undefined && PATH_KEYS.has(key)) || isAbsolute(value)) targets.add(value);
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) collectPathValues(item, key, targets);
    return;
  }
  if (value && typeof value === "object") {
    for (const [childKey, childValue] of Object.entries(value)) {
      collectPathValues(childValue, childKey, targets);
    }
  }
}

function extractTargets(output: unknown): Targets {
  const args = (output as { args?: Record<string, unknown> } | undefined)?.args;
  if (!args) return { paths: [], unresolvablePatch: false };

  const targets = new Set<string>();
  collectPathValues(args, undefined, targets);
  let unresolvablePatch = false;
  for (const [key, value] of Object.entries(args)) {
    if (!PATCH_KEYS.has(key) || typeof value !== "string") continue;
    let found = false;
    // Match OpenCode's apply_patch parser: split only on LF, then match its
    // exact prefixes and trim the suffix.
    for (const line of value.split("\n")) {
      const prefix = PATCH_PREFIXES.find((candidate) => line.startsWith(candidate));
      if (!prefix) continue;
      targets.add(line.slice(prefix.length).trim());
      found = true;
    }
    if (!found) unresolvablePatch = true;
  }
  return { paths: [...targets].filter(Boolean), unresolvablePatch };
}

function normalizeTarget(directory: string, target: string): string {
  let resolved = resolve(directory, target);
  for (let hops = 0; hops < 40; hops += 1) {
    let stat: ReturnType<typeof lstatSync>;
    try {
      stat = lstatSync(resolved);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return resolved;
      throw new Error(`fr-isolation: cannot inspect target symlink: ${resolved}`);
    }
    if (!stat.isSymbolicLink()) return resolved;
    resolved = resolve(dirname(resolved), readlinkSync(resolved));
  }
  throw new Error("fr-isolation: target symlink chain exceeds 40 hops");
}

export async function FrIsolationRequired(ctx: {
  project: unknown;
  client: unknown;
  $: unknown;
  directory: string;
  worktree: string;
}) {
  const claimChild = createClaimHandler({
    client: ctx.client,
    directory: ctx.worktree || ctx.directory,
    claimed: sharedClaimed(),
  });
  const exportSession = createShellEnvHandler();
  const exportPin = createPinHandler();
  return {
    event: createIdleHandler({
      client: ctx.client,
      directory: ctx.worktree || ctx.directory,
      actedOn: sharedActedOn(),
    }),
    "shell.env": async (input: ShellEnvInput, output: ShellEnvOutput) => {
      await exportSession(input, output);
      await exportPin(input, output);
    },
    "tool.execute.before": async (input: { tool: string; sessionID?: string }, output: unknown) => {
      // Before the gate, and whatever the tool: a child's first call of ANY
      // kind is the earliest moment it can be named. Never throws.
      await claimChild(input);

      // OpenCode cannot intercept filesystem effects of Bash. Other known
      // read-only tools are excluded; every remaining tool is inspected.
      if (NON_WRITING_TOOLS.has(input.tool)) return;

      // Deliberate base-clone edit — the documented escape hatch.
      if (process.env.FR_BASE_OK === "1") return;

      const targets = extractTargets(output);
      if (targets.unresolvablePatch) {
        const resolution = resolveMarker(normalizeTarget(ctx.directory, ".fr-unresolvable-patch-target"));
        if (resolution.toplevel && resolution.frEnabled && !resolution.hasValidMarker) {
          throw new Error(
            "fr-isolation: edit with an unresolvable patch target blocked — not inside an fr-isolation " +
              "workspace. Enter isolation (`fr isolation up` / fr-goal) and edit in the worktree; " +
              "or add the path to `.fr-isolation-allow`; or set FR_BASE_OK=1 for a deliberate " +
              "base-clone edit. See ~/.claude/rules/fr-isolation-required.md (#328)."
          );
        }
        // A malformed patch is ambiguous even in an isolated worktree.
        if (resolution.toplevel && resolution.frEnabled) {
          throw new Error("fr-isolation: edit with an unresolvable patch target blocked");
        }
      }
      if (targets.paths.length === 0) return;

      for (const target of targets.paths) {
        const file = normalizeTarget(ctx.directory, target);
        const resolution = resolveMarker(file);
        if (!resolution.toplevel || !resolution.frEnabled) continue; // not fr-enabled — allow
        if (resolution.hasValidMarker) continue; // valid isolation workspace — allow
        if (matchesAllowlist(resolution.toplevel, file)) continue;

        if (resolution.drift) {
          const { marker, head } = resolution.drift;
          throw new Error(
            `fr-isolation: edit to \`${target}\` blocked — this workspace was registered for ` +
              `${marker} but has ${head} checked out, so fr's state no longer describes it. ` +
              `Switch back with \`git switch ${marker}\`; to keep working on ${head}, then give ` +
              `it its own workspace with \`fr isolation up --branch ${head}\` (#553).`
          );
        }
        throw new Error(
          `fr-isolation: edit to \`${target}\` blocked — not inside an fr-isolation ` +
            "workspace. Enter isolation (`fr isolation up` / fr-goal) and edit in the " +
            "worktree; or add the path to `.fr-isolation-allow`; or set FR_BASE_OK=1 for " +
            "a deliberate base-clone edit. See ~/.claude/rules/fr-isolation-required.md (#328)."
        );
      }
    },
  };
}
