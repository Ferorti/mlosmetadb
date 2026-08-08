"""What /search actually matches, field by field and edge case by edge case.

These assert the behaviour the search *should* have. Where one fails, it names
a real defect rather than a changed convention — see the module each test
points at.
"""

from fastapi.testclient import TestClient

from main import app
from tests.conftest_search import search_db  # noqa: F401  (pytest fixture)


def hits(client, **params):
    r = client.get("/search", params={"mode": "fuzzy", **params})
    assert r.status_code == 200, r.text
    return r.json()


def ids(payload):
    return {p["uniprot_id"] for p in payload["proteins"]}


# ── which fields a protein search covers ─────────────────────────────────────

def test_matches_through_gene_name(search_db):
    with TestClient(app) as c:
        assert "P00001" in ids(hits(c, q="kinase"))


def test_matches_through_protein_name(search_db):
    """The case that made the field select dangerous: on the real database all
    50 hits for "kinase" exist only because of protein_name."""
    with TestClient(app) as c:
        assert "P00002" in ids(hits(c, q="kinase"))


def test_matches_through_uniprot_id(search_db):
    with TestClient(app) as c:
        assert "KINASE9" in ids(hits(c, q="kinase"))


def test_all_three_fields_answer_one_query(search_db):
    with TestClient(app) as c:
        found = ids(hits(c, q="kinase"))
    assert {"P00001", "P00002", "KINASE9"} <= found


def test_matching_is_case_insensitive(search_db):
    with TestClient(app) as c:
        assert "P00004" in ids(hits(c, q="KINASE"))
        assert "P00004" in ids(hits(c, q="kinase"))
        assert "P00004" in ids(hits(c, q="KiNaSe"))


def test_null_gene_and_protein_name_do_not_break_the_query(search_db):
    with TestClient(app) as c:
        found = ids(hits(c, q="kinase"))
    assert "P00008" not in found


# ── whole-word vs substring, which differs per field ─────────────────────────

def test_protein_name_matches_whole_words_only(search_db):
    """protein_name is matched with '% q %', so "kinase" does not hit
    "Phosphokinaselike". gene_name and uniprot_id are plain substrings. The
    asymmetry is deliberate — it keeps protein_name from matching everything —
    but it is invisible from the UI, so it is pinned down here."""
    with TestClient(app) as c:
        found = ids(hits(c, q="kinase"))
    assert "P00009" not in found


def test_gene_name_matches_substrings(search_db):
    with TestClient(app) as c:
        assert "P00001" in ids(hits(c, q="INASE"))


# ── SQL LIKE metacharacters arriving from user input ─────────────────────────

def test_underscore_in_a_query_is_literal_not_a_wildcard(search_db):
    """'A_B' is a real gene name here and 'AXB' is the decoy. Without ESCAPE,
    LIKE treats '_' as "any single character" and the decoy matches too."""
    with TestClient(app) as c:
        found = ids(hits(c, q="A_B"))
    assert "P00005" in found
    assert "P00006" not in found


def test_percent_in_a_query_is_literal_not_a_wildcard(search_db):
    """'%' from the user must not turn into "match anything"."""
    with TestClient(app) as c:
        found = ids(hits(c, q="C%D"))
    assert found == {"P00007"}


# ── MLO name matching ────────────────────────────────────────────────────────

def test_mlo_matches_the_slug(search_db):
    with TestClient(app) as c:
        assert "stress_granule" in {m["unified_mlo"] for m in hits(c, q="stress_granule")["mlos"]}


def test_mlo_matches_the_spaced_spelling(search_db):
    with TestClient(app) as c:
        assert "stress_granule" in {m["unified_mlo"] for m in hits(c, q="stress granule")["mlos"]}


def test_mlo_matching_is_case_insensitive(search_db):
    with TestClient(app) as c:
        assert "stress_granule" in {m["unified_mlo"] for m in hits(c, q="Stress Granule")["mlos"]}


# ── response contract ────────────────────────────────────────────────────────

def test_total_hits_counts_proteins_and_mlos_together(search_db):
    """Not a defect in itself — the field is named total_hits — but it is the
    number the results header used to print as "N proteins"."""
    with TestClient(app) as c:
        payload = hits(c, q="stress granule")
    assert payload["total_hits"] == len(payload["proteins"]) + len(payload["mlos"])


def test_a_query_matching_nothing_returns_empty_lists_not_an_error(search_db):
    with TestClient(app) as c:
        payload = hits(c, q="zzzznomatch")
    assert payload["proteins"] == [] and payload["mlos"] == []


def test_whitespace_only_query_is_rejected(search_db):
    """A blank query must not degrade into '%%', which matches the corpus."""
    with TestClient(app) as c:
        r = c.get("/search", params={"q": "   "})
    assert r.status_code == 422, f"returned {r.status_code} with {len(r.json().get('proteins', []))} proteins"


def test_exact_mode_without_fts5_is_a_clean_501(search_db):
    with TestClient(app) as c:
        r = c.get("/search", params={"q": "kinase", "mode": "exact"})
    assert r.status_code in (200, 501)
    if r.status_code == 501:
        assert r.json()["error"] == "fts5_unavailable"


def test_an_invalid_mode_is_rejected(search_db):
    with TestClient(app) as c:
        r = c.get("/search", params={"q": "kinase", "mode": "sideways"})
    assert r.status_code == 422


# ── policy: inactive datasets must be invisible ──────────────────────────────

def test_inactive_annotations_are_not_searchable(search_db):
    """P00006's only annotation has dataset_active = 0."""
    with TestClient(app) as c:
        r = c.get("/proteins", params={"mlo": "p_granule"})
    assert r.status_code == 200
    assert r.json()["total"] == 0


# ── startup guard ────────────────────────────────────────────────────────────

def test_a_missing_database_fails_loudly(tmp_path, monkeypatch):
    """sqlite3.connect() creates an empty file for a path that does not exist,
    so a wrong MLOSMETADB_PATH used to surface as "no such table: main.proteins"
    from inside the FTS5 build — which says nothing about the real problem."""
    import asyncio

    import database as db_module

    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "nope.db")
    try:
        asyncio.run(db_module.open_db())
    except RuntimeError as e:
        assert "Database not found" in str(e)
        assert "nope.db" in str(e)
    else:
        raise AssertionError("open_db() accepted a nonexistent database")
    finally:
        db_module._db = None
