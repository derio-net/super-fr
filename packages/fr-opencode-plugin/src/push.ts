// The merged-PR push guard — the OpenCode 2 port of
// plugins/super-fr/hooks/fr-merged-pr-push-guard.sh (spec 2026-10-20-opencode-2-support R4).
//
// While a pipeline sentinel exists for this session, a `git push` from a branch
// whose PR is already MERGED or CLOSED is refused: pushing there orphans the
// commit from `main` (#320's merge race).
//
// Fail-open on EVERY ambiguity — no sentinel, no push, gh missing, no PR, a
// network or auth error, a timeout — exactly as the bash hook does. It is a
// discipline backstop, not a security boundary.
//
// TODAY'S DECISION, NOT A WIDER ONE: the bash hook acts on `git push` only. The
// spec's "`git push` / `gh pr merge`" names the commands the guard runs on, and
// `gh pr merge` is not one the bash guard refuses, so the port does not either.
//
// Returns the refusal text, or undefined to allow. Never throws.
import { statSync } from "node:fs";
import { sentinelPath } from "./sentinel";
import { run, type RunAnswer } from "./spawn";

// The bash hook's ERE, verbatim but for [[:alnum:]]/[[:space:]] spelled out.
// grep matches it against EVERY line of the command, so this does too.
const SP = "[ \\t\\n\\v\\f\\r]";
const NSP = "[^ \\t\\n\\v\\f\\r]";
const GIT_PUSH = new RegExp(
  `(^|[^A-Za-z0-9_])git(${SP}+-${NSP}+(${SP}+[^ \\t\\n\\v\\f\\r-]${NSP}*)?)*${SP}+push($|[^A-Za-z0-9_-])`
);

const GH_TIMEOUT_MS = 20_000;

export type PrStateReader = (cwd: string) => Promise<RunAnswer>;

const defaultReader: PrStateReader = (cwd) => run("gh", ["pr", "view", "--json", "state"], { cwd, timeoutMs: GH_TIMEOUT_MS });

export function isGitPush(command: string): boolean {
  return command.split("\n").some((line) => GIT_PUSH.test(line));
}

export async function decidePush(
  command: string,
  cwd: string,
  sessionID: string,
  readState: PrStateReader = defaultReader
): Promise<string | undefined> {
  try {
    if (!sessionID) return undefined;
    try {
      if (!statSync(sentinelPath(sessionID)).isFile()) return undefined;
    } catch {
      return undefined; // no active pipeline for this session
    }
    if (!isGitPush(command)) return undefined;
    if (!cwd) return undefined;
    const answer = await readState(cwd);
    if (answer.code !== 0 || !answer.stdout.trim()) return undefined;
    const state = (JSON.parse(answer.stdout) as { state?: unknown }).state;
    if (state !== "MERGED" && state !== "CLOSED") return undefined;
    return (
      `Pre-push guard: this branch's PR is ${state}. Pushing here orphans the commit from ` +
      "`main` (#320 merge-race). Stop — cherry-pick the commit onto `main` (or open a fresh " +
      "branch/PR) instead. See plugins/super-fr/skills/fr-isolation (pre-push guard)."
    );
  } catch {
    return undefined;
  }
}
