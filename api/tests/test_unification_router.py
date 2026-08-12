import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from fastapi.testclient import TestClient

from queries import unification_queries as uq
from main import app


def test_unification_stats_happy_path(tmp_path, monkeypatch, test_db):
    monkeypatch.setattr(uq, "EXPORTS_DIR", tmp_path)
    payload = {"meta": {"n_annotations": 42}, "summary": {"n_annotations": 42}}
    (tmp_path / "unification_stats.json").write_text(json.dumps(payload))

    with TestClient(app) as client:
        r = client.get("/unification/stats")

    assert r.status_code == 200
    assert r.json() == payload


def test_unification_stats_503_when_artifact_missing(tmp_path, monkeypatch, test_db):
    monkeypatch.setattr(uq, "EXPORTS_DIR", tmp_path)

    with TestClient(app) as client:
        r = client.get("/unification/stats")

    assert r.status_code == 503
    assert r.json()["error"] == "unification_stats_unavailable"


def test_discrepant_pairs_export_happy_path(tmp_path, monkeypatch, test_db):
    monkeypatch.setattr(uq, "EXPORTS_DIR", tmp_path)
    (tmp_path / "discrepant_pairs.csv").write_text("uniprot_id,unified_mlo\nP1,stress_granule\n")

    with TestClient(app) as client:
        r = client.get("/unification/discrepant-pairs/export")

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "P1,stress_granule" in r.text


def test_discrepant_pairs_export_503_when_missing(tmp_path, monkeypatch, test_db):
    monkeypatch.setattr(uq, "EXPORTS_DIR", tmp_path)

    with TestClient(app) as client:
        r = client.get("/unification/discrepant-pairs/export")

    assert r.status_code == 503
    assert r.json()["error"] == "unification_export_unavailable"


def test_mlo_term_mapping_export_happy_path(tmp_path, monkeypatch, test_db):
    monkeypatch.setattr(uq, "EXPORTS_DIR", tmp_path)
    (tmp_path / "mlo_term_mapping.csv").write_text("unified_mlo,source_db\nstress_granule,PhaSepDB\n")

    with TestClient(app) as client:
        r = client.get("/unification/mlo-term-mapping/export")

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "stress_granule,PhaSepDB" in r.text


def test_mlo_term_mapping_export_503_when_missing(tmp_path, monkeypatch, test_db):
    monkeypatch.setattr(uq, "EXPORTS_DIR", tmp_path)

    with TestClient(app) as client:
        r = client.get("/unification/mlo-term-mapping/export")

    assert r.status_code == 503
    assert r.json()["error"] == "unification_export_unavailable"
