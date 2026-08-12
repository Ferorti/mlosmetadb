import sys
from pathlib import Path

REFACTOR_ROOT = Path(__file__).resolve().parent.parent
if str(REFACTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(REFACTOR_ROOT))

sys.path.insert(0, str(REFACTOR_ROOT / "database"))

from policy import (
    CANONICAL_SOURCE_NAMES,
    EXCLUDED_MLO_SPATIAL_LOCATIONS,
    active_annotation_clause,
    canonical_source_case_sql,
    component_role_clause,
    excluded_mlo_spatial_clause,
    regulator_annotation_clause,
)
from schemas.intermediate import SOURCE_DBS


def test_active_annotation_clause_default_alias():
    assert active_annotation_clause() == "ma.dataset_active = 1"


def test_active_annotation_clause_custom_alias():
    assert active_annotation_clause("x") == "x.dataset_active = 1"
    assert active_annotation_clause("ma2") == "ma2.dataset_active = 1"


def test_excluded_mlo_spatial_locations_excludes_unspecified_by_default():
    # Reversed 2026-08-05 (frontend-phase audit, commit e799f6a, REFACTOR_LOG.md
    # Entry 14): 'NotInformed' was leaking into the /mlos browse grid as if it
    # were a real organelle. Was [] through the api/ phase (Entry 11); moved from
    # the category value 'Unspecified' to spatial_location='unspecified' by the
    # four-axis migration -- see policy.py's own docstring for the rationale.
    assert EXCLUDED_MLO_SPATIAL_LOCATIONS == ["unspecified"]


def test_excluded_mlo_spatial_clause_excludes_unspecified_by_default():
    clause, params = excluded_mlo_spatial_clause("mv")
    assert clause == "(mv.spatial_location IS NULL OR mv.spatial_location NOT IN (?))"
    assert params == ["unspecified"]


def test_excluded_mlo_spatial_clause_keeps_terms_with_an_undetermined_axis():
    """A NULL axis is a gap, a placeholder value is a curated statement.

    `spatial_location NOT IN ('unspecified')` is NULL for a NULL axis, which in a
    WHERE conjunct silently drops the row -- the same NULL-unsafety that
    component_role_clause() exists to avoid. Any term whose axis was never
    determined has to stay browsable.
    """
    clause, _ = excluded_mlo_spatial_clause("mv")
    assert "IS NULL OR" in clause


def test_excluded_mlo_spatial_clause_is_noop_when_empty(monkeypatch):
    monkeypatch.setattr("policy.EXCLUDED_MLO_SPATIAL_LOCATIONS", [])
    clause, params = excluded_mlo_spatial_clause("mv")
    assert clause is None
    assert params == []


def test_regulator_annotation_clause_keys_on_the_kind_of_claim():
    """Not on source_db: what makes a row a regulator claim is that a curator
    assigned the label, not that DrLLPS is the one publishing it."""
    assert regulator_annotation_clause() == (
        "(ma.evidence_type = 'curator_assignment' AND ma.source_role = 'Regulator')"
    )
    assert "source_db" not in regulator_annotation_clause()


def test_regulator_annotation_clause_custom_alias():
    assert regulator_annotation_clause("x") == (
        "(x.evidence_type = 'curator_assignment' AND x.source_role = 'Regulator')"
    )


def test_component_role_clause_default_alias():
    assert (
        component_role_clause()
        == "(ma.unified_role IS NULL OR LOWER(ma.unified_role) != 'driver')"
    )


def test_component_role_clause_custom_alias():
    assert (
        component_role_clause("x")
        == "(x.unified_role IS NULL OR LOWER(x.unified_role) != 'driver')"
    )


# ---------------------------------------------------------------------------
# Canonical source names
#
# CANONICAL_SOURCE_NAMES is a display-name map, and for a while it was also
# acting as cover for a data defect: it carried a sixth and seventh key,
# "PhaseDB" and "PhasePDB", both folding to "PhaSepDB", because one source
# database was being ingested twice under two tags. Mapping the display name
# hid the duplication from the About page while every underlying count stayed
# doubled. See docs/issues/001-phasedb-phasepdb-duplicate-ingestion.md.
#
# The invariant that would have caught it: this map's keys are exactly the
# valid source_db values, one entry per ingested source, no more.
# ---------------------------------------------------------------------------

def test_canonical_source_names_keys_are_exactly_the_valid_source_dbs():
    assert set(CANONICAL_SOURCE_NAMES) == set(SOURCE_DBS)


def test_canonical_source_names_has_one_entry_per_source():
    assert len(CANONICAL_SOURCE_NAMES) == len(SOURCE_DBS)


def test_no_two_tags_fold_into_the_same_display_name():
    """Two tags sharing a display name means one source is ingested twice."""
    names = list(CANONICAL_SOURCE_NAMES.values())
    assert len(names) == len(set(names)), f"duplicate display names: {names}"


def test_retired_ingestion_tags_are_not_reintroduced():
    for retired in ("PhaseDB", "PhasePDB"):
        assert retired not in CANONICAL_SOURCE_NAMES
        assert retired not in SOURCE_DBS


def test_phasepdb_is_spelled_with_a_lowercase_p_before_db():
    """Matches the database's own Nucleic Acids Research paper title."""
    assert CANONICAL_SOURCE_NAMES["PhaSepDB"] == "PhaSepDB"


def test_canonical_source_case_sql_covers_every_tag():
    sql = canonical_source_case_sql()
    for raw, canonical in CANONICAL_SOURCE_NAMES.items():
        assert f"WHEN '{raw}' THEN '{canonical}'" in sql


def test_canonical_source_case_sql_honours_a_custom_column():
    sql = canonical_source_case_sql("ma.source_db")
    assert sql.startswith("CASE ma.source_db ")
    assert sql.endswith("ELSE ma.source_db END")
