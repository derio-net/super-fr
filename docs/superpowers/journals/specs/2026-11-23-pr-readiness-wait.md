<!-- fr:journal-schema=4 -->
# Journal: 2026-11-23-pr-readiness-wait

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-23T07:59:36+00:00 input=true -->
### brief · discovery · Operator brief

I've noticed that, when super-fr delivers a draft PR, either via fr-goal or fr-debugging or the closeout PR, it doesn't wait to see whether it can merge cleanly or whether CI is green. I think a repo-level setting should be introduced that sets these behaviors. These default behaviors can be overriden per feature/bug is needed.
