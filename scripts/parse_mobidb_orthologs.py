#!/usr/bin/env python3
"""
parse_mobidb_orthologs.py — parsea mobidb_cache.db para ortholog_ids.

Escribe en:
  - ortholog_meta:     gene_name, protein_name, organism, length, disorder%, sequence
  - ortholog_features: IDRs, LCDs, MoRFs, pLDDT, dominios Pfam

Solo procesa IDs presentes en la tabla orthologs.
"""

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "database" / "mlosmetadb.db"
CACHE_DB = ROOT / "database" / "cache" / "mobidb_cache.db"

# (json_key, feature_type, source, use_content_fraction)
FEATURE_MAP = [
    ("prediction-disorder-mobidb_lite",                 "idr",          "MobiDB-lite",        True),
    ("prediction-disorder-alphafold",                   "idr",          "AlphaFold-disorder", True),
    ("prediction-plddt-alphafold",                      "plddt_region", "AlphaFold",          True),
    ("prediction-low_complexity-mobidb_lite_sub",       "lcd",          "MobiDB-lite-sub",    False),
    ("prediction-low_complexity-seg",                   "lcd",          "SEG",                False),
    ("derived-binding_mode_disorder_to_order-priority", "morf",         "MobiDB",             True),
    ("homology-domain-pfam",                            "domain",       "Pfam",               False),
]

MOBIDB_SOURCES = {t[2] for t in FEATURE_MAP}


def _content_fraction(block: dict, key: str) -> float | None:
    """Extracts content_fraction from a MobiDB block."""
    return block.get("content_fraction")


def parse_features(uid: str, data: dict, fetched_at: str) -> list[tuple]:
    rows = []
    for json_key, feature_type, source, use_cf in FEATURE_MAP:
        if json_key not in data:
            continue
        block = data[json_key]
        regions = block.get("regions") or []
        content_fraction = block.get("content_fraction") if use_cf else None

        if json_key == "homology-domain-pfam":
            # Pfam has parallel lists: regions, regions_ids, regions_names
            ids = block.get("regions_ids") or []
            names = block.get("regions_names") or []
            for i, region in enumerate(regions):
                if len(region) < 2:
                    continue
                start, end = region[0], region[1]
                accession = ids[i] if i < len(ids) else None
                label = names[i] if i < len(names) else None
                rows.append((uid, feature_type, source, label, accession, start, end, None, None, fetched_at))
        else:
            for region in regions:
                if len(region) < 2:
                    continue
                start, end = region[0], region[1]
                score = region[2] if len(region) > 2 else None
                metadata = json.dumps({"content_fraction": content_fraction}) if content_fraction is not None else None
                rows.append((uid, feature_type, source, None, None, start, end, score, metadata, fetched_at))

    return rows


def parse_meta(uid: str, data: dict, fetched_at: str) -> dict:
    disorder_mobidb = None
    block_mobidb = data.get("prediction-disorder-mobidb_lite")
    if block_mobidb:
        disorder_mobidb = block_mobidb.get("content_fraction")

    disorder_af = None
    block_af = data.get("prediction-disorder-alphafold")
    if block_af:
        disorder_af = block_af.get("content_fraction")

    return {
        "ortholog_id":             uid,
        "gene_name":               data.get("gene"),
        "protein_name":            data.get("name"),
        "organism":                data.get("organism"),
        "taxon_id":                data.get("ncbi_taxon_id"),
        "length":                  data.get("length"),
        "disorder_mobidb_lite_dc": disorder_mobidb,
        "disorder_alphafold_dc":   disorder_af,
        "sequence":                data.get("sequence"),
        "fetch_date":              fetched_at,
    }


