import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from fastapi.testclient import TestClient

from queries import unification_queries as uq
from main import app


def test_unification_stats_happy_path(tmp_path, monkeypatch):
    monkeypatch.setattr(uq, "EXPORTS_DIR", tmp_path)
    payload = {"meta": {"n_annotations": 42}, "summary": {"n_annotations": 42}}
    (tmp_path / "unification_stats.json").write_text(json.dumps(payload))

    with TestClient(app) as client:
        r = client.get("/unification/stats")

    assert r.status_code == 200
    assert r.json() == payload


def test_unification_stats_503_when_artifact_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(uq, "EXPORTS_DIR", tmp_path)

    with TestClient(app) as client:
        r = client.get("/unification/stats")

    assert r.status_code == 503
    assert r.json()["error"] == "unification_stats_unavailable"
