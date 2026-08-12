import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from queries import unification_queries as uq


def test_load_unification_stats_reads_and_parses_json(tmp_path, monkeypatch):
    monkeypatch.setattr(uq, "EXPORTS_DIR", tmp_path)
    (tmp_path / "unification_stats.json").write_text(json.dumps({"meta": {"n_annotations": 42}}))

    result = uq.load_unification_stats()

    assert result == {"meta": {"n_annotations": 42}}


def test_load_unification_stats_returns_none_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(uq, "EXPORTS_DIR", tmp_path)

    assert uq.load_unification_stats() is None


def test_load_unification_stats_returns_none_on_malformed_json(tmp_path, monkeypatch):
    monkeypatch.setattr(uq, "EXPORTS_DIR", tmp_path)
    (tmp_path / "unification_stats.json").write_text("{not valid json")

    assert uq.load_unification_stats() is None


def test_discrepant_pairs_csv_path_points_under_exports_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(uq, "EXPORTS_DIR", tmp_path)
    assert uq.discrepant_pairs_csv_path() == tmp_path / "discrepant_pairs.csv"


def test_mlo_term_mapping_csv_path_points_under_exports_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(uq, "EXPORTS_DIR", tmp_path)
    assert uq.mlo_term_mapping_csv_path() == tmp_path / "mlo_term_mapping.csv"
