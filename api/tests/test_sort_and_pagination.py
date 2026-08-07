"""The sort and pagination contract of /proteins.

_build_sort's docstring states the contract — NULLs always last regardless of
direction, uniprot_id breaks every tie, role encoded as a rank — and warns that
`frontend/src/utils/sortProteins.js` mirrors it with "no test suite that would
catch the drift". This file is the missing half of that: it pins the server
side down so the mirror has something to be checked against.
"""

from fastapi.testclient import TestClient

from main import app
from tests.conftest_search import sort_db  # noqa: F401  (pytest fixture)

SORTABLE = ["gene_name", "mlo_count", "source_db_count", "disorder_mobidb_lite_dc", "role"]


def page(client, **params):
    r = client.get("/proteins", params={"per_page": 50, **params})
    assert r.status_code == 200, r.text
    return r.json()


def order(payload):
    return [p["uniprot_id"] for p in payload["proteins"]]


# ── NULLs last, in both directions ───────────────────────────────────────────

def test_nulls_sort_last_descending(sort_db):
    with TestClient(app) as c:
        got = order(page(c, sort_by="disorder_mobidb_lite_dc", sort_order="desc"))
    assert got[-1] == "S00002", got


def test_nulls_sort_last_ascending_too(sort_db):
    """The contract is NULL-last "regardless of direction" — not NULL-first when
    the direction flips, which is what a plain ORDER BY would do."""
    with TestClient(app) as c:
        got = order(page(c, sort_by="disorder_mobidb_lite_dc", sort_order="asc"))
    assert got[-1] == "S00002", got


def test_null_gene_name_sorts_last(sort_db):
    with TestClient(app) as c:
        got = order(page(c, sort_by="gene_name", sort_order="asc"))
    assert got[-1] == "S00004", got


# ── ties ─────────────────────────────────────────────────────────────────────

def test_ties_break_on_uniprot_id(sort_db):
    """S00005 and S00006 are identical on every sortable column."""
    with TestClient(app) as c:
        for direction in ("asc", "desc"):
            got = order(page(c, sort_by="disorder_mobidb_lite_dc", sort_order=direction))
            assert got.index("S00005") < got.index("S00006"), (direction, got)


def test_every_sortable_column_produces_a_total_order(sort_db):
    """No sort may drop or duplicate a row, and repeating the same request must
    return the same order."""
    with TestClient(app) as c:
        for key in SORTABLE:
            for direction in ("asc", "desc"):
                first  = order(page(c, sort_by=key, sort_order=direction))
                second = order(page(c, sort_by=key, sort_order=direction))
                assert len(first) == 6, (key, direction, first)
                assert len(set(first)) == 6, (key, direction, first)
                assert first == second, (key, direction, first, second)


def test_reversing_the_direction_reverses_the_non_null_rows(sort_db):
    with TestClient(app) as c:
        asc  = order(page(c, sort_by="mlo_count", sort_order="asc"))
        desc = order(page(c, sort_by="mlo_count", sort_order="desc"))
    assert set(asc) == set(desc)
    assert asc[0] != desc[0], (asc, desc)


# ── invalid input ────────────────────────────────────────────────────────────

def test_an_unknown_sort_by_is_rejected_not_silently_ignored(sort_db):
    with TestClient(app) as c:
        r = c.get("/proteins", params={"sort_by": "no_such_column"})
    assert r.status_code == 422, f"accepted an unknown sort key: {r.status_code}"


def test_an_unknown_sort_order_is_rejected(sort_db):
    with TestClient(app) as c:
        r = c.get("/proteins", params={"sort_by": "gene_name", "sort_order": "sideways"})
    assert r.status_code == 422, f"accepted an unknown sort order: {r.status_code}"


def test_sort_by_cannot_smuggle_sql(sort_db):
    with TestClient(app) as c:
        r = c.get("/proteins", params={"sort_by": "gene_name; DROP TABLE proteins"})
    assert r.status_code == 422
    with TestClient(app) as c:
        assert page(c)["total"] == 6


# ── pagination ───────────────────────────────────────────────────────────────

def test_paging_covers_every_row_exactly_once(sort_db):
    """The property that matters: walking the pages must reconstruct the full
    set, with nothing missing and nothing repeated."""
    with TestClient(app) as c:
        seen, p = [], 1
        while True:
            payload = page(c, sort_by="gene_name", sort_order="asc", page=p, per_page=2)
            got = order(payload)
            if not got:
                break
            seen.extend(got)
            if p > 10:
                break
            p += 1
    assert len(seen) == 6, seen
    assert len(set(seen)) == 6, seen


def test_total_is_the_same_on_every_page(sort_db):
    with TestClient(app) as c:
        totals = [page(c, page=p, per_page=2)["total"] for p in (1, 2, 3)]
    assert totals == [6, 6, 6], totals


def test_a_page_past_the_end_is_empty_not_an_error(sort_db):
    with TestClient(app) as c:
        payload = page(c, page=99, per_page=20)
    assert payload["proteins"] == []
    assert payload["total"] == 6


def test_page_zero_is_rejected(sort_db):
    with TestClient(app) as c:
        r = c.get("/proteins", params={"page": 0})
    assert r.status_code == 422


def test_per_page_is_capped(sort_db):
    with TestClient(app) as c:
        r = c.get("/proteins", params={"per_page": 100000})
    assert r.status_code == 422, "an unbounded per_page lets one request read the table"
