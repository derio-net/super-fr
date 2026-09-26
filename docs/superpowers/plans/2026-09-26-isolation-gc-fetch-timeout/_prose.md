# Isolation GC fetch timeout

`_reap_hazard` currently performs its remote comparison with an untimed
`git fetch`. Use the existing bounded network helper, and pin both the helper
call (including its worktree cwd) and the fail-closed timeout behavior with a
regression test.

The change is intentionally limited to the fetch invocation and focused test.
Keep the local-first checks, `origin` absence handling, and `unverifiable`
hazard response unchanged.
