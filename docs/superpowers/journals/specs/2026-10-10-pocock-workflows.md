# Journal: 2026-10-10-pocock-workflows

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-10-10T20:32:29+00:00 input=true -->
### brief · discovery · Operator brief

I want to create new workflows that wrap Matt Pocock's skills in github mattpocock/skills.

<!-- fr:journal kind=decision scope=spec id=d1-wrap-depth created=2026-10-10T20:32:29+00:00 -->
### d1-wrap-depth · decision · Matt's flow owns the run, tracked by fr

Steps mirror Matt's flow (grill-with-docs → to-spec → to-tickets → implement → pr → retro) rather than swapping disciplines into the fr-goal skeleton. Operator asked how superpowers is wrapped/installed; answered — a self-updating prerequisite named by fr skills and manifests, never installed or copied by super-fr.

<!-- fr:journal kind=decision scope=spec id=d2-source created=2026-10-10T20:32:29+00:00 -->
### d2-source · decision · Prerequisite plus read-the-installed-SKILL.md

Operator installs mattpocock-skills (self-updating); fr resolves each named skill's installed SKILL.md per harness and the agent reads the non-invocable ones. No vendoring, no install.sh wiring.

<!-- fr:journal kind=decision scope=spec id=d3-flows created=2026-10-10T20:32:29+00:00 -->
### d3-flows · decision · Main flow plus diagnosing-bugs

Two shapes, pocock and pocock-bugs. triage, wayfinder, implement-spec deferred.

<!-- fr:journal kind=decision scope=spec id=d4-artifacts created=2026-10-10T20:32:29+00:00 -->
### d4-artifacts · decision · fr files are the record

to-spec writes an fr spec (Matt's template +

<!-- fr:journal kind=decision scope=spec id=d5-gates created=2026-10-10T20:32:29+00:00 -->
### d5-gates · decision · New workflows with Matt's own gates, fr-enforced

Not fr-goal shapes. Matt's operator checkpoints (grill, to-spec seam check, to-tickets quiz, diagnosing-bugs no-loop stop, retro) become gate:operator steps; fr adds evidence/journal gates where needed.

<!-- fr:journal kind=decision scope=spec id=d6-entry created=2026-10-10T20:32:29+00:00 -->
### d6-entry · decision · Generic fr-flow driver plus fr-pocock / fr-pocock-bugs aliases

Operator asked whether this exists; answered — the fr run verbs drive any shape, but no driver skill without fr-goal's contract exists. Build both.

<!-- fr:journal kind=decision scope=spec id=d7-verification created=2026-10-10T20:32:29+00:00 -->
### d7-verification · decision · candidate pre-merge, live row post-merge

Candidate scenarios against a stub mattpocock-skills install; the real end-to-end flow is a post-merge live row.
