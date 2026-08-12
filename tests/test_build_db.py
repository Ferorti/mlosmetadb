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

# `Categoria` is still in the file (it is the provenance of the spatial axis for
# 121 of the 177 terms) but load_mlo_vocabulary() no longer reads it: the
# classification comes from mlo_axes.csv, keyed by canonical instead of by source
# label. Two source names for one canonical with disagreeing categories used to
# be a hard failure; here it is simply not expressible.
MAPPING_CSV = """Nombre Original,Nombre Sugerido,Categoria,Justificacion Biologica
Nucleolus,nucleolus,Nuclear,test entry
Nucleoli,nucleolus,Citoplasma,same canonical, contradictory old category
Stress granule,stress_granule,Citoplasma,test entry
"""

AXES_CSV = """unified_mlo,spatial_location,spatial_location_evidence,taxonomic_scope,taxonomic_support_n,physiological_state,cell_type_context
nucleolus,nucleus,from_category,Metazoa,2,constitutive,
stress_granule,cytoplasm,from_category,,,stress_induced,neuron
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
    (db_dir / "mappings" / "mlo_axes.csv").write_text(AXES_CSV)
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


# ---------------------------------------------------------------------------
# The four axes (R1-ACT-06): mlo_axes.csv replaced `Categoria` as the source of
# the vocabulary's classification, and the loader's refusals moved with it.
# ---------------------------------------------------------------------------

def test_the_axes_land_on_the_vocabulary(build):
    build()
    con = sqlite3.connect(build.db_path)
    rows = dict((r[0], r[1:]) for r in con.execute(
        "SELECT unified_mlo, spatial_location, spatial_location_evidence, taxonomic_scope, "
        "taxonomic_support_n, physiological_state, cell_type_context FROM mlo_vocabulary"))
    assert "category" not in {c[1] for c in con.execute("PRAGMA table_info(mlo_vocabulary)")}
    con.close()
    assert rows["nucleolus"] == ("nucleus", "from_category", "Metazoa", 2, "constitutive", None)
    # Empty axis fields become NULL, not '': rho_body's taxonomic scope is a real
    # gap (its only protein is deleted in UniProt) and cell_type_context is absent
    # by design for the 143 terms where cell type is not part of the definition.
    assert rows["stress_granule"] == ("cytoplasm", "from_category", None, None, "stress_induced", "neuron")


def test_two_mapping_rows_for_one_canonical_no_longer_conflict(build):
    """MAPPING_CSV gives nucleolus two source names with contradictory Categoria
    values. Before the migration that aborted the load; now the column is not
    read and the axes file is one-to-one with the canonical."""
    build()
    con = sqlite3.connect(build.db_path)
    n = con.execute("SELECT COUNT(*) FROM mlo_vocabulary WHERE unified_mlo='nucleolus'").fetchone()[0]
    con.close()
    assert n == 1


def test_a_duplicated_axes_row_is_fatal(build):
    (build_db.MAP_DIR / "mlo_axes.csv").write_text(
        AXES_CSV + "nucleolus,cytoplasm,hand_assigned,Fungi,9,constitutive,\n")
    with pytest.raises(SystemExit, match="repite 'nucleolus'"):
        build()


def test_axes_for_a_term_no_mapping_produces_is_fatal(build):
    """A stale axes file is a defect, not a harmless extra row: it means the
    classification and the mapping disagree about which terms exist."""
    (build_db.MAP_DIR / "mlo_axes.csv").write_text(
        AXES_CSV + "retired_body,nucleus,hand_assigned,Metazoa,1,constitutive,\n")
    with pytest.raises(SystemExit, match="retired_body"):
        build()


def test_a_served_term_without_axes_is_fatal(build):
    """The inverse gap. A term with no axes row is tolerated while it reaches no
    annotation (three do, and get pruned), but never once it ships."""
    (build_db.MAP_DIR / "mlo_axes.csv").write_text(
        "\n".join(AXES_CSV.splitlines()[:2]) + "\n")   # header + nucleolus only
    with pytest.raises(SystemExit, match="sin ejes obligatorios"):
        build()


def test_migration_replaces_category_on_an_existing_db(build):
    """The shipped DB has the old column and 250 MB of fetched data that must not
    be rebuilt from scratch, so the column change is an ALTER, not a re-CREATE."""
    build()
    con = sqlite3.connect(build.db_path)
    con.executescript("""
        DROP TABLE mlo_annotations;
        DROP TABLE mlo_definitions;
        ALTER TABLE mlo_vocabulary DROP COLUMN spatial_location;
        ALTER TABLE mlo_vocabulary ADD COLUMN category TEXT;
        UPDATE mlo_vocabulary SET category = 'Nuclear';
    """)
    con.commit()
    con.close()

    build()

    con = sqlite3.connect(build.db_path)
    cols = {c[1] for c in con.execute("PRAGMA table_info(mlo_vocabulary)")}
    spatial = con.execute(
        "SELECT spatial_location FROM mlo_vocabulary WHERE unified_mlo='nucleolus'").fetchone()[0]
    con.close()
    assert "category" not in cols
    assert spatial == "nucleus"
