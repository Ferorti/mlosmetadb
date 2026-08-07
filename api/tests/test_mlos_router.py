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


# ── source names (aliases used by the source databases) ─────────────────────

def test_mlos_expose_source_names(test_db):
    """A name a source database uses but the unified vocabulary does not, e.g.
    "GW-body" for p_body, is the only way those organelles are findable."""
    with TestClient(app) as client:
        r = client.get("/mlos")
    assert r.status_code == 200
    by_mlo = {m["unified_mlo"]: m for m in r.json()["mlos"]}
    assert "source_names" in next(iter(by_mlo.values()))


def test_source_names_exclude_the_unified_name(test_db):
    with TestClient(app) as client:
        r = client.get("/mlos")
    for m in r.json()["mlos"]:
        unified = m["unified_mlo"].replace("_", " ").lower()
        assert unified not in [n.lower() for n in m["source_names"]], m["unified_mlo"]


def test_source_names_have_no_casing_duplicates(test_db):
    with TestClient(app) as client:
        r = client.get("/mlos")
    for m in r.json()["mlos"]:
        lowered = [n.lower() for n in m["source_names"]]
        assert len(lowered) == len(set(lowered)), m
