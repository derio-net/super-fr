<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-event-driven-a-la-carte

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-19T22:20:50+00:00 input=true -->
### brief · discovery · Operator brief

I want to make super-fr a-la-carte and event-driven. With event driven I mean, that the handoffs between agents and gates should be clear events that can be sent to a broker. The interested parties (the Test-Agent manning the Tester Gate, or the Orchestrator manning the Wave Driver, or the Product Owner Agent doing the brainstorming or Architect Agent doing the wayfinding (foreshadowing)) can send and subscribe to events and thus move a feature/task between them until it's finished. With a-la-carte, I mean to extend the per-repo yaml file(s) with a composable configuration that allows things like the available workflows, the components of the PR (not everybody wants to see Proportionality or Cost), the repo/quiet/stealth choices and more

<!-- fr:journal kind=decision scope=spec id=operator-decisions-r1 created=2026-11-24T18:04:09+00:00 -->
### operator-decisions-r1 · decision · Operator decisions D1-D15 (brainstorm rounds 1-8)

- D0 Each workflow Step declares a station; a step boundary is a commit (pushed per mode). Ad-hoc flows (fr-debugging, ...) become workflows. A mechanical Router decides handoffs: a Port with adapters (first beside the wave driver; a Local Router for stealth; a future service).
- Split config: the repo declares stations abstractly; a host file binds stations to runner/harness/model. A future Coordinator node may hold configs for several Runner nodes.
- D1 Every runner a Station binds must provide SessionMessenger; messaging capability no longer decides continue-vs-fresh.
- D2 Two run configurations ("staffing"): solo (one session runs the workflow, declared agents run as subagents) and stations (the Router routes each step to its station).
- D3 One Router per space (repo: remote feature branches; quiet: fr branch; stealth: tracking branch); Router/station config lives in that space's settings.
- D4 Runs register implicitly: the cursor in the space, watched via fr_dispatch Source.
- D5 One Router per space, held by a lease; several Routers per host allowed.
- D6 Stealth uses the Local Router on its tracking space.
- D7 Stealth: state is pushed to the tracking repo on every write (as today); code reaches the target (fr push, fr pr create) only after explicit operator confirmation, regardless of git.push.
- D8 cncd is not bindable to Stations; candidate for deprecation (out of scope).
- D9 Station sessions are one per ticket.
- D10 A full host spills over to another binding of the same station when the host file names one and the space is pushed; otherwise the step waits and raises a Need after a set time; stealth always waits. A host-wide admission ledger (HostCapacity port: slots + sampled load) is shared by all Routers and wave drivers on a host.
- D11 The profile is the unit of access: a station names a profile; a profile declares reach; a binding lists the profiles its host can enter; a bounded reach probe runs at admission; impossible bindings/fallbacks are refused by fr hosts check.
- D12 .fr/ holds repo configuration only and follows the space (product checkout / fr branch / tracking branch). REPO_CONFIG_KINDS, fr-profiles.yaml and .fr-isolation-allow move into it; triage working state leaves it.
- D13 super-fr's shipped defaults (workflows, verifications, lenses, later stations) get one home and one wheel copy, one sync, one resolver.
- D14 Triage state follows the unit under triage; the triage branch is the wave-driver Router's space.
- D15 Triage branch location: repo scope -> fr-triage/<scope-id> in the repo; org scope -> the org's state repo; stealth -> the tracking repo; a repo may name a state repo in .fr/settings.yaml; the privacy guard is unchanged.
