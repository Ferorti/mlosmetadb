#!/usr/bin/env python3
"""
fetch_uniprot.py — batch fetch UniProt → uniprot_cache.db y actualiza proteins
"""

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "database" / "mlosmetadb.db"
CACHE_DB = ROOT / "database" / "cache" / "uniprot_cache.db"

FIELDS = (
    "accession,gene_names,protein_name,organism_name,"
    "organism_id,sequence,length,lineage,reviewed"
)
BASE_URL = "https://rest.uniprot.org/uniprotkb/search"
BATCH_SIZE = 100
DELAY = 0.2
MAX_RETRIES = 3


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_with_retry(session: requests.Session, url: str, params: dict) -> requests.Response:
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, params=params, timeout=60)
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = 2 ** attempt
                print(f"  HTTP {resp.status_code}, reintentando en {wait}s ...")
                time.sleep(wait)
                continue
            return resp
        except requests.exceptions.Timeout:
            wait = 2 ** attempt
            print(f"  Timeout, reintentando en {wait}s ...")
            time.sleep(wait)
    return session.get(url, params=params, timeout=60)


def parse_protein(entry: dict) -> dict:
    uid = entry.get("primaryAccession", "")

    genes = entry.get("genes", [])
    gene_name = None
    if genes and "geneName" in genes[0]:
        gene_name = genes[0]["geneName"].get("value")

    protein_name = None
    pd = entry.get("proteinDescription", {})
    rn = pd.get("recommendedName", {})
    if rn:
        protein_name = rn.get("fullName", {}).get("value")
    if not protein_name:
        sn = pd.get("submittedName", [])
        if sn:
            protein_name = sn[0].get("fullName", {}).get("value")

    organism = entry.get("organism", {}).get("scientificName")
    taxon_id = entry.get("organism", {}).get("taxonId")

    seq_obj = entry.get("sequence", {})
    sequence = seq_obj.get("value")
    length = seq_obj.get("length")

    lineage = entry.get("lineages", [])

    entry_type = entry.get("entryType", "")
    reviewed = 1 if entry_type == "UniProtKB reviewed (Swiss-Prot)" else 0

    return {
        "uniprot_id": uid,
        "gene_name": gene_name,
        "protein_name": protein_name,
        "organism": organism,
        "taxon_id": taxon_id,
        "sequence": sequence,
        "length": length,
        "lineage": json.dumps(lineage) if lineage else None,
        "reviewed": reviewed,
        "fetch_date": now(),
    }


def update_protein(con_main: sqlite3.Connection, data: dict) -> None:
    con_main.execute(
        """UPDATE proteins SET
            gene_name=?, protein_name=?, organism=?, taxon_id=?,
            sequence=?, length=?, lineage=?, reviewed=?, fetch_date=?
           WHERE uniprot_id=?""",
        (
            data["gene_name"], data["protein_name"], data["organism"],
            data["taxon_id"], data["sequence"], data["length"],
            data["lineage"], data["reviewed"], data["fetch_date"],
            data["uniprot_id"],
        ),
    )


def main() -> None:
    con_main = sqlite3.connect(DB)
    con_main.execute("PRAGMA foreign_keys = ON")
    con_cache = sqlite3.connect(CACHE_DB)

    all_ids = [r[0] for r in con_main.execute("SELECT uniprot_id FROM proteins")]
    cached = {
        r[0]
        for r in con_cache.execute(
            "SELECT uniprot_id FROM responses WHERE status_code=200"
        )
    }

    pending = [uid for uid in all_ids if uid not in cached]
    print(f"Total proteinas: {len(all_ids)}")
    print(f"Ya en cache:     {len(cached)}")
    print(f"Por fetchear:    {len(pending)}")

    if not pending:
        print("Nada que hacer.")
        con_main.close()
        con_cache.close()
        return

    session = requests.Session()
    session.headers["Accept"] = "application/json"

    batches = [pending[i:i + BATCH_SIZE] for i in range(0, len(pending), BATCH_SIZE)]
    total_ok = 0
    total_err = 0
    fetched_at = now()

    for b_idx, batch in enumerate(batches):
        print(f"Batch {b_idx + 1}/{len(batches)} ({len(batch)} IDs) ...", end=" ", flush=True)
        query = " OR ".join(f"accession:{uid}" for uid in batch)
        params = {"query": query, "fields": FIELDS, "format": "json", "size": 500}

        try:
            resp = fetch_with_retry(session, BASE_URL, params)
        except Exception as exc:
            print(f"ERROR: {exc}")
            for uid in batch:
                con_cache.execute(
                    "INSERT OR IGNORE INTO fetch_errors (uniprot_id, error_type, error_detail, attempted_at) VALUES (?,?,?,?)",
                    (uid, "request_error", str(exc), now()),
                )
            con_cache.commit()
            total_err += len(batch)
            continue

        if resp.status_code != 200:
            print(f"HTTP {resp.status_code}")
            for uid in batch:
                con_cache.execute(
                    "INSERT OR IGNORE INTO fetch_errors (uniprot_id, error_type, error_detail, attempted_at) VALUES (?,?,?,?)",
                    (uid, "http_error", str(resp.status_code), now()),
                )
            con_cache.commit()
            total_err += len(batch)
            time.sleep(DELAY)
            continue

        try:
            data = resp.json()
        except Exception as exc:
            print(f"JSON parse error: {exc}")
            total_err += len(batch)
            time.sleep(DELAY)
            continue

        results = data.get("results", [])
        returned_ids: set[str] = set()

        for entry in results:
            uid = entry.get("primaryAccession", "")
            if not uid:
                continue
            returned_ids.add(uid)
            parsed = parse_protein(entry)

            con_cache.execute(
                "INSERT OR REPLACE INTO responses (uniprot_id, response, fetched_at, status_code) VALUES (?,?,?,?)",
                (uid, json.dumps(entry), fetched_at, 200),
            )
            update_protein(con_main, parsed)
            total_ok += 1

        not_found = set(batch) - returned_ids
        for uid in not_found:
            con_cache.execute(
                "INSERT OR IGNORE INTO fetch_errors (uniprot_id, error_type, error_detail, attempted_at) VALUES (?,?,?,?)",
                (uid, "not_found", "accession not returned by API", now()),
            )
            total_err += 1

        con_cache.commit()
        con_main.commit()
        print(f"ok={len(results)}, not_found={len(not_found)}")
        time.sleep(DELAY)

    print()
    print("=== Resultados ===")
    n_seq = con_main.execute("SELECT COUNT(*) FROM proteins WHERE sequence IS NOT NULL").fetchone()[0]
    n_missing = con_main.execute("SELECT COUNT(*) FROM proteins WHERE sequence IS NULL").fetchone()[0]
    print(f"Fetcheadas con exito: {total_ok}")
    print(f"Errores/no encontradas: {total_err}")
    print(f"proteins con secuencia: {n_seq}")
    print(f"proteins sin secuencia: {n_missing}")

    errs = con_cache.execute(
        "SELECT error_type, COUNT(*) FROM fetch_errors GROUP BY error_type"
    ).fetchall()
    if errs:
        print("Errores por tipo:")
        for etype, cnt in errs:
            print(f"  {etype}: {cnt}")

    con_main.close()
    con_cache.close()


if __name__ == "__main__":
    main()
