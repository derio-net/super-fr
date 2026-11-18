// The shipped rules for OpenCode (consumer-delivery R2).
//
// OpenCode never reads `~/.claude/rules/`, so install delivers the rules into
// `<plugin dir>/rules/` (scripts/deliver-opencode-plugin.sh) and this handler
// appends each as a system part on the `context` hook. It runs on every
// request, and the hook's `system` may already hold a rule: from a kept part
// of an earlier request, from another loaded copy of this plugin, or from
// opencode.json's `instructions`. So a rule is appended only when no existing
// part already CONTAINS its text, or names the same rule file in an
// `Instructions from: <path>/<file>` header (opencode.json's loader writes
// one), so a checkout whose mirror differs from the installed copy (version
// skew while developing super-fr) still gets one copy. No session lookup: children and top-level
// sessions alike get the rules. Not a ported hook, so no parity marker.
//
// The header format is OpenCode's own, read from the opencode v2.3.0 binary
// (`strings $(command -v opencode)`, 2026-11-18): its instruction renderer is
// `Instructions from: ${path}\n${content}`, several files joined by "\n\n" in
// ONE part, and its "changed"/"added" re-renders embed the same line. So the
// header is matched anywhere in a part, the path absolute.
//
// A missing `rules/` dir is silent: it is the designed state of the in-tree
// plugin (`.opencode/plugins/` re-exports this package, and nothing delivers
// rules beside it). A dir that EXISTS but cannot be listed, or a rule file that
// cannot be read, is a broken install: one stderr line names it, and the failed
// load is not cached, so a later request tries again.
//
// NEVER THROWS.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

export type RulesHandlerOptions = {
  rulesDir: string;
  /** Test seam: the directory listing. */
  readdir?: (dir: string) => string[];
  /** Test seam: reading one rule file. */
  readFile?: (path: string) => string;
  /** Test seam: where a warning line goes (stderr, as the plugin's other warnings). */
  warn?: (line: string) => void;
};

type ContextEvent = { sessionID?: unknown; system?: unknown };
type Rule = { text: string; compare: string; header: RegExp };

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

type Loaded = { rules: Rule[]; complete: boolean };

function errCode(err: unknown): unknown {
  return (err as { code?: unknown } | null | undefined)?.code;
}

function errText(err: unknown): string {
  const code = errCode(err);
  if (typeof code === "string") return code;
  return err instanceof Error ? err.message : String(err);
}

function loadRules(
  dir: string,
  readdir: (dir: string) => string[],
  readFile: (path: string) => string,
  warn: (line: string) => void
): Loaded {
  let names: string[];
  try {
    names = readdir(dir).filter((n) => n.endsWith(".md")).sort();
  } catch (err) {
    // No rules dir: the in-tree plugin's designed state, silent and final.
    if (errCode(err) === "ENOENT") return { rules: [], complete: true };
    warn(`super-fr: cannot list the rules dir ${dir} (${errText(err)}); no shipped rule is injected.`);
    return { rules: [], complete: false };
  }
  const rules: Rule[] = [];
  let complete = true;
  for (const name of names) {
    const path = join(dir, name);
    try {
      const text = readFile(path);
      const header = new RegExp(`Instructions from: \\S*[/\\\\]${escapeRe(name)}(?:\\s|$)`);
      if (text.trim() !== "") rules.push({ text, compare: text.trim(), header });
    } catch (err) {
      // An unreadable file is skipped; the rest still load.
      complete = false;
      warn(`super-fr: cannot read the rule file ${path} (${errText(err)}); that rule is not injected.`);
    }
  }
  return { rules, complete };
}

function partText(part: unknown): string | undefined {
  if (typeof part === "string") return part;
  const text = (part as { text?: unknown } | null | undefined)?.text;
  return typeof text === "string" ? text : undefined;
}

export function createRulesHandler(options: RulesHandlerOptions) {
  let cached: Rule[] | undefined;
  const readdir = options.readdir ?? ((d: string) => readdirSync(d));
  const readFile = options.readFile ?? ((p: string) => readFileSync(p, "utf8"));
  const warn = options.warn ?? ((line: string) => console.error(line));

  return async (event: ContextEvent | null | undefined): Promise<void> => {
    try {
      if (!event || !Array.isArray(event.system)) return;
      let rules = cached;
      if (rules === undefined) {
        const loaded = loadRules(options.rulesDir, readdir, readFile, warn);
        rules = loaded.rules;
        if (loaded.complete) cached = rules; // a failed read is retried next request
      }
      const system = event.system as unknown[];
      for (const rule of rules) {
        const present = system.some((part) => {
          const t = partText(part);
          return t !== undefined && (t.includes(rule.compare) || rule.header.test(t));
        });
        if (!present) system.push({ type: "text", text: rule.text });
      }
    } catch {
      // Fail open, always.
    }
  };
}
