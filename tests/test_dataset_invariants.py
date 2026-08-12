"""Witness tests against the real database/mlosmetadb.db.

Every other suite in this repo runs on a synthetic fixture DB, which is right
for testing logic but means nothing ever looked at the shipped dataset. The
PhaSepDB double-ingestion survived for months in plain sight: 54,786 annotation
rows where 35,971 were real, and a `source_db_count` of 6 when only five source
databases existed. No test could fail, because no test read the data.

Two kinds of check live here:

* **Invariants** — properties that must hold for any version of the dataset.
  They are hard-coded and are the real regression net.
* **Witnesses** — the current counts, compared against `dataset_baseline.json`.
  These are *expected* to change when the dataset is deliberately regenerated;
  the point is that the change has to be an explicit, reviewable edit to the
  baseline rather than something nobody notices.

To refresh the baseline after an intended regeneration:

    python3 tests/test_dataset_invariants.py

and commit the diff alongside the change that caused it.

Skipped entirely when the DB is absent (it is gitignored, ~250 MB).
"""

import json
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "database"))

from schemas.intermediate import SOURCE_DBS

DB_PATH = REPO_ROOT / "database" / "mlosmetadb.db"
BASELINE_PATH = Path(__file__).resolve().parent / "dataset_baseline.json"

REFRESH_HINT = (
    "If the dataset was regenerated on purpose, refresh the baseline with "
    "`python3 tests/test_dataset_invariants.py` and commit the diff."
)

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason=f"{DB_PATH} not present (gitignored); dataset witnesses skipped",
)


@pytest.fixture(scope="module")
def db():
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    yield con
    con.close()


def _count(con, sql: str, *params) -> int:
    return con.execute(sql, params).fetchone()[0]


# ---------------------------------------------------------------------------
# Invariants — must hold for any version of the dataset
# ---------------------------------------------------------------------------

def test_every_source_db_is_a_declared_source(db):
    found = {r[0] for r in db.execute("SELECT DISTINCT source_db FROM mlo_annotations")}
    assert found <= set(SOURCE_DBS), f"undeclared source_db values: {found - set(SOURCE_DBS)}"


def test_no_retired_ingestion_tag_is_present(db):
    """PhaseDB/PhasePDB were one resource ingested twice. See docs/issues/001."""
    assert _count(db, "SELECT COUNT(*) FROM mlo_annotations "
                      "WHERE source_db IN ('PhaseDB', 'PhasePDB')") == 0


def test_the_row_grain_holds(db):
    """One row per (uniprot_id, source_db, source_mlo, source_role).

    This is the invariant the double-ingestion violated, and the one
    integrate.py's collapse_duplicates() exists to enforce.
    """
    dupes = _count(db, """
        SELECT COUNT(*) FROM (
            SELECT 1 FROM mlo_annotations
            GROUP BY uniprot_id, source_db, source_mlo, source_role
            HAVING COUNT(*) > 1)
    """)
    assert dupes == 0, f"{dupes} duplicated annotation keys"


def test_no_protein_claims_more_sources_than_exist(db):
    worst = _count(db, "SELECT MAX(source_db_count) FROM protein_summary")
    assert worst <= len(SOURCE_DBS), (
        f"a protein reports {worst} source databases, but only "
        f"{len(SOURCE_DBS)} exist -- the symptom of a source ingested twice"
    )


def test_annotations_reference_existing_proteins(db):
    assert _count(db, "SELECT COUNT(*) FROM mlo_annotations "
                      "WHERE uniprot_id NOT IN (SELECT uniprot_id FROM proteins)") == 0


def test_annotations_reference_the_controlled_vocabulary(db):
    assert _count(db, "SELECT COUNT(*) FROM mlo_annotations "
                      "WHERE unified_mlo NOT IN (SELECT unified_mlo FROM mlo_vocabulary)") == 0


def test_unified_role_is_driver_client_or_null(db):
    bad = {r[0] for r in db.execute(
        "SELECT DISTINCT unified_role FROM mlo_annotations "
        "WHERE unified_role IS NOT NULL AND unified_role NOT IN ('driver', 'client')")}
    assert not bad, f"unexpected unified_role values: {bad}"


def test_dataset_active_is_zero_or_one(db):
    assert _count(db, "SELECT COUNT(*) FROM mlo_annotations "
                      "WHERE dataset_active NOT IN (0, 1)") == 0


def test_nothing_is_excluded_from_the_served_dataset(db):
    """policy.py: dataset_active=0 is a deliberate scope exclusion, and there is
    no longer any. DrLLPS Regulator was the only case and R1-ACT-14 closed it
    against us: hiding those 1.389 rows removed 501 proteins from the dataset
    outright, since a regulator annotation was the only one they had.

    Asserted as an equality against the served count rather than as
    `COUNT(dataset_active = 0) == 0`, because the old shape of this test
    (dataset_active=0 rows that are not DrLLPS Regulator) now passes for the
    wrong reason — it is vacuously true over an empty set. If an exclusion is
    ever argued for again, this fails and sends the reader to policy.py and to
    docs/review/findings.csv, which is the point."""
    assert (_count(db, "SELECT COUNT(*) FROM mlo_annotations WHERE dataset_active = 1")
            == _count(db, "SELECT COUNT(*) FROM mlo_annotations"))


