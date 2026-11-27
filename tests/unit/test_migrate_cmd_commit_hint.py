"""`fr migrate artifacts --yes` prints the commit to make; under quiet and stealth a moved
file's destination is in the configuration checkout, outside the product, and fr already
pushed it there. Found by the config-homes scenario (plan 2026-11-24-s1-configuration-homes
P7.T1.S1): the printed `git add --` named those outside paths, so the command it told the
operator to run failed with "outside repository"."""

from __future__ import annotations

from pathlib import Path

from fr.commands.migrate_cmd import _commit_paths


def test_only_paths_inside_the_product_are_named(tmp_path: Path) -> None:
    product = tmp_path / "work"
    config = tmp_path / "fr-config"
    paths = [product / "docs/superpowers/models.yaml", config / ".fr/models.yaml"]
    inside, outside = _commit_paths(paths, product)
    assert inside == ["docs/superpowers/models.yaml"]
    assert outside == [str(config / ".fr/models.yaml")]


def test_a_symlinked_spelling_of_the_product_still_counts_as_inside(tmp_path: Path) -> None:
    real = tmp_path / "real"
    (real / "docs").mkdir(parents=True)
    (tmp_path / "link").symlink_to(real)
    inside, outside = _commit_paths([tmp_path / "link/docs/x.yaml"], real)
    assert inside == ["docs/x.yaml"] and outside == []
