"""Regression tests for scripts/build_unification_stats.py.

Runs against the live database/mlosmetadb.db (like tests/test_dataset_invariants.py
does) rather than a synthetic fixture, because this script's whole job is
recomputing report-ready numbers from that exact database.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_unification_stats as bus


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
