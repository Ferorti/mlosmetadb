"""Purpose-built corpus for characterizing search semantics.

Kept apart from conftest.py's FIXTURE on purpose: that one is tuned to exact
counts asserted by the role/MLO tests, so growing it would break them for
reasons unrelated to what they check. Every protein here exists to isolate one
question — which field matched, how case is handled, what a wildcard in user
input does — so a failure names the defect by itself.
"""

import asyncio
import sqlite3

import aiosqlite
import pytest

import database as db_module
from tests.conftest import SCHEMA

# Each row isolates exactly one matching path for the query "kinase" -- via
# gene_name or uniprot_id, the only two columns search matches on -- plus the
# edge cases that no realistic corpus would contain often enough to notice.
SEARCH_FIXTURE = """
INSERT INTO proteins (uniprot_id, gene_name, protein_name, organism, taxon_id, length, reviewed) VALUES
    -- matches "kinase" ONLY through gene_name
    ('P00001', 'KINASE1', 'Uncharacterized protein',            'Homo sapiens', 9606, 100, 1),
    -- matches "kinase" ONLY through protein_name (the case the field select broke)
    ('P00002', 'STK33',   'Serine/threonine-protein kinase 33', 'Homo sapiens', 9606, 200, 1),
    -- matches "kinase" ONLY through uniprot_id
    ('KINASE9', 'ABC1',   'Unrelated protein',                  'Mus musculus', 10090, 300, 0),
    -- mixed case, to pin down case-insensitivity
    ('P00004', 'KiNaSe4', 'MiXeD CaSe KINASE protein',          'Homo sapiens', 9606, 400, 1),
    -- literal SQL LIKE metacharacters in the data
    ('P00005', 'A_B',     'Underscore gene protein',            'Homo sapiens', 9606, 500, 1),
    ('P00006', 'AXB',     'Decoy for the underscore test',      'Homo sapiens', 9606, 600, 1),
    ('P00007', 'C%D',     'Percent gene protein',               'Homo sapiens', 9606, 700, 1),
    -- NULL gene_name and protein_name: must not crash, must not match
    ('P00008', NULL,      NULL,                                 'Homo sapiens', 9606, 800, 1),
    -- exact mode must be able to return more than one row: same gene_name,
    -- different organism, neither one deduplicated away
    ('P00011', 'DUPGENE', 'Duplicate gene protein one',         'Homo sapiens', 9606, 100, 1),
    ('P00012', 'DUPGENE', 'Duplicate gene protein two',         'Mus musculus', 10090, 100, 1);

INSERT INTO protein_summary (uniprot_id, has_driver, has_client, source_db_count, mlo_count, mlos, source_dbs) VALUES
    ('P00001', 1, 0, 2, 2, '["stress_granule","nucleolus"]', 'PhaSepDB,DrLLPS'),
    ('P00002', 0, 1, 1, 1, '["stress_granule"]',             'PhaSepDB'),
    ('KINASE9',0, 0, 1, 0, NULL,                             'CDCODE'),
    ('P00004', 1, 0, 1, 1, '["nucleolus"]',                  'PhaSepDB'),
    ('P00005', 0, 0, 1, 0, NULL,                             'PhaSepDB'),
    ('P00006', 0, 0, 1, 0, NULL,                             'PhaSepDB'),
    ('P00007', 0, 0, 1, 0, NULL,                             'PhaSepDB'),
    ('P00008', 0, 0, 1, 0, NULL,                             'PhaSepDB'),
    ('P00011', 0, 0, 1, 0, NULL,                             'PhaSepDB'),
    ('P00012', 0, 0, 1, 0, NULL,                             'PhaSepDB');

INSERT INTO mlo_vocabulary (unified_mlo, spatial_location, spatial_location_evidence,
                            taxonomic_scope, taxonomic_support_n, physiological_state,
                            cell_type_context) VALUES
    ('stress_granule', 'cytoplasm', 'from_category', 'Metazoa', 3, 'stress_induced', NULL),
    ('nucleolus',      'nucleus',   'from_category', 'Metazoa', 2, 'constitutive',   NULL),
    ('p_granule',      'cytoplasm', 'from_category', 'Metazoa', 1, 'constitutive',   'germline');

INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active) VALUES
    ('P00001', 'PhaSepDB', 'stress_granule', 'driver', 1),
    ('P00001', 'DrLLPS',  'nucleolus',      'driver', 1),
    ('P00002', 'PhaSepDB', 'stress_granule', 'client', 1),
    ('P00004', 'PhaSepDB', 'nucleolus',      'driver', 1),
    -- inactive dataset: must be invisible through every endpoint
    ('P00006', 'PhaSepDB', 'p_granule',      'driver', 0);
"""

