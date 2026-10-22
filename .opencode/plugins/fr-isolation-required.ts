// Thin re-export so this repo's own OpenCode sessions load the super-fr plugin
// automatically from .opencode/plugins/ (OpenCode's project-local plugin
// directory). The implementation lives in packages/fr-opencode-plugin/ — an
// OpenCode 2 plugin definition (`{ id, setup }`) — so it can also be published
// to npm and consumed by other repos via the config's "plugin" array; see that
// package's README.md.
export { default } from "../../packages/fr-opencode-plugin/src/index";
