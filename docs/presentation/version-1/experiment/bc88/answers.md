# Answer sheet — written BEFORE either run

Read out verbatim if a run asks. **Draft — confirm or overwrite before recording.**

Remember what we learned: this sheet is a *response* document. A run that never
asks never receives any of it, so nothing here can be assumed to have reached
the work. Anything that must bind both arms belongs in the prompt instead.

| # | Question | Answer |
|---|---|---|
| 1 | How many ownership classes? | Keep `framework` / `merged` / `content`; add **one** new state for a framework-class file the consumer has changed. Do not redesign the taxonomy. |
| 2 | Where does a consumer declare divergence? | A repo-local file the consumer owns, not a key inside `.blog-craft.yaml` — the config is `content` and a migration already rewrites it (#73). |
| 3 | How is divergence detected? | By comparing against the render at `blog_craft_version`, the base `/update` already recovers for its 3-way merge. Do not invent a second base. |
| 4 | What does `/update` do on a diverged framework file? | Never silently replace. Preserve the consumer's copy and report it. Whether it then offers a merge is the run's design call. |
| 5 | Warn or fail? | Report loudly and exit non-zero when a divergence would have been erased. A silent pass is the bug. |
| 6 | Scope | Classification model + ONE mechanism end to end. Anything else is deferred and recorded, not built. |
| 7 | Out of scope | Migrating existing consumers, a patch-queue system, upstreaming automation, changes to frank. |
