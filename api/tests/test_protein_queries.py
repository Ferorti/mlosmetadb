import asyncio

from queries.protein_queries import (
    get_protein_mlo_annotations,
    get_proteins_facets,
    get_proteins_page,
)


def test_get_protein_mlo_annotations_excludes_inactive_row(test_db):
    rows = asyncio.run(get_protein_mlo_annotations("QEXCL1"))
    assert rows == []


def test_get_protein_mlo_annotations_includes_active_row(test_db):
    rows = asyncio.run(get_protein_mlo_annotations("P35637"))
    assert len(rows) == 1
    assert rows[0]["unified_mlo"] == "stress_granule"
    assert rows[0]["unified_role"] == "driver"


def test_get_proteins_page_role_filter_excludes_inactive_only_protein(test_db):
    total, rows = asyncio.run(
        get_proteins_page(None, None, "condensate_excluded", None, None, None, None, "asc", 1, 50)
    )
    assert total == 0
    assert rows == []


def test_get_proteins_facets_mlo_facet_excludes_inactive_annotation(test_db):
    facets = asyncio.run(get_proteins_facets(None, None, None, None, None, None))
    assert facets["by_mlo"].get("condensate_excluded") is None
    assert facets["by_mlo"].get("stress_granule") == 1


def test_get_proteins_page_role_component_includes_null_role(test_db):
    total, rows = asyncio.run(
        get_proteins_page(None, None, None, "component", None, None, None, "asc", 1, 50)
    )
    ids = {r["uniprot_id"] for r in rows}
    assert "PNULLROLE" in ids  # NULL role must count as component
    assert "PCLIENT" in ids    # client role must also count as component
    assert "P35637" not in ids  # driver must NOT count as component


from queries.protein_queries import get_proteins_export


def test_get_proteins_export_no_filters_returns_all_proteins(test_db):
    rows = asyncio.run(get_proteins_export(None, None, None, None, None))
    ids = {r["uniprot_id"] for r in rows}
    assert ids == {"P35637", "PCLIENT", "PNULLROLE", "QREG01", "QEXCL1"}


def test_get_proteins_export_serves_regulators_and_still_drops_excluded_rows(test_db):
    """Both DrLLPS proteins in the fixture hang off one resource, and only one of
    them ships: QREG01's regulator row is served since R1-ACT-14, QEXCL1's
    dataset_active=0 row is not. Filtering by source_db has to separate them,
    which a filter that keyed on the resource could not do."""
    rows = asyncio.run(get_proteins_export(None, None, None, None, ["DrLLPS"]))
    assert {r["uniprot_id"] for r in rows} == {"QREG01"}


def test_get_proteins_export_source_db_filter_is_multi_value(test_db):
    rows = asyncio.run(get_proteins_export(None, None, None, None, ["PhaSepDB", "CDCODE"]))
    ids = {r["uniprot_id"] for r in rows}
    assert ids == {"P35637", "PCLIENT", "PNULLROLE"}


def test_get_proteins_export_role_component_includes_null_and_client(test_db):
    rows = asyncio.run(get_proteins_export(None, None, None, "component", None))
    ids = {r["uniprot_id"] for r in rows}
    assert "PNULLROLE" in ids
    assert "PCLIENT" in ids
    assert "P35637" not in ids
