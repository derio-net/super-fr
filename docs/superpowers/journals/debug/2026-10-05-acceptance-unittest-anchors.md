# Journal: 2026-10-05-acceptance-unittest-anchors

<!-- fr:journal kind=repro scope=debug id=9f19f502254f created=2026-10-05T20:36:40+00:00 -->
### 9f19f502254f · repro · unittest spellings fail both anchor paths

node_line("class TestA:\n    def test_b(self): pass\n", "TestA.test_b") -> None (the :: form -> 2), so `fr acceptance check` reports a live test as "renamed or deleted" (gh#965). collected_node_at(src, 4) for `class FooTests(unittest.TestCase): def test_x` -> None, so the matrix-name-anchors repair never converts a #L<n> that sits in it (gh#893).
