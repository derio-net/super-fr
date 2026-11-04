<!-- fr:journal-schema=3 -->
# Journal: 2026-11-04-opencode-idle-session-directory

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-11-04T13:44:51+00:00 -->
### repro-1 · repro · Idle nudge computed in the plugin's directory, not the session's

gh#1371, observed live on fr 6.1.0 with the OpenCode 2.x plugin. A session in checkout B received "fr run <run-in-A> is idle … run fr run advance <run-in-A>"; that advance refused in B (no such run). `fr run check --idle --format json` exits 3 in A and returns `{"idle": false, "reason": "no-run"}` in B. Static repro: `src/index.ts` passes `ctx.location.directory` as `directory` to `createIdleHandler`, and `src/idle.ts` always calls `runFr(options.directory)`, whatever the session. The pinning test drives the handler with a session whose `location.directory` differs from the handler's.
