import sqlite3

from fastapi.testclient import TestClient

from main import app
from routers.proteins import _build_export_record, _records_to_tsv, _EXPORT_BASIC_FIELDS, _EXPORT_FULL_FIELDS


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


def test_build_export_record_basic_omits_annotation_fields():
    row = {
        "uniprot_id": "P1", "gene_name": "G1", "protein_name": "N1", "organism": "Homo sapiens",
        "sequence_length": 100, "reviewed": 1, "has_driver": 1, "has_client": 0,
        "source_dbs": "PhaseDB,CDCODE", "mlo_count": 2, "mlos": '["a","b"]',
    }
    record = _build_export_record(row, "basic")
    assert set(record.keys()) == set(_EXPORT_BASIC_FIELDS)


def test_build_export_record_full_parses_json_lists():
    row = {
        "uniprot_id": "P1", "gene_name": "G1", "protein_name": "N1", "organism": "Homo sapiens",
        "sequence_length": 100, "reviewed": 1, "has_driver": 1, "has_client": 0,
        "source_dbs": "PhaseDB,CDCODE", "mlo_count": 2, "mlos": '["a","b"]',
    }
    record = _build_export_record(row, "full")
    assert set(record.keys()) == set(_EXPORT_FULL_FIELDS)
    assert record["mlos"] == ["a", "b"]
    assert record["source_dbs"] == ["PhaseDB", "CDCODE"]
    assert record["has_driver"] is True


def test_build_export_record_full_keeps_sequence_features_as_raw_json_text():
    row = {
        "uniprot_id": "P1", "gene_name": "G1", "protein_name": "N1", "organism": "Homo sapiens",
        "sequence_length": 100, "reviewed": 1, "has_driver": 1, "has_client": 0,
        "source_dbs": "PhaseDB,CDCODE", "mlo_count": 2, "mlos": '["a","b"]',
        "idr_regions": '[{"start": 1, "end": 20}]', "lcr_regions": None,
        "domains": '[{"label": "KH domain"}]',
    }
    record = _build_export_record(row, "full")
    assert record["idr_regions"] == '[{"start": 1, "end": 20}]'
    assert record["lcr_regions"] is None
    assert record["domains"] == '[{"label": "KH domain"}]'
    assert record["role"] == "driver"


def test_records_to_tsv_joins_lists_with_semicolon():
    records = [{"uniprot_id": "P1", "mlos": ["a", "b"], "source_dbs": ["PhaseDB", "CDCODE"]}]
    tsv = _records_to_tsv(records, ["uniprot_id", "mlos", "source_dbs"])
    lines = tsv.strip().split("\n")
    assert lines[0] == "uniprot_id\tmlos\tsource_dbs"
    assert lines[1] == "P1\ta;b\tPhaseDB;CDCODE"


def test_records_to_tsv_passes_through_raw_json_text_unmodified():
    records = [{"uniprot_id": "P1", "idr_regions": '[{"start": 1, "end": 20}]'}]
    tsv = _records_to_tsv(records, ["uniprot_id", "idr_regions"])
    lines = tsv.strip().split("\n")
    assert lines[1] == 'P1\t[{"start": 1, "end": 20}]'


def test_records_to_tsv_none_becomes_empty_string():
    tsv = _records_to_tsv([{"uniprot_id": "P1", "gene_name": None}], ["uniprot_id", "gene_name"])
    lines = tsv.rstrip("\n").split("\n")
    assert lines[1] == "P1\t"


def test_records_to_tsv_header_present_with_zero_rows():
    tsv = _records_to_tsv([], ["uniprot_id", "gene_name"])
    assert tsv.strip() == "uniprot_id\tgene_name"


def test_export_endpoint_json_default_returns_all_proteins(test_db):
    with TestClient(app) as client:
        r = client.get("/proteins/export", params={"format": "json"})
    assert r.status_code == 200
    ids = {row["uniprot_id"] for row in r.json()}
    assert ids == {"P35637", "PCLIENT", "PNULLROLE", "QREG01"}


def test_export_endpoint_source_db_filter_excludes_inactive_regulator(test_db):
    with TestClient(app) as client:
        r = client.get("/proteins/export", params={"source_db": ["DrLLPS"], "format": "json"})
    assert r.status_code == 200
    assert r.json() == []


def test_export_endpoint_tsv_has_attachment_header_and_basic_columns(test_db):
    with TestClient(app) as client:
        r = client.get("/proteins/export", params={"format": "tsv", "fields": "basic"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/tab-separated-values")
    assert 'attachment; filename="mlosmetadb_export.tsv"' in r.headers["content-disposition"]
    header = r.text.split("\n")[0].split("\t")
    assert header == _EXPORT_BASIC_FIELDS


def test_export_endpoint_invalid_format_returns_422(test_db):
    with TestClient(app) as client:
        r = client.get("/proteins/export", params={"format": "xml"})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_parameter"


def test_export_endpoint_invalid_fields_returns_422(test_db):
    with TestClient(app) as client:
        r = client.get("/proteins/export", params={"fields": "everything"})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_parameter"


def test_citation_check_combines_phasedb_and_phasepdb_into_one_entry(test_db):
    conn = sqlite3.connect(test_db)
    conn.execute(
        "INSERT INTO mlo_vocabulary (unified_mlo, category) VALUES ('condensate_y', 'Cytoplasmic')"
    )
    conn.execute(
        "INSERT INTO proteins (uniprot_id, gene_name, organism, length) VALUES "
        "('PPDB01', 'PPDBTEST', 'Homo sapiens', 120)"
    )
    conn.execute(
        "INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active) "
        "VALUES ('PPDB01', 'PhasePDB', 'condensate_y', 'driver', 1)"
    )
    conn.commit()
    conn.close()

    with TestClient(app) as client:
        r = client.post("/proteins/citations", json={"uniprot_ids": ["P35637", "PPDB01", "PCLIENT"]})
    assert r.status_code == 200
    # P35637 and PCLIENT are tagged 'PhaseDB', PPDB01 is tagged 'PhasePDB' --
    # both must fold into the single 'PhaSepDB' display name.
    assert r.json()["by_source"] == {"PhaSepDB": 3}


def test_citation_check_ignores_unmatched_uniprot_ids(test_db):
    with TestClient(app) as client:
        r = client.post("/proteins/citations", json={"uniprot_ids": ["P35637", "NOTAREALID"]})
    assert r.status_code == 200
    assert r.json()["by_source"] == {"PhaSepDB": 1}


def test_citation_check_empty_list_returns_422(test_db):
    with TestClient(app) as client:
        r = client.post("/proteins/citations", json={"uniprot_ids": []})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_parameter"


def test_citation_check_too_many_ids_returns_422(test_db):
    ids = [f"P{i:05d}" for i in range(501)]
    with TestClient(app) as client:
        r = client.post("/proteins/citations", json={"uniprot_ids": ids})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_parameter"


def test_protein_detail_serves_the_sequence(test_db):
    with TestClient(app) as client:
        r = client.get("/protein/P35637")
    assert r.status_code == 200
    body = r.json()
    assert body["sequence"] == "MASNDYTQ"
    assert body["sequence_length"] == len(body["sequence"])


def test_protein_detail_tolerates_a_missing_sequence(test_db):
    with TestClient(app) as client:
        r = client.get("/protein/QREG01")
    assert r.status_code == 200
    assert r.json()["sequence"] is None
