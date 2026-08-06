import sqlite3
import sys
from pathlib import Path

REFACTOR_ROOT = Path(__file__).resolve().parent.parent
if str(REFACTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(REFACTOR_ROOT))
sys.path.insert(0, str(REFACTOR_ROOT / "scripts"))

from build_summary import _build_mlo_aggregates


def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE mlo_annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, uniprot_id TEXT,
            source_db TEXT, unified_mlo TEXT, unified_role TEXT,
            dataset_active INTEGER NOT NULL DEFAULT 1
        );
        INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active)
        VALUES ('ACTIVE1', 'PhaseDB', 'stress_granule', 'driver', 1);
        INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active)
        VALUES ('REGONLY', 'DrLLPS', 'nucleolus', NULL, 0);
    """)
    conn.commit()
    return conn


def test_build_mlo_aggregates_excludes_inactive_only_protein():
    conn = _make_conn()
    result = _build_mlo_aggregates(conn)
    conn.close()

    assert result["ACTIVE1"]["mlo_count"] == 1
    assert result["ACTIVE1"]["source_db_count"] == 1
    assert result["ACTIVE1"]["mlos"] == ["stress_granule"]

    # REGONLY's only row is dataset_active=0 -- it must not appear at all
    # (no GROUP BY group is produced once the WHERE clause excludes its
    # only row), not appear with stale mlo_count/source_db_count of 1.
    assert "REGONLY" not in result
