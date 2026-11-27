# CI hygiene sweep

One agentic phase: six small CI leftovers from the single-Python change, one reviewable diff.
Tasks follow the spec Design sections: R4 (UV_PYTHON + tripwire), R5 (permissions + tripwire),
R1 (retire spec-status), R2/R3 (floors.py and test_ci_shards.py leftovers), then the two
acceptance rows move to `ci` and the quality gate runs.

No member issue is a phase `tracking_issue` (the wave driver owns their labels).
