# Journal: 2026-09-27-journal-clock

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-27T10:26:22 -->
### repro · repro · journal stamps are naive local time, read in the reader's zone

super-fr#625. Writers `commands/journal_cmd.py:_timestamp`, `record/apply.py:_stamp` and the inline `fr run` decision stamp (`commands/run_cmd.py` ~1071) all call naive `datetime.now()`. `journal/model.py:journal_stamp_as_utc` localises a naive stamp in the READER's zone. A review written in a UTC container at T, read on a UTC+9 host, is interpreted as T-9h, so `fr run resolve` (`run_cmd.py` evidence gate) refuses it as "before this step opened". West of UTC the shift goes the other way, so a stale review is accepted. `journal/operator.py` has the same skew for its answered-since window.

<!-- fr:journal kind=root-cause scope=debug id=rc created=2026-09-27T10:26:23 -->
### rc · root-cause · writers omit the offset, so the writer's zone is lost

A naive stamp carries no zone. The reader can only guess its own zone, which is right only when writer and reader share a TZ. Fix at the source: every writer stamps aware UTC (`+00:00`), matching the run cursor's `_now`. The reader keeps its current fallback for legacy naive stamps. Not an artifact shape change: `created` is a `str`, the header tokeniser splits on spaces (no space in `+00:00`), and every released reader parses it with `fromisoformat` and then `astimezone(UTC)`/`parse_timestamp`, which already handle an aware value (see the existing `journal_stamp_as_utc("...+00:00")` assertion in test_journal_model). The structure validator does not check the format. No stamp bump.

<!-- fr:journal kind=finding scope=debug id=fix created=2026-09-27T08:34:13+00:00 state=fixed -->
### fix · finding [fixed] · all three writers stamp aware UTC via journal_now()

New `fr.journal.model.journal_now()` (UTC, second precision, `+00:00`). `journal_cmd._timestamp`, `record.apply._stamp` and the inline decision stamp in `run_cmd` call it. `journal_stamp_as_utc` is unchanged, so legacy naive stamps still read in the reader zone. The gate refusal message no longer calls the stamp "(local)". Pinned by `tests/unit/test_journal_stamp_offset.py`, committed red first (8 failures): UTC writer read in Tokyo/LA for both callable writers, a source tripwire against naive `datetime.now()` in all three writer modules, and end-to-end, a UTC-written review accepted by the spec-review gate under Asia/Tokyo. No artifact stamp bump (see rc).

<!-- fr:journal kind=review scope=debug id=review created=2026-09-27T08:37:08+00:00 -->
### review · review · independent review: no findings

A separate-context reviewer checked four things and raised no findings at confidence >= 80: (1) no other naive `created` writer exists in packages/*/src or plugins/; (2) mixing naive and aware stamps breaks nothing, because `_same_entry` excludes `created`, entries are never sorted by it, and both readers go through `journal_stamp_as_utc`; (3) this is not an artifact shape change (`created: str`, the space-split tokenizer is unaffected); (4) the tests pin writer and reader TZ separately and restore it.
