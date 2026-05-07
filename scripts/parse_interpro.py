#!/usr/bin/env python3
"""
parse_interpro.py — parsea interpro_cache.db → sequence_features en mlosmetadb.db

Extrae dominios y familias de Pfam y SMART desde el campo `entries`.

Nota: los sequence_features de InterPro (coils, signal_p, tmhmm, mobidb_lite)
no están disponibles en la versión actual de la API. Esos features vienen de
parse_mobidb.py para IDRs, y de la API de InterPro si se añade soporte futuro.
"""

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "database" / "mlosmetadb.db"
CACHE_DB = ROOT / "database" / "cache" / "interpro_cache.db"

ALLOWED_SOURCES = {"pfam", "smart"}
ALLOWED_TYPES = {"domain", "family"}


def parse_entries(uid: str, entries: list, fetched_at: str) -> list[tuple]:
    rows = []
    for entry in entries:
        meta = entry.get("metadata", {})
        db = (meta.get("source_database") or "").lower()
        entry_type = (meta.get("type") or "").lower()

        if db not in ALLOWED_SOURCES or entry_type not in ALLOWED_TYPES:
            continue

        accession = meta.get("accession")
        name = meta.get("name")
        feature_type = entry_type  # "domain" or "family"

        for protein_match in entry.get("proteins") or []:
            for location in protein_match.get("entry_protein_locations") or []:
                for fragment in location.get("fragments") or []:
                    start = fragment.get("start")
                    end = fragment.get("end")
                    score = fragment.get("score")
                    # dc-status and model in metadata
                    extra = {}
                    if fragment.get("dc-status"):
                        extra["dc_status"] = fragment["dc-status"]
                    if location.get("model"):
                        extra["model"] = location["model"]
                    metadata_str = json.dumps(extra) if extra else None

                    rows.append((
                        uid,
                        feature_type,
                        db,        # "pfam" or "smart"
                        name,      # label
                        accession,
                        start,
                        end,
                        score,
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

    # Proteínas ya procesadas para fuentes interpro (pfam/smart)
    already_done = {
        r[0]
        for r in con_main.execute(
            "SELECT DISTINCT uniprot_id FROM sequence_features WHERE source IN ('pfam', 'smart')"
        )
    }
    print(f"Ya procesadas (pfam/smart): {len(already_done)}")

    total_processed = 0
    total_inserted = 0
    total_skipped_done = 0
    total_skipped_invalid = 0
    total_empty_entries = 0
    total_no_protein = 0

    # Inspect protein structure for first 3 proteins processed
    inspected = 0

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
            data = json.loads(resp_str)
        except (json.JSONDecodeError, TypeError):
            continue

        # Log protein structure for first 3 (as instructed)
        if inspected < 3:
            prot = data.get("protein", {})
            print(f"\n[inspect {inspected+1}] {uid} — protein keys: {list(prot.keys())}")
            ef = prot.get("extra_fields", {})
            if ef:
                print(f"  extra_fields keys: {list(ef.keys())}")
            if "sequence_features" in prot:
                print(f"  sequence_features keys: {list(prot['sequence_features'].keys())}")
            else:
                print("  sequence_features: AUSENTE en protein (no disponible en API actual)")
            inspected += 1

        entries = data.get("entries") or []
        if not entries:
            total_empty_entries += 1
            continue

        rows = parse_entries(uid, entries, fetched_at)
        batch.extend(rows)
        total_processed += 1

        if len(batch) >= 2000:
            con_main.executemany(
                "INSERT OR IGNORE INTO sequence_features "
                "(uniprot_id, feature_type, source, label, accession, start, end, score, metadata, fetch_date) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                batch,
            )
            con_main.commit()
            total_inserted += len(batch)
            batch.clear()

        if total_processed % 500 == 0:
            print(f"  [{total_processed}] procesadas, {total_inserted} filas insertadas ...")

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
    print("=== Resultados parse_interpro ===")
    print(f"Proteínas procesadas:     {total_processed}")
    print(f"Saltadas (ya en DB):      {total_skipped_done}")
    print(f"Saltadas (no en proteins):{total_skipped_invalid}")
    print(f"Sin entries en cache:     {total_empty_entries}")
    print(f"Filas insertadas:         {total_inserted}")

    print("\n--- sequence_features por feature_type y source (fuentes interpro) ---")
    for row in con_main.execute(
        "SELECT feature_type, source, COUNT(*) FROM sequence_features "
        "WHERE source IN ('pfam', 'smart') "
        "GROUP BY feature_type, source ORDER BY feature_type, source"
    ):
        print(f"  {row[0]:20s} {row[1]:15s} {row[2]}")

    con_main.close()
    con_cache.close()


if __name__ == "__main__":
    main()
