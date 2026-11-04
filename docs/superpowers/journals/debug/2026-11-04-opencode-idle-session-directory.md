<!-- fr:journal-schema=3 -->
# Journal: 2026-11-04-opencode-idle-session-directory

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-11-04T13:44:51+00:00 -->
### repro-1 · repro · Idle nudge computed in the plugin's directory, not the session's

gh#1371, observed live on fr 6.1.0 with the OpenCode 2.x plugin. A session in checkout B received "fr run <run-in-A> is idle … run fr run advance <run-in-A>"; that advance refused in B (no such run). `fr run check --idle --format json` exits 3 in A and returns `{"idle": false, "reason": "no-run"}` in B. Static repro: `src/index.ts` passes `ctx.location.directory` as `directory` to `createIdleHandler`, and `src/idle.ts` always calls `runFr(options.directory)`, whatever the session. The pinning test drives the handler with a session whose `location.directory` differs from the handler's.

<!-- fr:journal kind=root-cause scope=debug id=root-cause-1 created=2026-11-04T13:44:53+00:00 -->
### root-cause-1 · root-cause · isTopLevel fetches Session.Info and drops its location

`isTopLevel` already calls `ctx.session.get({sessionID})`. In `@opencode/schema` 2.1.0 the returned `Session.Info` carries a REQUIRED `location: {directory, workspaceID?}` (`schema/dist/session.d.ts`), and `SessionDomain` exposes `move`, so a session can sit in a different directory from the plugin. The handler throws that info away and runs fr in `options.directory`, the plugin's `ctx.location.directory`. Two results: wrong-repo nudges, and silent misses when the session's own checkout has an idle run (the gh#518 failure). The TUI already resolves per session (`src/tui/segment.ts` `sessionDirectory`); the idle guard never did. `test/idle.test.ts` writes the assumption into a comment ("the directory is the plugin's location").

<!-- fr:journal kind=finding scope=debug id=fix-1 created=2026-11-04T13:47:48+00:00 state=fixed -->
### fix-1 · finding [fixed] · Idle guard resolves fr's cwd per session

Fixed in 6539c05e2. `src/idle.ts`: `isTopLevel` became `topLevelInfo`, which returns the `Session.Info` it already fetched, and `sessionDirectory(info, options.directory)` picks `location.directory`, falling back to the plugin directory when it is missing, null, empty or not a string. Pinned by `test/idle.test.ts` "asks fr in the SESSION's directory": both session-directory cases were red before the fix and green after; the five fallback cases pin the fail-open path. Full plugin suite 254 pass, tsc clean.
