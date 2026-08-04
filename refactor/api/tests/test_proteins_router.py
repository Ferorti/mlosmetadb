from fastapi.testclient import TestClient

from main import app


def test_protein_detail_shows_raw_driver_role(test_db):
    with TestClient(app) as client:
        r = client.get("/protein/P35637")
    assert r.status_code == 200
    anns = r.json()["mlo_annotations"]
    assert len(anns) == 1
    assert anns[0]["unified_role"] == "driver"
    assert anns[0]["unified_role"] != "component"


def test_protein_detail_shows_raw_client_role_not_component(test_db):
    with TestClient(app) as client:
        r = client.get("/protein/PCLIENT")
    assert r.status_code == 200
    anns = r.json()["mlo_annotations"]
    assert anns[0]["unified_role"] == "client"
