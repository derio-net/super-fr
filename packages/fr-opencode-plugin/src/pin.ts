// The fr-binary pin — super-fr#746; the OpenCode half of fr-binary-pin.sh.
//
// OpenCode 2 (V2 plugin API): the transport is `ctx.shell.hook("create.before")`,
// whose event carries a mutable `env` merged into the spawned shell.
//
// OpenCode's shell tool (`bash` before 2.0) runs `/bin/zsh -c`, and zsh re-reads ~/.zshenv on
// every start: a PATH rebuild there can put a different `fr` first than the
// one this plugin's `fr` (spawned through ./spawn) resolves from
// OpenCode's own PATH. So this exports the plugin's `fr --identity` into every
// `bash` command as FR_HARNESS_FR — a non-PATH variable `.zshenv` leaves alone
// — and `fr` refuses at CLI entry when a PATH-reached `fr` disagrees
// (fr/binary_identity.py).
//
// Transport only, and NEVER THROWS. `fr` is asked ONCE per plugin load, lazily
// on the first `bash` call; a missing `fr`, one too old to know `--identity`,
// or a hang pins nothing, which is exactly the behaviour before the pin.
import { run } from "./spawn";

/** The `shell` hook's `create.before` event (OpenCode 2) — `env` is merged
 * into the spawned command. */
export type ShellCreateEvent = {
  command?: string;
  cwd?: string;
  env?: Record<string, string | undefined>;
};

export const PIN_ENV_KEY = "FR_HARNESS_FR";

export type PinHandlerOptions = {
  /** Test seam. Default: `fr --identity` from OpenCode's own PATH. */
  identify?: () => Promise<string | undefined>;
  timeoutMs?: number;
};

const DEFAULT_TIMEOUT_MS = 10_000;

function defaultIdentify(timeoutMs: number): () => Promise<string | undefined> {
  return async () => {
    const answer = await run("fr", ["--identity"], { timeoutMs });
    return answer.code === 0 ? answer.stdout : undefined;
  };
}

export function createPinHandler(
  options: PinHandlerOptions = {}
): (event: ShellCreateEvent) => Promise<void> {
  const identify = options.identify ?? defaultIdentify(options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  let pinned: Promise<string | undefined> | undefined;

  return async (event) => {
    try {
      pinned ??= identify().then(
        (raw) => (raw ?? "").split("\n")[0]?.trim() || undefined,
        () => undefined
      );
      const identity = await pinned;
      if (!identity) return;
      event.env ??= {};
      event.env[PIN_ENV_KEY] = identity;
    } catch {
      // Attribution, not a gate: a failure here must never fail the command.
    }
  };
}
