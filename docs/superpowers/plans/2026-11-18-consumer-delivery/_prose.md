# Consumer delivery: OpenCode rules and scaffolds — plan

Spec: `docs/superpowers/specs/2026-11-18-consumer-delivery-design.md`.

Three agentic phases, one per independently reviewable ask:

1. **OpenCode plugin** (#1402, #1375; R1–R7). The skeleton: smoke and change fragment first, then the shipped rules delivered into `<plugins>/fr-opencode-plugin/rules/` and injected once per request, then the nag, bind and claim handlers moved to the session's directory. TypeScript under `packages/fr-opencode-plugin` plus install.sh, the delivery script and their drift test.
2. **Consumer CI scaffold** (#1308, #1186; R8–R13). Action pins table, fr pinned to its release commit via `git ls-remote`, the staleness warning in `fr acceptance check`, archive-pr's env-only push auth, and the three forges' debt jobs. Depends on phase 1 only for the shared change fragment.
3. **SSO / forward-auth refusal** (#1271; R14). One helper, every tea/glab JSON read, a redacted fixture.

No manual phase: the operator-driven checks (a real OpenCode session, real Gitea/GitLab runners) are the spec's Test Plan, post-merge. The frank half of #1271 is derio-net/frank#1014. No member issue is a phase tracking issue.
