// Thin re-export so this repo's own OpenCode sessions load
// fr-isolation-required automatically from .opencode/plugins/ (OpenCode's
// project-local plugin directory). The implementation lives in
// packages/fr-opencode-plugin/ so it can also be published to npm and
// consumed by other repos via opencode.json's "plugin" array — see that
// package's README.md.
export { FrIsolationRequired as default } from "../../packages/fr-opencode-plugin/src/index";
