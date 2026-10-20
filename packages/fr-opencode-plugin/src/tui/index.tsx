// super-fr's OpenCode 2 status line (spec 2026-10-20-opencode-2-support R12).
//
// A TUI plugin, not a server one. OpenCode 2.1.0 resolves a plugin DIRECTORY's
// TUI entrypoint as `<dir>/tui` (this file) and its server entrypoint as
// `<dir>/server` or `<dir>/index` — so the server loader never imports this
// file, and this file never imports the server plugin. JSX, `solid-js` and
// `@opentui/solid` are provided by the opencode binary's own runtime; a
// consumer installs nothing (measured live, plan journal p3-tui-spike).
//
// Deliberately thin: every decision is in ./segment (tested without JSX).
// This file is not type-checked by `tsc` (its JSX types live in packages the
// binary bundles); the live probe in tests/integration/test_opencode_plugin_live.py
// is what proves it loads and renders.
import { join } from "node:path";
import { createSignal } from "solid-js";

import { createSegmentCache, readSegment, REFRESH_EVENTS, sessionDirectory } from "./segment";

const SCRIPT = join(import.meta.dir, "fr-statusline-segment.sh");

export default {
  id: "super-fr.statusline",
  setup(context: any) {
    // Each render's directory is its SESSION's (slot input `sessionID` ->
    // context.data.session.get(id).location.directory), falling back to the
    // TUI's launch directory for the home screen or a session not yet loaded.
    const [version, setVersion] = createSignal(0);
    const launch: string = context.location?.directory ?? process.cwd();
    const cache = createSegmentCache(
      (key) => sessionDirectory(context.data?.session, key || undefined, launch),
      (cwd) => readSegment(cwd, SCRIPT),
      () => setVersion((v) => v + 1),
      250,
    );
    const offs: Array<() => void> = REFRESH_EVENTS.map((type) =>
      context.data.on(type, (event: any) => cache.refresh(event?.sessionID ?? event?.data?.sessionID))
    );
    // Both reads sit inside the JSX expression so Solid tracks them: a new
    // segment (version) or a slot input naming another session re-renders.
    const render = (input: any) => <text>{(version(), cache.text(input?.sessionID ?? ""))}</text>;
    offs.push(context.ui.slot({ append: "prompt.footer.status", render }));
    offs.push(context.ui.slot({ append: "home.footer.status", render }));
    return () => {
      cache.cancel();
      for (const off of offs) off();
    };
  },
};
