from fastapi.testclient import TestClient

from main import app


def test_mlo_detail_proteins_show_raw_role_not_component(test_db):
    with TestClient(app) as client:
        r = client.get("/mlo/p_granule")
    assert r.status_code == 200
    items = r.json()["proteins"]["items"]
    assert len(items) == 1
    assert items[0]["unified_role"] == "client"
    assert items[0]["unified_role"] != "component"
