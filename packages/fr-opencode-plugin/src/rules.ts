// The shipped rules for OpenCode (consumer-delivery R2).
//
// OpenCode never reads `~/.claude/rules/`, so install delivers the rules into
// `<plugin dir>/rules/` (scripts/deliver-opencode-plugin.sh) and this handler
// appends each as a system part on the `context` hook. It runs on every
// request, and the hook's `system` may already hold a rule: from a kept part
// of an earlier request, from another loaded copy of this plugin, or from
// opencode.json's `instructions`. So a rule is appended only when no existing
// part already CONTAINS its text. No session lookup: children and top-level
// sessions alike get the rules. Not a ported hook, so no parity marker.
//
// NEVER THROWS.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

export type RulesHandlerOptions = {
  rulesDir: string;
  /** Test seam: the directory listing. */
  readdir?: (dir: string) => string[];
};

type ContextEvent = { sessionID?: unknown; system?: unknown };
type Rule = { text: string; compare: string };

function loadRules(dir: string, readdir: (dir: string) => string[]): Rule[] {
  let names: string[];
  try {
    names = readdir(dir).filter((n) => n.endsWith(".md")).sort();
  } catch {
    return [];
  }
  const rules: Rule[] = [];
  for (const name of names) {
    try {
      const text = readFileSync(join(dir, name), "utf8");
      if (text.trim() !== "") rules.push({ text, compare: text.trim() });
    } catch {
      // An unreadable file is skipped; the rest still load.
    }
  }
  return rules;
}

function partText(part: unknown): string | undefined {
  if (typeof part === "string") return part;
  const text = (part as { text?: unknown } | null | undefined)?.text;
  return typeof text === "string" ? text : undefined;
}

export function createRulesHandler(options: RulesHandlerOptions) {
  let cached: Rule[] | undefined;
  const readdir = options.readdir ?? ((d: string) => readdirSync(d));

  return async (event: ContextEvent | null | undefined): Promise<void> => {
    try {
      if (!event || !Array.isArray(event.system)) return;
      cached ??= loadRules(options.rulesDir, readdir);
      const system = event.system as unknown[];
      for (const rule of cached) {
        const present = system.some((part) => partText(part)?.includes(rule.compare) === true);
        if (!present) system.push({ type: "text", text: rule.text });
      }
    } catch {
      // Fail open, always.
    }
  };
}
