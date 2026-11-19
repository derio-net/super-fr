<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-event-driven-a-la-carte

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-19T22:20:50+00:00 input=true -->
### brief · discovery · Operator brief

I want to make super-fr a-la-carte and event-driven. With event driven I mean, that the handoffs between agents and gates should be clear events that can be sent to a broker. The interested parties (the Test-Agent manning the Tester Gate, or the Orchestrator manning the Wave Driver, or the Product Owner Agent doing the brainstorming or Architect Agent doing the wayfinding (foreshadowing)) can send and subscribe to events and thus move a feature/task between them until it's finished. With a-la-carte, I mean to extend the per-repo yaml file(s) with a composable configuration that allows things like the available workflows, the components of the PR (not everybody wants to see Proportionality or Cost), the repo/quiet/stealth choices and more
