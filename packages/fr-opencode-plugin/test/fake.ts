// A fake OpenCode 2 plugin context: captures every hook `setup` registers and
// replays a scripted event stream. Shared by the plugin-level tests.
import plugin from "../src/index";

export type Hook = (event: never) => Promise<void> | void;

export type FakeOptions = {
  directory?: string;
  /** `location.project.directory` — the PROJECT root, which the gate must not
   * use as its base (a workspace can sit inside a project). */
  projectDirectory?: string;
  session?: unknown;
  /** Events `ctx.event.subscribe` yields, in order. */
  events?: unknown[];
};

export function fakeCtx(options: FakeOptions = {}) {
  const hooks = new Map<string, Hook[]>();
  const register = (domain: string) => async (name: string, callback: Hook) => {
    const key = `${domain}:${name}`;
    hooks.set(key, [...(hooks.get(key) ?? []), callback]);
    return { dispose: () => undefined };
  };
  const subscribed: AbortSignal[] = [];
  let markDrained: () => void = () => undefined;
  /** Resolves once the plugin has consumed (and handled) every scripted event. */
  const drained = new Promise<void>((resolve) => (markDrained = resolve));
  const ctx = {
    location: {
      directory: options.directory ?? "/nonexistent",
      project: { id: "prj", directory: options.projectDirectory ?? "/nonexistent", canonical: "/nonexistent" },
    },
    // The caller's session API (get/prompt), plus the hook registrar the
    // plugin's `context` handler needs.
    session: Object.assign(Object.create((options.session ?? {}) as object), {
      hook: register("session"),
    }) as unknown,
    tool: { hook: register("tool") },
    shell: { hook: register("shell") },
    event: {
      subscribe(opts?: { signal?: AbortSignal }) {
        if (opts?.signal) subscribed.push(opts.signal);
        const queue = [...(options.events ?? [])];
        return (async function* () {
          try {
            for (const event of queue) yield event;
          } finally {
            markDrained();
          }
        })();
      },
    },
  };
  return { ctx, hooks, subscribed, drained };
}

/** Run `setup` on a fake context; returns the captured hooks and the cleanup. */
export async function load(options: FakeOptions = {}) {
  const fake = fakeCtx(options);
  const cleanup = await plugin.setup(fake.ctx as never);
  const one = (key: string) => {
    const list = fake.hooks.get(key) ?? [];
    if (list.length !== 1) throw new Error(`expected one ${key} hook, got ${list.length}`);
    return list[0] as (event: unknown) => Promise<void>;
  };
  return {
    ...fake,
    cleanup,
    executeBefore: one("tool:execute.before"),
    executeAfter: one("tool:execute.after"),
    context: one("session:context"),
    createBefore: one("shell:create.before"),
  };
}
