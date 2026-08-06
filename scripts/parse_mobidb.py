#!/usr/bin/env python3
"""
parse_mobidb.py — parsea mobidb_cache.db → sequence_features en mlosmetadb.db

Extrae IDRs, LCDs, MoRFs, pLDDT y DisProt desde el JSON de MobiDB.
"""

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "database" / "mlosmetadb.db"
CACHE_DB = ROOT / "database" / "cache" / "mobidb_cache.db"

# (json_key, feature_type, source, include_content_fraction)
FEATURE_MAP = [
    ("prediction-disorder-mobidb_lite",                     "idr",         "MobiDB-lite",        True),
    ("prediction-disorder-th_50",                           "idr",         "MobiDB-th50",        True),
    ("curated-disorder-disprot",                            "idr_curated", "DisProt",            True),
    ("prediction-low_complexity-seg",                       "lcd",         "SEG",                False),
    ("prediction-low_complexity-mobidb_lite_sub",           "lcd",         "MobiDB-lite-sub",    False),
    ("derived-binding_mode_disorder_to_order-priority",     "morf",        "MobiDB",             True),
    ("prediction-disorder-alphafold",                       "idr",         "AlphaFold-disorder", True),
    ("prediction-plddt-alphafold",                          "plddt_region","AlphaFold",          True),
]

# Sources written by this script — used for idempotency check
MOBIDB_SOURCES = {t[2] for t in FEATURE_MAP}


def parse_mobidb_record(uid: str, data: dict, fetched_at: str) -> list[tuple]:
    rows = []
    for key, feature_type, source, use_cf in FEATURE_MAP:
        if key not in data:
            continue
        block = data[key]
        regions = block.get("regions") or []
        content_fraction = block.get("content_fraction") if use_cf else None

        for region in regions:
            if len(region) < 2:
                continue
            start, end = region[0], region[1]

            metadata: dict = {}
            if content_fraction is not None:
                metadata["content_fraction"] = content_fraction
            if key == "curated-disorder-disprot":
                source_id = block.get("source_id", "")
                if source_id:
                    metadata["source_id"] = source_id

            metadata_str = json.dumps(metadata) if metadata else None

            rows.append((
                uid,
                feature_type,
                source,
                None,      # label — not available in MobiDB regions
                None,      # accession
                start,
                end,
                None,      # score
                metadata_str,
                fetched_at,
            ))
    return rows


def main() -> None:
    con_main = sqlite3.connect(DB)
    con_main.execute("PRAGMA journal_mode=WAL")
    con_cache = sqlite3.connect(CACHE_DB)

    valid_ids = {r[0] for r in con_main.execute("SELECT uniprot_id FROM proteins")}
    print(f"Proteínas en DB: {len(valid_ids)}")

    already_done = {
        r[0]
        for r in con_main.execute(
            f"SELECT DISTINCT uniprot_id FROM sequence_features WHERE source IN ({','.join('?'*len(MOBIDB_SOURCES))})",
            tuple(MOBIDB_SOURCES),
        )
    }
    print(f"Ya procesadas (MobiDB sources): {len(already_done)}")

    total_processed = 0
    total_inserted = 0
    total_skipped_done = 0
    total_skipped_invalid = 0
    total_empty = 0
    total_no_regions = 0

    cur = con_cache.execute("SELECT uniprot_id, response, fetched_at FROM responses WHERE status_code=200")
    batch: list[tuple] = []

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

        # MobiDB response is stored as a list with one element
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

        rows = parse_mobidb_record(uid, data, fetched_at)
        if not rows:
            total_no_regions += 1
        else:
            batch.extend(rows)
            total_processed += 1

        if len(batch) >= 5000:
            con_main.executemany(
                "INSERT OR IGNORE INTO sequence_features "
                "(uniprot_id, feature_type, source, label, accession, start, end, score, metadata, fetch_date) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                batch,
            )
            con_main.commit()
            total_inserted += len(batch)
            batch.clear()

        if (total_processed + total_no_regions) % 500 == 0 and (total_processed + total_no_regions) > 0:
            print(f"  [{total_processed + total_no_regions}] procesadas, {total_inserted} filas insertadas ...")

    if batch:
        con_main.executemany(
            "INSERT OR IGNORE INTO sequence_features "
            "(uniprot_id, feature_type, source, label, accession, start, end, score, metadata, fetch_date) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            batch,
        )
        con_main.commit()
        total_inserted += len(batch)

    print()
    print("=== Resultados parse_mobidb ===")
    print(f"Proteínas con features:   {total_processed}")
    print(f"Sin regiones anotadas:    {total_no_regions}")
    print(f"Saltadas (ya en DB):      {total_skipped_done}")
    print(f"Saltadas (no en proteins):{total_skipped_invalid}")
    print(f"Sin datos en cache:       {total_empty}")
    print(f"Filas insertadas:         {total_inserted}")

    print("\n--- sequence_features por feature_type y source (MobiDB) ---")
    for row in con_main.execute(
        f"SELECT feature_type, source, COUNT(*) FROM sequence_features "
        f"WHERE source IN ({','.join('?'*len(MOBIDB_SOURCES))}) "
        f"GROUP BY feature_type, source ORDER BY feature_type, source",
        tuple(MOBIDB_SOURCES),
    ):
        print(f"  {row[0]:20s} {row[1]:25s} {row[2]}")

    con_main.close()
    con_cache.close()


if __name__ == "__main__":
    main()
