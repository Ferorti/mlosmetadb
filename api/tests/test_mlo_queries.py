import asyncio

import policy
from queries.mlo_queries import get_all_mlos, get_mlo_proteins_page, get_mlo_stats


def test_get_mlo_stats_excludes_inactive_only_protein(test_db):
    stats = asyncio.run(get_mlo_stats("nucleolus"))
    assert stats["total_proteins"] == 0
    assert stats["by_source"] == {}


def test_get_mlo_stats_counts_active_protein(test_db):
    stats = asyncio.run(get_mlo_stats("stress_granule"))
    assert stats["total_proteins"] == 1
    assert stats["by_source"] == {"PhaSepDB": 1}
    assert stats["by_role"] == {"driver": 1}


def test_get_mlo_proteins_page_excludes_inactive_only_protein(test_db):
    total, rows = asyncio.run(get_mlo_proteins_page("nucleolus", None, None, None, 1, 50))
    assert total == 0
    assert rows == []


def test_get_all_mlos_shows_zero_count_for_inactive_only_mlo(test_db):
    rows = asyncio.run(get_all_mlos(category=None))
    by_mlo = {r["unified_mlo"]: r for r in rows}
    assert by_mlo["stress_granule"]["protein_count"] == 1
    # nucleolus's only annotation is inactive -- it must still be listed
    # (mlo_vocabulary entry exists) but with a zero protein_count, not
    # disappear and not count the inactive row.
    assert by_mlo["nucleolus"]["protein_count"] == 0


def test_excluded_mlo_category_clause_wired_into_get_all_mlos(test_db, monkeypatch):
    monkeypatch.setattr(policy, "EXCLUDED_MLO_CATEGORIES", ["Nuclear"])
    rows = asyncio.run(get_all_mlos(category=None))
    names = {r["unified_mlo"] for r in rows}
    assert "nucleolus" not in names       # category='Nuclear', now excluded
    assert "stress_granule" in names      # category='Cytoplasmic', unaffected
