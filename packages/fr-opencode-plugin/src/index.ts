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
import { isAbsolute, resolve } from "node:path";
import { createIdleHandler } from "./idle";
import { matchesAllowlist, resolveMarker } from "./marker";

// This is intentionally not a writer allowlist: unknown path-carrying tools
// fail closed. Bash is separately declared as ungated in parity.yaml.
const NON_WRITING_TOOLS = new Set(["bash"]);

function extractTargets(output: unknown): string[] | null {
  const args = (output as { args?: Record<string, unknown> } | undefined)?.args;
  if (!args) return null;

  const direct = [args.filePath, args.path, args.file, args.filename].filter(
    (candidate): candidate is string => typeof candidate === "string"
  );
  const patches = [args.patchText, args.patch, args.diff].filter(
    (candidate): candidate is string => typeof candidate === "string"
  );
  if (patches.length === 0) return direct;

  const targets = new Set(direct);
  for (const patch of patches) {
    // OpenCode's apply_patch carries each target in its unified patch header.
    const matches = patch.matchAll(/^\*\*\* (?:Add|Update|Delete) File: (.+)$|^\*\*\* Move to: (.+)$/gm);
    for (const match of matches) targets.add((match[1] ?? match[2]).trim());
  }
  return targets.size > 0 ? [...targets] : null;
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
      if (targets !== null && targets.length === 0) return;

      for (const target of targets ?? ["<unresolvable patch target>"]) {
        const file = isAbsolute(target) ? target : resolve(ctx.worktree || ctx.directory, target);
        const resolution = resolveMarker(file);
        if (!resolution.toplevel || !resolution.frEnabled) continue; // not fr-enabled — allow
        if (resolution.hasValidMarker) continue; // valid isolation workspace — allow
        if (targets !== null && matchesAllowlist(resolution.toplevel, file)) continue;

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
