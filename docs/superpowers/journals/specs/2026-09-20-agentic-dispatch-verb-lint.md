# Journal: 2026-09-20-agentic-dispatch-verb-lint

<!-- fr:journal kind=decision scope=spec id=d1-scope created=2026-09-20T15:00:59 -->
### d1-scope · decision · Scope: #428 items 1, 2 and 4 ship; item 3 stays open

Operator answered the batched Q&A: ship the `fr plan self-review` lint (item 1), the executor contract that refuses the tick (item 2, `fr-phase-executor.md` + `fr-execute`), and fr-plan's outcomes-not-mechanisms guidance (item 4). Item 3 (`fr journal check --require-reviews`) is a new CLI surface and stays open as its own issue. Rationale given: a gate that errors without saying what to write instead is half a fix, so 2 and 4 are what make 1 actionable. #496 is explicitly out of scope (owned by the parallel fr run cursor run).

<!-- fr:journal kind=decision scope=spec id=d2-precision created=2026-09-20T15:00:59 -->
### d2-precision · decision · Precision-first, single error tier — the issue's literal pattern list is unusable here

Measured during the brainstorm over all 1419 agentic steps in this repo's 43 parseable plan folders (live + archived): #428's literal proposal fires 237 times on bare `dispatch` alone (16.7% of steps), 42 times on a bare `<word>:<word>` token (`start:end`, `cli:app`, `fr:synced`), plus hits on `spawn`, `delegate to`, `subagent_type` and `Task tool` — every one a false positive, because super-fr is a repo ABOUT dispatch. At error severity that breaks self-review on super-fr's own plans. Chosen instead: an imperative-head dispatch verb with an agent-shaped object, plus explicit mechanism tokens. Measured 0 hits / 1419 steps while still matching the frank case verbatim. This mirrors the existing agentic-purity comment: 'Deliberately conservative (precision over recall)'. No warn tier (~240 warnings would train authors to ignore the output) and no per-step suppression marker.

<!-- fr:journal kind=decision scope=spec id=d3-escape created=2026-09-20T15:01:00 -->
### d3-escape · decision · A [manual] phase is the escape route — no new override mechanism

When a plan genuinely needs subagent work, it goes in a `[manual]` phase. The lint only inspects agentic phases, so the escape already exists and needs no code. Perfectly parallel to #252's rule, which this mirrors: dispatch is orchestrator-only work exactly as #252's target is human-only work. Rejected: a spec-scope override decision in the shape of `skeleton-override-<plan-slug>` — it is more machinery AND it would let an agentic phase keep a step the executor still cannot perform, which is the defect itself.

<!-- fr:journal kind=decision scope=spec id=d4-tiers created=2026-09-20T15:01:00 -->
### d4-tiers · decision · Model tiers rebound: claude-code/standard sonnet-5 → opus-5

Operator asked for 'standard & deep -> opus, fast -> sonnet'. fr's real tier vocabulary is `mechanical | standard | hard`, not fast/standard/deep (the question used the wrong names); mapped deep→hard, fast→mechanical. Resulting claude-code config: hard=claude-opus-5 (already bound), standard=claude-opus-5 (CHANGED from claude-sonnet-5), mechanical=claude-sonnet-5 (already bound). All three tiers are now bound, so no phase dispatch in this run can silently inherit the session model. opencode bindings untouched.
