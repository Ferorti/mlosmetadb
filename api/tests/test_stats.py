import asyncio

from main import _compute_stats


def test_compute_stats_mlo_annotations_excludes_inactive_row(test_db):
    stats = asyncio.run(_compute_stats())
    assert stats["mlo_annotations"]["total"] == 3
    assert stats["mlo_annotations"]["by_source"] == {"PhaseDB": 2, "CDCODE": 1}
    assert stats["mlo_annotations"]["unique_mlos"] == 3
