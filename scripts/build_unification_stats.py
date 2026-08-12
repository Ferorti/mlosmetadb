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


# ── F3: MLO vocabulary ────────────────────────────────────────────────────────

def build_f3_vocab_collapse(conn: sqlite3.Connection) -> list:
    active = policy.active_annotation_clause("ma")
    rows = conn.execute(f"""
        SELECT
            ma.unified_mlo,
            COUNT(DISTINCT ma.source_mlo) AS n_source_names,
            COUNT(DISTINCT ma.source_db) AS n_sources,
            COUNT(*) AS annotations,
            COUNT(DISTINCT ma.uniprot_id) AS proteins
        FROM mlo_annotations ma
        WHERE {active}
        GROUP BY ma.unified_mlo
        ORDER BY n_source_names DESC, ma.unified_mlo
    """).fetchall()
    return [
        {
            "unified_mlo": r[0], "n_source_names": r[1], "n_sources": r[2],
            "annotations": r[3], "proteins": r[4],
        }
        for r in rows
    ]


# ── F4: Role harmonisation ────────────────────────────────────────────────────

def build_f4_role_mapping(conn: sqlite3.Connection, category_map: dict) -> list:
    active = policy.active_annotation_clause("ma")
    rows = conn.execute(f"""
        SELECT ma.source_db, ma.source_role, COUNT(*), COUNT(DISTINCT ma.uniprot_id)
        FROM mlo_annotations ma
        WHERE {active}
        GROUP BY ma.source_db, ma.source_role
        ORDER BY ma.source_db, ma.source_role
    """).fetchall()
    result = []
    for source_db, source_role, annotations, proteins in rows:
        mapping = category_map[(source_db, source_role)]
        result.append({
            "source_db": source_db,
            "source_role": source_role,
            "evidence_type": mapping["evidence_type"],
            "category": mapping["category"],
            "annotations": annotations,
            "proteins": proteins,
        })
    return result


# ── Shared pair-level data (F5, F5b, discrepant_pairs.csv all read this) ──────

def build_pair_data(conn: sqlite3.Connection, category_map: dict) -> dict:
    """(uniprot_id, unified_mlo) -> {
        "source_dbs": set[str],
        "categories": set[str],
        "rows": list[{"source_db", "source_role", "evidence_type", "category", "evidence"}],
    }

    Grain matches mlo_annotations exactly: a single source_db can contribute
    more than one row to the same pair (e.g. PhaSepDB reporting both `client`
    and `driver` for the same protein+MLO — 217 such pairs in the live
    dataset, see the design spec's verification). Do not collapse per source_db
    before this point.
    """
    active = policy.active_annotation_clause("ma")
    rows = conn.execute(f"""
        SELECT ma.uniprot_id, ma.unified_mlo, ma.source_db, ma.source_role, ma.evidence_type, ma.evidence
        FROM mlo_annotations ma
        WHERE {active}
    """).fetchall()

    pair_data = defaultdict(lambda: {"source_dbs": set(), "categories": set(), "rows": []})
    for uniprot_id, unified_mlo, source_db, source_role, evidence_type, evidence in rows:
        key = (uniprot_id, unified_mlo)
        category = category_map[(source_db, source_role)]["category"]
        pair_data[key]["source_dbs"].add(source_db)
        pair_data[key]["categories"].add(category)
        pair_data[key]["rows"].append({
            "source_db": source_db,
            "source_role": source_role,
            "evidence_type": evidence_type,
            "category": category,
            "evidence": evidence,
        })
    return dict(pair_data)


def build_agreement_summary(pair_data: dict) -> dict:
    shared = {k: v for k, v in pair_data.items() if len(v["source_dbs"]) >= 2}
    concordant = 0
    disc_patterns = defaultdict(int)
    for v in shared.values():
        if len(v["categories"]) == 1:
            concordant += 1
        else:
            disc_patterns["|".join(sorted(v["categories"]))] += 1
    discordant = sum(disc_patterns.values())
    return {
        "shared_pairs": len(shared),
        "concordant_pairs": concordant,
        "discordant_pairs": discordant,
        "disc_patterns": dict(disc_patterns),
    }


