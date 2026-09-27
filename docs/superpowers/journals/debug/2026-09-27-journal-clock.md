# Journal: 2026-09-27-journal-clock

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-27T10:26:22 -->
### repro · repro · journal stamps are naive local time, read in the reader's zone

super-fr#625. Writers `commands/journal_cmd.py:_timestamp`, `record/apply.py:_stamp` and the inline `fr run` decision stamp (`commands/run_cmd.py` ~1071) all call naive `datetime.now()`. `journal/model.py:journal_stamp_as_utc` localises a naive stamp in the READER's zone. A review written in a UTC container at T, read on a UTC+9 host, is interpreted as T-9h, so `fr run resolve` (`run_cmd.py` evidence gate) refuses it as "before this step opened". West of UTC the shift goes the other way, so a stale review is accepted. `journal/operator.py` has the same skew for its answered-since window.
