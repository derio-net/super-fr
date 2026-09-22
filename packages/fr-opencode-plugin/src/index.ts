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
// EXPORT DISCIPLINE: OpenCode calls every export of a plugin module as a
// plugin. Helpers live in ./marker and ./idle; this file exports plugins only.
import { existsSync, realpathSync } from "node:fs";
import { isAbsolute, resolve } from "node:path";
import { createIdleHandler } from "./idle";
import { matchesAllowlist, resolveMarker } from "./marker";

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
  const resolved = resolve(directory, target);
  return existsSync(resolved) ? realpathSync.native(resolved) : resolved;
}

export async function FrIsolationRequired(ctx: {
  project: unknown;
  client: unknown;
  $: unknown;
  directory: string;
  worktree: string;
}) {
  return {
    event: createIdleHandler({ client: ctx.client, directory: ctx.worktree || ctx.directory }),
    "tool.execute.before": async (input: { tool: string }, output: unknown) => {
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
