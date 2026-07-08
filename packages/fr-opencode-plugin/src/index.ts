// OpenCode plugin: deny Edit/Write-class tool calls targeting tracked
// source in an fr-enabled repo unless a valid .fr-isolation marker is
// present. Ports plugins/super-fr/hooks/fr-isolation-required.sh (a Claude
// Code PreToolUse hook) to OpenCode's tool.execute.before hook — see that
// script for the authoritative decision-logic comments; this file mirrors
// its behavior exactly (fail-closed on ambiguity, same two escape hatches).
import { isAbsolute } from "node:path";
import { matchesAllowlist, resolveMarker } from "./marker";

const EDIT_TOOLS = new Set(["edit", "write", "patch", "multiedit"]);

function extractFilePath(output: unknown): string | undefined {
  const args = (output as { args?: Record<string, unknown> } | undefined)?.args;
  if (!args) return undefined;
  const candidate = args.filePath ?? args.path;
  return typeof candidate === "string" ? candidate : undefined;
}

export async function FrIsolationRequired(_ctx: {
  project: unknown;
  client: unknown;
  $: unknown;
  directory: string;
  worktree: string;
}) {
  return {
    "tool.execute.before": async (input: { tool: string }, output: unknown) => {
      if (!EDIT_TOOLS.has(input.tool)) return;

      // Deliberate base-clone edit — the documented escape hatch.
      if (process.env.FR_BASE_OK === "1") return;

      const file = extractFilePath(output);
      if (!file || !isAbsolute(file)) return; // no parseable target — not our concern

      const resolution = resolveMarker(file);
      if (!resolution.toplevel || !resolution.frEnabled) return; // not fr-enabled — allow
      if (resolution.hasValidMarker) return; // valid isolation workspace — allow
      if (matchesAllowlist(resolution.toplevel, file)) return; // operator-managed exemption

      throw new Error(
        `fr-isolation: edit to \`${file}\` blocked — not inside an fr-isolation ` +
          "workspace. Enter isolation (`fr isolation up` / fr-goal) and edit in the " +
          "worktree; or add the path to `.fr-isolation-allow`; or set FR_BASE_OK=1 for " +
          "a deliberate base-clone edit. See ~/.claude/rules/fr-isolation-required.md (#328)."
      );
    },
  };
}
