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
    disorder_mobidb_lite_dc REAL, disorder_alphafold_dc REAL
);
CREATE TABLE mlo_vocabulary (unified_mlo TEXT PRIMARY KEY, category TEXT);
CREATE TABLE mlo_annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT, uniprot_id TEXT NOT NULL,
    source_db TEXT NOT NULL, source_mlo TEXT, unified_mlo TEXT NOT NULL,
    source_role TEXT, unified_role TEXT,
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
# - P35637 (FUS): one ACTIVE driver annotation in stress_granule via PhaseDB.
# - QREG01 (synthetic): ONLY an INACTIVE DrLLPS-Regulator annotation in
#   nucleolus -- the case that must be invisible everywhere after the fix.
FIXTURE = """
INSERT INTO proteins (uniprot_id, gene_name, organism, length) VALUES
    ('P35637', 'FUS', 'Homo sapiens', 526),
    ('QREG01', 'REGTEST', 'Homo sapiens', 100);

INSERT INTO mlo_vocabulary (unified_mlo, category) VALUES
    ('stress_granule', 'Cytoplasmic'),
    ('nucleolus', 'Nuclear');

INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active) VALUES
    ('P35637', 'PhaseDB', 'stress_granule', 'driver', 1);

INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active) VALUES
    ('QREG01', 'DrLLPS', 'nucleolus', NULL, 0);

INSERT INTO protein_summary (uniprot_id, has_driver, has_client, source_db_count, mlo_count, mlos, source_dbs) VALUES
    ('P35637', 1, 0, 1, 1, '["stress_granule"]', 'PhaseDB'),
    ('QREG01', 0, 0, 0, 0, NULL, NULL);

INSERT INTO mlo_vocabulary (unified_mlo, category) VALUES
    ('p_granule', 'Cytoplasmic');

INSERT INTO proteins (uniprot_id, gene_name, organism, length) VALUES
    ('PCLIENT', 'CLIENTTEST', 'Homo sapiens', 200);
INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active) VALUES
    ('PCLIENT', 'PhaseDB', 'p_granule', 'client', 1);
INSERT INTO protein_summary (uniprot_id, has_driver, has_client, source_db_count, mlo_count, mlos, source_dbs) VALUES
    ('PCLIENT', 0, 1, 1, 1, '["p_granule"]', 'PhaseDB');

-- PNULLROLE: active mlo_annotations row with unified_role IS NULL (CD-CODE-
-- style annotation gap), in its own MLO ('condensate_x') to avoid colliding
-- with any existing test's counts on p_granule/stress_granule/nucleolus.
INSERT INTO mlo_vocabulary (unified_mlo, category) VALUES
    ('condensate_x', 'Cytoplasmic');

INSERT INTO proteins (uniprot_id, gene_name, organism, length) VALUES
    ('PNULLROLE', 'NULLROLETEST', 'Homo sapiens', 150);
INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active) VALUES
    ('PNULLROLE', 'CDCODE', 'condensate_x', NULL, 1);
INSERT INTO protein_summary (uniprot_id, has_driver, has_client, source_db_count, mlo_count, mlos, source_dbs) VALUES
    ('PNULLROLE', 0, 0, 1, 1, '["condensate_x"]', 'CDCODE');
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
