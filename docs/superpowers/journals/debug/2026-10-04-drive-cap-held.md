# Journal: 2026-10-04-drive-cap-held

<!-- fr:journal kind=repro scope=debug id=f6334fddb4de created=2026-10-04T04:25:20+00:00 -->
### f6334fddb4de · repro · drive plan silent when the in-flight cap holds the selection

gh#913: four unselected batches in flight, two selected wave-1 batches proposed, max_inflight 4. `drive --once` printed only `in flight 0, merged 0, pending 2, closing 0` and dispatched nothing, no line saying why. Repro as a pure drive_pass snapshot: unselected occupants fill the cap, selected batches proposed → actions == ().
