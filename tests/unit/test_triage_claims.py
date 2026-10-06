"""Claims smoke: the test wiring runs before any claim code exists."""

import fr.triage  # noqa: F401
from fr import labels


def test_the_in_progress_label_is_where_claims_will_sit_beside_it() -> None:
    assert labels.FR_IN_PROGRESS.name == "fr:in-progress"
