# Draft PRs that settle — plan

Spec: `docs/superpowers/specs/2026-11-23-pr-readiness-wait-design.md`.

The plan has three phases, one per ask that can be reviewed on its own:

1. **Engine and verb (skeleton).** The `git.settle` setting; the pure `fr.settle` engine
   (states, modes, verdict, exit codes); the driver-managed exemption with its brief
   sentence; the bounded poll; and `fr pr settle`. The later phases reuse `evaluate`.
2. **Overrides, PR body, deliver witness.** The `settle.` grammar lines; override
   precedence (spec line, debug-journal decision); the required `## PR settle` section;
   and the derived `settle` witness. The witness is evaluated outside `derive()` so that
   exit 75 still reaches the caller. Every fr-goal run passes this gate, so the phase is
   `hard`.
3. **Skills and mirrors.** fr-goal, fr-debugging and the hand-run close-out brief run the
   settle loop. The mirrors are regenerated and the docs pages updated.

No artifact changes shape (spec §C), so no stamp, migration or validator ships.