# ── F5b: discrepancy by MLO ────────────────────────────────────────────────────

def build_f5b_discrepancy_by_mlo(pair_data: dict) -> list:
    by_mlo = defaultdict(int)
    for (uniprot_id, unified_mlo), v in pair_data.items():
        if len(v["source_dbs"]) >= 2 and len(v["categories"]) > 1:
            by_mlo[unified_mlo] += 1
    result = [{"unified_mlo": mlo, "n_discordant": n} for mlo, n in by_mlo.items()]
    result.sort(key=lambda r: -r["n_discordant"])
    return result


# ── F6: PMID overlap between sources ──────────────────────────────────────────

def _distinct_pmids_by_source(conn: sqlite3.Connection) -> dict:
    active = policy.active_annotation_clause("ma")
    rows = conn.execute(f"""
        SELECT ma.source_db, ma.evidence
        FROM mlo_annotations ma
        WHERE {active} AND ma.evidence IS NOT NULL AND ma.evidence != 'NULL'
    """).fetchall()
    pmids_by_source = defaultdict(set)
    for source_db, evidence in rows:
        for pmid in evidence.split(";"):
            pmid = pmid.strip()
            if pmid:
                pmids_by_source[source_db].add(pmid)
    return pmids_by_source


def build_f6_pmid_overlap_sources(conn: sqlite3.Connection) -> list:
    pmids_by_source = _distinct_pmids_by_source(conn)
    sources_with_pmids = sorted(db for db, pmids in pmids_by_source.items() if pmids)
    result = []
    for i in range(len(sources_with_pmids)):
        for j in range(i + 1, len(sources_with_pmids)):
            db_a, db_b = sources_with_pmids[i], sources_with_pmids[j]
            set_a, set_b = pmids_by_source[db_a], pmids_by_source[db_b]
            shared = len(set_a & set_b)
            union = len(set_a | set_b)
            result.append({
                "db_a": db_a, "db_b": db_b,
                "n_a": len(set_a), "n_b": len(set_b),
                "shared": shared,
                "jaccard": round(shared / union, 3) if union else 0.0,
            })
    result.sort(key=lambda r: -r["shared"])
    return result


# ── PMID independence (F6 left panel + summary) ───────────────────────────────

def build_pmid_independence_stats(conn: sqlite3.Connection) -> dict:
    active = policy.active_annotation_clause("ma")
    rows = conn.execute(f"""
        SELECT ma.uniprot_id, ma.unified_mlo, ma.source_db, ma.evidence
        FROM mlo_annotations ma
        WHERE {active} AND ma.source_db != 'CDCODE'
    """).fetchall()

    pair_source_pmids = defaultdict(dict)
    for uniprot_id, unified_mlo, source_db, evidence in rows:
        pmids = set()
        if evidence and evidence != "NULL":
            for pmid in evidence.split(";"):
                pmid = pmid.strip()
                if pmid:
                    pmids.add(pmid)
        if pmids:
            key = (uniprot_id, unified_mlo)
            pair_source_pmids[key].setdefault(source_db, set())
            pair_source_pmids[key][source_db] |= pmids

    comparable = shared = 0
    for source_map in pair_source_pmids.values():
        if len(source_map) < 2:
            continue
        comparable += 1
        pmid_sets = list(source_map.values())
        if any(pmid_sets[i] & pmid_sets[j]
               for i in range(len(pmid_sets)) for j in range(i + 1, len(pmid_sets))):
            shared += 1

    independent = comparable - shared
    return {
        "pairs_pmid_comparable": comparable,
        "pairs_shared_pub": shared,
        "pairs_independent_pub": independent,
        "pct_independent_pub": round(100 * independent / comparable, 1) if comparable else 0.0,
    }


def _git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
    except Exception:
        return "unknown"


