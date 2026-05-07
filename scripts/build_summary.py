#!/usr/bin/env python3
"""
build_summary.py — Phase 4 auxiliary table builder.
Run once before starting the API, after all pipeline stages are complete.

Actions:
  1. ALTER TABLE proteins ADD COLUMN disorder_mobidb_lite_dc / disorder_alphafold_dc
  2. Populate disorder columns from mobidb_cache.db
  3. CREATE TABLE protein_summary and populate it
  4. CREATE INDEX on sequence_features(feature_type, source)
"""

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "database" / "mlosmetadb.db"
MOBIDB_CACHE_PATH = ROOT / "database" / "cache" / "mobidb_cache.db"
BATCH_SIZE = 500


# ── Step 1 ────────────────────────────────────────────────────────────────────

def add_disorder_columns(conn: sqlite3.Connection) -> None:
    for col in ("disorder_mobidb_lite_dc", "disorder_alphafold_dc"):
        try:
            conn.execute(f"ALTER TABLE proteins ADD COLUMN {col} REAL")
            print(f"  + column: {col}")
        except sqlite3.OperationalError:
            print(f"  = column exists: {col}")
    conn.commit()


# ── Step 2 ────────────────────────────────────────────────────────────────────

def populate_disorder(conn: sqlite3.Connection, cache_conn: sqlite3.Connection) -> None:
    uids = [r[0] for r in conn.execute("SELECT uniprot_id FROM proteins").fetchall()]

    cache_map = {
        r[0]: r[1]
        for r in cache_conn.execute(
            "SELECT uniprot_id, response FROM responses WHERE status_code=200"
        ).fetchall()
    }

    updates: list[tuple] = []
    null_mobidb = null_alphafold = 0

    for uid in uids:
        raw = cache_map.get(uid)
        mobidb_dc = alphafold_dc = None

        if raw:
            try:
                data = json.loads(raw)
                entry = data[0] if isinstance(data, list) else data

                m = entry.get("prediction-disorder-mobidb_lite")
                if m:
                    mobidb_dc = m.get("content_fraction")

                a = entry.get("prediction-disorder-alphafold")
                if a:
                    alphafold_dc = a.get("content_fraction")
            except Exception:
                pass

        if mobidb_dc is None:
            null_mobidb += 1
        if alphafold_dc is None:
            null_alphafold += 1

        updates.append((mobidb_dc, alphafold_dc, uid))

    conn.executemany(
        "UPDATE proteins SET disorder_mobidb_lite_dc=?, disorder_alphafold_dc=? WHERE uniprot_id=?",
        updates,
    )
    conn.commit()
    print(f"  Updated {len(updates)} proteins")
    print(f"  NULL disorder_mobidb_lite_dc: {null_mobidb}")
    print(f"  NULL disorder_alphafold_dc:   {null_alphafold}")


# ── Step 3 helpers ────────────────────────────────────────────────────────────

def _build_idr_regions(conn: sqlite3.Connection) -> dict[str, dict]:
    # DB source values: 'MobiDB-lite', 'AlphaFold-disorder'
    SOURCE_KEY = {"MobiDB-lite": "mobidb_lite", "AlphaFold-disorder": "alphafold"}
    rows = conn.execute(
        """
        SELECT uniprot_id, source, start, end
        FROM sequence_features
        WHERE feature_type='idr' AND source IN ('MobiDB-lite','AlphaFold-disorder')
        ORDER BY uniprot_id, source, start
        """
    ).fetchall()
    result: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for uid, source, start, end in rows:
        result[uid][SOURCE_KEY[source]].append([start, end])
    return {uid: dict(srcs) for uid, srcs in result.items()}


def _build_lcr_regions(conn: sqlite3.Connection) -> dict[str, dict]:
    # LCD source in DB: 'MobiDB-lite-sub'
    rows = conn.execute(
        """
        SELECT uniprot_id, label, start, end
        FROM sequence_features
        WHERE feature_type='lcd' AND source='MobiDB-lite-sub'
        ORDER BY uniprot_id, start
        """
    ).fetchall()
    result: dict[str, list] = defaultdict(list)
    for uid, label, start, end in rows:
        result[uid].append({"start": start, "end": end, "label": label})
    return {uid: {"mobidb_lite": items} for uid, items in result.items()}


def _build_domains(conn: sqlite3.Connection) -> dict[str, dict]:
    # Domain source in DB: 'pfam', 'smart' (lowercase)
    SOURCE_KEY = {"pfam": "Pfam", "smart": "SMART"}
    rows = conn.execute(
        """
        SELECT uniprot_id, source, label, accession, start, end
        FROM sequence_features
        WHERE feature_type IN ('domain','family') AND source IN ('pfam','smart')
        ORDER BY uniprot_id, source, start
        """
    ).fetchall()
    result: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for uid, source, label, accession, start, end in rows:
        key = SOURCE_KEY[source]
        result[uid][key].append({"start": start, "end": end, "label": label, "accession": accession})
    return {uid: dict(dbs) for uid, dbs in result.items()}


