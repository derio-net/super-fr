# Journal: 2026-09-20-phases-file-tier-reaches-dispatch

<!-- fr:journal kind=decision scope=spec id=d1 created=2026-09-20T13:29:13 -->
### d1 · decision · Scope includes the fr-plan prose, not only the CLI ingestion

Operator answered the batched gate: 'CLI + fr-plan prose'. The three code edits alone leave tier reachable but unrequested — fr-plan/SKILL.md never mentions tier, while fr-goal §3 already asserts 'fr-plan tags each phase a tier'. The skill gains the instruction and .opencode/skills/fr-plan/SKILL.md is regenerated via scripts/sync-opencode.py.

<!-- fr:journal kind=decision scope=spec id=d2 created=2026-09-20T13:29:14 -->
### d2 · decision · Both self-review gates ship: the tier fr_version floor probe AND the untiered-agentic warning

Operator selected both. Floor probe mirrors the acceptance 3.7.0 / skeleton probes for tier's 3.12.0 introduction against the default '>=3.0.0,<5.0.0'. Untiered warning makes the silent untiered dispatch fallback observable at plan time (#498's fail-visibly doctrine). Disclosed and accepted before the decision: both fire immediately on this repo's existing plans. Both are severity=warn, so no exit code and no CI gate changes.

<!-- fr:journal kind=decision scope=spec id=d3 created=2026-09-20T13:29:14 -->
### d3 · decision · Patch bump 4.8.0 -> 4.8.1

Operator chose patch over minor. The behaviour shipped in 3.12.0; this restores it rather than adding it, and the fr-plan prose documents an obligation fr-goal already asserted. AGENTS.md makes patch the default for CLI fixes and skill copy.

<!-- fr:journal kind=decision scope=spec id=d4 created=2026-09-20T13:29:15 -->
### d4 · decision · Verification is unit plus an in-repo end-to-end to the dispatch brief

Operator chose 'Unit + in-repo end-to-end' over unit-only and over a post-merge live item. An integration test scaffolds a tiered plan through --phases-file and drives fr run advance to the implement group's first member, asserting the brief carries that phase's tier. It stops short of a real subagent; the live session-row claim stays with opencode-subagent-dispatch at skipped.

<!-- fr:journal kind=decision scope=spec id=d5 created=2026-09-20T13:29:15 -->
### d5 · decision · The brief gains resolved_tier; tier keeps its meaning as the manifest literal

Follow-up question, asked because the chosen D4 test presumed a brief field that does not exist. Operator chose the additive key over resolving from_phase in place. Resolving in place would break the documented property that the brief is a faithful exhaustive echo of every Step field, which test_the_dispatch_brief_is_exhaustive_of_steps_agent_relevant_fields derives from the model. resolved_tier is added to the MEMBER brief only — a group spans every phase and has no single tier to resolve — and is null when the phase declares none.

<!-- fr:journal kind=discovery scope=spec id=disc1 created=2026-09-20T13:29:30 -->
### disc1 · discovery · The #498 premise is wrong: tier DOES reach this repo's plans, by hand-edit

The goal statement held that tier 'currently never reaches the plan on any harness at all', and asked whether that explains most of #498. It does not. Two live plans here carry real tiers (2026-09-19-opencode-subagent-dispatch, 2026-09-20-opencode-tier-binding-reaches-dispatch). Forensic evidence that create() did not write them: _build_phase_doc appends acceptance and skeleton at the END of the header dict, but in both plans tier sits between tag and depends_on — where PhaseHeader declares it, and where a hand-edit would put it. create() cannot produce that ordering. So #498's observed artifact (an installed OpenCode agent file with no model: line) is an independent break, correctly fixed by #504. #434's real contribution to that chain is that tier arrival is unreliable and undocumented — and post-#504 MORE dangerous, because the agent files now carry correct models, so an untiered dispatch is indistinguishable from working tiering.

<!-- fr:journal kind=discovery scope=spec id=disc2 created=2026-09-20T13:29:31 -->
### disc2 · discovery · A third break: fr never resolves the from_phase sentinel into the dispatch brief

tier: from_phase in the shipped manifest is a policy sentinel nothing in fr resolves. _build_member_brief (run_cmd.py:628) returns 'member.tier if member.tier is not None else group.tier', so the brief hands the orchestrator the literal string 'from_phase'. The join to a concrete tier is delegated entirely to the LLM orchestrator via fr-goal §5 prose. Found while checking whether D4's chosen test was writable — it was not, which is what prompted the D5 follow-up question.

<!-- fr:journal kind=discovery scope=spec id=disc3 created=2026-09-20T13:29:31 -->
### disc3 · discovery · Matrix row fr-goal-phase-tiering reads ci for a capability broken upstream of its tests

The row claims 'fr-plan annotates each phase with a tier; the orchestrator dispatches that phase's subagent at the mapped model' at status: ci. Its unit levels pin PhaseHeader.tier and fr models resolve in ISOLATION; nothing pins that a planner's tier reaches a plan, and until this spec ships it cannot. Same pattern #498 named. Corrected in this PR.
