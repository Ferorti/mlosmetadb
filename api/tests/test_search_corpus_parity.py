"""One corpus, whether or not a filter is applied.

The defect these pin down: a free-text search with any filter escalated to
/search/advanced, whose only text parameter was `gene_name`, a single-column
LIKE. So "kinase" — which matches 50 real proteins by protein_name and none by
gene_name — returned nothing the moment a filter was touched, and searching
nucleolin among drivers reported zero.

The fix is one shared corpus: /search/advanced?q= must match exactly what
/search?q= matches, so applying a filter narrows the result set and never
changes what "matching" means.
"""

from fastapi.testclient import TestClient

from main import app
from tests.conftest_search import search_db  # noqa: F401  (pytest fixture)


def basic(client, q):
    r = client.get("/search", params={"q": q, "mode": "fuzzy"})
    assert r.status_code == 200, r.text
    return {p["uniprot_id"] for p in r.json()["proteins"]}


def advanced(client, **params):
    r = client.get("/search/advanced", params={"per_page": 50, **params})
    assert r.status_code == 200, r.text
    return {p["uniprot_id"] for p in r.json()["proteins"]}


# ── the two paths must agree ─────────────────────────────────────────────────

def test_free_text_matches_the_same_proteins_on_both_paths(search_db):
    with TestClient(app) as c:
        for q in ("kinase", "INASE", "A_B", "C%D", "KiNaSe"):
            assert advanced(c, q=q) == basic(c, q), q


def test_advanced_free_text_reaches_uniprot_id(search_db):
    with TestClient(app) as c:
        assert "KINASE9" in advanced(c, q="kinase")


def test_advanced_free_text_escapes_like_metacharacters(search_db):
    with TestClient(app) as c:
        assert advanced(c, q="A_B") == {"P00005"}
        assert advanced(c, q="C%D") == {"P00007"}


# ── the regression itself ────────────────────────────────────────────────────

def test_a_filter_narrows_the_result_set_without_changing_the_corpus(search_db):
    """P00001 is a driver whose only "kinase" match is its gene_name."""
    with TestClient(app) as c:
        unfiltered = advanced(c, q="kinase")
        drivers = advanced(c, q="kinase", role="driver")
    assert "P00001" in unfiltered
    assert "P00001" in drivers, "a gene_name match vanished as soon as a filter was applied"
    assert drivers <= unfiltered, "filtering must be a subset, not a different search"


def test_filtering_by_organelle_keeps_gene_name_matches(search_db):
    with TestClient(app) as c:
        assert "P00001" in advanced(c, q="kinase", mlo="stress_granule")


# ── q counts as a filter, and paginates ──────────────────────────────────────

def test_free_text_alone_is_enough_to_query_the_endpoint(search_db):
    with TestClient(app) as c:
        r = c.get("/search/advanced", params={"q": "kinase"})
    assert r.status_code == 200, "q alone should satisfy the no-filters check"


def test_no_parameters_at_all_is_still_rejected(search_db):
    with TestClient(app) as c:
        r = c.get("/search/advanced")
    assert r.status_code == 422
    assert r.json()["error"] == "no_filters_provided"


def test_free_text_results_paginate_with_a_real_total(search_db):
    """The old path capped at 50 with no total, so its pager did nothing."""
    with TestClient(app) as c:
        first = c.get("/search/advanced", params={"q": "kinase", "page": 1, "per_page": 2}).json()
        second = c.get("/search/advanced", params={"q": "kinase", "page": 2, "per_page": 2}).json()
    assert first["total"] == second["total"]
    assert first["total"] >= 3
    ids_first = {p["uniprot_id"] for p in first["proteins"]}
    ids_second = {p["uniprot_id"] for p in second["proteins"]}
    assert len(ids_first) == 2
    assert not (ids_first & ids_second), "pages must not overlap"


# ── mode=exact (docs/issues/005) ─────────────────────────────────────────────
#
# Every free-text search from the results page goes through /search/advanced
# (this file's whole reason for existing), so mode=exact has to work HERE for
# the "Exact match" checkbox to mean anything -- /search's own mode=exact was
# never actually reachable from that checkbox after the escalation consolidation.

def test_advanced_mode_exact_matches_only_the_exact_gene_name(search_db):
    """The reported bug: q="FUS" under exact mode must not also match "FUS3"."""
    with TestClient(app) as c:
        assert advanced(c, q="FUS", mode="exact") == {"P00013"}


def test_advanced_mode_exact_is_case_insensitive(search_db):
    with TestClient(app) as c:
        assert advanced(c, q="fus", mode="exact") == {"P00013"}


def test_advanced_mode_fuzzy_still_matches_the_substring(search_db):
    """Unchanged default behaviour: fuzzy is the LIKE search this file already
    covers everywhere else."""
    with TestClient(app) as c:
        assert advanced(c, q="FUS", mode="fuzzy") == {"P00013", "P00014"}


def test_advanced_mode_exact_returns_empty_for_a_pure_substring_query(search_db):
    """"kinase" matches three proteins by substring (gene_name or uniprot_id)
    but is not literally any of their gene_name/uniprot_id values."""
    with TestClient(app) as c:
        assert advanced(c, q="kinase", mode="fuzzy") == {"P00001", "P00004", "KINASE9"}
        assert advanced(c, q="kinase", mode="exact") == set()


def test_advanced_mode_exact_still_composes_with_a_filter(search_db):
    with TestClient(app) as c:
        assert advanced(c, q="FUS", mode="exact", organism="Homo sapiens") == {"P00013"}
        assert advanced(c, q="FUS", mode="exact", organism="Saccharomyces cerevisiae") == set()


def test_advanced_default_mode_is_fuzzy_when_omitted(search_db):
    with TestClient(app) as c:
        assert advanced(c, q="FUS") == {"P00013", "P00014"}


def test_advanced_rejects_an_invalid_mode(search_db):
    with TestClient(app) as c:
        r = c.get("/search/advanced", params={"q": "FUS", "mode": "bogus"})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_parameter"


def test_free_text_respects_sorting(search_db):
    with TestClient(app) as c:
        asc = [p["uniprot_id"] for p in c.get(
            "/search/advanced", params={"q": "kinase", "sort_by": "gene_name", "sort_order": "asc", "per_page": 50}
        ).json()["proteins"]]
        desc = [p["uniprot_id"] for p in c.get(
            "/search/advanced", params={"q": "kinase", "sort_by": "gene_name", "sort_order": "desc", "per_page": 50}
        ).json()["proteins"]]
    assert set(asc) == set(desc)
    assert asc != desc
