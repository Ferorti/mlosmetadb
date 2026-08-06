import asyncio

from queries.search_queries import advanced_search, get_advanced_search_facets


def test_advanced_search_mlo_filter_excludes_inactive_only_protein(test_db):
    total, rows = asyncio.run(
        advanced_search(
            gene_name=None, uniprot_id=None, organism=None, taxon_id=None,
            mlo="nucleolus", role=None, source_db=None,
            feature_type=None, feature_label=None, feature_accession=None,
            page=1, per_page=50,
        )
    )
    assert total == 0
    assert rows == []


def test_advanced_search_facets_mlo_bucket_excludes_inactive_annotation(test_db):
    facets = asyncio.run(
        get_advanced_search_facets(
            gene_name=None, uniprot_id=None, organism=None, taxon_id=None,
            mlo=None, role=None, source_db=None,
            feature_type=None, feature_label=None, feature_accession=None,
        )
    )
    assert facets["by_mlo"].get("nucleolus") is None
    assert facets["by_mlo"].get("stress_granule") == 1
