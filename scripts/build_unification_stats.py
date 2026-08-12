#!/usr/bin/env python3
"""
build_unification_stats.py — Data-layer build for the "Data unification"
report section (docs/review/unification_section/INFORME_SECCION_UNIFICACION.md).

Reads database/mlosmetadb.db (dataset_active=1 rows only) and
database/mappings/role_harmonisation.csv. Writes:
  - database/exports/unification_stats.json
  - database/exports/discrepant_pairs.csv
  - database/exports/mlo_term_mapping.csv

Run after any pipeline regeneration (scripts/build_db.py, scripts/build_summary.py):
    python3 scripts/build_unification_stats.py
"""

import csv
import json
import sqlite3
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import policy

DB_PATH = ROOT / "database" / "mlosmetadb.db"
CATEGORY_CSV_PATH = ROOT / "database" / "mappings" / "role_harmonisation.csv"
EXPORT_DIR = ROOT / "database" / "exports"


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA query_only = ON")
    return conn


def load_category_map() -> dict:
    """(source_db, source_role) -> {"unified_role": str|None, "category": str,
    "evidence_type": str, "note": str}."""
    with open(CATEGORY_CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    result = {}
    for row in rows:
        unified_role = None if row["unified_role"] == "NULL" else row["unified_role"]
        result[(row["source_db"], row["source_role"])] = {
            "unified_role": unified_role,
            "category": row["category"],
            "evidence_type": row["evidence_type"],
            "note": row["note"],
        }
    return result


# ── F1: Sources ───────────────────────────────────────────────────────────────

def build_f1_source_contribution(conn: sqlite3.Connection) -> list:
    active = policy.active_annotation_clause("ma")
    rows = conn.execute(f"""
        SELECT
            ma.source_db,
            COUNT(*) AS annotations,
            COUNT(DISTINCT ma.uniprot_id) AS proteins,
            COUNT(DISTINCT ma.source_mlo) AS source_terms,
            COUNT(DISTINCT ma.unified_mlo) AS unified_terms
        FROM mlo_annotations ma
        WHERE {active}
        GROUP BY ma.source_db
        ORDER BY ma.source_db
    """).fetchall()
    return [
        {
            "source_db": r[0], "annotations": r[1], "proteins": r[2],
            "source_terms": r[3], "unified_terms": r[4],
        }
        for r in rows
    ]


# ── F2: Protein overlap ───────────────────────────────────────────────────────

def build_f2_protein_source_combos(conn: sqlite3.Connection) -> list:
    active = policy.active_annotation_clause("ma")
    rows = conn.execute(f"""
        SELECT ma.uniprot_id, ma.source_db
        FROM mlo_annotations ma
        WHERE {active}
    """).fetchall()

    protein_sources = defaultdict(set)
    for uniprot_id, source_db in rows:
        protein_sources[uniprot_id].add(source_db)

    combo_counts = defaultdict(int)
    for sources in protein_sources.values():
        combo_counts[tuple(sorted(sources))] += 1

    result = [
        {
            "combo_label": "+".join(combo),
            "sources": list(combo),
            "n_proteins": n,
            "n_sources": len(combo),
        }
        for combo, n in combo_counts.items()
    ]
    result.sort(key=lambda r: -r["n_proteins"])
    return result


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect_db()

    print("=== Loading role_harmonisation.csv ===")
    category_map = load_category_map()
    print(f"  {len(category_map)} (source_db, source_role) pairs")

    print("=== F1: source contribution ===")
    f1 = build_f1_source_contribution(conn)
    for row in f1:
        print(f"  {row['source_db']}: {row['annotations']} annotations, {row['proteins']} proteins")

    print("=== F2: protein source combos ===")
    f2 = build_f2_protein_source_combos(conn)
    print(f"  {len(f2)} distinct combos")

    conn.close()


if __name__ == "__main__":
    main()
