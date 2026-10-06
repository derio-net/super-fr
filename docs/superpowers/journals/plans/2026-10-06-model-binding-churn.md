# Journal: 2026-10-06-model-binding-churn

<!-- fr:journal kind=discovery scope=plan id=p1-opencode-run-needs-closed-stdin created=2026-10-06T18:13:34+00:00 phase=1 -->
### p1-opencode-run-needs-closed-stdin · discovery · opencode run blocks forever when stdin is left open (phase 1)

Capturing the probe fixtures, `opencode run` with an inherited stdin produced no output for 90 s and was killed by timeout (rc 124). With `</dev/null` it answers in seconds. run_opencode therefore passes stdin=DEVNULL. Also observed: a dead model (ProviderModelNotFoundError) exited 1, not 0 as the spec background says, so classify never reads the return code.

<!-- fr:journal kind=discovery scope=plan id=p1-argument-injection-guard created=2026-10-06T18:13:34+00:00 phase=1 -->
### p1-argument-injection-guard · discovery · Binding values can arrive from the tracked repo models.yaml and reach opencode's argv (phase 1)

Coordinator-directed security fix. fr.bindings.valid_provider/valid_model_name/valid_model_id (provider ^[A-Za-z0-9][A-Za-z0-9._-]*$, model part ^[A-Za-z0-9][A-Za-z0-9._:-]*$). OpenCodeProber.probe returns unknown (`<m> is not a provider/model id`) and catalogue returns [] for an invalid value WITHOUT spawning; the model is passed as the single token --model=<id>. `fr models set` refuses (exit 2) an opencode id that is not provider/model, and for other harnesses a value starting with '-' or containing whitespace, before writing; claude-code bare ids such as claude-opus-5-5 still work. The stub opencode and fixtures README were updated for --model=. Existing opencode `set` tests that used bare names (m, s, h) now use p/m, p/s, p/h.

<!-- fr:journal kind=decision scope=plan id=p1-hint-only-without-lineage created=2026-10-06T18:13:34+00:00 phase=1 -->
### p1-hint-only-without-lineage · decision · Provider hint is tried only when the dead model has no entry and no snapshot (phase 1)

Spec R4 lists family, tier, hint in order but says the hint applies when neither rule above has inputs. Read literally: with no catalogue entry and no snapshot the family rule has no family and the tier rule has no dead price, so only the hint is tried (and a hinted pick is never autonomous). A dead model that does have lineage never uses the hint.

<!-- fr:journal kind=decision scope=plan id=p1-unknown-not-cached created=2026-10-06T18:13:34+00:00 phase=1 -->
### p1-unknown-not-cached · decision · ProbeCache stores only live and dead verdicts (phase 1)

An unknown (timeout, server error) is a transient failure; caching it for 6 h would hide recovery. fresh=True still bypasses for the others.

<!-- fr:journal kind=decision scope=plan id=p1-prober-seam created=2026-10-06T18:13:34+00:00 phase=1 -->
### p1-prober-seam · decision · fr.bindings.prober_for is the one monkeypatched factory; default_prober_for is its implementation (phase 1)

Callers must use fr.bindings.prober_for(...) via the module attribute. tests/conftest.py autouse fixture replaces it with an always-live, empty-catalogue prober and sets FR_MODELS_CACHE_DIR (a new override of the $HOME/.cache/fr/models path) so the suite never touches the real opencode or an operator's cache. Phase 2 tests monkeypatch the same name.

<!-- fr:journal kind=discovery scope=plan id=p1-check-exit-and-repo-layer created=2026-10-06T18:13:34+00:00 phase=1 -->
### p1-check-exit-and-repo-layer · discovery · fr models check on a repo-layer dead binding (phase 1)

check never rewrites docs/superpowers/models.yaml (R9): on a terminal it names the file and does not offer to apply; the dead binding still counts toward exit 1.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-06T18:13:34+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

check_bindings was already one function over choose_replacement/offers; nothing to extract beyond naming.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t7 created=2026-10-06T18:13:34+00:00 phase=1 -->
### no-refactor-p1-t7 · discovery · no-refactor-because P1.T7 (phase 1)

Scenario scripts share one sourced helper (_stub_opencode.sh) from the start; nothing duplicated to clean.
