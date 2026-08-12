import asyncio

import database
from main import _compute_stats


def test_compute_stats_mlo_annotations_excludes_inactive_row(test_db):
    """QEXCL1's dataset_active=0 row is the one left out. QREG01's regulator row
    is counted since R1-ACT-14, which is why DrLLPS appears here at all."""
    stats = asyncio.run(_compute_stats())
    assert stats["mlo_annotations"]["total"] == 4
    assert stats["mlo_annotations"]["by_source"] == {"PhaSepDB": 2, "CDCODE": 1, "DrLLPS": 1}
    assert stats["mlo_annotations"]["unique_mlos"] == 4


def test_compute_stats_buckets_regulators_as_unknown_not_as_a_third_role(test_db):
    """/stats keys by_role off the raw unified_role value, so a regulator lands in
    'unknown' together with CD-CODE's roleless rows. That is deliberate and
    documented in api/CLAUDE.md: only /mlo/{id} grew a 'regulator' bucket. If this
    endpoint should distinguish them too, the fix is a third branch here, not a
    'regulator' string written into unified_role."""
    stats = asyncio.run(_compute_stats())
    assert stats["mlo_annotations"]["by_role"] == {"driver": 1, "client": 1, "unknown": 2}


def test_compute_stats_unique_proteins_by_source_dedupes_multiple_annotations(test_db):
    async def _setup_and_run():
        conn = await database.get_db()
        await conn.execute(
            "INSERT INTO mlo_vocabulary (unified_mlo, spatial_location, physiological_state) "
            "VALUES ('extra_mlo', 'cytoplasm', 'constitutive')"
        )
        await conn.execute(
            "INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active) "
            "VALUES ('P35637', 'PhaSepDB', 'extra_mlo', 'driver', 1)"
        )
        await conn.commit()
        return await _compute_stats()

    stats = asyncio.run(_setup_and_run())
    # P35637 now has two ACTIVE PhaSepDB rows (stress_granule + extra_mlo): by_source
    # (row count) must reflect both, but unique_proteins_by_source (protein count)
    # must still count P35637 once -- that's the whole point of the new field.
    assert stats["mlo_annotations"]["by_source"]["PhaSepDB"] == 3
    assert stats["mlo_annotations"]["unique_proteins_by_source"]["PhaSepDB"] == 2
    assert stats["mlo_annotations"]["unique_proteins_by_source"]["CD-CODE"] == 1


def test_compute_stats_organism_other_count_covers_the_long_tail(test_db):
    async def _setup_and_run():
        conn = await database.get_db()
        # Fixture already has 4 proteins, all organism='Homo sapiens'. Add 10 more
        # single-protein organisms so there are 11 distinct organisms total --
        # one more than by_organism's LIMIT 10 -- so exactly one organism (whichever
        # the DB's tie-break excludes; all ties have count=1, so it doesn't matter
        # which) must fall into other_organisms_count regardless of ordering.
        for i in range(10):
            await conn.execute(
                "INSERT INTO proteins (uniprot_id, gene_name, organism, length) VALUES (?, ?, ?, ?)",
                (f"PORG{i:02d}", f"ORGTEST{i}", f"Test organism {i}", 100),
            )
        await conn.commit()
        return await _compute_stats()

    stats = asyncio.run(_setup_and_run())
    assert stats["proteins"]["total_organisms"] == 11
    assert len(stats["proteins"]["by_organism"]) == 10
    # The defining invariant: top-10 sum + the "other" count must reconcile to the
    # real total, so a donut/pie chart built from these two numbers together always
    # matches the headline protein count -- never a silently-truncated top-10 sum.
    assert (
        sum(stats["proteins"]["by_organism"].values()) + stats["proteins"]["other_organisms_count"]
        == stats["proteins"]["total"]
    )
    assert stats["proteins"]["other_organisms_count"] == 1
