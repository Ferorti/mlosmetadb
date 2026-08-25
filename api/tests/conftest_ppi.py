"""Purpose-built corpus for characterizing the PPI query path
(docs/issues/003-ppi-endpoint-role-and-evidence-bugs.md).

Kept apart from conftest.py's FIXTURE on purpose, same reasoning as
conftest_search.py: that fixture is tuned to exact global counts asserted by
the /stats, facets and export tests, so adding a protein with its own
mlo_annotations rows here would shift those counts for reasons unrelated to
what they check.
"""

import asyncio
import sqlite3

import aiosqlite
import pytest

import database as db_module
from tests.conftest import SCHEMA

# P35637: drives stress_granule, has no annotation in p_granule -- the hub.
#   Also carries a self-interaction row (docs/issues/004) to check it's
#   excluded from its own partner list.
# PCLIENT: client (non-driver) of p_granule only, has_driver=0 globally.
# PSCOPED: drives stress_granule AND is a client of p_granule -- has_driver=1
#   globally, but does NOT drive p_granule specifically. This is the case
#   that exposes finding 2: role=driver&mlo=p_granule must exclude it even
#   though "has_driver=1" and "has *some* annotation in p_granule" are both
#   independently true.
# PREG01: curator-assigned DrLLPS Regulator of nucleolus, never a driver
#   anywhere -- the mutually-exclusive "regulator, never a driver" bucket
#   role=regulator must match (docs/issues/004).
# PREV01: in-dataset partner recorded with the hub in uniprot_id_b, not
#   uniprot_id_a -- parse_biogrid.py only swaps the not-in-dataset side into
#   uniprot_id_a (scripts/CLAUDE.md); when BOTH interactors are already in
#   `proteins`, whichever BioGRID called "Interactor A" keeps that column, so
#   P35637 can legitimately end up as uniprot_id_b for a real partner. Exists
#   to catch queries anchored only to uniprot_id_a = hub (docs/issues/006).
PPI_FIXTURE = """
INSERT INTO proteins (uniprot_id, gene_name, organism, length) VALUES
    ('P35637',  'FUS',        'Homo sapiens', 8),
    ('PCLIENT', 'CLIENTTEST', 'Homo sapiens', 200),
    ('PSCOPED', 'SCOPEDTEST', 'Homo sapiens', 180),
    ('PREG01',  'REGTEST',    'Homo sapiens', 220),
    ('PREV01',  'REVTEST',    'Homo sapiens', 150);

INSERT INTO mlo_vocabulary (unified_mlo, spatial_location, spatial_location_evidence,
                            taxonomic_scope, taxonomic_support_n, physiological_state,
                            cell_type_context) VALUES
    ('stress_granule', 'cytoplasm', 'from_category', 'Metazoa', 2, 'stress_induced', NULL),
    ('p_granule',      'cytoplasm', 'from_category', 'Metazoa', 4, 'constitutive',   'germline'),
    ('nucleolus',      'nucleus',   'from_category', 'Metazoa', 1, 'constitutive',   NULL);

INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, source_role, unified_role, evidence_type, dataset_active) VALUES
    ('P35637',  'PhaSepDB', 'stress_granule', NULL,        'driver', NULL,                  1),
    ('PCLIENT', 'PhaSepDB', 'p_granule',      NULL,        'client', NULL,                  1),
    ('PSCOPED', 'PhaSepDB', 'stress_granule', NULL,        'driver', NULL,                  1),
    ('PSCOPED', 'PhaSepDB', 'p_granule',      NULL,        'client', NULL,                  1),
    ('PREG01',  'DrLLPS',   'nucleolus',      'Regulator', NULL,     'curator_assignment',  1);

INSERT INTO protein_summary (uniprot_id, has_driver, has_client, source_db_count, mlo_count, mlos, source_dbs) VALUES
    ('P35637',  1, 0, 1, 1, '["stress_granule"]',              'PhaSepDB'),
    ('PCLIENT', 0, 1, 1, 1, '["p_granule"]',                   'PhaSepDB'),
    ('PSCOPED', 1, 1, 1, 2, '["stress_granule", "p_granule"]', 'PhaSepDB'),
    ('PREG01',  0, 0, 1, 1, '["nucleolus"]',                   'DrLLPS'),
    ('PREV01',  0, 0, 0, 0, '[]',                               '');

-- P35637 (hub) <-> PCLIENT carries TWO independent BioGRID-style evidence
-- rows (different experimental_system/pubmed_id) -- the shape that exposed
-- finding 1 (get_ppi_page's bare GROUP BY silently kept only one of them).
-- P35637 <-> PSCOPED carries one row and exists for finding 2's test above.
-- P35637 <-> PREG01 exists for the regulator-role tests below.
-- P35637 <-> P35637 is the self-interaction row docs/issues/004 is about.
-- PREV01 <-> P35637 is stored with the HUB in uniprot_id_b -- docs/issues/006.
INSERT INTO ppi (uniprot_id_a, uniprot_id_b, in_db, experimental_system, pubmed_id, source_version) VALUES
    ('P35637', 'PCLIENT', 1, 'Affinity Capture-MS',    '11111111', 'BIOGRID-TEST'),
    ('P35637', 'PCLIENT', 1, 'Two-hybrid',              '22222222', 'BIOGRID-TEST'),
    ('P35637', 'PSCOPED', 1, 'Affinity Capture-MS',     '33333333', 'BIOGRID-TEST'),
    ('P35637', 'PREG01',  1, 'Affinity Capture-Western','44444444', 'BIOGRID-TEST'),
    ('P35637', 'P35637',  1, 'Co-crystal Structure',    '55555555', 'BIOGRID-TEST'),
    ('PREV01', 'P35637',  1, 'Affinity Capture-MS',     '66666666', 'BIOGRID-TEST');
"""


@pytest.fixture
def ppi_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "ppi.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.executescript(PPI_FIXTURE)
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