def _build_mlo_aggregates(conn: sqlite3.Connection) -> dict[str, dict]:
    rows = conn.execute(
        """
        SELECT
            uniprot_id,
            MAX(CASE WHEN LOWER(unified_role)='driver' THEN 1 ELSE 0 END) AS has_driver,
            MAX(CASE WHEN LOWER(unified_role)='client' THEN 1 ELSE 0 END) AS has_client,
            COUNT(DISTINCT source_db)  AS source_db_count,
            COUNT(DISTINCT unified_mlo) AS mlo_count,
            GROUP_CONCAT(DISTINCT unified_mlo) AS mlos_concat
        FROM mlo_annotations
        GROUP BY uniprot_id
        """
    ).fetchall()
    result = {}
    for uid, has_driver, has_client, sdb_count, mlo_count, mlos_concat in rows:
        result[uid] = {
            "has_driver": has_driver,
            "has_client": has_client,
            "source_db_count": sdb_count,
            "mlo_count": mlo_count,
            "mlos": sorted(mlos_concat.split(",")) if mlos_concat else [],
        }
    return result


# ── Step 3 main ───────────────────────────────────────────────────────────────

def create_and_populate_summary(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS protein_summary (
            uniprot_id      TEXT PRIMARY KEY,
            idr_regions     TEXT,
            lcr_regions     TEXT,
            domains         TEXT,
            has_driver      INTEGER,
            has_client      INTEGER,
            source_db_count INTEGER,
            mlo_count       INTEGER,
            mlos            TEXT
        )
    """)
    conn.execute("DELETE FROM protein_summary")
    conn.commit()

    print("  Loading feature aggregates...")
    idr_map = _build_idr_regions(conn)
    lcr_map = _build_lcr_regions(conn)
    dom_map = _build_domains(conn)
    mlo_map = _build_mlo_aggregates(conn)

    uids = [r[0] for r in conn.execute("SELECT uniprot_id FROM proteins").fetchall()]
    print(f"  Building {len(uids):,} rows...")

    batch: list[tuple] = []
    for uid in uids:
        idr = idr_map.get(uid)
        lcr = lcr_map.get(uid)
        dom = dom_map.get(uid)
        mlo = mlo_map.get(uid, {})
        batch.append((
            uid,
            json.dumps(idr) if idr else None,
            json.dumps(lcr) if lcr else None,
            json.dumps(dom) if dom else None,
            mlo.get("has_driver", 0),
            mlo.get("has_client", 0),
            mlo.get("source_db_count", 0),
            mlo.get("mlo_count", 0),
            json.dumps(mlo["mlos"]) if mlo.get("mlos") else None,
        ))
        if len(batch) >= BATCH_SIZE:
            conn.executemany("INSERT INTO protein_summary VALUES (?,?,?,?,?,?,?,?,?)", batch)
            batch = []

    if batch:
        conn.executemany("INSERT INTO protein_summary VALUES (?,?,?,?,?,?,?,?,?)", batch)
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM protein_summary").fetchone()[0]
    with_idr = conn.execute("SELECT COUNT(*) FROM protein_summary WHERE idr_regions IS NOT NULL").fetchone()[0]
    with_dom = conn.execute("SELECT COUNT(*) FROM protein_summary WHERE domains IS NOT NULL").fetchone()[0]
    print(f"  Inserted {total:,} rows | with IDR: {with_idr:,} | with domains: {with_dom:,}")


# ── Step 4 ────────────────────────────────────────────────────────────────────

def create_index(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sf_type_source ON sequence_features(feature_type, source)"
    )
    conn.commit()
    print("  Index idx_sf_type_source created")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    for path, name in [(DB_PATH, "mlosmetadb.db"), (MOBIDB_CACHE_PATH, "mobidb_cache.db")]:
        if not path.exists():
            print(f"ERROR: {name} not found at {path}", file=sys.stderr)
            sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cache_conn = sqlite3.connect(MOBIDB_CACHE_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    print("=== Step 1: ALTER TABLE proteins (disorder columns) ===")
    add_disorder_columns(conn)

    print("\n=== Step 2: Populate disorder columns from mobidb_cache ===")
    populate_disorder(conn, cache_conn)

    print("\n=== Step 3: Create and populate protein_summary ===")
    create_and_populate_summary(conn)

    print("\n=== Step 4: Create sequence_features index ===")
    create_index(conn)

    conn.close()
    cache_conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
