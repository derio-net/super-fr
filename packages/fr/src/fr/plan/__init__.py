"""Legacy v1 plan reader.

Retained ONLY for `fr migrate v1-to-v2`'s use — `vk.migrate` imports
`vk.plan.parser.parse_plan` to read v1 `.md` plans during conversion to
the v2 plan-as-folder format. No v2 code path other than the migration
tool touches this package.

Phase 6 of the v2 rebuild self-migrates this repo's remaining v1 plans;
once that is done and no consumer repo still has v1 plans in flight, the
whole `vk.plan/` directory (and `vk.migrate`) can be deleted.
"""
