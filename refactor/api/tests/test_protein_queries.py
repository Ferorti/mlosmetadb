import asyncio

from queries.protein_queries import (
    get_protein_mlo_annotations,
    get_proteins_facets,
    get_proteins_page,
)


def test_get_protein_mlo_annotations_excludes_inactive_row(test_db):
    rows = asyncio.run(get_protein_mlo_annotations("QREG01"))
    assert rows == []


def test_get_protein_mlo_annotations_includes_active_row(test_db):
    rows = asyncio.run(get_protein_mlo_annotations("P35637"))
    assert len(rows) == 1
    assert rows[0]["unified_mlo"] == "stress_granule"
    assert rows[0]["unified_role"] == "driver"


def test_get_proteins_page_role_filter_excludes_inactive_only_protein(test_db):
    total, rows = asyncio.run(
        get_proteins_page(None, None, "nucleolus", None, None, None, None, "asc", 1, 50)
    )
    assert total == 0
    assert rows == []


def test_get_proteins_facets_mlo_facet_excludes_inactive_annotation(test_db):
    facets = asyncio.run(get_proteins_facets(None, None, None, None, None, None))
    assert facets["by_mlo"].get("nucleolus") is None
    assert facets["by_mlo"].get("stress_granule") == 1
