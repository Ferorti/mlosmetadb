import asyncio

import policy
from queries.mlo_queries import get_all_mlos, get_mlo_proteins_page, get_mlo_stats


def test_get_mlo_stats_excludes_inactive_only_protein(test_db):
    stats = asyncio.run(get_mlo_stats("condensate_excluded"))
    assert stats["total_proteins"] == 0
    assert stats["by_source"] == {}


def test_get_mlo_stats_counts_active_protein(test_db):
    stats = asyncio.run(get_mlo_stats("stress_granule"))
    assert stats["total_proteins"] == 1
    assert stats["by_source"] == {"PhaSepDB": 1}
    assert stats["by_role"] == {"driver": 1}


def test_get_mlo_stats_buckets_a_regulator_as_its_own_role(test_db):
    """R1-ACT-14. QREG01's only annotation is a DrLLPS Regulator call on
    nucleolus: it now counts, and it must not count as a component -- 'component'
    asserts residency in the organelle, which is the one thing the source is not
    claiming. The old two-branch CASE folded all 1.389 of these into it."""
    stats = asyncio.run(get_mlo_stats("nucleolus"))
    assert stats["total_proteins"] == 1
    assert stats["by_role"] == {"regulator": 1}
    assert "component" not in stats["by_role"]


def test_regulator_rows_still_carry_a_null_unified_role(test_db):
    """The bucket is computed at read time from (evidence_type, source_role).
    If 'regulator' ever shows up in the stored column, this is where to look."""
    total, rows = asyncio.run(get_mlo_proteins_page("nucleolus", None, None, None, 1, 50))
    assert total == 1
    assert rows[0]["uniprot_id"] == "QREG01"
    assert rows[0]["unified_role"] is None


def test_get_mlo_proteins_page_excludes_inactive_only_protein(test_db):
    total, rows = asyncio.run(get_mlo_proteins_page("condensate_excluded", None, None, None, 1, 50))
    assert total == 0
    assert rows == []


def test_get_all_mlos_shows_zero_count_for_inactive_only_mlo(test_db):
    rows = asyncio.run(get_all_mlos())
    by_mlo = {r["unified_mlo"]: r for r in rows}
    assert by_mlo["stress_granule"]["protein_count"] == 1
    # condensate_excluded's only annotation is inactive -- it must still be listed
    # (mlo_vocabulary entry exists) but with a zero protein_count, not
    # disappear and not count the inactive row.
    assert by_mlo["condensate_excluded"]["protein_count"] == 0


def test_get_all_mlos_counts_a_regulator_only_mlo(test_db):
    """The inverse of the test above, and the reason the two are worth keeping
    apart: an unserved row and a served-but-roleless row look identical in this
    listing's shape and mean opposite things."""
    rows = asyncio.run(get_all_mlos())
    by_mlo = {r["unified_mlo"]: r for r in rows}
    assert by_mlo["nucleolus"]["protein_count"] == 1
    assert by_mlo["nucleolus"]["driver_count"] == 0


def test_excluded_mlo_spatial_clause_wired_into_get_all_mlos(test_db, monkeypatch):
    monkeypatch.setattr(policy, "EXCLUDED_MLO_SPATIAL_LOCATIONS", ["nucleus"])
    rows = asyncio.run(get_all_mlos())
    names = {r["unified_mlo"] for r in rows}
    assert "nucleolus" not in names       # spatial_location='nucleus', now excluded
    assert "stress_granule" in names      # spatial_location='cytoplasm', unaffected


def test_get_all_mlos_serves_the_four_axes(test_db):
    rows = asyncio.run(get_all_mlos())
    p_granule = next(r for r in rows if r["unified_mlo"] == "p_granule")
    assert p_granule["spatial_location"] == "cytoplasm"
    assert p_granule["taxonomic_scope"] == "Metazoa"
    assert p_granule["physiological_state"] == "constitutive"
    assert p_granule["cell_type_context"] == "germline"
    # Served next to the taxonomic scope so a client can tell a scope resting on
    # 4 proteins from one resting on 400 (see MloAxesWithProvenance).
    assert p_granule["taxonomic_support_n"] == 4
    assert p_granule["spatial_location_evidence"] == "from_category"


def test_get_all_mlos_filters_on_each_axis_independently(test_db):
    async def names(**kwargs):
        return {r["unified_mlo"] for r in await get_all_mlos(**kwargs)}

    assert asyncio.run(names(spatial_location="nucleus")) == {"nucleolus"}
    assert asyncio.run(names(physiological_state="stress_induced")) == {"stress_granule"}
    assert asyncio.run(names(cell_type_context="germline")) == {"p_granule"}
    # Orthogonal axes conjoin: this is the question `category` could not ask.
    assert asyncio.run(names(spatial_location="cytoplasm",
                             physiological_state="stress_induced")) == {"stress_granule"}
    assert asyncio.run(names(spatial_location="nucleus",
                             physiological_state="stress_induced")) == set()
