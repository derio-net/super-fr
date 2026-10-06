"""Model bindings that survive provider churn (spec 2026-10-06-model-binding-churn).

`fr.models` stays the config layer (tier -> model strings). This package asks a
provider whether a bound model still answers (`probe`), reads the catalogue for
lineage and price (`catalogue`), picks a replacement by fixed rules (`choose`)
and reports a harness's bindings as a whole (`health`).
"""
