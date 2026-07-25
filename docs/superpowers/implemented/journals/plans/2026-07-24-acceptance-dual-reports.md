# Journal: 2026-07-24-acceptance-dual-reports

<!-- fr:journal kind=review scope=plan id=rev-independent created=2026-07-24T22:16:37 -->
### rev-independent · review · Independent review: no blockers/majors/minors, 4 nits

Determinism empirically confirmed across checkout paths. check() fold-in verified existence-gated/read-only/exit-1. Back-compat github single render intact.

<!-- fr:journal kind=finding scope=plan id=f1-out-sentinel created=2026-07-24T22:16:37 state=fixed -->
### f1-out-sentinel · finding [fixed] · report --out default-collision: explicit --out == default was treated as SET

Fixed: --out now defaults to None (sentinel); explicit --out (even == default path) is single-file. New test test_report_explicit_out_equal_to_default_is_single_file. Also resolves nit#2 (explicit-out link-mode intent).

<!-- fr:journal kind=finding scope=plan id=f2-nits-accepted created=2026-07-24T22:16:37 state=refuted -->
### f2-nits-accepted · finding [refuted] · check.py dead-guard + init-degrade skipped-semantics (nits 3,4)

Left as-is: the try/except is harmless defense-in-depth; degrade-to-skipped is documented by test_init_degrades. Neither is a defect.
