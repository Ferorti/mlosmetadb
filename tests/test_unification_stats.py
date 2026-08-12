"""Regression tests for scripts/build_unification_stats.py.

Runs against the live database/mlosmetadb.db (like tests/test_dataset_invariants.py
does) rather than a synthetic fixture, because this script's whole job is
recomputing report-ready numbers from that exact database.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_unification_stats as bus

DB_PATH = REPO_ROOT / "database" / "mlosmetadb.db"

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason=f"{DB_PATH} not present (gitignored); unification-stats tests skipped",
)


def test_load_category_map_has_eight_pairs_with_all_columns():
    cat_map = bus.load_category_map()
    assert len(cat_map) == 8
    for (source_db, source_role), row in cat_map.items():
        assert row["category"] in ("driver", "regulator", "component")
        assert row["evidence_type"]
        assert row["unified_role"] in ("driver", "client", None)


def test_f1_source_contribution_covers_five_sources_and_sums_to_total():
    conn = bus.connect_db()
    f1 = bus.build_f1_source_contribution(conn)
    assert len(f1) == 5
    assert {row["source_db"] for row in f1} == {
        "CDCODE", "DrLLPS", "LLPSDB", "PhaSepDB", "PhasePro",
    }
    total_annotations = conn.execute(
        f"SELECT COUNT(*) FROM mlo_annotations ma WHERE {bus.policy.active_annotation_clause('ma')}"
    ).fetchone()[0]
    assert sum(row["annotations"] for row in f1) == total_annotations


def test_f2_protein_source_combos_proteins_sum_to_total_proteins():
    conn = bus.connect_db()
    f2 = bus.build_f2_protein_source_combos(conn)
    total_proteins = conn.execute(
        f"SELECT COUNT(DISTINCT ma.uniprot_id) FROM mlo_annotations ma WHERE {bus.policy.active_annotation_clause('ma')}"
    ).fetchone()[0]
    assert sum(row["n_proteins"] for row in f2) == total_proteins


def test_disc_patterns_sum_to_discordant_count():
    conn = bus.connect_db()
    category_map = bus.load_category_map()
    pair_data = bus.build_pair_data(conn, category_map)
    summary = bus.build_agreement_summary(pair_data)

    assert sum(summary["disc_patterns"].values()) == summary["discordant_pairs"]


def test_f6_pmid_overlap_matches_reference():
    conn = bus.connect_db()
    f6 = bus.build_f6_pmid_overlap_sources(conn)
    assert len(f6) == 6  # C(4,2) -- CD-CODE excluded, it cites no PMIDs


def test_cat3_annotations_sum_to_total():
    conn = bus.connect_db()
    category_map = bus.load_category_map()
    f4 = bus.build_f4_role_mapping(conn, category_map)
    active = policy_total = conn.execute(
        f"SELECT COUNT(*) FROM mlo_annotations ma WHERE {bus.policy.active_annotation_clause('ma')}"
    ).fetchone()[0]
    assert sum(row["annotations"] for row in f4) == policy_total


def test_discrepant_pairs_rows_count_matches_discordant():
    conn = bus.connect_db()
    category_map = bus.load_category_map()
    pair_data = bus.build_pair_data(conn, category_map)
    rows = bus.build_discrepant_pairs_rows(conn, pair_data)
    summary = bus.build_agreement_summary(pair_data)
    assert len(rows) == summary["discordant_pairs"]


def test_discrepant_pairs_row_shape_and_alignment():
    conn = bus.connect_db()
    category_map = bus.load_category_map()
    pair_data = bus.build_pair_data(conn, category_map)
    rows = bus.build_discrepant_pairs_rows(conn, pair_data)

    # Q7Z3E1/nuclear_body is a real discordant pair verified during design
    # (CDCODE=component, PhaSepDB=driver) -- do not swap in a pair from
    # f5_role_discrepancy_pairs.csv without checking its n_cats first, that
    # file lists all 10,617 shared pairs, not just the 1,318 discordant ones.
    row = next(r for r in rows if r["uniprot_id"] == "Q7Z3E1" and r["unified_mlo"] == "nuclear_body")
    assert row["categories"] == "component;driver"
    sources = row["sources"].split(";")
    categories = row["categories"].split(";")
    assert len(sources) == len(categories)
    assert sources == sorted(sources)
    for field in ("uniprot_id", "gene_name", "unified_mlo", "sources", "categories",
                  "source_roles", "evidence_types", "pmids_per_source"):
        assert field in row


def test_mlo_term_mapping_rows_cover_every_source_triple():
    conn = bus.connect_db()
    rows = bus.build_mlo_term_mapping_rows(conn)
    active = bus.policy.active_annotation_clause("ma")
    expected_triples = conn.execute(f"""
        SELECT COUNT(DISTINCT ma.unified_mlo || '|' || ma.source_db || '|' || ma.source_mlo)
        FROM mlo_annotations ma WHERE {active}
    """).fetchone()[0]
    assert len(rows) == expected_triples

    row = next(r for r in rows if r["unified_mlo"] == "stress_granule" and r["source_db"] == "PhaSepDB")
    assert row["annotations"] > 0
    assert row["proteins"] > 0


def test_mlo_term_mapping_left_join_keeps_rows_with_no_definition():
    conn = bus.connect_db()
    rows = bus.build_mlo_term_mapping_rows(conn)
    # some combos have no curated definition (verified during design: 111 of 483) --
    # they must still appear, with definition explicitly None, not be dropped.
    assert any(r["definition"] is None for r in rows)


def test_cat3_annotations_sum_equals_db_count():
    """docs/review/unification_section/INFORME_SECCION_UNIFICACION.md §6.3:
    'el pipeline falla si sum(cat3) != n_annotations'."""
    conn = bus.connect_db()
    category_map = bus.load_category_map()
    data = bus.write_unification_stats_json(conn, category_map)
    assert sum(data["summary"]["cat3_annotations"].values()) == data["summary"]["n_annotations"]


def test_no_unmapped_source_db_source_role_pair():
    """§6.3: 'el pipeline falla ... si aparece un par (source_db, source_role)
    sin mapeo en las 3 categorías'."""
    conn = bus.connect_db()
    category_map = bus.load_category_map()
    active = bus.policy.active_annotation_clause("ma")
    live_pairs = set(conn.execute(
        f"SELECT DISTINCT ma.source_db, ma.source_role FROM mlo_annotations ma WHERE {active}"
    ).fetchall())
    unmapped = live_pairs - set(category_map.keys())
    assert not unmapped, f"unmapped (source_db, source_role) pairs: {unmapped}"


def test_summary_n_annotations_matches_direct_db_count():
    conn = bus.connect_db()
    active = bus.policy.active_annotation_clause("ma")
    direct_count = conn.execute(f"SELECT COUNT(*) FROM mlo_annotations ma WHERE {active}").fetchone()[0]
    category_map = bus.load_category_map()
    data = bus.write_unification_stats_json(conn, category_map)
    assert data["summary"]["n_annotations"] == direct_count


def test_mlo_term_mapping_annotations_sum_matches_total():
    """Guards against join fan-out: if mlo_definitions ever had 2 rows for
    the same (unified_mlo, source_db, source_name), the LEFT JOIN would
    double-count that triple's annotations without changing the row count."""
    conn = bus.connect_db()
    rows = bus.build_mlo_term_mapping_rows(conn)
    active = bus.policy.active_annotation_clause("ma")
    total_annotations = conn.execute(
        f"SELECT COUNT(*) FROM mlo_annotations ma WHERE {active}"
    ).fetchone()[0]
    assert sum(r["annotations"] for r in rows) == total_annotations