def write_unification_stats_json(conn: sqlite3.Connection, category_map: dict) -> dict:
    import datetime

    active = policy.active_annotation_clause("ma")
    n_annotations = conn.execute(f"SELECT COUNT(*) FROM mlo_annotations ma WHERE {active}").fetchone()[0]
    n_proteins = conn.execute(f"SELECT COUNT(DISTINCT ma.uniprot_id) FROM mlo_annotations ma WHERE {active}").fetchone()[0]
    n_unified_mlo_terms = conn.execute(f"SELECT COUNT(DISTINCT ma.unified_mlo) FROM mlo_annotations ma WHERE {active}").fetchone()[0]
    n_source_entries = conn.execute(
        f"SELECT COUNT(DISTINCT ma.source_db || '|' || ma.source_mlo) FROM mlo_annotations ma WHERE {active}"
    ).fetchone()[0]

    f1 = build_f1_source_contribution(conn)
    f2 = build_f2_protein_source_combos(conn)
    f3 = build_f3_vocab_collapse(conn)
    f4 = build_f4_role_mapping(conn, category_map)
    pair_data = build_pair_data(conn, category_map)
    agreement = build_agreement_summary(pair_data)
    f5b = build_f5b_discrepancy_by_mlo(pair_data)
    f6 = build_f6_pmid_overlap_sources(conn)
    pmid_stats = build_pmid_independence_stats(conn)

    proteins_multi_source = sum(row["n_proteins"] for row in f2 if row["n_sources"] >= 2)
    proteins_single_source = sum(row["n_proteins"] for row in f2 if row["n_sources"] == 1)

    cat3_annotations = defaultdict(int)
    cat3_evidence_types = defaultdict(set)
    for row in f4:
        cat3_annotations[row["category"]] += row["annotations"]
        cat3_evidence_types[row["category"]].add(row["evidence_type"])

    unique_pmids = len({
        pmid.strip()
        for (_db, evidence) in conn.execute(
            f"SELECT ma.source_db, ma.evidence FROM mlo_annotations ma WHERE {active} AND ma.evidence IS NOT NULL AND ma.evidence != 'NULL'"
        ).fetchall()
        for pmid in evidence.split(";") if pmid.strip()
    })
    annotations_without_pmid = conn.execute(
        f"SELECT COUNT(*) FROM mlo_annotations ma WHERE {active} AND (ma.evidence IS NULL OR ma.evidence = 'NULL')"
    ).fetchone()[0]

    collapse_ratio = round(n_source_entries / n_unified_mlo_terms, 2) if n_unified_mlo_terms else 0.0

    data = {
        "meta": {
            "db_commit": _git_commit(ROOT),
            "build_date": datetime.datetime.utcnow().isoformat() + "Z",
            "n_annotations": n_annotations,
        },
        "summary": {
            "n_annotations": n_annotations,
            "n_proteins": n_proteins,
            "n_unified_mlo_terms": n_unified_mlo_terms,
            "n_source_entries": n_source_entries,
            "collapse_ratio": collapse_ratio,
            "proteins_multi_source": proteins_multi_source,
            "proteins_single_source": proteins_single_source,
            "cat3_annotations": dict(cat3_annotations),
            "cat3_evidence_type_counts": {k: len(v) for k, v in cat3_evidence_types.items()},
            "unique_pmids": unique_pmids,
            "annotations_without_pmid": annotations_without_pmid,
            **agreement,
            **pmid_stats,
        },
        "f1_source_contribution": f1,
        "f2_protein_source_combos": f2,
        "f3_vocab_collapse": f3,
        "f4_role_mapping": f4,
        "f5b_discrepancy_by_mlo": f5b,
        "f6_pmid_overlap_sources": f6,
    }

    out_path = EXPORT_DIR / "unification_stats.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Wrote {out_path}")
    return data


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect_db()

    print("=== Loading role_harmonisation.csv ===")
    category_map = load_category_map()
    print(f"  {len(category_map)} (source_db, source_role) pairs")

    print("=== Building unification_stats.json ===")
    data = write_unification_stats_json(conn, category_map)
    print(f"  n_annotations={data['summary']['n_annotations']}")
    print(f"  shared_pairs={data['summary']['shared_pairs']} "
          f"concordant={data['summary']['concordant_pairs']} "
          f"discordant={data['summary']['discordant_pairs']}")

    conn.close()


if __name__ == "__main__":
    main()
