"""Tests for scripts/build_db.py's re-runnability.

`database/CLAUDE.md` documents regeneration as `integrate.py` → `build_db.py` →
`build_summary.py`, run over the existing DB. Until 2026-08-08 the second and
third of those appended instead of replacing, so running the documented
sequence twice silently doubled `mlo_annotations` and `mlo_definitions`. These
tests pin the fix: re-running replaces the tables build_db.py owns, and only
those -- the fetched data in `proteins` and the enrichment tables has to
survive, or a rebuild would cost days of API fetching.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_db

MAPPING_CSV = """Nombre Original,Nombre Sugerido,Categoria,Justificacion Biologica
Nucleolus,nucleolus,Nuclear,test entry
Stress granule,stress_granule,Citoplasma,test entry
"""

DEFINITIONS_CSV = """unified_mlo,source_db,source_name,definition
nucleolus,PhaSepDB,Nucleolus,The largest nuclear body.
"""

TSV_COLUMNS = ("uniprot_id\tsource_db\tsource_mlo\tunified_mlo\tsource_role\t"
               "unified_role\tdataset_active\tevidence\torganism\n")
TSV_ROWS = (
    "P35637\tPhaSepDB\tNucleolus\tnucleolus\tdriver\tdriver\t1\t111\tHomo sapiens\n"
    "P35637\tPhaSepDB\tNucleolus\tnucleolus\tclient\tclient\t1\t222\tHomo sapiens\n"
    "Q00001\tDrLLPS\tStress granule\tstress_granule\tClient\tclient\t1\t333\tHomo sapiens\n"
    # dropped on load: no coverage in the mapping
    "Q00002\tDrLLPS\tSomething\tunmapped\tClient\tclient\t1\t444\tHomo sapiens\n"
)


@pytest.fixture
def build(tmp_path, monkeypatch):
    """Point build_db.py at a temp tree and return a runnable main()."""
    db_dir = tmp_path / "database"
    (db_dir / "mappings").mkdir(parents=True)
    (db_dir / "final").mkdir()
    (db_dir / "mappings" / "mlo_mapping.csv").write_text(MAPPING_CSV)
    (db_dir / "final" / "mlo_definitions.csv").write_text(DEFINITIONS_CSV)
    (db_dir / "mlosmetadb.tsv").write_text(TSV_COLUMNS + TSV_ROWS)

    monkeypatch.setattr(build_db, "DB_DIR", db_dir)
    monkeypatch.setattr(build_db, "MAP_DIR", db_dir / "mappings")
    monkeypatch.setattr(build_db, "FINAL", db_dir / "final")
    monkeypatch.setattr(build_db, "DB", db_dir / "mlosmetadb.db")
    monkeypatch.setattr(build_db, "CACHE_DIR", db_dir / "cache")

    def _counts():
        con = sqlite3.connect(db_dir / "mlosmetadb.db")
        out = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
               for t in ("mlo_annotations", "mlo_definitions", "mlo_vocabulary", "proteins")}
        con.close()
        return out

    build_db.main.counts = _counts
    build_db.main.db_path = db_dir / "mlosmetadb.db"
    return build_db.main


def test_first_run_loads_the_expected_rows(build):
    build()
    counts = build.counts()
    # the 'unmapped' row is dropped, the driver/client pair for the same MLO is not
    assert counts["mlo_annotations"] == 3
    assert counts["mlo_definitions"] == 1
    assert counts["mlo_vocabulary"] == 2
    assert counts["proteins"] == 2


def test_running_twice_does_not_double_the_tables(build):
    build()
    first = build.counts()
    build()
    assert build.counts() == first


def test_running_three_times_still_does_not_drift(build):
    build()
    first = build.counts()
    build()
    build()
    assert build.counts() == first


def test_rerun_preserves_fetched_protein_data(build):
    """A rebuild of the annotations must not cost the UniProt fetch."""
    build()
    con = sqlite3.connect(build.db_path)
    con.execute("UPDATE proteins SET gene_name='FUS', sequence='MASNDYTQQ', length=9 "
                "WHERE uniprot_id='P35637'")
    con.commit()
    con.close()

    build()

    con = sqlite3.connect(build.db_path)
    row = con.execute("SELECT gene_name, sequence, length FROM proteins "
                      "WHERE uniprot_id='P35637'").fetchone()
    con.close()
    assert row == ("FUS", "MASNDYTQQ", 9)


def test_rerun_preserves_tables_build_db_does_not_own(build):
    """sequence_features/ppi/orthologs are written by other scripts entirely."""
    build()
    con = sqlite3.connect(build.db_path)
    con.execute("INSERT INTO sequence_features (uniprot_id, feature_type, source, start, end) "
                "VALUES ('P35637', 'idr', 'MobiDB-lite', 1, 50)")
    con.execute("INSERT INTO ppi (uniprot_id_a, uniprot_id_b, experimental_system) "
                "VALUES ('P35637', 'Q13148', 'Co-immunoprecipitation')")
    con.execute("INSERT INTO orthologs (uniprot_id, ortholog_id) VALUES ('P35637', 'P56959')")
    con.commit()
    con.close()

    build()

    con = sqlite3.connect(build.db_path)
    surviving = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                 for t in ("sequence_features", "ppi", "orthologs")}
    con.close()
    assert surviving == {"sequence_features": 1, "ppi": 1, "orthologs": 1}


def test_rerun_picks_up_a_changed_dataset(build):
    """Replacing, not appending, is what makes a regenerated TSV take effect."""
    build()
    (build_db.DB_DIR / "mlosmetadb.tsv").write_text(
        TSV_COLUMNS +
        "P35637\tPhaSepDB\tNucleolus\tnucleolus\tdriver\tdriver\t1\t111\tHomo sapiens\n"
    )
    build()

    con = sqlite3.connect(build.db_path)
    rows = con.execute("SELECT uniprot_id, source_db, unified_role FROM mlo_annotations").fetchall()
    con.close()
    assert rows == [("P35637", "PhaSepDB", "driver")]