# Sorting corpus: NULLs and ties are where the two sort implementations can
# silently diverge, so they are the point of every row here.
SORT_FIXTURE = """
INSERT INTO proteins (uniprot_id, gene_name, protein_name, organism, taxon_id, length, reviewed,
                      disorder_mobidb_lite_dc) VALUES
    ('S00001', 'ALPHA', 'Sortable one',   'Homo sapiens', 9606, 100, 1, 0.90),
    ('S00002', 'BETA',  'Sortable two',   'Homo sapiens', 9606, 100, 1, NULL),
    ('S00003', 'GAMMA', 'Sortable three', 'Homo sapiens', 9606, 100, 1, 0.10),
    ('S00004', NULL,    'Sortable four',  'Homo sapiens', 9606, 100, 1, 0.50),
    -- S00005/S00006 tie on every sortable column: only uniprot_id can break it
    ('S00005', 'DELTA', 'Sortable five',  'Homo sapiens', 9606, 100, 1, 0.50),
    ('S00006', 'DELTA', 'Sortable six',   'Homo sapiens', 9606, 100, 1, 0.50);

INSERT INTO protein_summary (uniprot_id, has_driver, has_client, source_db_count, mlo_count, mlos, source_dbs) VALUES
    ('S00001', 1, 0, 3, 5, '["stress_granule"]', 'PhaSepDB'),
    ('S00002', 0, 1, 1, 1, '["nucleolus"]',      'PhaSepDB'),
    ('S00003', 0, 0, 2, 3, '["nucleolus"]',      'PhaSepDB'),
    ('S00004', 1, 0, 2, 2, '["nucleolus"]',      'PhaSepDB'),
    ('S00005', 0, 0, 2, 2, '["nucleolus"]',      'PhaSepDB'),
    ('S00006', 0, 0, 2, 2, '["nucleolus"]',      'PhaSepDB');

INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active) VALUES
    ('S00001', 'PhaSepDB', 'stress_granule', 'driver', 1),
    ('S00002', 'PhaSepDB', 'nucleolus',      'client', 1),
    ('S00003', 'PhaSepDB', 'nucleolus',      NULL,     1),
    ('S00004', 'PhaSepDB', 'nucleolus',      'driver', 1),
    ('S00005', 'PhaSepDB', 'nucleolus',      NULL,     1),
    ('S00006', 'PhaSepDB', 'nucleolus',      NULL,     1);
"""


def _build(tmp_path, monkeypatch, *scripts):
    db_path = str(tmp_path / "search.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    for s in scripts:
        conn.executescript(s)
    conn.commit()
    conn.close()

    monkeypatch.setattr(db_module, "DB_PATH", db_path)

    async def _open():
        db_module._db = await aiosqlite.connect(db_path)
        db_module._db.row_factory = aiosqlite.Row

    asyncio.run(_open())
    return db_path


def _teardown():
    async def _close():
        await db_module._db.close()

    asyncio.run(_close())
    db_module._db = None


@pytest.fixture
def search_db(tmp_path, monkeypatch):
    path = _build(tmp_path, monkeypatch, SEARCH_FIXTURE)
    yield path
    _teardown()


@pytest.fixture
def sort_db(tmp_path, monkeypatch):
    path = _build(tmp_path, monkeypatch, SORT_FIXTURE)
    yield path
    _teardown()
