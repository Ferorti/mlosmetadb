from fastapi.testclient import TestClient

from main import app


def test_single_character_query_is_accepted(test_db):
    """A one-letter search is a legitimate broad search, not a malformed request.

    The endpoint caps its own result set at 50 rows, so the only thing the old
    two-character floor bought was an error where results were expected.
    """
    with TestClient(app) as client:
        r = client.get("/search", params={"q": "F"})
    assert r.status_code == 200
    genes = [p["gene_name"] for p in r.json()["proteins"]]
    assert "FUS" in genes


def test_empty_query_is_still_rejected(test_db):
    with TestClient(app) as client:
        r = client.get("/search", params={"q": ""})
    assert r.status_code == 422


def test_validation_errors_do_not_leak_server_paths(test_db):
    """str() of a pydantic ValidationError embeds the raising source file and
    line. Putting it in a user-facing field publishes the server's filesystem
    layout to anyone who can type a bad query."""
    with TestClient(app) as client:
        r = client.get("/search", params={"q": ""})
    message = r.json()["message"]
    assert "File \"" not in message
    assert ".py" not in message
    assert "/api/routers" not in message


def test_validation_errors_name_the_offending_parameter(test_db):
    with TestClient(app) as client:
        r = client.get("/search", params={"q": ""})
    body = r.json()
    assert body["error"] == "invalid_parameter"
    assert "q" in body["message"]


def test_mlo_search_matches_names_written_with_spaces(test_db):
    """MLO names are stored slugged ('stress_granule') but people type them the
    way they read ('stress granule') — and that spelling is literally what the
    search box suggests as an example."""
    with TestClient(app) as client:
        r = client.get("/search", params={"q": "stress granule"})
    assert r.status_code == 200
    assert "stress_granule" in [m["unified_mlo"] for m in r.json()["mlos"]]


def test_mlo_search_still_matches_the_raw_slug(test_db):
    with TestClient(app) as client:
        r = client.get("/search", params={"q": "stress_granule"})
    assert r.status_code == 200
    assert "stress_granule" in [m["unified_mlo"] for m in r.json()["mlos"]]