def test_regulator_rows_are_served_with_a_null_role(db):
    """The reinstatement is two facts, and both have to hold: the rows count
    (dataset_active=1) and 'regulator' never becomes a unified_role value.
    What identifies them is (evidence_type, source_role) —
    policy.regulator_annotation_clause(), which the /mlo/{id} by_role CASE reads."""
    total, active, roles = db.execute(
        "SELECT COUNT(*), SUM(dataset_active), COUNT(DISTINCT unified_role) "
        "FROM mlo_annotations "
        "WHERE evidence_type = 'curator_assignment' AND source_role = 'Regulator'"
    ).fetchone()
    assert total > 0, "no quedan filas de regulador: ¿cambió la etiqueta de DrLLPS?"
    assert active == total
    assert roles == 0, "unified_role tiene que seguir siendo NULL en toda fila de regulador"


def test_source_mlo_is_never_blank(db):
    """An absent MLO name becomes the curated token NotInformed, never ''."""
    assert _count(db, "SELECT COUNT(*) FROM mlo_annotations "
                      "WHERE source_mlo IS NULL OR TRIM(source_mlo) = ''") == 0


def test_protein_summary_covers_every_protein_exactly_once(db):
    assert (_count(db, "SELECT COUNT(*) FROM protein_summary")
            == _count(db, "SELECT COUNT(*) FROM proteins")
            == _count(db, "SELECT COUNT(DISTINCT uniprot_id) FROM protein_summary"))
    assert _count(db, "SELECT COUNT(*) FROM protein_summary "
                      "WHERE uniprot_id NOT IN (SELECT uniprot_id FROM proteins)") == 0


def test_every_protein_has_at_least_one_annotation(db):
    """Proteins enter the DB through mlo_annotations; an orphan means a
    load dropped rows without dropping the protein stub."""
    assert _count(db, "SELECT COUNT(*) FROM proteins "
                      "WHERE uniprot_id NOT IN (SELECT uniprot_id FROM mlo_annotations)") == 0


def test_every_annotation_has_an_evidence_type(db):
    """A NULL evidence_type means integrate.py met a (source_db, source_role)
    pair its table does not cover — an upstream change, not a data gap. The
    eight pairs present today were verified exhaustive, so this must stay 0."""
    assert _count(db, "SELECT COUNT(*) FROM mlo_annotations WHERE evidence_type IS NULL") == 0


def test_every_served_term_carries_the_mandatory_axes(db):
    """Mirrors build_db.py::assert_axes_complete() against the shipped DB.

    taxonomic_scope and cell_type_context are NULL-able on purpose (rho_body has
    nothing to derive the first from; the second applies to 34 of 177 terms by
    design). The other three are not: a NULL there means mlo_axes.csv fell behind
    the mapping files and a term shipped unclassified."""
    assert _count(db, "SELECT COUNT(*) FROM mlo_vocabulary WHERE spatial_location IS NULL "
                      "OR spatial_location_evidence IS NULL OR physiological_state IS NULL") == 0


def test_category_is_gone_from_the_vocabulary(db):
    """R1-ACT-06 replaced it. Re-adding it would give the classification two
    representations, which is what the four-axis migration exists to end."""
    cols = {r[1] for r in db.execute("PRAGMA table_info(mlo_vocabulary)")}
    assert "category" not in cols
    assert {"spatial_location", "taxonomic_scope", "physiological_state",
            "cell_type_context"} <= cols


def test_spatial_location_evidence_declares_which_values_were_assigned_by_hand(db):
    """The audit derived 121 spatial values from the curated v6 category and
    assigned 56 itself from the organelle's biology, asking explicitly that those
    56 be reviewed. Storing which is which keeps that request queryable instead of
    leaving it in prose nobody joins against."""
    found = {r[0] for r in db.execute(
        "SELECT DISTINCT spatial_location_evidence FROM mlo_vocabulary")}
    assert found == {"from_category", "hand_assigned"}


def test_evidence_type_values_are_the_five_documented_ones(db):
    allowed = {"in_vitro_llps", "cellular_localisation", "cellular_requirement",
               "curator_assignment", "membership_only"}
    found = {r[0] for r in db.execute("SELECT DISTINCT evidence_type FROM mlo_annotations")}
    assert found <= allowed, f"evidence_type inesperado: {sorted(found - allowed)}"


# ---------------------------------------------------------------------------
# Witnesses — compared against the committed baseline
# ---------------------------------------------------------------------------

