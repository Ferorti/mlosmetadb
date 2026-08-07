import asyncio

import database
from main import _compute_stats


def test_compute_stats_mlo_annotations_excludes_inactive_row(test_db):
    stats = asyncio.run(_compute_stats())
    assert stats["mlo_annotations"]["total"] == 3
    assert stats["mlo_annotations"]["by_source"] == {"PhaseDB": 2, "CDCODE": 1}
    assert stats["mlo_annotations"]["unique_mlos"] == 3


def test_compute_stats_unique_proteins_by_source_dedupes_multiple_annotations(test_db):
    async def _setup_and_run():
        conn = await database.get_db()
        await conn.execute(
            "INSERT INTO mlo_vocabulary (unified_mlo, category) VALUES ('extra_mlo', 'Cytoplasmic')"
        )
        await conn.execute(
            "INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active) "
            "VALUES ('P35637', 'PhaseDB', 'extra_mlo', 'driver', 1)"
        )
        await conn.commit()
        return await _compute_stats()

    stats = asyncio.run(_setup_and_run())
    # P35637 now has two ACTIVE PhaseDB rows (stress_granule + extra_mlo): by_source
    # (row count) must reflect both, but unique_proteins_by_source (protein count)
    # must still count P35637 once -- that's the whole point of the new field.
    assert stats["mlo_annotations"]["by_source"]["PhaseDB"] == 3
    assert stats["mlo_annotations"]["unique_proteins_by_source"]["PhaseDB"] == 2
    assert stats["mlo_annotations"]["unique_proteins_by_source"]["CDCODE"] == 1
