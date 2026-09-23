# fr triage — backlog triage that runs on any harness

Spec: `docs/superpowers/specs/2026-09-21-fr-triage-design.md`.

The engine is an `fr` verb and the skill is thin prose over it, because both mirror generators
copy only `SKILL.md` — anything bundled beside a skill would never reach OpenCode or Hermes. The
four agentic phases build that engine from the forge inward, then the skill on top:

1. **Walking skeleton.** `fr triage collect` exists, writes a facts file from captured `gh`
   fixtures, and joins the migration gate's read-only list. The skeleton proves the seam, the
   command registration and CI before any real logic lands.
2. **Collect.** The full facts model and the part that is easy to get plausibly wrong: PRs
   inverted into issues keyed on the *reference's* repository, stages derived rather than set, and
   org scope that records an unreadable repo instead of aborting.
3. **Check and render.** The two outputs a person sees. `check` makes unranked issues impossible
   to miss, the failure the Artifact board had. `render` is deterministic and treats every
   forge-sourced string as hostile, because org scope renders text from every contributor.
4. **The skill.** Written against a recorded baseline of how an agent triages without it (plan
   journal `skill-baseline`, produced by the orchestrator before this phase, since the phase
   executor cannot run a second agent), then shipped through both mirror generators with a minor
   version bump.

Phase 5 is the post-merge walk on Claude Code and OpenCode, which only an operator on those
harnesses can do.

Tiers: the skeleton is `standard`. Collect, render and the skill are `hard`, because each has a
correctness property that a plausible implementation gets wrong: cross-repo keying, escaping and
determinism, and a skill that actually changes behaviour.