def _snapshot(con) -> dict:
    q = lambda sql: [tuple(r) for r in con.execute(sql)]
    return {
        "table_rows": {t: _count(con, f"SELECT COUNT(*) FROM {t}") for t in (
            "proteins", "mlo_annotations", "mlo_vocabulary", "mlo_definitions",
            "protein_summary", "sequence_features", "ppi", "orthologs")},
        "annotations_by_source": dict(q(
            "SELECT source_db, COUNT(*) FROM mlo_annotations GROUP BY 1 ORDER BY 1")),
        "annotations_by_role": dict(q(
            "SELECT COALESCE(unified_role, 'NULL'), COUNT(*) "
            "FROM mlo_annotations GROUP BY 1 ORDER BY 1")),
        "annotations_by_dataset_active": dict(q(
            "SELECT CAST(dataset_active AS TEXT), COUNT(*) "
            "FROM mlo_annotations GROUP BY 1 ORDER BY 1")),
        "annotations_by_evidence_type": dict(q(
            "SELECT COALESCE(evidence_type, 'NULL'), COUNT(*) "
            "FROM mlo_annotations GROUP BY 1 ORDER BY 1")),
        "source_db_count_histogram": dict(q(
            "SELECT CAST(source_db_count AS TEXT), COUNT(*) "
            "FROM protein_summary GROUP BY 1 ORDER BY 1")),
        # The four axes that replaced `category` (R1-ACT-06). spatial_location is
        # here rather than all four because it is the one a curator will revise:
        # 56 of its values were assigned by hand and are pending review, so a
        # change to any of them shows up as a baseline diff instead of silently.
        "vocabulary_by_spatial_location": dict(q(
            "SELECT spatial_location, COUNT(*) FROM mlo_vocabulary GROUP BY 1 ORDER BY 1")),
        "vocabulary_by_spatial_evidence": dict(q(
            "SELECT spatial_location_evidence, COUNT(*) FROM mlo_vocabulary GROUP BY 1 ORDER BY 1")),
        "proteins_without_sequence": _count(
            con, "SELECT COUNT(*) FROM proteins WHERE sequence IS NULL"),
        "annotations_with_literal_null_evidence": _count(
            con, "SELECT COUNT(*) FROM mlo_annotations WHERE evidence = 'NULL'"),
        "distinct_unified_mlos_in_use": _count(
            con, "SELECT COUNT(DISTINCT unified_mlo) FROM mlo_annotations"),
        "fus_p35637": {
            "source_dbs": con.execute(
                "SELECT source_dbs FROM protein_summary WHERE uniprot_id='P35637'").fetchone()[0],
            "mlo_count": _count(
                con, "SELECT mlo_count FROM protein_summary WHERE uniprot_id='P35637'"),
            "annotation_rows": _count(
                con, "SELECT COUNT(*) FROM mlo_annotations WHERE uniprot_id='P35637'"),
        },
    }


@pytest.fixture(scope="module")
def baseline():
    if not BASELINE_PATH.exists():
        pytest.fail(f"{BASELINE_PATH} is missing. {REFRESH_HINT}")
    return json.loads(BASELINE_PATH.read_text())


@pytest.fixture(scope="module")
def snapshot(db):
    """Computed once: it counts every row of ppi (~900k) and sequence_features."""
    return _snapshot(db)


COMPARED_SECTIONS = [
    "table_rows",
    "annotations_by_source",
    "annotations_by_role",
    "annotations_by_dataset_active",
    "annotations_by_evidence_type",
    "source_db_count_histogram",
    "vocabulary_by_spatial_location",
    "vocabulary_by_spatial_evidence",
    "proteins_without_sequence",
    "annotations_with_literal_null_evidence",
    "distinct_unified_mlos_in_use",
    "fus_p35637",
]


@pytest.mark.parametrize("section", COMPARED_SECTIONS)
def test_dataset_matches_the_committed_baseline(snapshot, baseline, section):
    assert snapshot[section] == baseline[section], REFRESH_HINT


def test_baseline_declares_the_commit_it_was_generated_on(baseline):
    """Sin esto no hay forma de detectar que un análisis externo midió sobre
    una copia vieja: la ronda 1 de la auditoría corrió sobre 54.786 filas
    cuando la base viva tenía 35.971, y nada lo declaraba."""
    meta = baseline.get("_meta")
    assert meta, "dataset_baseline.json no tiene bloque _meta"
    assert meta.get("generated_on_commit"), "_meta sin generated_on_commit"
    assert meta.get("generated_at"), "_meta sin generated_at"


def test_meta_is_not_part_of_the_compared_sections():
    """_meta cambia en cada regeneración. Si entrara en la comparación, el test
    de la línea base fallaría en cada commit."""
    assert "_meta" not in COMPARED_SECTIONS


def _baseline_meta() -> dict:
    """Identifica sobre qué commit se generó esta línea base.

    El sha es el de HEAD al momento de regenerar, o sea el commit *anterior*
    al que va a incluir el archivo. Se lee como "generado sobre el commit X",
    que es lo que hace falta para detectar deriva contra un análisis externo.
    """
    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent,
    ).stdout.strip() or "unknown"
    return {"generated_on_commit": sha, "generated_at": date.today().isoformat()}


def _write_baseline() -> None:
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    # _meta va acá y no en _snapshot() a propósito: la fixture del test usa
    # _snapshot() en cada corrida y no debe depender de que git esté disponible.
    payload = {"_meta": _baseline_meta(), **_snapshot(con)}
    BASELINE_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    con.close()
    print(f"baseline written: {BASELINE_PATH}")


if __name__ == "__main__":
    _write_baseline()
