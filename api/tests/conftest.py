import asyncio
import sqlite3
import sys
from pathlib import Path

import aiosqlite
import pytest

API_ROOT = Path(__file__).resolve().parent.parent      # refactor/api/
REFACTOR_ROOT = API_ROOT.parent                          # refactor/
for p in (str(API_ROOT), str(REFACTOR_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import database as db_module

SCHEMA = """
CREATE TABLE proteins (
    uniprot_id TEXT PRIMARY KEY, gene_name TEXT, protein_name TEXT,
    organism TEXT, taxon_id INTEGER, length INTEGER, reviewed INTEGER,
    disorder_mobidb_lite_dc REAL, disorder_alphafold_dc REAL,
    sequence TEXT
);
CREATE TABLE mlo_vocabulary (
    unified_mlo TEXT PRIMARY KEY,
    spatial_location TEXT, spatial_location_evidence TEXT,
    taxonomic_scope TEXT, taxonomic_support_n INTEGER,
    physiological_state TEXT, cell_type_context TEXT
);
CREATE TABLE mlo_annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT, uniprot_id TEXT NOT NULL,
    source_db TEXT NOT NULL, source_mlo TEXT, unified_mlo TEXT NOT NULL,
    source_role TEXT, unified_role TEXT, evidence_type TEXT,
    dataset_active INTEGER NOT NULL DEFAULT 1, evidence TEXT
);
CREATE TABLE mlo_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, unified_mlo TEXT NOT NULL,
    source_db TEXT NOT NULL, source_name TEXT, definition TEXT
);
CREATE TABLE protein_summary (
    uniprot_id TEXT PRIMARY KEY, idr_regions TEXT, lcr_regions TEXT, domains TEXT,
    has_driver INTEGER, has_client INTEGER, source_db_count INTEGER,
    mlo_count INTEGER, mlos TEXT, source_dbs TEXT
);
CREATE TABLE ppi (
    id INTEGER PRIMARY KEY AUTOINCREMENT, uniprot_id_a TEXT, uniprot_id_b TEXT,
    in_db INTEGER DEFAULT 0, experimental_system TEXT, pubmed_id TEXT,
    source_version TEXT
);
CREATE TABLE sequence_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT, uniprot_id TEXT, feature_type TEXT,
    source TEXT, label TEXT, accession TEXT, start INTEGER, end INTEGER,
    score REAL, metadata TEXT
);
"""

# Fixture data, mirroring the project's standard test-protein convention:
# - P35637 (FUS): one ACTIVE driver annotation in stress_granule via PhaSepDB.
# - QREG01 (synthetic): ONLY a DrLLPS **Regulator** annotation, in nucleolus.
#   Until 2026-08-12 that row was dataset_active=0 and this protein modelled the
#   case that had to be invisible everywhere. R1-ACT-14 reversed it: regulator
#   rows are served, so QREG01 now models the opposite -- a protein whose only
#   annotation is a curator-assigned regulator call, which must be visible and
#   must bucket as 'regulator' rather than as a component of the organelle. The
#   real dataset has 501 of these.
# - QEXCL1 (synthetic): the dataset_active=0 case, which no real row occupies
#   any more. Kept because policy.active_annotation_clause() is still wired into
#   every query and an unexercised filter is an untested one.
FIXTURE = """
-- P35637 carries a sequence, QREG01 does not: the API must serve both, since
-- 289 of the 15694 real proteins have a NULL sequence.
INSERT INTO proteins (uniprot_id, gene_name, organism, length, sequence) VALUES
    ('P35637', 'FUS', 'Homo sapiens', 8, 'MASNDYTQ'),
    ('QREG01', 'REGTEST', 'Homo sapiens', 100, NULL);

INSERT INTO mlo_vocabulary (unified_mlo, spatial_location, spatial_location_evidence,
                            taxonomic_scope, taxonomic_support_n, physiological_state,
                            cell_type_context) VALUES
    ('stress_granule', 'cytoplasm', 'from_category', 'Metazoa', 2, 'stress_induced', NULL),
    ('nucleolus',      'nucleus',   'from_category', 'Metazoa', 1, 'constitutive',   NULL);

INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, source_role, unified_role, evidence_type, dataset_active) VALUES
    ('P35637', 'PhaSepDB', 'stress_granule', 'driver', 'driver', 'cellular_requirement', 1);

-- unified_role stays NULL and the row is served: what marks it as a regulator
-- claim is (evidence_type, source_role), which is what
-- policy.regulator_annotation_clause() reads.
INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, source_role, unified_role, evidence_type, dataset_active) VALUES
    ('QREG01', 'DrLLPS', 'nucleolus', 'Regulator', NULL, 'curator_assignment', 1);

INSERT INTO protein_summary (uniprot_id, has_driver, has_client, source_db_count, mlo_count, mlos, source_dbs) VALUES
    ('P35637', 1, 0, 1, 1, '["stress_granule"]', 'PhaSepDB'),
    ('QREG01', 0, 0, 1, 1, '["nucleolus"]', 'DrLLPS');

INSERT INTO mlo_vocabulary (unified_mlo, spatial_location, spatial_location_evidence,
                            taxonomic_scope, taxonomic_support_n, physiological_state,
                            cell_type_context) VALUES
    ('p_granule', 'cytoplasm', 'from_category', 'Metazoa', 4, 'constitutive', 'germline');

INSERT INTO proteins (uniprot_id, gene_name, organism, length) VALUES
    ('PCLIENT', 'CLIENTTEST', 'Homo sapiens', 200);
INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active) VALUES
    ('PCLIENT', 'PhaSepDB', 'p_granule', 'client', 1);
INSERT INTO protein_summary (uniprot_id, has_driver, has_client, source_db_count, mlo_count, mlos, source_dbs) VALUES
    ('PCLIENT', 0, 1, 1, 1, '["p_granule"]', 'PhaSepDB');

-- PNULLROLE: active mlo_annotations row with unified_role IS NULL (CD-CODE-
-- style annotation gap), in its own MLO ('condensate_x') to avoid colliding
-- with any existing test's counts on p_granule/stress_granule/nucleolus.
INSERT INTO mlo_vocabulary (unified_mlo, spatial_location, spatial_location_evidence,
                            taxonomic_scope, taxonomic_support_n, physiological_state,
                            cell_type_context) VALUES
    ('condensate_x', 'cytoplasm', 'from_category', 'Metazoa', 1, 'constitutive', NULL);

INSERT INTO proteins (uniprot_id, gene_name, organism, length) VALUES
    ('PNULLROLE', 'NULLROLETEST', 'Homo sapiens', 150);
INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, source_role, unified_role, evidence_type, dataset_active) VALUES
    ('PNULLROLE', 'CDCODE', 'condensate_x', 'NotInformed', NULL, 'membership_only', 1);
INSERT INTO protein_summary (uniprot_id, has_driver, has_client, source_db_count, mlo_count, mlos, source_dbs) VALUES
    ('PNULLROLE', 0, 0, 1, 1, '["condensate_x"]', 'CDCODE');

-- QEXCL1: the only dataset_active=0 row in the fixture, and deliberately not a
-- regulator -- source_role/evidence_type are left NULL so nothing reads it as
-- one. It stands in for whatever future exclusion policy.py argues for, and
-- keeps every "inactive rows are filtered" test pointed at a real subject now
-- that the regulator rows have left that role. Its own MLO, so it cannot shift
-- another test's counts.
INSERT INTO mlo_vocabulary (unified_mlo, spatial_location, spatial_location_evidence,
                            taxonomic_scope, taxonomic_support_n, physiological_state,
                            cell_type_context) VALUES
    ('condensate_excluded', 'cytoplasm', 'hand_assigned', 'Metazoa', 1, 'constitutive', NULL);

INSERT INTO proteins (uniprot_id, gene_name, organism, length) VALUES
    ('QEXCL1', 'EXCLTEST', 'Homo sapiens', 120);
INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, source_role, unified_role, evidence_type, dataset_active) VALUES
    ('QEXCL1', 'DrLLPS', 'condensate_excluded', NULL, NULL, 'curator_assignment', 0);
INSERT INTO protein_summary (uniprot_id, has_driver, has_client, source_db_count, mlo_count, mlos, source_dbs) VALUES
    ('QEXCL1', 0, 0, 0, 0, NULL, NULL);
"""


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.executescript(FIXTURE)
    conn.commit()
    conn.close()

    monkeypatch.setattr(db_module, "DB_PATH", db_path)

    async def _open():
        db_module._db = await aiosqlite.connect(db_path)
        db_module._db.row_factory = aiosqlite.Row

    async def _close():
        await db_module._db.close()

    asyncio.run(_open())
    yield db_path
    asyncio.run(_close())
    db_module._db = None
