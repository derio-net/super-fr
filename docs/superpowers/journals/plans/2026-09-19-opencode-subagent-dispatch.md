# Journal: 2026-09-19-opencode-subagent-dispatch

<!-- fr:journal kind=discovery scope=plan id=x-plan1 created=2026-09-20T00:01:09 -->
### x-plan1 · discovery · fr plan create silently drops a phase header's tier:

The phases-file schema `fr plan create --help` documents is {number, title, tag, depends_on, skeleton, tasks} — `tier` is not in it, and a `tier:` key present in the phases file is dropped without a warning. `fr.types.PhaseHeader.tier` accepts it fine, so the key was re-added directly to 01-05.yaml after create and self-review still passes. Worth a follow-up in fr itself: fr-goal §5 resolves each phase`s model from `tier`, so a plan authored through the documented path gets no tiering at all, silently. Not fixed here — out of scope for #494, and a silent drop deserves its own loud failure rather than a rider.