def main() -> None:
    con_main = sqlite3.connect(DB)
    con_main.execute("PRAGMA journal_mode=WAL")
    con_cache = sqlite3.connect(CACHE_DB)

    valid_ids = {r[0] for r in con_main.execute("SELECT DISTINCT ortholog_id FROM orthologs")}
    print(f"Ortholog IDs en DB:  {len(valid_ids)}")

    already_done = {
        r[0]
        for r in con_main.execute(
            f"SELECT DISTINCT ortholog_id FROM ortholog_features "
            f"WHERE source IN ({','.join('?'*len(MOBIDB_SOURCES))})",
            tuple(MOBIDB_SOURCES),
        )
    }
    print(f"Ya procesados:       {len(already_done)}")

    total_processed = 0
    total_no_regions = 0
    total_skipped_done = 0
    total_skipped_invalid = 0
    total_empty = 0
    total_inserted = 0
    feature_batch: list[tuple] = []
    meta_batch: list[dict] = []

    cur = con_cache.execute("SELECT uniprot_id, response, fetched_at FROM responses WHERE status_code=200")

    for uid, resp_str, fetched_at in cur:
        if uid not in valid_ids:
            total_skipped_invalid += 1
            continue
        if uid in already_done:
            total_skipped_done += 1
            continue

        try:
            raw = json.loads(resp_str)
        except (json.JSONDecodeError, TypeError):
            total_empty += 1
            continue

        if isinstance(raw, list):
            if not raw:
                total_empty += 1
                continue
            data = raw[0]
        elif isinstance(raw, dict):
            data = raw
        else:
            total_empty += 1
            continue

        feat_rows = parse_features(uid, data, fetched_at)
        meta = parse_meta(uid, data, fetched_at)

        meta_batch.append(meta)
        if feat_rows:
            feature_batch.extend(feat_rows)
            total_processed += 1
        else:
            total_no_regions += 1

        if len(feature_batch) >= 5000 or len(meta_batch) >= 1000:
            _flush(con_main, feature_batch, meta_batch)
            total_inserted += len(feature_batch)
            feature_batch.clear()
            meta_batch.clear()

        if (total_processed + total_no_regions) % 1000 == 0 and (total_processed + total_no_regions) > 0:
            print(f"  [{total_processed + total_no_regions}] procesados, {total_inserted} features insertadas ...")

    if feature_batch or meta_batch:
        _flush(con_main, feature_batch, meta_batch)
        total_inserted += len(feature_batch)

    print()
    print("=== Resultados parse_mobidb_orthologs ===")
    print(f"Con features:        {total_processed}")
    print(f"Sin regiones:        {total_no_regions}")
    print(f"Saltados (ya en DB): {total_skipped_done}")
    print(f"Saltados (no en orthologs): {total_skipped_invalid}")
    print(f"Sin datos en cache:  {total_empty}")
    print(f"Feature rows insertadas: {total_inserted}")

    n_meta = con_main.execute("SELECT COUNT(*) FROM ortholog_meta").fetchone()[0]
    print(f"Registros en ortholog_meta: {n_meta}")

    print("\n--- ortholog_features por tipo y fuente ---")
    for row in con_main.execute(
        "SELECT feature_type, source, COUNT(*) FROM ortholog_features "
        "GROUP BY feature_type, source ORDER BY feature_type, source"
    ):
        print(f"  {row[0]:20s} {row[1]:25s} {row[2]}")

    con_main.close()
    con_cache.close()


def _flush(con: sqlite3.Connection, features: list[tuple], metas: list[dict]) -> None:
    if features:
        con.executemany(
            "INSERT OR IGNORE INTO ortholog_features "
            "(ortholog_id, feature_type, source, label, accession, start, end, score, metadata, fetch_date) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            features,
        )
    if metas:
        con.executemany(
            """INSERT OR REPLACE INTO ortholog_meta
               (ortholog_id, gene_name, protein_name, organism, taxon_id,
                length, disorder_mobidb_lite_dc, disorder_alphafold_dc, sequence, fetch_date)
               VALUES (:ortholog_id, :gene_name, :protein_name, :organism, :taxon_id,
                       :length, :disorder_mobidb_lite_dc, :disorder_alphafold_dc, :sequence, :fetch_date)""",
            metas,
        )
    con.commit()


if __name__ == "__main__":
    main()
